from fastapi import APIRouter, Request, Depends, HTTPException, Query
from db.connection import get_single_connection
from db.db_helpers import fetch_one, execute_write
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal

router = APIRouter()

@router.delete("/remove_scanner_bookmark")
async def remove_scanner_bookmark(
    scanner_id: int = Query(..., description="Scanner ID to remove bookmark"),
    request: Request = None,
    user_data=Depends(authorize_user)
):
    try:
        conn = await get_single_connection()

        # Check if bookmark exists
        exists_query = """
            SELECT 1 FROM mt_bookmarked_scanners
            WHERE "userID" = $1 AND "scannerID" = $2
            LIMIT 1
        """
        exists = await fetch_one(exists_query, (user_data["user_id"], scanner_id), conn)
        if not exists:
            await conn.close()
            raise HTTPException(status_code=404, detail="Bookmark not found")

        await execute_write(
            """
            DELETE FROM mt_bookmarked_scanners
            WHERE "userID" = $1 AND "scannerID" = $2
            """,
            (user_data["user_id"], scanner_id),
            conn
        )

        await conn.close()
        return {"message": "Bookmark removed"}

    except Exception as e:
        await notify_internal(f"[Remove Scanner Bookmark Error] {e}")
        raise HTTPException(status_code=500, detail="Failed to remove bookmark")
