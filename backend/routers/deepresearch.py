"""
Deepresearch Research Paper wizard endpoints.

Provides staged execution of the 4-phase Deepresearch workflow
(idea → method → experiment → paper) where each stage is triggered
individually by the user after review/edit.
"""

import asyncio
import contextvars
import io
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks

from models.deepresearch_schemas import (
    DeepresearchCreateRequest,
    DeepresearchCreateResponse,
    DeepresearchExecuteRequest,
    DeepresearchStageResponse,
    DeepresearchStageContentResponse,
    DeepresearchArtifactsResponse,
    ArtifactManifest,
    DeepresearchContentUpdateRequest,
    DeepresearchRefineRequest,
    DeepresearchRefineResponse,
    DeepresearchTaskStateResponse,
    DeepresearchRecentTaskResponse,
    AnalyzeFilesResponse,
    RefineContextRequest,
    RefineContextResponse,
    UpdateDescriptionRequest,
    AiEditTexRequest,
    AiEditTexResponse,
    CompileTexRequest,
    CompileTexResponse,
    ExperimentPlanPreviewResponse,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/deepresearch", tags=["Deepresearch"])


# Stage definitions
STAGE_DEFS = [
    {"number": 1, "name": "idea_generation", "shared_key": "research_idea", "file": "idea.md"},
    {"number": 2, "name": "method_development", "shared_key": "methodology", "file": "methods.md"},
    {"number": 3, "name": "experiment_execution", "shared_key": "results", "file": "results.md"},
    {"number": 4, "name": "paper_generation", "shared_key": None, "file": None},
]

# Maps stage_num -> the short name stage_helpers.create_work_dir uses to
# produce the per-stage sub-directory. The sub-directory pattern is
# f"{short_name}_generation_output". Used by _clear_stage_scratch to
# invalidate stale pickles / plans on re-run.
_STAGE_SHORT_NAME = {1: "idea", 2: "method", 3: "experiment"}

# Upper bounds for chat_history persisted in the ``TaskStage.output_data``
# JSON column. Full chat history is still written to disk under
# ``<work_dir>/<stage>/chats/*.json`` — these caps only apply to the DB
# copy, which must be small enough for fast queries and page loads.
_DB_CHAT_HISTORY_MAX_MESSAGES = 500
_DB_CHAT_HISTORY_HEAD_MESSAGES = 50   # keep first N to preserve early context
_DB_CHAT_HISTORY_MAX_CONTENT_CHARS = 20_000
_DB_CHAT_HISTORY_TRUNC_MARKER = "… [truncated for DB persistence; full content in work_dir/chats/]"


def _truncate_chat_history_for_db(chat_history: list) -> list:
    """Return a chat_history list sized to fit comfortably in the DB JSON column.

    Three bounds applied in order:
      1. Each message's ``content`` is capped at ``_DB_CHAT_HISTORY_MAX_CONTENT_CHARS``.
      2. If > ``_DB_CHAT_HISTORY_MAX_MESSAGES`` messages: keep first ``_DB_CHAT_HISTORY_HEAD_MESSAGES``
         plus the last ``_MAX - _HEAD`` messages, with a synthetic gap marker.
      3. Malformed non-dict entries are preserved as-is (avoid surprises).

    The original ``chat_history`` list is not mutated.
    """
    if not isinstance(chat_history, list) or not chat_history:
        return chat_history or []

    def _cap_one(msg):
        if not isinstance(msg, dict):
            return msg
        content = msg.get("content")
        if isinstance(content, str) and len(content) > _DB_CHAT_HISTORY_MAX_CONTENT_CHARS:
            head_len = _DB_CHAT_HISTORY_MAX_CONTENT_CHARS - len(_DB_CHAT_HISTORY_TRUNC_MARKER)
            capped = {**msg, "content": content[:max(0, head_len)] + _DB_CHAT_HISTORY_TRUNC_MARKER}
            return capped
        return msg

    capped = [_cap_one(m) for m in chat_history]

    if len(capped) <= _DB_CHAT_HISTORY_MAX_MESSAGES:
        return capped

    head = capped[:_DB_CHAT_HISTORY_HEAD_MESSAGES]
    tail_n = _DB_CHAT_HISTORY_MAX_MESSAGES - _DB_CHAT_HISTORY_HEAD_MESSAGES
    tail = capped[-tail_n:] if tail_n > 0 else []
    dropped = len(capped) - len(head) - len(tail)
    gap_marker = {
        "role": "system",
        "name": "_truncation_marker",
        "content": (
            f"[{dropped} intermediate messages truncated for DB persistence; "
            f"full history available in work_dir/<stage>/chats/]"
        ),
    }
    return head + [gap_marker] + tail


def _clear_stage_scratch(work_dir: str, stage_num: int) -> None:
    """Wipe stale planning / context artifacts for a stage about to re-run.

    When a user re-executes an already-completed stage (e.g. after editing
    upstream data or plan), old ``context/context_step_*.pkl`` and the
    ``planning/final_plan.json`` from the prior run are still on disk.
    If anything downstream loads from them (restart flows, plan-load
    fallbacks), the new run would silently inherit the old plan/context.

    Preserves ``chats/`` and ``cost/`` — they are historical records that
    operators sometimes diff across runs to understand behavior.

    Best-effort: per-file try/except so a permission error on one file
    doesn't block the re-run. Only stages 1-3 have a scratch layout;
    stage 4 (paper) uses a different layout and is left untouched.
    """
    if stage_num not in _STAGE_SHORT_NAME:
        return
    stage_dir = os.path.join(work_dir, f"{_STAGE_SHORT_NAME[stage_num]}_generation_output")
    if not os.path.isdir(stage_dir):
        return

    targets_to_wipe = (
        os.path.join(stage_dir, "context"),
        os.path.join(stage_dir, "planning", "final_plan.json"),
        os.path.join(stage_dir, "final_plan.json"),  # older layout
    )
    wiped: List[str] = []
    for target in targets_to_wipe:
        try:
            if os.path.isdir(target):
                import shutil as _shutil
                _shutil.rmtree(target, ignore_errors=True)
                wiped.append(target)
            elif os.path.isfile(target):
                os.remove(target)
                wiped.append(target)
        except OSError as exc:
            logger.warning("stage_scratch_wipe_failed path=%s error=%s", target, exc)

    if wiped:
        logger.info("stage_scratch_wiped stage=%d count=%d paths=%s", stage_num, len(wiped), wiped)


# Track running background tasks
_running_tasks: Dict[str, asyncio.Task] = {}

# Track running file-analysis background tasks
_running_analyses: Dict[str, asyncio.Task] = {}

# Shared console buffers for stage execution (thread-safe)
# Key: "task_id:stage_num", Value: list of output lines
_console_buffers: Dict[str, List[str]] = {}
_console_lock = threading.Lock()

# Maximum lines per console buffer to prevent memory exhaustion
_MAX_CONSOLE_BUFFER_LINES = 50_000


# =============================================================================
# Helpers
# =============================================================================

_db_initialized = False
_db_init_lock = threading.Lock()

def _get_db():
    """Get a database session, ensuring schema is up to date."""
    global _db_initialized
    if not _db_initialized:
        with _db_init_lock:
            # Double-check after acquiring lock
            if not _db_initialized:
                from cmbagent.database.base import init_database
                init_database()
                _db_initialized = True
    from cmbagent.database.base import get_db_session
    return get_db_session()


def _get_stage_repo(db, session_id: str = "deepresearch"):
    from cmbagent.database.repository import TaskStageRepository
    return TaskStageRepository(db, session_id=session_id)


def _get_cost_repo(db, session_id: str = "deepresearch"):
    from cmbagent.database.repository import CostRepository
    return CostRepository(db, session_id=session_id)


def _get_work_dir(task_id: str, session_id: str = None, base_work_dir: str = None) -> str:
    """Get the work directory for a deepresearch task.

    Uses session-based structure: {base}/sessions/{session_id}/tasks/{task_id}
    matching the structure used by all other task modes.
    Falls back to legacy deepresearch_tasks/{task_id} when session_id is absent.
    """
    from core.config import settings
    base = os.path.expanduser(base_work_dir or settings.default_work_dir)
    if session_id:
        return os.path.join(base, "sessions", session_id, "tasks", task_id)
    # Legacy fallback for old tasks without a session
    return os.path.join(base, "deepresearch_tasks", task_id)


def _get_session_id_for_task(task_id: str, db) -> str:
    """Look up the session_id for a deepresearch task from its WorkflowRun."""
    from cmbagent.database.models import WorkflowRun
    run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
    if run:
        return run.session_id
    return "deepresearch"  # fallback for legacy tasks


def build_shared_state(task_id: str, up_to_stage: int, db, session_id: str = "deepresearch") -> Dict[str, Any]:
    """Reconstruct shared_state from completed stages' output_data['shared'].

    This accumulates context (research_idea, methodology, results, etc.)
    from all completed stages prior to the one being executed.
    """
    repo = _get_stage_repo(db, session_id=session_id)
    stages = repo.list_stages(parent_run_id=task_id)
    shared: Dict[str, Any] = {}
    for stage in stages:
        if stage.stage_number < up_to_stage and stage.status == "completed":
            if stage.output_data and "shared" in stage.output_data:
                shared.update(stage.output_data["shared"])
    return shared


def _stage_to_response(stage) -> DeepresearchStageResponse:
    return DeepresearchStageResponse(
        stage_number=stage.stage_number,
        stage_name=stage.stage_name,
        status=stage.status,
        started_at=stage.started_at.isoformat() if stage.started_at else None,
        completed_at=stage.completed_at.isoformat() if stage.completed_at else None,
        error=stage.error_message,
    )


# Auto-generated files in input_files/ that should NOT be listed as "uploaded data"
_AUTO_GENERATED_FILES = {
    "data_description.md", "idea.md", "methods.md", "results.md", "data_context.md",
}
_AUTO_GENERATED_DIRS = {"plots", "paper"}


def _build_file_context(work_dir: str) -> str:
    """Scan input_files/ for user-uploaded data files and build context string.

    If data_context.md exists (written by the analyze-files endpoint), it is
    included first as the authoritative 'Research Data Foundation'. Individual
    file paths + raw previews follow so agents can reference exact paths.
    """
    input_dir = os.path.join(work_dir, "input_files")
    if not os.path.isdir(input_dir):
        return ""

    sections = []

    # ── Primary: AI-generated data context (if analysis has been run) ──
    data_context_path = os.path.join(input_dir, "data_context.md")
    if os.path.isfile(data_context_path):
        try:
            with open(data_context_path, 'r', encoding='utf-8', errors='replace') as f:
                ctx = f.read().strip()
            if ctx:
                sections.append("\n\n---\n## Research Data Foundation\n\n" + ctx)
        except Exception:
            pass

    # ── Secondary: Individual file paths + raw previews ──
    uploaded_files = []
    for entry in os.listdir(input_dir):
        if entry in _AUTO_GENERATED_FILES:
            continue
        if entry in _AUTO_GENERATED_DIRS:
            continue
        full_path = os.path.join(input_dir, entry)
        if not os.path.isfile(full_path):
            continue
        uploaded_files.append((entry, full_path))

    if not uploaded_files:
        return "\n".join(sections) if sections else ""

    lines = ["\n\n---\n## Uploaded Data Files\n"]
    lines.append("The following data files have been uploaded and are available at the paths below.\n")

    for name, path in sorted(uploaded_files):
        size = os.path.getsize(path)
        size_str = f"{size}" if size < 1024 else f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/1024/1024:.1f}MB"
        lines.append(f"### `{name}` ({size_str})")
        lines.append(f"**Absolute path:** `{path}`\n")

        # For text-readable files, include a preview
        text_exts = {'.csv', '.txt', '.md', '.json', '.tsv', '.dat'}
        ext = os.path.splitext(name)[1].lower()
        if ext in text_exts and size < 10 * 1024 * 1024:  # Skip previews for files >10MB
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    preview_lines = []
                    for i, line in enumerate(f):
                        if i >= 15:
                            preview_lines.append("... (truncated)")
                            break
                        preview_lines.append(line.rstrip())
                if preview_lines:
                    lines.append("**Preview (first 15 lines):**")
                    lines.append("```")
                    lines.extend(preview_lines)
                    lines.append("```\n")
            except Exception:
                pass

    lines.append("Use the absolute paths above to read these files in your code.\n")
    sections.append("\n".join(lines))
    return "\n".join(sections)


