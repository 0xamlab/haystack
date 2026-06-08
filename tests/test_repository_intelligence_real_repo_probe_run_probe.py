"""Tests for repository_intelligence_real_repo_probe: run_probe.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_run_probe_persists_runtime_and_measures_warm_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = _typescript_rootdir_repo(tmp_path)
    _init_git_repo(repo_path)
    runtime_dir = tmp_path / "runtime"

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _probe_envelope(), {"execution_ms": 9}

    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
        ),
    )

    result = run_probe(
        repo_path=repo_path,
        focus_paths=["services/app"],
        diagnostic_command="cat diagnostics.txt # pnpm exec tsc -p tsconfig.test.json --noEmit",
        diagnostic_base_path="services/app",
        planner_model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        runtime_dir=runtime_dir,
        reuse_existing_state=False,
        max_files=256,
        max_file_size_bytes=100_000,
        max_total_bytes=2_000_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert result["runtime"]["persisted"] is True
    assert Path(result["runtime"]["repository_runtime_root"]).exists()
    assert result["prepass"]["cache_status"] == "miss_stored"
    assert result["prepass"]["cache_enabled"] is True
    assert result["snapshot"]["status"] == "created"
    assert result["snapshot"]["warm_status"] == "existing"
    assert result["graph_query"]["seed_file_paths"]
    assert result["graph_query"]["top_change_risk_files"]
    assert result["decision_plan"]["decision_plan"]["repository_analysis"]["planner_execution_mode"] == (
        "deterministic_local"
    )
    assert result["simulation"]["recommended_action"] == "apply_patch"
    assert result["apply_patch_only"]["mode"] == "patch_only"
    assert result["apply_patch_only"]["applied"] is False
    assert result["planner_status"] == "patch_only_completed"


def test_run_probe_reuses_git_prepass_cache_for_hot_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = _typescript_rootdir_repo(tmp_path)
    _init_git_repo(repo_path)
    runtime_dir = tmp_path / "runtime"
    command_calls = 0
    graph_calls = 0
    original_run_command = probe_module._run_command
    original_build_connected_dependency_map = probe_module._build_connected_dependency_map

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _probe_envelope(), {"execution_ms": 9}

    def _counting_run_command(repo_path: Path, command: str) -> dict[str, object]:
        nonlocal command_calls
        command_calls += 1
        return original_run_command(repo_path, command)

    def _counting_build_connected_dependency_map(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal graph_calls
        graph_calls += 1
        return original_build_connected_dependency_map(*args, **kwargs)

    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
        ),
    )
    monkeypatch.setattr(probe_module, "_run_command", _counting_run_command)
    monkeypatch.setattr(
        probe_module,
        "_build_connected_dependency_map",
        _counting_build_connected_dependency_map,
    )

    first = run_probe(
        repo_path=repo_path,
        focus_paths=["services/app"],
        diagnostic_command="cat diagnostics.txt # pnpm exec tsc -p tsconfig.test.json --noEmit",
        diagnostic_base_path="services/app",
        planner_model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        runtime_dir=runtime_dir,
        reuse_existing_state=False,
        max_files=256,
        max_file_size_bytes=100_000,
        max_total_bytes=2_000_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )
    second = run_probe(
        repo_path=repo_path,
        focus_paths=["services/app"],
        diagnostic_command="cat diagnostics.txt # pnpm exec tsc -p tsconfig.test.json --noEmit",
        diagnostic_base_path="services/app",
        planner_model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        runtime_dir=runtime_dir,
        reuse_existing_state=True,
        max_files=256,
        max_file_size_bytes=100_000,
        max_total_bytes=2_000_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert first["prepass"]["cache_status"] == "miss_stored"
    assert second["prepass"]["cache_status"] == "hit"
    assert second["snapshot"]["status"] == "existing"
    assert second["graph_query"]["top_change_risk_files"]
    assert second["diagnostic_command"]["elapsed_ms"] == 0.0
    assert second["diagnostic_command"]["cached_elapsed_ms"] is not None
    assert command_calls == 1
    assert graph_calls == 1


