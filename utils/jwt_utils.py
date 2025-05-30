from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback_monktrader_dev_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days

def create_jwt_token(user_id: int, iat: datetime, exp: datetime) -> str:
    payload = {
        "user_id": user_id,
        "iat": int(iat.timestamp()),
        "exp": int(exp.timestamp()),
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)

def decode_jwt_token(token: str, expect_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expect_type:
            raise JWTError("Token type mismatch")
        return payload
    except ExpiredSignatureError:
        raise JWTError("Token expired")
    except JWTError as e:
        raise JWTError(f"Invalid token: {e}")