# ── Context-aware console capture ──
# Routes stdout/stderr to the correct per-task console buffer using TWO
# complementary mechanisms:
#   1. Thread-ID mapping  — primary, covers asyncio.to_thread workers AND
#      any sub-threads they spawn (via _CapturingThread monkey-patch).
#   2. contextvars        — fallback, covers direct async code (stage 4
#      paper phase) where multiple asyncio tasks share the event-loop thread.

_active_buf_key: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    '_active_buf_key', default=None,
)

# Thread-ID → buf_key mapping.  Registered when a worker thread starts,
# unregistered when it ends.  Sub-threads created by libraries (autogen,
# crewai) inherit the parent thread's buf_key via _CapturingThread.
_thread_buf_map: Dict[int, str] = {}
_thread_buf_map_lock = threading.Lock()

# Original streams saved before capture is installed
_original_stdout = None
_original_stderr = None
_capture_installed = False

# Keep reference to original Thread class before monkey-patching
_OriginalThread = threading.Thread


class _CapturingThread(_OriginalThread):
    """Thread subclass that propagates the parent thread's buf_key to the
    child thread, so console output from library-spawned sub-threads is
    routed to the correct task buffer."""

    def start(self):
        parent_tid = threading.get_ident()
        with _thread_buf_map_lock:
            parent_buf = _thread_buf_map.get(parent_tid)
        if parent_buf:
            original_run = self.run

            def _wrapped_run():
                with _thread_buf_map_lock:
                    _thread_buf_map[threading.get_ident()] = parent_buf
                try:
                    original_run()
                finally:
                    with _thread_buf_map_lock:
                        _thread_buf_map.pop(threading.get_ident(), None)

            self.run = _wrapped_run
        super().start()


class _RoutingConsoleCapture:
    """A single sys.stdout/stderr replacement that routes output to the
    correct per-task console buffer.

    Lookup order: thread-ID map → contextvars → discard (terminal only).
    """

    def __init__(self, original_stream):
        self._original = original_stream

    def write(self, text: str):
        # Always write to original stream (terminal)
        if self._original:
            try:
                self._original.write(text)
            except Exception:
                pass
        # Route to the correct buffer
        if text and text.strip():
            # 1. Try thread-ID map (covers to_thread workers + sub-threads)
            with _thread_buf_map_lock:
                buf_key = _thread_buf_map.get(threading.get_ident())
            # 2. Fallback to context var (covers async code in event loop)
            if buf_key is None:
                buf_key = _active_buf_key.get(None)
            if buf_key:
                with _console_lock:
                    buf = _console_buffers.setdefault(buf_key, [])
                    if len(buf) < _MAX_CONSOLE_BUFFER_LINES:
                        buf.append(text.rstrip())

    def flush(self):
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass

    def fileno(self):
        if self._original:
            return self._original.fileno()
        raise io.UnsupportedOperation("fileno")

    def isatty(self):
        return False

    def __getattr__(self, name):
        # Proxy any other attribute to the original stream
        return getattr(self._original, name)


def _install_console_capture():
    """Install the global routing capture on sys.stdout/stderr (once).

    Also monkey-patches threading.Thread so sub-threads spawned by libraries
    inherit the parent thread's buf_key for correct output routing.
    """
    global _original_stdout, _original_stderr, _capture_installed
    if _capture_installed:
        return
    _original_stdout = sys.stdout
    _original_stderr = sys.stderr
    sys.stdout = _RoutingConsoleCapture(_original_stdout)
    sys.stderr = _RoutingConsoleCapture(_original_stderr)
    threading.Thread = _CapturingThread  # type: ignore[misc]
    _capture_installed = True


def _run_with_thread_capture(buf_key: str, func, *args, **kwargs):
    """Wrapper that registers the current thread's ID → buf_key mapping
    before running func, and unregisters on exit.  Passed as the target
    to asyncio.to_thread() so the worker thread is tracked."""
    tid = threading.get_ident()
    with _thread_buf_map_lock:
        _thread_buf_map[tid] = buf_key
    try:
        return func(*args, **kwargs)
    finally:
        with _thread_buf_map_lock:
            _thread_buf_map.pop(tid, None)


def _get_console_lines(buf_key: str, since_index: int = 0) -> List[str]:
    """Get console output lines since a given index."""
    with _console_lock:
        buf = _console_buffers.get(buf_key, [])
        return buf[since_index:]


def _clear_console_buffer(buf_key: str):
    """Remove a console buffer once done."""
    with _console_lock:
        _console_buffers.pop(buf_key, None)


# =============================================================================
# POST /api/deepresearch/create
# =============================================================================

