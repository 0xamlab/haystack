from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from decision_engine import async_client_job_surface, client_job_surface


def test_submit_job_normalizes_legacy_simulation_payload() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs["json"]
        return {"job_id": "job_123"}

    client = SimpleNamespace(_request=_request)

    result = client_job_surface.submit_job(
        client,
        {
            "variables": [
                {
                    "name": "revenue",
                    "distribution": "normal",
                    "mean": 100000,
                    "std_dev": 15000,
                }
            ],
            "runs": 500,
        },
    )

    assert result == {"job_id": "job_123"}
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/jobs"
    assert captured["json"] == {
        "request": {
            "mode": "expert",
            "simulation": {
                "variables": [
                    {
                        "name": "revenue",
                        "distribution": "normal",
                        "params": {"mean": 100000, "std": 15000},
                    }
                ],
                "objective_function": "revenue",
                "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
            },
            "runs": 500,
        }
    }


def test_submit_job_accepts_documented_kwargs_surface() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["json"] = kwargs["json"]
        return {"job_id": "job_456"}

    client = SimpleNamespace(_request=_request)

    result = client_job_surface.submit_job(
        client,
        mode="auto",
        scenario={
            "variables": {"revenue": {"low": 80000, "high": 200000}},
            "objective": "maximize_net_value",
        },
        runs=1000,
        callback_url="https://example.com/webhook",
    )

    assert result == {"job_id": "job_456"}
    assert captured["json"] == {
        "request": {
            "mode": "auto",
            "scenario": {
                "variables": {"revenue": {"low": 80000, "high": 200000}},
                "objective": "maximize_net_value",
            },
            "runs": 1000,
        },
        "callback_url": "https://example.com/webhook",
    }


def test_submit_job_backfills_missing_auto_objective() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["json"] = kwargs["json"]
        return {"job_id": "job_789"}

    client = SimpleNamespace(_request=_request)

    result = client_job_surface.submit_job(
        client,
        {
            "mode": "auto",
            "scenario": {
                "variables": {
                    "revenue": {"low": 100000, "high": 130000},
                    "cost": {"low": -90000, "high": -65000},
                }
            },
        },
    )

    assert result == {"job_id": "job_789"}
    assert captured["json"] == {
        "request": {
            "mode": "auto",
            "scenario": {
                "variables": {
                    "revenue": {"low": 100000, "high": 130000},
                    "cost": {"low": -90000, "high": -65000},
                },
                "objective": "maximize_net_value",
            },
        }
    }


@pytest.mark.anyio
async def test_async_submit_job_unwraps_request_envelope() -> None:
    captured: dict[str, object] = {}

    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs["json"]
        return {"job_id": "job_async"}

    client = SimpleNamespace(_request=_request)

    result = await async_client_job_surface.submit_job(
        client,
        {
            "request": {
                "mode": "auto",
                "scenario": {
                    "variables": {"x": {"low": 1, "high": 2}},
                    "objective": "maximize_net_value",
                },
            }
        },
    )

    assert result == {"job_id": "job_async"}
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/jobs"
    assert captured["json"] == {
        "request": {
            "mode": "auto",
            "scenario": {
                "variables": {"x": {"low": 1, "high": 2}},
                "objective": "maximize_net_value",
            },
        }
    }


def test_list_jobs_builds_paginated_query() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        assert kwargs == {}
        return {"jobs": [], "total": 0, "page": 2, "limit": 10, "pages": 0}

    client = SimpleNamespace(_request=_request)

    result = client_job_surface.list_jobs(client, page=2, limit=10, status="queued")

    assert result.page == 2
    assert result.limit == 10
    assert result.jobs == []
    assert captured == {
        "method": "GET",
        "path": "/v1/jobs/list?page=2&limit=10&status=queued",
    }


def test_get_job_targets_status_endpoint() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        assert kwargs == {}
        return {"job_id": "job_123", "status": "queued"}

    client = SimpleNamespace(_request=_request)

    result = client_job_surface.get_job(client, "job_123")

    assert result["status"] == "queued"
    assert captured == {"method": "GET", "path": "/v1/jobs/job_123"}


