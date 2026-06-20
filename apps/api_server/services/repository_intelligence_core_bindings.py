# ruff: noqa: E402
"""Lazy module loaders + compat re-export bindings for repository intelligence core.

Extracted from repository_intelligence_core so the core logic module stays within the
per-module line budget. This layer holds the per-submodule lazy loaders and the
``X = submodule.X`` / ``_lazy_module_attr`` alias bindings (one entry per re-exported
helper / language), which scale with the helper + language count rather than with logic.
They are star-imported back into core so callers keep resolving them from core.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import lru_cache
from typing import Any

from apps.api_server.services import (
    repository_intelligence_cache as repository_cache,
    repository_intelligence_contracts as repository_contracts,
    repository_intelligence_indexing as repository_indexing,
    repository_intelligence_inventory as repository_inventory,
    repository_intelligence_patch_analysis as repository_patch_analysis,
    repository_intelligence_runtime as repository_runtime_module,
    repository_intelligence_shared as repository_shared_module,
)



@lru_cache(maxsize=1)
def _adapter_parser_dispatch_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_adapter_parser_dispatch as repository_adapter_parser_dispatch,
    )

    return repository_adapter_parser_dispatch


@lru_cache(maxsize=1)
def _analysis_workflow_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_analysis_workflow as repository_analysis_workflow,
    )

    return repository_analysis_workflow


@lru_cache(maxsize=1)
def _autoit_parser_dispatch_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_autoit_parser_dispatch as repository_autoit_parser_dispatch,
    )

    return repository_autoit_parser_dispatch


@lru_cache(maxsize=1)
def _decision_plan_workflow_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_decision_plan_workflow as repository_decision_plan_workflow,
    )

    return repository_decision_plan_workflow


@lru_cache(maxsize=1)
def _execution_workflow_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_execution_workflow as repository_execution_workflow,
    )

    return repository_execution_workflow


@lru_cache(maxsize=1)
def _fish_parser_dispatch_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_fish_parser_dispatch as repository_fish_parser_dispatch,
    )

    return repository_fish_parser_dispatch


@lru_cache(maxsize=1)
def _file_selection_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_file_selection as repository_file_selection,
    )

    return repository_file_selection


@lru_cache(maxsize=1)
def _graph_workflow_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_graph_workflow as repository_graph_workflow,
    )

    return repository_graph_workflow


@lru_cache(maxsize=1)
def _janet_parser_dispatch_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_janet_parser_dispatch as repository_janet_parser_dispatch,
    )

    return repository_janet_parser_dispatch


@lru_cache(maxsize=1)
def _language_resolution_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_language_resolution as repository_language_resolution,
    )

    return repository_language_resolution


@lru_cache(maxsize=1)
def _module_aliases_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_module_aliases as repository_module_aliases,
    )

    return repository_module_aliases


@lru_cache(maxsize=1)
def _planner_generation_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_planner_generation as repository_planner_generation,
    )

    return repository_planner_generation


@lru_cache(maxsize=1)
def _security_analysis_workflow_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_security_analysis_workflow as repository_security_analysis_workflow,
    )

    return repository_security_analysis_workflow


@lru_cache(maxsize=1)
def _snapshot_workflow_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_snapshot_workflow as repository_snapshot_workflow,
    )

    return repository_snapshot_workflow


@lru_cache(maxsize=1)
def _simple_parser_dispatch_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_simple_parser_dispatch as repository_simple_parser_dispatch,
    )

    return repository_simple_parser_dispatch


@lru_cache(maxsize=1)
def _repository_source_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_repository_source as repository_repository_source,
    )

    # Inject the file hasher so the repository-source module reuses core's ``_hash_file``.
    # Resolve it off the core module at call time (not via a closure over this module's
    # namespace) so a ``monkeypatch.setattr(core, "_hash_file", ...)`` is still honoured
    # by the repository-source call path.
    from apps.api_server.services import repository_intelligence_core as _core

    repository_repository_source._hash_file = lambda path: _core._hash_file(path)
    return repository_repository_source


@lru_cache(maxsize=1)
def _repository_storage_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_storage as repository_storage,
    )

    return repository_storage


@lru_cache(maxsize=1)
def _squirrel_parser_dispatch_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_squirrel_parser_dispatch as repository_squirrel_parser_dispatch,
    )

    return repository_squirrel_parser_dispatch


def _lazy_module_attr(module_loader: Callable[[], Any], name: str) -> Callable[..., Any]:
    def _call(*args: Any, **kwargs: Any) -> Any:
        return getattr(module_loader(), name)(*args, **kwargs)

    return _call


# Lazily-resolved re-exports of parser-dispatch / language-resolution helpers. Bound
# through core's __getattr__ (returning the *real* function for identity) rather than as
# eager wrappers, so importing core leaves these submodules unloaded (the lazy-load
# tests guard that). Maps export name -> (submodule loader, attribute).
_LAZY_MODULE_ATTR_EXPORTS: dict[str, tuple[Callable[[], Any], str]] = {
    "_augment_julia_package_symbol_references": (_language_resolution_module, "_augment_julia_package_symbol_references"),
    "_augment_r_package_symbol_references": (_language_resolution_module, "_augment_r_package_symbol_references"),
    "_resolve_symbol_reference_target": (_language_resolution_module, "_resolve_symbol_reference_target"),
    "_parse_python_file": (_simple_parser_dispatch_module, "_parse_python_file"),
    "_parse_rust_file": (_simple_parser_dispatch_module, "_parse_rust_file"),
    "_parse_go_file": (_simple_parser_dispatch_module, "_parse_go_file"),
    "_parse_js_like_file": (_simple_parser_dispatch_module, "_parse_js_like_file"),
    "_parse_coffeescript_file": (_simple_parser_dispatch_module, "_parse_coffeescript_file"),
    "_parse_vala_file": (_simple_parser_dispatch_module, "_parse_vala_file"),
    "_parse_mql5_file": (_simple_parser_dispatch_module, "_parse_mql5_file"),
    "_parse_gams_file": (_simple_parser_dispatch_module, "_parse_gams_file"),
    "_parse_nix_file": (_simple_parser_dispatch_module, "_parse_nix_file"),
    "_parse_nushell_file": (_simple_parser_dispatch_module, "_parse_nushell_file"),
    "_parse_fish_file": (_fish_parser_dispatch_module, "_parse_fish_file"),
    "_parse_openscad_file": (_simple_parser_dispatch_module, "_parse_openscad_file"),
    "_parse_purescript_file": (_simple_parser_dispatch_module, "_parse_purescript_file"),
    "_parse_gleam_file": (_simple_parser_dispatch_module, "_parse_gleam_file"),
    "_parse_janet_file": (_janet_parser_dispatch_module, "_parse_janet_file"),
    "_parse_haxe_file": (_simple_parser_dispatch_module, "_parse_haxe_file"),
    "_parse_autohotkey_file": (_simple_parser_dispatch_module, "_parse_autohotkey_file"),
    "_parse_autoit_file": (_autoit_parser_dispatch_module, "_parse_autoit_file"),
    "_parse_squirrel_file": (_squirrel_parser_dispatch_module, "_parse_squirrel_file"),
    "_parse_starlark_file": (_simple_parser_dispatch_module, "_parse_starlark_file"),
    "_parse_vimscript_file": (_simple_parser_dispatch_module, "_parse_vimscript_file"),
    "_parse_v_file": (_simple_parser_dispatch_module, "_parse_v_file"),
    "_parse_smalltalk_file": (_simple_parser_dispatch_module, "_parse_smalltalk_file"),
    "_parse_mojo_file": (_simple_parser_dispatch_module, "_parse_mojo_file"),
    "_parse_python_dependencies_only": (_simple_parser_dispatch_module, "_parse_python_dependencies_only"),
    "_parse_c_family_dependencies_only": (_simple_parser_dispatch_module, "_parse_c_family_dependencies_only"),
    "_parse_c_family_file": (_simple_parser_dispatch_module, "_parse_c_family_file"),
    "_parse_zig_dependencies_only": (_simple_parser_dispatch_module, "_parse_zig_dependencies_only"),
    "_parse_zig_file": (_simple_parser_dispatch_module, "_parse_zig_file"),
    "_parse_js_like_dependencies_only": (_simple_parser_dispatch_module, "_parse_js_like_dependencies_only"),
    "_parse_coffeescript_dependencies_only": (_simple_parser_dispatch_module, "_parse_coffeescript_dependencies_only"),
    "_parse_vala_dependencies_only": (_simple_parser_dispatch_module, "_parse_vala_dependencies_only"),
    "_parse_mql5_dependencies_only": (_simple_parser_dispatch_module, "_parse_mql5_dependencies_only"),
    "_parse_gams_dependencies_only": (_simple_parser_dispatch_module, "_parse_gams_dependencies_only"),
    "_parse_nix_dependencies_only": (_simple_parser_dispatch_module, "_parse_nix_dependencies_only"),
    "_parse_nushell_dependencies_only": (_simple_parser_dispatch_module, "_parse_nushell_dependencies_only"),
    "_parse_fish_dependencies_only": (_fish_parser_dispatch_module, "_parse_fish_dependencies_only"),
    "_parse_openscad_dependencies_only": (_simple_parser_dispatch_module, "_parse_openscad_dependencies_only"),
    "_parse_purescript_dependencies_only": (_simple_parser_dispatch_module, "_parse_purescript_dependencies_only"),
    "_parse_gleam_dependencies_only": (_simple_parser_dispatch_module, "_parse_gleam_dependencies_only"),
    "_parse_janet_dependencies_only": (_janet_parser_dispatch_module, "_parse_janet_dependencies_only"),
    "_parse_haxe_dependencies_only": (_simple_parser_dispatch_module, "_parse_haxe_dependencies_only"),
    "_parse_autohotkey_dependencies_only": (_simple_parser_dispatch_module, "_parse_autohotkey_dependencies_only"),
    "_parse_autoit_dependencies_only": (_autoit_parser_dispatch_module, "_parse_autoit_dependencies_only"),
    "_parse_squirrel_dependencies_only": (_squirrel_parser_dispatch_module, "_parse_squirrel_dependencies_only"),
    "_parse_starlark_dependencies_only": (_simple_parser_dispatch_module, "_parse_starlark_dependencies_only"),
    "_parse_vimscript_dependencies_only": (_simple_parser_dispatch_module, "_parse_vimscript_dependencies_only"),
    "_parse_v_dependencies_only": (_simple_parser_dispatch_module, "_parse_v_dependencies_only"),
    "_parse_smalltalk_dependencies_only": (_simple_parser_dispatch_module, "_parse_smalltalk_dependencies_only"),
    "_parse_mojo_dependencies_only": (_simple_parser_dispatch_module, "_parse_mojo_dependencies_only"),
    "_parse_rust_dependencies_only": (_simple_parser_dispatch_module, "_parse_rust_dependencies_only"),
    "_parse_go_dependencies_only": (_simple_parser_dispatch_module, "_parse_go_dependencies_only"),
    "_parse_dart_dependencies_only": (_simple_parser_dispatch_module, "_parse_dart_dependencies_only"),
    "_parse_dart_file": (_simple_parser_dispatch_module, "_parse_dart_file"),
}


def _registered_adapter_dependency_parsers() -> Mapping[str, Any]:
    return _adapter_parser_dispatch_module().REGISTERED_ADAPTER_DEPENDENCY_PARSERS


def _registered_adapter_file_parsers() -> Mapping[str, Any]:
    return _adapter_parser_dispatch_module().REGISTERED_ADAPTER_FILE_PARSERS


def _repository_capabilities_response_model():
    from apps.api_server.schemas.repositories import (
        RepositoryIntelligenceCapabilitiesResponse,
    )

    return RepositoryIntelligenceCapabilitiesResponse


def _simulation_request_expert_model():
    from apps.api_server.schemas.simulate import SimulateRequestExpert

    return SimulateRequestExpert


def _decision_plan_model():
    from apps.api_server.schemas.response import DecisionPlan

    return DecisionPlan


RepositoryIntelligenceError = repository_contracts.RepositoryIntelligenceError
from apps.api_server.schemas.repositories import (  # noqa: E402
    RepositoryGraphQueryRequest as RepositoryGraphQueryRequest,
)
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
_write_cache_json_atomic = repository_runtime_module._write_cache_json_atomic

_file_analysis_context_hash = repository_cache._file_analysis_context_hash
_dependency_analysis_cache_key = repository_cache._dependency_analysis_cache_key
_dependency_analysis_cache_path = repository_cache._dependency_analysis_cache_path
_file_analysis_cache_key = repository_cache._file_analysis_cache_key
_file_analysis_cache_path = repository_cache._file_analysis_cache_path
_load_dependency_analysis_cache = repository_cache._load_dependency_analysis_cache
_load_file_analysis_cache = repository_cache._load_file_analysis_cache
_serialize_dependency_analysis = repository_cache._serialize_dependency_analysis
_serialize_file_analysis = repository_cache._serialize_file_analysis

# NOTE: _build_module_index is intentionally NOT bound here. The modularization test
# requires identity with module_aliases._build_module_index while the lazy-load test
# requires module_aliases to stay unimported at core import; core's __getattr__ resolves
# it on first access (returning the real function). Internal callers use
# _module_aliases_module()._build_module_index.

_patch_changed_files = repository_patch_analysis._patch_changed_files
_top_level_service = repository_patch_analysis._top_level_service
_is_test_path = repository_patch_analysis._is_test_path




__all__ = [
    "_LAZY_MODULE_ATTR_EXPORTS",
    "_adapter_parser_dispatch_module",
    "_analysis_workflow_module",
    "_autoit_parser_dispatch_module",
    "_decision_plan_workflow_module",
    "_execution_workflow_module",
    "_fish_parser_dispatch_module",
    "_file_selection_module",
    "_graph_workflow_module",
    "_janet_parser_dispatch_module",
    "_language_resolution_module",
    "_module_aliases_module",
    "_planner_generation_module",
    "_security_analysis_workflow_module",
    "_snapshot_workflow_module",
    "_simple_parser_dispatch_module",
    "_repository_source_module",
    "_repository_storage_module",
    "_squirrel_parser_dispatch_module",
    "_lazy_module_attr",
    "_registered_adapter_dependency_parsers",
    "_registered_adapter_file_parsers",
    "_repository_capabilities_response_model",
    "_simulation_request_expert_model",
    "_decision_plan_model",
    "RepositoryIntelligenceError",
    "_Dependency",
    "_DeterministicConfigPatch",
    "_DeterministicLiteralPatch",
    "_FileAnalysis",
    "_InlineConnector",
    "_InlineConnectorType",
    "_estimate_tokens",
    "_language_for_path",
    "_DEFAULT_EXCLUDED_PATH_PARTS",
    "_build_workspace_package_index",
    "_build_workspace_go_module_index",
    "_stable_identifier",
    "_utc_now",
    "_coerce_scope_uuid",
    "_hash_payload",
    "_apply_dir",
    "_decision_plans_dir",
    "_lookup_response_payload",
    "_read_json",
    "_simulation_lookup_dir",
    "_simulations_dir",
    "_triage_dir",
    "_write_json",
    "_write_json_atomic",
    "_write_cache_json_atomic",
    "_file_analysis_context_hash",
    "_dependency_analysis_cache_key",
    "_dependency_analysis_cache_path",
    "_file_analysis_cache_key",
    "_file_analysis_cache_path",
    "_load_dependency_analysis_cache",
    "_load_file_analysis_cache",
    "_serialize_dependency_analysis",
    "_serialize_file_analysis",
    "_patch_changed_files",
    "_top_level_service",
    "_is_test_path",
    "RepositoryGraphQueryRequest",
]


