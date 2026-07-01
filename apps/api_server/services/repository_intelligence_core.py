from __future__ import annotations

import hashlib
import os as _os
import uuid
from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apps.api_server.services import (
    repository_intelligence_cache as repository_cache,
)
from apps.api_server.services import (
    repository_intelligence_contracts as repository_contracts,
)
from apps.api_server.services import (
    repository_intelligence_indexing as repository_indexing,
)
from apps.api_server.services import (
    repository_intelligence_inventory as repository_inventory,
)
from apps.api_server.services import (
    repository_intelligence_patch_analysis as repository_patch_analysis,
)
from apps.api_server.services import (
    repository_intelligence_runtime as repository_runtime_module,
)
from apps.api_server.services import (
    repository_intelligence_shared as repository_shared_module,
)
from apps.api_server.services.repository_language_priority import (
    repository_language_support_progress,
    supported_repository_languages,
)

if TYPE_CHECKING:
    from apps.api_server.models.data_connector import DataConnector
    from apps.api_server.schemas.repositories import (
        RepositoryApplyRequest,
        RepositoryApplyResponse,
        RepositoryDecisionPlanCreateRequest,
        RepositoryDecisionPlanResponse,
        RepositoryGraphQueryRequest,
        RepositoryGraphQueryResponse,
        RepositoryIntelligenceCapabilitiesResponse,
        RepositorySimulatePatchRequest,
        RepositorySimulationRequest,
        RepositorySnapshotCreateRequest,
        RepositorySnapshotResponse,
        RepositoryTriageRequest,
        RepositoryTriageResponse,
    )
    from apps.api_server.schemas.response import DecisionEnvelope, DecisionPlan
    from apps.api_server.schemas.simulate import SimulateRequestExpert

os = _os

_ADAPTER_PARSER_DISPATCH_EXPORT_NAMES = frozenset(
    {
        "_REGISTERED_ADAPTER_DEPENDENCY_PARSERS",
        "_REGISTERED_ADAPTER_FILE_PARSERS",
        "_parse_jvm_dependencies_only",
        "_parse_jvm_file",
        "_parse_r_dependencies_only",
        "_parse_r_file",
    }
)

get_policy = None  # re-export slot (monkeypatchable as core.get_policy)


def _get_policy_callable():
    if get_policy is not None:
        return get_policy
    from apps.api_server.services.execution_policy_service import (
        get_policy as _get_policy,
    )

    return _get_policy


run_simulation_fast = None  # re-export slot (monkeypatchable as core.run_simulation_fast)


def _run_simulation_fast_callable():
    if run_simulation_fast is not None:
        return run_simulation_fast
    from apps.api_server.services.simulation_service import (
        run_simulation_fast as _run_simulation_fast,
    )

    return _run_simulation_fast



_REPOSITORY_INTELLIGENCE_ENGINE_REVISION = "repository-intelligence-v2026-06-07-r124"
_DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID = "repository.deterministic_local_v1"
_VERIFIED_AGENTIC_REPOSITORY_MODEL_ID = "repository.verified_agentic_v1"
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


# Lazy submodule loaders + compat re-export bindings live in
# repository_intelligence_core_bindings (split out to keep this module within the
# per-module line budget). Star-import them so callers keep resolving them from core.
from apps.api_server.schemas.repositories import (  # noqa: E402
    SecurityAnalysisClosureRequest,
    SecurityAnalysisClosureResponse,
    SecurityAnalysisRequest,
    SecurityAnalysisResponse,
)
from apps.api_server.services.repository_intelligence_core_bindings import *  # noqa: E402,F401,F403
from apps.api_server.services.repository_intelligence_core_bindings import (  # noqa: E402
    _LAZY_MODULE_ATTR_EXPORTS,
    _adapter_parser_dispatch_module,
    _file_selection_module,
    _module_aliases_module,
    _registered_adapter_dependency_parsers,
    _registered_adapter_file_parsers,
    _repository_source_module,
    _security_analysis_workflow_module,
)


