"""
POST /v1/simulate/stream — Server-Sent Events (SSE) progressive simulation output.

The Mojo engine emits NDJSON lines to stdout:
  - type="progress"  → Welford online stats at every checkpoint_every runs
  - type="final"     → Complete DecisionEnvelope (last line)

The SSE router:
  1. Validates auth + quota (same as /v1/simulate)
  2. Spawns mojo_build/simulate with stream=true in the payload
  3. Reads stdout line-by-line and yields each as an SSE data frame
  4. Client receives live progress then the final complete envelope

Wire-protocol (text/event-stream):
  data: {"type":"progress","runs_completed":1000,"runs_total":50000,"progress":0.02,...}
  data: {"type":"progress",...}
  data: {"type":"final","result":{...full DecisionEnvelope...}}

Usage:
  curl -N -X POST https://api.algenta.com/v1/simulate/stream \\
    -H "Authorization: Bearer sk-..." \\
    -H "Content-Type: application/json" \\
    -d '{"mode":"expert","runs":100000,"variables":[...],"objective_function":"..."}'
"""

import asyncio
import json
import os
import textwrap
from collections.abc import AsyncGenerator
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from apps.api_server.middleware.auth import AuthContext, get_current_org, get_redis
from apps.api_server.schemas.simulate import SimulateRequest, SimulateRequestAuto
from apps.api_server.services.quota_service import check_quota_redis, check_rate_limit
from apps.api_server.services.simulation_payloads import (
    _build_auto_mojo_payload,
    _build_expert_mojo_payload,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Streaming"])

# ── Locate binary ─────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_ROOT, "mojo_build", "simulate")


# ── SSE helpers ───────────────────────────────────────────────────────────────


def _sse_line(data: str) -> str:
    return f"data: {data}\n\n"


def _sse_comment(msg: str) -> str:
    return f": {msg}\n\n"


def _sse_event(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


# ── Payload builder ───────────────────────────────────────────────────────────


def _build_stream_payload(
    request: SimulateRequest,
    checkpoint_every: int,
) -> dict[str, Any]:
    """Convert SimulateRequest to Mojo engine JSON payload with stream=True."""
    if isinstance(request, SimulateRequestAuto):
        payload = _build_auto_mojo_payload(request)
    else:
        payload = _build_expert_mojo_payload(request)
    payload["stream"] = True
    payload["checkpoint_every"] = checkpoint_every
    return payload


# ── Core async generator ──────────────────────────────────────────────────────


async def _stream_mojo(payload: dict[str, Any]) -> AsyncGenerator[str, None]:
    """
    Spawn mojo binary, relay NDJSON lines as SSE frames.
    Yields SSE-formatted strings.
    """
    if not os.path.isfile(_BIN):
        yield _sse_event(
            "error",
            json.dumps({"error": "Mojo engine not built", "hint": "run make build-mojo"}),
        )
        return

    payload_bytes = json.dumps(payload).encode()

    try:
        proc = await asyncio.create_subprocess_exec(
            _BIN,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception:
        logger.exception(
            "stream_mojo_spawn_failed",
            route="/v1/simulate/stream",
        )
        yield _sse_event(
            "error",
            json.dumps(
                {
                    "error": {
                        "code": "engine_spawn_failed",
                        "message": "Failed to start the simulation engine.",
                    }
                }
            ),
        )
        return

    assert proc.stdin and proc.stdout

    # Feed payload to stdin, close so engine knows input is done
    proc.stdin.write(payload_bytes)
    proc.stdin.close()

    # Send a heartbeat comment immediately so the connection doesn't time out
    yield _sse_comment("stream-started")

    # Read stdout line by line
    async for raw_line in proc.stdout:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Non-JSON (e.g. debug print) — forward as comment
            yield _sse_comment(line[:200])
            continue

        t = obj.get("type", "")
        if t == "progress":
            yield _sse_event("progress", line)
        elif t == "final":
            yield _sse_event("final", line)
        else:
            # Unknown structured output — pass through as a data frame
            yield _sse_line(line)

    await proc.wait()

    if proc.returncode != 0:
        err_msg = ""
        if proc.stderr is not None:
            stderr_raw = await proc.stderr.read()
            err_msg = stderr_raw.decode("utf-8", errors="replace")[:500]
        yield _sse_event("error", json.dumps({"error": "engine_error", "detail": err_msg}))

    yield _sse_comment("stream-end")


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.post(
    "/v1/simulate/stream",
    summary="Streaming simulation via Server-Sent Events",
    description=textwrap.dedent("""
        Run a simulation and receive progressive results via **Server-Sent Events**.

        The connection stays open and emits events as the Mojo engine computes:
        - **`progress`** events every `checkpoint_every` runs (default: 1000)
          Each carries Welford online statistics: `mean`, `std`, `min`, `max`,
          `probability_of_loss`, `runs_completed`, `progress` (0–1).
        - **`final`** event when complete — contains the full `DecisionEnvelope`
          identical to what `/v1/simulate` returns.

        ### Example (curl)
        ```bash
        curl -N -X POST /v1/simulate/stream \\
          -H "Authorization: Bearer sk-..." \\
          -H "Content-Type: application/json" \\
          -d '{"mode":"expert","runs":100000,"variables":[...]}'
        ```

        ### Example (JavaScript EventSource)
        ```javascript
        const es = new EventSource('/v1/simulate/stream?token=sk-...');
        es.addEventListener('progress', e => console.log(JSON.parse(e.data)));
        es.addEventListener('final', e => {
          console.log(JSON.parse(e.data).result);
          es.close();
        });
        ```

        ### Query parameters
        - `checkpoint_every` — emit a progress event every N runs (default: 1000, min: 100)
    """),
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE stream of progress events + final DecisionEnvelope",
        },
    },
)
async def simulate_stream(
    request: Request,
    payload: SimulateRequest,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis: Annotated[object, Depends(get_redis)],
    checkpoint_every: int = 1000,
) -> StreamingResponse:
    """Stream simulation results via SSE as Mojo computes."""
    # ── Auth + quota (same guards as /v1/simulate) ────────────────────────────
    try:
        await check_rate_limit(
            auth["org_id"],
            auth["plan"],
            redis,
            request_state=request.state,
        )
    except Exception as exc:
        logger.debug("stream_rate_limit_check_failed", error=str(exc))

    try:
        await check_quota_redis(auth["org_id"], auth["plan"], redis)
    except Exception:
        logger.exception(
            "stream_quota_check_failed",
            route="/v1/simulate/stream",
            org_id=str(auth["org_id"]),
        )

        async def _quota_err() -> AsyncGenerator[str, None]:
            yield _sse_event(
                "error",
                json.dumps(
                    {
                        "error": {
                            "code": "quota_exceeded",
                            "message": "Quota check failed or limit reached.",
                        }
                    }
                ),
            )

        return StreamingResponse(
            _quota_err(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Build Mojo payload ────────────────────────────────────────────────────
    if checkpoint_every < 100:
        checkpoint_every = 100
    mojo_payload = _build_stream_payload(payload, checkpoint_every)

    logger.info(
        "stream_simulation_start",
        org_id=str(auth["org_id"]),
        runs=mojo_payload.get("runs"),
        engine_type=mojo_payload.get("engine_type"),
        checkpoint_every=checkpoint_every,
    )

    return StreamingResponse(
        _stream_mojo(mojo_payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx: disable response buffering
            "Connection": "keep-alive",
        },
    )
