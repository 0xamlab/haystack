"""MCP tools: submit_job, get_job_status."""
from __future__ import annotations

import json
from typing import Any

from apps.mcp_server.client import api

SUBMIT_JOB_SPEC: dict[str, Any] = {
    "name": "submit_job",
    "description": (
        "Submit a long-running async simulation job. "
        "Use for n_simulations > 500,000 or when you need a callback. "
        "Returns a job_id — poll with get_job_status."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "variables":     {"type": "array",  "items": {"type": "object"}},
            "objective":     {"type": "string", "default": "maximize"},
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
    "description": "Poll async simulation job status and retrieve result when complete.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "UUID of the async job"},
        },
        "required": ["job_id"],
    },
}


async def submit_job_handler(arguments: dict[str, Any]) -> str:
    variables    = arguments.get("variables", [])
    objective    = arguments.get("objective", "maximize")
    n_sims       = int(arguments.get("n_simulations", 1_000_000))
    callback_url = arguments.get("callback_url")

    var_dict: dict[str, dict] = {}
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
    return json.dumps({
        "job_id": result.get("job_id"),
        "status": result.get("status"),
        "message": "Job submitted. Poll with get_job_status(job_id=...) to check progress.",
    }, indent=2)


async def get_job_status_handler(arguments: dict[str, Any]) -> str:
    job_id = arguments.get("job_id")
    if not job_id:
        return json.dumps({"error": "job_id is required"})
    result = await api("GET", f"/v1/jobs/{job_id}")
    return json.dumps(result, indent=2)
