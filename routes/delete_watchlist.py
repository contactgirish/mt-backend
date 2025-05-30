from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal
from db.connection import get_single_connection

router = APIRouter()

class DeleteWatchlistRequest(BaseModel):
    watchlist_id: int

@router.post("/delete_watchlist")
async def delete_watchlist(payload: DeleteWatchlistRequest, request: Request, user_data: dict = Depends(authorize_user)):
    try:
        user_id = user_data["user_id"]
        conn = await get_single_connection()

        result = await conn.execute(
            "DELETE FROM mt_watchlists WHERE id = $1 AND user_id = $2",
            payload.watchlist_id, user_id
        )

        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Watchlist not found")

        return ORJSONResponse({"success": True, "message": "Watchlist deleted"})

    except HTTPException as he:
        raise he
    except Exception as e:
        await notify_internal(f"[DeleteWatchlist Error] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
