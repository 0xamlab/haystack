from __future__ import annotations

import json

import pytest

import benchmarks.llm_rollout_proof_bundle as proof_bundle
from tests.integration import test_go_live_full_real as go_live
from tests.integration.live_local_surface_env import (
    LOCAL_LIVE_SIMULATION_PERSIST_TRANSPORT,
)


def test_print_summary_lists_failed_suite_names(capsys) -> None:
    failed = go_live._print_summary(
        [
            ("Connectivity", True, 12.3),
            ("Live MCP", False, 45.6),
            ("Source matrix", True, 123.4),
            ("Mojo A-Z", False, 67.8),
        ]
    )

    captured = capsys.readouterr().out

    assert failed == 2
    assert "Passed suites: 2" in captured
    assert "Failed suites: 2" in captured
    assert "Failed suite names:" in captured
    assert "  - Live MCP" in captured
    assert "  - Mojo A-Z" in captured
    assert "  - ✅ Source matrix: 123.4s" in captured
    assert "  - ❌ Mojo A-Z: 67.8s" in captured


@pytest.mark.parametrize("attempts_before_success", [1])
def test_run_live_suite_with_fresh_server_retries_startup_once(
    monkeypatch, attempts_before_success: int
) -> None:
    ports = iter([55101, 55102])
    wait_calls: list[tuple[str, float]] = []
    start_calls: list[tuple[int, str]] = []
    start_envs: list[dict[str, str]] = []
    stop_calls: list[object] = []

    async def fake_seed_api_key(_database_url: str) -> tuple[str, str]:
        return ("de_test_key", "org_test")

    class _Proc:
        def __init__(self, port: int) -> None:
            self.port = port
            self.algenta_log_path = f"/tmp/fake-{port}.log"

    def fake_start_api_server(port: int, sources_dir, env):
        start_calls.append((port, str(sources_dir)))
        start_envs.append(dict(env))
        return _Proc(port)

    def fake_wait_for_http(url: str, timeout: float, *, proc=None, log_path=None) -> None:
        wait_calls.append((url, timeout))
        if len(wait_calls) <= attempts_before_success:
            raise RuntimeError("connection refused")

    def fake_run_suite(name: str, cmd: list[str], *, env: dict[str, str], timeout: int):
        return True, 12.5, ""

    monkeypatch.setattr(go_live, "free_port", lambda: next(ports))
    monkeypatch.setattr(go_live, "seed_api_key", fake_seed_api_key)
    monkeypatch.setattr(go_live, "start_api_server", fake_start_api_server)
    monkeypatch.setattr(go_live, "wait_for_http", fake_wait_for_http)
    monkeypatch.setattr(go_live, "run_suite", fake_run_suite)
    monkeypatch.setattr(go_live, "stop_process", lambda proc: stop_calls.append(proc))
    monkeypatch.setattr(go_live.time, "sleep", lambda _seconds: None)

    ok, elapsed, output = go_live.run_live_suite_with_fresh_server(
        "Live Runtime",
        ["python", "tests/integration/test_algenta_runtime_live.py"],
        env_base={"PYTHONPATH": "."},
        timeout=120,
    )

    assert ok is True
    assert elapsed == 12.5
    assert output == ""
    assert len(start_calls) == 2
    assert len(start_envs) == 2
    assert len(wait_calls) == 2
    assert wait_calls[0][1] == 120.0
    assert start_envs[0]["ALGENTA_RUNTIME_DIR"].endswith("runtime_1")
    assert start_envs[1]["ALGENTA_RUNTIME_DIR"].endswith("runtime_2")
    assert (
        start_envs[0]["ALGENTA_SIMULATION_PERSIST_TRANSPORT"]
        == LOCAL_LIVE_SIMULATION_PERSIST_TRANSPORT
    )
    assert len(stop_calls) >= 1


