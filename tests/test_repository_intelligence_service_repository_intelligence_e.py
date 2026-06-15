"""Tests for repository_intelligence_service: repository_intelligence_e.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_intelligence_pascal_solidity_helpers_are_modularized() -> None:
    assert repository_service._normalize_pascal_target is (
        repository_pascal_solidity_dispatch._normalize_pascal_target
    )
    assert repository_service._collect_pascal_symbol_entries is (
        repository_pascal_solidity_dispatch._collect_pascal_symbol_entries
    )
    assert repository_service._resolve_pascal_target is (
        repository_pascal_solidity_dispatch._resolve_pascal_target
    )
    assert repository_service._parse_pascal_file is (
        repository_pascal_solidity_dispatch._parse_pascal_file
    )
    assert repository_service._resolve_solidity_import is (
        repository_pascal_solidity_dispatch._resolve_solidity_import
    )
    assert repository_service._parse_solidity_dependencies_only is (
        repository_pascal_solidity_dispatch._parse_solidity_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["pascal"] is (
        repository_pascal_solidity_dispatch._parse_pascal_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["delphi"] is (
        repository_pascal_solidity_dispatch._parse_delphi_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["delphi"] is (
        repository_pascal_solidity_dispatch._parse_delphi_file
    )
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["solidity"] is (
        repository_pascal_solidity_dispatch._parse_solidity_file
    )


def test_repository_intelligence_storage_helpers_are_modularized() -> None:
    assert repository_service._hash_file is repository_storage._hash_file
    assert repository_service._artifact_ref is repository_storage._artifact_ref
    assert repository_service._extract_tar_handle is repository_storage._extract_tar_handle
    assert repository_service._extract_tar is repository_storage._extract_tar
    assert repository_service._extract_zip is repository_storage._extract_zip
    assert repository_service._extract_archive is repository_storage._extract_archive
    assert repository_service._snapshot_paths is repository_storage._snapshot_paths
    assert repository_service.materialized_snapshot is repository_storage.materialized_snapshot
    assert repository_service._load_snapshot_manifest is repository_storage._load_snapshot_manifest
    assert repository_service._load_triage_manifest is repository_storage._load_triage_manifest
    assert repository_service._load_decision_plan_manifest is (
        repository_storage._load_decision_plan_manifest
    )
    assert repository_service._load_patch_impact_manifest is (
        repository_storage._load_patch_impact_manifest
    )
    assert repository_service._load_simulation_manifest is (
        repository_storage._load_simulation_manifest
    )


def test_repository_intelligence_snapshot_workflow_helpers_are_modularized() -> None:
    assert repository_service._snapshot_lookup_key is (
        repository_snapshot_workflow._snapshot_lookup_key
    )
    assert repository_service._snapshot_lookup_path is (
        repository_snapshot_workflow._snapshot_lookup_path
    )
    assert repository_service._create_source_archive is (
        repository_snapshot_workflow._create_source_archive
    )


def test_repository_intelligence_snapshot_workflow_wrappers_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SimpleNamespace(id="repo-1", org_id="org-1")
    request = RepositorySnapshotCreateRequest()
    snapshot_result = object()
    get_result = object()
    observed: dict[str, dict[str, Any]] = {}

    def _fake_create_repository_snapshot(**kwargs: Any) -> object:
        observed["create"] = kwargs
        return snapshot_result

    def _fake_get_repository_snapshot(**kwargs: Any) -> object:
        observed["get"] = kwargs
        return get_result

    monkeypatch.setattr(
        repository_snapshot_workflow,
        "create_repository_snapshot",
        _fake_create_repository_snapshot,
    )
    monkeypatch.setattr(
        repository_snapshot_workflow,
        "get_repository_snapshot",
        _fake_get_repository_snapshot,
    )

    assert (
        repository_service.create_repository_snapshot(
            connector=connector,
            request=request,
        )
        is snapshot_result
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
    assert observed["create"]["parse_connector_config"] is repository_service._parse_connector_config
    assert observed["create"]["resolved_repository_source"] is repository_service.resolved_repository_source
    assert (
        observed["create"]["compact_repository_focus_paths"]
        is repository_service._compact_repository_focus_paths
    )
    assert observed["create"]["iter_repository_files"] is repository_service._iter_repository_files
    assert observed["create"]["build_module_index"] is repository_service._build_module_index
    assert (
        observed["create"]["build_workspace_package_index"]
        is repository_service._build_workspace_package_index
    )
    assert (
        observed["create"]["build_workspace_go_module_index"]
        is repository_service._build_workspace_go_module_index
    )
    assert (
        observed["create"]["git_tracked_content_hashes"]
        is repository_service._git_tracked_content_hashes
    )
    assert (
        observed["create"]["file_analysis_context_hash"]
        is repository_service._file_analysis_context_hash
    )
    assert observed["create"]["analyze_snapshot_files"] is repository_service._analyze_snapshot_files
    assert (
        observed["create"]["augment_r_package_symbol_references"]
        is repository_service._augment_r_package_symbol_references
    )
    assert (
        observed["create"]["augment_julia_package_symbol_references"]
        is repository_service._augment_julia_package_symbol_references
    )
    assert (
        observed["create"]["resolve_symbol_reference_target"]
        is repository_service._resolve_symbol_reference_target
    )
    assert observed["create"]["hash_file"] is repository_service._hash_file
    assert observed["create"]["write_bytes_with_hash"] is repository_service._write_bytes_with_hash

    assert (
        repository_service.get_repository_snapshot(
            connector=connector,
            snapshot_id="snapshot-1",
        )
        is get_result
    )
    assert observed["get"]["connector"] is connector
    assert observed["get"]["snapshot_id"] == "snapshot-1"
    assert (
        observed["get"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert observed["get"]["load_snapshot_manifest"] is repository_service._load_snapshot_manifest


def test_repository_intelligence_graph_workflow_wrappers_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SimpleNamespace(id="repo-1", org_id="org-1")
    graph_request = repository_service.RepositoryGraphQueryRequest(
        snapshot_id="snapshot-1",
        file_path="src/service.py",
    )
    triage_request = RepositoryTriageRequest(
        snapshot_id="snapshot-1",
        signals={"issue_text": "service failure"},
    )
    query_result = object()
    triage_result = object()
    observed: dict[str, dict[str, Any]] = {}

    def _fake_query_repository_graph(**kwargs: Any) -> object:
        observed["query"] = kwargs
        return query_result

    def _fake_triage_repository(**kwargs: Any) -> object:
        observed["triage"] = kwargs
        return triage_result

    monkeypatch.setattr(
        repository_graph_workflow,
        "query_repository_graph",
        _fake_query_repository_graph,
    )
    monkeypatch.setattr(
        repository_graph_workflow,
        "triage_repository",
        _fake_triage_repository,
    )

    assert (
        repository_service.query_repository_graph(
            connector=connector,
            request=graph_request,
        )
        is query_result
    )
    assert observed["query"]["connector"] is connector
    assert observed["query"]["request"] is graph_request
    assert (
        observed["query"]["engine_revision"]
        == repository_service._REPOSITORY_INTELLIGENCE_ENGINE_REVISION
    )
    assert (
        observed["query"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert observed["query"]["load_snapshot_manifest"] is repository_service._load_snapshot_manifest
    assert observed["query"]["load_triage_manifest"] is repository_service._load_triage_manifest
    assert observed["query"]["read_json"] is repository_service._read_json

    assert (
        repository_service.triage_repository(
            connector=connector,
            request=triage_request,
        )
        is triage_result
    )
    assert observed["triage"]["connector"] is connector
    assert observed["triage"]["request"] is triage_request
    assert (
        observed["triage"]["engine_revision"]
        == repository_service._REPOSITORY_INTELLIGENCE_ENGINE_REVISION
    )
    assert (
        observed["triage"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert (
        observed["triage"]["load_snapshot_manifest"] is repository_service._load_snapshot_manifest
    )
    assert observed["triage"]["read_json"] is repository_service._read_json
    assert observed["triage"]["materialized_snapshot"] is repository_service.materialized_snapshot


def test_repository_intelligence_decision_plan_helpers_are_modularized() -> None:
    assert repository_service._decision_plan_lookup_key is (
        repository_decision_plan_workflow._decision_plan_lookup_key
    )
    assert repository_service._raise_local_planner_unsupported is (
        repository_planner_generation._raise_local_planner_unsupported
    )
    assert repository_service._extract_return_literal_mismatch is (
        repository_planner_generation._extract_return_literal_mismatch
    )
    assert repository_service._workspace_context_value is (
        repository_planner_generation._workspace_context_value
    )
    assert repository_service._position_to_offset is (
        repository_planner_generation._position_to_offset
    )
    assert repository_service._python_string_literal is (
        repository_planner_generation._python_string_literal
    )
    assert repository_service._extract_json_object is (
        repository_planner_generation._extract_json_object
    )
    assert repository_service._decision_plan_integrity is (
        repository_decision_plan_workflow._decision_plan_integrity
    )
    assert repository_service._option_risk is repository_decision_plan_workflow._option_risk


def test_repository_intelligence_patch_analysis_helpers_are_modularized() -> None:
    assert repository_service._patch_changed_files is (
        repository_patch_analysis._patch_changed_files
    )
    assert repository_service._top_level_service is repository_patch_analysis._top_level_service
    assert repository_service._is_test_path is repository_patch_analysis._is_test_path


def test_repository_intelligence_patch_analysis_test_path_cache_reuses_results() -> None:
    repository_patch_analysis._is_test_path.cache_clear()

    assert repository_patch_analysis._is_test_path("src/tests/sample_test.ml") is True
    assert repository_patch_analysis._is_test_path("src/tests/sample_test.ml") is True

    assert repository_patch_analysis._is_test_path.cache_info().hits >= 1


def test_repository_intelligence_patch_analysis_test_path_suffixes_cover_power_shell_and_erlang() -> None:
    assert repository_patch_analysis._is_test_path("scripts/build.spec.ps1") is True
    assert repository_patch_analysis._is_test_path("apps/demo/suite.erl") is True
    assert repository_patch_analysis._is_test_path("src/runtime/worker.py") is False


def test_repository_intelligence_patch_analysis_validate_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_validate_patch_against_snapshot(**kwargs: Any) -> None:
        observed.update(kwargs)

    monkeypatch.setattr(
        repository_patch_analysis,
        "_validate_patch_against_snapshot",
        _fake_validate_patch_against_snapshot,
    )

    snapshot_manifest = {"snapshot_id": "snapshot-1", "source_archive_path": "/tmp/source.tar"}
    patch_diff = "diff --git a/src/app.py b/src/app.py\n"

    repository_service._validate_patch_against_snapshot(
        snapshot_manifest=snapshot_manifest,
        patch_diff=patch_diff,
    )

    assert observed["snapshot_manifest"] is snapshot_manifest
    assert observed["patch_diff"] == patch_diff
    assert observed["materialized_snapshot"] is repository_service.materialized_snapshot
    assert observed["git_command"] is repository_service._git_command


def test_repository_intelligence_fsharp_helpers_are_modularized() -> None:
    assert repository_service._normalize_fsharp_symbol_name is (
        repository_service.fsharp_adapter.normalize_symbol_name
    )
    assert repository_service._normalize_fsharp_target is (
        repository_service.fsharp_adapter.normalize_target
    )
    assert repository_service._fsharp_path_aliases is repository_service.fsharp_adapter.path_aliases
    assert repository_service._fsharp_namespaces_from_text is (
        repository_service.fsharp_adapter.namespaces_from_text
    )
    assert repository_service._fsharp_open_targets is (
        repository_service.fsharp_adapter.open_targets
    )


def test_repository_intelligence_fsharp_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_suffix_match: Any,
        resolve_directory_prefix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["resolve_directory_prefix_match"] = resolve_directory_prefix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.fsharp_adapter, "parse_file", _fake_parse_file)

    module_index = {"Acme.Core": "src/Acme/Core.fs"}

    result = repository_service._parse_fsharp_file(
        "src/Acme/App.fs",
        "module Acme.App",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/Acme/App.fs"
    assert observed["text"] == "module Acme.App"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert callable(observed["resolve_suffix_match"])
    assert callable(observed["resolve_directory_prefix_match"])


def test_repository_intelligence_fsharp_lookup_helpers_resolve_without_generic_fallback() -> None:
    def _unexpected_suffix_match(*_args: Any, **_kwargs: Any) -> str | None:
        raise AssertionError("expected F# adapter to use its prebuilt lookup")

    def _unexpected_directory_prefix_match(*_args: Any, **_kwargs: Any) -> str | None:
        raise AssertionError("expected F# adapter to use its prebuilt lookup")

    module_index = {
        "Acme.Core": "src/Acme/Core.fs",
        "Acme.Request": "src/Acme/Core.fs",
        "Acme.RequestOps": "src/Acme/Core.fs",
        "Request": "src/Acme/Core.fs",
        "RequestOps": "src/Acme/Core.fs",
        "Acme.Http": "src/Acme/Http.fs",
    }
    module_index_lookup = repository_service.fsharp_adapter._build_module_index_lookup(
        module_index
    )

    resolved_import = repository_service.fsharp_adapter.resolve_import(
        "Acme.Core",
        module_index=module_index,
        module_index_lookup=module_index_lookup,
        resolve_suffix_match=_unexpected_suffix_match,
        resolve_directory_prefix_match=_unexpected_directory_prefix_match,
    )
    resolved_context_reference = repository_service.fsharp_adapter.resolve_context_reference(
        current_namespaces=("Acme",),
        opened_namespaces=("Acme.Core",),
        target_name="RequestOps",
        module_index=module_index,
        module_index_lookup=module_index_lookup,
        resolve_suffix_match=_unexpected_suffix_match,
        resolve_directory_prefix_match=_unexpected_directory_prefix_match,
    )

    assert resolved_import == "src/Acme/Core.fs"
    assert resolved_context_reference == "src/Acme/Core.fs"


def test_repository_intelligence_fsharp_cached_context_lookup_reuses_import_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_index = {
        "Acme.Core": "src/Acme/Core.fs",
        "Acme.RequestOps": "src/Acme/Core.fs",
        "RequestOps": "src/Acme/Core.fs",
    }
    resolve_calls: list[str] = []
    original_resolve_import = repository_service.fsharp_adapter.resolve_import

    def _counting_resolve_import(
        import_target: str,
        *,
        module_index: dict[str, str],
        module_index_lookup,
        resolve_suffix_match,
        resolve_directory_prefix_match,
    ) -> str | None:
        resolve_calls.append(import_target)
        return original_resolve_import(
            import_target,
            module_index=module_index,
            module_index_lookup=module_index_lookup,
            resolve_suffix_match=resolve_suffix_match,
            resolve_directory_prefix_match=resolve_directory_prefix_match,
        )

    monkeypatch.setattr(repository_service.fsharp_adapter, "resolve_import", _counting_resolve_import)

    resolve_import_target, resolve_context_target = (
        repository_service.fsharp_adapter._build_cached_resolvers(
            module_index=module_index,
            resolve_suffix_match=lambda *_args, **_kwargs: None,
            resolve_directory_prefix_match=lambda *_args, **_kwargs: None,
        )
    )

    assert resolve_import_target("Acme.Core") == "src/Acme/Core.fs"
    assert resolve_context_target((), (), "Acme.Core") == "src/Acme/Core.fs"
    assert resolve_calls == ["Acme.Core"]


def test_repository_intelligence_fsharp_lookup_path_normalization_reuses_cache() -> None:
    repository_service.fsharp_adapter._normalize_lookup_path.cache_clear()

    assert (
        repository_service.fsharp_adapter._normalize_lookup_path("src\\Acme\\Core.fs")
        == "src/Acme/Core.fs"
    )
    assert (
        repository_service.fsharp_adapter._normalize_lookup_path("src\\Acme\\Core.fs")
        == "src/Acme/Core.fs"
    )

    assert repository_service.fsharp_adapter._normalize_lookup_path.cache_info().hits >= 1


def test_repository_intelligence_fsharp_lookup_candidate_generation_reuses_cache() -> None:
    repository_service.fsharp_adapter._import_lookup_suffixes.cache_clear()
    repository_service.fsharp_adapter._import_lookup_prefixes.cache_clear()
    repository_service.fsharp_adapter._context_lookup_suffixes.cache_clear()

    assert repository_service.fsharp_adapter._import_lookup_suffixes("Acme.Core") == (
        "acme.core",
        "acme/core",
        "acme/core.fs",
        "acme/core.fsi",
        "acme/core.fsx",
        "core.fs",
        "core.fsi",
        "core.fsx",
    )
    assert repository_service.fsharp_adapter._import_lookup_suffixes("Acme.Core") == (
        "acme.core",
        "acme/core",
        "acme/core.fs",
        "acme/core.fsi",
        "acme/core.fsx",
        "core.fs",
        "core.fsi",
        "core.fsx",
    )
    assert repository_service.fsharp_adapter._import_lookup_prefixes("Acme.Core") == (
        "acme/core",
        "src/acme/core",
        "app/acme/core",
        "lib/acme/core",
    )
    assert repository_service.fsharp_adapter._context_lookup_suffixes("Request") == (
        "request.fs",
        "request.fsi",
        "request.fsx",
    )

    assert repository_service.fsharp_adapter._import_lookup_suffixes.cache_info().hits >= 1
    assert repository_service.fsharp_adapter._import_lookup_prefixes.cache_info().misses == 1
    assert repository_service.fsharp_adapter._context_lookup_suffixes.cache_info().misses == 1


def test_repository_intelligence_fsharp_type_reference_resolution_reuses_per_name_cache() -> None:
    observed_targets: list[str] = []

    def _resolve_context_target(
        current_namespaces,
        opened_namespaces,
        target_name: str,
    ) -> str | None:
        assert tuple(current_namespaces) == ("Acme",)
        assert tuple(opened_namespaces) == ("Acme.Core",)
        observed_targets.append(target_name)
        if target_name == "Request":
            return "src/Acme/Core.fs"
        return None

    dependencies = repository_service.fsharp_adapter._append_type_reference_dependencies(
        dependencies=(),
        import_bindings={},
        opened_namespaces=("Acme.Core",),
        current_namespaces=("Acme",),
        declared_symbol_names={"Handler"},
        file_path="src/Acme/Handler.fs",
        text=(
            "type Handler =\n"
            "    { Primary: Request\n"
            "      Secondary: Request }\n"
            "\n"
            "let promote (value: Request) = value\n"
        ),
        stable_identifier=lambda prefix, payload: (
            f"{prefix}:{payload['file_path']}:{payload['target']}:{payload['line']}"
        ),
        resolve_context_target=_resolve_context_target,
    )

    assert observed_targets.count("Request") == 1
    assert [dependency.target_symbol for dependency in dependencies] == ["Request"]
    assert [dependency.target_file for dependency in dependencies] == ["src/Acme/Core.fs"]


def test_repository_intelligence_ruby_helpers_are_modularized() -> None:
    assert repository_service._ruby_module_aliases_for_path is (
        repository_service.ruby_adapter.module_aliases_for_path
    )


def test_repository_intelligence_ruby_parse_wrapper_delegates(
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
        root_path: Path,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["module_index_aliases_for_file"] = module_index_aliases_for_file
        observed["root_path"] = root_path
        return (), (), ()

    monkeypatch.setattr(repository_service.ruby_adapter, "parse_file", _fake_parse_file)

    module_index = {"lib/acme/widget.rb": "lib/acme/widget.rb"}

    result = repository_service._parse_ruby_file(
        "lib/acme/app.rb",
        "require 'acme/widget'",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "lib/acme/app.rb"
    assert observed["text"] == "require 'acme/widget'"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match
    assert observed["module_index_aliases_for_file"] is (
        repository_service._module_index_aliases_for_file
    )
    assert observed["root_path"] == Path(".")


def test_repository_intelligence_crystal_helpers_are_modularized() -> None:
    assert repository_service._is_crystal_constant_alias is (
        repository_service.crystal_adapter.is_constant_alias
    )
    assert repository_service._crystal_declared_type_aliases_for_path is (
        repository_service.crystal_adapter.declared_type_aliases_for_path
    )
    assert repository_service._crystal_constant_aliases_for_file is (
        repository_service.crystal_adapter.constant_aliases_for_file
    )


def test_repository_intelligence_crystal_parse_wrapper_delegates(
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
        module_index_values: Any,
        module_index_aliases_for_file: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["module_index_values"] = module_index_values
        observed["module_index_aliases_for_file"] = module_index_aliases_for_file
        return (), (), ()

    monkeypatch.setattr(repository_service.crystal_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/acme/widget.cr": "src/acme/widget.cr"}

    result = repository_service._parse_crystal_file(
        "src/acme/app.cr",
        "require \"acme/widget\"",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/acme/app.cr"
    assert observed["text"] == 'require "acme/widget"'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match
    assert observed["module_index_values"] is repository_service._module_index_values
    assert observed["module_index_aliases_for_file"] is (
        repository_service._module_index_aliases_for_file
    )


def test_repository_intelligence_php_helpers_are_modularized() -> None:
    assert repository_service._php_current_namespace is repository_service.php_adapter.current_namespace
    assert repository_service._php_leading_docblock is repository_service.php_adapter.leading_docblock
    assert repository_service._php_symbol_declaration_header is (
        repository_service.php_adapter.symbol_declaration_header
    )
    assert repository_service._php_doc_type_tokens is repository_service.php_adapter.doc_type_tokens
    assert repository_service._php_type_tokens_from_header is (
        repository_service.php_adapter.type_tokens_from_header
    )
    assert repository_service._php_module_aliases_for_path is (
        repository_service.php_adapter.module_aliases_for_path
    )


def test_repository_intelligence_php_adapter_helpers_are_modularized() -> None:
    assert repository_service.php_adapter.current_namespace is (
        repository_php_primitives.current_namespace
    )
    assert repository_service.php_adapter.leading_docblock is (
        repository_php_primitives.leading_docblock
    )
    assert repository_service.php_adapter.symbol_declaration_header is (
        repository_php_primitives.symbol_declaration_header
    )
    assert repository_service.php_adapter.doc_type_tokens is (
        repository_php_primitives.doc_type_tokens
    )
    assert repository_service.php_adapter.type_tokens_from_header is (
        repository_php_primitives.type_tokens_from_header
    )
    assert repository_service.php_adapter._symbol_entries is (
        repository_php_primitives._symbol_entries
    )
    assert repository_service.php_adapter.module_aliases_for_path is (
        repository_php_analysis_support.module_aliases_for_path
    )
    assert repository_service.php_adapter.resolve_import is (
        repository_php_analysis_support.resolve_import
    )
    assert repository_service.php_adapter.resolve_same_namespace_reference is (
        repository_php_analysis_support.resolve_same_namespace_reference
    )
    assert repository_service.php_adapter.resolve_reference_target is (
        repository_php_analysis_support.resolve_reference_target
    )
    assert repository_service.php_adapter.iter_reference_targets is (
        repository_php_analysis_support.iter_reference_targets
    )
    assert repository_service.php_adapter.extract_import_bindings is (
        repository_php_analysis_support.extract_import_bindings
    )
    assert repository_service.php_adapter.parse_dependencies_only is (
        repository_php_analysis_support.parse_dependencies_only
    )
    assert repository_service.php_adapter.parse_file is repository_php_analysis_support.parse_file


def test_repository_intelligence_php_parse_wrapper_delegates(
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

    monkeypatch.setattr(repository_service.php_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/Acme/Widget.php": "src/Acme/Widget.php"}

    result = repository_service._parse_php_file(
        "src/Acme/App.php",
        "<?php\nuse Acme\\\\Widget;\n",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/Acme/App.php"
    assert observed["text"] == "<?php\nuse Acme\\\\Widget;\n"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_elixir_helpers_are_modularized() -> None:
    assert repository_service._elixir_module_aliases_for_path is (
        repository_service.elixir_adapter.module_aliases_for_path
    )
    assert repository_service._elixir_module_path_variants is (
        repository_service.elixir_adapter.module_path_variants
    )


def test_repository_intelligence_elixir_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_suffix_match: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_suffix_match"] = resolve_suffix_match
        return ()

    monkeypatch.setattr(
        repository_service.elixir_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"lib/acme/widget.ex": "lib/acme/widget.ex"}

    result = repository_service._parse_elixir_dependencies_only(
        "lib/acme/app.ex",
        "alias Acme.Widget",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "lib/acme/app.ex"
    assert observed["text"] == "alias Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_elixir_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.elixir_adapter, "parse_file", _fake_parse_file)

    module_index = {"lib/acme/widget.ex": "lib/acme/widget.ex"}

    result = repository_service._parse_elixir_file(
        "lib/acme/app.ex",
        "alias Acme.Widget",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "lib/acme/app.ex"
    assert observed["text"] == "alias Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_perl_helpers_are_modularized() -> None:
    assert repository_service._perl_module_aliases_for_path is (
        repository_service.perl_adapter.module_aliases_for_path
    )
    assert repository_service._extract_perl_use_args is (
        repository_service.perl_adapter.extract_use_args
    )
    assert repository_service._is_perl_package_like is (
        repository_service.perl_adapter.is_package_like
    )


def test_repository_intelligence_perl_dependency_wrapper_delegates(
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
        repository_service.perl_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"lib/Acme/Widget.pm": "lib/Acme/Widget.pm"}

    result = repository_service._parse_perl_dependencies_only(
        "lib/Acme/App.pm",
        "use Acme::Widget qw(run);",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "lib/Acme/App.pm"
    assert observed["text"] == "use Acme::Widget qw(run);"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_perl_parse_wrapper_delegates(
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

    monkeypatch.setattr(repository_service.perl_adapter, "parse_file", _fake_parse_file)

    module_index = {"lib/Acme/Widget.pm": "lib/Acme/Widget.pm"}

    result = repository_service._parse_perl_file(
        "lib/Acme/App.pm",
        "use Acme::Widget qw(run);",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "lib/Acme/App.pm"
    assert observed["text"] == "use Acme::Widget qw(run);"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_lua_helpers_are_modularized() -> None:
    assert repository_service._LUA_REQUIRE_RE is repository_service.lua_adapter.REQUIRE_RE
    assert repository_service._LUA_REQUIRE_BINDING_RE is (
        repository_service.lua_adapter.REQUIRE_BINDING_RE
    )
    assert repository_service._LUA_RESERVED_SYMBOL_NAMES is (
        repository_service.lua_adapter.RESERVED_SYMBOL_NAMES
    )
