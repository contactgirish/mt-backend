from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from db.connection import get_single_connection
from db.db_helpers import fetch_one, execute_write
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal

router = APIRouter()

class BookmarkRequest(BaseModel):
    scanner_id: int

@router.post("/remove_scanner_bookmark")
async def remove_scanner_bookmark(payload: BookmarkRequest, request: Request, user_data=Depends(authorize_user)):
    try:
        conn = await get_single_connection()

        # Check if bookmark exists
        exists_query = """
            SELECT 1 FROM mt_bookmarked_scanners
            WHERE "userID" = $1 AND "scannerID" = $2
            LIMIT 1
        """
        exists = await fetch_one(exists_query, (user_data["user_id"], payload.scanner_id), conn)
        if not exists:
            await conn.close()
            return ORJSONResponse({"success": False, "message": "Bookmark not found"})

        await execute_write(
            """
            DELETE FROM mt_bookmarked_scanners
            WHERE "userID" = $1 AND "scannerID" = $2
            """,
            (user_data["user_id"], payload.scanner_id),
            conn
        )

        await conn.close()
        return ORJSONResponse({"success": True, "message": "Bookmark removed"})

    except Exception as e:
        await notify_internal(f"[Remove Scanner Bookmark Error] {e}")
        raise HTTPException(status_code=500, detail="Failed to remove bookmark")
