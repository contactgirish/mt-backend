from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, EmailStr
from utils.auth import authorize_user
from db.connection import get_single_connection
from db.db_helpers import fetch_one, execute_write
from utils.telegram_notifier import notify_internal

router = APIRouter()

class UserProfileUpdateRequest(BaseModel):
    email: EmailStr
    phone_number: str
    first_name: str
    last_name: str

@router.get("/get_user_profile")
async def get_user_profile(request: Request, payload: dict = Depends(authorize_user)):
    try:
        user_id = payload["user_id"]
        conn = await get_single_connection()

        profile_query = """
            SELECT u.email, u.phone_number, u.first_name, u.last_name,
                   s.plan_type, s.start_date, s.end_date
            FROM mt_users u
            LEFT JOIN mt_subscriptions s ON u.id = s.user_id
            WHERE u.id = $1
            LIMIT 1
        """
        user_data = await fetch_one(profile_query, (user_id,), conn)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        return ORJSONResponse(dict(user_data))

    except Exception as e:
        await notify_internal(f"[Get Profile Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch profile")

@router.post("/update_user_profile")
async def update_user_profile(payload: UserProfileUpdateRequest, request: Request, token_data: dict = Depends(authorize_user)):
    try:
        user_id = token_data["user_id"]
        conn = await get_single_connection()

        update_query = """
            UPDATE mt_users
            SET email = $1,
                phone_number = $2,
                first_name = $3,
                last_name = $4,
                updated_at = now()
            WHERE id = $5
        """
        await execute_write(update_query, (
            payload.email,
            payload.phone_number,
            payload.first_name,
            payload.last_name,
            user_id
        ), conn)

        return ORJSONResponse({"success": True, "message": "Profile updated"})

    except Exception as e:
        await notify_internal(f"[Update Profile Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update profile")
