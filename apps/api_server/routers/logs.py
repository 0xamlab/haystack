"""
GET /v1/logs — Server-Sent Events (SSE) streaming of structured API logs.

In production this would tail a real log aggregator (Loki, CloudWatch, Datadog).
Here we tail the structlog output from the running process via a shared asyncio queue.
"""
import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from apps.api_server.middleware.auth import AuthContext, get_current_org

router = APIRouter(tags=["Logs"])

# Module-level queue: structlog middleware pushes entries here
_log_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)


def push_log_event(event: dict) -> None:
    """Called by middleware/services to push a log line into the SSE queue."""
    try:
        _log_queue.put_nowait({**event, "ts": datetime.now(tz=UTC).isoformat()})
    except asyncio.QueueFull:
        # Drop oldest if queue is full (non-blocking)
        try:
            _log_queue.get_nowait()
            _log_queue.put_nowait({**event, "ts": datetime.now(tz=UTC).isoformat()})
        except asyncio.QueueEmpty:
            pass


async def _generate_log_stream(request: Request, node_id: str | None = None) -> AsyncIterator[str]:
    """Yield SSE events from the log queue until client disconnects."""
    # Send initial connection event
    yield (
        "data: "
        + json.dumps(
            {
                "type": "connected",
                "ts": datetime.now(tz=UTC).isoformat(),
                "message": "Log stream connected",
            }
        )
        + "\n\n"
    )

    while True:
        # Check if client disconnected
        if await request.is_disconnected():
            break

        try:
            # Wait for next log event (timeout so we can check disconnect)
            log_event = await asyncio.wait_for(_log_queue.get(), timeout=5.0)

            # Filter by node_id if specified
            if node_id and log_event.get("node_id") != node_id:
                continue

            yield f"data: {json.dumps(log_event)}\n\n"

        except TimeoutError:
            # Send keepalive ping so connection doesn't timeout
            yield f": keepalive {datetime.now(tz=UTC).isoformat()}\n\n"
        except GeneratorExit:
            break
        except Exception:
            break


@router.get(
    "/v1/logs",
    summary="Stream structured logs via Server-Sent Events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_logs(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    node_id: str | None = None,
    level: str | None = None,
) -> StreamingResponse:
    """
    SSE stream of API log events.

    Query params:
    - node_id: filter by compute node ID
    - level: filter by log level (info, warning, error)

    Connect with:
        const es = new EventSource('/v1/logs', { headers: { Authorization: 'Bearer sk_...' } })
    """
    return StreamingResponse(
        _generate_log_stream(request, node_id=node_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
