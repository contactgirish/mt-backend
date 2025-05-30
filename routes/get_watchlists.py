from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal
from db.connection import get_single_connection
from db.db_helpers import fetch_all

router = APIRouter()

@router.get("/get_watchlists")
async def get_watchlists(request: Request, user_data: dict = Depends(authorize_user)):
    try:
        user_id = user_data["user_id"]
        conn = await get_single_connection()
        rows = await fetch_all(
            "SELECT id, watchlist_name, created_at FROM mt_watchlists WHERE user_id = $1 ORDER BY created_at DESC",
            (user_id,),
            conn
        )
        return ORJSONResponse({"success": True, "watchlists": [dict(row) for row in rows]})
    except Exception as e:
        await notify_internal(f"[GetWatchlists Error] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
