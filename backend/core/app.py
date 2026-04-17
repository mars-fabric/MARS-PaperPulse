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
    """Get default log file path in work directory."""
    work_dir = os.getenv("CMBAGENT_DEFAULT_WORK_DIR", "~/Desktop/cmbdir")
    work_dir = os.path.expanduser(work_dir)
    log_dir = Path(work_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return str(log_dir / "backend.log")


def _recover_stale_running_stages():
    """Reset any stages stuck in 'running' status from a previous server session.

    On server restart, in-memory _running_tasks is empty, so any stage still
    marked 'running' in the DB is orphaned.  Mark them 'failed' so users can
    retry instead of being stuck forever.
    """
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
                log.warning("Found %d stale 'running' stage(s) from previous session — resetting to 'failed'", len(stale))
                for stage in stale:
                    stage.status = "failed"
                    stage.error_message = "Server restarted while stage was running. Click retry to re-execute."
                    stage.completed_at = datetime.now(timezone.utc)
                    log.info("  Reset stage %s (run=%s, stage_num=%d)", stage.id, stage.parent_run_id, stage.stage_number)
                db.commit()
            else:
                log.info("No stale running stages found — clean startup")
        finally:
            db.close()
    except Exception as exc:
        log.error("Failed to recover stale stages on startup: %s", exc, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: re-apply logging after uvicorn overrides it, sync credentials, recover stale stages."""
    configure_logging(**_log_config)
    import logging
    log = logging.getLogger(__name__)
    log.info("Backend started, logs writing to %s", _log_config.get("log_file", "console"))

    # Sync credentials from vault + .env -> cmbagent ProviderRegistry
    try:
        from services.config_bridge import ConfigBridge
        sync_results = ConfigBridge.sync_all()
        log.info("Credential sync on startup: %s", sync_results)
    except Exception as exc:
        log.warning("Credential sync failed on startup (non-fatal): %s", exc)

    _recover_stale_running_stages()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    global _app, _log_config

    # Build log config
    log_file = os.getenv("LOG_FILE") or _get_default_log_file()
    _log_config = {
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "json_output": os.getenv("LOG_JSON", "false").lower() == "true",
        "log_file": log_file,
    }

    # Initial configure (may be overridden by uvicorn, re-applied in lifespan)
    configure_logging(**_log_config)

    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _app = app
    return app


def get_app() -> FastAPI:
    """Get the current FastAPI application instance."""
    global _app
    if _app is None:
        _app = create_app()
    return _app