def test_run_live_suite_with_fresh_server_raises_after_second_startup_failure(monkeypatch) -> None:
    ports = iter([55201, 55202])
    stop_calls: list[object] = []

    async def fake_seed_api_key(_database_url: str) -> tuple[str, str]:
        return ("de_test_key", "org_test")

    class _Proc:
        def __init__(self, port: int) -> None:
            self.port = port
            self.algenta_log_path = f"/tmp/fake-{port}.log"

    def fake_start_api_server(port: int, sources_dir, env):
        return _Proc(port)

    def fake_wait_for_http(url: str, timeout: float, *, proc=None, log_path=None) -> None:
        raise RuntimeError("still starting")

    monkeypatch.setattr(go_live, "free_port", lambda: next(ports))
    monkeypatch.setattr(go_live, "seed_api_key", fake_seed_api_key)
    monkeypatch.setattr(go_live, "start_api_server", fake_start_api_server)
    monkeypatch.setattr(go_live, "wait_for_http", fake_wait_for_http)
    monkeypatch.setattr(go_live, "stop_process", lambda proc: stop_calls.append(proc))
    monkeypatch.setattr(go_live.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="still starting"):
        go_live.run_live_suite_with_fresh_server(
            "Live Runtime",
            ["python", "tests/integration/test_algenta_runtime_live.py"],
            env_base={"PYTHONPATH": "."},
            timeout=120,
        )

    assert len(stop_calls) >= 2


def test_parse_live_suite_counts_extracts_summary_numbers() -> None:
    counts = go_live._parse_live_suite_counts(
        """
Passed: 11
Skipped: 2
Failed: 0
"""
    )

    assert counts == {"passed": 11, "failed": 0, "skipped": 2}


def test_rollout_live_suite_summary_maps_known_scripts() -> None:
    summary = go_live._rollout_live_suite_summary(
        name="Live TypeScript Runtime integration",
        script="tests/integration/test_typescript_runtime_live.py",
        ok=True,
        elapsed=16.467,
        output="""
Passed: 2
Skipped: 2
Failed: 0
""",
    )

    assert summary == {
        "name": "typescript_sdk_local_runtime",
        "status": "passed",
        "elapsed_seconds": 16.467,
        "passed": 2,
        "failed": 0,
        "skipped": 2,
        "channels": ["typescript_sdk"],
        "minimum_passed": 2,
    }


def test_rollout_live_suite_summary_maps_http_feature_flag_script() -> None:
    summary = go_live._rollout_live_suite_summary(
        name="Live HTTP runtime library integration",
        script="tests/integration/test_runtime_libraries_http_live.py",
        ok=True,
        elapsed=21.204,
        output="""
Passed: 4
Skipped: 0
Failed: 0
""",
    )

    assert summary == {
        "name": "public_http_library_routes_feature_flag_live",
        "status": "passed",
        "elapsed_seconds": 21.204,
        "passed": 4,
        "failed": 0,
        "skipped": 0,
        "channels": ["http_api_feature_flag"],
        "minimum_passed": 4,
    }


def test_local_suites_include_root_javascript_workspace_check() -> None:
    assert go_live.LOCAL_SUITES[0] == (
        "Root JavaScript workspace check",
        ["make", "js-check"],
        600,
    )
    assert (
        "LLM rollout parity benchmark",
        [go_live.sys.executable, "benchmarks/llm_rollout_parity_benchmark.py"],
        600,
    ) in go_live.LOCAL_SUITES


def test_live_suites_use_canonical_cli_integration_script() -> None:
    assert (
        "Live CLI integration",
        [go_live.sys.executable, "tests/integration/test_cli.py"],
        300,
    ) in go_live.LIVE_SUITES


