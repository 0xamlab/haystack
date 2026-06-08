from __future__ import annotations

import argparse
import asyncio
import contextlib
import difflib
import json
import os
import statistics
import tempfile
import time
import uuid
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from apps.api_server.schemas.repositories import (
    RepositoryApplyMode,
    RepositoryApplyRequest,
    RepositoryDecisionPlanCreateRequest,
    RepositorySimulationRequest,
    RepositorySnapshotCreateRequest,
    RepositoryTriageRequest,
)
from apps.api_server.schemas.response import (
    DecisionEnvelope,
    MetricsSummary,
    PercentileSummary,
    RunMetadata,
)
from apps.api_server.services import repository_intelligence as repository_service

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "repository_intelligence_benchmark.json"
BENCHMARK_CLASS = "B10"
DEFAULT_ITERATIONS = 5
DEFAULT_WARMUP = 1
_ORG_ID = uuid.uuid5(uuid.NAMESPACE_URL, "algenta-repository-intelligence-benchmark-org")
_ROOT_CONNECTOR_ID = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "algenta-repository-intelligence-benchmark-connector",
)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = int(percentile * (len(ordered) - 1))
    return ordered[index]


def _summarize_timings(samples_ns: list[int]) -> dict[str, float]:
    samples_ms = [sample / 1_000_000.0 for sample in samples_ns]
    return {
        "mean_ms": statistics.mean(samples_ms),
        "min_ms": min(samples_ms),
        "max_ms": max(samples_ms),
        "p50_ms": _percentile(samples_ms, 0.50),
        "p90_ms": _percentile(samples_ms, 0.90),
        "p95_ms": _percentile(samples_ms, 0.95),
        "p99_ms": _percentile(samples_ms, 0.99),
    }


def _summarize_numeric(samples: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(samples),
        "min": min(samples),
        "max": max(samples),
        "p50": _percentile(samples, 0.50),
        "p90": _percentile(samples, 0.90),
        "p95": _percentile(samples, 0.95),
        "p99": _percentile(samples, 0.99),
    }


def _decision_envelope() -> DecisionEnvelope:
    return DecisionEnvelope(
        run_id=uuid.uuid5(uuid.NAMESPACE_URL, "algenta-repository-intelligence-benchmark-run"),
        engine_version="2026.05.0",
        recommended_action="apply_patch",
        confidence=0.92,
        rationale="Deterministic local benchmark simulation satisfied policy thresholds.",
        metrics=MetricsSummary(
            expected_value=88.0,
            median=84.0,
            std_deviation=8.0,
            variance=64.0,
            probability_of_loss=0.07,
            var_95=11.0,
            cvar_95=13.0,
        ),
        percentiles=PercentileSummary(
            p5=-11.0,
            p25=63.0,
            p50=84.0,
            p75=97.0,
            p95=109.0,
        ),
        scenarios_run=5_000,
        execution_ms=9,
        metadata=RunMetadata(
            mode="expert",
            seed=42,
            billing_units=1,
            engine_version="2026.05.0",
        ),
    )


def _connector_for_repo(repo_path: Path, *, iteration: int) -> SimpleNamespace:
    connector_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"{_ROOT_CONNECTOR_ID}-iteration-{iteration}",
    )
    return SimpleNamespace(
        id=connector_id,
        org_id=_ORG_ID,
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )


def _write_sample_repository(repo_path: Path) -> int:
    (repo_path / "src").mkdir(parents=True, exist_ok=True)
    (repo_path / "tests").mkdir(parents=True, exist_ok=True)
    (repo_path / "docs").mkdir(parents=True, exist_ok=True)
    (repo_path / "src" / "service.py").write_text(
        "def normalize_status(status: str) -> str:\n"
        "    lowered = status.strip().lower()\n"
        '    if lowered == "open":\n'
        '        return "closed"\n'
        "    return lowered\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "api.py").write_text(
        "from src.service import normalize_status\n\n\n"
        "def render_status(payload: dict[str, str]) -> str:\n"
        '    return normalize_status(payload["status"])\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "catalog.py").write_text(
        "STATUS_LABELS = {\n"
        '    "open": "Open order awaiting fulfillment",\n'
        '    "closed": "Closed order with no further changes expected",\n'
        '    "pending": "Pending order awaiting approval",\n'
        '    "cancelled": "Cancelled order removed from processing",\n'
        '    "escalated": "Escalated order requires operator review",\n'
        "}\n\n"
        "def describe_status(name: str) -> str:\n"
        '    return STATUS_LABELS.get(name, "Unknown order status")\n\n'
        "def ordered_status_labels() -> list[str]:\n"
        "    return [\n"
        "        describe_status(\"open\"),\n"
        "        describe_status(\"closed\"),\n"
        "        describe_status(\"pending\"),\n"
        "        describe_status(\"cancelled\"),\n"
        "        describe_status(\"escalated\"),\n"
        "    ]\n\n"
        "# Benchmark token inventory padding for raw repository size.\n"
        "STATUS_RUNBOOK_NOTES = [\n"
        '    "Normalize status values before they reach downstream APIs.",\n'
        '    "OPEN must remain open after normalization to preserve contracts.",\n'
        '    "Closed and cancelled values are irreversible terminal states.",\n'
        '    "Escalated values require synchronous operator follow-up.",\n'
        '    "Pending values must be revisited after approval workflows finish.",\n'
        '    "Status renderers must stay consistent with service-level normalization.",\n'
        '    "Repository benchmark fixtures keep this file large on purpose.",\n'
        "]\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "test_service.py").write_text(
        "from src.service import normalize_status\n\n\n"
        "def test_normalize_status_open() -> None:\n"
        '    assert normalize_status("OPEN") == "open"\n',
        encoding="utf-8",
    )
    (repo_path / "tests" / "test_api.py").write_text(
        "from src.api import render_status\n\n\n"
        "def test_render_status_open() -> None:\n"
        '    assert render_status({"status": "OPEN"}) == "open"\n',
        encoding="utf-8",
    )
    (repo_path / "README.md").write_text(
        "# Customer Repository\n\n"
        "This deterministic fixture exercises Algenta Repository Intelligence "
        "for repository benchmark proof.\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "runbook.md").write_text(
        "# Runbook\n\n"
        "normalize_status should never map OPEN to closed.\n",
        encoding="utf-8",
    )
    return 7


def _snapshot_request() -> RepositorySnapshotCreateRequest:
    return RepositorySnapshotCreateRequest(
        include_patterns=["src/**", "tests/**", "docs/**", "README.md"],
        exclude_patterns=["**/__pycache__/**"],
        max_files=128,
        max_file_size_bytes=100_000,
    )


def _triage_request(snapshot_id: str) -> RepositoryTriageRequest:
    return RepositoryTriageRequest(
        snapshot_id=snapshot_id,
        max_evidence_items=1,
        max_snippet_lines=5,
        token_budget=256,
        signals={
            "issue_text": (
                "Production regression: normalize_status returns closed for OPEN "
                "inputs after the latest deploy."
            ),
            "diagnostics": [
                {
                    "path": "src/service.py",
                    "line": 4,
                    "severity": "error",
                    "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                }
            ],
            "failing_tests": [
                "tests/test_service.py::test_normalize_status_open",
                "tests/test_api.py::test_render_status_open",
            ],
            "changed_files": ["src/service.py"],
            "workspace_context": [
                "incident/normalize-status-regression",
                "jira/REPO-1842",
                "runbook/normalize-status",
            ],
        },
    )


def _repository_patch_diff(repo_path: Path) -> str:
    source_path = repo_path / "src" / "service.py"
    old_text = source_path.read_text(encoding="utf-8")
    new_text = (
        "def normalize_status(status: str) -> str:\n"
        "    lowered = status.strip().lower()\n"
        '    if lowered == "open":\n'
        '        return "open"\n'
        "    return lowered\n"
    )
    return "".join(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile="a/src/service.py",
            tofile="b/src/service.py",
        )
    )


@contextlib.contextmanager
def _temporary_runtime_dir(path: Path) -> Iterator[None]:
    original = os.environ.get("ALGENTA_RUNTIME_DIR")
    os.environ["ALGENTA_RUNTIME_DIR"] = str(path)
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("ALGENTA_RUNTIME_DIR", None)
        else:
            os.environ["ALGENTA_RUNTIME_DIR"] = original