def _module_self() -> Any:
    import sys

    return sys.modules[__name__]


def _require_repository_connector(*args: Any, **kwargs: Any) -> None:
    _repository_source_module()._require_repository_connector(*args, **kwargs)


def _repo_access_token(*args: Any, **kwargs: Any) -> str | None:
    return _repository_source_module()._repo_access_token(*args, **kwargs)


def _repository_url(*args: Any, **kwargs: Any) -> str | None:
    return _repository_source_module()._repository_url(*args, **kwargs)


def _authenticated_repository_url(*args: Any, **kwargs: Any) -> str:
    return _repository_source_module()._authenticated_repository_url(*args, **kwargs)


# Names re-exported from lazily-loaded submodules but required to keep *identity* with
# the real function (the modularization tests assert e.g.
# ``core._build_module_index is module_aliases._build_module_index``). Resolving them
# through ``__getattr__`` keeps the submodule unimported until first access (the lazy-load
# tests guard that importing core leaves these modules unloaded) while still handing back
# the genuine function object. Internal call sites reference the submodule loader directly.
_REPOSITORY_SOURCE_IDENTITY_EXPORTS = frozenset(
    {
        "_parse_connector_config",
        "_git_command",
        "_git_tracked_content_hashes",
        "resolved_repository_source",
    }
)
_MODULE_ALIASES_IDENTITY_EXPORTS = frozenset({"_build_module_index"})
_FILE_SELECTION_IDENTITY_EXPORTS = frozenset(
    {
        "_append_repository_file",
        "_compact_repository_focus_paths",
        "_detected_repository_file_language",
        "_iter_repository_files",
        "_path_is_indexable_repository_file",
    }
)
_STORAGE_IDENTITY_EXPORTS = frozenset(
    {
        "_hash_file",
        "materialized_snapshot",
        "_load_snapshot_manifest",
        "_load_triage_manifest",
        "_load_decision_plan_manifest",
        "_load_patch_impact_manifest",
        "_load_simulation_manifest",
    }
)


