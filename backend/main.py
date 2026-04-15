"""
MARS-PaperPulse Backend API - Main Entry Point

Standalone Deep Research application extracted from MARS.
"""

import logging
import sys
from pathlib import Path

# Add the backend directory to the path to import local modules
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, WebSocket

# Import core app factory
from core.app import create_app

# Import routers
from routers import register_routers

# Import WebSocket components
from websocket.events import send_ws_event

ws_logger = logging.getLogger("websocket")

# Create the FastAPI application
app = create_app()

# Register all REST API routers
register_routers(app)


# WebSocket endpoint for Deepresearch stage execution
@app.websocket("/ws/deepresearch/{task_id}/{stage_num}")
async def deepresearch_websocket_endpoint(websocket: WebSocket, task_id: str, stage_num: int):
    """WebSocket endpoint for streaming Deepresearch stage execution output.

    Streams console output from the shared buffer in real-time and sends
    stage_completed/stage_failed events when the phase finishes.
    """
    import asyncio
    from routers.deepresearch import _get_console_lines, _clear_console_buffer

    await websocket.accept()

    buf_key = f"{task_id}:{stage_num}"
    line_index = 0

    try:
        from routers.deepresearch import _running_tasks

        await send_ws_event(websocket, "status", {
            "message": f"Connected to stage {stage_num}",
            "stage_num": stage_num,
        }, run_id=task_id)

        # Track consecutive cycles with no active backend task and no console output
        # to detect stale "running" stages quickly
        stale_check_cycles = 0
        STALE_THRESHOLD = 5  # After 5 seconds with no task and no output, mark as stale

        while True:
            await asyncio.sleep(1)

            # Stream new console output lines
            new_lines = _get_console_lines(buf_key, since_index=line_index)
            for line in new_lines:
                await send_ws_event(websocket, "console_output", {
                    "text": line,
                    "stage_num": stage_num,
                }, run_id=task_id)
            line_index += len(new_lines)

            # Check DB for stage completion (every cycle)
            try:
                from cmbagent.database.base import get_db_session
                db = get_db_session()
                try:
                    from routers.deepresearch import _get_session_id_for_task, _get_stage_repo
                    session_id = _get_session_id_for_task(task_id, db)
                    repo = _get_stage_repo(db, session_id=session_id)
                    stages = repo.list_stages(parent_run_id=task_id)
                    stage = next((s for s in stages if s.stage_number == stage_num), None)
                    if stage:
                        if stage.status == "completed":
                            # Flush remaining console lines
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_completed", {
                                "stage_num": stage_num,
                                "stage_name": stage.stage_name,
                            }, run_id=task_id)
                            break
                        elif stage.status == "failed":
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_failed", {
                                "stage_num": stage_num,
                                "error": stage.error_message or "Stage failed",
                            }, run_id=task_id)
                            break
                        elif stage.status == "running":
                            # Detect stale "running" — no active background task
                            bg_key = f"{task_id}:{stage_num}"
                            has_active_task = bg_key in _running_tasks and not _running_tasks[bg_key].done()
                            if not has_active_task and not new_lines:
                                stale_check_cycles += 1
                            else:
                                stale_check_cycles = 0

                            if stale_check_cycles >= STALE_THRESHOLD:
                                # Stage is stuck — reset it in DB and notify client
                                from datetime import datetime, timezone
                                stage.status = "failed"
                                stage.error_message = "Execution was interrupted (no active process). Click retry to re-run."
                                stage.completed_at = datetime.now(timezone.utc)
                                db.commit()
                                await send_ws_event(websocket, "stage_failed", {
                                    "stage_num": stage_num,
                                    "error": stage.error_message,
                                }, run_id=task_id)
                                break
                finally:
                    db.close()
            except Exception as db_err:
                ws_logger.debug("WS DB check error task=%s stage=%d: %s", task_id, stage_num, db_err)
    except Exception as ws_err:
        # Log disconnects at debug level (normal), other errors at warning
        if "disconnect" in str(ws_err).lower() or "close" in str(ws_err).lower():
            ws_logger.debug("WS disconnected task=%s stage=%d", task_id, stage_num)
        else:
            ws_logger.warning("WS error task=%s stage=%d: %s", task_id, stage_num, ws_err)
    finally:
        # Ensure WebSocket is properly closed so the client gets a close frame
        try:
            await websocket.close()
        except Exception:
            pass  # Already closed or disconnected
