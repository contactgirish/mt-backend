from db.db_helpers import fetch_one
from math import floor

async def calculate_final_price(plan_id: int, promocode: str = None, conn=None, plan_type: str = None):
    plan_query = """
        SELECT id, plan_name, price_before_tax, duration_days
        FROM mt_subscription_master
        WHERE id = $1
    """
    gst_query = "SELECT gst FROM mt_config LIMIT 1"

    plan = await fetch_one(plan_query, (plan_id,), conn)
    gst_row = await fetch_one(gst_query, (), conn)

    if not plan or not gst_row:
        raise ValueError("Missing plan or GST configuration")

    price = float(plan["price_before_tax"])
    discount = 0.0

    if promocode:
        promo_query = """
            SELECT * FROM mt_promocodes
            WHERE LOWER(promocode) = LOWER($1)
              AND status = 'active'
              AND valid_from <= NOW()
              AND valid_to >= NOW()
        """
        promo = await fetch_one(promo_query, (promocode,), conn)

        if not promo:
            raise ValueError("Invalid or expired promocode")

        applicable = (promo.get("applicable_plan") or "ALL").upper()
        plan_type_upper = plan_type.upper() if plan_type else None

        if applicable != "ALL" and applicable != plan_type_upper:
            raise ValueError(f"This promocode is only valid for {applicable.lower()} plans.")

        if promo["promocode_type"] == "flat_discount":
            discount = float(promo["promocode_value"])
        elif promo["promocode_type"] == "percent_discount":
            discount = (float(promo["promocode_value"]) / 100.0) * price
        elif promo["promocode_type"] == "free_days":
            # If free_days is applicable, you might want to handle this upstream
            return {
                "plan_name": plan["plan_name"],
                "type": "free_days",
                "free_days": int(promo["promocode_value"]),
                "duration_days": int(plan["duration_days"]),
            }

    discounted = max(price - discount, 0.0)
    gst_percent = float(gst_row["gst"])
    gst_amount = floor((gst_percent / 100.0) * discounted)
    final_price = floor(discounted + gst_amount)

    return {
        "plan_name": plan["plan_name"],
        "price": floor(price),
        "discount_amount": floor(discount),
        "gst": gst_amount,
        "final_price": final_price,
        "duration_days": int(plan["duration_days"])
    }
