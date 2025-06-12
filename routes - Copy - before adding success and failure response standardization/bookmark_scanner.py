from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from db.connection import get_single_connection
from db.db_helpers import fetch_one, execute_write
from utils.auth import authorize_user
from utils.datetime_utils import utc_now
from utils.telegram_notifier import notify_internal

router = APIRouter()

class BookmarkRequest(BaseModel):
    scanner_id: int

@router.post("/bookmark_scanner")
async def bookmark_scanner(payload: BookmarkRequest, request: Request, user_data=Depends(authorize_user)):
    try:
        conn = await get_single_connection()

        # Check if bookmark already exists
        exists_query = """
            SELECT 1 FROM mt_bookmarked_scanners
            WHERE "userID" = $1 AND "scannerID" = $2
            LIMIT 1
        """
        exists = await fetch_one(exists_query, (user_data["user_id"], payload.scanner_id), conn)
        if exists:
            await conn.close()
            return ORJSONResponse({"success": False, "message": "Already bookmarked"})

        now = utc_now()
        await execute_write(
            """
            INSERT INTO mt_bookmarked_scanners ("userID", "scannerID", created_at)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            (user_data["user_id"], payload.scanner_id, now),
            conn
        )

        await conn.close()
        return ORJSONResponse({"success": True, "message": "Scanner bookmarked"})

    except Exception as e:
        await notify_internal(f"[Bookmark Scanner Error] {e}")
        raise HTTPException(status_code=500, detail="Failed to bookmark scanner")
