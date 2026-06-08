from __future__ import annotations

import hashlib
import os as _os
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from apps.api_server.models.data_connector import DataConnector
from apps.api_server.schemas.repositories import (
    RepositoryApplyRequest,
    RepositoryApplyResponse,
    RepositoryDecisionPlanCreateRequest,
    RepositoryDecisionPlanResponse,
    RepositoryGraphQueryRequest,
    RepositoryGraphQueryResponse,
    RepositoryIntelligenceCapabilitiesResponse,
    RepositorySimulationRequest,
    RepositorySnapshotCreateRequest,
    RepositorySnapshotResponse,
    RepositoryTriageRequest,
    RepositoryTriageResponse,
)
from apps.api_server.schemas.response import DecisionEnvelope, DecisionPlan
from apps.api_server.schemas.simulate import SimulateRequestExpert
from apps.api_server.services import (
    repository_intelligence_adapter_parser_dispatch as repository_adapter_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_analysis_workflow as repository_analysis_workflow,
)
from apps.api_server.services import (
    repository_intelligence_autoit_parser_dispatch as repository_autoit_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_cache as repository_cache,
)
from apps.api_server.services import (
    repository_intelligence_compat_exports as repository_compat_exports,
)
from apps.api_server.services import (
    repository_intelligence_contracts as repository_contracts,
)
from apps.api_server.services import (
    repository_intelligence_decision_plan_workflow as repository_decision_plan_workflow,
)
from apps.api_server.services import (
    repository_intelligence_execution_workflow as repository_execution_workflow,
)
from apps.api_server.services import (
    repository_intelligence_file_selection as repository_file_selection,
)
from apps.api_server.services import (
    repository_intelligence_fish_parser_dispatch as repository_fish_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_graph_workflow as repository_graph_workflow,
)
from apps.api_server.services import (
    repository_intelligence_indexing as repository_indexing,
)
from apps.api_server.services import (
    repository_intelligence_inventory as repository_inventory,
)
from apps.api_server.services import (
    repository_intelligence_janet_parser_dispatch as repository_janet_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_language_resolution as repository_language_resolution,
)
from apps.api_server.services import (
    repository_intelligence_module_aliases as repository_module_aliases,
)
from apps.api_server.services import (
    repository_intelligence_patch_analysis as repository_patch_analysis,
)
from apps.api_server.services import (
    repository_intelligence_planner_generation as repository_planner_generation,
)
from apps.api_server.services import (
    repository_intelligence_repository_source as repository_repository_source,
)
from apps.api_server.services import (
    repository_intelligence_runtime as repository_runtime_module,
)
from apps.api_server.services import (
    repository_intelligence_shared as repository_shared_module,
)
from apps.api_server.services import (
    repository_intelligence_simple_parser_dispatch as repository_simple_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_snapshot_workflow as repository_snapshot_workflow,
)
from apps.api_server.services import (
    repository_intelligence_squirrel_parser_dispatch as repository_squirrel_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_storage as repository_storage,
)
from apps.api_server.services.execution_policy_service import get_policy
from apps.api_server.services.repository_language_priority import (
    repository_language_support_progress,
    supported_repository_languages,
)
from apps.api_server.services.simulation_service import run_simulation_fast

os = _os

REPOSITORY_CONNECTOR_TYPES = repository_repository_source.REPOSITORY_CONNECTOR_TYPES
_REPOSITORY_INTELLIGENCE_ENGINE_REVISION = "repository-intelligence-v2026-06-07-r124"
_DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID = "repository.deterministic_local_v1"
_ENTRYPOINT_DEMOTED_LANGUAGES = frozenset(
    {
        "css",
        "edn",
        "html",
        "json",
        "markdown",
        "nimble",
        "nimscript",
        "opam",
        "rockspec",
        "toml",
        "xml",
        "yaml",
    }
)

RepositoryIntelligenceError = repository_contracts.RepositoryIntelligenceError
_Dependency = repository_contracts._Dependency
_DeterministicConfigPatch = repository_contracts._DeterministicConfigPatch
_DeterministicLiteralPatch = repository_contracts._DeterministicLiteralPatch
_FileAnalysis = repository_contracts._FileAnalysis
_InlineConnector = repository_contracts._InlineConnector
_InlineConnectorType = repository_contracts._InlineConnectorType