def __getattr__(name: str) -> Any:
    if name == "REPOSITORY_CONNECTOR_TYPES":
        return _repository_source_module().REPOSITORY_CONNECTOR_TYPES
    if name in _REPOSITORY_SOURCE_IDENTITY_EXPORTS:
        return getattr(_repository_source_module(), name)
    if name in _MODULE_ALIASES_IDENTITY_EXPORTS:
        return getattr(_module_aliases_module(), name)
    if name in _FILE_SELECTION_IDENTITY_EXPORTS:
        return getattr(_file_selection_module(), name)
    if name in _STORAGE_IDENTITY_EXPORTS:
        return getattr(_repository_storage_module(), name)
    _lazy_export = _LAZY_MODULE_ATTR_EXPORTS.get(name)
    if _lazy_export is not None:
        module_loader, attr = _lazy_export
        return getattr(module_loader(), attr)
    if name in _ADAPTER_PARSER_DISPATCH_EXPORT_NAMES:
        adapter_parser_dispatch = _adapter_parser_dispatch_module()
        if name == "_REGISTERED_ADAPTER_DEPENDENCY_PARSERS":
            return _registered_adapter_dependency_parsers()
        if name == "_REGISTERED_ADAPTER_FILE_PARSERS":
            return _registered_adapter_file_parsers()
        return getattr(adapter_parser_dispatch, name)

    from apps.api_server.services import (
        repository_intelligence_compat_exports as repository_compat_exports,
    )

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
    adapter_parser_dispatch = _adapter_parser_dispatch_module()
    return _analysis_workflow_module()._analyze_file_dependencies(
        root_path=root_path,
        path=path,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        path_is_indexable_repository_file=_file_selection_module()._path_is_indexable_repository_file,
        language_for_path=_language_for_path,
        registered_adapter_dependency_parsers=_registered_adapter_dependency_parsers(),
        parse_r_dependencies_only=adapter_parser_dispatch._parse_r_dependencies_only,
        parse_dart_dependencies_only=_simple_parser_dispatch_module()._parse_dart_dependencies_only,
        parse_python_dependencies_only=_simple_parser_dispatch_module()._parse_python_dependencies_only,
        parse_c_family_dependencies_only=_simple_parser_dispatch_module()._parse_c_family_dependencies_only,
        parse_zig_dependencies_only=_simple_parser_dispatch_module()._parse_zig_dependencies_only,
        parse_coffeescript_dependencies_only=_simple_parser_dispatch_module()._parse_coffeescript_dependencies_only,
        parse_vala_dependencies_only=_simple_parser_dispatch_module()._parse_vala_dependencies_only,
        parse_mql5_dependencies_only=_simple_parser_dispatch_module()._parse_mql5_dependencies_only,
        parse_gams_dependencies_only=_simple_parser_dispatch_module()._parse_gams_dependencies_only,
        parse_nix_dependencies_only=_simple_parser_dispatch_module()._parse_nix_dependencies_only,
        parse_nushell_dependencies_only=_simple_parser_dispatch_module()._parse_nushell_dependencies_only,
        parse_fish_dependencies_only=_fish_parser_dispatch_module()._parse_fish_dependencies_only,
        parse_openscad_dependencies_only=_simple_parser_dispatch_module()._parse_openscad_dependencies_only,
        parse_purescript_dependencies_only=_simple_parser_dispatch_module()._parse_purescript_dependencies_only,
        parse_gleam_dependencies_only=_simple_parser_dispatch_module()._parse_gleam_dependencies_only,
        parse_janet_dependencies_only=_janet_parser_dispatch_module()._parse_janet_dependencies_only,
        parse_haxe_dependencies_only=_simple_parser_dispatch_module()._parse_haxe_dependencies_only,
        parse_autohotkey_dependencies_only=_simple_parser_dispatch_module()._parse_autohotkey_dependencies_only,
        parse_autoit_dependencies_only=_autoit_parser_dispatch_module()._parse_autoit_dependencies_only,
        parse_squirrel_dependencies_only=_squirrel_parser_dispatch_module()._parse_squirrel_dependencies_only,
        parse_starlark_dependencies_only=_simple_parser_dispatch_module()._parse_starlark_dependencies_only,
        parse_vimscript_dependencies_only=_simple_parser_dispatch_module()._parse_vimscript_dependencies_only,
        parse_v_dependencies_only=_simple_parser_dispatch_module()._parse_v_dependencies_only,
        parse_smalltalk_dependencies_only=_simple_parser_dispatch_module()._parse_smalltalk_dependencies_only,
        parse_js_like_dependencies_only=_simple_parser_dispatch_module()._parse_js_like_dependencies_only,
        parse_go_dependencies_only=_simple_parser_dispatch_module()._parse_go_dependencies_only,
        parse_jvm_dependencies_only=adapter_parser_dispatch._parse_jvm_dependencies_only,
        parse_rust_dependencies_only=_simple_parser_dispatch_module()._parse_rust_dependencies_only,
        parse_mojo_dependencies_only=_simple_parser_dispatch_module()._parse_mojo_dependencies_only,
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
    return _analysis_workflow_module()._analyze_file_dependencies_cached(
        root_path=root_path,
        path=path,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        analysis_context_hash=analysis_context_hash,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        hash_file=_module_self()._hash_file,
        dependency_analysis_cache_key=_dependency_analysis_cache_key,
        dependency_analysis_cache_path=_dependency_analysis_cache_path,
        load_dependency_analysis_cache=_load_dependency_analysis_cache,
        serialize_dependency_analysis=_serialize_dependency_analysis,
        write_json_atomic=_write_cache_json_atomic,
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
    adapter_parser_dispatch = _adapter_parser_dispatch_module()
    return _analysis_workflow_module()._analyze_file(
        root_path=root_path,
        path=path,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        hash_file=_module_self()._hash_file,
        path_is_indexable_repository_file=_file_selection_module()._path_is_indexable_repository_file,
        language_for_path=_language_for_path,
        estimate_tokens=_estimate_tokens,
        registered_adapter_file_parsers=_registered_adapter_file_parsers(),
        parse_r_file=adapter_parser_dispatch._parse_r_file,
        parse_dart_file=_simple_parser_dispatch_module()._parse_dart_file,
        parse_python_file=_simple_parser_dispatch_module()._parse_python_file,
        parse_c_family_file=_simple_parser_dispatch_module()._parse_c_family_file,
        parse_zig_file=_simple_parser_dispatch_module()._parse_zig_file,
        parse_rust_file=_simple_parser_dispatch_module()._parse_rust_file,
        parse_mojo_file=_simple_parser_dispatch_module()._parse_mojo_file,
        parse_coffeescript_file=_simple_parser_dispatch_module()._parse_coffeescript_file,
        parse_vala_file=_simple_parser_dispatch_module()._parse_vala_file,
        parse_mql5_file=_simple_parser_dispatch_module()._parse_mql5_file,
        parse_gams_file=_simple_parser_dispatch_module()._parse_gams_file,
        parse_nix_file=_simple_parser_dispatch_module()._parse_nix_file,
        parse_nushell_file=_simple_parser_dispatch_module()._parse_nushell_file,
        parse_fish_file=_fish_parser_dispatch_module()._parse_fish_file,
        parse_openscad_file=_simple_parser_dispatch_module()._parse_openscad_file,
        parse_purescript_file=_simple_parser_dispatch_module()._parse_purescript_file,
        parse_gleam_file=_simple_parser_dispatch_module()._parse_gleam_file,
        parse_janet_file=_janet_parser_dispatch_module()._parse_janet_file,
        parse_haxe_file=_simple_parser_dispatch_module()._parse_haxe_file,
        parse_autohotkey_file=_simple_parser_dispatch_module()._parse_autohotkey_file,
        parse_autoit_file=_autoit_parser_dispatch_module()._parse_autoit_file,
        parse_squirrel_file=_squirrel_parser_dispatch_module()._parse_squirrel_file,
        parse_starlark_file=_simple_parser_dispatch_module()._parse_starlark_file,
        parse_vimscript_file=_simple_parser_dispatch_module()._parse_vimscript_file,
        parse_v_file=_simple_parser_dispatch_module()._parse_v_file,
        parse_smalltalk_file=_simple_parser_dispatch_module()._parse_smalltalk_file,
        parse_js_like_file=_simple_parser_dispatch_module()._parse_js_like_file,
        parse_go_file=_simple_parser_dispatch_module()._parse_go_file,
        parse_jvm_file=adapter_parser_dispatch._parse_jvm_file,
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
    return _analysis_workflow_module()._analyze_file_cached(
        root_path=root_path,
        path=path,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        analysis_context_hash=analysis_context_hash,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        hash_file=_module_self()._hash_file,
        file_analysis_cache_key=_file_analysis_cache_key,
        file_analysis_cache_path=_file_analysis_cache_path,
        load_file_analysis_cache=_load_file_analysis_cache,
        serialize_file_analysis=_serialize_file_analysis,
        write_json_atomic=_write_cache_json_atomic,
        analyze_file=_analyze_file,
        git_content_hashes=git_content_hashes,
    )


def _snapshot_analysis_max_workers(file_count: int) -> int:
    return _analysis_workflow_module()._snapshot_analysis_max_workers(file_count)


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
    return _analysis_workflow_module()._analyze_snapshot_files(
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
    return _snapshot_workflow_module().create_repository_snapshot(
        connector=connector,
        request=request,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        require_repository_connector=_require_repository_connector,
        parse_connector_config=_repository_source_module()._parse_connector_config,
        resolved_repository_source=_repository_source_module().resolved_repository_source,
        compact_repository_focus_paths=_file_selection_module()._compact_repository_focus_paths,
        iter_repository_files=_file_selection_module()._iter_repository_files,
        build_module_index=_module_aliases_module()._build_module_index,
        build_workspace_package_index=_build_workspace_package_index,
        build_workspace_go_module_index=_build_workspace_go_module_index,
        git_tracked_content_hashes=_repository_source_module()._git_tracked_content_hashes,
        file_analysis_context_hash=_file_analysis_context_hash,
        analyze_snapshot_files=_analyze_snapshot_files,
        augment_r_package_symbol_references=_language_resolution_module()._augment_r_package_symbol_references,
        augment_julia_package_symbol_references=_language_resolution_module()._augment_julia_package_symbol_references,
        resolve_symbol_reference_target=_language_resolution_module()._resolve_symbol_reference_target,
        hash_file=_module_self()._hash_file,
        write_bytes_with_hash=_write_bytes_with_hash,
    )


def get_repository_snapshot(
    *, connector: DataConnector, snapshot_id: str
) -> RepositorySnapshotResponse:
    return _snapshot_workflow_module().get_repository_snapshot(
        connector=connector,
        snapshot_id=snapshot_id,
        require_repository_connector=_require_repository_connector,
        load_snapshot_manifest=_repository_storage_module()._load_snapshot_manifest,
    )


def get_repository_intelligence_capabilities() -> RepositoryIntelligenceCapabilitiesResponse:
    progress = repository_language_support_progress()
    return _repository_capabilities_response_model().model_validate(
        {
            "supported_languages": list(supported_repository_languages()),
            "support_progress": {
                "supported_real_language_count": progress.supported_real_language_count,
                "ranked_target_language_count": progress.ranked_target_language_count,
                "requested_ranked_target_language_count": (
                    progress.requested_ranked_target_language_count
                ),
                "available_ranked_real_language_count": (
                    progress.available_ranked_real_language_count
                ),
                "target_clamped_to_available_ranked_real_languages": (
                    progress.target_clamped_to_available_ranked_real_languages
                ),
                "progress_fraction": progress.progress_fraction,
                "progress_label": progress.progress_label,
            },
        }
    )


def query_repository_graph(
    *, connector: DataConnector, request: RepositoryGraphQueryRequest
) -> RepositoryGraphQueryResponse:
    return _graph_workflow_module().query_repository_graph(
        connector=connector,
        request=request,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        require_repository_connector=_require_repository_connector,
        load_snapshot_manifest=_repository_storage_module()._load_snapshot_manifest,
        load_triage_manifest=_repository_storage_module()._load_triage_manifest,
        read_json=_read_json,
    )


def triage_repository(
    *, connector: DataConnector, request: RepositoryTriageRequest
) -> RepositoryTriageResponse:
    return _graph_workflow_module().triage_repository(
        connector=connector,
        request=request,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        require_repository_connector=_require_repository_connector,
        load_snapshot_manifest=_repository_storage_module()._load_snapshot_manifest,
        read_json=_read_json,
        materialized_snapshot=_repository_storage_module().materialized_snapshot,
    )


# --- Security-analyses reachability proofs (codna contract) -----------------------


def _security_safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9._-]", "_", str(value))[:200] or "finding"


def _codna_patch_digest(diff: str) -> str:
    """Match codna's findings.digest_of(diff): 'sha256:' + sha256(json.dumps(diff)). The engine
    stores diffs with its own raw hash, so closure must recompute codna's scheme to match."""
    import hashlib
    import json

    payload = json.dumps(diff, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _persist_security_proofs(
    *, connector: DataConnector, response: SecurityAnalysisResponse
) -> None:
    """Best-effort: persist each per-finding proof so closure can recover the obligation later.
    If this fails, closure simply degrades to 'unknown' (never crashes the endpoint)."""
    from apps.api_server.services import repository_intelligence_runtime as repository_runtime

    org_id = str(connector.org_id)
    repository_id = str(connector.id)
    base = repository_runtime._security_analyses_dir(org_id, repository_id) / "by_finding"
    try:
        base.mkdir(parents=True, exist_ok=True)
        for proof in response.proofs:
            repository_runtime._write_json(
                base / f"{_security_safe_id(proof.canonical_finding_id)}.json",
                {
                    "analysis_id": response.analysis_id,
                    "snapshot_id": response.snapshot.id,
                    "proof": proof.model_dump(mode="json"),
                },
            )
    except OSError:
        pass


def _load_security_proof_by_finding(
    *, org_id: str, repository_id: str, canonical_finding_id: str, snapshot_id: str | None = None
) -> dict[str, Any] | None:
    from apps.api_server.services import repository_intelligence_runtime as repository_runtime

    path = (
        repository_runtime._security_analyses_dir(org_id, repository_id)
        / "by_finding"
        / f"{_security_safe_id(canonical_finding_id)}.json"
    )
    try:
        if path.exists():
            return repository_runtime._read_json(path).get("proof")
    except (OSError, ValueError):
        pass
    return None


def _load_patch_diff_by_digest(*, org_id: str, repository_id: str, patch_digest: str) -> str | None:
    from apps.api_server.services import repository_intelligence_runtime as repository_runtime

    plans_dir = repository_runtime._decision_plans_dir(org_id, repository_id)
    try:
        manifests = sorted(plans_dir.glob("*.json"))
    except OSError:
        return None
    for manifest_path in manifests:
        try:
            manifest = repository_runtime._read_json(manifest_path)
        except (OSError, ValueError):
            continue
        diff = manifest.get("patch_diff")
        if not diff and manifest.get("patch_path"):
            try:
                diff = Path(manifest["patch_path"]).read_text(encoding="utf-8")
            except OSError:
                diff = None
        if diff and _codna_patch_digest(diff) == patch_digest:
            return diff
    return None


def _security_analysis_lookup_key(request: SecurityAnalysisRequest) -> str:
    from apps.api_server.services.repository_intelligence_shared import _stable_identifier

    return _stable_identifier(
        "security_analysis_lookup",
        {
            "engine_revision": _REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
            "snapshot_id": request.snapshot_id,
            "sarif_digest": request.sarif_digest,
            "policy_digest": request.policy_digest,
            "model_pack_digest": request.model_pack_digest,
            "scanner": request.scanner.model_dump(mode="json"),
            "findings": sorted(f.canonical_id for f in request.findings),
        },
    )


def analyze_repository_security(
    *, connector: DataConnector, request: SecurityAnalysisRequest
) -> SecurityAnalysisResponse:
    from apps.api_server.services import repository_intelligence_runtime as repository_runtime
    from apps.api_server.services.repository_intelligence_lookup_store import (
        mirror_lookup,
        read_lookup_shared,
    )

    _require_repository_connector(connector)
    org_id = str(connector.org_id)
    repository_id = str(connector.id)
    lookup_key = _security_analysis_lookup_key(request)
    lookup_dir = repository_runtime._security_analysis_lookup_dir(org_id, repository_id)
    lookup_path = lookup_dir / f"{lookup_key}.json"

    # build-once / query-many: node-local cache first (warm fast path), then the shared
    # cross-replica cache (s3 only). A miss/fault just recomputes the identical result.
    try:
        if lookup_path.exists():
            cached = repository_runtime._read_json(lookup_path).get("response")
            if cached:
                return SecurityAnalysisResponse.model_validate(cached)
    except (OSError, ValueError):
        pass
    shared = read_lookup_shared(
        org_id=org_id, repository_id=repository_id,
        kind="security_analysis_lookup", lookup_key=lookup_key,
    )
    if shared and shared.get("response"):
        return SecurityAnalysisResponse.model_validate(shared["response"])

    response = _security_analysis_workflow_module().analyze_repository_security_batch(
        connector=connector,
        request=request,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        require_repository_connector=_require_repository_connector,
        load_snapshot_manifest=_repository_storage_module()._load_snapshot_manifest,
    )
    _persist_security_proofs(connector=connector, response=response)
    payload = {"lookup_key": lookup_key, "response": response.model_dump(mode="json")}
    try:
        lookup_dir.mkdir(parents=True, exist_ok=True)
        repository_runtime._write_json(lookup_path, payload)
    except OSError:
        pass
    mirror_lookup(
        org_id=org_id, repository_id=repository_id,
        kind="security_analysis_lookup", lookup_key=lookup_key, payload=payload,
    )
    return response


def analyze_repository_security_closure(
    *, connector: DataConnector, request: SecurityAnalysisClosureRequest
) -> SecurityAnalysisClosureResponse:
    return _security_analysis_workflow_module().analyze_repository_security_closure(
        connector=connector,
        request=request,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        require_repository_connector=_require_repository_connector,
        load_security_proof_by_finding=_load_security_proof_by_finding,
        load_patch_diff_by_digest=_load_patch_diff_by_digest,
    )


def _resolve_repository_model(explicit_model: str | None) -> str:
    return _planner_generation_module()._resolve_repository_model(
        explicit_model,
        deterministic_local_model_id=_DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        verified_agentic_model_id=_VERIFIED_AGENTIC_REPOSITORY_MODEL_ID,
    )


def _deterministic_typescript_rootdir_patch(
    *,
    snapshot_manifest: dict[str, Any],
    triage_manifest: dict[str, Any],
    root_path: Path,
) -> _DeterministicConfigPatch:
    return _planner_generation_module()._deterministic_typescript_rootdir_patch(
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
    return _planner_generation_module()._deterministic_python_return_literal_patch(
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
    return _planner_generation_module()._generate_deterministic_repository_patch_plan(
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
    return await _planner_generation_module()._generate_repository_patch_plan(
        model_id=model_id,
        snapshot_manifest=snapshot_manifest,
        triage_manifest=triage_manifest,
        deterministic_local_model_id=_DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        verified_agentic_model_id=_VERIFIED_AGENTIC_REPOSITORY_MODEL_ID,
    )


def _validate_patch_against_snapshot(*, snapshot_manifest: dict[str, Any], patch_diff: str) -> None:
    repository_patch_analysis._validate_patch_against_snapshot(
        snapshot_manifest=snapshot_manifest,
        patch_diff=patch_diff,
        materialized_snapshot=_repository_storage_module().materialized_snapshot,
        git_command=_repository_source_module()._git_command,
    )


def _patch_impact_summary(snapshot_manifest: dict[str, Any], patch_diff: str) -> dict[str, Any]:
    return _decision_plan_workflow_module()._patch_impact_summary(
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
    return await _decision_plan_workflow_module().create_repository_decision_plan(
        connector=connector,
        request=request,
        engine_revision=_REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
        require_repository_connector=_require_repository_connector,
        resolve_repository_model=_resolve_repository_model,
        read_json=_read_json,
        generate_repository_patch_plan=_generate_repository_patch_plan,
        validate_patch_against_snapshot=_validate_patch_against_snapshot,
        patch_impact_summary=_patch_impact_summary,
        is_test_path=_is_test_path,
    )


def _simulation_request_from_plan(plan: DecisionPlan) -> SimulateRequestExpert:
    _decision_plan_model()
    _simulation_request_expert_model()
    return _execution_workflow_module()._simulation_request_from_plan(plan)


async def simulate_repository_decision(
    *,
    connector: DataConnector,
    request: RepositorySimulationRequest,
) -> DecisionEnvelope:
    return await _execution_workflow_module().simulate_repository_decision(
        connector=connector,
        request=request,
        require_repository_connector=_require_repository_connector,
        get_policy=get_policy,
        load_decision_plan_manifest=_repository_storage_module()._load_decision_plan_manifest,
        simulation_lookup_key=_simulation_lookup_key,
        simulation_lookup_dir=_simulation_lookup_dir,
        read_json=_read_json,
        simulations_dir=_simulations_dir,
        lookup_response_payload=_lookup_response_payload,
        write_json=_write_json,
        load_snapshot_manifest=_repository_storage_module()._load_snapshot_manifest,
        load_patch_impact_manifest=_repository_storage_module()._load_patch_impact_manifest,
        run_simulation_fast=run_simulation_fast,
        utc_now=_utc_now,
        stable_identifier=_stable_identifier,
    )


async def simulate_repository_patch(
    *,
    connector: DataConnector,
    request: RepositorySimulatePatchRequest,
) -> DecisionEnvelope:
    return await _execution_workflow_module().simulate_repository_patch(
        connector=connector,
        request=request,
        require_repository_connector=_require_repository_connector,
        get_policy=get_policy,
        load_snapshot_manifest=_repository_storage_module()._load_snapshot_manifest,
        validate_patch_against_snapshot=_validate_patch_against_snapshot,
        patch_impact_summary=_patch_impact_summary,
        run_simulation_fast=run_simulation_fast,
    )


def _patch_text_for_plan(
    *, org_id: str, repository_id: str, decision_plan_manifest: dict[str, Any]
) -> str:
    return _execution_workflow_module()._patch_text_for_plan(
        org_id=org_id,
        repository_id=repository_id,
        decision_plan_manifest=decision_plan_manifest,
    )


def _ensure_clean_git_worktree(path: Path) -> None:
    _execution_workflow_module()._ensure_clean_git_worktree(path, git_command=_repository_source_module()._git_command)


def _apply_patch_to_git_checkout(
    *,
    checkout_path: Path,
    patch_text: str,
    branch_name: str,
    commit_message: str,
    base_branch: str | None,
) -> str:
    return _execution_workflow_module()._apply_patch_to_git_checkout(
        checkout_path=checkout_path,
        patch_text=patch_text,
        branch_name=branch_name,
        commit_message=commit_message,
        base_branch=base_branch,
        git_command=_repository_source_module()._git_command,
    )


def _config_remote_metadata(
    connector_type: str, config: dict[str, Any], repository_url: str
) -> dict[str, str]:
    return _execution_workflow_module()._config_remote_metadata(
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
    return await _execution_workflow_module()._create_pull_request(
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
    return await _execution_workflow_module().apply_repository_decision(
        connector=connector,
        request=request,
        require_repository_connector=_require_repository_connector,
        parse_connector_config=_repository_source_module()._parse_connector_config,
        load_decision_plan_manifest=_repository_storage_module()._load_decision_plan_manifest,
        load_simulation_manifest=_repository_storage_module()._load_simulation_manifest,
        load_snapshot_manifest=_repository_storage_module()._load_snapshot_manifest,
        utc_now=_utc_now,
        patch_changed_files=_patch_changed_files,
        resolved_repository_source=_repository_source_module().resolved_repository_source,
        git_command=_repository_source_module()._git_command,
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
    with _repository_source_module().resolved_repository_source(connector=fake_connector, config=config, ref=None) as source:
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
                        else _file_selection_module()._detected_repository_file_language(path, repo_root=source.root_path)
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
    with _repository_source_module().resolved_repository_source(connector=fake_connector, config=config, ref=None) as source:
        entry_count = sum(1 for _ in source.root_path.rglob("*"))
        source_label = source.repository_url or str(source.root_path)
        return True, f"Repository source reachable: {source_label} ({entry_count} entries)."
