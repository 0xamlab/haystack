"""Async loopback client for the agent-core sidecar (the forked-Cline execution head).

POSTs one run to the sidecar over the NDJSON contract and returns its ``final`` frame —
the ``run_agent`` result dict the ``verified_agentic`` planner consumes. The sidecar
mutates files under ``working_dir`` (shared filesystem); Python recomputes the diff.

Wave B2 made this:
  * async + non-blocking (httpx, never freezes the event loop);
  * routed through ``egress_guard`` as an operator-configured internal service, so the
    fail-closed self-hosted/air-gapped policy + audit apply (loopback is allowed, not
    SSRF-blocked — same posture as the MinIO client);
  * retry ONLY on connection-establishment failures — a run that already started must
    never be re-issued (that would re-bill the LLM). The dedup lock (Wave C2) makes
    broader retries safe later;
  * fronted by a per-endpoint circuit breaker so a wedged sidecar fails fast.

Wiring (unchanged):
    run_agent = make_sidecar_run_agent(os.environ["ALGENTA_AGENT_CORE_URL"])  # async
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
from typing import Any

import httpx
from httpx import AsyncClient

from apps.api_server.services.egress_guard import EgressAuditContext, async_http_request

DEFAULT_TIMEOUT_S = 120.0
_AGENT_CORE_URL_ENV = "ALGENTA_AGENT_CORE_URL"
_MAX_CONNECT_RETRIES = int(os.environ.get("ALGENTA_AGENT_CORE_CONNECT_RETRIES", "2"))
_CONNECT_TIMEOUT_S = 10.0
_BREAKER_THRESHOLD = int(os.environ.get("ALGENTA_AGENT_CORE_BREAKER_THRESHOLD", "5"))
_BREAKER_COOLDOWN_S = float(os.environ.get("ALGENTA_AGENT_CORE_BREAKER_COOLDOWN_S", "30"))


class _CircuitBreaker:
    """Per-endpoint breaker: opens after N consecutive failures, half-opens after a
    cooldown so one trial can close it. Stops a wedged sidecar from absorbing traffic."""

    def __init__(self, threshold: int, cooldown_s: float) -> None:
        self._threshold = threshold
        self._cooldown_s = cooldown_s
        self._failures: dict[str, int] = {}
        self._opened_at: dict[str, float] = {}

    def check(self, key: str) -> None:
        opened = self._opened_at.get(key)
        if opened is None:
            return
        if time.monotonic() - opened < self._cooldown_s:
            raise RuntimeError(
                f"agent-core circuit open for {key} "
                f"(cooling down ~{self._cooldown_s:.0f}s after repeated failures)"
            )
        self._opened_at.pop(key, None)  # cooldown elapsed -> half-open (allow a trial)

    def record_success(self, key: str) -> None:
        self._failures.pop(key, None)
        self._opened_at.pop(key, None)

    def record_failure(self, key: str) -> None:
        count = self._failures.get(key, 0) + 1
        self._failures[key] = count
        if count >= self._threshold:
            self._opened_at[key] = time.monotonic()


_BREAKER = _CircuitBreaker(_BREAKER_THRESHOLD, _BREAKER_COOLDOWN_S)


def _backoff_seconds(attempt: int) -> float:
    base = min(0.5 * (2 ** (attempt - 1)), 5.0)
    return base + random.uniform(0, base / 2)  # exponential backoff + jitter


def _parse_final_frame(text: str) -> dict[str, Any]:
    """Last ``final`` NDJSON frame wins; intermediate frames are streaming telemetry."""
    final: dict[str, Any] = {}
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            frame = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(frame, dict) and frame.get("type") == "final":
            final = frame
    if not final:
        # No final frame => the sidecar died mid-stream; treat as aborted.
        return {"status": "aborted", "agent_run_id": None, "transcript_ref": None}
    return final


async def run_agent_via_sidecar(
    *,
    working_dir: str,
    task_spec: dict[str, Any],
    injected_context: dict[str, Any],
    limits: dict[str, Any],
    base_url: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    client: AsyncClient | None = None,
    audit_context: EgressAuditContext | None = None,
) -> dict[str, Any]:
    """POST one run to the agent-core sidecar and return its ``final`` frame.

    Raises RuntimeError if no base_url is configured, the circuit is open, the sidecar
    is unreachable after retries, or a request fails mid-flight (the planner maps a
    failed runner onto a RepositoryIntelligenceError)."""
    base_url = base_url or os.environ.get(_AGENT_CORE_URL_ENV)
    if not base_url:
        raise RuntimeError(
            f"agent-core base_url not configured (set {_AGENT_CORE_URL_ENV} or pass base_url)."
        )
    url = base_url.rstrip("/") + "/run"
    body = {
        "working_dir": working_dir,
        "task_spec": task_spec,
        "injected_context": injected_context,
        "limits": limits,
    }
    timeout = httpx.Timeout(connect=_CONNECT_TIMEOUT_S, read=timeout_s, write=30.0, pool=_CONNECT_TIMEOUT_S)

    # B7: authenticate to the sidecar with the shared internal bearer when configured
    # (the operator sets the same value as the sidecar's AGENT_CORE_AUTH_TOKEN).
    headers: dict[str, str] = {}
    token = os.environ.get("ALGENTA_AGENT_CORE_TOKEN") or os.environ.get("AGENT_CORE_AUTH_TOKEN")
    if token:
        headers["authorization"] = f"Bearer {token}"

    _BREAKER.check(base_url)
    attempt = 0
    while True:
        attempt += 1
        try:
            response = await async_http_request(
                method="POST",
                url=url,
                surface="repository_agent_core",
                explicit_configured=True,
                egress_class="operator_service",
                audit_context=audit_context,
                client=client,
                json=body,
                headers=headers,
                timeout=timeout,
            )
            break
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            # Connection never established -> the run has NOT started; safe to retry.
            _BREAKER.record_failure(base_url)
            if attempt > _MAX_CONNECT_RETRIES:
                raise RuntimeError(
                    f"agent-core sidecar unreachable after {attempt} attempt(s): {exc}"
                ) from exc
            await asyncio.sleep(_backoff_seconds(attempt))
        except (httpx.HTTPError, OSError) as exc:
            # Mid-flight failure: the run may have started -> NEVER retry (no re-bill).
            _BREAKER.record_failure(base_url)
            raise RuntimeError(f"agent-core sidecar request failed: {exc}") from exc

    _BREAKER.record_success(base_url)
    return _parse_final_frame(response.text)


def make_sidecar_run_agent(base_url: str | None = None):
    """Return an async ``run_agent``-shaped callable bound to a sidecar base_url."""

    async def _runner(
        *,
        working_dir: str,
        task_spec: dict[str, Any],
        injected_context: dict[str, Any],
        limits: dict[str, Any],
    ) -> dict[str, Any]:
        return await run_agent_via_sidecar(
            working_dir=working_dir,
            task_spec=task_spec,
            injected_context=injected_context,
            limits=limits,
            base_url=base_url,
        )

    return _runner
