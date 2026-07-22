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


# Resolve the real SpanProcessor base class so this processor implements the
# full interface the SDK expects. Newer OpenTelemetry SDKs (>=1.44) invoke
# internal hooks like ``_on_ending`` on every registered processor, which only
# exist on the ``SpanProcessor`` ABC — a duck-typed class raises
# AttributeError. Falling back to ``object`` keeps import-safety when the SDK
# is absent (tracing disabled in dev).
try:  # pragma: no cover - exercised only when SDK present
    from opentelemetry.sdk.trace import SpanProcessor as _SpanProcessorBase
except Exception:  # pragma: no cover - SDK not installed
    _SpanProcessorBase = object  # type: ignore[assignment,misc]


class DynamicSessionProcessor(_SpanProcessorBase):
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


def instrument_langchain(provider: Any) -> None:
    """
    Auto-instrument LangChain / LangGraph so stage 4-5 LLM calls reach Langfuse.

    Stages 1-3 run on AG2 (instrumented by cmbagent.init_tracing).  Stages 4-5
    are LangGraph pipelines whose LangChain ``.invoke()`` / ``.stream()`` calls
    are NOT covered by the AG2 instrumentation.  OpenInference's LangChain
    instrumentor emits GenAI OTel spans against the same TracerProvider, so
    those calls are exported to Langfuse and picked up by
    ``DynamicSessionProcessor`` (session.id / trace.name / user.id).

    Silent no-op when tracing is disabled or the optional package is missing.
    """
    if provider is None:
        return
    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
    except ImportError as exc:
        log.warning(
            "LangChain tracing unavailable (%s). Install with "
            "`pip install openinference-instrumentation-langchain` to trace "
            "stages 4-5 in Langfuse.",
            exc,
        )
        return
    try:
        LangChainInstrumentor().instrument(tracer_provider=provider)
        log.info("LangChain/LangGraph instrumentation enabled (stages 4-5)")
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Could not instrument LangChain: %s", exc)


def filter_langchain_callbacks(callbacks: Any) -> list:
    """Return only genuine LangChain callback handlers from ``callbacks``.

    cmbagent's ``WorkflowCallbacks`` (cost/event tracking) is NOT a LangChain
    ``BaseCallbackHandler`` and must never be placed in a LangGraph/LangChain
    ``config["callbacks"]`` — doing so raises
    ``AttributeError: 'WorkflowCallbacks' object has no attribute 'parent_run_id'``
    inside LangChain's callback manager.

    Stage 4-5 LLM tracing is handled globally by the OpenInference LangChain
    instrumentor, so in practice this returns an empty list; it exists so that
    any real LangChain handler (should one ever be passed) is still forwarded.
    """
    if not callbacks:
        return []
    try:
        from langchain_core.callbacks.base import BaseCallbackHandler
    except Exception:
        return []
    items = callbacks if isinstance(callbacks, (list, tuple)) else [callbacks]
    return [cb for cb in items if isinstance(cb, BaseCallbackHandler)]


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------

def build_trace_name(
    task_id: str,
    stage_num: Optional[int] = None,
    stage_name: Optional[str] = None,
) -> str:
    """Build a Langfuse trace name.

    When a stage is known, the name is prefixed with ``stage{n}_{stage_name}_``
    so each stage shows up as its own clearly-labelled trace in Langfuse while
    still grouping under the same ``session.id`` (= task_id).  Falls back to the
    legacy ``deepresearch-{task_id}`` form when no stage context is available.
    """
    if stage_num is not None:
        label = (stage_name or "stage").strip().replace(" ", "_")
        return f"stage{stage_num}_{label}_{task_id}"
    return f"deepresearch-{task_id}"


def set_task_trace_context(
    task_id: str,
    user_id: str,
    stage_num: Optional[int] = None,
    stage_name: Optional[str] = None,
) -> Tuple:
    """
    Set per-task tracing context in the current async coroutine.

    Must be called BEFORE asyncio.to_thread() so the worker thread
    inherits the ContextVar values.

    When ``stage_num`` / ``stage_name`` are supplied the Langfuse trace name is
    stage-scoped (e.g. ``stage4_paper_generation_<task_id>``) so stages are
    easy to distinguish in the Langfuse UI.

    Returns tokens for reset via clear_task_trace_context().
    """
    t1 = _session_id_var.set(task_id)
    t2 = _trace_name_var.set(build_trace_name(task_id, stage_num, stage_name))
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
