"""
Bootstrap the default admin user on first boot.

Reads DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD from the environment.
If no admin exists yet and both vars are set, creates one admin user with
status='approved'.

Also migrates any existing sessions (user_id=NULL) to this admin so
existing tasks remain visible after auth is enabled.
"""

import logging
import os

log = logging.getLogger(__name__)


def bootstrap_default_admin(db) -> str | None:
    """
    Create the default admin if the env vars are set and no admin exists.

    Returns the admin's user_id, or None if skipped.
    """
    from models.auth import User
    from core.security import hash_password

    email = os.environ.get("DEFAULT_ADMIN_EMAIL", "").strip()
    password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "").strip()

    if not email or not password:
        log.debug("DEFAULT_ADMIN_EMAIL / DEFAULT_ADMIN_PASSWORD not set — skipping admin bootstrap")
        return None

    existing_admin = db.query(User).filter(User.role == "admin").first()
    if existing_admin:
        log.debug("Admin already exists (%s) — skipping bootstrap", existing_admin.email)
        return existing_admin.id

    # Check if user with that email already exists (e.g. from a previous partial setup)
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        from datetime import datetime, timezone
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name="Default Admin",
            role="admin",
            status="approved",
            approved_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        log.info("Default admin created: %s", email)
    else:
        # Only promote accounts that are in a benign state. Never resurrect a
        # rejected/suspended account into an admin via the bootstrap env vars.
        if user.status in ("rejected", "suspended"):
            log.error(
                "Refusing to bootstrap admin: existing user %s is in '%s' status",
                email, user.status,
            )
            raise RuntimeError(
                f"Cannot promote user {email} to admin from '{user.status}' status"
            )
        user.role = "admin"
        user.status = "approved"
        db.commit()
        log.info("Existing user %s promoted to admin", email)

    _migrate_orphan_sessions(db, user.id)
    return user.id


def _migrate_orphan_sessions(db, admin_id: str) -> None:
    """Set user_id=admin_id on all sessions where user_id is NULL."""
    try:
        from cmbagent.database.models import Session
        orphans = db.query(Session).filter(Session.user_id.is_(None)).all()
        if not orphans:
            return

        for sess in orphans:
            sess.user_id = admin_id
        db.commit()

        # Write audit records
        from models.auth import UserAuditLog
        for sess in orphans:
            db.add(UserAuditLog(
                user_id=admin_id,
                action="session_migrated",
                resource_type="session",
                resource_id=sess.id,
                meta={"migrated_to_admin": admin_id},
            ))
        db.commit()
        log.info("Migrated %d orphan sessions to admin %s", len(orphans), admin_id)
    except Exception as exc:
        log.warning("Session migration failed (non-fatal): %s", exc)
