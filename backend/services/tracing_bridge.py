"""
Tracing bridge — per-task session IDs without modifying mars_cmbagent.

The cmbagent `init_tracing()` is idempotent and bakes a fixed session_id
into its SessionAttributeProcessor at construction time.  We work around
this by adding our own DynamicSessionProcessor to the same TracerProvider
after init_tracing() returns.  Because processors run in registration order,
DynamicSessionProcessor executes last and overwrites session.id + user.id
with the per-task values stored in ContextVars.

Python's asyncio.to_thread() copies the current contextvars.Context snapshot
into the worker thread, so values set before to_thread() are automatically
available in the thread — no manual propagation needed for ContextVars.

For W3C trace context (parent span ID), callers must manually capture and
restore otel_context.get_current() in the worker thread.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, Optional, Tuple

log = logging.getLogger(__name__)

# Per-task context vars — set before entering stage execution
_session_id_var: ContextVar[str] = ContextVar("pp_session_id", default="")
_trace_name_var: ContextVar[str] = ContextVar("pp_trace_name",  default="")
_user_id_var:    ContextVar[str] = ContextVar("pp_user_id",     default="")


class DynamicSessionProcessor:
    """
    OpenTelemetry SpanProcessor that reads per-task values from ContextVars
    and overwrites session.id / langfuse.trace.name / user.id on every span.

    Registered on the TracerProvider AFTER cmbagent's SessionAttributeProcessor
    so our values win.
    """

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        sid   = _session_id_var.get()
        tname = _trace_name_var.get()
        uid   = _user_id_var.get()
        if sid:
            span.set_attribute("session.id", sid)
        if tname:
            span.set_attribute("langfuse.trace.name", tname)
        if uid:
            span.set_attribute("user.id", uid)

    def on_end(self, span: Any) -> None:  # noqa: D401
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: Optional[int] = None) -> bool:
        return True


def init_paperpulse_tracing(provider: Any) -> None:
    """
    Attach DynamicSessionProcessor to the provider returned by init_tracing().

    Safe to call with provider=None (tracing disabled in dev).
    """
    if provider is None:
        return
    try:
        provider.add_span_processor(DynamicSessionProcessor())
        log.info("DynamicSessionProcessor attached to TracerProvider")
    except Exception as exc:
        log.warning("Could not attach DynamicSessionProcessor: %s", exc)


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------

def set_task_trace_context(task_id: str, user_id: str) -> Tuple:
    """
    Set per-task tracing context in the current async coroutine.

    Must be called BEFORE asyncio.to_thread() so the worker thread
    inherits the ContextVar values.

    Returns tokens for reset via clear_task_trace_context().
    """
    t1 = _session_id_var.set(task_id)
    t2 = _trace_name_var.set(f"deepresearch-{task_id}")
    t3 = _user_id_var.set(user_id)
    return (t1, t2, t3)


def clear_task_trace_context(tokens: Tuple) -> None:
    """Reset ContextVars to their previous values."""
    t1, t2, t3 = tokens
    _session_id_var.reset(t1)
    _trace_name_var.reset(t2)
    _user_id_var.reset(t3)


def get_task_trace_context() -> dict:
    """Snapshot current context values (used for logging / audit)."""
    return {
        "session_id": _session_id_var.get(),
        "trace_name": _trace_name_var.get(),
        "user_id":    _user_id_var.get(),
    }


def apply_task_trace_context_dict(ctx: dict) -> Tuple:
    """
    Apply a previously snapshotted context dict.

    Useful when you need to restore context inside a callback that does NOT
    inherit it automatically (e.g., a raw threading.Thread).
    """
    t1 = _session_id_var.set(ctx.get("session_id", ""))
    t2 = _trace_name_var.set(ctx.get("trace_name", ""))
    t3 = _user_id_var.set(ctx.get("user_id", ""))
    return (t1, t2, t3)


# ---------------------------------------------------------------------------
# Span helper
# ---------------------------------------------------------------------------

def get_tracer(name: str = "paperpulse.stages"):
    """Return the global OTel tracer for PaperPulse stage spans."""
    try:
        from opentelemetry import trace as otel_trace
        return otel_trace.get_tracer(name)
    except ImportError:
        return _NoopTracer()


class _NoopSpan:
    """Fallback when opentelemetry is not installed."""
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def set_attribute(self, *_): pass
    def record_exception(self, *_): pass
    def set_status(self, *_): pass


class _NoopTracer:
    def start_as_current_span(self, *_, **__):
        return _NoopSpan()
