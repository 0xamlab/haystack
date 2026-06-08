from __future__ import annotations

from benchmarks.repository_intelligence_benchmark import BENCHMARK_CLASS, run_benchmark


def test_repository_intelligence_benchmark_reports_expected_shape() -> None:
    results = run_benchmark(iterations=1, warmup=0)

    assert results["benchmark"] == "repository_intelligence_benchmark"
    assert results["benchmark_class"] == BENCHMARK_CLASS
    assert results["iterations"] == 1
    assert results["warmup_iterations"] == 0
    assert results["repository_fixture"] == {
        "connector_type": "local_repo",
        "primary_language": "python",
        "file_count": 7,
        "control_plane_mode": "deterministic_stub",
        "workflow": (
            "snapshot -> triage -> decision_plan -> patch_impact -> simulate -> "
            "apply_patch_only -> apply_local_branch"
        ),
    }

    for stage_name in (
        "cold_snapshot",
        "existing_snapshot_hit",
        "triage",
        "decision_plan",
        "simulation",
        "apply_patch_only",
        "apply_local_branch",
        "changed_snapshot_refresh",
    ):
        stage = results["stages"][stage_name]
        assert stage["min_ms"] >= 0.0
        assert stage["p50_ms"] >= stage["min_ms"]
        assert stage["p99_ms"] <= stage["max_ms"]

    reduction = results["token_reduction"]
    assert reduction["raw_repo_token_estimate"]["mean"] > 0.0
    assert reduction["evidence_bundle_token_count"]["mean"] > 0.0
    assert reduction["saved_tokens"]["mean"] > 0.0
    assert reduction["reduction_ratio"]["mean"] >= 1.0

    patch_impact = results["patch_impact"]
    assert 0.0 < patch_impact["patch_impact_risk_score"]["mean"] < 1.0
    assert patch_impact["dependency_fanout"]["mean"] >= 1.0
    assert patch_impact["api_break_candidates"]["mean"] >= 0.0
    assert patch_impact["likely_failing_tests"]["mean"] >= 1.0
    assert patch_impact["blast_radius_counts"] == {"low": 1}
    assert patch_impact["rollback_complexity_counts"] == {"low": 1}

    apply_gate = results["apply_gate"]
    assert apply_gate["passed_runs"] == 1
    assert apply_gate["blocked_runs"] == 0
    assert apply_gate["recommended_actions"] == {"apply_patch": 1}
