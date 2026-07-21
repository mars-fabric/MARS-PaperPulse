"""
Auth endpoints: signup, login, refresh, logout, me, change-password.

Rate limits:
  - /signup: 5 requests / IP / minute
  - /login:  5 requests / IP / minute
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, field_validator

from core.dependencies import get_current_user, get_db
from core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    validate_password_policy,
    verify_password,
)
from models.auth import User, UserRefreshToken

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def check_policy(cls, v: str) -> str:
        errors = validate_password_policy(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_policy(cls, v: str) -> str:
        errors = validate_password_policy(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class UserMeResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    status: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LOCK_THRESHOLD = 5
_LOCK_MINUTES = 15


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _ensure_db_ready():
    from cmbagent.database.base import init_database
    init_database()


def _write_audit(db, user_id: str, action: str, ip: str, ua: str, metadata: dict = None):
    from models.auth import UserAuditLog
    from services.audit_logger import write_audit
    write_audit(db, user_id=user_id, action=action, ip_address=ip,
                user_agent=ua, metadata=metadata)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(request: Request, body: SignupRequest, db=Depends(get_db)):
    """Register a new user. Account starts in 'pending' status until an admin approves it."""
    _ensure_db_ready()
    from models.auth import User  # noqa — import after DB init

    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role="user",
        status="pending",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _write_audit(db, user.id, "signup", _client_ip(request),
                 request.headers.get("user-agent", ""), {"email": body.email})

    return {"message": "Account created. Waiting for admin approval.", "user_id": user.id}


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, body: LoginRequest, db=Depends(get_db)):
    """Authenticate with email/password. Returns access + refresh tokens."""
    _ensure_db_ready()

    user = db.query(User).filter(User.email == body.email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    now = datetime.now(timezone.utc)

    # Check lockout
    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(
            status_code=429,
            detail=f"Account locked. Try again after {user.locked_until.strftime('%H:%M UTC')}",
        )

    if not verify_password(body.password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= _LOCK_THRESHOLD:
            from datetime import timedelta
            user.locked_until = now + timedelta(minutes=_LOCK_MINUTES)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.status == "pending":
        raise HTTPException(status_code=403, detail="Account pending admin approval")
    if user.status == "rejected":
        raise HTTPException(status_code=403, detail="Account rejected")
    if user.status == "suspended":
        raise HTTPException(status_code=403, detail="Account suspended")

    # Reset failed attempts on successful auth
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    # Issue tokens
    access_token = create_access_token(user.id, user.email, user.role)
    plain_refresh = generate_refresh_token()
    rt = UserRefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(plain_refresh),
        expires_at=refresh_token_expiry(),
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    db.add(rt)
    db.commit()

    _write_audit(db, user.id, "login", _client_ip(request),
                 request.headers.get("user-agent", ""))

    return {
        "access_token": access_token,
        "refresh_token": plain_refresh,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role},
    }


@router.post("/refresh")
async def refresh(body: RefreshRequest, db=Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    token_hash = hash_refresh_token(body.refresh_token)
    now = datetime.now(timezone.utc)

    rt = (
        db.query(UserRefreshToken)
        .filter(
            UserRefreshToken.token_hash == token_hash,
            UserRefreshToken.revoked_at.is_(None),
        )
        .first()
    )
    if rt is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    expires = rt.expires_at.replace(tzinfo=timezone.utc) if rt.expires_at.tzinfo is None else rt.expires_at
    if expires < now:
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = db.query(User).filter(User.id == rt.user_id).first()
    if user is None or user.status != "approved":
        raise HTTPException(status_code=403, detail="Account not active")

    access_token = create_access_token(user.id, user.email, user.role)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(body: RefreshRequest, db=Depends(get_db)):
    """Revoke a refresh token (invalidates this device's session)."""
    token_hash = hash_refresh_token(body.refresh_token)
    rt = db.query(UserRefreshToken).filter(UserRefreshToken.token_hash == token_hash).first()
    if rt:
        rt.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return {"message": "Logged out"}


@router.get("/me", response_model=UserMeResponse)
async def me(current_user=Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "status": current_user.status,
    }


@router.post("/change-password")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Change the authenticated user's password."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.password_hash = hash_password(body.new_password)
    db.commit()

    _write_audit(db, current_user.id, "password_change", _client_ip(request),
                 request.headers.get("user-agent", ""))
    return {"message": "Password changed successfully"}
