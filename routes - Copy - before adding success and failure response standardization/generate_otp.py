from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, EmailStr
from db.connection import get_single_connection
from db.db_helpers import fetch_one, execute_write
from utils.telegram_notifier import notify_internal
from utils.version_utils import determine_update_type
from utils.datetime_utils import utc_now, utc_in
import random
import aiohttp
import os
from utils.response_builder import success_response, error_response

router = APIRouter()
SPARKPOST_API_KEY = os.getenv("SPARKPOST_API_KEY")

class GenerateOtpRequest(BaseModel):
    email: EmailStr
    appversion: str
    platform: str

@router.post("/generate_otp")
async def generate_otp(payload: GenerateOtpRequest, request: Request):
    try:
        email = payload.email.lower()
        now = utc_now()
        expires_at = utc_in(minutes=5)

        conn = await get_single_connection()

        user_row = await conn.fetchrow("SELECT id, is_blocked FROM mt_users WHERE email = $1", email)
        if user_row and user_row["is_blocked"]:
            await notify_internal(f"[Blocked OTP Attempt] Email: {email}")
            return error_response(message="Sorry, the user id is blocked.", status_code=403)

        recent_otp = await conn.fetchrow(
            "SELECT * FROM mt_otps WHERE email = $1 ORDER BY created_at DESC LIMIT 1",
            email
        )
        if recent_otp:
            if (now - recent_otp["last_sent_at"]).total_seconds() < 60:
                return error_response(message="Please wait before requesting another OTP", status_code=403)

            if recent_otp["attempt_count"] >= 3:
                return error_response(message="OTP request limit exceeded.", status_code=429)

        otp = f"{random.randint(100000, 999999)}"
        if recent_otp:
            await conn.execute(
                """
                UPDATE mt_otps
                SET otp = $1, expires_at = $2, is_valid = true,
                    last_sent_at = $3, attempt_count = attempt_count + 1
                WHERE id = $4
                """,
                otp, expires_at, now, recent_otp["id"]
            )
        else:
            await conn.execute(
                """
                INSERT INTO mt_otps (email, otp, created_at, expires_at, attempt_count, last_sent_at, is_valid)
                VALUES ($1, $2, $3, $4, 1, $3, true)
                """,
                email, otp, now, expires_at
            )

        await send_otp_email(email, otp)
        update_type = await determine_update_type(conn, payload.platform, payload.appversion)
	        return success_response(
            data={"updateType": update_type},
            message="OTP sent successfully",
            status_code=200
        )

    except Exception as e:
        await notify_internal(f"[Generate OTP Error] {str(e)}")
        return error_response(message="Internal Server Error", status_code=500)

async def send_otp_email(email: str, otp_code: str):
    api_url = "https://api.sparkpost.com/api/v1/transmissions"
    
    html_template = f"""
    <div style='background-color: #f5f7fa; padding: 24px; font-family: "Segoe UI", Roboto, sans-serif;'>
      <div style='max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 32px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05); border: 1px solid #e2e8f0;'>

        <div style='text-align: center; margin-bottom: 20px;'>
          <img src='https://static.ygfintech.in/images/mt_logo_only.png' alt='MonkTrader' width='50'>
        </div>

        <p style='font-size: 18px; color: #444; text-align: center; margin: 0 0 12px;'>Your OTP is:</p>

        <div style='text-align: center; margin-bottom: 30px;'>
          <span style='
            display: inline-block;
            font-size: 30px;
            font-family: "Segoe UI", Roboto, sans-serif;
            font-weight: bold;
            background-color: #f0f0f0;
            color: #000000;
            padding: 12px 20px;
            border-radius: 8px;
            letter-spacing: 4px;
            border: 1px solid #ccc;
            max-width: 90%;
            word-break: break-word;'>
            {otp_code}
          </span>
        </div>

        <p style='text-align: center; font-size: 18px; color: #2C3098; margin-bottom: 8px;'>
          Welcome to MonkTrader.ai
        </p>

        <p style='text-align: center; font-size: 16px; color: #444; font-weight: 500; margin-top: 0; margin-bottom: 30px;'>
          Let's start building Wealth
        </p>

        <p style='font-size: 14px; color: #444; margin-bottom: 18px;'>
          Please use the OTP code above to complete your verification. It is valid for the next <strong>5 minutes</strong>.
        </p>
        <p style='font-size: 14px; color: #444; margin-bottom: 24px;'>
          If you did not request this code, please ignore this email or contact us at
          <a href='mailto:support@monktrader.ai' style='color: #0056D2;'>support@monktrader.ai</a>.
        </p>

        <hr style='border: none; border-top: 1px solid #e0e0e0; margin: 32px 0;'>

        <p style='font-size: 14px; color: #888; text-align: center;'>
          Thank you for joining us,<br><strong>The MonkTrader Team</strong>
        </p>
      </div>
    </div>
    """

    payload = {
        "content": {
            "from": {
                "email": "txn@notifications.monktrader.in",
                "name": "MonkTrader"
            },
            "subject": f"MonkTrader OTP: {otp_code}",
            "html": html_template,
        },
        "recipients": [{"address": email}]
    }

    headers = {
        "Authorization": SPARKPOST_API_KEY,
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, json=payload, headers=headers, timeout=10) as resp:
            if resp.status != 200:
                error_msg = await resp.text()
                return error_response(message=f"Failed to send OTP email. Status {resp.status}: {error_msg}", status_code=429)
