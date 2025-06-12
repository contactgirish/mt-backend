from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from utils.custom_response import CustomJSONResponse
from utils.response_builder import error_response
from utils.telegram_notifier import notify_internal
from db.connection import get_single_connection
from routes import router as all_routes
from tasks.blocklist_updater import refresh_blocked_users_forever

import asyncio

app = FastAPI(
    title="MonkTrader API",
    default_response_class=CustomJSONResponse
)

# ✅ GZip compression
app.add_middleware(GZipMiddleware, minimum_size=500)

# ✅ CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Global HTTPException handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return error_response(message=exc.detail, status_code=exc.status_code)

# ✅ Global validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_messages = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err["loc"] if loc != "body")
        if err["msg"].lower() == "field required":
            error_messages.append(f"Field '{field}' is required")
        else:
            error_messages.append(f"Field '{field}' is {err['msg'].lower()}")
    return error_response(
        message="Validation failed: " + "; ".join(error_messages),
        status_code=422
    )

# ✅ Global fallback error handler
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    await notify_internal(f"[Unhandled Error] {str(exc)}")
    return error_response(message="Internal Server Error", status_code=500)

# ✅ Register all routers
app.include_router(all_routes)

# ✅ Startup tasks
@app.on_event("startup")
async def startup():
    try:
        # Ping DB
        conn = await get_single_connection()
        await conn.execute("SELECT 1")
        await conn.close()

        # Background blocklist refresh
        asyncio.create_task(refresh_blocked_users_forever())
    except Exception as e:
        await notify_internal(f"❌ Startup failure: {str(e)}")

# ✅ ECS/Fargate-compatible health check
@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "ok"}
