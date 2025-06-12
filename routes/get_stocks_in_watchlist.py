from fastapi import APIRouter, Request, Depends, HTTPException, Query
from db.connection import get_single_connection
from db.db_helpers import fetch_all, fetch_one
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal
from decimal import Decimal
import math

router = APIRouter()

VALID_SORT_COLUMNS = {
    "added_date": "w.added_date",
    "latest_price": "w.added_price",
    "sector": "sm.sectorname",
    "company_size": "sm.company_size",
    "companyname": "sm.companyname",
    "changed_percentage": "sm.changed_percentage",
    "price_difference": "sm.price_difference"
}

@router.get("/get_stocks_in_watchlist")
async def get_stocks_in_watchlist(
    watchlist_id: int = Query(..., description="Watchlist ID"),
    request: Request = None,
    user_data: dict = Depends(authorize_user),
    page: int = Query(1, ge=1),
    limit: int | None = Query(None),
    sort_by: str = Query(
        "added_date",
        pattern="^(added_date|latest_price|sector|company_size|companyname|changed_percentage|price_difference)$"
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    sector: str | None = Query(None),
    company_size: str | None = Query(None)
):
    user_id = user_data["user_id"]
    sort_column = VALID_SORT_COLUMNS.get(sort_by, "w.added_date")
    sort_direction = "ASC" if sort_order == "asc" else "DESC"
    offset = (page - 1) * limit if limit else 0

    conn = await get_single_connection()

    try:
        # Step 1: Verify ownership
        ownership = await fetch_one(
            "SELECT id FROM mt_watchlists WHERE id = $1 AND user_id = $2",
            (watchlist_id, user_id),
            conn
        )
        if not ownership:
            raise HTTPException(status_code=404, detail="The specified watchlist does not exist.")

        # Step 2: Build filter clause (case-insensitive)
        filter_clause = []
        params = [watchlist_id]

        if sector:
            filter_clause.append("sm.sectorname ILIKE ${}".format(len(params) + 1))
            params.append(sector)

        if company_size:
            filter_clause.append("sm.company_size ILIKE ${}".format(len(params) + 1))
            params.append(company_size)

        where_sql = " AND " + " AND ".join(filter_clause) if filter_clause else ""

        # Step 3: Count query
        count_sql = f"""
            SELECT COUNT(*) FROM mt_watchlist_stocks w
            JOIN script_master sm ON w.script_id = sm.script_id
            WHERE w.watchlist_id = $1 {where_sql}
        """
        count_row = await fetch_one(count_sql, tuple(params), conn)
        total_stocks = count_row["count"] if count_row else 0

        # Step 4: Select query
        select_sql = f"""
            SELECT 
                w.script_id,
                w.added_price,
                w.added_date,
                COALESCE(sm.companyname, '') AS companyname,
                COALESCE(sm.companyshortname, '') AS companyshortname,
                COALESCE(sm.exchange, '') AS exchange,
                COALESCE(sm.changed_percentage, 0.0) AS changed_percentage,
                COALESCE(sm.price_difference, 0.0) AS price_difference,
                COALESCE(sm.sectorcode, '') AS sectorcode,
                COALESCE(sm.sector, '') AS sector,
                COALESCE(sm.company_size, '') AS company_size
            FROM mt_watchlist_stocks w
            JOIN script_master sm ON w.script_id = sm.script_id
            WHERE w.watchlist_id = $1 {where_sql}
            ORDER BY {sort_column} {sort_direction}
        """

        if limit:
            select_sql += " LIMIT ${} OFFSET ${}".format(len(params) + 1, len(params) + 2)
            params += [limit, offset]

        rows = await fetch_all(select_sql, tuple(params), conn)

        def normalize(row):
            return {
                k: float(v) if isinstance(v, Decimal) else v
                for k, v in dict(row).items()
            }

        stocks = [normalize(row) for row in rows]

        # Step 5: Build response
        meta = {
            "watchlist_id": watchlist_id,
            "total_stocks": total_stocks,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "sector_filter": sector,
            "company_size_filter": company_size,
            "stocks": stocks
        }

        if limit:
            total_pages = math.ceil(total_stocks / limit) if total_stocks > 0 else 1
            meta.update({
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "has_next_page": page < total_pages,
                "has_prev_page": page > 1
            })

        return {"data": meta}

    except HTTPException:
        raise
    except Exception as e:
        await notify_internal(f"[Get Watchlist Stocks Error] {e}")
        raise HTTPException(status_code=500, detail="Something went wrong")
    finally:
        await conn.close()