@router.post("/create", response_model=DeepresearchCreateResponse)
async def create_deepresearch_task(request: DeepresearchCreateRequest):
    """Create a new Deepresearch research task with 4 pending stages."""
    task_id = str(uuid.uuid4())

    # Create a proper session via SessionManager (matches AI-Weekly, etc.)
    from services.session_manager import get_session_manager
    from core.config import settings
    sm = get_session_manager()

    # Resolve base work directory from request (frontend config) or backend setting
    base_work_dir = request.work_dir or settings.default_work_dir
    base_work_dir = os.path.expanduser(base_work_dir)

    # Create session first so we have the session_id for path construction
    session_id = sm.create_session(
        mode="deepresearch-research",
        config={"task_id": task_id, "base_work_dir": base_work_dir},
        name=f"Deepresearch: {request.task[:60]}",
    )

    # Session-based work dir: {base}/sessions/{session_id}/tasks/{task_id}
    # This matches the structure used by all other task modes
    work_dir = _get_work_dir(task_id, session_id=session_id, base_work_dir=base_work_dir)
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.join(work_dir, "input_files"), exist_ok=True)
    # Create standard subdirectories agents expect
    for subdir in ("data", "codebase", "chats", "planning", "control"):
        os.makedirs(os.path.join(work_dir, subdir), exist_ok=True)

    db = _get_db()
    try:
        # Create parent WorkflowRun
        from cmbagent.database.models import WorkflowRun

        parent_run = WorkflowRun(
            id=task_id,
            session_id=session_id,
            mode="deepresearch-research",
            agent="planner",
            model="gpt-4o",
            status="executing",
            task_description=request.task,
            started_at=datetime.now(timezone.utc),
            meta={
                "work_dir": work_dir,
                "base_work_dir": base_work_dir,
                "data_description": request.data_description or "",
                "config": request.config or {},
                "session_id": session_id,
            },
        )
        db.add(parent_run)
        db.flush()

        # Create 4 pending TaskStage records
        repo = _get_stage_repo(db, session_id=session_id)
        stage_responses = []
        for sdef in STAGE_DEFS:
            stage = repo.create_stage(
                parent_run_id=task_id,
                stage_number=sdef["number"],
                stage_name=sdef["name"],
                status="pending",
                input_data={"task": request.task, "data_description": request.data_description},
            )
            stage_responses.append(_stage_to_response(stage))

        db.commit()

        # Write data description to input_files/
        if request.data_description:
            desc_path = os.path.join(work_dir, "input_files", "data_description.md")
            with open(desc_path, "w") as f:
                f.write(request.data_description)

        logger.info("deepresearch_task_created task_id=%s session_id=%s", task_id, session_id)
        return DeepresearchCreateResponse(
            task_id=task_id,
            work_dir=work_dir,
            stages=stage_responses,
        )
    except Exception as e:
        db.rollback()
        logger.error("deepresearch_create_failed error=%s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# =============================================================================
# POST /api/deepresearch/{task_id}/stages/{num}/execute
# =============================================================================

@router.post("/{task_id}/stages/{stage_num}/execute")
async def execute_stage(task_id: str, stage_num: int, request: DeepresearchExecuteRequest = None):
    """Trigger execution of a single Deepresearch phase.

    Runs the phase asynchronously in the background. Connect to
    the WebSocket /ws/deepresearch/{task_id}/{stage_num} for streaming output.
    """
    if stage_num < 1 or stage_num > 4:
        raise HTTPException(status_code=400, detail="stage_num must be 1-4")

    # Check not already running
    bg_key = f"{task_id}:{stage_num}"
    if bg_key in _running_tasks and not _running_tasks[bg_key].done():
        raise HTTPException(status_code=409, detail="Stage is already executing")

    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        if not stages:
            raise HTTPException(status_code=404, detail="Task not found")

        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        if stage.status == "running":
            # Check if the background task is actually alive
            if bg_key in _running_tasks and not _running_tasks[bg_key].done():
                raise HTTPException(status_code=409, detail="Stage is already running")
            # Stale "running" from a previous server session — reset to allow retry
            logger.warning("Resetting stale 'running' stage %s for task %s", stage_num, task_id)
            repo.update_stage_status(
                stage.id, "failed",
                error_message="Execution was interrupted. Retrying...",
            )
            # Refresh the stage object after status update
            stage = next((s for s in repo.list_stages(parent_run_id=task_id) if s.stage_number == stage_num), stage)

        if stage.status == "completed":
            # Allow re-execution: reset to "pending" so the stage can be re-run.
            # This enables users to re-run a stage after editing its output
            # or if they want to regenerate results with different config.
            logger.info("Re-running completed stage %d for task %s", stage_num, task_id)
            repo.update_stage_status(stage.id, "pending")
            stage = next((s for s in repo.list_stages(parent_run_id=task_id) if s.stage_number == stage_num), stage)

            # Wipe stale planning / context pickles so the rerun truly
            # regenerates instead of inheriting pre-edit state. This uses
            # parent_run.meta["work_dir"] which we haven't fetched yet in
            # this branch — defer the actual wipe to just before _run_phase
            # spawns (see _clear_stage_scratch call below).

        # Validate prerequisites: all previous stages must be completed
        # Also recover stale "running" prerequisite stages
        stages = repo.list_stages(parent_run_id=task_id)  # Refresh after possible status update above
        for s in stages:
            if s.stage_number < stage_num:
                if s.status == "running":
                    # Check if this prerequisite stage has an active background task
                    prereq_key = f"{task_id}:{s.stage_number}"
                    if prereq_key not in _running_tasks or _running_tasks[prereq_key].done():
                        # Stale — reset it so the error message is accurate
                        logger.warning("Resetting stale prerequisite stage %d for task %s", s.stage_number, task_id)
                        repo.update_stage_status(
                            s.id, "failed",
                            error_message="Execution was interrupted (server restart).",
                        )
                        raise HTTPException(
                            status_code=400,
                            detail=f"Stage {s.stage_number} ({s.stage_name}) was interrupted. Please re-run it first."
                        )
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Stage {s.stage_number} ({s.stage_name}) is still running. Wait for it to complete."
                        )
                elif s.status != "completed":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stage {s.stage_number} ({s.stage_name}) must be completed first"
                    )

        # Get parent run metadata
        from cmbagent.database.models import WorkflowRun
        parent_run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent_run:
            raise HTTPException(status_code=404, detail="Parent workflow run not found")

        work_dir = parent_run.meta.get("work_dir") if parent_run.meta else _get_work_dir(task_id)
        task_description = parent_run.task_description or ""
        data_description = (parent_run.meta or {}).get("data_description") or ""

        # Enhance data_description with uploaded file context
        file_context = _build_file_context(work_dir)
        if file_context:
            data_description = data_description + file_context

        # Build shared state from completed stages
        shared_state = build_shared_state(task_id, stage_num, db, session_id=session_id)
        shared_state.setdefault("data_description", data_description)

        # Mark stage as running (reset timestamps/error for retries)
        stage.status = "running"
        stage.started_at = datetime.now(timezone.utc)
        stage.completed_at = None
        stage.error_message = None

        # Update parent WorkflowRun status back to "executing"
        # (may have been "failed" from a previous stop or crash)
        from cmbagent.database.models import WorkflowRun as _WFRun
        parent = db.query(_WFRun).filter(_WFRun.id == task_id).first()
        if parent and parent.status != "executing":
            parent.status = "executing"

        db.commit()

        config_overrides = (request.config_overrides if request else None) or {}
    finally:
        db.close()

    # Invalidate stale per-stage pickles / planning json BEFORE the
    # background task starts, so any restart/resume logic inside the
    # phase cannot accidentally pick up pre-edit state from a prior run.
    # Safe to call every time: the helper is a no-op when the stage
    # sub-directory doesn't exist yet.
    _clear_stage_scratch(work_dir, stage_num)

    # Launch background execution
    task = asyncio.create_task(
        _run_phase(task_id, stage_num, task_description, work_dir, shared_state, config_overrides)
    )
    _running_tasks[bg_key] = task

    return {"status": "executing", "stage_num": stage_num, "task_id": task_id}


