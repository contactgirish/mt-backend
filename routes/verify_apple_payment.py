from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
from db.connection import get_single_connection
from db.db_helpers import execute_write, fetch_one
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal
from utils.payment_calculator import calculate_final_price

router = APIRouter()

class ApplePaymentRequest(BaseModel):
    payment_id: str
    receipt: str
    amount: float
    email: Optional[str]
    contact: Optional[str]
    plan_id: int
    promocode: Optional[str] = None

def utc_today():
    return datetime.now(timezone.utc).date()

@router.post("/verify_apple_payment")
async def verify_apple_payment(payload: ApplePaymentRequest, user_data: dict = Depends(authorize_user)):
    conn = await get_single_connection()
    try:
        user_id = user_data["user_id"]
        today = utc_today()

        # ✅ Step 1: Get plan_type from DB (plan_name)
        plan_row = await fetch_one(
            "SELECT plan_name FROM mt_subscription_master WHERE id = $1",
            (payload.plan_id,),
            conn
        )
        if not plan_row:
            raise HTTPException(status_code=404, detail="Invalid plan ID")

        plan_type = plan_row["plan_name"]

        # ✅ Step 2: Validate promocode logic
        result = await calculate_final_price(
            payload.plan_id,
            payload.promocode,
            conn,
            plan_type
        )

        await execute_write("""
            INSERT INTO mt_transactions (
                user_id, payment_id, razorpay_order_id, razorpay_signature,
                amount, currency, email, contact, payment_status, payment_type,
                receipt, promocode, notes
            ) VALUES ($1,$2,NULL,NULL,$3,$4,$5,$6,'captured','Apple',$7,$8,$9)
        """, (
            user_id,
            payload.payment_id,
            result["final_price"],
            "INR",
            payload.email,
            payload.contact,
            payload.receipt,
            payload.promocode,
            "{}"
        ), conn)

        # ✅ Deactivate old subscriptions
        await execute_write("UPDATE mt_subscriptions SET is_active = FALSE WHERE user_id = $1 AND is_active = TRUE", (user_id,), conn)

        # ✅ Create new active subscription
        await execute_write("""
            INSERT INTO mt_subscriptions (
                user_id, plan_id, plan_type, start_date, end_date,
                created_at, is_active, payment_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, TRUE, $7)
        """, (
            user_id,
            payload.plan_id,
            result["plan_name"],
            today,
            today + timedelta(days=result["duration_days"]),
            today,
            payload.payment_id
        ), conn)

        await notify_internal(f"[🍎 Apple Verified] UID {user_id}, ₹{result['final_price']}")
        return {"amount": result["final_price"]}

    except ValueError as ve:
        await notify_internal(f"[❌ Apple Verify Error] {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await notify_internal(f"[❌ Apple Verify Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Apple payment verification failed")
    finally:
        await conn.close()
