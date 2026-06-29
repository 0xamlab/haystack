"""Wave A1 regression: a long agent run must not freeze the API event loop.

Before A1 the verified_agentic planner awaited a BLOCKING urllib call (run_agent)
directly inside its async coroutine, freezing the whole uvicorn worker for the
multi-minute run and starving every co-tenant request. A1 wraps run_agent in
asyncio.to_thread. This test proves the loop stays responsive: a heartbeat keeps
ticking while a deliberately slow (blocking) run_agent executes.

This guards the A1 mitigation; B2 supersedes it (worker job + async client), at
which point this test moves to the worker path.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from pathlib import Path

from apps.api_server.services import repository_intelligence_verified_agentic as va

_SLOW_SECONDS = 0.4
_HEARTBEAT_INTERVAL = 0.02


async def test_blocking_run_agent_does_not_starve_event_loop(monkeypatch, tmp_path: Path):
    # Stub the heavy I/O so we reach run_agent with minimal setup.
    @contextlib.contextmanager
    def _fake_materialized(_manifest, **_kwargs):
        yield str(tmp_path)

    monkeypatch.setattr(va.repository_storage, "materialized_snapshot", _fake_materialized)
    monkeypatch.setattr(va, "_build_line_context_bundle", lambda **_: {})
    monkeypatch.setattr(va, "_capture_repository_tree_state", lambda _p: {})
    monkeypatch.setattr(va, "_dedupe_bundled_evidence", lambda evidence, _bundle: evidence)
    # non-empty diff so the planner returns a plan instead of raising "no_change"
    monkeypatch.setattr(va, "_unified_diff_from_tree_states", lambda _a, _b: "--- a\n+++ b\n")
    monkeypatch.setattr(va, "_planner_usage_from_agent_result", lambda _r: {})

    def _slow_blocking_run_agent(**_kwargs):
        time.sleep(_SLOW_SECONDS)  # mimics the blocking urllib call to the sidecar
        return {"status": "completed", "root_cause": "x", "confidence": 0.6}

    ticks = 0

    async def _heartbeat():
        nonlocal ticks
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            ticks += 1

    loop = asyncio.get_running_loop()
    hb = asyncio.create_task(_heartbeat())
    start = loop.time()

    plan = await va._generate_verified_agentic_repository_patch_plan(
        model_id="repository.verified_agentic_v1",
        snapshot_manifest={"snapshot_id": "snap_test", "repository_id": "repo_test"},
        triage_manifest={},
        run_agent=_slow_blocking_run_agent,
        graph_query=lambda **_: None,
    )

    elapsed = loop.time() - start
    hb.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await hb

    # the blocking work really took ~_SLOW_SECONDS ...
    assert elapsed >= _SLOW_SECONDS
    assert plan["patch_diff"]
    # ... yet the loop kept ticking. If run_agent were awaited on-loop (the bug),
    # the heartbeat would be frozen (~0-1 ticks). With to_thread it ticks freely.
    expected_min_ticks = int((_SLOW_SECONDS / _HEARTBEAT_INTERVAL) * 0.4)
    assert ticks >= expected_min_ticks, f"event loop was starved during the agent run (ticks={ticks})"


async def test_async_run_agent_is_awaited_and_non_blocking(monkeypatch, tmp_path: Path):
    """B2: the default runner is async; the planner awaits it directly (no to_thread) and
    a slow async run_agent (non-blocking I/O) still lets the loop serve co-tenants."""

    @contextlib.contextmanager
    def _fake_materialized(_manifest, **_kwargs):
        yield str(tmp_path)

    monkeypatch.setattr(va.repository_storage, "materialized_snapshot", _fake_materialized)
    monkeypatch.setattr(va, "_build_line_context_bundle", lambda **_: {})
    monkeypatch.setattr(va, "_capture_repository_tree_state", lambda _p: {})
    monkeypatch.setattr(va, "_dedupe_bundled_evidence", lambda evidence, _bundle: evidence)
    monkeypatch.setattr(va, "_unified_diff_from_tree_states", lambda _a, _b: "--- a\n+++ b\n")
    monkeypatch.setattr(va, "_planner_usage_from_agent_result", lambda _r: {})

    async def _slow_async_run_agent(**_kwargs):
        await asyncio.sleep(_SLOW_SECONDS)  # non-blocking; the planner awaits it directly
        return {"status": "completed", "root_cause": "x", "confidence": 0.6}

    ticks = 0

    async def _heartbeat():
        nonlocal ticks
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            ticks += 1

    hb = asyncio.create_task(_heartbeat())
    plan = await va._generate_verified_agentic_repository_patch_plan(
        model_id="repository.verified_agentic_v1",
        snapshot_manifest={"snapshot_id": "snap_test", "repository_id": "repo_test"},
        triage_manifest={},
        run_agent=_slow_async_run_agent,
        graph_query=lambda **_: None,
    )
    hb.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await hb

    assert plan["patch_diff"]
    assert ticks >= int((_SLOW_SECONDS / _HEARTBEAT_INTERVAL) * 0.4)
