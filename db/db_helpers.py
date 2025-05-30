from utils.telegram_notifier import notify_internal

async def fetch_one(query: str, values: tuple, conn):
    try:
        return await conn.fetchrow(query, *values)
    except Exception as e:
        await notify_internal(f"DB fetch_one error: {e}")
        raise

async def fetch_all(query: str, values: tuple, conn):
    try:
        return await conn.fetch(query, *values)
    except Exception as e:
        await notify_internal(f"DB fetch_all error: {e}")
        raise

async def execute_write(query: str, values: tuple, conn):
    try:
        return await conn.execute(query, *values)
    except Exception as e:
        await notify_internal(f"DB execute_write error: {e}")
        raise

async def bulk_insert(query: str, list_of_tuples: list, conn):
    try:
        await conn.executemany(query, list_of_tuples)
    except Exception as e:
        await notify_internal(f"DB bulk_insert error: {e}")
        raise