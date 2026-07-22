"""
FastAPI application factory and configuration.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import configure_logging

# Global app instance
_app: FastAPI = None

# Store log config for re-application after uvicorn overrides
_log_config = {}


def _get_default_log_file() -> str:
    work_dir = os.getenv("CMBAGENT_DEFAULT_WORK_DIR", "~/Desktop/cmbdir")
    work_dir = os.path.expanduser(work_dir)
    log_dir = Path(work_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return str(log_dir / "backend.log")


def _recover_stale_running_stages():
    """Reset any stages stuck in 'running' status from a previous server session."""
    import logging
    log = logging.getLogger(__name__)
    try:
        from cmbagent.database.base import init_database, get_db_session
        from cmbagent.database.models import TaskStage
        from datetime import datetime, timezone

        init_database()
        db = get_db_session()
        try:
            stale = db.query(TaskStage).filter(TaskStage.status == "running").all()
            if stale:
                log.warning(
                    "Found %d stale 'running' stage(s) from previous session — resetting to 'failed'",
                    len(stale),
                )
                for stage in stale:
                    stage.status = "failed"
                    stage.error_message = (
                        "Server restarted while stage was running. Click retry to re-execute."
                    )
                    stage.completed_at = datetime.now(timezone.utc)
                db.commit()
            else:
                log.info("No stale running stages found — clean startup")
        finally:
            db.close()
    except Exception as exc:
        log.error("Failed to recover stale stages on startup: %s", exc, exc_info=True)


def _init_auth_tables():
    """Import auth models so they are registered with the shared Base before init_database()."""
    try:
        import models.auth  # noqa — registers User, UserRefreshToken, AdminApprovalLog, UserAuditLog
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Could not import auth models: %s", exc)


def _bootstrap_default_admin():
    """Create the default admin user and migrate orphan sessions if env vars are set."""
    import logging
    log = logging.getLogger(__name__)
    try:
        from cmbagent.database.base import get_db_session
        db = get_db_session()
        try:
            from services.default_admin import bootstrap_default_admin
            admin_id = bootstrap_default_admin(db)
            if admin_id:
                log.info("Default admin ready (id=%s)", admin_id)
        finally:
            db.close()
    except Exception as exc:
        log.warning("Default admin bootstrap failed (non-fatal): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: logging, tracing, credentials, stale-stage recovery, admin bootstrap."""
    configure_logging(**_log_config)
    import logging
    log = logging.getLogger(__name__)
    log.info("Backend started, logs writing to %s", _log_config.get("log_file", "console"))

    # --- Tracing (init once at startup) ---
    _tracer_provider = None
    try:
        from cmbagent.tracing import init_tracing, shutdown_tracing
        from services.tracing_bridge import init_paperpulse_tracing, instrument_langchain

        _tracer_provider = init_tracing(
            service_name="MARS-PaperPulse",
            trace_name="paperpulse-backend",
        )
        init_paperpulse_tracing(_tracer_provider)
        # Instrument LangChain/LangGraph so stages 4-5 (paper/report) LLM calls
        # are exported to Langfuse alongside the AG2-based stages 1-3.
        instrument_langchain(_tracer_provider)
        if _tracer_provider:
            log.info("Langfuse tracing enabled")
        else:
            log.info("Langfuse tracing disabled (LANGFUSE_PUBLIC_KEY not set)")
    except Exception as exc:
        log.warning("Tracing init failed (non-fatal): %s", exc)

    # --- Credential sync ---
    try:
        from services.config_bridge import ConfigBridge
        sync_results = ConfigBridge.sync_all()
        log.info("Credential sync on startup: %s", sync_results)
    except Exception as exc:
        log.warning("Credential sync failed on startup (non-fatal): %s", exc)

    _recover_stale_running_stages()
    _bootstrap_default_admin()

    # --- Periodic event-queue cleanup ---
    import asyncio

    async def _periodic_event_queue_cleanup():
        try:
            from event_queue import event_queue
        except Exception:
            return
        while True:
            await asyncio.sleep(600)
            try:
                event_queue.cleanup_all_old_events()
            except Exception as _exc:
                log.debug("Event queue cleanup error (non-fatal): %s", _exc)

    asyncio.create_task(_periodic_event_queue_cleanup())
    yield

    # --- Shutdown tracing ---
    try:
        if _tracer_provider:
            from cmbagent.tracing import shutdown_tracing
            shutdown_tracing(_tracer_provider)
    except Exception:
        pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    global _app, _log_config

    # Import auth models before DB init so they are in the shared metadata
    _init_auth_tables()

    log_file = os.getenv("LOG_FILE") or _get_default_log_file()
    _log_config = {
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "json_output": os.getenv("LOG_JSON", "false").lower() == "true",
        "log_file": log_file,
    }

    configure_logging(**_log_config)

    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # CORS — must come before RequestContextMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", "traceparent", "tracestate"],
    )

    # Request context — injects trace_id, user_id into every request's log context
    try:
        from middleware.request_context import RequestContextMiddleware
        app.add_middleware(RequestContextMiddleware)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("RequestContextMiddleware not loaded: %s", exc)

    _app = app
    return app


def get_app() -> FastAPI:
    global _app
    if _app is None:
        _app = create_app()
    return _app
