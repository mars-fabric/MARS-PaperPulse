"""
Tracing bridge — per-task session IDs without modifying mars_cmbagent.

The cmbagent `init_tracing()` is idempotent and bakes a fixed session_id
into its SessionAttributeProcessor at construction time.  We work around
this by adding our own DynamicSessionProcessor to the same TracerProvider
after init_tracing() returns.  Because processors run in registration order,
DynamicSessionProcessor executes last and overwrites session.id + user.id
with the per-task values stored in the trace registry.

Lookup strategy in DynamicSessionProcessor
-------------------------------------------
ContextVars are ideal for asyncio tasks and threads spawned via
asyncio.to_thread(), but AG2 creates its own internal threads that do NOT
inherit the calling context's ContextVars.  The solution is a
process-global _TRACE_REGISTRY dict keyed by OTel trace_id (derived
deterministically from task_id UUID).  The trace_id is always present on
every span object, regardless of which thread the span ends in, so the
registry lookup is always reliable.

ContextVars are kept as a secondary source for compatibility.

Registry lifecycle:
  set_task_trace_context()   → registers entry
  clear_task_trace_context() → removes entry (called after stage flush)

For W3C trace context (parent span ID), callers must manually capture and
restore otel_context.get_current() in the worker thread.
"""

from __future__ import annotations

import logging
import os
import re as _re
import threading
from contextvars import ContextVar
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-task context vars — set before entering stage execution.
# Available in asyncio tasks and threads spawned via asyncio.to_thread().
# NOT available in AG2's internal threads (use _TRACE_REGISTRY instead).
# ---------------------------------------------------------------------------
_session_id_var: ContextVar[str] = ContextVar("pp_session_id", default="")
_trace_name_var: ContextVar[str] = ContextVar("pp_trace_name",  default="")
_user_id_var:    ContextVar[str] = ContextVar("pp_user_id",     default="")

# ---------------------------------------------------------------------------
# Process-global trace registry — keyed by OTel trace_id hex string.
# Works in ALL threads including AG2 internals.
# ---------------------------------------------------------------------------
_TRACE_REGISTRY: Dict[str, Dict[str, str]] = {}
_REGISTRY_LOCK = threading.Lock()


def _registry_get(trace_id_hex: str) -> Dict[str, str]:
    with _REGISTRY_LOCK:
        return dict(_TRACE_REGISTRY.get(trace_id_hex, {}))


def _registry_set(trace_id_hex: str, session_id: str, trace_name: str, user_id: str) -> None:
    with _REGISTRY_LOCK:
        _TRACE_REGISTRY[trace_id_hex] = {
            "session_id": session_id,
            "trace_name": trace_name,
            "user_id":    user_id,
        }


def _registry_remove(trace_id_hex: str) -> None:
    with _REGISTRY_LOCK:
        _TRACE_REGISTRY.pop(trace_id_hex, None)


# ---------------------------------------------------------------------------
# SpanProcessor base
# ---------------------------------------------------------------------------
try:  # pragma: no cover - exercised only when SDK present
    from opentelemetry.sdk.trace import SpanProcessor as _SpanProcessorBase
except Exception:  # pragma: no cover - SDK not installed
    _SpanProcessorBase = object  # type: ignore[assignment,misc]


