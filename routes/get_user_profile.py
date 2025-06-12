from fastapi import APIRouter, Depends, Request, HTTPException, Query
from db.connection import get_single_connection
from db.db_helpers import fetch_one
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal

router = APIRouter()

@router.get("/get_user_profile")
async def get_user_profile(
    user_id: int = Query(..., description="User ID to fetch profile"),
    request: Request = None,
    payload: dict = Depends(authorize_user)
):
    try:
        conn = await get_single_connection()

        # Fetch user details
        user_query = """
            SELECT email, phone_number, first_name, last_name, is_blocked
            FROM mt_users
            WHERE id = $1
        """
        user = await fetch_one(user_query, (user_id,), conn)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Fetch active subscription
        sub_query = """
            SELECT plan_type, start_date, end_date
            FROM mt_subscriptions
            WHERE user_id = $1 AND is_active = true
            ORDER BY start_date DESC
            LIMIT 1
        """
        subscription = await fetch_one(sub_query, (user_id,), conn)

        await conn.close()

        return {
            "email": user["email"],
            "phone_number": user["phone_number"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "is_blocked": user["is_blocked"],
            "plan_type": subscription["plan_type"] if subscription else None,
            "start_date": subscription["start_date"].isoformat() if subscription else None,
            "end_date": subscription["end_date"].isoformat() if subscription else None
        }

    except HTTPException:
        raise
    except Exception as e:
        await notify_internal(f"[get_user_profile Error] {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
