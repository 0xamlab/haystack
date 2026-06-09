"""
Live HTTP runtime-library coverage for the 22-library Mojo LLM rollout.

This verifies the feature-flagged `/v1/libraries*` surface against the real
compiled Mojo worker pool, not mocked route handlers.

Run:
  python3 tests/integration/test_runtime_libraries_http_live.py
"""

from __future__ import annotations

import os
import sys

if __name__ == "__main__" and os.environ.get("ALGENTA_SKIP_RUNTIME_LIBRARIES_HTTP", "0") == "1":
    print("[skip] tests/integration/test_runtime_libraries_http_live.py — ALGENTA_SKIP_RUNTIME_LIBRARIES_HTTP=1")
    sys.exit(0)

import importlib
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.llm_rollout_live_artifacts import (
    LIVE_SUMMARY_ARTIFACTS,
    write_live_summary_artifact,
)
from apps.api_server.config import get_settings
from apps.api_server.middleware.auth import get_current_org
from tests._asgi_client import SyncASGIClient
from tests.llm_rollout_matrix import (
    LLM_ROLLOUT_FUNCTION_CASES,
    LLM_ROLLOUT_FUNCTIONS_BY_MODULE,
    LLM_ROLLOUT_MODULE_NAMES,
    assert_rollout_channel_result,
)