async def _run_phase(
    task_id: str,
    stage_num: int,
    task_description: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Execute a Deepresearch phase in the background.

    Stages 1-3 call planning_and_control_context_carryover() directly
    with full callbacks (cost tracking, event logging, structured print).
    Stage 4 uses DeepresearchPaperPhase (LangGraph).
    """
    sdef = STAGE_DEFS[stage_num - 1]
    buf_key = f"{task_id}:{stage_num}"

    # Initialize console buffer
    with _console_lock:
        _console_buffers[buf_key] = [f"Starting {sdef['name']}..."]

    try:
        if stage_num <= 3:
            await _run_planning_control_stage(
                task_id, stage_num, sdef, buf_key,
                task_description, work_dir, shared_state, config_overrides,
            )
        else:
            await _run_paper_stage(
                task_id, stage_num, sdef, buf_key,
                task_description, work_dir, shared_state, config_overrides,
            )
    except Exception as e:
        logger.error("deepresearch_phase_exception task=%s stage=%d error=%s", task_id, stage_num, e, exc_info=True)
        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(
                f"Error: {e}"
            )
        # Mark stage as failed
        db = _get_db()
        try:
            sid = _get_session_id_for_task(task_id, db)
            repo = _get_stage_repo(db, session_id=sid)
            stages = repo.list_stages(parent_run_id=task_id)
            stage = next((s for s in stages if s.stage_number == stage_num), None)
            if stage:
                repo.update_stage_status(stage.id, "failed", error_message=str(e))
            db.commit()
        finally:
            db.close()
    finally:
        bg_key = f"{task_id}:{stage_num}"
        _running_tasks.pop(bg_key, None)
        # Schedule delayed buffer cleanup (gives WebSocket 60s to read remaining lines)
        async def _delayed_buffer_cleanup(key: str, delay: int = 60):
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                pass
            finally:
                _clear_console_buffer(key)
        asyncio.create_task(_delayed_buffer_cleanup(buf_key))


async def _run_planning_control_stage(
    task_id: str,
    stage_num: int,
    sdef: dict,
    buf_key: str,
    task_description: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Run stages 1-3 by calling planning_and_control_context_carryover directly.

    Sets up full callback infrastructure (CostCollector, ExecutionEvent logging,
    structured print callbacks) before calling the function, matching the
    observability of the standard task execution flow in task_executor.py.
    """
    from cmbagent.workflows.planning_control import planning_and_control_context_carryover
    from cmbagent.callbacks import merge_callbacks, create_print_callbacks, WorkflowCallbacks
    from task_framework import stage_helpers

    # ── 1. Set up DB session for cost + event tracking ──
    db = _get_db()
    session_id = _get_session_id_for_task(task_id, db)

    cost_collector = None
    event_repo = None
    try:
        from execution.cost_collector import CostCollector
        cost_collector = CostCollector(
            db_session=db,
            session_id=session_id,
            run_id=task_id,
        )
    except Exception as exc:
        logger.warning("deepresearch_cost_collector_init_failed error=%s", exc)

    try:
        from cmbagent.database.repository import EventRepository
        event_repo = EventRepository(db, session_id)
    except Exception as exc:
        logger.warning("deepresearch_event_repo_init_failed error=%s", exc)

    # ── 2. Build event tracking callbacks ──
    execution_order = [0]  # mutable counter for ordering

    def on_agent_msg(agent, role, content, metadata):
        if not event_repo:
            return
        try:
            execution_order[0] += 1
            event_repo.create_event(
                run_id=task_id,
                event_type="agent_call",
                execution_order=execution_order[0],
                agent_name=agent,
                status="completed",
                inputs={"role": role, "message": (content or "")[:500]},
                outputs={"full_content": (content or "")[:3000]},
                meta={"stage_num": stage_num, "stage_name": sdef["name"]},
            )
        except Exception as exc:
            logger.debug("deepresearch_event_create_failed error=%s", exc)
            try:
                db.rollback()
            except Exception:
                pass

    def on_code_exec(agent, code, language, result):
        if not event_repo:
            return
        try:
            execution_order[0] += 1
            event_repo.create_event(
                run_id=task_id,
                event_type="code_exec",
                execution_order=execution_order[0],
                agent_name=agent,
                status="completed",
                inputs={"language": language, "code": (code or "")[:2000]},
                outputs={"result": (str(result) if result else "")[:2000]},
                meta={"stage_num": stage_num, "stage_name": sdef["name"]},
            )
        except Exception as exc:
            logger.debug("deepresearch_code_event_failed error=%s", exc)
            try:
                db.rollback()
            except Exception:
                pass

    def on_tool(agent, tool_name, arguments, result):
        if not event_repo:
            return
        try:
            import json as _json
            execution_order[0] += 1
            args_str = _json.dumps(arguments, default=str)[:500] if isinstance(arguments, dict) else str(arguments)[:500]
            event_repo.create_event(
                run_id=task_id,
                event_type="tool_call",
                execution_order=execution_order[0],
                agent_name=agent,
                status="completed",
                inputs={"tool": tool_name, "args": args_str},
                outputs={"result": (str(result) if result else "")[:2000]},
                meta={"stage_num": stage_num, "stage_name": sdef["name"]},
            )
        except Exception as exc:
            logger.debug("deepresearch_tool_event_failed error=%s", exc)
            try:
                db.rollback()
            except Exception:
                pass

    def on_cost_update(cost_data):
        if cost_collector:
            try:
                cost_collector.collect_from_callback(cost_data)
            except Exception as exc:
                logger.debug("deepresearch_cost_callback_failed error=%s", exc)
                try:
                    db.rollback()
                except Exception:
                    pass

    event_tracking_callbacks = WorkflowCallbacks(
        on_agent_message=on_agent_msg,
        on_code_execution=on_code_exec,
        on_tool_call=on_tool,
        on_cost_update=on_cost_update,
    )

    workflow_callbacks = merge_callbacks(
        create_print_callbacks(),
        event_tracking_callbacks,
    )

    # ── 3. Build stage-specific kwargs ──
    data_description = shared_state.get("data_description") or task_description

    if stage_num == 1:
        kwargs = stage_helpers.build_idea_kwargs(
            data_description=data_description,
            work_dir=work_dir,
            parent_run_id=task_id,
            config_overrides=config_overrides,
        )
    elif stage_num == 2:
        if "research_idea" not in shared_state:
            raise ValueError("Stage 1 (Idea Generation) output is missing 'research_idea'. Re-run Stage 1.")
        kwargs = stage_helpers.build_method_kwargs(
            data_description=data_description,
            research_idea=shared_state["research_idea"],
            work_dir=work_dir,
            parent_run_id=task_id,
            config_overrides=config_overrides,
        )
    elif stage_num == 3:
        missing = [k for k in ("research_idea", "methodology") if k not in shared_state]
        if missing:
            raise ValueError(f"Previous stage outputs missing: {', '.join(missing)}. Re-run earlier stages.")
        kwargs = stage_helpers.build_experiment_kwargs(
            data_description=data_description,
            research_idea=shared_state["research_idea"],
            methodology=shared_state["methodology"],
            work_dir=work_dir,
            parent_run_id=task_id,
            config_overrides=config_overrides,
        )

    # Inject callbacks
    kwargs["callbacks"] = workflow_callbacks

    # Extract task arg (planning_and_control takes it as first positional arg)
    task_arg = kwargs.pop("task")

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Stage {stage_num} ({sdef['name']}) initialized, executing..."
        )

    # ── 4. Run with thread-isolated stdout capture ──
    # Install the global routing capture (idempotent), then run the function
    # inside _run_with_thread_capture which registers the worker thread's ID
    # → buf_key so ALL output (including from library sub-threads) is routed
    # to the correct console buffer.
    _install_console_capture()

    results = await asyncio.to_thread(
        _run_with_thread_capture,
        buf_key,
        planning_and_control_context_carryover,
        task_arg,
        **kwargs,
    )

    # ── 5. Extract results + save files ──
    # Truncate chat_history BEFORE passing it to the build_*_output
    # helpers. Full, un-truncated history is still persisted as JSON
    # files under ``<work_dir>/<stage>/chats/`` by cmbagent itself — we
    # only shrink the copy that goes into the DB ``output_data`` JSON
    # column, which grows unbounded on retry-heavy runs.
    chat_history_for_db = _truncate_chat_history_for_db(results["chat_history"])

    if stage_num == 1:
        # extract_idea_result walks the FULL chat_history (needed for the
        # broad fallback), not the DB-truncated one.
        research_idea = stage_helpers.extract_idea_result(results)
        idea_path = stage_helpers.save_idea(research_idea, work_dir)
        output_data = stage_helpers.build_idea_output(
            research_idea, data_description, idea_path, chat_history_for_db,
        )
    elif stage_num == 2:
        methodology = stage_helpers.extract_method_result(results)
        methods_path = stage_helpers.save_method(methodology, work_dir)
        output_data = stage_helpers.build_method_output(
            shared_state.get("research_idea", ""), data_description,
            methodology, methods_path, chat_history_for_db,
        )
    elif stage_num == 3:
        experiment_results, plot_paths = stage_helpers.extract_experiment_result(results)
        results_path, plots_dir, final_plot_paths = stage_helpers.save_experiment(
            experiment_results, plot_paths, work_dir,
        )
        output_data = stage_helpers.build_experiment_output(
            shared_state.get("research_idea", ""), data_description,
            shared_state.get("methodology", ""), experiment_results,
            final_plot_paths, results_path, plots_dir, chat_history_for_db,
            work_dir=work_dir,
        )

    # ── 6. Safety net: scan work_dir for cost files written to disk ──
    if cost_collector:
        try:
            cost_collector.collect_from_work_dir(work_dir)
        except Exception as exc:
            logger.debug("deepresearch_cost_work_dir_failed error=%s", exc)

    # Close the callback DB session — it may be in a bad state after
    # long-running callbacks.  Use a fresh session for the persist step.
    try:
        db.close()
    except Exception:
        pass

    # ── 7. Persist to DB (fresh session) ──
    persist_db = _get_db()
    try:
        repo = _get_stage_repo(persist_db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if stage:
            repo.update_stage_status(
                stage.id,
                "completed",
                output_data=output_data,
                output_files=list(output_data.get("artifacts", {}).values()),
            )
            logger.info("deepresearch_stage_completed task=%s stage=%d", task_id, stage_num)
            with _console_lock:
                _console_buffers.setdefault(buf_key, []).append(
                    f"Stage {stage_num} ({sdef['name']}) completed successfully."
                )

            # Update parent status: "completed" if all stages done
            refreshed = repo.list_stages(parent_run_id=task_id)
            if all(s.status == "completed" for s in refreshed):
                from cmbagent.database.models import WorkflowRun as _WR
                parent = persist_db.query(_WR).filter(_WR.id == task_id).first()
                if parent:
                    parent.status = "completed"

        persist_db.commit()
    finally:
        persist_db.close()


async def _run_paper_stage(
    task_id: str,
    stage_num: int,
    sdef: dict,
    buf_key: str,
    task_description: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Run stage 4 (paper generation) using DeepresearchPaperPhase (LangGraph)."""
    from task_framework.phases.paper import DeepresearchPaperPhase, DeepresearchPaperPhaseConfig
    from cmbagent.phases.base import PhaseContext, PhaseStatus
    from cmbagent.config.model_registry import get_model_registry

    stage_defaults = get_model_registry().get_stage_defaults("deepresearch", 4)
    config_kwargs = {"parent_run_id": task_id, **stage_defaults, **config_overrides}
    phase = DeepresearchPaperPhase(DeepresearchPaperPhaseConfig(**config_kwargs))

    context = PhaseContext(
        workflow_id=f"deepresearch-{task_id}",
        run_id=task_id,
        phase_id=f"stage-{stage_num}",
        task=task_description,
        work_dir=work_dir,
        shared_state=shared_state,
        api_keys={},
        callbacks=None,
    )

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Paper generation initialized, executing..."
        )

    # Run the phase with context-aware stdout capture.
    # Paper phase is async (runs in the event loop), so use contextvars
    # for routing.  Each asyncio task has its own context copy.
    _install_console_capture()
    _active_buf_key.set(buf_key)

    try:
        result = await phase.execute(context)
    finally:
        _active_buf_key.set(None)

    # Persist result to DB
    db = _get_db()
    try:
        sid = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=sid)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if stage:
            if result.status == PhaseStatus.COMPLETED:
                repo.update_stage_status(
                    stage.id,
                    "completed",
                    output_data=result.context.output_data,
                    output_files=list((result.context.output_data or {}).get("artifacts", {}).values()),
                )
                logger.info("deepresearch_stage_completed task=%s stage=%d", task_id, stage_num)
                with _console_lock:
                    _console_buffers.setdefault(buf_key, []).append(
                        f"Stage {stage_num} ({sdef['name']}) completed successfully."
                    )

                # Update parent status: "completed" if all stages done
                refreshed = repo.list_stages(parent_run_id=task_id)
                if all(s.status == "completed" for s in refreshed):
                    from cmbagent.database.models import WorkflowRun as _WR2
                    parent = db.query(_WR2).filter(_WR2.id == task_id).first()
                    if parent:
                        parent.status = "completed"
            else:
                repo.update_stage_status(
                    stage.id,
                    "failed",
                    error_message=result.error or "Phase failed",
                )
                logger.error("deepresearch_stage_failed task=%s stage=%d error=%s", task_id, stage_num, result.error)
                with _console_lock:
                    _console_buffers.setdefault(buf_key, []).append(
                        f"Stage {stage_num} failed: {result.error}"
                    )
        db.commit()
    finally:
        db.close()


# =============================================================================
# GET /api/deepresearch/{task_id}/stages/{num}/content
# =============================================================================

@router.get("/{task_id}/stages/{stage_num}/content", response_model=DeepresearchStageContentResponse)
async def get_stage_content(task_id: str, stage_num: int):
    """Get the output content and shared_state for a completed stage."""
    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        content = None
        shared = None
        if stage.output_data:
            shared = stage.output_data.get("shared")
            # Try to get main content from the shared_state key
            sdef = STAGE_DEFS[stage_num - 1]
            if sdef["shared_key"] and shared:
                content = shared.get(sdef["shared_key"])

            # Fallback 1: read from the .md file on disk
            if not content and sdef["file"]:
                from cmbagent.database.models import WorkflowRun
                parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
                work_dir = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
                file_path = os.path.join(work_dir, "input_files", sdef["file"])
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        content = f.read()

            # Fallback 2: re-extract from chat_history stored in output_data
            if not content and stage.output_data.get("chat_history"):
                try:
                    from task_framework import stage_helpers
                    if stage_num == 1:
                        content = stage_helpers.extract_idea_result(
                            {"chat_history": stage.output_data["chat_history"]}
                        )
                        # Repair: persist the recovered content back to DB and disk
                        if content and shared is not None and sdef["shared_key"]:
                            shared[sdef["shared_key"]] = content
                            stage.output_data["shared"] = shared
                            from cmbagent.database.repository import TaskStageRepository
                            repo.update_stage_status(
                                stage.id, "completed", output_data=stage.output_data
                            )
                            db.commit()
                            logger.info("deepresearch_content_recovered task=%s stage=%d len=%d",
                                        task_id, stage_num, len(content))
                except Exception as exc:
                    logger.warning("deepresearch_content_recovery_failed task=%s stage=%d error=%s",
                                   task_id, stage_num, exc)

        # Sanitize output_files: expand any directory entries to their actual files
        # (handles old tasks whose artifacts dict included 'paper/': <dir>)
        raw_files = stage.output_files or []
        sanitized_files = []
        for f in raw_files:
            if f and os.path.isfile(f):
                sanitized_files.append(f)
            elif f and os.path.isdir(f):
                # Expand directory: include .tex and .pdf files
                for fname in sorted(os.listdir(f)):
                    if fname.endswith(('.tex', '.pdf')):
                        sanitized_files.append(os.path.join(f, fname))

        # Stage 3 artifact manifest. New runs persist this in output_data;
        # for older completed runs we lazily backfill by walking work_dir.
        manifest_data = None
        if stage_num == 3 and stage.status == "completed":
            manifest_data = (stage.output_data or {}).get("artifact_manifest")
            if not manifest_data:
                from cmbagent.database.models import WorkflowRun
                from task_framework import stage_helpers
                parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
                wd = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
                if wd and os.path.isdir(os.path.join(wd, stage_helpers.EXPERIMENT_SUBDIR)):
                    try:
                        manifest_data = stage_helpers.collect_experiment_artifacts(wd)
                        stage_helpers.write_artifact_manifest(wd, manifest_data)
                        # Persist back so future reads are O(1)
                        new_output = dict(stage.output_data or {})
                        new_output["artifact_manifest"] = manifest_data
                        repo.update_stage_status(stage.id, stage.status, output_data=new_output)
                        db.commit()
                        logger.info("artifact_manifest_backfilled task=%s files=%d",
                                    task_id, sum(len(v) for v in manifest_data.values()))
                    except Exception as exc:
                        logger.warning("artifact_manifest_backfill_failed task=%s error=%s", task_id, exc)
                        manifest_data = None

        return DeepresearchStageContentResponse(
            stage_number=stage.stage_number,
            stage_name=stage.stage_name,
            status=stage.status,
            content=content,
            shared_state=shared,
            output_files=sanitized_files,
            artifact_manifest=ArtifactManifest(**manifest_data) if manifest_data else None,
        )
    finally:
        db.close()


# =============================================================================
# GET /api/deepresearch/{task_id}/stages/{num}/artifacts
# GET /api/deepresearch/{task_id}/stages/{num}/artifacts/zip
# =============================================================================

@router.get("/{task_id}/stages/{stage_num}/artifacts", response_model=DeepresearchArtifactsResponse)
async def list_stage_artifacts(task_id: str, stage_num: int, refresh: bool = False):
    """Return the categorized artifact manifest for a stage.

    By default reads the manifest stored in ``output_data`` (fast). If
    ``refresh=true``, re-walks the work directory — useful when files
    were added/removed by user edits or ad-hoc tool runs after the
    stage initially completed.

    Currently only Stage 3 (experiment) emits a manifest; other stages
    return an empty manifest with totals=0.
    """
    from task_framework import stage_helpers

    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        work_dir = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)

        manifest_data = None
        if stage_num == 3:
            if not refresh:
                manifest_data = (stage.output_data or {}).get("artifact_manifest")
            if refresh or not manifest_data:
                if work_dir and os.path.isdir(os.path.join(work_dir, stage_helpers.EXPERIMENT_SUBDIR)):
                    manifest_data = stage_helpers.collect_experiment_artifacts(work_dir)
                    stage_helpers.write_artifact_manifest(work_dir, manifest_data)
                    new_output = dict(stage.output_data or {})
                    new_output["artifact_manifest"] = manifest_data
                    repo.update_stage_status(stage.id, stage.status, output_data=new_output)
                    db.commit()

        manifest_obj = ArtifactManifest(**manifest_data) if manifest_data else ArtifactManifest()
        all_files = (
            manifest_obj.results + manifest_obj.plots + manifest_obj.code +
            manifest_obj.data + manifest_obj.reports + manifest_obj.chats +
            manifest_obj.planning
        )

        return DeepresearchArtifactsResponse(
            stage_number=stage.stage_number,
            stage_name=stage.stage_name,
            status=stage.status,
            work_dir=work_dir,
            artifact_manifest=manifest_obj,
            total_files=len(all_files),
            total_bytes=sum(a.size for a in all_files),
        )
    finally:
        db.close()


@router.get("/{task_id}/stages/{stage_num}/artifacts/zip")
async def download_stage_artifacts_zip(task_id: str, stage_num: int, categories: Optional[str] = None):
    """Stream a zip archive of the stage's artifacts.

    ``categories`` is an optional comma-separated subset, e.g.
    ``categories=plots,data``. When omitted, includes everything.
    Files are stored uncompressed (ZIP_STORED) — most artifacts are
    already binary/compressed and CPU-bound recompression doesn't pay.
    """
    import io
    import zipfile
    from fastapi.responses import StreamingResponse
    from task_framework import stage_helpers

    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        manifest_data = (stage.output_data or {}).get("artifact_manifest")
        if not manifest_data:
            from cmbagent.database.models import WorkflowRun
            parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            wd = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
            if wd and os.path.isdir(os.path.join(wd, stage_helpers.EXPERIMENT_SUBDIR)):
                manifest_data = stage_helpers.collect_experiment_artifacts(wd)

        if not manifest_data:
            raise HTTPException(status_code=404, detail="No artifacts available for this stage")

        wanted = None
        if categories:
            wanted = {c.strip() for c in categories.split(",") if c.strip()}

        # Build the zip in memory — typical run is < 100 MB; for very large
        # runs the user can fetch individual files via /api/files/download.
        buf = io.BytesIO()
        added = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
            for category, items in manifest_data.items():
                if wanted is not None and category not in wanted:
                    continue
                for item in items:
                    src = item.get("path")
                    if not src or not os.path.isfile(src):
                        continue
                    arc = os.path.join(category, item.get("rel_path") or item.get("name", ""))
                    try:
                        zf.write(src, arcname=arc)
                        added += 1
                    except OSError as exc:
                        logger.warning("artifact_zip_skip path=%s error=%s", src, exc)

        if added == 0:
            raise HTTPException(status_code=404, detail="No matching files to download")

        buf.seek(0)
        filename = f"deepresearch-{task_id}-stage{stage_num}-artifacts.zip"
        safe_filename = filename.replace('"', '\\"')
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
        )
    finally:
        db.close()


# =============================================================================
# PUT /api/deepresearch/{task_id}/stages/{num}/content
# =============================================================================

@router.put("/{task_id}/stages/{stage_num}/content")
async def update_stage_content(task_id: str, stage_num: int, request: DeepresearchContentUpdateRequest):
    """Save user edits to a stage's content.

    Updates both the markdown file on disk and the output_data['shared']
    in the database so the next stage reads the edited version.
    """
    if stage_num < 1 or stage_num > 4:
        raise HTTPException(status_code=400, detail="stage_num must be 1-4")

    sdef = STAGE_DEFS[stage_num - 1]

    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        if stage.status not in ("completed", "failed"):
            raise HTTPException(status_code=400, detail="Can only edit completed or recovered stages")

        # If stage was failed but has recovered content, mark it as completed
        new_status = "completed" if stage.status == "failed" else stage.status

        # Validate that field is an expected shared_state key
        allowed_fields = {"research_idea", "methodology", "results"}
        if request.field not in allowed_fields:
            raise HTTPException(status_code=400, detail=f"Invalid field '{request.field}'. Allowed: {sorted(allowed_fields)}")

        # Update output_data['shared'][field]
        output_data = stage.output_data or {}
        shared = output_data.get("shared", {})
        shared[request.field] = request.content
        output_data["shared"] = shared

        repo.update_stage_status(stage.id, new_status, output_data=output_data)

        # Also update the .md file on disk
        if sdef["file"]:
            from cmbagent.database.models import WorkflowRun
            parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            work_dir = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
            file_path = os.path.join(work_dir, "input_files", sdef["file"])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(request.content)

        db.commit()
        return {"status": "saved", "field": request.field}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# =============================================================================
# POST /api/deepresearch/{task_id}/stages/{num}/refine
# =============================================================================

@router.post("/{task_id}/stages/{stage_num}/refine", response_model=DeepresearchRefineResponse)
async def refine_stage_content(task_id: str, stage_num: int, request: DeepresearchRefineRequest):
    """Use LLM to refine stage content via diff-based patching.

    Flow:
      1. Ask the LLM for a JSON array of find→replace edits.
      2. Apply patches to the original content (unchanged text stays byte-identical).
      3. If JSON parsing or all patches fail, fall back to a full-document rewrite.

    Returns the refined content plus metadata about how it was produced.
    """
    import concurrent.futures
    from services.diff_patcher import refine_with_diff

    def _llm_call(messages, model, temperature, max_tokens):
        from cmbagent.llm_provider import safe_completion
        return safe_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    try:
        def _run():
            return refine_with_diff(
                content=request.content,
                user_request=request.message,
                llm_call=_llm_call,
                model="gpt-4o",
                temperature=0.4,
                fallback_temperature=0.7,
            )

        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await asyncio.get_running_loop().run_in_executor(executor, _run)

        edits_applied = len(result.applied)
        edits_failed = len(result.failed)
        method = result.method

        if method == "diff":
            msg = f"Applied {edits_applied} edit(s) via diff patching"
            if edits_failed:
                msg += f" ({edits_failed} edit(s) could not be located)"
        else:
            msg = "Content refined via full-document rewrite (diff patching was not possible)"

        return DeepresearchRefineResponse(
            refined_content=result.content,
            message=msg,
            method=method,
            edits_applied=edits_applied,
            edits_failed=edits_failed,
        )
    except Exception as e:
        logger.error("deepresearch_refine_failed error=%s", e)
        raise HTTPException(status_code=500, detail=f"Refinement failed: {str(e)}")


def _pick_plan_preview_model(task_meta: dict | None) -> tuple[str, str]:
    """Resolve which LLM to use for the cheap plan-preview call.

    Priority:
      1. ``task_meta['config']['planner_model']`` if the user set one for this task
      2. The active provider's "default" / first model from the registry
      3. A static fallback ('gpt-4o-mini') so the endpoint still works in
         barebones dev environments.

    Returns ``(model_id, source_label)``. ``source_label`` is logged so we
    can debug which path was taken.
    """
    cfg = (task_meta or {}).get("config") or {}
    user_pick = cfg.get("planner_model") or cfg.get("orchestration_model")
    if user_pick:
        return str(user_pick), "task_config"

    try:
        from cmbagent.providers.registry import ProviderRegistry
        registry = ProviderRegistry.instance()
        models = registry.get_available_models_for_configured_providers() or []
        if models:
            # Prefer a small/cheap model if one is obvious; otherwise first
            cheap_keywords = ("mini", "flash", "haiku", "small", "nano", "lite")
            for m in models:
                mid = (m.get("model_id") or m.get("id") or "").lower()
                if any(k in mid for k in cheap_keywords):
                    return m.get("model_id") or m.get("id") or "", "configured_cheap"
            first = models[0]
            picked = first.get("model_id") or first.get("id")
            if picked:
                return picked, "configured_first"
    except Exception:
        pass

    return "gpt-4o-mini", "static_fallback"


@router.post(
    "/{task_id}/stages/3/plan-preview",
    response_model=ExperimentPlanPreviewResponse,
)
async def preview_experiment_plan(task_id: str):
    """Generate a cheap preview of the experiment plan *before* committing to
    a full Stage-3 execution.

    Reads the idea/methods/data context from disk, asks an LLM for a short
    bulleted plan summary (steps, expected outputs, risks), and returns it
    as markdown. No artifacts are written; this does not advance the stage.
    """
    import concurrent.futures
    from cmbagent.database.models import WorkflowRun

    db = _get_db()
    try:
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")
        meta = parent.meta or {}
        work_dir = meta.get("work_dir") or _get_work_dir(task_id)
    finally:
        db.close()

    input_dir = os.path.join(work_dir, "input_files")
    parts: list[str] = []
    based_on: list[str] = []

    def _read(name: str, label: str) -> None:
        p = os.path.join(input_dir, name)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    txt = f.read().strip()
                if txt:
                    parts.append(f"## {label}\n\n{txt}")
                    based_on.append(name)
            except Exception:
                pass

    _read("idea.md", "Research Idea")
    _read("methods.md", "Methodology")
    _read("data_context.md", "Data Context")
    _read("data_description.md", "Data Description")

    if not parts:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot preview plan: idea.md and methods.md not found in "
                "input_files. Run Stage 1 and Stage 2 first."
            ),
        )

    research_context = "\n\n".join(parts)

    prompt = (
        "You are an experiment-planning assistant for a research codebase. "
        "Given the research idea, methodology, and any data context below, "
        "produce a SHORT actionable plan that the engineer agent will execute "
        "in Stage 3.\n\n"
        "Output a markdown document with these sections:\n"
        "  1. **Steps** — numbered list (max 6) of concrete actions: data prep, "
        "model fits, statistical tests, plots. Each item one line.\n"
        "  2. **Expected outputs** — bullets: which figures, metrics, or "
        "tables Stage 3 should produce.\n"
        "  3. **Risks / unknowns** — bullets: what could fail or take longer "
        "than expected. Be specific to the data described above.\n\n"
        "Be concise. Do not invent data sources not implied by the inputs. "
        "Do not output code.\n\n"
        f"### Inputs\n\n{research_context}\n"
    )

    model, source = _pick_plan_preview_model(meta)
    logger.info("plan_preview_model task=%s model=%s source=%s", task_id, model, source)

    def _llm_call() -> str:
        from cmbagent.llm_provider import safe_completion
        resp = safe_completion(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            temperature=0.3,
            max_tokens=1200,
        )
        # safe_completion returns either a string or an object with .content
        if isinstance(resp, str):
            return resp
        return getattr(resp, "content", str(resp))

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            plan_md = await asyncio.get_running_loop().run_in_executor(executor, _llm_call)
    except Exception as e:
        logger.error("plan_preview_failed task=%s model=%s error=%s", task_id, model, e)
        raise HTTPException(status_code=500, detail=f"Plan preview failed: {e}")

    return ExperimentPlanPreviewResponse(
        plan_markdown=plan_md.strip() if isinstance(plan_md, str) else str(plan_md),
        based_on=based_on,
    )


# =============================================================================
# File Analysis  (POST analyze-files, GET console, PUT context, POST refine, PATCH description)
# =============================================================================

@router.post("/{task_id}/analyze-files", response_model=AnalyzeFilesResponse)
async def analyze_files(task_id: str):
    """Analyze uploaded files using LLM — runs in background.

    Extracts metadata for CSV/TSV, JSON, TXT, FITS, HDF5, NPY/NPZ, PDF files,
    then calls gpt-4o to produce a structured Research Data Context document
    saved to input_files/data_context.md.

    Poll GET /{task_id}/analyze-files/console for streaming progress.
    """
    if task_id in _running_analyses and not _running_analyses[task_id].done():
        raise HTTPException(status_code=409, detail="Analysis already running")

    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent_run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent_run:
            raise HTTPException(status_code=404, detail="Task not found")
        work_dir = (parent_run.meta or {}).get("work_dir") or _get_work_dir(task_id)
    finally:
        db.close()

    buf_key = f"{task_id}:analyze"
    with _console_lock:
        _console_buffers[buf_key] = ["Starting file analysis..."]

    task_obj = asyncio.create_task(_run_file_analysis(task_id, work_dir, buf_key))
    _running_analyses[task_id] = task_obj
    return AnalyzeFilesResponse()


@router.get("/{task_id}/analyze-files/console")
async def get_analyze_console(task_id: str, since: int = 0):
    """Poll analysis progress. Returns is_done=True and context_text when complete."""
    buf_key = f"{task_id}:analyze"
    raw_lines = _get_console_lines(buf_key, since_index=since)

    with _console_lock:
        full_buf = list(_console_buffers.get(buf_key, []))
    has_done = "__ANALYZE_DONE__" in full_buf
    has_error = "__ANALYZE_ERROR__" in full_buf
    is_done = has_done or has_error

    # Calculate next_index from raw (unfiltered) lines so the client
    # advances past sentinel entries and never re-fetches them.
    next_index = since + len(raw_lines)

    # Filter sentinels from displayed lines
    display_lines = [l for l in raw_lines if l not in ("__ANALYZE_DONE__", "__ANALYZE_ERROR__")]

    context_text = None
    if has_done:
        db = _get_db()
        try:
            from cmbagent.database.models import WorkflowRun
            run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            work_dir = (run.meta or {}).get("work_dir") if run and run.meta else _get_work_dir(task_id)
        finally:
            db.close()
        ctx_path = os.path.join(work_dir, "input_files", "data_context.md")
        if os.path.isfile(ctx_path):
            try:
                with open(ctx_path, 'r', encoding='utf-8') as f:
                    context_text = f.read()
            except Exception:
                pass

    return {
        "lines": display_lines,
        "next_index": next_index,
        "is_done": is_done,
        "has_error": has_error,
        "context_text": context_text,
    }


@router.put("/{task_id}/context")
async def save_file_context(task_id: str, request: RefineContextRequest):
    """Save an edited data context directly to data_context.md (no LLM involved)."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")
        work_dir = (run.meta or {}).get("work_dir") or _get_work_dir(task_id)
    finally:
        db.close()

    ctx_path = os.path.join(work_dir, "input_files", "data_context.md")
    try:
        with open(ctx_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "saved"}


@router.post("/{task_id}/refine-context", response_model=RefineContextResponse)
async def refine_file_context(task_id: str, request: RefineContextRequest):
    """Use LLM to refine the data context via diff-based patching, then save."""
    import concurrent.futures
    from services.diff_patcher import refine_with_diff

    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")
        work_dir = (run.meta or {}).get("work_dir") or _get_work_dir(task_id)
    finally:
        db.close()

    def _llm_call(messages, model, temperature, max_tokens):
        from cmbagent.llm_provider import safe_completion
        return safe_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    try:
        def _run():
            return refine_with_diff(
                content=request.content,
                user_request=request.message,
                llm_call=_llm_call,
                model="gpt-4o",
                temperature=0.4,
                fallback_temperature=0.4,
            )

        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await asyncio.get_running_loop().run_in_executor(executor, _run)

        ctx_path = os.path.join(work_dir, "input_files", "data_context.md")
        with open(ctx_path, 'w', encoding='utf-8') as f:
            f.write(result.content)

        return RefineContextResponse(refined_content=result.content)
    except Exception as e:
        logger.error("deepresearch_refine_context_failed error=%s", e)
        raise HTTPException(status_code=500, detail=f"Refinement failed: {str(e)}")


@router.patch("/{task_id}/description")
async def update_task_description(task_id: str, request: UpdateDescriptionRequest):
    """Update task description and/or data description — used when task is pre-created."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")
        if request.task is not None:
            run.task_description = request.task
        if request.data_description is not None:
            meta = dict(run.meta or {})
            meta["data_description"] = request.data_description
            run.meta = meta
            work_dir = meta.get("work_dir") or _get_work_dir(task_id)
            desc_path = os.path.join(work_dir, "input_files", "data_description.md")
            os.makedirs(os.path.dirname(desc_path), exist_ok=True)
            with open(desc_path, 'w', encoding='utf-8') as f:
                f.write(request.data_description)
        db.commit()
        return {"status": "updated"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


async def _run_file_analysis(task_id: str, work_dir: str, buf_key: str):
    """Background: inspect each uploaded file, build LLM prompt, write data_context.md."""
    import concurrent.futures

    def _do_analysis():
        input_dir = os.path.join(work_dir, "input_files")
        if not os.path.isdir(input_dir):
            return "No input_files directory found."

        file_infos = []
        for entry in sorted(os.listdir(input_dir)):
            if entry in _AUTO_GENERATED_FILES or entry in _AUTO_GENERATED_DIRS:
                continue
            full_path = os.path.join(input_dir, entry)
            if not os.path.isfile(full_path):
                continue
            file_infos.append((entry, full_path))

        if not file_infos:
            return "No user-uploaded data files found to analyze."

        with _console_lock:
            _console_buffers[buf_key].append(
                f"Found {len(file_infos)} file(s). Extracting metadata..."
            )

        summaries = []
        for name, path in file_infos:
            with _console_lock:
                _console_buffers[buf_key].append(f"  \u2192 Inspecting: {name}")

            size = os.path.getsize(path)
            size_str = (
                f"{size}B" if size < 1024
                else f"{size/1024:.1f}KB" if size < 1024 * 1024
                else f"{size/1024/1024:.1f}MB"
            )
            ext = os.path.splitext(name)[1].lower()
            info = [f"### File: `{name}` ({size_str})", f"**Path:** `{path}`"]

            try:
                if ext in ('.csv', '.tsv'):
                    import csv as _csv
                    delim = '\t' if ext == '.tsv' else ','
                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                        reader = _csv.reader(f, delimiter=delim)
                        rows = []
                        for i, row in enumerate(reader):
                            if i >= 35:
                                rows.append(['...'])
                                break
                            rows.append(row)
                    if rows:
                        info.append(f"Format: {'TSV' if ext == '.tsv' else 'CSV'}, {len(rows[0])} columns")
                        info.append(f"Columns: {', '.join(rows[0])}")
                        info.append(f"Preview ({min(5, len(rows)-1)} data rows):")
                        info.append("```")
                        info.append(', '.join(str(v) for v in rows[0]))
                        for r in rows[1:6]:
                            info.append(', '.join(str(v) for v in r))
                        info.append("```")

                elif ext == '.json':
                    import json as _json
                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                        raw = f.read(100_000)
                    try:
                        data = _json.loads(raw)
                        if isinstance(data, list):
                            info.append(f"Format: JSON array with {len(data)} items")
                            if data and isinstance(data[0], dict):
                                info.append(f"Item keys: {list(data[0].keys())}")
                                info.append("```json")
                                info.append(_json.dumps(data[0], indent=2)[:600])
                                info.append("```")
                        elif isinstance(data, dict):
                            info.append(f"Format: JSON object, keys: {list(data.keys())}")
                            info.append("```json")
                            info.append(_json.dumps({k: data[k] for k in list(data)[:10]}, indent=2)[:600])
                            info.append("```")
                    except _json.JSONDecodeError:
                        info.append("Note: file does not parse as valid JSON")

                elif ext in ('.txt', '.md', '.dat'):
                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                        preview = [f.readline() for _ in range(50)]
                    preview = [l.rstrip('\n') for l in preview if l]
                    info.append(f"Format: text ({len(preview)} lines shown):")
                    info.append("```")
                    info.extend(preview)
                    info.append("```")

                elif ext in ('.fits', '.fit', '.fts'):
                    try:
                        import astropy.io.fits as fits
                        with fits.open(path) as hdul:
                            info.append(f"Format: FITS with {len(hdul)} HDU(s):")
                            for i, hdu in enumerate(hdul):
                                shape = hdu.data.shape if hdu.data is not None else None
                                info.append(f"  HDU {i} ({type(hdu).__name__}): shape={shape}")
                                if hasattr(hdu, 'columns') and hdu.columns:
                                    info.append(f"    Columns: {', '.join(hdu.columns.names)}")
                                interesting = [
                                    'BUNIT', 'CRVAL1', 'CRVAL2', 'OBJECT',
                                    'TELESCOP', 'INSTRUME', 'DATE-OBS',
                                ]
                                if hdu.header:
                                    hdr_items = [(k, v) for k, v in hdu.header.items()
                                                 if k in interesting and v]
                                    if hdr_items:
                                        info.append("    Key header: " +
                                                    ', '.join(f'{k}={v}' for k, v in hdr_items))
                    except ImportError:
                        info.append("Format: FITS (astropy not available)")
                    except Exception as e:
                        info.append(f"Format: FITS (read error: {e})")

                elif ext in ('.hdf5', '.h5', '.he5'):
                    try:
                        import h5py
                        with h5py.File(path, 'r') as f:
                            info.append("Format: HDF5, structure:")
                            def _visit(name, obj):
                                if name.count('/') >= 4:
                                    return
                                if isinstance(obj, h5py.Dataset):
                                    info.append(f"  Dataset /{name}: shape={obj.shape}, dtype={obj.dtype}")
                                elif isinstance(obj, h5py.Group):
                                    info.append(f"  Group   /{name}/")
                            f.visititems(_visit)
                    except ImportError:
                        info.append("Format: HDF5 (h5py not available)")
                    except Exception as e:
                        info.append(f"Format: HDF5 (read error: {e})")

                elif ext == '.npy':
                    try:
                        import numpy as np
                        arr = np.load(path, allow_pickle=False)
                        info.append(f"Format: NumPy array, shape={arr.shape}, dtype={arr.dtype}")
                        if arr.size > 0:
                            info.append(f"  min={float(arr.min()):.4g}, "
                                        f"max={float(arr.max()):.4g}, "
                                        f"mean={float(arr.mean()):.4g}")
                    except Exception as e:
                        info.append(f"Format: NumPy array (read error: {e})")

                elif ext == '.npz':
                    try:
                        import numpy as np
                        data = np.load(path, allow_pickle=False)
                        info.append(f"Format: NumPy archive, {len(data.files)} arrays:")
                        for key in data.files:
                            arr = data[key]
                            info.append(f"  '{key}': shape={arr.shape}, dtype={arr.dtype}")
                    except Exception as e:
                        info.append(f"Format: NumPy archive (read error: {e})")

                elif ext == '.pdf':
                    try:
                        from services.pdf_extractor import extract_pdf_content
                        # Extract up to 8000 chars to give LLM rich context
                        extracted = extract_pdf_content(path, max_chars=8000)
                        if extracted:
                            # Count pages via PyMuPDF
                            try:
                                import fitz
                                doc = fitz.open(path)
                                num_pages = len(doc)
                                doc.close()
                                info.append(f"Format: PDF, {num_pages} pages")
                            except Exception:
                                info.append("Format: PDF")
                            info.append(f"Extracted content:\n```\n{extracted}\n```")
                        else:
                            info.append("Format: PDF (text extraction returned no content)")
                    except Exception as e:
                        info.append(f"Format: PDF (read error: {e})")

                else:
                    info.append(f"Format: binary ({ext or 'unknown extension'}), {size_str}")

            except Exception as e:
                info.append(f"Error inspecting file: {e}")

            summaries.append("\n".join(info))

        files_section = "\n\n".join(summaries)
        with _console_lock:
            _console_buffers[buf_key].append(
                "Sending file metadata to LLM for scientific analysis..."
            )

        from cmbagent.llm_provider import safe_completion

        logger.info("File analysis: %d files inspected, sending to LLM", len(file_infos))
        logger.debug("File analysis prompt preview (first 500 chars): %s", files_section[:500])

        prompt = (
            "You are an expert research data analyst. Analyze the following research data files "
            "and produce a comprehensive, structured data context document.\n\n"
            "This context will be used by an AI research assistant to:\n"
            "1. Generate research ideas grounded in what the data can actually support\n"
            "2. Design methodologies that reference correct variable names, file paths, "
            "and data structures\n"
            "3. Write experiment code that correctly reads and processes these exact files\n\n"
            f"## Uploaded Research Files\n\n{files_section}\n\n"
            "## Instructions\n"
            "Generate a structured **Research Data Context** document covering:\n"
            "1. **Dataset Overview** - What dataset(s) are these? Source, survey, instrument, "
            "origin if identifiable.\n"
            "2. **File Inventory** - For each file: purpose, format, key contents, and the "
            "absolute path for use in code.\n"
            "3. **Key Variables & Columns** - Important variables with exact names, physical "
            "units, expected ranges, scientific meaning.\n"
            "4. **Data Dimensions & Scale** - Number of rows/samples, time range, spatial "
            "coverage, spectral range, etc.\n"
            "5. **Relationships Between Files** - How files relate to each other, join keys, "
            "shared indices.\n"
            "6. **Scientific Context** - What scientific questions this dataset is suited to "
            "answer.\n"
            "7. **Analysis Notes** - Known quirks, missing values, coordinate systems, "
            "calibration status, caveats.\n\n"
            "Be specific and factual. Use exact variable/column names from the files. "
            "Use markdown formatting.\n"
            "Output ONLY the data context document - no preamble, no explanation."
        )

        result = safe_completion(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.3,
            max_tokens=4000,
        )
        logger.info("File analysis LLM response length: %d", len(result) if result else 0)

        if not result or not result.strip():
            logger.warning("File analysis: LLM returned empty response, using file summaries as fallback")
            result = (
                "# Research Data Context\n\n"
                "*(Auto-generated from file metadata — LLM analysis returned no content)*\n\n"
                + files_section
            )

        return result

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            context_text = await asyncio.get_running_loop().run_in_executor(executor, _do_analysis)

        ctx_path = os.path.join(work_dir, "input_files", "data_context.md")
        logger.info("Writing data_context.md to %s (length=%d)", ctx_path, len(context_text) if context_text else 0)
        os.makedirs(os.path.dirname(ctx_path), exist_ok=True)
        with open(ctx_path, 'w', encoding='utf-8') as f:
            f.write(context_text)

        with _console_lock:
            _console_buffers[buf_key].append("\u2713 Analysis complete. Data context saved.")
            _console_buffers[buf_key].append("__ANALYZE_DONE__")
        logger.info("deepresearch_analyze_complete task_id=%s ctx_path=%s", task_id, ctx_path)
    except Exception as e:
        logger.error("deepresearch_analyze_failed task_id=%s error=%s", task_id, e, exc_info=True)
        with _console_lock:
            _console_buffers[buf_key].append(f"Error: {e}")
            _console_buffers[buf_key].append("__ANALYZE_ERROR__")
    finally:
        _running_analyses.pop(task_id, None)


# =============================================================================
# GET /api/deepresearch/{task_id}/stages/{num}/console  (REST fallback for console)
# =============================================================================

@router.get("/{task_id}/stages/{stage_num}/console")
async def get_stage_console(task_id: str, stage_num: int, since: int = 0):
    """Get console output lines for a running stage (REST polling fallback).

    Args:
        since: Line index to start from (for incremental fetching)
    """
    buf_key = f"{task_id}:{stage_num}"
    lines = _get_console_lines(buf_key, since_index=since)
    return {
        "lines": lines,
        "next_index": since + len(lines),
        "stage_num": stage_num,
    }


# =============================================================================
# GET /api/deepresearch/recent  (must be before /{task_id} to avoid route conflict)
# =============================================================================

@router.get("/recent", response_model=List[DeepresearchRecentTaskResponse])
async def list_recent_tasks(include_all: bool = False):
    """List Deepresearch tasks for the session sidebar.

    Args:
        include_all: If True, include completed and failed tasks too.
                     If False (default), only return active/in-progress tasks.
    """
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun

        query = db.query(WorkflowRun).filter(
            WorkflowRun.mode == "deepresearch-research",
            WorkflowRun.parent_run_id.is_(None),  # Only parent runs
        )

        if not include_all:
            query = query.filter(
                WorkflowRun.status.in_(["executing", "draft", "planning"]),
            )

        runs = (
            query
            .order_by(WorkflowRun.started_at.desc())
            .limit(50)
            .all()
        )

        result = []
        parent_status_changed = False
        for run in runs:
            repo = _get_stage_repo(db, session_id=run.session_id)
            progress = repo.get_task_progress(parent_run_id=run.id)
            current_stage = None
            stages = repo.list_stages(parent_run_id=run.id)
            for s in stages:
                if s.status != "completed":
                    current_stage = s.stage_number
                    break

            # Compute effective status from child stages for reliability.
            # The parent WorkflowRun.status may be stale (e.g. "failed" after
            # a stop, but user has retried and a stage is now "running").
            effective_status = run.status
            has_running = any(s.status == "running" for s in stages)
            has_failed = any(s.status == "failed" for s in stages)
            all_completed = all(s.status == "completed" for s in stages) and len(stages) > 0

            if has_running:
                effective_status = "executing"
            elif all_completed:
                effective_status = "completed"
            elif has_failed and not has_running:
                effective_status = "failed"

            # Sync parent status if it diverged from computed status
            if run.status != effective_status:
                run.status = effective_status
                parent_status_changed = True

            result.append(DeepresearchRecentTaskResponse(
                task_id=run.id,
                task=run.task_description or "",
                status=effective_status,
                created_at=run.started_at.isoformat() if run.started_at else None,
                current_stage=current_stage,
                progress_percent=progress.get("progress_percent", 0.0),
            ))

        if parent_status_changed:
            db.commit()

        return result
    finally:
        db.close()


# =============================================================================
# POST /api/deepresearch/{task_id}/stop
# =============================================================================

@router.post("/{task_id}/stop")
async def stop_task(task_id: str):
    """Stop a running Deepresearch task.

    Cancels any executing background stage and marks it as failed.
    """
    # Cancel any running asyncio tasks for this task_id
    cancelled = []
    for key in list(_running_tasks):
        if key.startswith(f"{task_id}:"):
            bg_task = _running_tasks.get(key)
            if bg_task and not bg_task.done():
                bg_task.cancel()
                cancelled.append(key)

    # Update DB: mark running stages as failed
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        session_id = parent.session_id
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        for s in stages:
            if s.status == "running":
                repo.update_stage_status(s.id, "failed", error_message="Stopped by user")

        parent.status = "failed"
        db.commit()

        return {"status": "stopped", "task_id": task_id, "cancelled_stages": cancelled}
    finally:
        db.close()


# =============================================================================
# DELETE /api/deepresearch/{task_id}
# =============================================================================

@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a Deepresearch task, its DB records, and its work directory.

    Running stages are cancelled first.
    """
    import shutil

    # 1. Cancel any running background tasks
    for key in list(_running_tasks):
        if key.startswith(f"{task_id}:"):
            bg_task = _running_tasks.pop(key, None)
            if bg_task and not bg_task.done():
                bg_task.cancel()

    # Clean up console buffers (thread-safe: snapshot + remove inside lock)
    with _console_lock:
        keys_to_remove = [key for key in _console_buffers if key.startswith(f"{task_id}:")]
        for key in keys_to_remove:
            _console_buffers.pop(key, None)

    # 2. Delete DB records
    db = _get_db()
    work_dir = None
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        work_dir = (parent.meta or {}).get("work_dir")
        session_id = parent.session_id

        try:
            # TaskStage rows first (cascade in model, explicit for SQLite-migrated DBs).
            repo = _get_stage_repo(db, session_id=session_id)
            stages = repo.list_stages(parent_run_id=task_id)
            for s in stages:
                db.delete(s)
            db.flush()

            # Orphaned child stage runs — parent_run_id FK is "SET NULL" so they
            # otherwise linger. Delete them explicitly to keep the DB clean.
            child_runs = db.query(WorkflowRun).filter(WorkflowRun.parent_run_id == task_id).all()
            for c in child_runs:
                db.delete(c)
            db.flush()

            db.delete(parent)
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("deepresearch_delete_failed task_id=%s error=%s", task_id, exc)
            raise HTTPException(status_code=500, detail=f"Delete failed: {exc}") from exc
    finally:
        db.close()

    # 3. Remove work directory from disk
    if work_dir and os.path.isdir(work_dir):
        try:
            shutil.rmtree(work_dir)
        except Exception as exc:
            logger.warning("deepresearch_delete_workdir_failed path=%s error=%s", work_dir, exc)

    return {"status": "deleted", "task_id": task_id}


# =============================================================================
# POST /api/deepresearch/{task_id}/ai-edit-tex
# =============================================================================

@router.post("/{task_id}/ai-edit-tex", response_model=AiEditTexResponse)
async def ai_edit_tex(task_id: str, request: AiEditTexRequest):
    """Use an LLM to apply a natural-language edit instruction to a .tex file.

    Returns the edited LaTeX source. The caller is responsible for saving it
    (via PUT /api/files/content) before compiling.
    """
    import concurrent.futures

    tex_path = os.path.realpath(request.tex_path)

    # Validate the .tex path belongs to this task's work directory
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")
        work_dir = (parent.meta or {}).get("work_dir") or _get_work_dir(task_id)
        work_dir = os.path.realpath(work_dir)
        if not (tex_path == work_dir or tex_path.startswith(work_dir + os.sep)):
            raise HTTPException(status_code=403, detail="TeX file path is outside the task's working directory")
    finally:
        db.close()

    if not os.path.isfile(tex_path):
        raise HTTPException(status_code=404, detail="TeX file not found")

    try:
        with open(tex_path, "r", encoding="utf-8") as f:
            original = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read TeX file: {e}")

    system_prompt = (
        "You are an expert LaTeX editor. The user will give you a LaTeX source document "
        "and an instruction describing modifications to make. "
        "Apply the instruction carefully and return ONLY the complete modified LaTeX source, "
        "with no additional commentary, markdown fences, or explanations."
    )
    user_prompt = (
        f"--- INSTRUCTION ---\n{request.instruction}\n\n"
        f"--- CURRENT LATEX SOURCE ---\n{original}"
    )

    try:
        def _call_llm():
            from cmbagent.llm_provider import safe_completion
            return safe_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="gpt-4o",
                temperature=0.2,
                max_tokens=8192,
            )

        with concurrent.futures.ThreadPoolExecutor() as executor:
            edited = await asyncio.get_running_loop().run_in_executor(executor, _call_llm)

        return AiEditTexResponse(edited_content=edited or original)
    except Exception as e:
        logger.error("deepresearch_ai_edit_tex_failed task=%s error=%s", task_id, e)
        raise HTTPException(status_code=500, detail=f"AI edit failed: {e}")


