"""
Audit logging helper.

Writes UserAuditLog rows that include the current trace_id so every
audit event can be correlated with its Langfuse trace.
"""

from typing import Any, Dict, Optional

from core.logging import current_trace_id


def write_audit(
    db,
    *,
    user_id: Optional[str],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Insert a UserAuditLog row and commit immediately.

    Automatically includes the current trace_id from the logging contextvar
    so the row is always correlated with the active Langfuse trace.
    """
    from models.auth import UserAuditLog

    trace_id = current_trace_id.get()
    if trace_id:
        meta = dict(metadata or {})
        meta["trace_id"] = trace_id
    else:
        meta = metadata

    log = UserAuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        meta=meta,
    )
    db.add(log)
    db.commit()
