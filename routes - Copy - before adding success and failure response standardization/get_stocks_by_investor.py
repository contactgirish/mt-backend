from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import ORJSONResponse
from db.connection import get_single_connection
from db.db_helpers import fetch_all, fetch_one
from utils.auth import authorize_user

router = APIRouter()

@router.get("/get_stocks_by_investor")
async def get_stocks_by_investor(
    request: Request,
    investor: str = Query(..., min_length=1),
    limit: int = Query(50, gt=0, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(authorize_user)
):
    try:
        investor = investor.strip()
        conn = await get_single_connection()

        count_query = """
            SELECT COUNT(*) AS total_count
            FROM mt_large_shareholders
            WHERE LOWER("Investor") = LOWER($1)
        """
        count_row = await fetch_one(count_query, (investor,), conn)
        total_stocks = count_row["total_count"] if count_row else 0

        query = f"""
            SELECT shp.*, 
                   sm.script_id, sm.sector, sm.company_size, sm.latest_price, sm.exchange,
                   sm.companyname, sm.companyshortname
            FROM mt_large_shareholders shp
            JOIN LATERAL (
                SELECT script_id, sector, company_size, latest_price, exchange, companyname, companyshortname
                FROM script_master sm
                WHERE sm.co_code = shp.co_code
                ORDER BY (sm.exchange = 'NSE') DESC, sm.updated_at DESC
                LIMIT 1
            ) sm ON true
            WHERE LOWER(shp."Investor") = LOWER($1)
            ORDER BY shp."PortfolioValueInCr" DESC
            OFFSET {offset} LIMIT {limit}
        """

        rows = await fetch_all(query, (investor,), conn)
        await conn.close()

        results = [dict(row) for row in rows]

        return ORJSONResponse(content={
            "success": True,
            "total_stocks": total_stocks,
            "data": results
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))