# =============================================================================
# POST /api/deepresearch/{task_id}/compile-tex
# =============================================================================

@router.post("/{task_id}/compile-tex", response_model=CompileTexResponse)
async def compile_tex(task_id: str, request: CompileTexRequest):
    """Compile a .tex file to PDF using xelatex.

    The .tex file must already be saved on disk before calling this endpoint.
    Returns the path to the generated PDF and the compiler log.
    """
    import concurrent.futures
    import subprocess
    import shutil

    tex_path = os.path.realpath(request.tex_path)

    # Validate the .tex path belongs to this task's work directory
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")
        work_dir = (parent.meta or {}).get("work_dir") or _get_work_dir(task_id)
        work_dir = os.path.realpath(work_dir)
        if not (tex_path == work_dir or tex_path.startswith(work_dir + os.sep)):
            raise HTTPException(status_code=403, detail="TeX file path is outside the task's working directory")
    finally:
        db.close()

    if not os.path.isfile(tex_path):
        raise HTTPException(status_code=404, detail="TeX file not found")

    tex_dir = os.path.dirname(tex_path)
    tex_name = os.path.basename(tex_path)
    tex_stem = os.path.splitext(tex_name)[0]
    pdf_path = os.path.join(tex_dir, f"{tex_stem}.pdf")
    bib_path = os.path.join(tex_dir, "bibliography.bib")

    def _compile():
        log_lines = []

        def run_xelatex():
            result = subprocess.run(
                ["xelatex", "-no-shell-escape", "-interaction=nonstopmode", "-file-line-error", tex_name],
                cwd=tex_dir,
                input="\n",
                capture_output=True,
                text=True,
                timeout=120,  # 2 min timeout per xelatex run
            )
            log_lines.append(result.stdout[-4000:] if result.stdout else "")
            return result.returncode == 0

        def run_bibtex():
            subprocess.run(
                ["bibtex", tex_stem],
                cwd=tex_dir,
                capture_output=True,
                text=True,
                timeout=60,  # 1 min timeout for bibtex
            )

        ok = run_xelatex()
        if os.path.exists(bib_path):
            run_bibtex()
            run_xelatex()
            run_xelatex()
        else:
            run_xelatex()

        # Clean auxiliary files
        for ext in ("aux", "log", "out", "bbl", "blg", "synctex.gz"):
            aux = os.path.join(tex_dir, f"{tex_stem}.{ext}")
            if os.path.exists(aux):
                os.remove(aux)

        success = os.path.exists(pdf_path)
        return success, "\n".join(log_lines)

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            success, log = await asyncio.get_running_loop().run_in_executor(executor, _compile)

        return CompileTexResponse(
            pdf_path=pdf_path if success else None,
            success=success,
            log=log,
        )
    except Exception as e:
        logger.error("deepresearch_compile_tex_failed task=%s error=%s", task_id, e)
        raise HTTPException(status_code=500, detail=f"Compilation failed: {e}")


