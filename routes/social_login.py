from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr
from db.connection import get_single_connection
from utils.jwt_utils import create_jwt_token
from utils.telegram_notifier import notify_internal
from utils.auth_providers import verify_google_token, verify_apple_token
from utils.version_utils import determine_update_type
from utils.datetime_utils import utc_now, utc_in
import traceback
from typing import Optional

router = APIRouter()

class SocialLoginRequest(BaseModel):
    platform: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    appversion: str
    provider_user_id: str

@router.post("/social_login")
async def social_login(payload: SocialLoginRequest, request: Request):
    try:
        print(f"[LOG] Login Attempt: {payload.dict()}")

        platform = payload.platform.lower()
        if platform not in ["google", "apple"]:
            raise HTTPException(status_code=400, detail="Unsupported platform")

        phone_number = payload.phone_number or None
        conn = await get_single_connection()
        now = utc_now()
        access_exp = utc_in(days=30)

        update_type = await determine_update_type(conn, platform, payload.appversion)

        select_query = """
            SELECT id, is_blocked FROM mt_users
            WHERE (email = $1 AND $1 IS NOT NULL)
               OR (provider_user_id = $2 AND provider = $3)
            LIMIT 1
        """
        result = await conn.fetchrow(select_query, payload.email, payload.provider_user_id, platform)

        is_new_user = False

        if result:
            user_id = result["id"]
            if result["is_blocked"]:
                try:
                    await notify_internal(f"[Blocked Login Attempt] User ID {user_id} tried to log in.")
                except Exception as te:
                    print(f"[Telegram Notify Failed] {te}")
                    raise HTTPException(status_code=403, detail="User account is blocked. Please contact support.")

            await conn.execute(
                "UPDATE mt_users SET jwt_iat = $1, jwt_exp = $2 WHERE id = $3",
                now, access_exp, user_id
            )

        else:
            is_new_user = True
            insert_query = """
                INSERT INTO mt_users (
                    email, phone_number, first_name, last_name, provider, provider_user_id,
                    jwt_iat, jwt_exp, created_at, monk_ai_views, is_blocked, is_deleted
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8, now(), 0, false, false)
                RETURNING id
            """
            try:
                row = await conn.fetchrow(
                    insert_query,
                    payload.email,
                    phone_number,
                    payload.firstname,
                    payload.lastname,
                    platform,
                    payload.provider_user_id,
                    now,
                    access_exp
                )
            except Exception as db_exc:
                await notify_internal(f"[DB Insert Error] {db_exc}\n{traceback.format_exc()}")
                raise HTTPException(status_code=500, detail="Failed to create user in database.")

            if not row or "id" not in row:
                await notify_internal("[DB Insert Error] Insert succeeded but no row returned.")
                raise HTTPException(status_code=500, detail="User creation failed.")                    

            user_id = row["id"]

            # Insert default subscription for new users
            start_date = now
            end_date = utc_in(days=365 * 10)
            await conn.execute(
                """
                INSERT INTO mt_subscriptions (user_id, plan_type, start_date, end_date, created_at)
                VALUES ($1, 'FREE', $2, $3, $4)
                """,
                user_id, start_date, end_date, now
            )

        access_token = create_jwt_token(user_id=user_id, iat=now, exp=access_exp)

        return {
            "access_token": access_token,
            "expires_in": 60 * 60 * 24 * 30,
            "user_id": user_id,
            "isNewUser": is_new_user,
            "update_type": update_type
        }

    except Exception as e:
        print("[EXCEPTION CAUGHT] Sending to Telegram...")
        try:
            await notify_internal(f"[Login Error] {e}\n{traceback.format_exc()}")
        except Exception as te:
            print(f"[Telegram Notify Failed] {te}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")