from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, constr
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal
from db.connection import get_single_connection

router = APIRouter()

class RenameWatchlistRequest(BaseModel):
    watchlist_id: int
    new_name: constr(strip_whitespace=True, min_length=1, max_length=255)

@router.post("/rename_watchlist")
async def rename_watchlist(payload: RenameWatchlistRequest, request: Request, user_data: dict = Depends(authorize_user)):
    try:
        user_id = user_data["user_id"]
        conn = await get_single_connection()

        # Case-insensitive duplicate name check
        existing = await conn.fetchrow(
            "SELECT id FROM mt_watchlists WHERE user_id = $1 AND LOWER(watchlist_name) = LOWER($2)",
            user_id, payload.new_name
        )
        if existing:
            raise HTTPException(status_code=409, detail="Watchlist name already exists")

        result = await conn.execute(
            """
            UPDATE mt_watchlists
            SET watchlist_name = $1
            WHERE id = $2 AND user_id = $3
            """,
            payload.new_name, payload.watchlist_id, user_id
        )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Watchlist not found")

        return ORJSONResponse({"success": True, "message": "Watchlist renamed"})

    except HTTPException as he:
        raise he
    except Exception as e:
        await notify_internal(f"[RenameWatchlist Error] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
