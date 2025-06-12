from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, EmailStr
from db.connection import get_single_connection
from utils.jwt_utils import create_jwt_token
from utils.telegram_notifier import notify_internal
from utils.datetime_utils import utc_now, utc_in

router = APIRouter()

class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str

@router.post("/verify_otp")
async def verify_otp(payload: VerifyOtpRequest, request: Request):
    try:
        email = payload.email.lower()
        otp = payload.otp.strip()
        now = utc_now()
        access_exp = utc_in(days=30)

        conn = await get_single_connection()

        row = await conn.fetchrow(
            """
            SELECT * FROM mt_otps
            WHERE email = $1 AND otp = $2 AND is_valid = true AND expires_at > $3
            ORDER BY created_at DESC LIMIT 1
            """,
            email, otp, now
        )

        if not row:
            return ORJSONResponse(
                status_code=401,
                content={"success": False, "message": "Invalid or expired OTP"}
            )

        await conn.execute("UPDATE mt_otps SET is_valid = false WHERE id = $1", row["id"])

        user_row = await conn.fetchrow("SELECT id FROM mt_users WHERE email = $1", email)
        is_new_user = False

        if user_row:
            user_id = user_row["id"]
        else:
            is_new_user = True
            insert_query = """
                INSERT INTO mt_users (
                    email, phone_number, first_name, last_name, provider, provider_user_id,
                    jwt_iat, jwt_exp, created_at, updated_at, monk_ai_views, is_blocked, is_deleted
                )
                VALUES ($1, NULL, NULL, NULL, 'email', NULL, $2, $3, now(), now(), 0, false, false)
                RETURNING id
            """
            row = await conn.fetchrow(insert_query, email, now, access_exp)
            user_id = row["id"]

            # Insert FREE subscription for new user
            start_date = now
            end_date = utc_in(days=365 * 10)  # 10 years
            await conn.execute(
                """
                INSERT INTO mt_subscriptions (
                    user_id, plan_type, start_date, end_date, created_at
                )
                VALUES ($1, 'FREE', $2, $3, $4)
                """,
                user_id, start_date, end_date, now
            )

        access_token = create_jwt_token(user_id=user_id, iat=now, exp=access_exp)

        return ORJSONResponse({
            "success": True,
            "access_token": access_token,
            "expires_in": 60 * 60 * 24 * 30,  # 30 days
            "user_id": user_id,
            "newuser": is_new_user
        })

    except Exception as e:
        await notify_internal(f"[Verify OTP Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
