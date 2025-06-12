from fastapi import APIRouter, HTTPException, Request, Depends, Query
from db.connection import get_single_connection
from db.db_helpers import fetch_one, fetch_all
from utils.auth import authorize_user

router = APIRouter()

@router.get("/get_investors")
async def get_investors(
    request: Request,
    script_id: int,
    limit: int = Query(10, gt=0, le=500),
    user=Depends(authorize_user)
):
    try:
        conn = await get_single_connection()

        co_code_row = await fetch_one("SELECT co_code FROM script_master WHERE script_id = $1", (script_id,), conn)
        if not co_code_row:
            await conn.close()
            raise HTTPException(status_code=404, detail="No company found for the given script ID.")

        co_code = co_code_row["co_code"]

        count_query = "SELECT COUNT(*) FROM mt_large_shareholders WHERE co_code = $1"
        count_row = await fetch_one(count_query, (co_code,), conn)
        total_investors = count_row["count"] if count_row else 0

        query = f"""
            SELECT * FROM mt_large_shareholders
            WHERE co_code = $1
            ORDER BY "PortfolioValueInCr" DESC
            LIMIT {limit}
        """

        rows = await fetch_all(query, (co_code,), conn)
        await conn.close()

        results = [dict(row) for row in rows]
        return {
            "total_investors": total_investors,
            "data": results
        }


    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
