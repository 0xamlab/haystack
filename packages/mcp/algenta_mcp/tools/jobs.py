"""MCP tools: submit_job, list_jobs, get_job_status, poll_job, get_job_result, cancel_job, test_webhook_delivery."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from algenta_mcp.client import api

SUBMIT_JOB_SPEC: dict[str, Any] = {
    "name": "submit_job",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Submit a long-running async simulation job. "
        "Use for n_simulations > 500,000 or when you need a callback. "
        "variables is an array of {name, low, high} objects — one uniform range "
        "per variable; objective defaults to maximize and n_simulations defaults "
        "to 1000000. "
        "Returns a job_id — poll with get_job_status. Submitting persists the job "
        "under the active API key's organization; when callback_url is set, "
        "completion is delivered to it by outbound webhook."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "variables": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "One {name, low, high} object per variable (uniform range)."
                ),
            },
            "objective": {"type": "string", "default": "maximize"},
            "n_simulations": {"type": "integer", "default": 1000000},
            "callback_url": {
                "type": "string",
                "description": "Webhook URL for completion notification",
            },
        },
        "required": ["variables"],
    },
}

GET_JOB_STATUS_SPEC: dict[str, Any] = {
    "name": "get_job_status",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Fetch the latest async simulation job status by id. Read-only and non-destructive; "
        "not separately rate-limited. Use poll_job to block until a terminal state. Returns "
        "the job record with status, progress, timestamps, and poll_url."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "UUID of the async job"},
        },
        "required": ["job_id"],
    },
}

POLL_JOB_SPEC: dict[str, Any] = {
    "name": "poll_job",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Wait for an async simulation job to reach a terminal state. Returns the final "
        "result when the job completes, or the terminal status when it fails, is cancelled, "
        "or times out. Read-only: it polls the job's status endpoints and changes nothing. "
        "Use get_job_status for a single non-blocking check."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "UUID of the async job"},
            "timeout_seconds": {
                "type": "number",
                "minimum": 0.001,
                "default": 30.0,
                "description": "Maximum wall-clock time to wait before returning a timed_out response.",
            },
            "poll_interval_seconds": {
                "type": "number",
                "minimum": 0.001,
                "default": 2.0,
                "description": "Delay between status checks while the job is still queued or running.",
            },
        },
        "required": ["job_id"],
    },
}

GET_JOB_RESULT_SPEC: dict[str, Any] = {
    "name": "get_job_result",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Fetch an async simulation job's result payload once it has completed. Use "
        "get_job_status for a progress check (or poll_job to block) before calling "
        "this. Read-only and non-destructive; not separately rate-limited."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "UUID of the async job"},
        },
        "required": ["job_id"],
    },
}

LIST_JOBS_SPEC: dict[str, Any] = {
    "name": "list_jobs",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the organization's async simulation jobs, newest first, with pagination "
        "(defaults page 1, limit 25, max 200) and an optional status filter such as "
        "queued, running, completed, failed, or cancelled. Each entry carries the job "
        "id, status, progress, and poll URL. Use get_job_status or poll_job to follow "
        "one job and get_job_result for its output. Read-only. Returns jobs plus "
        "total, page, limit, and pages."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "minimum": 1,
                "default": 1,
                "description": "1-based page number; defaults to 1.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "default": 25,
                "description": "Jobs per page, up to 200; defaults to 25.",
            },
            "status": {
                "type": "string",
                "description": (
                    "Optional job status filter such as queued, running, completed, "
                    "failed, or cancelled."
                ),
            },
        },
    },
}

CANCEL_JOB_SPEC: dict[str, Any] = {
    "name": "cancel_job",
    "annotations": {"readOnlyHint": False, "destructiveHint": True,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Cancel a queued or running async simulation job by id. Use this for queued or "
        "running jobs; list_jobs shows their states. Returns the updated job record with "
        "its terminal status."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "UUID of the async job"},
        },
        "required": ["job_id"],
    },
}

TEST_WEBHOOK_DELIVERY_SPEC: dict[str, Any] = {
    "name": "test_webhook_delivery",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Send one real test webhook payload (event webhook.test with a sample message) "
        "to a callback URL and return the delivery result. This makes an actual "
        "outbound HTTP POST from the Algenta API to the given URL, with no retries. "
        "Use it to verify a receiver before wiring callback_url into submit_job or "
        "register_trigger. Returns success, the receiver's HTTP status_code, and a "
        "message."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "callback_url": {
                "type": "string",
                "description": "URL that should receive the test webhook payload.",
            },
        },
        "required": ["callback_url"],
    },
}


async def submit_job_handler(arguments: dict[str, Any]) -> str:
    variables_raw = arguments.get("variables", [])
    variables = (
        [item for item in variables_raw if isinstance(item, dict)]
        if isinstance(variables_raw, list)
        else []
    )
    objective = arguments.get("objective", "maximize")
    n_sims = int(arguments.get("n_simulations", 1_000_000))
    callback_url = arguments.get("callback_url")

    var_dict: dict[str, dict[str, Any]] = {}
    for v in variables:
        var_dict[v["name"]] = {"low": v["low"], "high": v["high"]}

    payload: dict[str, Any] = {
        "mode": "auto",
        "n_simulations": n_sims,
        "scenario": {"variables": var_dict, "objective": objective},
    }
    if callback_url:
        payload["callback_url"] = callback_url

    result = await api("POST", "/v1/jobs", json=payload)
    return json.dumps(
        {
            "job_id": result.get("job_id"),
            "status": result.get("status"),
            "message": "Job submitted. Poll with get_job_status(job_id=...) to check progress.",
        },
        indent=2,
    )


async def get_job_status_handler(arguments: dict[str, Any]) -> str:
    job_id = arguments.get("job_id")
    if not job_id:
        return json.dumps({"error": "job_id is required"})
    result = await api("GET", f"/v1/jobs/{job_id}")
    return json.dumps(result, indent=2)


async def poll_job_handler(arguments: dict[str, Any]) -> str:
    job_id = arguments.get("job_id")
    if not job_id:
        return json.dumps({"error": "job_id is required"})

    timeout_seconds = float(arguments.get("timeout_seconds", 30.0))
    poll_interval_seconds = float(arguments.get("poll_interval_seconds", 2.0))
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than 0")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be greater than 0")

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    status_path = f"/v1/jobs/{job_id}"
    result_path = f"/v1/jobs/{job_id}/result"
    last_status: dict[str, Any] | None = None

    while True:
        # api() raises a redacted MCPAPIError on >=400 (no raw-body leak); returns payload on 200.
        status_payload = await api("GET", status_path)
        if not isinstance(status_payload, dict):
            raise RuntimeError("Algenta API returned an unexpected job status payload type.")

        last_status = status_payload
        terminal_status = str(status_payload.get("status", "")).strip().lower()
        if terminal_status == "completed":
            result_payload = await api("GET", result_path)
            return json.dumps({"job": status_payload, "result": result_payload}, indent=2)

        if terminal_status in {"failed", "cancelled"}:
            return json.dumps({"job": status_payload, "terminal": True}, indent=2)

        now = loop.time()
        if now >= deadline:
            return json.dumps(
                {
                    "job": last_status,
                    "terminal": False,
                    "timed_out": True,
                    "timeout_seconds": timeout_seconds,
                },
                indent=2,
            )

        await asyncio.sleep(min(poll_interval_seconds, max(0.0, deadline - now)))


async def get_job_result_handler(arguments: dict[str, Any]) -> str:
    job_id = arguments.get("job_id")
    if not job_id:
        return json.dumps({"error": "job_id is required"})
    result = await api("GET", f"/v1/jobs/{job_id}/result")
    return json.dumps(result, indent=2)


async def list_jobs_handler(arguments: dict[str, Any]) -> str:
    page = int(arguments.get("page", 1))
    limit = int(arguments.get("limit", 25))
    status = arguments.get("status")
    if page < 1:
        raise ValueError("page must be at least 1")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    query = f"/v1/jobs/list?page={page}&limit={limit}"
    if isinstance(status, str) and status.strip():
        query = f"{query}&status={status.strip()}"
    result = await api("GET", query)
    return json.dumps(result, indent=2)


async def cancel_job_handler(arguments: dict[str, Any]) -> str:
    job_id = arguments.get("job_id")
    if not job_id:
        return json.dumps({"error": "job_id is required"})
    result = await api("POST", f"/v1/jobs/{job_id}/cancel")
    return json.dumps(result, indent=2)


async def test_webhook_delivery_handler(arguments: dict[str, Any]) -> str:
    callback_url = arguments.get("callback_url")
    if not isinstance(callback_url, str) or not callback_url:
        return json.dumps({"error": "callback_url is required"})
    result = await api("POST", "/v1/webhooks/test", json={"callback_url": callback_url})
    return json.dumps(result, indent=2)
