"""Tests for repository_intelligence_service: repository_intelligence_j.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_intelligence_julia_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/Helper.jl"

    monkeypatch.setattr(repository_service.julia_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"src/Helper.jl": "src/Helper.jl"}

    result = repository_service._resolve_julia_import(
        current_file="src/Acme.jl",
        import_target=".Helper",
        module_index=module_index,
    )

    assert result == "src/Helper.jl"
    assert observed["current_file"] == "src/Acme.jl"
    assert observed["import_target"] == ".Helper"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_julia_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return ()

    monkeypatch.setattr(
        repository_service.julia_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/Helper.jl": "src/Helper.jl"}

    result = repository_service._parse_julia_dependencies_only(
        "src/Acme.jl",
        'include("Helper.jl")',
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/Acme.jl"
    assert observed["text"] == 'include("Helper.jl")'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_julia_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.julia_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/Helper.jl": "src/Helper.jl"}

    result = repository_service._parse_julia_file(
        "src/Acme.jl",
        'include("Helper.jl")',
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/Acme.jl"
    assert observed["text"] == 'include("Helper.jl")'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_nim_helpers_are_modularized() -> None:
    assert repository_service._NIM_IMPORT_LINE_RE is repository_service.nim_adapter.IMPORT_LINE_RE
    assert repository_service._is_nim_declared_symbol_alias is (
        repository_service.nim_adapter.is_declared_symbol_alias
    )
    assert repository_service._nim_module_aliases_for_path is (
        repository_service.nim_adapter.module_aliases_for_path
    )


def test_repository_intelligence_nim_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/acme/util.nim"

    monkeypatch.setattr(repository_service.nim_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"src/acme/util.nim": "src/acme/util.nim"}

    result = repository_service._resolve_nim_import(
        current_file="src/acme.nim",
        import_target="acme/util",
        module_index=module_index,
    )

    assert result == "src/acme/util.nim"
    assert observed["current_file"] == "src/acme.nim"
    assert observed["import_target"] == "acme/util"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_nim_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
        module_index_aliases_for_file: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["module_index_aliases_for_file"] = module_index_aliases_for_file
        return ()

    monkeypatch.setattr(
        repository_service.nim_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/acme/util.nim": "src/acme/util.nim"}

    result = repository_service._parse_nim_dependencies_only(
        "src/acme.nim",
        "import acme/util",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/acme.nim"
    assert observed["text"] == "import acme/util"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match
    assert observed["module_index_aliases_for_file"] is (
        repository_service._module_index_aliases_for_file
    )


def test_repository_intelligence_nim_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
        module_index_aliases_for_file: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["module_index_aliases_for_file"] = module_index_aliases_for_file
        return (), (), ()

    monkeypatch.setattr(repository_service.nim_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/acme/util.nim": "src/acme/util.nim"}

    result = repository_service._parse_nim_file(
        "src/acme.nim",
        "import acme/util",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/acme.nim"
    assert observed["text"] == "import acme/util"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match
    assert observed["module_index_aliases_for_file"] is (
        repository_service._module_index_aliases_for_file
    )


@pytest.mark.anyio
async def test_repository_intelligence_decision_plan_workflow_wrappers_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SimpleNamespace(id="repo-1", org_id="org-1")
    request = RepositoryDecisionPlanCreateRequest(
        workspace_evidence_bundle_ref="bundle-1",
        snapshot_id="snapshot-1",
    )
    result = object()
    observed: dict[str, dict[str, Any]] = {}

    async def _fake_create_repository_decision_plan(**kwargs: Any) -> object:
        observed["create"] = kwargs
        return result

    monkeypatch.setattr(
        repository_decision_plan_workflow,
        "create_repository_decision_plan",
        _fake_create_repository_decision_plan,
    )

    assert (
        await repository_service.create_repository_decision_plan(
            connector=connector,
            request=request,
        )
        is result
    )
    assert observed["create"]["connector"] is connector
    assert observed["create"]["request"] is request
    assert (
        observed["create"]["engine_revision"]
        == repository_service._REPOSITORY_INTELLIGENCE_ENGINE_REVISION
    )
    assert (
        observed["create"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert (
        observed["create"]["resolve_repository_model"] is repository_service._resolve_repository_model
    )
    assert observed["create"]["read_json"] is repository_service._read_json
    assert (
        observed["create"]["generate_repository_patch_plan"]
        is repository_service._generate_repository_patch_plan
    )
    assert (
        observed["create"]["validate_patch_against_snapshot"]
        is repository_service._validate_patch_against_snapshot
    )
    assert observed["create"]["patch_impact_summary"] is repository_service._patch_impact_summary


@pytest.mark.anyio
async def test_repository_intelligence_execution_workflow_wrappers_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SimpleNamespace(id="repo-1", org_id="org-1")
    simulation_request = RepositorySimulationRequest(
        snapshot_id="snapshot-1",
        decision_plan_id="plan-1",
    )
    apply_request = RepositoryApplyRequest(
        snapshot_id="snapshot-1",
        decision_plan_id="plan-1",
        simulation_id="simulation-1",
        mode=RepositoryApplyMode.PATCH_ONLY,
    )
    simulation_result = object()
    apply_result = object()
    observed: dict[str, dict[str, Any]] = {}

    async def _fake_simulate_repository_decision(**kwargs: Any) -> object:
        observed["simulate"] = kwargs
        return simulation_result

    async def _fake_apply_repository_decision(**kwargs: Any) -> object:
        observed["apply"] = kwargs
        return apply_result

    monkeypatch.setattr(
        repository_execution_workflow,
        "simulate_repository_decision",
        _fake_simulate_repository_decision,
    )
    monkeypatch.setattr(
        repository_execution_workflow,
        "apply_repository_decision",
        _fake_apply_repository_decision,
    )

    assert (
        await repository_service.simulate_repository_decision(
            connector=connector,
            request=simulation_request,
        )
        is simulation_result
    )
    assert observed["simulate"]["connector"] is connector
    assert observed["simulate"]["request"] is simulation_request
    assert (
        observed["simulate"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert observed["simulate"]["get_policy"] is repository_service.get_policy
    assert (
        observed["simulate"]["load_decision_plan_manifest"]
        is repository_service._load_decision_plan_manifest
    )
    assert observed["simulate"]["simulation_lookup_key"] is repository_service._simulation_lookup_key
    assert observed["simulate"]["read_json"] is repository_service._read_json
    assert observed["simulate"]["run_simulation_fast"] is repository_service.run_simulation_fast
    assert observed["simulate"]["stable_identifier"] is repository_service._stable_identifier

    assert (
        await repository_service.apply_repository_decision(
            connector=connector,
            request=apply_request,
        )
        is apply_result
    )
    assert observed["apply"]["connector"] is connector
    assert observed["apply"]["request"] is apply_request
    assert (
        observed["apply"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert observed["apply"]["parse_connector_config"] is repository_service._parse_connector_config
    assert (
        observed["apply"]["load_decision_plan_manifest"]
        is repository_service._load_decision_plan_manifest
    )
    assert observed["apply"]["load_simulation_manifest"] is repository_service._load_simulation_manifest
    assert observed["apply"]["patch_changed_files"] is repository_service._patch_changed_files
    assert observed["apply"]["resolved_repository_source"] is repository_service.resolved_repository_source
    assert observed["apply"]["git_command"] is repository_service._git_command
    assert observed["apply"]["repository_url"] is repository_service._repository_url
    assert (
        observed["apply"]["authenticated_repository_url"]
        is repository_service._authenticated_repository_url
    )
    assert observed["apply"]["repo_access_token"] is repository_service._repo_access_token
    assert observed["apply"]["stable_identifier"] is repository_service._stable_identifier


