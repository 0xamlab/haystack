"""Tests for repository_intelligence_service: repository_simulation.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_repository_simulation_existing_lookup_skips_resimulation(
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
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )
    first = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            snapshot_id=snapshot.snapshot_id,
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )

    async def _unexpected_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("simulation fast path should reuse the persisted envelope")

    monkeypatch.setattr(repository_service, "run_simulation_fast", _unexpected_run_simulation_fast)
    simulation_id = str(first.validated_inputs["simulation_id"])
    simulation_path = repository_service._simulations_dir(
        str(connector.org_id),
        str(connector.id),
    ) / f"{simulation_id}.json"
    original_read_json = repository_service._read_json

    def _read_json_without_simulation_manifest(path: Path) -> dict[str, Any]:
        if Path(path) == simulation_path:
            raise AssertionError("simulation fast path should not reopen the simulation manifest")
        return original_read_json(path)

    monkeypatch.setattr(repository_service, "_read_json", _read_json_without_simulation_manifest)
    second = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )

    assert second.run_id == first.run_id
    assert second.recommended_action == first.recommended_action
    assert second.score_breakdown == first.score_breakdown


@pytest.mark.anyio
async def test_repository_simulation_uses_decision_plan_snapshot_when_omitted(
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

    assert envelope.validated_inputs["snapshot_id"] == snapshot.snapshot_id


@pytest.mark.anyio
async def test_repository_simulation_snapshot_mismatch_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    first_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=first_snapshot.snapshot_id,
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
    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )
    (repo_path / "src" / "service.py").write_text(
        "def normalize_status(status: str) -> str:\n"
        "    lowered = status.strip().lower()\n"
        '    if lowered == "open":\n'
        '        return "pending"\n'
        "    return lowered\n",
        encoding="utf-8",
    )
    second_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    with pytest.raises(repository_service.RepositoryIntelligenceError) as excinfo:
        await repository_service.simulate_repository_decision(
            connector=connector,
            request=RepositorySimulationRequest(
                snapshot_id=second_snapshot.snapshot_id,
                decision_plan_id=decision_plan.decision_plan_id,
            ),
        )

    assert excinfo.value.code == "repository_simulation_snapshot_mismatch"


@pytest.mark.anyio
async def test_repository_simulation_persists_risk_inputs_and_logs_final_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    logged: list[tuple[str, dict[str, Any]]] = []

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
        envelope = _decision_envelope()
        envelope.recommended_action = "reject"
        return envelope, {"execution_ms": 11}

    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
        ),
    )
    monkeypatch.setattr(
        repository_execution_workflow.logger,
        "info",
        lambda event, **kwargs: logged.append((event, kwargs)),
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )
    envelope = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            snapshot_id=snapshot.snapshot_id,
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )

    simulation_id = str(envelope.validated_inputs["simulation_id"])
    simulation_manifest = repository_service._read_json(
        repository_service._simulations_dir(str(connector.org_id), str(connector.id))
        / f"{simulation_id}.json"
    )
    repository_log = next(
        kwargs["extra"]
        for event, kwargs in logged
        if event == "simulation_computed"
        and kwargs.get("extra", {}).get("action_scope") == "repository_apply_gate"
    )

    assert envelope.recommended_action == "apply_patch"
    assert simulation_manifest["simulation_request"]["runs"] >= 1_000
    assert simulation_manifest["simulation_request"]["seed"] == 42
    assert simulation_manifest["simulation_request"]["objective_function"]
    assert (
        envelope.score_breakdown["risk_input_summary"]["objective_function"]
        == simulation_manifest["simulation_request"]["objective_function"]
    )
    assert isinstance(envelope.score_breakdown["patch_impact"]["risk_adjustments"], list)
    assert repository_log["repository_id"] == str(connector.id)
    assert repository_log["simulation_id"] == simulation_id
    assert repository_log["raw_recommended_action"] == "reject"
    assert repository_log["final_recommended_action"] == "apply_patch"
