"""
Tracing and observability tests.

Tests:
  - DynamicSessionProcessor writes contextvar values onto spans
  - init_tracing() is a no-op when LANGFUSE keys are absent
  - tracing_bridge context helpers set / clear / propagate correctly
  - audit_logger writes UserAuditLog rows with trace_id in metadata
  - Structured log context vars carry user_id and trace_id
  - RequestContextMiddleware extracts trace_id from traceparent header
"""

import os
import pytest
from unittest.mock import MagicMock, patch


# ──────────────────────────────────────────────────────────────────────────────
# DynamicSessionProcessor
# ──────────────────────────────────────────────────────────────────────────────

class TestDynamicSessionProcessor:
    def test_on_start_writes_session_id_from_contextvar(self):
        from services.tracing_bridge import (
            DynamicSessionProcessor,
            _session_id_var,
            _user_id_var,
            _trace_name_var,
        )

        token_s = _session_id_var.set("task-abc-123")
        token_u = _user_id_var.set("user-xyz")
        token_t = _trace_name_var.set("deepresearch-task-abc-123")
        try:
            span = MagicMock()
            proc = DynamicSessionProcessor()
            proc.on_start(span)

            span.set_attribute.assert_any_call("session.id", "task-abc-123")
            span.set_attribute.assert_any_call("user.id", "user-xyz")
            span.set_attribute.assert_any_call("langfuse.trace.name", "deepresearch-task-abc-123")
        finally:
            _session_id_var.reset(token_s)
            _user_id_var.reset(token_u)
            _trace_name_var.reset(token_t)

    def test_on_start_writes_nothing_when_contextvar_empty(self):
        from services.tracing_bridge import DynamicSessionProcessor

        span = MagicMock()
        proc = DynamicSessionProcessor()
        proc.on_start(span)

        span.set_attribute.assert_not_called()

    def test_force_flush_returns_true(self):
        from services.tracing_bridge import DynamicSessionProcessor
        assert DynamicSessionProcessor().force_flush() is True


# ──────────────────────────────────────────────────────────────────────────────
# set_task_trace_context / clear_task_trace_context
# ──────────────────────────────────────────────────────────────────────────────

class TestTraceBridgeHelpers:
    def test_set_and_clear_context(self):
        from services.tracing_bridge import (
            set_task_trace_context,
            clear_task_trace_context,
            get_task_trace_context,
            _session_id_var,
        )

        tokens = set_task_trace_context("task-999", "user-111")
        ctx = get_task_trace_context()
        assert ctx["session_id"] == "task-999"
        assert ctx["user_id"] == "user-111"
        assert ctx["trace_name"] == "deepresearch-task-999"

        clear_task_trace_context(tokens)
        assert _session_id_var.get() == ""

    def test_context_is_inherited_by_thread(self):
        """asyncio.to_thread inherits contextvars — simulate via copy_context."""
        import contextvars
        import threading
        from services.tracing_bridge import (
            set_task_trace_context,
            clear_task_trace_context,
            _session_id_var,
        )

        tokens = set_task_trace_context("task-for-thread", "user-for-thread")
        captured = {}

        def worker():
            captured["session_id"] = _session_id_var.get()

        # copy_context() simulates what asyncio.to_thread does
        ctx = contextvars.copy_context()
        t = threading.Thread(target=ctx.run, args=(worker,))
        t.start()
        t.join()

        clear_task_trace_context(tokens)
        assert captured["session_id"] == "task-for-thread"


# ──────────────────────────────────────────────────────────────────────────────
# init_tracing — no-op without LANGFUSE keys
# ──────────────────────────────────────────────────────────────────────────────

