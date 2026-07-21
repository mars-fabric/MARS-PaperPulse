"""
Request context middleware.

For every HTTP request:
  1. Read or generate a W3C traceparent / x-trace-id header.
  2. Continue the OTel trace so the frontend button-click and backend
     workflow appear in the same Langfuse trace.
  3. Extract user_id from the JWT (if present) without blocking on auth.
  4. Bind trace_id and user_id into structlog context so every log line
     carries them automatically.
  5. Log the request method, path, status code, duration, and user_id
     at INFO level on request completion.
"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.logging import (
    bind_logging_context,
    current_trace_id,
    current_user_id,
    get_logger,
)

log = get_logger(__name__)


def _extract_trace_id(request: Request) -> str:
    """
    Extract a trace-id from W3C traceparent or x-trace-id header.
    Falls back to a freshly generated UUID.
    """
    traceparent = request.headers.get("traceparent", "")
    if traceparent:
        parts = traceparent.split("-")
        if len(parts) >= 2:
            return parts[1]

    x_trace = request.headers.get("x-trace-id", "")
    if x_trace:
        return x_trace

    return uuid.uuid4().hex


def _extract_user_id_from_token(request: Request) -> str:
    """
    Decode the JWT from the Authorization header without raising an exception.
    Returns "" if the token is absent, invalid, or expired.
    """
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return ""
    token = auth[7:].strip()
    try:
        from core.security import decode_access_token
        payload = decode_access_token(token)
        return payload.get("sub", "")
    except Exception:
        return ""


def _continue_otel_trace(request: Request) -> None:
    """
    Attach the incoming W3C traceparent to the OTel context so downstream
    spans are children of the frontend-generated root span.
    """
    try:
        from opentelemetry import context as otel_context
        from opentelemetry.propagators.b3 import B3MultiFormat
        from opentelemetry.propagate import extract

        carrier = {
            "traceparent": request.headers.get("traceparent", ""),
            "tracestate":  request.headers.get("tracestate", ""),
        }
        ctx = extract(carrier)
        token = otel_context.attach(ctx)
        request.state._otel_ctx_token = token  # type: ignore[attr-defined]
    except Exception:
        pass  # OTel not installed or misconfigured — non-fatal


def _detach_otel_trace(request: Request) -> None:
    try:
        from opentelemetry import context as otel_context
        token = getattr(request.state, "_otel_ctx_token", None)
        if token is not None:
            otel_context.detach(token)
    except Exception:
        pass


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Inject trace_id, user_id, and request timing into every request."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = _extract_trace_id(request)
        user_id  = _extract_user_id_from_token(request)

        # Set structlog context vars (propagate to all log lines in this request)
        trace_token = current_trace_id.set(trace_id)
        user_token  = current_user_id.set(user_id)
        bind_logging_context(trace_id=trace_id, user_id=user_id)

        # Continue the W3C OTel trace from the frontend
        _continue_otel_trace(request)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            log.error(
                "Unhandled request error",
                method=request.method,
                path=request.url.path,
                error=str(exc),
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            _detach_otel_trace(request)
            current_trace_id.reset(trace_token)
            current_user_id.reset(user_token)

        # Add trace-id to response headers for client correlation
        response.headers["x-trace-id"] = trace_id

        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id or None,
            trace_id=trace_id,
        )
        return response
