from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from utils.auth import authorize_user
from db.connection import get_single_connection
from db.db_helpers import fetch_one, execute_write
from utils.telegram_notifier import notify_internal

router = APIRouter()

class DeleteStockRequest(BaseModel):
    watchlist_id: int
    script_id: int

@router.delete("/delete_stock_from_watchlist")
async def delete_stock_from_watchlist(
    payload: DeleteStockRequest,
    request: Request,
    user_data: dict = Depends(authorize_user)
):
    user_id = user_data["user_id"]
    conn = await get_single_connection()

    try:
        # Step 1: Check if watchlist belongs to user
        wl_check = await fetch_one(
            "SELECT id FROM mt_watchlists WHERE id = $1 AND user_id = $2",
            (payload.watchlist_id, user_id),
            conn
        )
        if not wl_check:
            raise HTTPException(status_code=404, detail="Watchlist not found or doesn't belong to user")

        # Step 2: Check if stock exists in that watchlist
        stock_check = await fetch_one(
            "SELECT id FROM mt_watchlist_stocks WHERE watchlist_id = $1 AND script_id = $2",
            (payload.watchlist_id, payload.script_id),
            conn
        )
        if not stock_check:
            raise HTTPException(status_code=404, detail="Stock not found in the watchlist")

        # Step 3: Perform deletion
        await execute_write(
            "DELETE FROM mt_watchlist_stocks WHERE id = $1",
            (stock_check["id"],),
            conn
        )

        return ORJSONResponse({"success": True, "message": "Stock removed from watchlist"})

    except HTTPException:
        raise
    except Exception as e:
        await notify_internal(f"[Delete Watchlist Stock Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        await conn.close()
