"""
FastAPI dependency injection: database session, current user, current admin.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jose import JWTError

from core.security import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# cmbagent's shared engine uses StaticPool (one connection shared across ALL
# threads), which is not safe when FastAPI runs concurrent requests in
# anyio/threadpool workers.  We create a separate NullPool engine that opens
# a fresh SQLite connection for each request and closes it immediately after.
# Both engines point at the same on-disk file, so reads/writes are compatible;
# WAL mode (set by cmbagent's PRAGMA hook) makes concurrent access safe.

_mars_engine = None
_mars_session_factory = None


def _get_mars_session_factory():
    global _mars_engine, _mars_session_factory
    if _mars_session_factory is not None:
        return _mars_session_factory

    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool
    from cmbagent.database.base import get_database_url

    db_url = get_database_url()
    kw = {"poolclass": NullPool}
    if db_url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False}

    _mars_engine = create_engine(db_url, **kw)

    if db_url.startswith("sqlite"):
        @event.listens_for(_mars_engine, "connect")
        def _set_pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    _mars_session_factory = sessionmaker(
        bind=_mars_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    return _mars_session_factory


def get_db():
    """Yield a per-request SQLAlchemy session backed by NullPool (thread-safe)."""
    factory = _get_mars_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Current user
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db=Depends(get_db),
):
    """
    Extract and validate the JWT Bearer token.  Returns the User ORM object.

    Raises 401 if the token is missing or invalid.
    Raises 403 if the account is not approved or is suspended.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload.get("sub", "")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    from models.auth import User
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status}. Contact an admin.",
        )
    return user


def get_current_admin(current_user=Depends(get_current_user)):
    """Like get_current_user but additionally asserts role == 'admin'."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# ---------------------------------------------------------------------------
# Optional auth (returns None when no token is present — used for public endpoints)
# ---------------------------------------------------------------------------

def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db=Depends(get_db),
):
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub", "")
        if not user_id:
            return None
        from models.auth import User
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.status == "approved":
            return user
        return None
    except JWTError:
        return None
