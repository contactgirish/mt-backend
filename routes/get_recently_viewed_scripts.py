from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal
from db.connection import get_single_connection
from db.db_helpers import fetch_all, fetch_one

router = APIRouter()

@router.get("/get_recently_viewed_scripts")
async def get_recently_viewed_scripts(request: Request, user=Depends(authorize_user)):
    try:
        user_id = user["user_id"]
        conn = await get_single_connection()

        config_row = await fetch_one("SELECT recently_viewed_count FROM mt_config LIMIT 1", (), conn)
        max_count = config_row["recently_viewed_count"] or 20  # fallback

        query = f"""
            SELECT s.script_id, s.co_code, s.companyname, s.companyshortname,
                   s.latest_price, s.changed_percentage, s.exchange, s.company_size
            FROM mt_recently_viewed_scripts rv
            JOIN script_master s ON rv.script_id = s.script_id
            WHERE rv.user_id = $1
            ORDER BY rv.viewed_at DESC
            LIMIT {max_count}
        """

        rows = await fetch_all(query, (user_id,), conn)
        return ORJSONResponse([dict(row) for row in rows])

    except Exception as e:
        await notify_internal(f"[Get Recently Viewed Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve recently viewed scripts")
