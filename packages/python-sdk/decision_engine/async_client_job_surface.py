# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from .exceptions import DecisionEngineError
from .model_loader import validate_model as _validate_model
from .request_simulation_helpers import _normalize_simulation_request

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


def _normalize_job_request(
    request: dict[str, Any] | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(request or {})
    merged.update(kwargs)
    if (
        "request" in merged
        and isinstance(merged["request"], dict)
        and not any(key in merged for key in {"mode", "scenario", "simulation", "variables"})
    ):
        merged = dict(merged["request"])
    return _normalize_simulation_request(merged)


async def submit_job(
    client: AsyncDecisionEngineClient,
    request: dict[str, Any] | None = None,
    callback_url: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {"request": _normalize_job_request(request, kwargs)}
    if callback_url:
        body["callback_url"] = callback_url
    return await client._request("POST", "/v1/jobs", json=body)


async def get_job(client: AsyncDecisionEngineClient, job_id: str) -> dict[str, Any]:
    return await client._request("GET", f"/v1/jobs/{job_id}")


async def get_job_result(client: AsyncDecisionEngineClient, job_id: str) -> dict[str, Any]:
    return await client._request("GET", f"/v1/jobs/{job_id}/result")


async def list_jobs(
    client: AsyncDecisionEngineClient,
    *,
    page: int = 1,
    limit: int = 25,
    status: str | None = None,
) -> Any:
    query_params: dict[str, Any] = {"page": page, "limit": limit}
    if status:
        query_params["status"] = status
    data = await client._request("GET", f"/v1/jobs/list?{urlencode(query_params)}")
    return _validate_model("JobListResponse", data)


async def cancel_job(client: AsyncDecisionEngineClient, job_id: str) -> dict[str, Any]:
    return await client._request("POST", f"/v1/jobs/{job_id}/cancel")


async def test_webhook_delivery(
    client: AsyncDecisionEngineClient,
    callback_url: str,
) -> dict[str, Any]:
    return await client._request("POST", "/v1/webhooks/test", json={"callback_url": callback_url})


async def poll_job(
    client: AsyncDecisionEngineClient,
    job_id: str,
    timeout: float = 300.0,
    poll_interval: float = 2.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = await get_job(client, job_id)
        if status["status"] == "completed":
            return await get_job_result(client, job_id)
        if status["status"] in ("failed", "cancelled"):
            error_message = status.get("error_message")
            raise DecisionEngineError(
                f"Job {job_id} ended with status '{status['status']}': {error_message}"
            )
        await asyncio.sleep(poll_interval)
    raise DecisionEngineError(f"Job {job_id} timed out after {timeout}s")


__all__ = [
    "_normalize_job_request",
    "cancel_job",
    "get_job",
    "get_job_result",
    "list_jobs",
    "poll_job",
    "submit_job",
    "test_webhook_delivery",
]
