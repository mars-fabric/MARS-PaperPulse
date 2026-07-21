"""
Auth models: User, UserRefreshToken, AdminApprovalLog, UserAuditLog.

All models share the same SQLAlchemy Base as cmbagent so they are created
together when init_database() runs.  Import this module BEFORE calling
init_database() so the metadata is populated.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    TIMESTAMP,
)
from sqlalchemy.orm import relationship

from cmbagent.database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    # role: "user" | "admin"
    role = Column(String(20), nullable=False, default="user")
    # status: "pending" | "approved" | "rejected" | "suspended"
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(TIMESTAMP, default=_utcnow)
    updated_at = Column(TIMESTAMP, default=_utcnow, onupdate=_utcnow)
    last_login_at = Column(TIMESTAMP, nullable=True)
    approved_at = Column(TIMESTAMP, nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(TIMESTAMP, nullable=True)

    refresh_tokens = relationship(
        "UserRefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs = relationship(
        "UserAuditLog", foreign_keys="UserAuditLog.user_id",
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_users_email_status", "email", "status"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r} role={self.role!r} status={self.status!r}>"


class UserRefreshToken(Base):
    __tablename__ = "user_refresh_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(TIMESTAMP, nullable=False)
    revoked_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, default=_utcnow)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_tokens_user_revoked", "user_id", "revoked_at"),
    )


class AdminApprovalLog(Base):
    """Records every approve/reject/suspend/reinstate action by an admin."""

    __tablename__ = "admin_approval_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    admin_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    # action: "approve" | "reject" | "suspend" | "reinstate"
    action = Column(String(20), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, default=_utcnow)

    __table_args__ = (
        Index("idx_approval_logs_user_action", "user_id", "action"),
    )


class UserAuditLog(Base):
    """Immutable audit trail for every user-visible action.

    Carries an optional trace_id in metadata so every row can be correlated
    with its Langfuse trace.
    """

    __tablename__ = "user_audit_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # e.g. signup, login, logout, task_create, stage_execute, stage_complete,
    #       stage_fail, task_stop, task_delete, file_upload, file_delete,
    #       user_approved, user_rejected, user_suspended, user_reinstated,
    #       session_migrated
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)  # "task", "file", "user"
    resource_id = Column(String(36), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    # JSON blob: { "trace_id": "...", "stage_num": 2, ... }
    # Named 'meta' (not 'metadata') — SQLAlchemy reserves 'metadata' on Base.
    meta = Column("metadata", JSON, nullable=True)
    created_at = Column(TIMESTAMP, default=_utcnow)

    user = relationship(
        "User", foreign_keys=[user_id], back_populates="audit_logs"
    )

    __table_args__ = (
        Index("idx_audit_logs_user_action", "user_id", "action"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
    )
