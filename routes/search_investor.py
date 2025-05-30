from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from db.connection import get_single_connection
from db.db_helpers import fetch_all
from utils.auth import authorize_user

router = APIRouter()

@router.get("/search_investor")
async def search_investor(
    request: Request,
    investor_name: str = Query(..., min_length=2),
    min_portfolio_value: float = Query(1.0, ge=0),
    user=Depends(authorize_user)
):
    try:
        conn = await get_single_connection()

        query = """
            SELECT "Investor", "InvestorType", "PortfolioValueInCr"
            FROM mt_large_shareholders
            WHERE LOWER("Investor") LIKE LOWER($1)
              AND "PortfolioValueInCr" >= $2
            ORDER BY "PortfolioValueInCr" DESC
            LIMIT 100
        """
        raw_results = await fetch_all(query, (f"%{investor_name}%", min_portfolio_value), conn)

        seen = set()
        unique_investors = []
        for row in raw_results:
            key = row["Investor"].strip().lower()
            if key not in seen:
                seen.add(key)
                unique_investors.append({
                    "Investor": row["Investor"],
                    "InvestorType": row["InvestorType"],
                    "PortfolioValueInCr": round(float(row["PortfolioValueInCr"]))
                })
            if len(unique_investors) == 20:
                break

        return ORJSONResponse(unique_investors)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
