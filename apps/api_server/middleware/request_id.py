"""Request ID + trace correlation — X-Request-Id and X-Trace-Id on every request and response.

WHY A TRACE ID AS WELL AS A REQUEST ID. They answer different questions. `request_id` identifies
one HTTP call to this server. `trace_id` identifies the whole distributed operation the call belongs
to, so an agent framework's single user-facing turn -- which may fan out to several Algenta calls,
each returning its own receipt -- can be reassembled afterwards from the audit trail. Every
integration this engine is exposed through (Foundry, LiteLLM, MAF, OTel-instrumented clients) emits
W3C `traceparent`; a governed-execution layer that drops it forces the operator to correlate by
timestamp, which is guesswork under concurrency.

W3C TRACE CONTEXT IS HONOURED RATHER THAN REINVENTED. If the caller sends a valid `traceparent`
(https://www.w3.org/TR/trace-context/), its 32-hex trace-id is adopted so our receipts join the
caller's existing trace. The spec is explicit that a MALFORMED traceparent must be ignored and a new
trace started -- not rejected, and not trusted -- because a broken upstream must never be able to
fail requests or poison correlation. That is why parsing here is strict and silent: it validates
version, field count, hex-ness and the all-zeroes sentinel, then falls back rather than raising.
"""

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-Id"
TRACE_ID_HEADER = "X-Trace-Id"
TRACEPARENT_HEADER = "traceparent"

# version "00": <2 hex>-<32 hex trace-id>-<16 hex parent-id>-<2 hex flags>. Later versions must be
# accepted forwards-compatibly per the spec, so the version field is not pinned to "00" here; only
# its shape is checked, and a longer field list is tolerated.
_TRACEPARENT_RE = re.compile(
    r"^(?P<version>[0-9a-f]{2})-(?P<trace_id>[0-9a-f]{32})-(?P<parent_id>[0-9a-f]{16})-"
    r"(?P<flags>[0-9a-f]{2})(?:-.*)?$"
)
_ALL_ZERO_TRACE = "0" * 32
_ALL_ZERO_PARENT = "0" * 16
# "ff" is forbidden as a version by the spec.
_INVALID_VERSION = "ff"


def parse_trace_id(traceparent: str | None) -> str | None:
    """Return the trace-id from a valid W3C traceparent, else None.

    None means "start a new trace", never "reject the request": an upstream emitting a malformed
    header must not be able to break calls, and must not be able to inject an unusable trace-id
    that then appears in receipts as though it were real.
    """
    if not traceparent:
        return None
    m = _TRACEPARENT_RE.match(traceparent.strip().lower())
    if m is None:
        return None
    if m.group("version") == _INVALID_VERSION:
        return None
    # All-zeroes is the spec's explicit "invalid" sentinel for both ids.
    if m.group("trace_id") == _ALL_ZERO_TRACE or m.group("parent_id") == _ALL_ZERO_PARENT:
        return None
    return m.group("trace_id")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id

        # Precedence: W3C traceparent (the interop standard every framework emits) > an explicit
        # X-Trace-Id (for callers that have a correlation id but no tracing stack) > a fresh id.
        trace_id = parse_trace_id(request.headers.get(TRACEPARENT_HEADER))
        if trace_id is None:
            supplied = (request.headers.get(TRACE_ID_HEADER) or "").strip().lower()
            trace_id = supplied if re.fullmatch(r"[0-9a-f]{32}", supplied) else uuid.uuid4().hex
        request.state.trace_id = trace_id

        response: Response = await call_next(request)  # type: ignore[operator]
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACE_ID_HEADER] = trace_id
        return response
