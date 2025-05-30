from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import ORJSONResponse
from utils.auth import authorize_user
from db.connection import get_single_connection
from db.db_helpers import fetch_all
from utils.telegram_notifier import notify_internal
from decimal import Decimal

router = APIRouter()

ALLOWED_SORT_FIELDS = {"companyname", "latest_price"}

def serialize_row(row):
    return {
        k: float(v) if isinstance(v, Decimal) else v
        for k, v in dict(row).items()
    }

@router.get("/get_stocks_in_sector")
async def get_stocks_in_sector(
    request: Request,
    user_data: dict = Depends(authorize_user),
    sectorcode: int = Query(..., description="Sector code as integer (e.g., 1, 82)"),
    sort_by: str = Query("companyname", pattern="^(companyname|latest_price)$", description="Sort field"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order: asc or desc"),
    company_size: str = Query(None, description="Optional filter: Small Cap, Mid Cap, Large Cap"),
    exchange: str = Query(None, description="Optional filter: NSE or BSE")
):
    conn = await get_single_connection()
    try:
        padded_sectorcode = str(sectorcode).zfill(8)

        filters = ["sectorcode = $1", "latest_price IS NOT NULL", "latest_price > 0"]
        values = [padded_sectorcode]
        param_index = 2

        if company_size:
            filters.append(f"company_size = ${param_index}")
            values.append(company_size)
            param_index += 1

        if exchange:
            filters.append(f"exchange = ${param_index}")
            values.append(exchange)
            param_index += 1

        where_clause = " AND ".join(filters)

        query = f"""
            SELECT * FROM (
                SELECT DISTINCT ON (co_code)
                    script_id,
                    co_code,
                    companyname,
                    companyshortname,
                    latest_price,
                    changed_percentage,
                    exchange,
                    company_size
                FROM script_master
                WHERE {where_clause}
                ORDER BY co_code, (exchange = 'NSE') DESC
            ) AS filtered
            ORDER BY {sort_by} {sort_order.upper()}
        """

        rows = await fetch_all(query, tuple(values), conn)
        results = [serialize_row(row) for row in rows]
        return ORJSONResponse(content={"success": True, "data": results})
    except Exception as e:
        await notify_internal(f"[get_stocks_in_sector Error] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        await conn.close()
