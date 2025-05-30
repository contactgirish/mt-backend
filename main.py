from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

from routes import router as all_routes
from tasks.blocklist_updater import refresh_blocked_users_forever
from tasks.otp_cleaner import clear_expired_otps

import asyncio

app = FastAPI(title="MonkTrader API", default_response_class=ORJSONResponse)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Register all routers from routes/__init__.py
app.include_router(all_routes)

@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend(), prefix="monktrader-cache")
    asyncio.create_task(refresh_blocked_users_forever())
    asyncio.create_task(clear_expired_otps())
