import secrets

from fastapi import Header, HTTPException

from .config import get_settings


async def require_api_key(x_api_key: str = Header(default="")) -> str:
    if not any(secrets.compare_digest(x_api_key, k) for k in get_settings().api_keys):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
    return x_api_key
