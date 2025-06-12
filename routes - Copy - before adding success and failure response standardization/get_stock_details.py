from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import ORJSONResponse
from utils.auth import authorize_user
from db.connection import get_single_connection
from db.db_helpers import fetch_all, fetch_one
from utils.telegram_notifier import notify_internal
import json

router = APIRouter()

# Configurable constant for number of large shareholders
LIMIT_LARGE_SHAREHOLDERS = 10

@router.get("/get_stock_details", response_class=ORJSONResponse)
async def get_stock_details(
    script_id: int = Query(..., description="Script ID"),
    user=Depends(authorize_user)
):
    conn = await get_single_connection()
    try:
        # Fetch main script and analysis
        meta_query = """
            SELECT
                sm.script_id,
                sm.co_code,
                sm.companyname,
                sm.companyshortname,
                sm.sector,
                sm.company_size,
                sm.latest_price,
                sm.changed_percentage,
                sm.price_difference,
                sm.market_cap,
                oaa.analysis_json
            FROM script_master sm
            LEFT JOIN mt_openai_analysis oaa ON sm.co_code = oaa.co_code
            WHERE sm.script_id = $1
        """
        meta = await fetch_one(meta_query, (script_id,), conn)
        if not meta:
            raise HTTPException(status_code=404, detail="Script not found")

        co_code = meta["co_code"]

        # Safely decode monk_ai_analysis even if double-encoded
        try:
            monk_analysis = meta["analysis_json"]
            if isinstance(monk_analysis, str):
                monk_analysis = json.loads(monk_analysis)
                if isinstance(monk_analysis, str):
                    monk_analysis = json.loads(monk_analysis)
        except Exception:
            monk_analysis = None

        # Fetch financial ratios
        fr_query = """
            SELECT
                yearend,
                pe,
                pbv,
                pricetosalesratio,
                pegratio,
                debt_equity,
                interestcover,
                roe,
                roce,
                roa,
                netprofitmargin_perc,
                operatingmargin_perc
            FROM financial_ratios_standalone
            WHERE co_code = $1
            ORDER BY yearend ASC
        """
        financials = await fetch_all(fr_query, (co_code,), conn)

        # Fetch shareholding pattern
        shp_query = """
            SELECT
                yearandmonth,
                promoters,
                dii,
                fii,
                public
            FROM shareholding_pattern
            WHERE co_code = $1
            ORDER BY yearandmonth ASC
        """
        shareholding = await fetch_all(shp_query, (co_code,), conn)

        # Fetch top N large shareholders sorted by PortfolioValueInCr
        mls_query = f"""
            SELECT *
            FROM mt_large_shareholders
            WHERE co_code = $1
            ORDER BY "PortfolioValueInCr" DESC NULLS LAST
            LIMIT {LIMIT_LARGE_SHAREHOLDERS}
        """
        raw_large_shareholders = await fetch_all(mls_query, (co_code,), conn)
        # Remove co_code and Shares from output
        large_shareholders = [
            {k: v for k, v in dict(row).items() if k not in ("co_code", "Shares")}
            for row in raw_large_shareholders
        ]

        return {
            "script_id": meta["script_id"],
            "companyname": meta["companyname"],
            "companyshortname": meta["companyshortname"],
            "sector": meta["sector"],
            "company_size": meta["company_size"],
            "latest_price": float(meta["latest_price"] or 0),
            "changed_percentage": float(meta["changed_percentage"] or 0),
            "price_difference": float(meta["price_difference"] or 0),
            "market_cap": float(meta["market_cap"] or 0),
            "monk_ai_analysis": monk_analysis,
            "financials": [dict(row) for row in financials],
            "shareholding_pattern": [dict(row) for row in shareholding],
            "large_shareholders": large_shareholders
        }

    except Exception as e:
        await notify_internal(f"[Get Stock Details Error] {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        await conn.close()
