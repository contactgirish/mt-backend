from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import ORJSONResponse
from db.connection import get_single_connection
from db.db_helpers import fetch_all
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal

router = APIRouter()

@router.get("/get_top_scanners")
async def get_top_scanners(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_data=Depends(authorize_user)
):
    try:
        conn = await get_single_connection()

        query = f"""
            SELECT s.*, top.bookmark_count
            FROM mt_scanners s
            JOIN (
                SELECT "scannerID", COUNT(*) AS bookmark_count
                FROM mt_bookmarked_scanners
                GROUP BY "scannerID"
                ORDER BY bookmark_count DESC
                LIMIT {limit} OFFSET {offset}
            ) top ON s."scannerID" = top."scannerID"
            ORDER BY top.bookmark_count DESC
        """

        records = await fetch_all(query, (), conn)
        await conn.close()

        top_scanners = [dict(row) for row in records]
        return ORJSONResponse(top_scanners)

    except Exception as e:
        await notify_internal(f"[Get Top Scanners Error] {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch top scanners")
