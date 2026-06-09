"""Loopback client for the agent-core sidecar (the forked-Cline execution head).

This is the production replacement for ``planner_generation._DEFAULT_RUN_AGENT``: it
POSTs the run request to the Node agent-core over the loopback NDJSON contract and
returns the sidecar's ``final`` frame, which IS the ``run_agent`` result dict the
``verified_agentic`` planner tier consumes. The sidecar mutates files under
``working_dir`` (shared filesystem); Python recomputes the authoritative diff.

Wiring (kept out of the planner module so it survives independent of it):
    from apps.api_server.services.repository_intelligence_agent_core_client import (
        make_sidecar_run_agent,
    )
    run_agent = make_sidecar_run_agent(os.environ["ALGENTA_AGENT_CORE_URL"])

Only loopback is used; the agent-core is the only cross-process hop in the product.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_TIMEOUT_S = 120
_AGENT_CORE_URL_ENV = "ALGENTA_AGENT_CORE_URL"


def run_agent_via_sidecar(
    *,
    working_dir: str,
    task_spec: dict[str, Any],
    injected_context: dict[str, Any],
    limits: dict[str, Any],
    base_url: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """POST one run to the agent-core sidecar and return its ``final`` frame.

    Raises RuntimeError if no base_url is configured, or on transport failure
    (the planner maps a missing/failed runner onto a RepositoryIntelligenceError).
    """
    base_url = base_url or os.environ.get(_AGENT_CORE_URL_ENV)
    if not base_url:
        raise RuntimeError(
            "agent-core base_url not configured "
            f"(set {_AGENT_CORE_URL_ENV} or pass base_url)."
        )

    payload = json.dumps(
        {
            "working_dir": working_dir,
            "task_spec": task_spec,
            "injected_context": injected_context,
            "limits": limits,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/run",
        data=payload,
        headers={"content-type": "application/json"},
        method="POST",
    )

    final: dict[str, Any] = {}
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                frame = json.loads(line)
                # The last `final` frame wins; intermediate event frames are
                # streaming telemetry only.
                if frame.get("type") == "final":
                    final = frame
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise RuntimeError(f"agent-core sidecar request failed: {exc}") from exc

    if not final:
        # No final frame => the sidecar died mid-stream; treat as aborted.
        return {"status": "aborted", "agent_run_id": None, "transcript_ref": None}
    return final


def make_sidecar_run_agent(base_url: str | None = None):
    """Return a ``run_agent``-shaped callable bound to a sidecar base_url."""

    def _runner(
        *,
        working_dir: str,
        task_spec: dict[str, Any],
        injected_context: dict[str, Any],
        limits: dict[str, Any],
    ) -> dict[str, Any]:
        return run_agent_via_sidecar(
            working_dir=working_dir,
            task_spec=task_spec,
            injected_context=injected_context,
            limits=limits,
            base_url=base_url,
        )

    return _runner