class DynamicSessionProcessor(_SpanProcessorBase):
    """
    OpenTelemetry SpanProcessor that overwrites session.id / user.id /
    langfuse.trace.name on every span using per-task values from the
    trace registry (keyed by OTel trace_id).

    Registered on the TracerProvider AFTER cmbagent's SessionAttributeProcessor
    so our values win.

    Implementation note — OTel SDK immutability
    -------------------------------------------
    Span.end() sets _attributes._immutable = True before calling ANY
    span-processor hooks (both _on_ending and on_end).  Standard
    __setitem__ / __delitem__ raise TypeError on an immutable
    BoundedAttributes.  We bypass this by writing directly to
    span._attributes._dict (the underlying plain dict).

    We do the work in _on_ending() rather than on_end() because _on_ending
    is called before BatchSpanProcessor.on_end() queues the span for async
    export — so there is no race between our modification and the export
    thread serialising the attributes.

    Lookup order for per-task values:
      1. _TRACE_REGISTRY[span.context.trace_id] — works in ALL threads
         including AG2's internal threads that do not inherit ContextVars.
      2. ContextVars — fallback for any span not covered by the registry.
    """

    def _lookup(self, span: Any) -> Dict[str, str]:
        """Return the per-task record for this span's trace_id, or {}."""
        try:
            tid = format(span.context.trace_id, "032x")
            rec = _registry_get(tid)
            if rec:
                return rec
        except Exception as exc:
            log.debug("_lookup registry exception: %s", exc)
        # ContextVar fallback
        sid   = _session_id_var.get()
        tname = _trace_name_var.get()
        uid   = _user_id_var.get()
        if sid or tname or uid:
            return {"session_id": sid, "trace_name": tname, "user_id": uid}
        return {}

    @staticmethod
    def _raw(attrs: Any) -> Any:
        """Return the underlying mutable dict of a BoundedAttributes object.

        BoundedAttributes._immutable blocks __setitem__/__delitem__ after
        Span.end() — access ._dict directly to bypass the guard.
        Falls back to the attrs object itself for duck-typed callers.
        """
        return getattr(attrs, "_dict", attrs)

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        rec = self._lookup(span)
        if not rec:
            return

        sid   = rec.get("session_id", "")
        tname = rec.get("trace_name", "")
        uid   = rec.get("user_id", "")

        if sid:
            span.set_attribute("session.id", sid)
        if uid:
            span.set_attribute("user.id", uid)

        # Stamp langfuse.trace.name only on stage-root or true-root spans.
        # Child spans do NOT get it here; _on_ending will DELETE any
        # langfuse.trace.name set by cmbagent's workflow_span body.
        if tname:
            try:
                parent = getattr(span, "parent", None)
                is_root = parent is None or not getattr(parent, "is_valid", False)
                is_stage_root = bool(parent and getattr(parent, "is_remote", False))
                if is_root or is_stage_root:
                    span.set_attribute("langfuse.trace.name", tname)
            except Exception:
                span.set_attribute("langfuse.trace.name", tname)

    def _on_ending(self, span: Any) -> None:
        """Mutate span attributes just before the span is ended.

        Called by the SDK BEFORE BatchSpanProcessor queues the span, so
        every change here is guaranteed to be visible to the export thread.
        _attributes._immutable is True at this point; we bypass it via ._dict.
        """
        ba = getattr(span, "_attributes", None)
        if ba is None:
            return
        d = self._raw(ba)

        rec = self._lookup(span)
        if rec:
            sid   = rec.get("session_id", "")
            uid   = rec.get("user_id", "")
            tname = rec.get("trace_name", "")
            try:
                if sid:
                    d["session.id"] = sid
                if uid:
                    d["user.id"] = uid

                parent = getattr(span, "parent", None)
                is_root = parent is None or not getattr(parent, "is_valid", False)
                is_stage_root = bool(parent and getattr(parent, "is_remote", False))

                if is_root or is_stage_root:
                    if tname:
                        d["langfuse.trace.name"] = tname
                else:
                    # Child span: delete langfuse.trace.name so Langfuse
                    # never renames the trace from a step span.
                    d.pop("langfuse.trace.name", None)
            except Exception as exc:
                log.debug("DynamicSessionProcessor _on_ending re-stamp failed: %s", exc)

        # Redact prompt/key payloads
        redact = os.environ.get("MARS_TRACING_REDACT", "prompts").lower()
        if redact == "none":
            return
        _REDACT_PREFIXES = ("gen_ai.prompt.", "gen_ai.completion.", "llm.")
        _REDACT_EXACT = {"input.value", "output.value",
                         "input.messages", "output.messages"}
        try:
            for key in list(d.keys()):
                if not isinstance(key, str):
                    continue
                if key in _REDACT_EXACT or any(key.startswith(p) for p in _REDACT_PREFIXES):
                    d[key] = "<redacted>"
        except Exception as exc:
            log.debug("DynamicSessionProcessor redaction failed: %s", exc)

    def on_end(self, span: Any) -> None:
        pass  # all work done in _on_ending before the span is queued

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
    """Legacy stage-scoped trace name. Kept for backward compatibility.

    New code should use build_run_trace_name() so all 5 stages share one trace.
    """
    if stage_num is not None:
        label = (stage_name or "stage").strip().replace(" ", "_")
        return f"stage{stage_num}_{label}_{task_id}"
    return f"deepresearch-{task_id}"


