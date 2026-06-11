"""Tests for repository_intelligence_service: repository_decision.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from apps.api_server.services import repository_intelligence_telemetry as telemetry
from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_repository_decision_plan_uses_deterministic_local_model(
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
                "failing_tests": ["tests/test_service.py::test_normalize_status_open"],
                "changed_files": ["src/service.py"],
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
    envelope = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            snapshot_id=snapshot.snapshot_id,
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )
    simulation_id = str(envelope.validated_inputs["simulation_id"])
    applied = await repository_service.apply_repository_decision(
        connector=connector,
        request=RepositoryApplyRequest(
            snapshot_id=snapshot.snapshot_id,
            decision_plan_id=decision_plan.decision_plan_id,
            simulation_id=simulation_id,
            mode=RepositoryApplyMode.LOCAL_BRANCH,
            write_permission=True,
            branch_name="algenta/test-open-fix",
        ),
    )

    current_branch = subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
        text=True,
    ).strip()
    repository_analysis = decision_plan.decision_plan.repository_analysis
    assert repository_analysis is not None
    assert repository_analysis.root_cause == (
        "normalize_status returns 'closed' instead of 'open' at src/service.py:4."
    )
    assert repository_analysis.planner_model_id == (
        repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID
    )
    assert repository_analysis.planner_execution_mode == "deterministic_local"
    assert repository_analysis.planner_provider_backend is None
    assert repository_analysis.generated_patch_ref is not None
    assert repository_analysis.patch_impact_report_ref is not None
    assert decision_plan.decision_plan.recommended_action == (
        "Correct normalize_status in src/service.py to return 'open'."
    )
    assert envelope.recommended_action == "apply_patch"
    assert applied.applied is True
    assert applied.commit_sha
    assert current_branch == "algenta/test-open-fix"
    assert 'return "open"' in (repo_path / "src" / "service.py").read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_repository_decision_plan_deterministic_local_model_fails_closed_when_unsupported(
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

    with pytest.raises(repository_service.RepositoryIntelligenceError) as excinfo:
        await repository_service.create_repository_decision_plan(
            connector=connector,
            request=RepositoryDecisionPlanCreateRequest(
                snapshot_id=snapshot.snapshot_id,
                workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
                model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
            ),
        )

    assert excinfo.value.code == "repository_local_planner_unsupported"


@pytest.mark.anyio
async def test_repository_decision_plan_deterministic_local_model_handles_ts6059_rootdir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_rootdir_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=[
                "services/app",
                "packages/common",
                "services/app/tsconfig.test.json",
                "services/app/tsconfig.json",
            ],
            include_patterns=["services/**/*.ts", "services/**/*.json", "packages/**/*.ts", "packages/**/*.json"],
        ),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "TypeScript test project fails with TS6059 rootDir drift.",
                "diagnostics": [
                    {
                        "path": "packages/common/src/shared.ts",
                        "line": 1,
                        "severity": "error",
                        "code": "TS6059",
                        "message": "File is not under 'rootDir' '/tmp/service'. 'rootDir' is expected to contain all source files.",
                    }
                ],
                "changed_files": ["packages/common/src/shared.ts"],
                "workspace_context": [
                    "command:cd services/app && pnpm exec tsc -p tsconfig.test.json --noEmit",
                    "diagnostic_base_path:services/app",
                    "tsconfig_project:services/app/tsconfig.test.json",
                ],
            },
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

    repository_analysis = decision_plan.decision_plan.repository_analysis
    assert repository_analysis is not None
    assert repository_analysis.planner_model_id == (
        repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID
    )
    assert repository_analysis.planner_execution_mode == "deterministic_local"
    assert repository_analysis.generated_patch_ref is not None
    assert repository_analysis.patch_impact_report_ref is not None
    assert "rootDir" in decision_plan.decision_plan.recommended_action

    plan_manifest = repository_service._load_decision_plan_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        decision_plan_id=decision_plan.decision_plan_id,
    )
    patch_text = Path(plan_manifest["patch_path"]).read_text(encoding="utf-8")
    assert "services/app/tsconfig.test.json" in patch_text
    assert '"rootDir": "../.."' in patch_text


@pytest.mark.anyio
async def test_repository_decision_plan_existing_lookup_skips_regeneration(
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
    first = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )

    async def _unexpected_generate_repository_patch_plan(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("decision-plan fast path should reuse the persisted plan")

    monkeypatch.setattr(
        repository_service,
        "_generate_repository_patch_plan",
        _unexpected_generate_repository_patch_plan,
    )
    plan_path = repository_service._decision_plans_dir(
        str(connector.org_id),
        str(connector.id),
    ) / f"{first.decision_plan_id}.json"
    original_read_json = repository_service._read_json

    def _read_json_without_plan_manifest(path: Path) -> dict[str, Any]:
        if Path(path) == plan_path:
            raise AssertionError("decision-plan fast path should not reopen the plan manifest")
        return original_read_json(path)

    monkeypatch.setattr(repository_service, "_read_json", _read_json_without_plan_manifest)
    second = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )

    assert second.decision_plan_id == first.decision_plan_id
    assert second.decision_plan == first.decision_plan


@pytest.mark.anyio
async def test_repository_decision_plan_uses_workspace_evidence_bundle_snapshot_when_omitted(
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

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )

    assert decision_plan.snapshot_id == snapshot.snapshot_id
    assert decision_plan.decision_plan.repository_analysis is not None


@pytest.mark.anyio
async def test_repository_decision_plan_workspace_evidence_bundle_snapshot_mismatch(
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
        await repository_service.create_repository_decision_plan(
            connector=connector,
            request=RepositoryDecisionPlanCreateRequest(
                snapshot_id=second_snapshot.snapshot_id,
                workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
                model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
            ),
        )

    assert excinfo.value.code == "repository_decision_plan_snapshot_mismatch"


@pytest.mark.anyio
async def test_repository_decision_plan_simulate_and_apply_local_branch(
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
        telemetry.record_tokens(
            input_uncached=900,
            input_cached_read=300,
            input_cached_write=50,
            output=120,
        )
        return {
            "root_cause": "handle_request dereferences user.name without a null guard.",
            "planner_model_id": "repo-fix-model",
            "planner_execution_mode": "provider_backed_chat",
            "planner_provider_backend": "openai",
            "candidate_fixes": ["Add a null guard before returning user.name."],
            "recommended_action": "Add null guard in handle_request",
            "rationale": "The failing path is isolated to src/service.py and the patch is localized.",
            "confidence": 0.89,
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
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
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
            snapshot_id=snapshot.snapshot_id,
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )
    simulation_id = str(envelope.validated_inputs["simulation_id"])
    applied = await repository_service.apply_repository_decision(
        connector=connector,
        request=RepositoryApplyRequest(
            snapshot_id=snapshot.snapshot_id,
            decision_plan_id=decision_plan.decision_plan_id,
            simulation_id=simulation_id,
            mode=RepositoryApplyMode.LOCAL_BRANCH,
            write_permission=True,
            branch_name="algenta/test-null-guard",
        ),
    )

    current_branch = subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
        text=True,
    ).strip()
    repository_analysis = decision_plan.decision_plan.repository_analysis
    assert repository_analysis is not None
    assert repository_analysis.generated_patch_ref is not None
    assert repository_analysis.planner_model_id == "repo-fix-model"
    assert repository_analysis.planner_execution_mode == "provider_backed_chat"
    assert repository_analysis.planner_provider_backend == "openai"
    assert decision_plan.planner_usage == {
        "input_tokens": 1250.0,
        "output_tokens": 120.0,
        "cache_read_tokens": 300.0,
        "cache_write_tokens": 50.0,
        "cost_usd": None,
    }
    assert envelope.recommended_action == "apply_patch"
    assert applied.applied is True
    assert applied.commit_sha
    assert current_branch == "algenta/test-null-guard"
    assert "anonymous" in source_path.read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_repository_decision_plan_surfaces_verified_agentic_usage_and_runtime_metadata(
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
                "issue_text": "normalize_status returns closed for open inputs",
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                    }
                ],
                "changed_files": ["src/service.py"],
            },
        ),
    )

    source_path = repo_path / "src" / "service.py"
    old_text = source_path.read_text(encoding="utf-8")
    new_text = old_text.replace('return "closed"', 'return "open"')
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
            "root_cause": "verified agent fixed the normalize_status literal mismatch.",
            "planner_model_id": repository_service._VERIFIED_AGENTIC_REPOSITORY_MODEL_ID,
            "planner_execution_mode": "verified_agentic",
            "planner_provider_backend": None,
            "candidate_fixes": ["Fix normalize_status literal"],
            "recommended_action": "Return open for OPEN inputs",
            "rationale": "Injected context was sufficient for the verified agent to patch directly.",
            "confidence": 0.91,
            "patch_diff": patch_diff,
            "planner_usage": {
                "input_tokens": 4200.0,
                "output_tokens": 210.0,
                "cache_read_tokens": 1600.0,
                "cache_write_tokens": 450.0,
                "cost_usd": None,
            },
            "agent_run_id": "agent_run_123",
            "session_id": "session_123",
            "runtime_kind": "cline",
            "runtime_provider": "anthropic",
            "runtime_model": "claude-sonnet-4-6",
            "planner_engine": "cline_fork",
        }

    monkeypatch.setattr(
        repository_service,
        "_resolve_repository_model",
        lambda _model: repository_service._VERIFIED_AGENTIC_REPOSITORY_MODEL_ID,
    )
    monkeypatch.setattr(
        repository_service,
        "_generate_repository_patch_plan",
        _fake_generate_repository_patch_plan,
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._VERIFIED_AGENTIC_REPOSITORY_MODEL_ID,
        ),
    )

    assert decision_plan.planner_usage == {
        "input_tokens": 4200.0,
        "output_tokens": 210.0,
        "cache_read_tokens": 1600.0,
        "cache_write_tokens": 450.0,
        "cost_usd": None,
    }
    assert decision_plan.agent_run_id == "agent_run_123"
    assert decision_plan.session_id == "session_123"
    assert decision_plan.runtime_kind == "cline"
    assert decision_plan.is_stub is None
    assert decision_plan.runtime_provider == "anthropic"
    assert decision_plan.runtime_model == "claude-sonnet-4-6"
