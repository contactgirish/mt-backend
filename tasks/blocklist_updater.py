import asyncio
from db.connection import get_single_connection

async def refresh_blocked_users_forever():
    while True:
        try:
            conn = await get_single_connection()
            rows = await conn.fetch("SELECT id FROM mt_users WHERE is_blocked = true")
            user_ids = [row["id"] for row in rows]

            from utils.user_blocklist import set_blocked_users
            set_blocked_users(user_ids)

            await conn.close()
        except Exception as e:
            print(f"[Blocklist Refresh Error] {e}")

        await asyncio.sleep(14400)  # 4 hours
