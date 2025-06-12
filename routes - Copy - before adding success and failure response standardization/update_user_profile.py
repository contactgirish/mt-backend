from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, EmailStr
from db.connection import get_single_connection
from db.db_helpers import execute_write
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal
from utils.datetime_utils import utc_now
from utils.user_blocklist import is_user_blocked

router = APIRouter()

class UpdateUserProfileRequest(BaseModel):
    email: EmailStr | None = None
    phone_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None

@router.post("/update_user_profile")
async def update_user_profile(
    payload: UpdateUserProfileRequest,
    request: Request,
    token_payload: dict = Depends(authorize_user)
):
    try:
        user_id = token_payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        if is_user_blocked(user_id):
            raise HTTPException(status_code=403, detail="User is blocked")

        update_fields = []
        values = []

        if payload.email is not None:
            update_fields.append("email = $%d" % (len(values) + 1))
            values.append(payload.email)

        if payload.phone_number is not None:
            update_fields.append("phone_number = $%d" % (len(values) + 1))
            values.append(payload.phone_number)

        if payload.first_name is not None:
            update_fields.append("first_name = $%d" % (len(values) + 1))
            values.append(payload.first_name)

        if payload.last_name is not None:
            update_fields.append("last_name = $%d" % (len(values) + 1))
            values.append(payload.last_name)

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Add updated_at timestamp
        update_fields.append("updated_at = $%d" % (len(values) + 1))
        values.append(utc_now())

        # Final user_id for WHERE clause
        values.append(user_id)

        query = f"""
            UPDATE mt_users
            SET {", ".join(update_fields)}
            WHERE id = ${len(values)}
        """

        conn = await get_single_connection()
        await execute_write(query, tuple(values), conn)
        await conn.close()

        return ORJSONResponse({"success": True, "message": "Profile updated successfully"})

    except HTTPException:
        raise
    except Exception as e:
        await notify_internal(f"[update_user_profile Error] {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
