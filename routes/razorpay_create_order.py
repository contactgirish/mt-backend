from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import requests
import os
import uuid
import traceback
from db.connection import get_single_connection
from db.db_helpers import execute_write, fetch_one
from utils.auth import authorize_user
from utils.payment_calculator import calculate_final_price

router = APIRouter()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

class RazorpayOrderRequest(BaseModel):
    plan_id: int
    promocode: str | None = None

@router.post("/razorpay_create_order")
async def create_razorpay_order(
    payload: RazorpayOrderRequest,
    user_data: dict = Depends(authorize_user)
):
    conn = await get_single_connection()
    try:
        print("🧾 Received Razorpay order request for plan:", payload.plan_id)
        if payload.promocode:
            print("🎟️ Promocode used:", payload.promocode)

        # ✅ Step 1: Fetch plan_name as plan_type
        plan_row = await fetch_one(
            "SELECT plan_name FROM mt_subscription_master WHERE id = $1",
            (payload.plan_id,),
            conn
        )
        if not plan_row:
            raise HTTPException(status_code=404, detail="Invalid plan ID")

        plan_type = plan_row["plan_name"]
        print("📦 Plan type:", plan_type)

        # ✅ Step 2: Validate final price using promo + GST logic
        result = await calculate_final_price(
            plan_id=payload.plan_id,
            promocode=payload.promocode,
            conn=conn,
            plan_type=plan_type
        )

        amount = result["final_price"]
        amount_in_paise = int(amount * 100)

        print("💰 Final price (rupees):", amount)
        print("📤 Creating Razorpay order with amount (paise):", amount_in_paise)

        payload_dict = {
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": str(uuid.uuid4()),
            "payment_capture": 1
        }

        response = requests.post(
            "https://api.razorpay.com/v1/orders",
            auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
            json=payload_dict,
            timeout=10
        )

        if response.status_code != 200:
            print("❌ Razorpay error:", response.text)
            raise HTTPException(status_code=500, detail="Failed to create Razorpay order")

        order = response.json()
        print("✅ Razorpay order created:", order["id"])

        await execute_write("""
            INSERT INTO mt_payment_orders (user_id, razorpay_order_id, plan_id, amount, promocode, status)
            VALUES ($1, $2, $3, $4, $5, 'created')
        """, (
            user_data["user_id"],
            order["id"],
            payload.plan_id,
            float(amount),
            payload.promocode
        ), conn)

        print("📝 Order saved to DB")
        return {"order": order}

    except ValueError as ve:
        print("⚠️ Promo validation error:", str(ve))
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        print("🔥 Unexpected exception:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        await conn.close()
