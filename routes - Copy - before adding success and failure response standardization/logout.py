from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from utils.jwt_utils import decode_jwt_token
from db.connection import get_single_connection
from utils.datetime_utils import utc_now
from utils.telegram_notifier import notify_internal

router = APIRouter()

class LogoutRequest(BaseModel):
    token: str

@router.post("/logout")
async def logout_user(payload: LogoutRequest, request: Request):
    try:
        token = payload.token
        decoded = decode_jwt_token(token, expect_type="access")
        user_id = decoded.get("user_id")
        iat = decoded.get("iat")

        if not user_id or not iat:
            raise HTTPException(status_code=400, detail="Invalid token")

        conn = await get_single_connection()
        now = utc_now()

        await conn.execute(
            "UPDATE mt_users SET jwt_exp = $1, updated_at = now() WHERE id = $2",
            now, user_id
        )

        return ORJSONResponse({"success": True, "message": "Logged out successfully"})

    except Exception as e:
        await notify_internal(f"[Logout Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to logout")
