from fastapi import APIRouter, Request, Depends, HTTPException, Query
from db.connection import get_single_connection
from db.db_helpers import fetch_all
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal

router = APIRouter()

@router.get("/search_stock")
async def search_stock(
    request: Request,
    search: str = Query(None),
    watchlist_id: int = Query(None),
    user=Depends(authorize_user)
):
    try:
        conn = await get_single_connection()
        term = search.strip() if search else ""
        term_len = len(term)

        base_condition = """
            latest_price IS NOT NULL AND latest_price != 0
            AND market_cap IS NOT NULL AND market_cap != 0
            AND company_size IS NOT NULL AND TRIM(company_size) NOT IN ('', '0', '0.0')
            AND exchange = 'NSE'
        """

        results = []

        if not term and not watchlist_id:
            # Return top 20 stocks by market cap
            query = f"""
                SELECT
                    script_id,
                    co_code,
                    companyname,
                    companyshortname,
                    latest_price::float,
                    exchange,
                    sector,
                    company_size,
                    changed_percentage::float
                FROM script_master
                WHERE {base_condition}
                ORDER BY market_cap DESC
                LIMIT 20
            """
            results = await fetch_all(query, (), conn)

        elif term_len == 1:
            query = f"""
                SELECT DISTINCT ON (companyname)
                    script_id,
                    co_code,
                    companyname,
                    companyshortname,
                    latest_price::float,
                    exchange,
                    sector,
                    company_size,
                    changed_percentage::float
                FROM script_master
                WHERE {base_condition}
                ORDER BY companyname, market_cap DESC
                LIMIT 20
            """
            results = await fetch_all(query, (), conn)

        else:
            query = f"""
                SELECT
                    script_id,
                    co_code,
                    companyname,
                    companyshortname,
                    latest_price::float,
                    exchange,
                    sector,
                    company_size,
                    changed_percentage::float
                FROM script_master
                WHERE {base_condition}
                  AND (
                    LOWER(companyname) ILIKE '%' || LOWER($1) || '%'
                    OR LOWER(companyshortname) ILIKE '%' || LOWER($1) || '%'
                  )
                ORDER BY market_cap DESC
                LIMIT 20
            """
            results = await fetch_all(query, (term,), conn)

        script_list = [row["script_id"] for row in results]

        watchlist_scripts = set()
        if watchlist_id and script_list:
            watchlist_query = """
                SELECT script_id FROM mt_watchlist_stocks
                WHERE watchlist_id = $1 AND script_id = ANY($2)
            """
            watchlist_result = await fetch_all(watchlist_query, (watchlist_id, script_list), conn)
            watchlist_scripts = {row["script_id"] for row in watchlist_result}

        enriched_results = []
        for row in results:
            item = dict(row)
            item["watchlist_status"] = item["script_id"] in watchlist_scripts
            enriched_results.append(item)

        return {"stocks": enriched_results}

    except Exception as e:
        await notify_internal(f"[Search Stock Error] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
