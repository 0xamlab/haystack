"""Tests for repository_intelligence_service: repository_apply.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_repository_apply_patch_only_bypasses_failed_apply_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "handle_request crashes when user is null",
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 2,
                        "severity": "error",
                        "message": "AttributeError: 'NoneType' object has no attribute 'name'",
                    }
                ],
            },
        ),
    )

    source_path = repo_path / "src" / "service.py"
    old_text = source_path.read_text(encoding="utf-8")
    new_text = (
        "def handle_request(user):\n"
        "    if user is None:\n"
        '        return "anonymous"\n'
        "    return user.name\n"
    )
    patch_diff = "".join(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile="a/src/service.py",
            tofile="b/src/service.py",
        )
    )

    async def _fake_generate_repository_patch_plan(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "root_cause": "handle_request dereferences user.name without a null guard.",
            "planner_model_id": "repo-fix-model",
            "planner_execution_mode": "provider_backed_chat",
            "planner_provider_backend": "openai",
            "candidate_fixes": ["Add a null guard before returning user.name."],
            "recommended_action": "Add null guard in handle_request",
            "rationale": "The failing path is isolated to src/service.py and the patch is localized.",
            "confidence": 0.61,
            "patch_diff": patch_diff,
        }

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _decision_envelope(), {"execution_ms": 11}

    monkeypatch.setattr(
        repository_service, "_resolve_repository_model", lambda _model: "repo-fix-model"
    )
    monkeypatch.setattr(
        repository_service,
        "_generate_repository_patch_plan",
        _fake_generate_repository_patch_plan,
    )
    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.99, risk_floor=5.0
        ),
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
        ),
    )
    envelope = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )
    simulation_id = str(envelope.validated_inputs["simulation_id"])
    applied = await repository_service.apply_repository_decision(
        connector=connector,
        request=RepositoryApplyRequest(
            decision_plan_id=decision_plan.decision_plan_id,
            simulation_id=simulation_id,
            mode=RepositoryApplyMode.PATCH_ONLY,
        ),
    )

    assert envelope.recommended_action == "hold_patch"
    assert applied.applied is False
    assert applied.mode == RepositoryApplyMode.PATCH_ONLY
    assert applied.apply_gate["passed"] is False
    assert "anonymous" in applied.patch


@pytest.mark.anyio
async def test_repository_apply_snapshot_mismatch_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN inputs."
                ),
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                    }
                ],
            },
        ),
    )

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _decision_envelope(), {"execution_ms": 11}

    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
        ),
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )
    envelope = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )
    simulation_id = str(envelope.validated_inputs["simulation_id"])

    with pytest.raises(repository_service.RepositoryIntelligenceError) as excinfo:
        await repository_service.apply_repository_decision(
            connector=connector,
            request=RepositoryApplyRequest(
                snapshot_id="snapshot_conflict",
                decision_plan_id=decision_plan.decision_plan_id,
                simulation_id=simulation_id,
                mode=RepositoryApplyMode.PATCH_ONLY,
            ),
        )

    assert excinfo.value.code == "repository_apply_requested_snapshot_mismatch"