# =============================================================================
# GET /api/deepresearch/{task_id}
# =============================================================================

@router.get("/{task_id}", response_model=DeepresearchTaskStateResponse)
async def get_task_state(task_id: str):
    """Get full task state for resume - all stages, costs, and progress.

    Automatically detects and resets stale 'running' stages (no active
    background task) so the frontend never sees a permanently stuck stage.
    """
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        repo = _get_stage_repo(db, session_id=parent.session_id)
        stages = repo.list_stages(parent_run_id=task_id)

        # Auto-recover stale "running" stages on read
        stale_recovered = False
        for s in stages:
            if s.status == "running":
                bg_key = f"{task_id}:{s.stage_number}"
                has_active_task = bg_key in _running_tasks and not _running_tasks[bg_key].done()
                if not has_active_task:
                    logger.warning(
                        "get_task_state: resetting stale 'running' stage %d for task %s",
                        s.stage_number, task_id,
                    )
                    repo.update_stage_status(
                        s.id, "failed",
                        error_message="Execution was interrupted. Click retry to re-run.",
                    )
                    stale_recovered = True

        if stale_recovered:
            db.commit()

        # Refresh stages after possible status updates
        stages = repo.list_stages(parent_run_id=task_id)
        progress = repo.get_task_progress(parent_run_id=task_id)

        # Get cost info
        total_cost = None
        try:
            cost_repo = _get_cost_repo(db, session_id=parent.session_id)
            cost_info = cost_repo.get_task_total_cost(parent_run_id=task_id)
            total_cost = cost_info.get("total_cost_usd")
        except Exception:
            pass

        # Determine current stage
        current_stage = None
        for s in stages:
            if s.status == "running":
                current_stage = s.stage_number
                break
        if current_stage is None:
            # Find first non-completed stage
            for s in stages:
                if s.status != "completed":
                    current_stage = s.stage_number
                    break

        return DeepresearchTaskStateResponse(
            task_id=task_id,
            task=parent.task_description or "",
            status=parent.status,
            work_dir=(parent.meta or {}).get("work_dir"),
            created_at=parent.started_at.isoformat() if parent.started_at else None,
            stages=[_stage_to_response(s) for s in stages],
            current_stage=current_stage,
            progress_percent=progress.get("progress_percent", 0.0),
            total_cost_usd=total_cost,
        )
    finally:
        db.close()
