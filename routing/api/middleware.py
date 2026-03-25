"""
CartPath — Auth Middleware
============================
JWT extraction from httpOnly cookies for FastAPI dependency injection.
"""

import os

from fastapi import Request, HTTPException
from jose import JWTError, jwt

JWT_SECRET = os.environ.get("CARTPATH_JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"


async def get_current_user(request: Request) -> dict:
    """Extract and validate JWT from access_token cookie. Raises 401 if invalid."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "user_id": payload["sub"],
            "email": payload["email"],
            "vehicle_type": payload.get("vehicle_type", "lsv"),
            "tier": payload.get("tier", "free"),
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_optional_user(request: Request) -> dict | None:
    """Same as get_current_user but returns None instead of raising."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None