_estimate_tokens = repository_indexing._estimate_tokens
_language_for_path = repository_indexing._language_for_path

_DEFAULT_EXCLUDED_PATH_PARTS = repository_inventory._DEFAULT_EXCLUDED_PATH_PARTS
_build_workspace_package_index = repository_inventory._build_workspace_package_index
_build_workspace_go_module_index = repository_inventory._build_workspace_go_module_index

_stable_identifier = repository_shared_module._stable_identifier
_utc_now = repository_shared_module._utc_now
_coerce_scope_uuid = repository_shared_module._coerce_scope_uuid
_hash_payload = repository_shared_module._hash_payload

_apply_dir = repository_runtime_module._apply_dir
_decision_plans_dir = repository_runtime_module._decision_plans_dir
_lookup_response_payload = repository_runtime_module._lookup_response_payload
_read_json = repository_runtime_module._read_json
_simulation_lookup_dir = repository_runtime_module._simulation_lookup_dir
_simulations_dir = repository_runtime_module._simulations_dir
_triage_dir = repository_runtime_module._triage_dir
_write_json = repository_runtime_module._write_json
_write_json_atomic = repository_runtime_module._write_json_atomic

_hash_file = repository_storage._hash_file
_load_decision_plan_manifest = repository_storage._load_decision_plan_manifest
_load_patch_impact_manifest = repository_storage._load_patch_impact_manifest
_load_simulation_manifest = repository_storage._load_simulation_manifest
_load_snapshot_manifest = repository_storage._load_snapshot_manifest
_load_triage_manifest = repository_storage._load_triage_manifest
materialized_snapshot = repository_storage.materialized_snapshot

_file_analysis_context_hash = repository_cache._file_analysis_context_hash
_dependency_analysis_cache_key = repository_cache._dependency_analysis_cache_key
_dependency_analysis_cache_path = repository_cache._dependency_analysis_cache_path
_file_analysis_cache_key = repository_cache._file_analysis_cache_key
_file_analysis_cache_path = repository_cache._file_analysis_cache_path
_load_dependency_analysis_cache = repository_cache._load_dependency_analysis_cache
_load_file_analysis_cache = repository_cache._load_file_analysis_cache
_serialize_dependency_analysis = repository_cache._serialize_dependency_analysis
_serialize_file_analysis = repository_cache._serialize_file_analysis

_parse_connector_config = repository_repository_source._parse_connector_config
_require_repository_connector = repository_repository_source._require_repository_connector
_repo_access_token = repository_repository_source._repo_access_token
_repository_url = repository_repository_source._repository_url
_authenticated_repository_url = repository_repository_source._authenticated_repository_url
_git_command = repository_repository_source._git_command
_git_tracked_content_hashes = repository_repository_source._git_tracked_content_hashes
resolved_repository_source = repository_repository_source.resolved_repository_source

_append_repository_file = repository_file_selection._append_repository_file
_compact_repository_focus_paths = repository_file_selection._compact_repository_focus_paths
_detected_repository_file_language = repository_file_selection._detected_repository_file_language
_iter_repository_files = repository_file_selection._iter_repository_files
_path_is_indexable_repository_file = repository_file_selection._path_is_indexable_repository_file

_build_module_index = repository_module_aliases._build_module_index
_augment_julia_package_symbol_references = (
    repository_language_resolution._augment_julia_package_symbol_references
)
_augment_r_package_symbol_references = (
    repository_language_resolution._augment_r_package_symbol_references
)
_resolve_symbol_reference_target = (
    repository_language_resolution._resolve_symbol_reference_target
)

_patch_changed_files = repository_patch_analysis._patch_changed_files
_top_level_service = repository_patch_analysis._top_level_service
_is_test_path = repository_patch_analysis._is_test_path

_REGISTERED_ADAPTER_DEPENDENCY_PARSERS = (
    repository_adapter_parser_dispatch.REGISTERED_ADAPTER_DEPENDENCY_PARSERS
)
_REGISTERED_ADAPTER_FILE_PARSERS = (
    repository_adapter_parser_dispatch.REGISTERED_ADAPTER_FILE_PARSERS
)

