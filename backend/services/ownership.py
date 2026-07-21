"""
Task ownership enforcement.

Every endpoint that accepts a task_id must call require_task_owner() to
ensure the authenticated user owns the task (or is an admin).
"""

from fastapi import HTTPException


def require_task_owner(task_id: str, user, db):
    """
    Load the WorkflowRun for task_id and assert the user owns it.

    Returns the WorkflowRun on success.
    Raises 404 if not found, 403 if the user doesn't own it.
    """
    from cmbagent.database.models import WorkflowRun, Session

    run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if user.role == "admin":
        return run

    # Load the parent session to check user_id
    session = db.query(Session).filter(Session.id == run.session_id).first()
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this task")

    return run


def require_file_owner(task_id: str, user, db) -> None:
    """
    Assert the user owns the task that a requested file path belongs to.
    Used in file upload/download/delete endpoints.
    """
    require_task_owner(task_id, user, db)
