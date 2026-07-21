"""
Admin endpoints: manage users and view audit logs.

All endpoints require admin role (enforced by get_current_admin).
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from core.dependencies import get_current_admin, get_db

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ActionRequest(BaseModel):
    reason: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    status: str
    created_at: Optional[str]
    last_login_at: Optional[str]
    approved_at: Optional[str]


class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    ip_address: Optional[str]
    metadata: Optional[dict]
    created_at: Optional[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(dt) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _user_dict(u) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "status": u.status,
        "created_at": _ts(u.created_at),
        "last_login_at": _ts(u.last_login_at),
        "approved_at": _ts(u.approved_at),
    }


def _perform_action(
    db, user_id: str, admin, action: str, reason: Optional[str],
    new_status: str, ip: str, ua: str,
):
    from models.auth import AdminApprovalLog, User
    from services.audit_logger import write_audit

    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot perform this action on your own account")

    old_status = target.status
    target.status = new_status
    if new_status == "approved":
        target.approved_at = datetime.now(timezone.utc)
        target.approved_by = admin.id

    log = AdminApprovalLog(
        user_id=user_id,
        admin_id=admin.id,
        action=action,
        reason=reason,
    )
    db.add(log)
    db.commit()

    # Audit logging must never fail the (already-committed) action.
    try:
        write_audit(
            db,
            user_id=admin.id,
            action=f"user_{action}d",
            resource_type="user",
            resource_id=user_id,
            ip_address=ip,
            user_agent=ua,
            metadata={"reason": reason, "old_status": old_status, "new_status": new_status},
        )
    except Exception:
        pass
    return target


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/users")
async def list_users(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    """List all users, optionally filtered by status."""
    from models.auth import User
    q = db.query(User)
    if status_filter:
        q = q.filter(User.status == status_filter)
    users = q.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return [_user_dict(u) for u in users]


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    from models.auth import User
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_dict(user)


@router.post("/users/{user_id}/approve")
async def approve_user(
    request: Request,
    user_id: str,
    body: ActionRequest = ActionRequest(),
    admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    user = _perform_action(
        db, user_id, admin, "approve", body.reason, "approved",
        _ip(request), request.headers.get("user-agent", ""),
    )
    return {"message": "User approved", "user": _user_dict(user)}


@router.post("/users/{user_id}/reject")
async def reject_user(
    request: Request,
    user_id: str,
    body: ActionRequest = ActionRequest(),
    admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    user = _perform_action(
        db, user_id, admin, "reject", body.reason, "rejected",
        _ip(request), request.headers.get("user-agent", ""),
    )
    return {"message": "User rejected", "user": _user_dict(user)}


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    request: Request,
    user_id: str,
    body: ActionRequest = ActionRequest(),
    admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    user = _perform_action(
        db, user_id, admin, "suspend", body.reason, "suspended",
        _ip(request), request.headers.get("user-agent", ""),
    )
    return {"message": "User suspended", "user": _user_dict(user)}


@router.post("/users/{user_id}/reinstate")
async def reinstate_user(
    request: Request,
    user_id: str,
    body: ActionRequest = ActionRequest(),
    admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    user = _perform_action(
        db, user_id, admin, "reinstate", body.reason, "approved",
        _ip(request), request.headers.get("user-agent", ""),
    )
    return {"message": "User reinstated", "user": _user_dict(user)}


@router.get("/audit-logs")
async def audit_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    """Paginated audit log with optional user and action filters."""
    from models.auth import UserAuditLog
    q = db.query(UserAuditLog)
    if user_id:
        q = q.filter(UserAuditLog.user_id == user_id)
    if action:
        q = q.filter(UserAuditLog.action == action)
    logs = q.order_by(UserAuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "ip_address": log.ip_address,
            "metadata": log.meta,
            "created_at": _ts(log.created_at),
        }
        for log in logs
    ]


@router.get("/stats")
async def stats(admin=Depends(get_current_admin), db=Depends(get_db)):
    """Quick dashboard counts."""
    from models.auth import User
    from sqlalchemy import func
    counts = (
        db.query(User.status, func.count(User.id))
        .group_by(User.status)
        .all()
    )
    return {row[0]: row[1] for row in counts}


def _ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
