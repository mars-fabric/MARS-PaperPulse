"""
Shared pytest fixtures for auth, ownership, and tracing tests.

All tests use an in-memory SQLite database so nothing is persisted between runs.
The FastAPI TestClient overrides the get_db dependency to use the same session.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# ── Ensure the backend directory is on the path ──────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ── Set required env vars before importing the app ───────────────────────────
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-256bits")
os.environ.setdefault("DEFAULT_ADMIN_EMAIL", "admin@test.example")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "Admin@1234!")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")

# ── In-memory SQLite engine ───────────────────────────────────────────────────
SQLALCHEMY_TEST_URL = "sqlite:///:memory:?check_same_thread=false"
_test_engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


def _create_all_tables():
    """Import every model so Base.metadata is populated, then create tables."""
    # Import cmbagent base first
    from cmbagent.database.base import Base as CmbBase
    # Import auth models (registers with same Base via cmbagent.database.base.Base)
    import models.auth  # noqa

    # Create all tables in the in-memory DB
    CmbBase.metadata.create_all(bind=_test_engine)


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    """Create tables once for the whole test session."""
    _create_all_tables()
    yield
    # Tables stay in memory until process exits — nothing to tear down


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Per-test isolated DB session; rolls back changes after each test."""
    connection = _test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> TestClient:
    """FastAPI TestClient with get_db overridden to use the test session."""
    # Import app after env vars are set
    from core.app import create_app
    from routers import register_routers
    from core.dependencies import get_db

    app = create_app()
    register_routers(app)

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── User factories ────────────────────────────────────────────────────────────

def _make_user(db, email: str, password: str, role: str = "user", status: str = "approved"):
    from models.auth import User
    from core.security import hash_password

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
        status=status,
    )
    if status == "approved":
        user.approved_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db):
    return _make_user(db, "admin@example.com", "Admin@1234!", role="admin", status="approved")


@pytest.fixture
def normal_user(db):
    return _make_user(db, "user@example.com", "User@1234!", role="user", status="approved")


@pytest.fixture
def pending_user(db):
    return _make_user(db, "pending@example.com", "User@1234!", role="user", status="pending")


@pytest.fixture
def user_b(db):
    return _make_user(db, "userb@example.com", "UserB@1234!", role="user", status="approved")


def _get_token(client: TestClient, email: str, password: str) -> str:
    """Log in and return the access token."""
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def admin_headers(client, admin_user):
    token = _get_token(client, "admin@example.com", "Admin@1234!")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_headers(client, normal_user):
    token = _get_token(client, "user@example.com", "User@1234!")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_b_headers(client, user_b):
    token = _get_token(client, "userb@example.com", "UserB@1234!")
    return {"Authorization": f"Bearer {token}"}