_parse_r_dependencies_only = repository_adapter_parser_dispatch._parse_r_dependencies_only
_parse_r_file = repository_adapter_parser_dispatch._parse_r_file
_parse_jvm_dependencies_only = repository_adapter_parser_dispatch._parse_jvm_dependencies_only
_parse_jvm_file = repository_adapter_parser_dispatch._parse_jvm_file

_parse_python_file = repository_simple_parser_dispatch._parse_python_file
_parse_rust_file = repository_simple_parser_dispatch._parse_rust_file
_parse_go_file = repository_simple_parser_dispatch._parse_go_file
_parse_js_like_file = repository_simple_parser_dispatch._parse_js_like_file
_parse_coffeescript_file = repository_simple_parser_dispatch._parse_coffeescript_file
_parse_vala_file = repository_simple_parser_dispatch._parse_vala_file
_parse_mql5_file = repository_simple_parser_dispatch._parse_mql5_file
_parse_gams_file = repository_simple_parser_dispatch._parse_gams_file
_parse_nix_file = repository_simple_parser_dispatch._parse_nix_file
_parse_nushell_file = repository_simple_parser_dispatch._parse_nushell_file
_parse_fish_file = repository_fish_parser_dispatch._parse_fish_file
_parse_openscad_file = repository_simple_parser_dispatch._parse_openscad_file
_parse_purescript_file = repository_simple_parser_dispatch._parse_purescript_file
_parse_gleam_file = repository_simple_parser_dispatch._parse_gleam_file
_parse_janet_file = repository_janet_parser_dispatch._parse_janet_file
_parse_haxe_file = repository_simple_parser_dispatch._parse_haxe_file
_parse_autohotkey_file = repository_simple_parser_dispatch._parse_autohotkey_file
_parse_autoit_file = repository_autoit_parser_dispatch._parse_autoit_file
_parse_squirrel_file = repository_squirrel_parser_dispatch._parse_squirrel_file
_parse_starlark_file = repository_simple_parser_dispatch._parse_starlark_file
_parse_vimscript_file = repository_simple_parser_dispatch._parse_vimscript_file
_parse_v_file = repository_simple_parser_dispatch._parse_v_file
_parse_smalltalk_file = repository_simple_parser_dispatch._parse_smalltalk_file
_parse_mojo_file = repository_simple_parser_dispatch._parse_mojo_file
_parse_python_dependencies_only = (
    repository_simple_parser_dispatch._parse_python_dependencies_only
)
_parse_c_family_dependencies_only = (
    repository_simple_parser_dispatch._parse_c_family_dependencies_only
)
_parse_c_family_file = repository_simple_parser_dispatch._parse_c_family_file
_parse_zig_dependencies_only = repository_simple_parser_dispatch._parse_zig_dependencies_only
_parse_zig_file = repository_simple_parser_dispatch._parse_zig_file
_parse_js_like_dependencies_only = (
    repository_simple_parser_dispatch._parse_js_like_dependencies_only
)
_parse_coffeescript_dependencies_only = (
    repository_simple_parser_dispatch._parse_coffeescript_dependencies_only
)
_parse_vala_dependencies_only = (
    repository_simple_parser_dispatch._parse_vala_dependencies_only
)
_parse_mql5_dependencies_only = (
    repository_simple_parser_dispatch._parse_mql5_dependencies_only
)
_parse_gams_dependencies_only = (
    repository_simple_parser_dispatch._parse_gams_dependencies_only
)
_parse_nix_dependencies_only = repository_simple_parser_dispatch._parse_nix_dependencies_only
_parse_nushell_dependencies_only = (
    repository_simple_parser_dispatch._parse_nushell_dependencies_only
)
_parse_fish_dependencies_only = (
    repository_fish_parser_dispatch._parse_fish_dependencies_only
)
_parse_openscad_dependencies_only = (
    repository_simple_parser_dispatch._parse_openscad_dependencies_only
)
_parse_purescript_dependencies_only = (
    repository_simple_parser_dispatch._parse_purescript_dependencies_only
)
_parse_gleam_dependencies_only = (
    repository_simple_parser_dispatch._parse_gleam_dependencies_only
)
_parse_janet_dependencies_only = (
    repository_janet_parser_dispatch._parse_janet_dependencies_only
)
_parse_haxe_dependencies_only = (
    repository_simple_parser_dispatch._parse_haxe_dependencies_only
)
_parse_autohotkey_dependencies_only = (
    repository_simple_parser_dispatch._parse_autohotkey_dependencies_only
)
_parse_autoit_dependencies_only = (
    repository_autoit_parser_dispatch._parse_autoit_dependencies_only
)
_parse_squirrel_dependencies_only = (
    repository_squirrel_parser_dispatch._parse_squirrel_dependencies_only
)
_parse_starlark_dependencies_only = (
    repository_simple_parser_dispatch._parse_starlark_dependencies_only
)
_parse_vimscript_dependencies_only = (
    repository_simple_parser_dispatch._parse_vimscript_dependencies_only
)
_parse_v_dependencies_only = repository_simple_parser_dispatch._parse_v_dependencies_only
_parse_smalltalk_dependencies_only = (
    repository_simple_parser_dispatch._parse_smalltalk_dependencies_only
)
_parse_mojo_dependencies_only = (
    repository_simple_parser_dispatch._parse_mojo_dependencies_only
)
_parse_rust_dependencies_only = (
    repository_simple_parser_dispatch._parse_rust_dependencies_only
)
_parse_go_dependencies_only = repository_simple_parser_dispatch._parse_go_dependencies_only
_parse_dart_dependencies_only = (
    repository_simple_parser_dispatch._parse_dart_dependencies_only
)
_parse_dart_file = repository_simple_parser_dispatch._parse_dart_file

