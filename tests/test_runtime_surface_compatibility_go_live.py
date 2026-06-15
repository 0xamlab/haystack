"""Tests for test_runtime_surface_compatibility: go_live.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-4/tests/test_runtime_surface_compatibility.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_surface_compatibility_helpers import *  # noqa: F401,F403


def test_go_live_suite_keeps_live_typescript_runtime_gate() -> None:
    go_live = (ROOT / "tests" / "integration" / "test_go_live_full_real.py").read_text(
        encoding="utf-8"
    )

    assert "Live CodnaClient integration" in go_live
    assert "tests/integration/test_algenta_client_live.py" in go_live
    assert "Live Python Mojo library integration" in go_live
    assert "tests/integration/test_algenta_mojo_library_live.py" in go_live
    assert "Live TypeScript Runtime integration" in go_live
    assert "tests/integration/test_typescript_runtime_live.py" in go_live
    assert "Live TypeScript SDK client integration" in go_live
    assert "tests/integration/test_typescript_sdk_client_live.py" in go_live
    assert "Live HTTP runtime library integration" in go_live
    assert "tests/integration/test_runtime_libraries_http_live.py" in go_live
    assert "LLM rollout parity benchmark" in go_live
    assert "benchmarks/llm_rollout_parity_benchmark.py" in go_live
    assert "LLM rollout compiled runtime benchmark" in go_live
    assert "benchmarks/llm_compiled_runtime_benchmark.py" in go_live
    assert "LLM rollout proof bundle" in go_live
    assert "build_proof_bundle(" in go_live


def test_go_live_full_real_script_writes_summary_artifact() -> None:
    full_real = (ROOT / "tests" / "integration" / "test_go_live_full_real.py").read_text(
        encoding="utf-8"
    )

    assert "python3 tests/integration/test_go_live_full_real.py" in full_real
    assert "PYTHONPATH=. python3 tests/integration/test_go_live_full_real.py" not in full_real
    assert "ROOT = Path(__file__).resolve().parents[2]" in full_real
    assert "sys.path.insert(0, str(ROOT))" in full_real
    assert 'SUITE_NAME = "go_live_full_real"' in full_real
    assert '"go_live_connectivity_local_only"' in full_real
    assert '"--summary-name"' in full_real
    assert "write_live_integration_summary(" in full_real
    assert "Summary artifact:" in full_real
    assert '("Live CLI integration", [sys.executable, "tests/integration/test_cli.py"], 300)' in full_real
    assert "test_cli_full.py" not in full_real


def test_go_live_connectivity_script_writes_summary_artifact() -> None:
    connectivity = (
        ROOT / "tests" / "integration" / "test_go_live_connectivity_real.py"
    ).read_text(encoding="utf-8")

    assert "python3 tests/integration/test_go_live_connectivity_real.py" in connectivity
    assert "PYTHONPATH=. python3 tests/integration/test_go_live_connectivity_real.py" not in connectivity
    assert 'SUITE_NAME = "go_live_connectivity_real"' in connectivity
    assert '"--summary-name"' in connectivity
    assert "write_live_integration_summary(" in connectivity
    assert "Summary artifact:" in connectivity
    assert '_emit(f"  ... {name}")' in connectivity


def test_go_live_verify_script_self_bootstraps_repo_imports() -> None:
    go_live_verify = (ROOT / "tests" / "go_live_verify.py").read_text(encoding="utf-8")

    assert "python3 tests/go_live_verify.py" not in go_live_verify
    assert "ROOT = Path(__file__).resolve().parents[1]" in go_live_verify
    assert "sys.path.insert(0, str(ROOT))" in go_live_verify
    assert "from tests.go_live_matrix_status import (" in go_live_verify


def test_go_live_full_real_skips_nested_verifier_inside_root_js_check() -> None:
    full_real = (ROOT / "tests" / "integration" / "test_go_live_full_real.py").read_text(
        encoding="utf-8"
    )

    assert 'if name == "Root JavaScript workspace check":' in full_real
    assert 'suite_env["DE_SKIP_GO_LIVE_VERIFY"] = "1"' in full_real


