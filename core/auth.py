import os
import logging
import requests
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

log = logging.getLogger(__name__)

security = HTTPBearer()
_jwks_cache = None


def _get_jwks():
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    supabase_url = os.getenv("SUPABASE_URL")
    url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    resp = requests.get(url)
    _jwks_cache = resp.json()
    return _jwks_cache


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    token = credentials.credentials

    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg", "HS256")

        if algorithm == "HS256":
            jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
            if not jwt_secret:
                raise HTTPException(status_code=500, detail="JWT secret not configured")
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )

        elif algorithm == "ES256":
            jwks = _get_jwks()
            payload = jwt.decode(
                token,
                jwks,
                algorithms=["ES256"],
                options={"verify_aud": False}
            )

        else:
            raise HTTPException(status_code=401, detail="Unsupported token algorithm")

        return payload

    except JWTError as e:
        log.warning(f"Invalid token: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_user_id(payload: dict) -> str:
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    return user_id
