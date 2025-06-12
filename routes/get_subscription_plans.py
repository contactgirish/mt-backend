from fastapi import APIRouter, Request, Query
from db.connection import get_single_connection
from db.db_helpers import fetch_all
from utils.telegram_notifier import notify_internal
from decimal import Decimal

router = APIRouter()

def convert_decimal_to_float(row: dict) -> dict:
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}

@router.get("/get_subscription_plans")
async def get_subscription_plans(request: Request, device_type: str = Query(...)):
    try:
        conn = await get_single_connection()
        query = """
            SELECT 
                id, plan_name, duration_days, original_price, discount_percent,
                price_before_tax, gst_percent, gst_amount, final_price,
                product_id, device_type, features, is_trial, is_active,
                created_at, updated_at
            FROM mt_subscription_master
            WHERE is_active = TRUE AND device_type = $1
            ORDER BY duration_days
        """
        rows = await fetch_all(query, (device_type,), conn)
        processed = [convert_decimal_to_float(dict(r)) for r in rows]
        return {"plans": processed}
    except Exception as e:
        await notify_internal(f"[Subscription Plans Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch subscription plans")

