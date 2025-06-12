from fastapi import APIRouter, Depends, HTTPException, Query
from utils.auth import authorize_user
from db.connection import get_single_connection
from db.db_helpers import fetch_all, fetch_one, execute_write
from utils.telegram_notifier import notify_internal
from utils.datetime_utils import utc_now
import json

router = APIRouter()

LIMIT_LARGE_SHAREHOLDERS = 10

@router.get("/get_stock_details")
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

        # ✅ Add to recently viewed
        try:
            user_id = user["user_id"]
            now = utc_now()

            await execute_write("""
                DELETE FROM mt_recently_viewed_scripts
                WHERE user_id = $1 AND script_id = $2
            """, (user_id, script_id), conn)

            await execute_write("""
                INSERT INTO mt_recently_viewed_scripts (user_id, script_id, viewed_at)
                VALUES ($1, $2, $3)
            """, (user_id, script_id, now), conn)

            config_row = await fetch_one("SELECT recently_viewed_count FROM mt_config LIMIT 1", (), conn)
            max_count = config_row["recently_viewed_count"] or 20

            await execute_write(f"""
                DELETE FROM mt_recently_viewed_scripts
                WHERE id NOT IN (
                    SELECT id FROM mt_recently_viewed_scripts
                    WHERE user_id = $1
                    ORDER BY viewed_at DESC
                    LIMIT {max_count}
                )
                AND user_id = $1
            """, (user_id,), conn)
        except Exception as log_e:
            await notify_internal(f"[Recently Viewed Error] {str(log_e)}")

        # Safely decode monk_ai_analysis
        try:
            monk_analysis = meta["analysis_json"]
            if isinstance(monk_analysis, str):
                monk_analysis = json.loads(monk_analysis)
                if isinstance(monk_analysis, str):
                    monk_analysis = json.loads(monk_analysis)
        except Exception:
            monk_analysis = None

        # Financial ratios
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

        # Shareholding pattern
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

        # Top large shareholders
        mls_query = f"""
            SELECT *
            FROM mt_large_shareholders
            WHERE co_code = $1
            ORDER BY "PortfolioValueInCr" DESC NULLS LAST
            LIMIT {LIMIT_LARGE_SHAREHOLDERS}
        """
        raw_large_shareholders = await fetch_all(mls_query, (co_code,), conn)
        large_shareholders = [
            {k: v for k, v in dict(row).items() if k not in ("co_code", "Shares")}
            for row in raw_large_shareholders
        ]

        # ✅ Consolidated + Standalone "Total Revenue" & "Profit After Tax"
        def fetch_financial_subset(table: str):
            query = f"""
                SELECT year, section, value
                FROM {table}
                WHERE co_code = $1 AND section IN ('Total Revenue', 'Profit After Tax')
                ORDER BY year DESC
            """
            return fetch_all(query, (co_code,), conn)

        def structure_financial_data(rows):
            result = {}
            for row in rows:
                y = row["year"]
                sec = row["section"]
                val = float(row["value"]) if row["value"] is not None else None
                if y not in result:
                    result[y] = {}
                result[y][sec] = val
            return result

        consolidated_rows = await fetch_financial_subset("financial_data_consolidated")
        standalone_rows = await fetch_financial_subset("financial_data_standalone")

        consolidated_data = structure_financial_data(consolidated_rows)
        standalone_data = structure_financial_data(standalone_rows)

        # ✅ Similar companies (exclude same co_code, include exchange)
        similar_companies_sql = """
            WITH ranked_scripts AS (
                SELECT
                    script_id,
                    co_code,
                    companyname,
                    companyshortname,
                    latest_price,
                    changed_percentage,
                    market_cap,
                    exchange,
                    ROW_NUMBER() OVER (
                        PARTITION BY co_code
                        ORDER BY CASE WHEN exchange = 'NSE' THEN 1 ELSE 2 END
                    ) AS row_rank
                FROM script_master
                WHERE sector = $1 AND market_cap IS NOT NULL AND market_cap > 0 AND co_code != $2
            )
            SELECT *
            FROM ranked_scripts
            WHERE row_rank = 1
            ORDER BY ABS(market_cap - $3)
            LIMIT 5
        """

        similar_companies = await fetch_all(similar_companies_sql, (meta["sector"], meta["co_code"], meta["market_cap"]), conn)

        similar_companies_result = [
            {
                "companyname": row["companyname"],
                "companyshortname": row["companyshortname"],
                "co_code": row["co_code"],
                "script_id": row["script_id"],
                "latest_price": float(row["latest_price"]) if row["latest_price"] is not None else None,
                "changed_percentage": float(row["changed_percentage"]) if row["changed_percentage"] is not None else None,
                "exchange": row["exchange"]
            }
            for row in similar_companies
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
            "large_shareholders": large_shareholders,
            "financial_data": {
                "consolidated": consolidated_data,
                "standalone": standalone_data
            },
            "similar_companies": similar_companies_result
        }

    except Exception as e:
        await notify_internal(f"[Get Stock Details Error] {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        await conn.close()
