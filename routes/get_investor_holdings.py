from fastapi import APIRouter, HTTPException, Request, Depends, Query
from db.connection import get_single_connection
from db.db_helpers import fetch_all, fetch_one
from utils.auth import authorize_user
import math

router = APIRouter()

@router.get("/get_investor_holdings")
async def get_investor_holdings(
    request: Request,
    investor_type: str = Query(...),
    limit: int = Query(50, gt=0, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(authorize_user)
):
    try:
        investor_type = investor_type.strip().upper()
        if investor_type not in ("FII", "DII", "SHARK"):
            raise HTTPException(status_code=400, detail="Invalid investor_type. Choose from FII, DII, Shark")

        conn = await get_single_connection()

        additional_filter = ""
        if investor_type == "SHARK":
            additional_filter = "AND \"InvestorCategory\" ILIKE 'Resident%'"

        count_query = f"""
            SELECT COUNT(*) AS total_count FROM (
                SELECT "Investor"
                FROM mt_large_shareholders
                WHERE LOWER("InvestorType") = LOWER($1) {additional_filter}
                GROUP BY "Investor"
                HAVING SUM("PortfolioValueInCr") > 1
            ) AS filtered
        """
        count_row = await fetch_one(count_query, (investor_type,), conn)
        total_records = count_row["total_count"] if count_row else 0
        total_pages = math.ceil(total_records / limit) if limit > 0 else 1

        query = f"""
            SELECT "Investor",
                   COUNT(*) AS stock_count,
                   ROUND(SUM("PortfolioValueInCr")::numeric, 2) AS total_value
            FROM mt_large_shareholders
            WHERE LOWER("InvestorType") = LOWER($1) {additional_filter}
            GROUP BY "Investor"
            HAVING SUM("PortfolioValueInCr") > 1
            ORDER BY total_value DESC
            OFFSET {offset} LIMIT {limit}
        """
        rows = await fetch_all(query, (investor_type,), conn)
        await conn.close()

        results = [
            {
                "Investor": row["Investor"],
                "stocks_held": row["stock_count"],
                "PortfolioValueInCr": float(row["total_value"])
            }
            for row in rows
        ]

        return {
            "total_available_records": total_records,
            "total_pages": total_pages,
            "data": results
        }


    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))