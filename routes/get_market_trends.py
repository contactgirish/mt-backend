from fastapi import APIRouter, Query, Request, Depends, HTTPException
from db.connection import get_single_connection
from db.db_helpers import fetch_all
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal

router = APIRouter()

@router.get("/get_market_trends")
async def get_market_trends(
    request: Request,
    trend: str = Query(..., regex="^(gainers|losers|active|unusual_volume|high_52|low_52|ath|atl)$"),
    exchange: str = Query(None),
    company_size: str = Query(None, regex="^(SMALL|MID|LARGE)?$", description="Use SMALL, MID, or LARGE"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_data: dict = Depends(authorize_user)
):
    try:
        conn = await get_single_connection()

        config = await conn.fetchrow("SELECT unusual_volume_threshold FROM mt_config LIMIT 1")
        if not config:
            raise Exception("Config not found in mt_config")
        volume_threshold = config["unusual_volume_threshold"]

        base_query = """
            SELECT
                script_id, co_code, companyname, companyshortname, latest_price,
                changed_percentage, volume, exchange, company_size
            FROM script_master
            WHERE latest_price IS NOT NULL
        """

        filters = []
        params = []

        if exchange:
            filters.append("exchange = $%d" % (len(params) + 1))
            params.append(exchange.upper())

        company_size_map = {
            "SMALL": "Small Cap",
            "MID": "Mid Cap",
            "LARGE": "Large Cap"
        }
        if company_size:
            mapped_value = company_size_map.get(company_size.upper())
            if mapped_value:
                filters.append("company_size = $%d" % (len(params) + 1))
                params.append(mapped_value)

        if trend == "gainers":
            filters.append("changed_percentage > 0")
            order_clause = "ORDER BY changed_percentage DESC"

        elif trend == "losers":
            filters.append("changed_percentage < 0")
            order_clause = "ORDER BY changed_percentage ASC"

        elif trend == "active":
            filters.append("volume >= $%d" % (len(params) + 1))
            params.append(volume_threshold)
            order_clause = "ORDER BY volume DESC"

        elif trend == "unusual_volume":
            filters.append("volume >= volume_moving_average * 2")
            filters.append("volume >= $%d" % (len(params) + 1))
            params.append(volume_threshold)
            order_clause = "ORDER BY (volume::float / NULLIF(volume_moving_average, 0)) DESC"

        elif trend == "high_52":
            filters.append("latest_price >= alltime_high")
            filters.append("alltime_high_date >= NOW() - INTERVAL '1 year'")
            order_clause = "ORDER BY companyname ASC"

        elif trend == "low_52":
            filters.append("latest_price <= alltime_low")
            filters.append("alltime_low_date >= NOW() - INTERVAL '1 year'")
            order_clause = "ORDER BY companyname ASC"

        elif trend == "ath":
            filters.append("latest_price >= alltime_high")
            order_clause = "ORDER BY companyname ASC"

        elif trend == "atl":
            filters.append("latest_price <= alltime_low")
            order_clause = "ORDER BY companyname ASC"

        if filters:
            base_query += " AND " + " AND ".join(filters)

        base_query += f" {order_clause} LIMIT {limit} OFFSET {offset}"

        results = await fetch_all(base_query, tuple(params), conn)
        return {"results": [dict(row) for row in results]}

    except Exception as e:
        await notify_internal(f"[get_market_trends Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
