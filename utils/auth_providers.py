import requests
import os
from jose import jwt
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIG ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")
APPLE_KEYS_URL = os.getenv("APPLE_KEYS_URL")

# --- VERIFICATION FUNCTIONS ---

def verify_google_token(id_token: str) -> dict:
    """
    Verifies a Google ID token and returns the payload if valid.
    """
    try:
        response = requests.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}",
            timeout=5
        )
        if response.status_code == 200:
            payload = response.json()
            if payload.get("aud") != GOOGLE_CLIENT_ID:
                raise ValueError("Invalid audience in Google token")
            return payload
        raise ValueError("Invalid token response from Google")
    except Exception as e:
        raise Exception(f"Google token verification failed: {e}")

def verify_apple_token(id_token: str) -> dict:
    """
    Verifies an Apple ID token by decoding its JWT and validating against Apple's public keys.
    """
    try:
        jwks_client = PyJWKClient(APPLE_KEYS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        decoded_token = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=APPLE_CLIENT_ID,
            issuer="https://appleid.apple.com"
        )

        return decoded_token

    except Exception as e:
        raise Exception(f"Apple token verification failed: {e}")
