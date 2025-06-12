# utils/exception_handler.py

from fastapi import Request, HTTPException
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from utils.telegram_notifier import notify_internal

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return ORJSONResponse(
        status_code=exc.status_code,
        content={
            "statusCode": exc.status_code,
            "status": False,
            "message": exc.detail,
            "data": {}
        }
    )

async def unhandled_exception_handler(request: Request, exc: Exception):
    await notify_internal(f"[Unhandled Exception] {type(exc).__name__}: {exc}")
    return ORJSONResponse(
        status_code=500,
        content={
            "statusCode": 500,
            "status": False,
            "message": "Internal server error",
            "data": {}
        }
    )