def build_run_trace_name(user_name: str, task_id: str) -> str:
    """Build the parent Langfuse trace name that groups all 5 stages of a run.

    Format: ``{user_slug}_{task_id}``
    All stage spans share this name so they appear under one Langfuse trace.
    """
    slug = _re.sub(r"[^a-z0-9]+", "_", user_name.lower()).strip("_") or "user"
    return f"{slug}_{task_id}"


def make_virtual_parent_context(task_id: str) -> Optional[Any]:
    """Return an OTel context holding a virtual (non-recording) root span.

    The span's trace_id is derived deterministically from ``task_id`` (UUID).
    Passing this as ``context=`` to ``tracer.start_as_current_span()`` makes
    every stage span a child of the same virtual root — they all share one
    OTel trace_id and therefore appear under one Langfuse trace.

    The virtual span is never exported (NonRecordingSpan).  Its ``is_remote``
    flag is True, which ``DynamicSessionProcessor`` uses to detect stage-root
    spans and stamp ``langfuse.trace.name`` on them.

    Returns None when opentelemetry is not installed (tracing disabled).
    """
    try:
        import uuid as _uuid
        from opentelemetry import trace as _otel_trace
        from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

        trace_id_int = int(_uuid.UUID(task_id))
        span_ctx = SpanContext(
            trace_id=trace_id_int,
            span_id=0x0000000000000001,
            is_remote=True,
            trace_flags=TraceFlags(0x01),
        )
        return _otel_trace.set_span_in_context(NonRecordingSpan(span_ctx))
    except Exception as exc:
        log.debug("make_virtual_parent_context unavailable: %s", exc)
        return None


def set_task_trace_context(
    task_id: str,
    user_id: str,
    run_trace_name: str = "",
    stage_num: Optional[int] = None,
    stage_name: Optional[str] = None,
) -> Tuple:
    """
    Set per-task tracing context for the current async coroutine AND the
    process-global trace registry.

    The registry entry is keyed by the OTel trace_id derived from task_id
    (same deterministic mapping used by make_virtual_parent_context).  This
    ensures DynamicSessionProcessor can look up correct values even in AG2's
    internal threads that do not inherit ContextVars.

    Returns tokens for reset via clear_task_trace_context().
    """
    import uuid as _uuid
    tname = (
        run_trace_name if run_trace_name
        else build_trace_name(task_id, stage_num, stage_name)
    )

    # Register in global registry keyed by the deterministic trace_id hex.
    trace_id_hex = _uuid.UUID(task_id).hex  # 32-char hex, no dashes
    _registry_set(trace_id_hex, task_id, tname, user_id)

    # Also set ContextVars for threads that do inherit them.
    t1 = _session_id_var.set(task_id)
    t2 = _trace_name_var.set(tname)
    t3 = _user_id_var.set(user_id)
    return (t1, t2, t3)


def clear_task_trace_context(tokens: Tuple) -> None:
    """Reset ContextVars and remove the task from the trace registry."""
    t1, t2, t3 = tokens
    # The current ContextVar value is the task_id we registered — remove it
    # from the registry BEFORE resetting the ContextVar.
    try:
        import uuid as _uuid
        current_task_id = _session_id_var.get()
        if current_task_id:
            _registry_remove(_uuid.UUID(current_task_id).hex)
    except Exception:
        pass
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
