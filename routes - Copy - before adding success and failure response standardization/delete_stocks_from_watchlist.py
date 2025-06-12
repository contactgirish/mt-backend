from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from utils.auth import authorize_user
from db.connection import get_db
from db.db_helpers import execute_write, fetch_one
from utils.telegram_notifier import notify_internal
from utils.datetime_utils import utc_now
import asyncpg

router = APIRouter()

class DeleteWatchlistStocksRequest(BaseModel):
    user_id: int
    watchlist_id: int
    script_ids: List[int]

@router.delete("/delete_stock_from_watchlist")
async def delete_stock_from_watchlist(
    payload: DeleteWatchlistStocksRequest,
    token_data: dict = Depends(authorize_user),
    conn: asyncpg.Connection = Depends(get_db)
):
    try:
        user_id = token_data["user_id"]
        if user_id != payload.user_id:
            raise HTTPException(status_code=403, detail="Permission denied")

        if not payload.script_ids:
            raise HTTPException(status_code=400, detail="No script_ids provided")

        # Validate watchlist
        result = await conn.fetchrow(
            "SELECT id FROM mt_watchlists WHERE id = $1 AND user_id = $2",
            (payload.watchlist_id, payload.user_id)
        )
        if not result:
            raise HTTPException(status_code=404, detail="Watchlist not found for this user")

        # For each script to be deleted, fetch existing data and log it
        now = utc_now()
        deleted_count = 0

        for script_id in payload.script_ids:
            # Check if exists in watchlist
            existing = await fetch_one(
                "SELECT added_date, added_price FROM mt_watchlist_stocks WHERE watchlist_id = $1 AND script_id = $2",
                (payload.watchlist_id, script_id),
                conn
            )
            if not existing:
                continue  # skip nonexistent entries

            # Get current price
            script = await fetch_one(
                "SELECT latest_price FROM script_master WHERE script_id = $1",
                (script_id,),
                conn
            )
            if not script:
                continue

            holding_days = (now - existing["added_date"]).days

            # Log deletion in history
            await execute_write(
                """
                INSERT INTO mt_watchlist_history (
                    user_id, watchlist_id, script_id, action, action_date, price, holding_duration_days
                ) VALUES ($1, $2, $3, 'removed', $4, $5, $6)
                """,
                (user_id, payload.watchlist_id, script_id, now, script["latest_price"], holding_days),
                conn
            )

            deleted_count += 1

        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="No valid scripts to delete")

        # Bulk delete
        delete_query = """
            DELETE FROM mt_watchlist_stocks
            WHERE watchlist_id = $1 AND script_id = ANY($2::int[])
        """
        await execute_write(delete_query, (payload.watchlist_id, payload.script_ids), conn)

        return {
            "status": "success",
            "message": f"{deleted_count} stock(s) deleted from watchlist"
        }

    except Exception as e:
        await notify_internal(f"[❌ Delete Watchlist Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
