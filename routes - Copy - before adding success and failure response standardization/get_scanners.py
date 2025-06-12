from fastapi import APIRouter, Request, Depends
from fastapi.responses import ORJSONResponse
from db.connection import get_single_connection
from db.db_helpers import fetch_all
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal

router = APIRouter()

@router.get("/get_scanners")
async def get_scanners(request: Request, user_data=Depends(authorize_user)):
    try:
        conn = await get_single_connection()
        query = "SELECT * FROM mt_scanners"
        records = await fetch_all(query, (), conn)
        await conn.close()

        scanners = [dict(record) for record in records]
        return ORJSONResponse(scanners)

    except Exception as e:
        await notify_internal(f"[get_scanners Error] {e}")
        return ORJSONResponse(
            status_code=500,
            content={"success": False, "message": "Failed to fetch scanners"}
        )