def test_get_job_result_targets_result_endpoint() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        assert kwargs == {}
        return {"job_id": "job_123", "result": {"ok": True}}

    client = SimpleNamespace(_request=_request)

    result = client_job_surface.get_job_result(client, "job_123")

    assert result["result"] == {"ok": True}
    assert captured == {"method": "GET", "path": "/v1/jobs/job_123/result"}


def test_cancel_job_targets_cancel_endpoint() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        assert kwargs == {}
        return {"job_id": "job_123", "status": "cancelled"}

    client = SimpleNamespace(_request=_request)

    result = client_job_surface.cancel_job(client, "job_123")

    assert result["status"] == "cancelled"
    assert captured == {"method": "POST", "path": "/v1/jobs/job_123/cancel"}


def test_test_webhook_delivery_targets_webhook_endpoint() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs["json"]
        return {"success": True, "status_code": 200, "message": "delivered"}

    client = SimpleNamespace(_request=_request)

    result = client_job_surface.test_webhook_delivery(client, "https://example.com/webhook")

    assert result["success"] is True
    assert captured == {
        "method": "POST",
        "path": "/v1/webhooks/test",
        "json": {"callback_url": "https://example.com/webhook"},
    }


def test_poll_job_returns_result_when_status_turns_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            {"job_id": "job_123", "status": "running"},
            {"job_id": "job_123", "status": "completed"},
            {"job_id": "job_123", "result": {"score": 0.98}},
        ]
    )
    calls: list[tuple[str, str]] = []

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert kwargs == {}
        calls.append((method, path))
        return next(responses)

    sleep_calls: list[float] = []
    monkeypatch.setattr(client_job_surface.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    client = SimpleNamespace(_request=_request)

    result = client_job_surface.poll_job(client, "job_123", timeout=5.0, poll_interval=0.25)

    assert result == {"job_id": "job_123", "result": {"score": 0.98}}
    assert calls == [
        ("GET", "/v1/jobs/job_123"),
        ("GET", "/v1/jobs/job_123"),
        ("GET", "/v1/jobs/job_123/result"),
    ]
    assert sleep_calls == [0.25]


def test_poll_job_raises_for_terminal_failed_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert kwargs == {}
        assert method == "GET"
        assert path == "/v1/jobs/job_123"
        return {
            "job_id": "job_123",
            "status": "failed",
            "error_message": "worker crashed",
        }

    monkeypatch.setattr(client_job_surface.time, "sleep", lambda _seconds: None)
    client = SimpleNamespace(_request=_request)

    with pytest.raises(client_job_surface.DecisionEngineError, match="worker crashed"):
        client_job_surface.poll_job(client, "job_123", timeout=5.0, poll_interval=0.25)


def test_poll_job_raises_for_terminal_cancelled_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert kwargs == {}
        assert method == "GET"
        assert path == "/v1/jobs/job_123"
        return {
            "job_id": "job_123",
            "status": "cancelled",
            "error_message": "cancelled by user",
        }

    monkeypatch.setattr(client_job_surface.time, "sleep", lambda _seconds: None)
    client = SimpleNamespace(_request=_request)

    with pytest.raises(client_job_surface.DecisionEngineError, match="cancelled by user"):
        client_job_surface.poll_job(client, "job_123", timeout=5.0, poll_interval=0.25)


@pytest.mark.anyio
async def test_async_list_jobs_builds_paginated_query() -> None:
    captured: dict[str, object] = {}

    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        assert kwargs == {}
        return {"jobs": [], "total": 0, "page": 1, "limit": 25, "pages": 0}

    client = SimpleNamespace(_request=_request)

    result = await async_client_job_surface.list_jobs(client)

    assert result.limit == 25
    assert result.page == 1
    assert result.jobs == []
    assert captured == {
        "method": "GET",
        "path": "/v1/jobs/list?page=1&limit=25",
    }


@pytest.mark.anyio
async def test_async_get_job_and_result_and_cancel_target_expected_endpoints() -> None:
    calls: list[tuple[str, str]] = []

    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert kwargs == {}
        calls.append((method, path))
        if path.endswith("/result"):
            return {"job_id": "job_123", "result": {"ok": True}}
        if path.endswith("/cancel"):
            return {"job_id": "job_123", "status": "cancelled"}
        return {"job_id": "job_123", "status": "queued"}

    client = SimpleNamespace(_request=_request)

    status = await async_client_job_surface.get_job(client, "job_123")
    result = await async_client_job_surface.get_job_result(client, "job_123")
    cancelled = await async_client_job_surface.cancel_job(client, "job_123")

    assert status["status"] == "queued"
    assert result["result"] == {"ok": True}
    assert cancelled["status"] == "cancelled"
    assert calls == [
        ("GET", "/v1/jobs/job_123"),
        ("GET", "/v1/jobs/job_123/result"),
        ("POST", "/v1/jobs/job_123/cancel"),
    ]


@pytest.mark.anyio
async def test_async_test_webhook_delivery_targets_webhook_endpoint() -> None:
    captured: dict[str, object] = {}

    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs["json"]
        return {"success": False, "status_code": 502, "message": "delivery failed"}

    client = SimpleNamespace(_request=_request)

    result = await async_client_job_surface.test_webhook_delivery(
        client,
        "https://example.com/webhook",
    )

    assert result["status_code"] == 502
    assert captured == {
        "method": "POST",
        "path": "/v1/webhooks/test",
        "json": {"callback_url": "https://example.com/webhook"},
    }


@pytest.mark.anyio
async def test_async_poll_job_returns_result_when_status_turns_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            {"job_id": "job_123", "status": "running"},
            {"job_id": "job_123", "status": "completed"},
            {"job_id": "job_123", "result": {"score": 0.99}},
        ]
    )
    calls: list[tuple[str, str]] = []
    sleep_calls: list[float] = []

    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert kwargs == {}
        calls.append((method, path))
        return next(responses)

    async def _sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(async_client_job_surface.asyncio, "sleep", _sleep)
    client = SimpleNamespace(_request=_request)

    result = await async_client_job_surface.poll_job(
        client,
        "job_123",
        timeout=5.0,
        poll_interval=0.25,
    )

    assert result == {"job_id": "job_123", "result": {"score": 0.99}}
    assert calls == [
        ("GET", "/v1/jobs/job_123"),
        ("GET", "/v1/jobs/job_123"),
        ("GET", "/v1/jobs/job_123/result"),
    ]
    assert sleep_calls == [0.25]


