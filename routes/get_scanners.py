from fastapi import APIRouter, Request, Depends
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
        return {"scanners": scanners}

    except Exception as e:
        await notify_internal(f"[get_scanners Error] {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch scanners")