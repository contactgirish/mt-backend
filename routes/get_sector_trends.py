from fastapi import APIRouter, Request, Depends, HTTPException, Query
from utils.auth import authorize_user
from db.connection import get_single_connection
from db.db_helpers import fetch_all
from utils.telegram_notifier import notify_internal
from decimal import Decimal

router = APIRouter()

ALLOWED_SORT_FIELDS = {
    "dma10", "dma20", "dma50", "dma100", "dma200", "current_value", "trend", "sectorname", "stock_count"
}

def serialize_row(row):
    return {
        k: float(v) if isinstance(v, Decimal) else v
        for k, v in dict(row).items()
    }

@router.get("/get_sector_trends")
async def get_sector_trends(
    request: Request,
    user_data: dict = Depends(authorize_user),
    sectorname: str = Query(None, description="Filter by sector name (case-insensitive partial match)"),
    sort_by: str = Query(None, description="Field to sort by"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order: asc or desc")
):
    conn = await get_single_connection()
    try:
        base_query = """
            WITH sector_stock_counts AS (
                SELECT sectorcode::int AS sectorcode, COUNT(DISTINCT co_code) AS stock_count
                FROM script_master
                WHERE sectorcode IS NOT NULL AND latest_price IS NOT NULL AND latest_price > 0
                GROUP BY sectorcode
            )
            SELECT DISTINCT
                sma.sectorcode,
                sma.sectorname,
                sma.dma10,
                sma.dma20,
                sma.dma50,
                sma.dma100,
                sma.dma200,
                sma.current_value,
                sma.trend,
                COALESCE(ssc.stock_count, 0) AS stock_count
            FROM script_master sm
            JOIN sectoral_moving_averages sma
                ON sm.sectorcode::int = sma.sectorcode
            LEFT JOIN sector_stock_counts ssc
                ON sma.sectorcode = ssc.sectorcode
            WHERE sm.sector IS NOT NULL
        """

        conditions = []
        values = []

        if sectorname:
            conditions.append(f"LOWER(sma.sectorname) LIKE LOWER(${len(values) + 1})")
            values.append(f"%{sectorname}%")

        if conditions:
            base_query += " AND " + " AND ".join(conditions)

        if sort_by and sort_by in ALLOWED_SORT_FIELDS:
            base_query += f" ORDER BY {sort_by} {sort_order.upper()}"
        else:
            base_query += " ORDER BY sma.sectorname ASC"

        base_query += " LIMIT 1000"

        rows = await fetch_all(base_query, tuple(values), conn)
        results = [serialize_row(row) for row in rows]
        return {"data": results}

    except Exception as e:
        await notify_internal(f"[get_sector_trends Error] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        await conn.close()