@contextlib.contextmanager
def _patched_repository_dependencies(patch_diff: str) -> Iterator[None]:
    original_resolve_repository_model = repository_service._resolve_repository_model
    original_generate_repository_patch_plan = repository_service._generate_repository_patch_plan
    original_run_simulation_fast = repository_service.run_simulation_fast
    original_get_policy = repository_service.get_policy

    async def _fake_generate_repository_patch_plan(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        return {
            "root_cause": "normalize_status maps the OPEN status to the wrong value.",
            "candidate_fixes": [
                "Return 'open' when the lowered status is 'open'.",
                "Keep downstream API consumers aligned with the normalized status contract.",
            ],
            "recommended_action": "Fix normalize_status OPEN handling",
            "rationale": (
                "The bounded workspace evidence bundle localizes the regression to "
                "src/service.py and the patch is isolated to one file."
            ),
            "confidence": 0.91,
            "patch_diff": patch_diff,
        }

    async def _fake_run_simulation_fast(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[DecisionEnvelope, dict[str, Any]]:
        del args, kwargs
        return _decision_envelope(), {"execution_ms": 9}

    repository_service._resolve_repository_model = lambda _model: "repo-benchmark-model"
    repository_service._generate_repository_patch_plan = _fake_generate_repository_patch_plan
    repository_service.run_simulation_fast = _fake_run_simulation_fast
    repository_service.get_policy = lambda _org_id: SimpleNamespace(  # type: ignore[assignment]
        snapshot_id="policy-benchmark",
        min_confidence=0.8,
        risk_floor=20.0,
    )
    try:
        yield
    finally:
        repository_service._resolve_repository_model = original_resolve_repository_model
        repository_service._generate_repository_patch_plan = original_generate_repository_patch_plan
        repository_service.run_simulation_fast = original_run_simulation_fast
        repository_service.get_policy = original_get_policy


async def _run_iteration(*, iteration: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"algenta-repo-benchmark-{iteration}-") as temp_dir:
        root = Path(temp_dir)
        repo_path = root / "customer-repo"
        runtime_dir = root / "runtime"
        file_count = _write_sample_repository(repo_path)
        connector = _connector_for_repo(repo_path, iteration=iteration)
        snapshot_request = _snapshot_request()
        patch_diff = _repository_patch_diff(repo_path)

        with _temporary_runtime_dir(runtime_dir), _patched_repository_dependencies(patch_diff):
            snapshot_start = time.perf_counter_ns()
            snapshot = repository_service.create_repository_snapshot(
                connector=connector,
                request=snapshot_request,
            )
            cold_snapshot_ns = time.perf_counter_ns() - snapshot_start

            existing_start = time.perf_counter_ns()
            existing_snapshot = repository_service.create_repository_snapshot(
                connector=connector,
                request=snapshot_request,
            )
            existing_snapshot_ns = time.perf_counter_ns() - existing_start
            if existing_snapshot.status != "existing":
                raise RuntimeError("Repository snapshot benchmark expected an existing cache hit.")

            triage_start = time.perf_counter_ns()
            triage = repository_service.triage_repository(
                connector=connector,
                request=_triage_request(snapshot.snapshot_id),
            )
            triage_ns = time.perf_counter_ns() - triage_start

            decision_plan_start = time.perf_counter_ns()
            decision_plan = await repository_service.create_repository_decision_plan(
                connector=connector,
                request=RepositoryDecisionPlanCreateRequest(
                    snapshot_id=snapshot.snapshot_id,
                    workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
                ),
            )
            decision_plan_ns = time.perf_counter_ns() - decision_plan_start

            simulation_start = time.perf_counter_ns()
            simulation = await repository_service.simulate_repository_decision(
                connector=connector,
                request=RepositorySimulationRequest(
                    snapshot_id=snapshot.snapshot_id,
                    decision_plan_id=decision_plan.decision_plan_id,
                    runs=1_000,
                    seed=42,
                ),
            )
            simulation_ns = time.perf_counter_ns() - simulation_start

            simulation_id = str(simulation.validated_inputs["simulation_id"])
            apply_start = time.perf_counter_ns()
            apply_result = await repository_service.apply_repository_decision(
                connector=connector,
                request=RepositoryApplyRequest(
                    snapshot_id=snapshot.snapshot_id,
                    decision_plan_id=decision_plan.decision_plan_id,
                    simulation_id=simulation_id,
                    mode=RepositoryApplyMode.PATCH_ONLY,
                ),
            )
            apply_patch_only_ns = time.perf_counter_ns() - apply_start

            branch_name = f"algenta/repo-benchmark-{iteration if iteration >= 0 else 'warmup'}"
            apply_local_branch_start = time.perf_counter_ns()
            apply_local_branch_result = await repository_service.apply_repository_decision(
                connector=connector,
                request=RepositoryApplyRequest(
                    snapshot_id=snapshot.snapshot_id,
                    decision_plan_id=decision_plan.decision_plan_id,
                    simulation_id=simulation_id,
                    mode=RepositoryApplyMode.LOCAL_BRANCH,
                    write_permission=True,
                    branch_name=branch_name,
                ),
            )
            apply_local_branch_ns = time.perf_counter_ns() - apply_local_branch_start
            if apply_local_branch_result.mode is not RepositoryApplyMode.LOCAL_BRANCH:
                raise RuntimeError(
                    "Repository benchmark expected local_branch apply mode for branch writes."
                )
            if not apply_local_branch_result.applied:
                raise RuntimeError("Repository benchmark expected local_branch apply to succeed.")
            if apply_local_branch_result.branch_name != branch_name:
                raise RuntimeError(
                    "Repository benchmark local_branch apply returned an unexpected branch name."
                )
            if not apply_local_branch_result.commit_sha:
                raise RuntimeError(
                    "Repository benchmark local_branch apply did not return a commit SHA."
                )
            local_checkout_path = str(apply_local_branch_result.local_checkout_path or "")
            if Path(local_checkout_path).resolve() != repo_path.resolve():
                raise RuntimeError(
                    "Repository benchmark local_branch apply returned an unexpected checkout path."
                )
            current_branch = str(
                repository_service._git_command(
                    ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"]
                )
            ).strip()
            if current_branch != branch_name:
                raise RuntimeError(
                    "Repository benchmark local_branch apply did not switch the checkout branch."
                )
            service_source = (repo_path / "src" / "service.py").read_text(encoding="utf-8")
            if 'return "open"' not in service_source:
                raise RuntimeError(
                    "Repository benchmark local_branch apply did not materialize the patch."
                )

            readme_path = repo_path / "README.md"
            readme_path.write_text(
                readme_path.read_text(encoding="utf-8")
                + f"\nBenchmark iteration refresh marker: {iteration}\n",
                encoding="utf-8",
            )
            changed_snapshot_start = time.perf_counter_ns()
            changed_snapshot = repository_service.create_repository_snapshot(
                connector=connector,
                request=snapshot_request,
            )
            changed_snapshot_ns = time.perf_counter_ns() - changed_snapshot_start
            if changed_snapshot.snapshot_id == snapshot.snapshot_id:
                raise RuntimeError(
                    "Repository snapshot benchmark expected a new snapshot after repository change."
                )

        repository_analysis = decision_plan.decision_plan.repository_analysis
        if repository_analysis is None:
            raise RuntimeError("Repository benchmark expected repository analysis metadata.")
        apply_gate = dict(apply_result.apply_gate)
        return {
            "file_count": file_count,
            "cold_snapshot_ns": cold_snapshot_ns,
            "existing_snapshot_hit_ns": existing_snapshot_ns,
            "triage_ns": triage_ns,
            "decision_plan_ns": decision_plan_ns,
            "simulation_ns": simulation_ns,
            "apply_patch_only_ns": apply_patch_only_ns,
            "apply_local_branch_ns": apply_local_branch_ns,
            "changed_snapshot_refresh_ns": changed_snapshot_ns,
            "raw_repo_token_estimate": float(triage.raw_repo_token_estimate),
            "evidence_bundle_token_count": float(triage.evidence_bundle_token_count),
            "saved_tokens": float(
                triage.raw_repo_token_estimate - triage.evidence_bundle_token_count
            ),
            "reduction_ratio": float(triage.reduction_ratio),
            "patch_impact_risk_score": float(
                simulation.score_breakdown["repository_risk_score"]
            ),
            "dependency_fanout": float(
                simulation.score_breakdown["patch_impact"]["dependency_fanout"]
            ),
            "api_break_candidates": float(
                simulation.score_breakdown["patch_impact"]["api_break_candidates"]
            ),
            "likely_failing_tests": float(len(repository_analysis.likely_failing_tests)),
            "blast_radius": repository_analysis.blast_radius,
            "rollback_complexity": repository_analysis.rollback_complexity,
            "apply_gate_passed": bool(apply_gate["passed"]),
            "recommended_action": str(simulation.recommended_action),
        }


async def _run_async_benchmark(*, iterations: int, warmup: int) -> dict[str, Any]:
    for warmup_iteration in range(warmup):
        await _run_iteration(iteration=-(warmup_iteration + 1))

    results = [await _run_iteration(iteration=index) for index in range(iterations)]
    numeric_keys = (
        "raw_repo_token_estimate",
        "evidence_bundle_token_count",
        "saved_tokens",
        "reduction_ratio",
        "patch_impact_risk_score",
        "dependency_fanout",
        "api_break_candidates",
        "likely_failing_tests",
    )
    stages = {
        "cold_snapshot": _summarize_timings(
            [int(result["cold_snapshot_ns"]) for result in results]
        ),
        "existing_snapshot_hit": _summarize_timings(
            [int(result["existing_snapshot_hit_ns"]) for result in results]
        ),
        "triage": _summarize_timings([int(result["triage_ns"]) for result in results]),
        "decision_plan": _summarize_timings(
            [int(result["decision_plan_ns"]) for result in results]
        ),
        "simulation": _summarize_timings([int(result["simulation_ns"]) for result in results]),
        "apply_patch_only": _summarize_timings(
            [int(result["apply_patch_only_ns"]) for result in results]
        ),
        "apply_local_branch": _summarize_timings(
            [int(result["apply_local_branch_ns"]) for result in results]
        ),
        "changed_snapshot_refresh": _summarize_timings(
            [int(result["changed_snapshot_refresh_ns"]) for result in results]
        ),
    }
    token_reduction = {
        key: _summarize_numeric([float(result[key]) for result in results])
        for key in numeric_keys[:4]
    }
    patch_impact = {
        key: _summarize_numeric([float(result[key]) for result in results])
        for key in numeric_keys[4:]
    }
    patch_impact["blast_radius_counts"] = dict(
        sorted(Counter(str(result["blast_radius"]) for result in results).items())
    )
    patch_impact["rollback_complexity_counts"] = dict(
        sorted(Counter(str(result["rollback_complexity"]) for result in results).items())
    )
    recommended_actions = dict(
        sorted(Counter(str(result["recommended_action"]) for result in results).items())
    )
    return {
        "benchmark": "repository_intelligence_benchmark",
        "benchmark_class": BENCHMARK_CLASS,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "iterations": iterations,
        "warmup_iterations": warmup,
        "repository_fixture": {
            "connector_type": "local_repo",
            "primary_language": "python",
            "file_count": int(results[0]["file_count"]),
            "control_plane_mode": "deterministic_stub",
            "workflow": (
                "snapshot -> triage -> decision_plan -> patch_impact -> simulate -> "
                "apply_patch_only -> apply_local_branch"
            ),
        },
        "stages": stages,
        "token_reduction": token_reduction,
        "patch_impact": patch_impact,
        "apply_gate": {
            "passed_runs": sum(1 for result in results if bool(result["apply_gate_passed"])),
            "blocked_runs": sum(1 for result in results if not bool(result["apply_gate_passed"])),
            "recommended_actions": recommended_actions,
        },
    }


def run_benchmark(
    *,
    iterations: int = DEFAULT_ITERATIONS,
    warmup: int = DEFAULT_WARMUP,
) -> dict[str, Any]:
    if iterations <= 0:
        raise ValueError("iterations must be greater than 0.")
    if warmup < 0:
        raise ValueError("warmup must be greater than or equal to 0.")
    return asyncio.run(_run_async_benchmark(iterations=iterations, warmup=warmup))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark the deterministic local Algenta Repository Intelligence "
            "workflow for repository snapshot, triage, plan, simulation, and apply gating."
        )
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="Number of measured repository workflow runs.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=DEFAULT_WARMUP,
        help="Number of warmup runs to execute before measurement.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the benchmark JSON artifact.",
    )
    args = parser.parse_args()

    results = run_benchmark(iterations=args.iterations, warmup=args.warmup)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
