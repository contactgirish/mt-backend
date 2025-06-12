from fastapi import APIRouter, Request, Depends, HTTPException
from db.connection import get_single_connection
from db.db_helpers import fetch_all
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal

router = APIRouter()

@router.get("/get_bookmarked_scanners")
async def get_bookmarked_scanners(request: Request, user_data=Depends(authorize_user)):
    try:
        conn = await get_single_connection()

        query = """
            SELECT s.*
            FROM mt_scanners s
            JOIN mt_bookmarked_scanners b
              ON s."scannerID" = b."scannerID"
            WHERE b."userID" = $1
        """

        records = await fetch_all(query, (user_data["user_id"],), conn)
        await conn.close()

        bookmarked = [dict(row) for row in records]
        return (bookmarked)

    except Exception as e:
        await notify_internal(f"[Get Bookmarked Scanners Error] {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch bookmarked scanners")
