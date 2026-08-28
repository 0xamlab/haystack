"""A4 (part 1): W3C trace-context propagation, so receipts join the caller's trace.

WHY THIS MATTERS FOR THE GOVERNED SURFACE. `request_id` identifies one HTTP call; `trace_id`
identifies the whole distributed operation it belongs to. One user-facing agent turn can fan out to
several Algenta calls, each returning its own receipt, and without a shared trace an operator has to
correlate those receipts by timestamp -- which is guesswork the moment two turns overlap. Every
framework this engine is exposed through (Foundry, LiteLLM, MAF, any OTel-instrumented client)
already emits `traceparent`, so honouring it costs nothing and dropping it loses the linkage.

THE PART THAT NEEDS THE MOST CARE IS THE MALFORMED INPUT. W3C trace-context says an unparseable
`traceparent` must be IGNORED and a new trace begun -- not rejected. A broken or hostile upstream
must not be able to fail requests, and must not be able to plant an unusable trace-id that then
appears in a receipt as though it were genuine. So most of these tests are negative: they assert the
request still succeeds AND that the bad value did not survive into the response.

Spec: https://www.w3.org/TR/trace-context/
"""

from __future__ import annotations

import re

import pytest
from starlette.requests import Request

from apps.api_server.middleware.request_id import (
    REQUEST_ID_HEADER,
    TRACE_ID_HEADER,
    TRACEPARENT_HEADER,
    parse_trace_id,
)

HEX32 = re.compile(r"^[0-9a-f]{32}$")

GOOD_TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
GOOD_PARENT = "00f067aa0ba902b7"
GOOD_TRACEPARENT = f"00-{GOOD_TRACE}-{GOOD_PARENT}-01"

# Anything here must be ignored, leaving a fresh trace. Each case is a real way upstreams break.
MALFORMED = [
    pytest.param("", id="empty"),
    pytest.param("   ", id="whitespace-only"),
    pytest.param("garbage", id="not-delimited"),
    pytest.param("00-tooshort-00f067aa0ba902b7-01", id="trace-id-too-short"),
    pytest.param(f"00-{GOOD_TRACE}aa-{GOOD_PARENT}-01", id="trace-id-too-long"),
    pytest.param(f"00-{'g' * 32}-{GOOD_PARENT}-01", id="trace-id-not-hex"),
    pytest.param(f"00-{GOOD_TRACE}-tooshort-01", id="parent-id-too-short"),
    pytest.param(f"00-{GOOD_TRACE}-{GOOD_PARENT}", id="missing-flags"),
    pytest.param(f"-{GOOD_TRACE}-{GOOD_PARENT}-01", id="missing-version"),
    pytest.param(f"00-{'0' * 32}-{GOOD_PARENT}-01", id="all-zero-trace-id-is-the-spec-sentinel"),
    pytest.param(f"00-{GOOD_TRACE}-{'0' * 16}-01", id="all-zero-parent-id-is-invalid"),
    pytest.param(f"ff-{GOOD_TRACE}-{GOOD_PARENT}-01", id="version-ff-is-forbidden"),
]


# ── the parser, exhaustively ─────────────────────────────────────────────────────────────────────


def test_a_valid_traceparent_yields_its_trace_id() -> None:
    assert parse_trace_id(GOOD_TRACEPARENT) == GOOD_TRACE


def test_parsing_is_case_and_whitespace_tolerant() -> None:
    """Headers arrive with stray whitespace and mixed case; neither should lose the trace."""
    assert parse_trace_id(f"  00-{GOOD_TRACE.upper()}-{GOOD_PARENT.upper()}-01  ") == GOOD_TRACE


def test_a_future_version_with_extra_fields_is_still_accepted() -> None:
    """The spec requires forwards compatibility: a newer version must not break correlation."""
    assert parse_trace_id(f"01-{GOOD_TRACE}-{GOOD_PARENT}-01-extrafield") == GOOD_TRACE


@pytest.mark.parametrize("raw", MALFORMED)
def test_malformed_traceparent_is_ignored_not_trusted(raw: str) -> None:
    assert parse_trace_id(raw) is None, f"{raw!r} must not be accepted as a trace-id"


def test_none_is_handled() -> None:
    assert parse_trace_id(None) is None


