"""
Security utilities: password hashing (Argon2), JWT tokens, refresh token hashing.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt

# ---------------------------------------------------------------------------
# Password hashing — Argon2
# ---------------------------------------------------------------------------

def _get_pwd_context():
    from passlib.context import CryptContext
    return CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _get_pwd_context().hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _get_pwd_context().verify(plain, hashed)


def validate_password_policy(password: str) -> list[str]:
    """Return a list of policy violations (empty = valid)."""
    errors: list[str] = []
    if len(password) < 8:
        errors.append("At least 8 characters required.")
    if not any(c.isupper() for c in password):
        errors.append("At least one uppercase letter required.")
    if not any(c.islower() for c in password):
        errors.append("At least one lowercase letter required.")
    if not any(c.isdigit() for c in password):
        errors.append("At least one digit required.")
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
        errors.append("At least one special character required.")
    return errors


# ---------------------------------------------------------------------------
# JWT — Access tokens
# ---------------------------------------------------------------------------

_ALGORITHM = "HS256"


def _get_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY", "")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY env var is not set")
    return secret


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "15")))
    )
    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, _get_secret(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and verify an access token. Raises JWTError on failure."""
    payload = jwt.decode(token, _get_secret(), algorithms=[_ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload


# ---------------------------------------------------------------------------
# Refresh tokens — opaque 64-byte random, stored as SHA-256 hash
# ---------------------------------------------------------------------------

def generate_refresh_token() -> str:
    """Return a URL-safe 64-byte random token (plain text, never stored)."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(plain: str) -> str:
    """SHA-256 hash stored in the DB."""
    return hashlib.sha256(plain.encode()).hexdigest()


def refresh_token_expiry() -> datetime:
    days = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    return datetime.now(timezone.utc) + timedelta(days=days)