@pytest.mark.anyio
async def test_async_poll_job_raises_for_terminal_cancelled_status() -> None:
    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert kwargs == {}
        assert method == "GET"
        assert path == "/v1/jobs/job_123"
        return {
            "job_id": "job_123",
            "status": "cancelled",
            "error_message": "cancelled by user",
        }

    client = SimpleNamespace(_request=_request)

    with pytest.raises(async_client_job_surface.DecisionEngineError, match="cancelled by user"):
        await async_client_job_surface.poll_job(
            client,
            "job_123",
            timeout=5.0,
            poll_interval=0.25,
        )


@pytest.mark.anyio
async def test_async_poll_job_raises_for_terminal_failed_status() -> None:
    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert kwargs == {}
        assert method == "GET"
        assert path == "/v1/jobs/job_123"
        return {
            "job_id": "job_123",
            "status": "failed",
            "error_message": "worker crashed",
        }

    client = SimpleNamespace(_request=_request)

    with pytest.raises(async_client_job_surface.DecisionEngineError, match="worker crashed"):
        await async_client_job_surface.poll_job(
            client,
            "job_123",
            timeout=5.0,
            poll_interval=0.25,
        )


@pytest.mark.anyio
async def test_async_poll_job_raises_for_timeout_without_sleeping_past_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert kwargs == {}
        calls.append((method, path))
        return {"job_id": "job_123", "status": "running"}

    sleep_calls: list[float] = []
    time_values = iter([100.0, 100.1, 100.2])

    async def _sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(async_client_job_surface.asyncio, "sleep", _sleep)
    monkeypatch.setattr(async_client_job_surface.time, "time", lambda: next(time_values))
    client = SimpleNamespace(_request=_request)

    with pytest.raises(async_client_job_surface.DecisionEngineError, match="timed out after 0.15s"):
        await async_client_job_surface.poll_job(
            client,
            "job_123",
            timeout=0.15,
            poll_interval=0.25,
        )

    assert calls == [("GET", "/v1/jobs/job_123")]
    assert sleep_calls == [0.25]
