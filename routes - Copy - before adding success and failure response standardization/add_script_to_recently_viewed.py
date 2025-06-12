from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from utils.auth import authorize_user
from utils.datetime_utils import utc_now
from utils.telegram_notifier import notify_internal
from db.connection import get_single_connection
from db.db_helpers import execute_write, fetch_one

router = APIRouter()

class AddRecentlyViewedRequest(BaseModel):
    script_id: int

@router.post("/add_script_to_recently_viewed")
async def add_script_to_recently_viewed(
    payload: AddRecentlyViewedRequest,
    request: Request,
    user=Depends(authorize_user)
):
    try:
        user_id = user["user_id"]
        script_id = payload.script_id
        now = utc_now()

        conn = await get_single_connection()

        # Step 1: Delete existing record if it exists
        delete_query = """
            DELETE FROM mt_recently_viewed_scripts
            WHERE user_id = $1 AND script_id = $2
        """
        await execute_write(delete_query, (user_id, script_id), conn)

        # Step 2: Insert the new view
        insert_query = """
            INSERT INTO mt_recently_viewed_scripts (user_id, script_id, viewed_at)
            VALUES ($1, $2, $3)
        """
        await execute_write(insert_query, (user_id, script_id, now), conn)

        # Step 3: Get view limit from config
        config_row = await fetch_one("SELECT recently_viewed_count FROM mt_config LIMIT 1", (), conn)
        max_count = config_row["recently_viewed_count"] or 20  # fallback default

        # Step 4: Trim old entries beyond config limit
        cleanup_query = f"""
            DELETE FROM mt_recently_viewed_scripts
            WHERE id NOT IN (
                SELECT id FROM mt_recently_viewed_scripts
                WHERE user_id = $1
                ORDER BY viewed_at DESC
                LIMIT {max_count}
            )
            AND user_id = $1
        """
        await execute_write(cleanup_query, (user_id,), conn)

        return ORJSONResponse({"success": True})

    except Exception as e:
        await notify_internal(f"[Recently Viewed Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add script to recently viewed")
