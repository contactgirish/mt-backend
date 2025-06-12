from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Literal
from db.connection import get_single_connection
from utils.auth import authorize_user
from utils.payment_calculator import calculate_final_price

router = APIRouter()

class ApplyPromocodeRequest(BaseModel):
    promocode: str
    device_type: Literal['IOS', 'Others']
    plan_id: int
    plan_type: Literal['ANNUAL', 'MONTHLY', '6MONTHS']

@router.post("/apply_promocode")
async def apply_promocode(
    payload: ApplyPromocodeRequest,
    user_data: dict = Depends(authorize_user)
):
    conn = await get_single_connection()
    try:
        result = await calculate_final_price(
            plan_id=payload.plan_id,
            promocode=payload.promocode,
            conn=conn,
            plan_type=payload.plan_type
        )

        if result.get("type") == "free_days":
            return {
                "success": True,
                "type": "free_days",
                "free_days": result["free_days"],
                "message": f"{result['free_days']} days free applied"
            }

        return {
            "success": True,
            "type": "discount",
            "original_price": result["price"],
            "discount_amount": result["discount_amount"],
            "gst": result["gst"],
            "final_price": result["final_price"],
            "message": f"Promocode applied successfully: {payload.promocode.upper()}"
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply promocode: {str(e)}")
    finally:
        await conn.close()
