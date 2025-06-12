from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from utils.auth import authorize_user
from utils.datetime_utils import utc_now
from utils.telegram_notifier import notify_internal
from db.connection import get_single_connection
from db.db_helpers import fetch_one, execute_write

router = APIRouter()

class AddStockToWatchlistRequest(BaseModel):
    watchlist_id: int
    script_id: int

@router.post("/add_stock_to_watchlist")
async def add_stock_to_watchlist(
    payload: AddStockToWatchlistRequest,
    request: Request,
    user_data: dict = Depends(authorize_user)
):
    user_id = user_data["user_id"]

    if not payload.watchlist_id or not payload.script_id:
        raise HTTPException(status_code=400, detail="watchlist_id and script_id are required")

    conn = await get_single_connection()
    try:
        # Check watchlist belongs to user
        watchlist = await fetch_one(
            "SELECT id FROM mt_watchlists WHERE id = $1 AND user_id = $2",
            (payload.watchlist_id, user_id),
            conn
        )
        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found or unauthorized")

        # Subscription logic for free users
        subscription = await fetch_one(
            "SELECT plan_type FROM mt_subscriptions WHERE user_id = $1 AND is_active = true",
            (user_id,),
            conn
        )
        if subscription and subscription["plan_type"].lower() == "free":
            config = await fetch_one(
                "SELECT number_of_stocks_in_watchlist_for_free_users FROM mt_config", (), conn
            )
            max_allowed = config["number_of_stocks_in_watchlist_for_free_users"]

            count_row = await fetch_one(
                "SELECT COUNT(*) AS total FROM mt_watchlist_stocks WHERE watchlist_id = $1",
                (payload.watchlist_id,),
                conn
            )
            if count_row["total"] >= max_allowed:
                raise HTTPException(
                    status_code=403,
                    detail=f"Free users can add only up to {max_allowed} stocks in a watchlist."
                )

        # Check if script exists
        script_row = await fetch_one(
            "SELECT latest_price FROM script_master WHERE script_id = $1",
            (payload.script_id,),
            conn
        )
        if not script_row:
            raise HTTPException(status_code=404, detail="Script ID not found in script_master")

        # Prevent duplicates
        existing = await fetch_one(
            "SELECT id FROM mt_watchlist_stocks WHERE watchlist_id = $1 AND script_id = $2",
            (payload.watchlist_id, payload.script_id),
            conn
        )
        if existing:
            raise HTTPException(status_code=409, detail="Script already exists in this watchlist")

        # Insert into watchlist
        now = utc_now()
        await execute_write(
            """
            INSERT INTO mt_watchlist_stocks (watchlist_id, script_id, added_price, added_date)
            VALUES ($1, $2, $3, $4)
            """,
            (payload.watchlist_id, payload.script_id, script_row["latest_price"], now),
            conn
        )

        # Insert audit log in history table
        await execute_write(
            """
            INSERT INTO mt_watchlist_history (user_id, watchlist_id, script_id, action, action_date, price)
            VALUES ($1, $2, $3, 'added', $4, $5)
            """,
            (user_id, payload.watchlist_id, payload.script_id, now, script_row["latest_price"]),
            conn
        )

        return ({"success": True, "message": "Stock added to watchlist"})

    except HTTPException:
        raise
    except Exception as e:
        await notify_internal(f"[AddStockToWatchlist Error] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        await conn.close()
