from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import jobs


def test_job_tool_specs_cover_async_listing_surface() -> None:
    assert jobs.SUBMIT_JOB_SPEC["name"] == "submit_job"
    assert jobs.GET_JOB_STATUS_SPEC["name"] == "get_job_status"
    assert jobs.POLL_JOB_SPEC["name"] == "poll_job"
    assert jobs.GET_JOB_RESULT_SPEC["name"] == "get_job_result"
    assert jobs.LIST_JOBS_SPEC["name"] == "list_jobs"
    assert jobs.CANCEL_JOB_SPEC["name"] == "cancel_job"
    assert jobs.TEST_WEBHOOK_DELIVERY_SPEC["name"] == "test_webhook_delivery"
    assert jobs.LIST_JOBS_SPEC["inputSchema"]["properties"]["page"]["minimum"] == 1
    assert jobs.LIST_JOBS_SPEC["inputSchema"]["properties"]["limit"]["minimum"] == 1


@pytest.mark.anyio
async def test_job_handlers_forward_canonical_api_routes(monkeypatch) -> None:
    calls: list[tuple[str, str, object]] = []

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((method, path, kwargs.get("json")))
        if (method, path) == ("POST", "/v1/jobs"):
            return {"job_id": "job_123", "status": "queued"}
        if (method, path) == ("GET", "/v1/jobs/job_123"):
            return {"job_id": "job_123", "status": "queued"}
        if (method, path) == ("GET", "/v1/jobs/job_123/result"):
            return {"status": "queued", "message": "result not ready"}
        if (method, path) == ("GET", "/v1/jobs/list?page=2&limit=10&status=queued"):
            return {"jobs": [], "total": 0, "page": 2, "limit": 10, "pages": 0}
        if (method, path) == ("POST", "/v1/jobs/job_123/cancel"):
            return {"job_id": "job_123", "status": "cancelled"}
        if (method, path) == ("POST", "/v1/webhooks/test"):
            return {"success": True, "status_code": 200, "message": "delivered"}
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(jobs, "api", _fake_api)

    submitted = json.loads(
        await jobs.submit_job_handler(
            {
                "variables": [{"name": "revenue", "low": 10, "high": 20}],
                "objective": "maximize_net_value",
                "n_simulations": 1000,
            }
        )
    )
    status = json.loads(await jobs.get_job_status_handler({"job_id": "job_123"}))
    result = json.loads(await jobs.get_job_result_handler({"job_id": "job_123"}))
    listed = json.loads(await jobs.list_jobs_handler({"page": 2, "limit": 10, "status": "queued"}))
    cancelled = json.loads(await jobs.cancel_job_handler({"job_id": "job_123"}))
    webhook = json.loads(
        await jobs.test_webhook_delivery_handler({"callback_url": "https://example.com/webhook"})
    )

    assert submitted["job_id"] == "job_123"
    assert status["job_id"] == "job_123"
    assert result["status"] == "queued"
    assert listed["page"] == 2
    assert cancelled["status"] == "cancelled"
    assert webhook["status_code"] == 200
    assert calls == [
        (
            "POST",
            "/v1/jobs",
            {
                "mode": "auto",
                "n_simulations": 1000,
                "scenario": {
                    "variables": {"revenue": {"low": 10, "high": 20}},
                    "objective": "maximize_net_value",
                },
            },
        ),
        ("GET", "/v1/jobs/job_123", None),
        ("GET", "/v1/jobs/job_123/result", None),
        ("GET", "/v1/jobs/list?page=2&limit=10&status=queued", None),
        ("POST", "/v1/jobs/job_123/cancel", None),
        ("POST", "/v1/webhooks/test", {"callback_url": "https://example.com/webhook"}),
    ]


@pytest.mark.anyio
async def test_list_jobs_handler_validates_pagination_arguments() -> None:
    with pytest.raises(ValueError, match="page must be at least 1"):
        await jobs.list_jobs_handler({"page": 0})
    with pytest.raises(ValueError, match="limit must be at least 1"):
        await jobs.list_jobs_handler({"limit": 0})


@pytest.mark.anyio
async def test_poll_job_handler_waits_until_completion_and_fetches_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    status_attempts = 0

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal status_attempts
        calls.append((method, path))
        if (method, path) == ("GET", "/v1/jobs/job_123"):
            status_attempts += 1
            if status_attempts == 1:
                return 200, {"job_id": "job_123", "status": "queued"}
            return 200, {"job_id": "job_123", "status": "completed"}
        if (method, path) == ("GET", "/v1/jobs/job_123/result"):
            return 200, {"status": "completed", "best_action": "expand_capacity"}
        raise AssertionError(f"unexpected call {(method, path)}")

    async def _fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(jobs, "api_with_status", _fake_api_with_status)
    monkeypatch.setattr(jobs.asyncio, "sleep", _fake_sleep)

    payload = json.loads(
        await jobs.poll_job_handler(
            {
                "job_id": "job_123",
                "timeout_seconds": 5.0,
                "poll_interval_seconds": 0.1,
            }
        )
    )

    assert payload["job"]["status"] == "completed"
    assert payload["result"]["best_action"] == "expand_capacity"
    assert calls == [
        ("GET", "/v1/jobs/job_123"),
        ("GET", "/v1/jobs/job_123"),
        ("GET", "/v1/jobs/job_123/result"),
    ]


@pytest.mark.anyio
async def test_poll_job_handler_returns_timeout_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeLoop:
        def __init__(self) -> None:
            self._times = iter((0.0, 0.02))

        def time(self) -> float:
            return next(self._times, 0.02)

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/jobs/job_123")
        return 200, {"job_id": "job_123", "status": "queued"}

    async def _fake_sleep(_: float) -> None:
        raise AssertionError("sleep should not be reached after timeout")

    monkeypatch.setattr(jobs, "api_with_status", _fake_api_with_status)
    monkeypatch.setattr(jobs.asyncio, "get_running_loop", lambda: _FakeLoop())
    monkeypatch.setattr(jobs.asyncio, "sleep", _fake_sleep)

    payload = json.loads(
        await jobs.poll_job_handler(
            {
                "job_id": "job_123",
                "timeout_seconds": 0.01,
                "poll_interval_seconds": 0.5,
            }
        )
    )

    assert payload["job"]["status"] == "queued"
    assert payload["timed_out"] is True
    assert payload["terminal"] is False


@pytest.mark.anyio
async def test_poll_job_handler_validates_timeout_arguments() -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be greater than 0"):
        await jobs.poll_job_handler({"job_id": "job_123", "timeout_seconds": 0})
    with pytest.raises(ValueError, match="poll_interval_seconds must be greater than 0"):
        await jobs.poll_job_handler({"job_id": "job_123", "poll_interval_seconds": 0})


@pytest.mark.anyio
async def test_result_and_cancel_handlers_require_job_id() -> None:
    assert json.loads(await jobs.poll_job_handler({})) == {"error": "job_id is required"}
    assert json.loads(await jobs.get_job_result_handler({})) == {"error": "job_id is required"}
    assert json.loads(await jobs.cancel_job_handler({})) == {"error": "job_id is required"}
    assert json.loads(await jobs.test_webhook_delivery_handler({})) == {
        "error": "callback_url is required"
    }
