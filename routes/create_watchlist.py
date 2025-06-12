from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, constr
from utils.auth import authorize_user
from utils.telegram_notifier import notify_internal
from db.connection import get_single_connection
from utils.datetime_utils import utc_now

router = APIRouter()

class CreateWatchlistRequest(BaseModel):
    watchlist_name: constr(strip_whitespace=True, min_length=1, max_length=255)

@router.post("/create_watchlist")
async def create_watchlist(
    payload: CreateWatchlistRequest,
    request: Request,
    user_data: dict = Depends(authorize_user)
):
    try:
        user_id = user_data["user_id"]
        watchlist_name = payload.watchlist_name.strip()
        now = utc_now()

        conn = await get_single_connection()

        # ✅ Get free user watchlist limit from mt_config
        config = await conn.fetchrow("SELECT watchlist_count_for_free_users FROM mt_config LIMIT 1")
        max_allowed = config["watchlist_count_for_free_users"]

        # ✅ Check if the user has a free plan
        subscription = await conn.fetchrow(
            "SELECT plan_type FROM mt_subscriptions WHERE user_id = $1 AND is_active = true",
            user_id
        )

        if subscription and subscription["plan_type"].lower() == "free":
            watchlist_count = await conn.fetchval(
                "SELECT COUNT(*) FROM mt_watchlists WHERE user_id = $1",
                user_id
            )
            if watchlist_count >= max_allowed:
                raise HTTPException(
                    status_code=403,
                    detail=f"Free plan users can only create up to {max_allowed} watchlists."
                )

        # ✅ Case-insensitive duplicate check
        exists = await conn.fetchrow(
            "SELECT id FROM mt_watchlists WHERE user_id = $1 AND LOWER(watchlist_name) = LOWER($2)",
            user_id, watchlist_name
        )
        if exists:
            raise HTTPException(status_code=409, detail="Watchlist name already exists")

        # ✅ Insert watchlist
        row = await conn.fetchrow(
            """
            INSERT INTO mt_watchlists (user_id, watchlist_name, created_at)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            user_id, watchlist_name, now
        )

        return ({
            "success": True,
            "message": "Watchlist created successfully",
            "watchlist_id": row["id"]
        })

    except HTTPException as he:
        raise he
    except Exception as e:
        await notify_internal(f"[CreateWatchlist Error] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