# ── the middleware, against the real app ────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_a_response_always_carries_both_ids(client) -> None:
    resp = await client.get("/v1/health")
    assert resp.status_code == 200, resp.text
    assert resp.headers.get(REQUEST_ID_HEADER), "X-Request-Id must always be present"
    trace = resp.headers.get(TRACE_ID_HEADER)
    assert trace and HEX32.match(trace), f"expected a 32-hex trace id, got {trace!r}"


@pytest.mark.anyio
async def test_a_callers_traceparent_is_adopted(client) -> None:
    """The whole point: our receipts must sit inside the caller's existing trace."""
    resp = await client.get("/v1/health", headers={TRACEPARENT_HEADER: GOOD_TRACEPARENT})
    assert resp.headers[TRACE_ID_HEADER] == GOOD_TRACE


@pytest.mark.anyio
@pytest.mark.parametrize("raw", MALFORMED)
async def test_a_broken_upstream_cannot_fail_the_request(client, raw: str) -> None:
    """A malformed traceparent must neither 4xx the call nor leak into the response."""
    resp = await client.get("/v1/health", headers={TRACEPARENT_HEADER: raw})
    assert resp.status_code == 200, f"malformed traceparent broke the request: {resp.status_code}"
    trace = resp.headers[TRACE_ID_HEADER]
    assert HEX32.match(trace), f"fell back to an invalid trace id: {trace!r}"
    assert trace != "0" * 32, "the all-zeroes sentinel must never be emitted as a real trace"
    stripped = raw.strip().lower()
    if stripped:  # "" is a substring of everything; nothing to assert for an empty header
        assert stripped not in trace, "the malformed value survived into the response"


@pytest.mark.anyio
async def test_an_explicit_trace_id_header_is_honoured_when_there_is_no_traceparent(client) -> None:
    """For callers that carry a correlation id but run no tracing stack."""
    resp = await client.get("/v1/health", headers={TRACE_ID_HEADER: GOOD_TRACE})
    assert resp.headers[TRACE_ID_HEADER] == GOOD_TRACE


@pytest.mark.anyio
async def test_traceparent_wins_over_an_explicit_trace_id(client) -> None:
    """traceparent is the interop standard, so it is the more authoritative of the two."""
    other = "1" * 32
    resp = await client.get(
        "/v1/health",
        headers={TRACEPARENT_HEADER: GOOD_TRACEPARENT, TRACE_ID_HEADER: other},
    )
    assert resp.headers[TRACE_ID_HEADER] == GOOD_TRACE


@pytest.mark.anyio
async def test_a_malformed_explicit_trace_id_is_replaced_not_echoed(client) -> None:
    resp = await client.get("/v1/health", headers={TRACE_ID_HEADER: "not-a-trace"})
    assert resp.status_code == 200
    assert HEX32.match(resp.headers[TRACE_ID_HEADER])
    assert "not-a-trace" not in resp.headers[TRACE_ID_HEADER]


@pytest.mark.anyio
async def test_two_calls_without_a_traceparent_get_distinct_traces(client) -> None:
    """Unrelated operations must not be collapsed into one trace by a constant fallback."""
    a = (await client.get("/v1/health")).headers[TRACE_ID_HEADER]
    b = (await client.get("/v1/health")).headers[TRACE_ID_HEADER]
    assert a != b


@pytest.mark.anyio
async def test_an_incoming_request_id_is_still_preserved(client) -> None:
    """Regression guard: adding trace handling must not disturb the existing request-id contract."""
    resp = await client.get("/v1/health", headers={REQUEST_ID_HEADER: "req_caller_supplied"})
    assert resp.headers[REQUEST_ID_HEADER] == "req_caller_supplied"


@pytest.mark.anyio
async def test_the_trace_id_is_available_to_handlers_on_request_state(client) -> None:
    """Downstream code (receipts, audit rows) reads request.state.trace_id, not the header."""
    from apps.api_server.main import app

    seen: dict[str, object] = {}

    @app.get("/__test_trace_state")
    async def _probe(request: Request) -> dict:  # pragma: no cover - registered for this test
        seen["trace_id"] = getattr(request.state, "trace_id", None)
        seen["request_id"] = getattr(request.state, "request_id", None)
        return {"ok": True}

    try:
        resp = await client.get(
            "/__test_trace_state", headers={TRACEPARENT_HEADER: GOOD_TRACEPARENT}
        )
        assert resp.status_code == 200, resp.text
        assert seen["trace_id"] == GOOD_TRACE, (
            "handlers must see the adopted trace on request.state, or receipts cannot record it"
        )
        assert seen["request_id"]
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", None) != "/__test_trace_state"
        ]
