"""Wave B2: the agent-core sidecar client is async + egress-guarded, retries ONLY
connection-establishment failures (a started run must never be re-issued / re-billed),
and is fronted by a per-endpoint circuit breaker."""

from __future__ import annotations

import json

import httpx
import pytest

from apps.api_server.services import repository_intelligence_agent_core_client as cc


class _Resp:
    def __init__(self, text: str) -> None:
        self.text = text


@pytest.mark.anyio
async def test_routes_through_egress_and_returns_final_frame(monkeypatch):
    async def _fake(**kwargs):
        # routed through egress_guard as an internal operator service (loopback allowed)
        assert kwargs["egress_class"] == "operator_service"
        assert kwargs["explicit_configured"] is True
        assert kwargs["url"].endswith("/run")
        return _Resp(
            "\n".join(
                [
                    json.dumps({"type": "event", "n": 1}),
                    json.dumps({"type": "final", "status": "completed", "agent_run_id": "r1"}),
                ]
            )
        )

    monkeypatch.setattr(cc, "async_http_request", _fake)
    cc._BREAKER.record_success("http://x")
    out = await cc.run_agent_via_sidecar(
        working_dir="/w", task_spec={}, injected_context={}, limits={}, base_url="http://x"
    )
    assert out["type"] == "final" and out["status"] == "completed" and out["agent_run_id"] == "r1"


@pytest.mark.anyio
async def test_missing_base_url_raises(monkeypatch):
    monkeypatch.delenv("ALGENTA_AGENT_CORE_URL", raising=False)
    with pytest.raises(RuntimeError):
        await cc.run_agent_via_sidecar(working_dir="/w", task_spec={}, injected_context={}, limits={})


@pytest.mark.anyio
async def test_connect_error_is_retried_then_succeeds(monkeypatch):
    calls = {"n": 0}

    async def _fake(**kwargs):
        calls["n"] += 1
        if calls["n"] <= 1:
            raise httpx.ConnectError("connection refused")
        return _Resp(json.dumps({"type": "final", "status": "completed"}))

    monkeypatch.setattr(cc, "async_http_request", _fake)
    monkeypatch.setattr(cc, "_backoff_seconds", lambda _a: 0.0)
    cc._BREAKER.record_success("http://retry")
    out = await cc.run_agent_via_sidecar(
        working_dir="/w", task_spec={}, injected_context={}, limits={}, base_url="http://retry"
    )
    assert out["status"] == "completed"
    assert calls["n"] == 2  # exactly one retry of the connection


@pytest.mark.anyio
async def test_mid_flight_error_is_not_retried(monkeypatch):
    """A read timeout means the run may have started — must NOT be re-issued."""
    calls = {"n": 0}

    async def _fake(**kwargs):
        calls["n"] += 1
        raise httpx.ReadTimeout("mid-flight")

    monkeypatch.setattr(cc, "async_http_request", _fake)
    cc._BREAKER.record_success("http://midflight")
    with pytest.raises(RuntimeError):
        await cc.run_agent_via_sidecar(
            working_dir="/w", task_spec={}, injected_context={}, limits={}, base_url="http://midflight"
        )
    assert calls["n"] == 1


@pytest.mark.anyio
async def test_circuit_opens_after_threshold(monkeypatch):
    key = "http://breaker-test"
    for _ in range(cc._BREAKER_THRESHOLD):
        cc._BREAKER.record_failure(key)

    async def _must_not_dispatch(**kwargs):
        raise AssertionError("must not dispatch while the circuit is open")

    monkeypatch.setattr(cc, "async_http_request", _must_not_dispatch)
    with pytest.raises(RuntimeError, match="circuit open"):
        await cc.run_agent_via_sidecar(
            working_dir="/w", task_spec={}, injected_context={}, limits={}, base_url=key
        )
    cc._BREAKER.record_success(key)  # reset shared singleton for other tests
