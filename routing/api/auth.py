"""
CartPath — Auth Endpoints
===========================
Passwordless email authentication with 6-digit verification codes.

Flow:
  1. POST /api/auth/send-code  {email}         → sends 6-digit code
  2. POST /api/auth/verify-code {email, code}  → creates/logs in user, sets cookies
  3. POST /api/auth/logout                     → clears cookies
  4. POST /api/auth/refresh                    → refreshes access token
  5. GET  /api/auth/me                         → returns user profile
  6. PATCH /api/auth/me                        → updates profile (display_name, vehicle_type)
"""

import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from jose import jwt
from pydantic import BaseModel, Field

from .db import get_db
from .email import send_verification_email
from .middleware import get_current_user, JWT_SECRET, JWT_ALGORITHM

router = APIRouter(prefix="/auth", tags=["auth"])

IS_PRODUCTION = os.environ.get("CARTPATH_ENV", "development") == "production"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30
CODE_EXPIRE_MINUTES = 10
MAX_CODE_ATTEMPTS = 5  # per email per 10-minute window

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


# ── Request/Response models ──────────────────────────

class SendCodeRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


class VerifyCodeRequest(BaseModel):
    email: str
    code: str = Field(..., min_length=6, max_length=6)


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    vehicle_type: str | None = None


# ── Helper functions ─────────────────────────────────

def _set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Set httpOnly auth cookies on the response."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/auth",
    )


def _clear_auth_cookies(response: Response):
    """Remove auth cookies."""
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth")


def _create_access_token(user: dict) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "vehicle_type": user["vehicle_type"],
        "tier": user["tier"],
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def _create_refresh_token(db, user_id: str) -> str:
    """Create a refresh token and store it in the database."""
    token_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    await db.execute(
        "INSERT INTO refresh_tokens (id, user_id, expires_at) VALUES (?, ?, ?)",
        (token_id, user_id, expires_at.isoformat()),
    )
    await db.commit()
    return token_id


def _user_row_to_dict(row) -> dict:
    """Convert a database row to a user dict."""
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "vehicle_type": row["vehicle_type"],
        "tier": row["tier"],
        "created_at": row["created_at"],
    }


# ── Endpoints ────────────────────────────────────────

@router.post("/send-code")
async def send_code(req: SendCodeRequest):
    """Send a 6-digit verification code to the given email."""
    email = req.email.strip().lower()
    if not EMAIL_REGEX.match(email):
        raise HTTPException(status_code=400, detail="Invalid email address")

    db = await get_db()

    # Rate limit: max 5 codes per email in a 10-minute window
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=CODE_EXPIRE_MINUTES)).isoformat()
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM verification_codes WHERE email = ? AND created_at > ?",
        (email, cutoff),
    )
    row = await cursor.fetchone()
    if row and row["cnt"] >= MAX_CODE_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a few minutes.")

    # Generate and store the code
    code = f"{secrets.randbelow(1000000):06d}"
    code_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_EXPIRE_MINUTES)

    await db.execute(
        "INSERT INTO verification_codes (id, email, code, expires_at) VALUES (?, ?, ?, ?)",
        (code_id, email, code, expires_at.isoformat()),
    )
    await db.commit()

    # Send the email
    sent = send_verification_email(email, code)
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send verification email. Please try again.")

    return {"ok": True, "message": "Verification code sent to your email."}


@router.post("/verify-code")
async def verify_code(req: VerifyCodeRequest, response: Response):
    """Verify the 6-digit code and authenticate the user."""
    email = req.email.strip().lower()
    code = req.code.strip()
    db = await get_db()

    now = datetime.now(timezone.utc).isoformat()

    # Find a valid, unused code for this email
    cursor = await db.execute(
        "SELECT id FROM verification_codes WHERE email = ? AND code = ? AND used = 0 AND expires_at > ?",
        (email, code, now),
    )
    code_row = await cursor.fetchone()

    if not code_row:
        raise HTTPException(status_code=400, detail="Invalid or expired code. Please try again.")

    # Mark the code as used
    await db.execute("UPDATE verification_codes SET used = 1 WHERE id = ?", (code_row["id"],))

    # Find or create user
    cursor = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
    user_row = await cursor.fetchone()

    if user_row:
        user = _user_row_to_dict(user_row)
    else:
        # Create new user
        user_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO users (id, email) VALUES (?, ?)",
            (user_id, email),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = await cursor.fetchone()
        user = _user_row_to_dict(user_row)

    # Issue tokens
    access_token = _create_access_token(user)
    refresh_token = await _create_refresh_token(db, user["id"])
    _set_auth_cookies(response, access_token, refresh_token)

    # Clean up old codes for this email
    await db.execute(
        "DELETE FROM verification_codes WHERE email = ? AND (used = 1 OR expires_at <= ?)",
        (email, now),
    )
    await db.commit()

    return {
        "ok": True,
        "user": {
            "user_id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "vehicle_type": user["vehicle_type"],
            "tier": user["tier"],
        },
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Log out: revoke refresh token and clear cookies."""
    db = await get_db()
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await db.execute("DELETE FROM refresh_tokens WHERE id = ?", (refresh_token,))
        await db.commit()
    _clear_auth_cookies(response)
    return {"ok": True}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    """Refresh the access token using the refresh token cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    cursor = await db.execute(
        "SELECT user_id FROM refresh_tokens WHERE id = ? AND expires_at > ?",
        (refresh_token, now),
    )
    token_row = await cursor.fetchone()
    if not token_row:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Get the user
    cursor = await db.execute("SELECT * FROM users WHERE id = ?", (token_row["user_id"],))
    user_row = await cursor.fetchone()
    if not user_row:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="User not found")

    user = _user_row_to_dict(user_row)
    access_token = _create_access_token(user)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    return {"ok": True}


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Return the current user's profile."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user["user_id"],))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    u = _user_row_to_dict(row)
    return {
        "user_id": u["id"],
        "email": u["email"],
        "display_name": u["display_name"],
        "vehicle_type": u["vehicle_type"],
        "tier": u["tier"],
    }


@router.patch("/me")
async def update_me(req: UpdateProfileRequest, user: dict = Depends(get_current_user)):
    """Update user profile fields."""
    db = await get_db()

    if req.vehicle_type and req.vehicle_type not in ("golf_cart", "lsv"):
        raise HTTPException(status_code=400, detail="vehicle_type must be 'golf_cart' or 'lsv'")

    updates = []
    params = []
    if req.display_name is not None:
        updates.append("display_name = ?")
        params.append(req.display_name.strip())
    if req.vehicle_type is not None:
        updates.append("vehicle_type = ?")
        params.append(req.vehicle_type)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = datetime('now')")
    params.append(user["user_id"])

    await db.execute(
        f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    await db.commit()

    # Return updated profile
    cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user["user_id"],))
    row = await cursor.fetchone()
    u = _user_row_to_dict(row)
    return {
        "user_id": u["id"],
        "email": u["email"],
        "display_name": u["display_name"],
        "vehicle_type": u["vehicle_type"],
        "tier": u["tier"],
    }
