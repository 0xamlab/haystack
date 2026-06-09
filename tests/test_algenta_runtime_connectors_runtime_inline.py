"""Tests for test_algenta_runtime_connectors: runtime_inline.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_3967a6fe-cb7-2/tests/test_algenta_runtime_connectors.py during modularization.
"""
from __future__ import annotations

from tests._test_algenta_runtime_connectors_helpers import *  # noqa: F401,F403


def test_runtime_inline_preview_uses_direct_preview_endpoints_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    calls: list[tuple[str, object]] = []

    class _FakeClient:
        def preview_test_connector(
            self, *, connector_type: str, config: dict[str, object] | None = None
        ):
            calls.append(("preview_test", {"connector_type": connector_type, "config": config}))
            return {
                "success": True,
                "message": "ok",
                "latency_ms": 9,
                "status": "live",
                "error_type": None,
                "recoverable": None,
            }

        def preview_browse_connector(
            self,
            *,
            connector_type: str,
            config: dict[str, object] | None = None,
        ):
            calls.append(("preview_browse", {"connector_type": connector_type, "config": config}))
            return _browse_payload("preview_inline")

        def create_connector(self, **kwargs):
            raise AssertionError(f"unexpected create_connector call: {kwargs}")

        def test_connector(self, connector_id: str):
            raise AssertionError(f"unexpected saved connector test: {connector_id}")

        def browse_connector(self, connector_id: str):
            raise AssertionError(f"unexpected saved connector browse: {connector_id}")

        def delete_connector(self, connector_id: str):
            raise AssertionError(f"unexpected delete_connector call: {connector_id}")

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    test_result = runtime.test_connector(
        connector={"type": "redis", "url": "redis://localhost:6379"}
    )
    browse = runtime.browse_connector(connector={"type": "redis", "url": "redis://localhost:6379"})

    assert test_result.success is True
    assert browse.total == 1
    assert calls == [
        ("preview_test", {"connector_type": "redis", "config": {"url": "redis://localhost:6379"}}),
        (
            "preview_browse",
            {"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
        ),
    ]


def test_runtime_inline_preview_falls_back_to_ephemeral_connector_flow_when_preview_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    calls: list[tuple[str, object]] = []

    class _PreviewUnavailableError(Exception):
        status_code = 404
        error_code = "not_found"
        response_body = {"error": {"code": "not_found", "message": "Not found"}}

    class _FakeClient:
        def preview_test_connector(
            self, *, connector_type: str, config: dict[str, object] | None = None
        ):
            raise _PreviewUnavailableError()

        def preview_browse_connector(
            self,
            *,
            connector_type: str,
            config: dict[str, object] | None = None,
        ):
            raise _PreviewUnavailableError()

        def create_connector(self, **kwargs):
            calls.append(("create", kwargs))
            return _connector_payload("preview_1")

        def test_connector(self, connector_id: str):
            calls.append(("test", connector_id))
            return {
                "success": True,
                "message": "ok",
                "latency_ms": 9,
                "status": "live",
                "error_type": None,
                "recoverable": None,
            }

        def browse_connector(self, connector_id: str):
            calls.append(("browse", connector_id))
            return _browse_payload(connector_id)

        def delete_connector(self, connector_id: str):
            calls.append(("delete", connector_id))
            return None

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    test_result = runtime.test_connector(
        connector={"type": "redis", "url": "redis://localhost:6379"}
    )
    browse = runtime.browse_connector(connector={"type": "redis", "url": "redis://localhost:6379"})

    assert test_result.success is True
    assert browse.total == 1
    assert [name for name, _payload in calls].count("create") == 2
    assert [name for name, _payload in calls].count("delete") == 2
    assert ("test", "preview_1") in calls
    assert ("browse", "preview_1") in calls


def test_runtime_inline_preview_rate_limit_surfaces_structured_error() -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    now = time.monotonic()
    runtime._inline_preview_events = [now] * 20

    with pytest.raises(RuntimeValidationError, match="rate limited"):
        runtime.test_connector(connector={"type": "redis", "url": "redis://localhost:6379"})


def test_runtime_inline_preview_cache_reuses_direct_preview_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    calls: list[tuple[str, object]] = []

    class _FakeClient:
        def preview_test_connector(
            self, *, connector_type: str, config: dict[str, object] | None = None
        ):
            calls.append(("preview_test", {"connector_type": connector_type, "config": config}))
            return {
                "success": True,
                "message": "ok",
                "latency_ms": 8,
                "status": "live",
                "error_type": None,
                "recoverable": None,
            }

        def preview_browse_connector(
            self,
            *,
            connector_type: str,
            config: dict[str, object] | None = None,
        ):
            calls.append(("preview_browse", {"connector_type": connector_type, "config": config}))
            return _browse_payload("preview_inline")

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    first_test = runtime.test_connector(
        connector={"type": "redis", "url": "redis://localhost:6379"}
    )
    second_test = runtime.test_connector(
        connector={"type": "redis", "url": "redis://localhost:6379"}
    )
    first_browse = runtime.browse_connector(
        connector={"type": "redis", "url": "redis://localhost:6379"}
    )
    second_browse = runtime.browse_connector(
        connector={"type": "redis", "url": "redis://localhost:6379"}
    )

    assert first_test == second_test
    assert first_browse == second_browse
    assert calls == [
        ("preview_test", {"connector_type": "redis", "config": {"url": "redis://localhost:6379"}}),
        (
            "preview_browse",
            {"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
        ),
    ]


def test_runtime_inline_preview_cache_expires_and_refreshes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    calls = 0

    class _FakeClient:
        def preview_test_connector(
            self, *, connector_type: str, config: dict[str, object] | None = None
        ):
            nonlocal calls
            calls += 1
            return {
                "success": True,
                "message": "ok",
                "latency_ms": 8,
                "status": "live",
                "error_type": None,
                "recoverable": None,
            }

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    runtime.test_connector(connector={"type": "redis", "url": "redis://localhost:6379"})
    assert len(runtime._inline_preview_cache) == 1
    cache_key = next(iter(runtime._inline_preview_cache))
    cached_value = runtime._inline_preview_cache[cache_key][1]
    runtime._inline_preview_cache[cache_key] = (0.0, cached_value)

    runtime.test_connector(connector={"type": "redis", "url": "redis://localhost:6379"})

    assert calls == 2


def test_runtime_inline_preview_capability_cache_skips_repeated_missing_test_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    calls: list[tuple[str, object]] = []

    class _PreviewUnavailableError(Exception):
        status_code = 404
        error_code = "not_found"
        response_body = {"error": {"code": "not_found", "message": "Not found"}}

    class _FakeClient:
        def preview_test_connector(
            self,
            *,
            connector_type: str,
            config: dict[str, object] | None = None,
        ):
            calls.append(("preview_test", {"connector_type": connector_type, "config": config}))
            raise _PreviewUnavailableError()

        def create_connector(self, **kwargs):
            calls.append(("create", kwargs))
            return _connector_payload("preview_1")

        def test_connector(self, connector_id: str):
            calls.append(("test", connector_id))
            return {
                "success": True,
                "message": "ok",
                "latency_ms": 8,
                "status": "live",
                "error_type": None,
                "recoverable": None,
            }

        def delete_connector(self, connector_id: str):
            calls.append(("delete", connector_id))
            return None

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    first = runtime.test_connector(connector={"type": "redis", "url": "redis://localhost:6379/0"})
    second = runtime.test_connector(connector={"type": "redis", "url": "redis://localhost:6379/1"})

    assert first.success is True
    assert second.success is True
    assert [name for name, _payload in calls if name == "preview_test"] == ["preview_test"]
    assert [name for name, _payload in calls if name == "create"] == ["create", "create"]
    assert runtime._get_inline_preview_capability(operation="test") is False


def test_runtime_inline_preview_capability_cache_expires_and_retries_missing_browse_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    calls: list[tuple[str, object]] = []

    class _PreviewUnavailableError(Exception):
        status_code = 404
        error_code = "not_found"
        response_body = {"error": {"code": "not_found", "message": "Not found"}}

    class _FakeClient:
        def preview_browse_connector(
            self,
            *,
            connector_type: str,
            config: dict[str, object] | None = None,
        ):
            calls.append(("preview_browse", {"connector_type": connector_type, "config": config}))
            raise _PreviewUnavailableError()

        def create_connector(self, **kwargs):
            calls.append(("create", kwargs))
            return _connector_payload("preview_1")

        def test_connector(self, connector_id: str):
            calls.append(("test", connector_id))
            return {
                "success": True,
                "message": "ok",
                "latency_ms": 8,
                "status": "live",
                "error_type": None,
                "recoverable": None,
            }

        def browse_connector(self, connector_id: str):
            calls.append(("browse", connector_id))
            return _browse_payload(connector_id)

        def delete_connector(self, connector_id: str):
            calls.append(("delete", connector_id))
            return None

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    first = runtime.browse_connector(connector={"type": "redis", "url": "redis://localhost:6379/0"})
    runtime._inline_preview_capabilities["browse"] = (0.0, False)
    second = runtime.browse_connector(
        connector={"type": "redis", "url": "redis://localhost:6379/1"}
    )

    assert first.total == 1
    assert second.total == 1
    assert [name for name, _payload in calls if name == "preview_browse"] == [
        "preview_browse",
        "preview_browse",
    ]
    assert runtime._get_inline_preview_capability(operation="browse") is False