repository_repository_source._hash_file = lambda path: _hash_file(path)


def __getattr__(name: str) -> Any:
    return repository_compat_exports.get_export(name)


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_bytes_with_hash(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return _hash_bytes(payload)


def _analyze_file_dependencies(
    *,
    root_path: Path,
    path: Path,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None = None,
    max_file_size_bytes: int,
) -> tuple[_Dependency, ...]:
    return repository_analysis_workflow._analyze_file_dependencies(
        root_path=root_path,
        path=path,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        path_is_indexable_repository_file=_path_is_indexable_repository_file,
        language_for_path=_language_for_path,
        registered_adapter_dependency_parsers=_REGISTERED_ADAPTER_DEPENDENCY_PARSERS,
        parse_r_dependencies_only=_parse_r_dependencies_only,
        parse_dart_dependencies_only=_parse_dart_dependencies_only,
        parse_python_dependencies_only=_parse_python_dependencies_only,
        parse_c_family_dependencies_only=_parse_c_family_dependencies_only,
        parse_zig_dependencies_only=_parse_zig_dependencies_only,
        parse_coffeescript_dependencies_only=_parse_coffeescript_dependencies_only,
        parse_vala_dependencies_only=_parse_vala_dependencies_only,
        parse_mql5_dependencies_only=_parse_mql5_dependencies_only,
        parse_gams_dependencies_only=_parse_gams_dependencies_only,
        parse_nix_dependencies_only=_parse_nix_dependencies_only,
        parse_nushell_dependencies_only=_parse_nushell_dependencies_only,
        parse_fish_dependencies_only=_parse_fish_dependencies_only,
        parse_openscad_dependencies_only=_parse_openscad_dependencies_only,
        parse_purescript_dependencies_only=_parse_purescript_dependencies_only,
        parse_gleam_dependencies_only=_parse_gleam_dependencies_only,
        parse_janet_dependencies_only=_parse_janet_dependencies_only,
        parse_haxe_dependencies_only=_parse_haxe_dependencies_only,
        parse_autohotkey_dependencies_only=_parse_autohotkey_dependencies_only,
        parse_autoit_dependencies_only=_parse_autoit_dependencies_only,
        parse_squirrel_dependencies_only=_parse_squirrel_dependencies_only,
        parse_starlark_dependencies_only=_parse_starlark_dependencies_only,
        parse_vimscript_dependencies_only=_parse_vimscript_dependencies_only,
        parse_v_dependencies_only=_parse_v_dependencies_only,
        parse_smalltalk_dependencies_only=_parse_smalltalk_dependencies_only,
        parse_js_like_dependencies_only=_parse_js_like_dependencies_only,
        parse_go_dependencies_only=_parse_go_dependencies_only,
        parse_jvm_dependencies_only=_parse_jvm_dependencies_only,
        parse_rust_dependencies_only=_parse_rust_dependencies_only,
        parse_mojo_dependencies_only=_parse_mojo_dependencies_only,
    )


def _analyze_file_dependencies_cached(
    *,
    root_path: Path,
    path: Path,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None,
    max_file_size_bytes: int,
    analysis_context_hash: str,
    git_content_hashes: dict[str, str] | None = None,
) -> tuple[_Dependency, ...]:
    return repository_analysis_workflow._analyze_file_dependencies_cached(
        root_path=root_path,
        path=path,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        analysis_context_hash=analysis_context_hash,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        hash_file=_hash_file,
        dependency_analysis_cache_key=_dependency_analysis_cache_key,
        dependency_analysis_cache_path=_dependency_analysis_cache_path,
        load_dependency_analysis_cache=_load_dependency_analysis_cache,
        serialize_dependency_analysis=_serialize_dependency_analysis,
        write_json_atomic=_write_json_atomic,
        analyze_file_dependencies=_analyze_file_dependencies,
        git_content_hashes=git_content_hashes,
    )


def _analyze_file(
    *,
    root_path: Path,
    path: Path,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None = None,
    max_file_size_bytes: int,
    content_hash: str | None = None,
) -> _FileAnalysis:
    return repository_analysis_workflow._analyze_file(
        root_path=root_path,
        path=path,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        hash_file=_hash_file,
        path_is_indexable_repository_file=_path_is_indexable_repository_file,
        language_for_path=_language_for_path,
        estimate_tokens=_estimate_tokens,
        registered_adapter_file_parsers=_REGISTERED_ADAPTER_FILE_PARSERS,
        parse_r_file=_parse_r_file,
        parse_dart_file=_parse_dart_file,
        parse_python_file=_parse_python_file,
        parse_c_family_file=_parse_c_family_file,
        parse_zig_file=_parse_zig_file,
        parse_rust_file=_parse_rust_file,
        parse_mojo_file=_parse_mojo_file,
        parse_coffeescript_file=_parse_coffeescript_file,
        parse_vala_file=_parse_vala_file,
        parse_mql5_file=_parse_mql5_file,
        parse_gams_file=_parse_gams_file,
        parse_nix_file=_parse_nix_file,
        parse_nushell_file=_parse_nushell_file,
        parse_fish_file=_parse_fish_file,
        parse_openscad_file=_parse_openscad_file,
        parse_purescript_file=_parse_purescript_file,
        parse_gleam_file=_parse_gleam_file,
        parse_janet_file=_parse_janet_file,
        parse_haxe_file=_parse_haxe_file,
        parse_autohotkey_file=_parse_autohotkey_file,
        parse_autoit_file=_parse_autoit_file,
        parse_squirrel_file=_parse_squirrel_file,
        parse_starlark_file=_parse_starlark_file,
        parse_vimscript_file=_parse_vimscript_file,
        parse_v_file=_parse_v_file,
        parse_smalltalk_file=_parse_smalltalk_file,
        parse_js_like_file=_parse_js_like_file,
        parse_go_file=_parse_go_file,
        parse_jvm_file=_parse_jvm_file,
        content_hash=content_hash,
    )


def _analyze_file_cached(
    *,
    root_path: Path,
    path: Path,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None,
    max_file_size_bytes: int,
    analysis_context_hash: str,
    git_content_hashes: dict[str, str] | None = None,
) -> _FileAnalysis:
    return repository_analysis_workflow._analyze_file_cached(
        root_path=root_path,
        path=path,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        analysis_context_hash=analysis_context_hash,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        hash_file=_hash_file,
        file_analysis_cache_key=_file_analysis_cache_key,
        file_analysis_cache_path=_file_analysis_cache_path,
        load_file_analysis_cache=_load_file_analysis_cache,
        serialize_file_analysis=_serialize_file_analysis,
        write_json_atomic=_write_json_atomic,
        analyze_file=_analyze_file,
        git_content_hashes=git_content_hashes,
    )


def _snapshot_analysis_max_workers(file_count: int) -> int:
    return repository_analysis_workflow._snapshot_analysis_max_workers(file_count)


def _analyze_snapshot_files(
    *,
    root_path: Path,
    files: Sequence[Path],
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None,
    max_file_size_bytes: int,
    analysis_context_hash: str,
    git_content_hashes: dict[str, str] | None = None,
    max_workers: int | None = None,
) -> list[_FileAnalysis]:
    return repository_analysis_workflow._analyze_snapshot_files(
        root_path=root_path,
        files=files,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        analysis_context_hash=analysis_context_hash,
        analyze_file_cached=_analyze_file_cached,
        git_content_hashes=git_content_hashes,
        max_workers=max_workers,
    )


def _simulation_lookup_key(
    *,
    snapshot_id: str,
    decision_plan_id: str,
    policy_snapshot_id: str,
    runs: int,
    seed: int | None,
) -> str:
    return _stable_identifier(
        "simulation_lookup",
        {
            "engine_revision": _REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
            "snapshot_id": snapshot_id,
            "decision_plan_id": decision_plan_id,
            "policy_snapshot_id": policy_snapshot_id,
            "runs": runs,
            "seed": seed,
        },
    )


def create_repository_snapshot(
    *,
    connector: DataConnector,
    request: RepositorySnapshotCreateRequest,
) -> RepositorySnapshotResponse:
    return repository_snapshot_workflow.create_repository_snapshot(
        connector=connector,
        request=request,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        require_repository_connector=_require_repository_connector,
        parse_connector_config=_parse_connector_config,
        resolved_repository_source=resolved_repository_source,
        compact_repository_focus_paths=_compact_repository_focus_paths,
        iter_repository_files=_iter_repository_files,
        build_module_index=_build_module_index,
        build_workspace_package_index=_build_workspace_package_index,
        build_workspace_go_module_index=_build_workspace_go_module_index,
        git_tracked_content_hashes=_git_tracked_content_hashes,
        file_analysis_context_hash=_file_analysis_context_hash,
        analyze_snapshot_files=_analyze_snapshot_files,
        augment_r_package_symbol_references=_augment_r_package_symbol_references,
        augment_julia_package_symbol_references=_augment_julia_package_symbol_references,
        resolve_symbol_reference_target=_resolve_symbol_reference_target,
        hash_file=_hash_file,
        write_bytes_with_hash=_write_bytes_with_hash,
    )


def get_repository_snapshot(
    *, connector: DataConnector, snapshot_id: str
) -> RepositorySnapshotResponse:
    return repository_snapshot_workflow.get_repository_snapshot(
        connector=connector,
        snapshot_id=snapshot_id,
        require_repository_connector=_require_repository_connector,
        load_snapshot_manifest=_load_snapshot_manifest,
    )


def get_repository_intelligence_capabilities() -> RepositoryIntelligenceCapabilitiesResponse:
    progress = repository_language_support_progress()
    return RepositoryIntelligenceCapabilitiesResponse.model_validate(
        {
            "supported_languages": list(supported_repository_languages()),
            "support_progress": {
                "supported_real_language_count": progress.supported_real_language_count,
                "ranked_target_language_count": progress.ranked_target_language_count,
                "progress_fraction": progress.progress_fraction,
                "progress_label": progress.progress_label,
            },
        }
    )


def query_repository_graph(
    *, connector: DataConnector, request: RepositoryGraphQueryRequest
) -> RepositoryGraphQueryResponse:
    return repository_graph_workflow.query_repository_graph(
        connector=connector,
        request=request,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        require_repository_connector=_require_repository_connector,
        load_snapshot_manifest=_load_snapshot_manifest,
        load_triage_manifest=_load_triage_manifest,
        read_json=_read_json,
    )


def triage_repository(
    *, connector: DataConnector, request: RepositoryTriageRequest
) -> RepositoryTriageResponse:
    return repository_graph_workflow.triage_repository(
        connector=connector,
        request=request,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        require_repository_connector=_require_repository_connector,
        load_snapshot_manifest=_load_snapshot_manifest,
        read_json=_read_json,
        materialized_snapshot=materialized_snapshot,
    )


def _resolve_repository_model(explicit_model: str | None) -> str:
    return repository_planner_generation._resolve_repository_model(
        explicit_model,
        deterministic_local_model_id=_DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
    )


def _deterministic_typescript_rootdir_patch(
    *,
    snapshot_manifest: dict[str, Any],
    triage_manifest: dict[str, Any],
    root_path: Path,
) -> _DeterministicConfigPatch:
    return repository_planner_generation._deterministic_typescript_rootdir_patch(
        snapshot_manifest=snapshot_manifest,
        triage_manifest=triage_manifest,
        root_path=root_path,
    )


def _deterministic_python_return_literal_patch(
    *,
    file_path: str,
    text: str,
    diagnostic_line: int | None,
    suspect_symbols: Sequence[str],
    current_literal: str,
    expected_literal: str,
) -> _DeterministicLiteralPatch:
    return repository_planner_generation._deterministic_python_return_literal_patch(
        file_path=file_path,
        text=text,
        diagnostic_line=diagnostic_line,
        suspect_symbols=suspect_symbols,
        current_literal=current_literal,
        expected_literal=expected_literal,
    )


def _generate_deterministic_repository_patch_plan(
    *,
    snapshot_manifest: dict[str, Any],
    triage_manifest: dict[str, Any],
) -> dict[str, Any]:
    return repository_planner_generation._generate_deterministic_repository_patch_plan(
        snapshot_manifest=snapshot_manifest,
        triage_manifest=triage_manifest,
        deterministic_local_model_id=_DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
    )


async def _generate_repository_patch_plan(
    *,
    model_id: str,
    snapshot_manifest: dict[str, Any],
    triage_manifest: dict[str, Any],
) -> dict[str, Any]:
    return await repository_planner_generation._generate_repository_patch_plan(
        model_id=model_id,
        snapshot_manifest=snapshot_manifest,
        triage_manifest=triage_manifest,
        deterministic_local_model_id=_DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
    )


def _validate_patch_against_snapshot(*, snapshot_manifest: dict[str, Any], patch_diff: str) -> None:
    repository_patch_analysis._validate_patch_against_snapshot(
        snapshot_manifest=snapshot_manifest,
        patch_diff=patch_diff,
        materialized_snapshot=materialized_snapshot,
        git_command=_git_command,
    )


def _patch_impact_summary(snapshot_manifest: dict[str, Any], patch_diff: str) -> dict[str, Any]:
    return repository_decision_plan_workflow._patch_impact_summary(
        snapshot_manifest,
        patch_diff,
        patch_changed_files=_patch_changed_files,
        top_level_service=_top_level_service,
        is_test_path=_is_test_path,
    )


async def create_repository_decision_plan(
    *,
    connector: DataConnector,
    request: RepositoryDecisionPlanCreateRequest,
) -> RepositoryDecisionPlanResponse:
    return await repository_decision_plan_workflow.create_repository_decision_plan(
        connector=connector,
        request=request,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        require_repository_connector=_require_repository_connector,
        resolve_repository_model=_resolve_repository_model,
        read_json=_read_json,
        generate_repository_patch_plan=_generate_repository_patch_plan,
        validate_patch_against_snapshot=_validate_patch_against_snapshot,
        patch_impact_summary=_patch_impact_summary,
    )


def _simulation_request_from_plan(plan: DecisionPlan) -> SimulateRequestExpert:
    return repository_execution_workflow._simulation_request_from_plan(plan)


async def simulate_repository_decision(
    *,
    connector: DataConnector,
    request: RepositorySimulationRequest,
) -> DecisionEnvelope:
    return await repository_execution_workflow.simulate_repository_decision(
        connector=connector,
        request=request,
        require_repository_connector=_require_repository_connector,
        get_policy=get_policy,
        load_decision_plan_manifest=_load_decision_plan_manifest,
        simulation_lookup_key=_simulation_lookup_key,
        simulation_lookup_dir=_simulation_lookup_dir,
        read_json=_read_json,
        simulations_dir=_simulations_dir,
        lookup_response_payload=_lookup_response_payload,
        write_json=_write_json,
        load_snapshot_manifest=_load_snapshot_manifest,
        load_patch_impact_manifest=_load_patch_impact_manifest,
        run_simulation_fast=run_simulation_fast,
        utc_now=_utc_now,
        stable_identifier=_stable_identifier,
    )


def _patch_text_for_plan(
    *, org_id: str, repository_id: str, decision_plan_manifest: dict[str, Any]
) -> str:
    return repository_execution_workflow._patch_text_for_plan(
        org_id=org_id,
        repository_id=repository_id,
        decision_plan_manifest=decision_plan_manifest,
    )


def _ensure_clean_git_worktree(path: Path) -> None:
    repository_execution_workflow._ensure_clean_git_worktree(path, git_command=_git_command)


def _apply_patch_to_git_checkout(
    *,
    checkout_path: Path,
    patch_text: str,
    branch_name: str,
    commit_message: str,
    base_branch: str | None,
) -> str:
    return repository_execution_workflow._apply_patch_to_git_checkout(
        checkout_path=checkout_path,
        patch_text=patch_text,
        branch_name=branch_name,
        commit_message=commit_message,
        base_branch=base_branch,
        git_command=_git_command,
    )


def _config_remote_metadata(
    connector_type: str, config: dict[str, Any], repository_url: str
) -> dict[str, str]:
    return repository_execution_workflow._config_remote_metadata(
        connector_type,
        config,
        repository_url,
    )


async def _create_pull_request(
    *,
    connector_type: str,
    config: dict[str, Any],
    repository_url: str,
    source_branch: str,
    target_branch: str,
    title: str,
    body: str,
) -> str:
    return await repository_execution_workflow._create_pull_request(
        connector_type=connector_type,
        config=config,
        repository_url=repository_url,
        source_branch=source_branch,
        target_branch=target_branch,
        title=title,
        body=body,
        repo_access_token=_repo_access_token,
    )


async def apply_repository_decision(
    *,
    connector: DataConnector,
    request: RepositoryApplyRequest,
) -> RepositoryApplyResponse:
    return await repository_execution_workflow.apply_repository_decision(
        connector=connector,
        request=request,
        require_repository_connector=_require_repository_connector,
        parse_connector_config=_parse_connector_config,
        load_decision_plan_manifest=_load_decision_plan_manifest,
        load_simulation_manifest=_load_simulation_manifest,
        load_snapshot_manifest=_load_snapshot_manifest,
        utc_now=_utc_now,
        patch_changed_files=_patch_changed_files,
        resolved_repository_source=resolved_repository_source,
        git_command=_git_command,
        repository_url=_repository_url,
        authenticated_repository_url=_authenticated_repository_url,
        repo_access_token=_repo_access_token,
        stable_identifier=_stable_identifier,
        apply_dir=_apply_dir,
        write_json=_write_json,
    )


def browse_repository_connector(
    *, connector_type: str, config: dict[str, Any]
) -> tuple[list[dict[str, Any]], str]:
    fake_connector = _InlineConnector(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        connector_type=_InlineConnectorType(connector_type),
    )
    with resolved_repository_source(connector=fake_connector, config=config, ref=None) as source:
        items: list[dict[str, Any]] = []
        for path in sorted(source.root_path.rglob("*"))[:100]:
            if path == source.root_path:
                continue
            relative_path = str(path.relative_to(source.root_path))
            if set(Path(relative_path).parts) & _DEFAULT_EXCLUDED_PATH_PARTS:
                continue
            items.append(
                {
                    "id": relative_path,
                    "label": relative_path,
                    "kind": "directory" if path.is_dir() else "file",
                    "selection": {"path": relative_path},
                    "language": (
                        None
                        if path.is_dir()
                        else _detected_repository_file_language(path, repo_root=source.root_path)
                    ),
                    "size": None if path.is_dir() else path.stat().st_size,
                }
            )
            if len(items) >= 100:
                break
        return items, f"Found {len(items)} repository entries"


def test_repository_connector(*, connector_type: str, config: dict[str, Any]) -> tuple[bool, str]:
    fake_connector = _InlineConnector(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        connector_type=_InlineConnectorType(connector_type),
    )
    with resolved_repository_source(connector=fake_connector, config=config, ref=None) as source:
        entry_count = sum(1 for _ in source.root_path.rglob("*"))
        source_label = source.repository_url or str(source.root_path)
        return True, f"Repository source reachable: {source_label} ({entry_count} entries)."
