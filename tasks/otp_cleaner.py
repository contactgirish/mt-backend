import asyncio
from db.connection import get_single_connection
from utils.telegram_notifier import notify_internal
from utils.datetime_utils import utc_now

async def clear_expired_otps():
    while True:
        try:
            conn = await get_single_connection()
            now = utc_now()
            await conn.execute("DELETE FROM mt_otps WHERE expires_at < $1", now)
            await conn.close()
        except Exception as e:
            await notify_internal(f"[OTP Cleaner Error] {str(e)}")

        await asyncio.sleep(600)  # Run every 10 minutes
