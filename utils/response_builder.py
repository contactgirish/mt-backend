from fastapi import HTTPException, Request
from fastapi.responses import ORJSONResponse
from functools import wraps

def success_response(data: dict | list, message: str = "Success", status_code: int = 200):
    return ORJSONResponse(
        status_code=status_code,
        content={
            "statusCode": status_code,
            "status": True,
            "message": message,
            "data": data
        }
    )

def error_response(message: str, status_code: int = 400):
    return ORJSONResponse(
        status_code=status_code,
        content={
            "statusCode": status_code,
            "status": False,
            "message": message,
            "data": {}
        }
    )

def standardized_exceptions(fn):
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except HTTPException as he:
            return error_response(message=he.detail, status_code=he.status_code)
        except Exception as e:
            # Fallback for unexpected errors
            from utils.telegram_notifier import notify_internal
            await notify_internal(f"[Unhandled Error] {str(e)}")
            return error_response(message="Internal Server Error", status_code=500)
    return wrapper