PASS = "✅"
FAIL = "❌"
SUITE_NAME = "public_http_library_routes_feature_flag_live"
SUMMARY_ARTIFACT = LIVE_SUMMARY_ARTIFACTS[SUITE_NAME]
results: list[tuple[str, bool, str]] = []


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def check(name: str, fn) -> Any:
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    try:
        value = fn()
        results.append((name, True, ""))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
        return value
    except AssertionError as exc:
        results.append((name, False, str(exc)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {exc}")
        return None
    except Exception as exc:  # noqa: BLE001
        message = f"{type(exc).__name__}: {exc}"
        results.append((name, False, message))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {message}")
        return None


def _reload_api_app() -> Any:
    get_settings.cache_clear()
    if "apps.api_server.main" in sys.modules:
        module = importlib.reload(sys.modules["apps.api_server.main"])
    else:
        module = importlib.import_module("apps.api_server.main")
    return module.app


def main() -> int:
    started = time.perf_counter()
    _emit("\n" + "=" * 70)
    _emit("  LIVE HTTP RUNTIME LIBRARY COVERAGE")
    _emit("=" * 70)

    previous_flag = os.environ.get("ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED")
    os.environ["ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED"] = "1"

    app = _reload_api_app()
    from apps.api_server.middleware import idempotency as idempotency_middleware
    from apps.api_server.routers import runtime_libraries as runtime_libraries_router

    original_rate_limit = runtime_libraries_router._enforce_runtime_library_rate_limit
    original_coordination_store = idempotency_middleware._coordination_store

    async def _allow_rate_limit(
        *,
        request: object,
        auth: object,
        redis_client: object,
    ) -> None:
        return None

    async def _fake_auth() -> dict[str, str]:
        return {
            "org_id": "org_http_runtime_live",
            "plan": "pro",
            "role": "owner",
            "user_id": "u_http_runtime_live",
            "key_id": "k_http_runtime_live",
        }

    runtime_libraries_router._enforce_runtime_library_rate_limit = _allow_rate_limit
    idempotency_middleware._coordination_store = (
        lambda request: idempotency_middleware._LOCAL_STORE
    )
    app.dependency_overrides[get_current_org] = _fake_auth

    try:
        with SyncASGIClient(
            app,
            manage_lifespan=True,
            raise_app_exceptions=False,
        ) as client:
            def test_http_health() -> None:
                response = client.get("/v1/libraries/health")
                assert response.status_code == 200, response.text
                payload = response.json()
                assert payload["status"] == "ok"
                assert payload["engine"] == "mojo"
                assert payload["runtime_available"] is True
                assert payload["module_count"] >= len(LLM_ROLLOUT_MODULE_NAMES)

            check("HTTP health reports live Mojo runtime availability", test_http_health)

            def test_http_inventory() -> None:
                modules: list[dict[str, Any]] = []
                page = 1
                total = None
                while total is None or len(modules) < total:
                    response = client.get("/v1/libraries", params={"limit": 200, "page": page})
                    assert response.status_code == 200, response.text
                    payload = response.json()
                    if total is None:
                        total = int(payload["total"])
                    modules.extend(payload["modules"])
                    if payload["count"] == 0:
                        break
                    page += 1

                assert total is not None
                assert len(modules) >= len(LLM_ROLLOUT_MODULE_NAMES)
                module_names = {item["name"] for item in modules}
                expected = set(LLM_ROLLOUT_MODULE_NAMES)
                assert expected.issubset(module_names)
                functions_by_name = {
                    str(item["name"]): tuple(str(function) for function in item["functions"])
                    for item in modules
                }
                for module_name, expected_functions in LLM_ROLLOUT_FUNCTIONS_BY_MODULE.items():
                    assert set(functions_by_name[module_name]) == set(expected_functions)

            check("HTTP lists all 22 rollout runtime modules", test_http_inventory)

            def test_http_search() -> None:
                response = client.get("/v1/libraries", params={"q": "kv_cache", "limit": 50})
                assert response.status_code == 200, response.text
                payload = response.json()
                names = {item["name"] for item in payload["modules"]}
                assert "kv_cache" in names
                assert "paged_kv_cache" in names

            check("HTTP module search finds serving rollout modules", test_http_search)

            def test_http_execute_all() -> None:
                for index, case in enumerate(LLM_ROLLOUT_FUNCTION_CASES):
                    response = client.post(
                        "/v1/libraries/execute",
                        json={
                            "module": case.module,
                            "function": case.function,
                            "args": case.args,
                            "request_id": f"req_http_rollout_{index:03d}",
                        },
                    )
                    assert response.status_code == 200, (
                        f"{case.module}.{case.function} -> {response.status_code}: {response.text}"
                    )
                    payload = response.json()
                    assert payload["module"] == case.module
                    assert payload["function"] == case.function
                    assert payload["engine_used"] == "mojo"
                    assert payload["request_id"] == f"req_http_rollout_{index:03d}"
                    assert_rollout_channel_result(case, payload["result"])

            check("HTTP executes all LLM rollout functions", test_http_execute_all)
    finally:
        app.dependency_overrides.clear()
        runtime_libraries_router._enforce_runtime_library_rate_limit = original_rate_limit
        idempotency_middleware._coordination_store = original_coordination_store
        if previous_flag is None:
            os.environ.pop("ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED", None)
        else:
            os.environ["ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED"] = previous_flag
        get_settings.cache_clear()

    failed = [name for name, ok, _ in results if not ok]
    _emit("\n" + "=" * 70)
    _emit(f"Passed: {sum(1 for _, ok, _ in results if ok)}")
    _emit(f"Failed: {len(failed)}")
    if failed:
        for name in failed:
            _emit(f"  - {name}")
    _emit("=" * 70)
    summary = write_live_summary_artifact(
        output_path=SUMMARY_ARTIFACT,
        suite_name=SUITE_NAME,
        script="tests/integration/test_runtime_libraries_http_live.py",
        channels=("http_api_feature_flag",),
        minimum_passed=4,
        passed=sum(1 for _, ok, _ in results if ok),
        failed=len(failed),
        skipped=0,
        elapsed_seconds=time.perf_counter() - started,
        extra={"feature_flag": "ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED"},
    )
    _emit(f"Summary artifact: {SUMMARY_ARTIFACT}")
    assert summary["status"] == ("passed" if not failed else "failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    import pytest
    exit_code = pytest.main([__file__, "-v"])
    try:
        from tests.integration.live_integration_artifacts import write_live_integration_summary
        artifact_path = write_live_integration_summary(
            SUITE_NAME,
            script="tests/integration/test_runtime_libraries_http_live.py",
            passed=0, failed=0, skipped=0, total=0,
            elapsed_seconds=0.0,
        )
        print(f"Summary artifact: {artifact_path}")
    except Exception:
        pass
    sys.exit(exit_code)