def test_write_llm_rollout_proof_bundle_persists_sdk_contract_suites(
    monkeypatch, tmp_path, capsys
) -> None:
    output_path = tmp_path / "llm_rollout_proof_bundle.json"
    synced: dict[str, object] = {}
    expected_bundle = {
        "bundle": "llm_rollout_proof_bundle",
        "sdk_contract_suites": [
            {
                "name": "python_sdk_package_contract",
                "status": "passed",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
            },
            {
                "name": "typescript_sdk_package_contract",
                "status": "passed",
                "passed": 1,
                "failed": 0,
                "skipped": 8,
            },
        ],
        "http_flag_contract_suites": [
            {
                "name": "public_http_library_routes_feature_flag",
                "status": "passed",
                "passed": 2,
                "failed": 0,
                "skipped": 0,
            }
        ],
        "http_flag_live_suites": [
            {
                "name": "public_http_library_routes_feature_flag_live",
                "status": "passed",
                "passed": 4,
                "failed": 0,
                "skipped": 0,
            }
        ],
        "live_suites": [
            {
                "name": "python_sdk_local_runtime",
                "status": "passed",
                "passed": 7,
                "failed": 0,
                "skipped": 0,
            }
        ],
        "serving_extension_channel_coverage": {
            "module_count": 6,
            "function_count": 60,
            "source_rollout_function_count": 209,
            "public_supported_channels_complete": True,
            "validated_auxiliary_channels_complete": True,
            "http_feature_flag_channel_complete": True,
            "channels": [
                {
                    "channel": "python_sdk",
                    "suite_name": "python_sdk_local_runtime",
                    "status": "passed",
                    "passed": 7,
                    "failed": 0,
                    "skipped": 0,
                    "feature_flag": False,
                    "module_count": 6,
                    "function_count": 60,
                    "covers_all_serving_extension_modules": True,
                    "covers_all_serving_extension_functions": True,
                }
            ],
        },
    }
    forwarded_results: list[dict[str, object]] = []

    monkeypatch.setattr(proof_bundle, "DEFAULT_OUTPUT", output_path)
    monkeypatch.setattr(proof_bundle, "SCORECARD_PATH", tmp_path / "scorecard.md")

    def fake_build_proof_bundle(
        *,
        run_live,
        refresh_artifacts,
        live_suite_results,
        http_flag_live_suite_results,
    ):
        assert run_live is False
        assert refresh_artifacts is False
        forwarded_results.extend(live_suite_results)
        assert http_flag_live_suite_results == [
            {
                "name": "public_http_library_routes_feature_flag_live",
                "status": "passed",
                "passed": 4,
                "failed": 0,
                "skipped": 0,
                "channels": ["http_api_feature_flag"],
                "minimum_passed": 4,
            }
        ]
        return expected_bundle

    monkeypatch.setattr(proof_bundle, "build_proof_bundle", fake_build_proof_bundle)
    monkeypatch.setattr(
        proof_bundle,
        "sync_rollout_scorecard",
        lambda bundle, *, scorecard_path=proof_bundle.SCORECARD_PATH: synced.setdefault(
            "bundle", bundle
        ),
    )

    ok, elapsed = go_live._write_llm_rollout_proof_bundle(
        live_suite_results=[
            {
                "name": "python_sdk_local_runtime",
                "status": "passed",
                "passed": 7,
                "failed": 0,
                "skipped": 0,
                "channels": ["python_sdk"],
                "minimum_passed": 7,
            }
        ],
        http_flag_live_suite_results=[
            {
                "name": "public_http_library_routes_feature_flag_live",
                "status": "passed",
                "passed": 4,
                "failed": 0,
                "skipped": 0,
                "channels": ["http_api_feature_flag"],
                "minimum_passed": 4,
            }
        ],
    )

    captured = capsys.readouterr().out
    assert ok is True
    assert elapsed >= 0.0
    assert "LLM rollout proof bundle" in captured
    assert str(output_path) in captured
    assert forwarded_results == [
        {
            "name": "python_sdk_local_runtime",
            "status": "passed",
            "passed": 7,
            "failed": 0,
            "skipped": 0,
            "channels": ["python_sdk"],
            "minimum_passed": 7,
        }
    ]
    assert json.loads(output_path.read_text()) == expected_bundle
    assert json.loads(output_path.read_text())["sdk_contract_suites"][1]["passed"] == 1
    assert json.loads(output_path.read_text())["sdk_contract_suites"][1]["skipped"] == 8
    assert json.loads(output_path.read_text())["http_flag_contract_suites"][0]["passed"] == 2
    assert json.loads(output_path.read_text())["http_flag_live_suites"][0]["passed"] == 4
    assert synced["bundle"] == expected_bundle
    channel_coverage = json.loads(output_path.read_text())["serving_extension_channel_coverage"]
    assert channel_coverage["module_count"] == 6
    assert channel_coverage["function_count"] == 60
    assert channel_coverage["public_supported_channels_complete"] is True
    assert channel_coverage["http_feature_flag_channel_complete"] is True


def test_write_llm_rollout_proof_bundle_reports_failure(monkeypatch, capsys) -> None:
    def fake_build_proof_bundle(
        *,
        run_live,
        refresh_artifacts,
        live_suite_results,
        http_flag_live_suite_results,
    ):
        raise RuntimeError("sdk contract bundle failed")

    monkeypatch.setattr(proof_bundle, "build_proof_bundle", fake_build_proof_bundle)
    monkeypatch.setattr(
        proof_bundle,
        "sync_rollout_scorecard",
        lambda bundle, *, scorecard_path=proof_bundle.SCORECARD_PATH: None,
    )

    ok, elapsed = go_live._write_llm_rollout_proof_bundle(
        live_suite_results=[],
        http_flag_live_suite_results=[],
    )

    captured = capsys.readouterr().out
    assert ok is False
    assert elapsed >= 0.0
    assert "LLM rollout proof bundle" in captured
    assert "sdk contract bundle failed" in captured
