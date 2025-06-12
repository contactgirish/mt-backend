from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from utils.auth import authorize_user
from db.connection import get_single_connection
from db.db_helpers import fetch_one
from utils.telegram_notifier import notify_internal
import json

router = APIRouter()

class GetTechnicalsRequest(BaseModel):
    script_id: int

@router.post("/get_technicals", response_class=ORJSONResponse)
async def get_technicals(data: GetTechnicalsRequest, user=Depends(authorize_user)):
    script_id = data.script_id

    query = "SELECT * FROM mt_script_technical_snapshot WHERE script_id = $1"

    conn = await get_single_connection()
    try:
        row = await fetch_one(query, (script_id,), conn)
        if not row:
            raise HTTPException(status_code=404, detail="Script ID not found")

        try:
            parsed_json = json.loads(row["result_json"]) if isinstance(row["result_json"], str) else row["result_json"]
        except Exception as e:
            await notify_internal(f"[Parse Error] script_id={script_id} | {e}")
            raise HTTPException(status_code=500, detail="Invalid result_json format")

        response = {
            "alltime_high": float(row["alltime_high"]) if row["alltime_high"] is not None else None,
            "alltime_low": float(row["alltime_low"]) if row["alltime_low"] is not None else None,
            "high_52_week": float(row["high_52_week"]) if row["high_52_week"] is not None else None,
            "low_52_week": float(row["low_52_week"]) if row["low_52_week"] is not None else None,
            "result_json": parsed_json
        }

        return ORJSONResponse(content=response)

    except Exception as e:
        await notify_internal(f"[Get Technicals Error] script_id={script_id} | {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        await conn.close()
