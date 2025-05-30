from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
import hmac
import hashlib
import os
from db.connection import get_single_connection
from db.db_helpers import fetch_one, execute_write
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal
from utils.payment_calculator import calculate_final_price

router = APIRouter()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

class VerifyPaymentRequest(BaseModel):
    payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    amount: float
    email: Optional[str]
    contact: Optional[str]
    promocode: Optional[str] = None

def utc_today():
    return datetime.now(timezone.utc).date()

@router.post("/razorpay_verify_payment")
async def razorpay_verify_payment(payload: VerifyPaymentRequest, user_data: dict = Depends(authorize_user)):
    conn = await get_single_connection()
    try:
        user_id = user_data["user_id"]

        order = await fetch_one(
            "SELECT * FROM mt_payment_orders WHERE razorpay_order_id = $1 AND user_id = $2",
            (payload.razorpay_order_id, user_id),
            conn
        )

        if not order or float(order["amount"]) != float(payload.amount):
            raise HTTPException(status_code=400, detail="Amount mismatch or order not found")

        # ✅ Step 1: Verify Razorpay signature
        body_str = f"{payload.razorpay_order_id}|{payload.payment_id}"
        expected = hmac.new(RAZORPAY_KEY_SECRET.encode(), body_str.encode(), hashlib.sha256).hexdigest()
        if expected != payload.razorpay_signature:
            raise HTTPException(status_code=400, detail="Invalid payment signature")

        # ✅ Step 2: Fetch plan_name as plan_type
        plan_row = await fetch_one(
            "SELECT plan_name FROM mt_subscription_master WHERE id = $1",
            (order["plan_id"],),
            conn
        )
        if not plan_row:
            raise HTTPException(status_code=404, detail="Invalid plan ID")

        plan_type = plan_row["plan_name"]

        # ✅ Step 3: Calculate final price with promocode
        result = await calculate_final_price(
            plan_id=order["plan_id"],
            promocode=payload.promocode,
            conn=conn,
            plan_type=plan_type
        )

        # ✅ Step 4: Store transaction
        await execute_write("""
            INSERT INTO mt_transactions (
                user_id, payment_id, razorpay_order_id, razorpay_signature,
                amount, currency, email, contact, payment_status, payment_type,
                receipt, promocode, notes
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'captured','Razorpay',NULL,$9,$10)
        """, (
            user_id,
            payload.payment_id,
            payload.razorpay_order_id,
            payload.razorpay_signature,
            result["final_price"],
            "INR",
            payload.email,
            payload.contact,
            payload.promocode,
            "{}"
        ), conn)

        # ✅ Step 5: Mark order as paid
        await execute_write(
            "UPDATE mt_payment_orders SET status = 'paid' WHERE razorpay_order_id = $1",
            (payload.razorpay_order_id,),
            conn
        )

        # ✅ Step 6: Deactivate previous subscriptions
        await execute_write(
            "UPDATE mt_subscriptions SET is_active = FALSE WHERE user_id = $1 AND is_active = TRUE",
            (user_id,),
            conn
        )

        # ✅ Step 7: Insert new subscription
        today = utc_today()
        await execute_write("""
            INSERT INTO mt_subscriptions (
                user_id, plan_id, plan_type, start_date, end_date,
                created_at, is_active, payment_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, TRUE, $7)
        """, (
            user_id,
            order["plan_id"],
            result["plan_name"],
            today,
            today + timedelta(days=result["duration_days"]),
            today,
            payload.payment_id
        ), conn)

        await notify_internal(f"[✅ Razorpay Verified] UID {user_id}, ₹{result['final_price']}")
        return ORJSONResponse({"success": True, "amount": result["final_price"]})

    except ValueError as ve:
        await notify_internal(f"[❌ Razorpay Verify Error] {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await notify_internal(f"[❌ Razorpay Verify Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Verification failed")
    finally:
        await conn.close()