class TestInitTracing:
    def test_no_op_without_langfuse_keys(self):
        # Ensure keys are absent
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)

            # Reset the idempotency flag so we can test a fresh call
            import cmbagent.tracing as _t
            original_init = _t._INITIALIZED
            original_provider = _t._TRACER_PROVIDER
            _t._INITIALIZED = False
            _t._TRACER_PROVIDER = None
            try:
                from cmbagent.tracing import init_tracing
                result = init_tracing(service_name="test")
                assert result is None
            finally:
                _t._INITIALIZED = original_init
                _t._TRACER_PROVIDER = original_provider

    def test_init_paperpulse_tracing_safe_with_none_provider(self):
        from services.tracing_bridge import init_paperpulse_tracing
        # Should not raise
        init_paperpulse_tracing(None)


# ──────────────────────────────────────────────────────────────────────────────
# Audit logger
# ──────────────────────────────────────────────────────────────────────────────

class TestAuditLogger:
    def test_write_audit_creates_log_row(self, db):
        from services.audit_logger import write_audit
        from models.auth import UserAuditLog

        write_audit(
            db,
            user_id="user-001",
            action="test_action",
            resource_type="task",
            resource_id="task-001",
            metadata={"extra": "value"},
        )

        log = db.query(UserAuditLog).filter(UserAuditLog.action == "test_action").first()
        assert log is not None
        assert log.user_id == "user-001"
        assert log.resource_id == "task-001"

    def test_write_audit_includes_trace_id_from_contextvar(self, db):
        from core.logging import current_trace_id
        from services.audit_logger import write_audit
        from models.auth import UserAuditLog

        token = current_trace_id.set("test-trace-id-abc")
        try:
            write_audit(
                db,
                user_id="user-002",
                action="traced_action",
            )
        finally:
            current_trace_id.reset(token)

        log = db.query(UserAuditLog).filter(UserAuditLog.action == "traced_action").first()
        assert log is not None
        assert log.meta is not None
        assert log.meta.get("trace_id") == "test-trace-id-abc"

    def test_write_audit_without_trace_id(self, db):
        from services.audit_logger import write_audit
        from models.auth import UserAuditLog

        write_audit(db, user_id="user-003", action="no_trace_action")

        log = db.query(UserAuditLog).filter(UserAuditLog.action == "no_trace_action").first()
        assert log is not None
        # metadata should be None or not contain trace_id
        if log.meta:
            assert "trace_id" not in log.meta


# ──────────────────────────────────────────────────────────────────────────────
# Structured logging context vars
# ──────────────────────────────────────────────────────────────────────────────

class TestLoggingContextVars:
    def test_user_id_and_trace_id_contextvar_exist(self):
        from core.logging import current_user_id, current_trace_id
        assert current_user_id is not None
        assert current_trace_id is not None

    def test_bind_logging_context_sets_vars(self):
        from core.logging import bind_logging_context, current_user_id, current_trace_id

        bind_logging_context(user_id="user-bind-test", trace_id="trace-bind-test")
        assert current_user_id.get() == "user-bind-test"
        assert current_trace_id.get() == "trace-bind-test"

        # Clean up
        from core.logging import current_user_id, current_trace_id
        current_user_id.set(None)
        current_trace_id.set(None)


# ──────────────────────────────────────────────────────────────────────────────
# RequestContextMiddleware — traceparent parsing
# ──────────────────────────────────────────────────────────────────────────────

class TestRequestContextMiddleware:
    def test_traceparent_in_request_sets_trace_id(self, client):
        """Backend should echo x-trace-id in the response header."""
        trace_id = "a" * 32
        span_id  = "b" * 16
        traceparent = f"00-{trace_id}-{span_id}-01"

        resp = client.get(
            "/api/health",
            headers={"traceparent": traceparent},
        )
        # Health endpoint exists and should return 200
        assert resp.status_code == 200
        # Middleware should echo the trace ID
        assert resp.headers.get("x-trace-id") == trace_id

    def test_request_without_traceparent_gets_generated_id(self, client):
        """Without a traceparent header, a new trace ID is generated."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert len(resp.headers.get("x-trace-id", "")) == 32  # UUID hex
