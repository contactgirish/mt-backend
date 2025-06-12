from fastapi import APIRouter, Depends, HTTPException
from utils.auth import authorize_user
from db.connection import get_db
from db.db_helpers import fetch_all
from utils.telegram_notifier import notify_internal

router = APIRouter()

@router.get("/get_technical_info")
async def get_technical_info(user=Depends(authorize_user), conn=Depends(get_db)):
    try:
        query = """
            SELECT indicator, indicator_type, indicator_description
            FROM mt_technical_info
            ORDER BY id
        """
        rows = await fetch_all(query, (), conn)
        return {"technical_info": [dict(row) for row in rows]}
    except Exception as e:
        await notify_internal(f"[Get Technical Info Error] {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch technical info.")
