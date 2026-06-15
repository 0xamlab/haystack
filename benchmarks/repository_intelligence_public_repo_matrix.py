from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from functools import lru_cache
import inspect
import json
import os
import re
import signal
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from urllib.parse import urlparse

import benchmarks.repository_intelligence_real_repo_probe as probe_module
from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import (
    repository_intelligence_compat_exports as repository_compat_exports,
)
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import repository_intelligence_cache as repository_cache
from apps.api_server.services import repository_intelligence_file_selection as repository_file_selection
from apps.api_server.services import repository_intelligence_indexing as repository_indexing
from apps.api_server.services import runtime_internal_contracts
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_contracts import RepositoryIntelligenceError
from apps.api_server.services.repository_language_priority import (
    DEFAULT_REAL_LANGUAGE_RANK_TARGET,
    canonical_repository_language,
    repository_language_support_progress,
    sort_repository_languages,
    sort_repository_languages_by_score,
    supported_repository_languages,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "repository_intelligence_public_repo_matrix.json"
DEFAULT_CHECKOUT_ROOT = PROJECT_ROOT / "build" / "repository_intelligence_public_repo_matrix_repos"
MatrixMode = Literal["seed_plan", "probe"]
_SHARED_RUNTIME_DIR_ENV = "ALGENTA_REPOSITORY_INTELLIGENCE_SHARED_RUNTIME_DIR"
_PUBLIC_REPOSITORY_CLONE_ATTEMPTS = 2
_PUBLIC_REPOSITORY_CHECKOUT_LOCK_TIMEOUT_SECONDS = 300.0
_PUBLIC_REPOSITORY_CHECKOUT_LOCK_POLL_INTERVAL_SECONDS = 0.1
# Keep the prepass intentionally small; later focused refinement can widen scope
# when the initial seed-plan slice is insufficient.
_PUBLIC_REPOSITORY_PROBE_FOCUS_PREPASS_MAX_FILES = 32
_PUBLIC_REPOSITORY_PREPASS_FOCUS_LIMIT = 12
_PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE_LIMIT = 256
_PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE: dict[tuple[str, str | None], tuple[str, ...]] = {}
_PUBLIC_REPOSITORY_TRACKED_RELATIVE_FILES_CACHE_LIMIT = 256
_PUBLIC_REPOSITORY_TRACKED_RELATIVE_FILES_CACHE: dict[str, tuple[str, ...]] = {}
_PUBLIC_REPOSITORY_HEAD_REVISION_CACHE_LIMIT = 256
_PUBLIC_REPOSITORY_HEAD_REVISION_CACHE: dict[str, str] = {}
_PUBLIC_REPOSITORY_REUSABLE_CHECKOUT_CACHE_LIMIT = 256
_PUBLIC_REPOSITORY_REUSABLE_CHECKOUT_CACHE: dict[str, bool] = {}
_PUBLIC_REPOSITORY_CANDIDATE_CONFIG_FOCUS_PATH_CACHE_LIMIT = 256
_PUBLIC_REPOSITORY_CANDIDATE_CONFIG_FOCUS_PATH_CACHE: dict[
    tuple[str, str, tuple[str, ...], str | None],
    tuple[str, ...],
] = {}
_PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE_LIMIT = 4096
_PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE: dict[
    tuple[str, str],
    frozenset[str],
] = {}
_PUBLIC_REPOSITORY_SEED_PLAN_RESULT_CACHE_LIMIT = 256
_PUBLIC_REPOSITORY_SEED_PLAN_RESULT_CACHE: dict[
    tuple[str, str, str, tuple[str, ...], int],
    dict[str, Any],
] = {}
_PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE_LIMIT = 256
_PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE: dict[
    tuple[str, str, str, tuple[str, ...], int],
    dict[str, Any] | None,
] = {}
_PUBLIC_REPOSITORY_REFINED_UNSCOPED_PROBE_PLAN_CACHE_LIMIT = 256
_PUBLIC_REPOSITORY_REFINED_UNSCOPED_PROBE_PLAN_CACHE: dict[
    tuple[str, str, str, int],
    tuple[dict[str, Any], tuple[str, ...]],
] = {}
_ExpectedEcosystemHintMetadata = tuple[
    Any,
    bool,
    frozenset[str],
    frozenset[str],
]
_EXPECTED_ECOSYSTEM_HINT_METADATA_CACHE: dict[
    str,
    _ExpectedEcosystemHintMetadata,
] = {}
_VERSIONISH_PATH_PART_RE = re.compile(
    r"^(?:v\d+|\d+(?:[._-]\d+){1,3})(?:[-._]?(?:alpha|beta|pre|preview|rc)\d*)?$",
    re.IGNORECASE,
)
_EMBEDDED_VERSIONISH_PATH_PART_RE = re.compile(
    r"^(?P<prefix>.*?)(?:[\s._-]+)?(?P<version>v?\d+(?:[._-]\d+){1,3}(?:[-._]?(?:alpha|beta|pre|preview|rc)\d*)?)$",
    re.IGNORECASE,
)
_EMBEDDED_ALPHA_PREFIXED_VERSIONISH_PATH_PART_RE = re.compile(
    r"^(?P<prefix>.*?)(?:[\s._-]+)(?P<family>[a-z]{1,4})(?P<version>\d+(?:[._-]\d+){0,3}(?:[-._]?(?:alpha|beta|pre|preview|rc)\d*)?)$",
    re.IGNORECASE,
)
_PUBLIC_REPOSITORY_RESOLVED_OID_RE = re.compile(r"^[0-9a-f]{40}$")


class PublicRepositoryCaseTimeoutError(TimeoutError):
    """Raised when a public repository matrix case exceeds its timeout."""


@lru_cache(maxsize=1)
def _profile_path_classification_support_module():
    from benchmarks import (
        repository_intelligence_real_repo_probe_profile_path_classification_support as path_classification_support,
    )

    return path_classification_support


def prime_public_repository_probe_runtime() -> None:
    initialize_pyarrow_parquet_runtime()
    runtime_internal_contracts.warm_repository_snapshot_parquet_contracts()
    repository_cache._analysis_implementation_fingerprint()
    repository_service._adapter_parser_dispatch_module()
    repository_service._analysis_workflow_module()


def clear_public_repository_prepass_focus_path_cache() -> None:
    clear_public_repository_probe_attempt_cache()


def clear_public_repository_probe_attempt_cache(
    *,
    preserve_prepass_focus_paths: bool = False,
    preserve_seed_plan_results: bool = False,
    preserve_path_candidate_ecosystems: bool = False,
    preserve_expected_ecosystem_hints: bool = False,
) -> None:
    if not preserve_prepass_focus_paths:
        _PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE.clear()
        _PUBLIC_REPOSITORY_TRACKED_RELATIVE_FILES_CACHE.clear()
        _PUBLIC_REPOSITORY_HEAD_REVISION_CACHE.clear()
        _PUBLIC_REPOSITORY_REUSABLE_CHECKOUT_CACHE.clear()
        _PUBLIC_REPOSITORY_CANDIDATE_CONFIG_FOCUS_PATH_CACHE.clear()
    if not preserve_seed_plan_results:
        _PUBLIC_REPOSITORY_SEED_PLAN_RESULT_CACHE.clear()
        _PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE.clear()
        _PUBLIC_REPOSITORY_REFINED_UNSCOPED_PROBE_PLAN_CACHE.clear()
    if not preserve_path_candidate_ecosystems:
        _PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE.clear()
    if not preserve_expected_ecosystem_hints:
        _EXPECTED_ECOSYSTEM_HINT_METADATA_CACHE.clear()
        _expected_ecosystem_static_hint_suffixes.cache_clear()
        _expected_ecosystem_hint_pathspecs.cache_clear()
        _path_basename_and_suffix.cache_clear()
        _static_language_hint_for_path.cache_clear()
        _path_matches_expected_ecosystem_hint_cached.cache_clear()


def _invalidate_public_repository_checkout_caches(repo_path: Path) -> None:
    repo_cache_key = str(_normalized_public_repository_repo_path(repo_path))
    _PUBLIC_REPOSITORY_TRACKED_RELATIVE_FILES_CACHE.pop(repo_cache_key, None)
    _PUBLIC_REPOSITORY_HEAD_REVISION_CACHE.pop(repo_cache_key, None)
    _PUBLIC_REPOSITORY_REUSABLE_CHECKOUT_CACHE.pop(repo_cache_key, None)
    for cache_key in tuple(_PUBLIC_REPOSITORY_CANDIDATE_CONFIG_FOCUS_PATH_CACHE):
        if cache_key[0] == repo_cache_key:
            _PUBLIC_REPOSITORY_CANDIDATE_CONFIG_FOCUS_PATH_CACHE.pop(cache_key, None)
    for cache_key in tuple(_PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE):
        if cache_key[0] == repo_cache_key:
            _PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE.pop(cache_key, None)
    for cache_key in tuple(_PUBLIC_REPOSITORY_SEED_PLAN_RESULT_CACHE):
        if cache_key[0] == repo_cache_key:
            _PUBLIC_REPOSITORY_SEED_PLAN_RESULT_CACHE.pop(cache_key, None)
    for cache_key in tuple(_PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE):
        if cache_key[0] == repo_cache_key:
            _PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE.pop(cache_key, None)
    for cache_key in tuple(_PUBLIC_REPOSITORY_REFINED_UNSCOPED_PROBE_PLAN_CACHE):
        if cache_key[0] == repo_cache_key:
            _PUBLIC_REPOSITORY_REFINED_UNSCOPED_PROBE_PLAN_CACHE.pop(cache_key, None)
    for cache_key in tuple(_PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE):
        if cache_key[0] == repo_cache_key:
            _PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE.pop(cache_key, None)


def _public_repository_probe_focus_prepass_max_files(max_files: int) -> int:
    return max(1, min(max_files, _PUBLIC_REPOSITORY_PROBE_FOCUS_PREPASS_MAX_FILES))


def _normalized_public_repository_repo_path(repo_path: Path) -> Path:
    return repo_path if repo_path.is_absolute() else repo_path.resolve()


def _public_repository_tracked_relative_files_cache_key(repo_path: Path) -> str:
    return str(_normalized_public_repository_repo_path(repo_path))


def _public_repository_head_revision_cache_key(repo_path: Path) -> str:
    return str(_normalized_public_repository_repo_path(repo_path))


def _public_repository_reusable_checkout_cache_key(repo_path: Path) -> str:
    return str(_normalized_public_repository_repo_path(repo_path))


def _public_repository_case_shared_runtime_dir(
    *,
    runtime_root: Path,
    case: PublicRepositoryCase,
) -> Path:
    return runtime_root / "_shared_cases" / _case_checkout_name(case)


def _public_repository_candidate_config_focus_paths_cache_key(
    *,
    repo_path: Path,
    focus_paths: list[str],
    diagnostic_base_path: Path,
    diagnostic_project_path: str | None,
) -> tuple[str, str, tuple[str, ...], str | None]:
    normalized_focus_paths = tuple(
        _normalized_public_repository_focus_paths(list(focus_paths))
    )
    normalized_base_path = (
        diagnostic_base_path
        if diagnostic_base_path.is_absolute()
        else diagnostic_base_path.resolve()
    )
    normalized_project_path = probe_module.repository_service._normalize_repository_relative_path(
        diagnostic_project_path
    )
    return (
        str(_normalized_public_repository_repo_path(repo_path)),
        str(normalized_base_path),
        normalized_focus_paths,
        normalized_project_path,
    )


def _cached_public_repository_candidate_config_focus_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    diagnostic_base_path: Path,
    diagnostic_project_path: str | None,
) -> list[str] | None:
    cached_focus_paths = _PUBLIC_REPOSITORY_CANDIDATE_CONFIG_FOCUS_PATH_CACHE.get(
        _public_repository_candidate_config_focus_paths_cache_key(
            repo_path=repo_path,
            focus_paths=focus_paths,
            diagnostic_base_path=diagnostic_base_path,
            diagnostic_project_path=diagnostic_project_path,
        )
    )
    if cached_focus_paths is None:
        return None
    return list(cached_focus_paths)


def _store_public_repository_candidate_config_focus_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    diagnostic_base_path: Path,
    diagnostic_project_path: str | None,
    config_focus_paths: list[str],
) -> list[str]:
    cache_key = _public_repository_candidate_config_focus_paths_cache_key(
        repo_path=repo_path,
        focus_paths=focus_paths,
        diagnostic_base_path=diagnostic_base_path,
        diagnostic_project_path=diagnostic_project_path,
    )
    normalized_config_focus_paths = tuple(
        _normalized_public_repository_focus_paths(list(config_focus_paths))
    )
    if len(_PUBLIC_REPOSITORY_CANDIDATE_CONFIG_FOCUS_PATH_CACHE) >= (
        _PUBLIC_REPOSITORY_CANDIDATE_CONFIG_FOCUS_PATH_CACHE_LIMIT
    ):
        oldest_key = next(iter(_PUBLIC_REPOSITORY_CANDIDATE_CONFIG_FOCUS_PATH_CACHE))
        _PUBLIC_REPOSITORY_CANDIDATE_CONFIG_FOCUS_PATH_CACHE.pop(oldest_key, None)
    _PUBLIC_REPOSITORY_CANDIDATE_CONFIG_FOCUS_PATH_CACHE[cache_key] = (
        normalized_config_focus_paths
    )
    return list(normalized_config_focus_paths)


def _cached_public_repository_head_revision(repo_path: Path) -> str | None:
    cached_revision = _PUBLIC_REPOSITORY_HEAD_REVISION_CACHE.get(
        _public_repository_head_revision_cache_key(repo_path)
    )
    if cached_revision is None:
        return None
    return str(cached_revision)


def _cached_reusable_public_repository_checkout(repo_path: Path) -> bool:
    return (
        _PUBLIC_REPOSITORY_REUSABLE_CHECKOUT_CACHE.get(
            _public_repository_reusable_checkout_cache_key(repo_path)
        )
        is True
    )


def _store_public_repository_head_revision(
    *,
    repo_path: Path,
    resolved_revision: str,
) -> str:
    normalized_revision = str(resolved_revision).strip().lower()
    if _PUBLIC_REPOSITORY_RESOLVED_OID_RE.fullmatch(normalized_revision) is None:
        raise ValueError(f"invalid public repository resolved revision: {resolved_revision}")
    cache_key = _public_repository_head_revision_cache_key(repo_path)
    if len(_PUBLIC_REPOSITORY_HEAD_REVISION_CACHE) >= (
        _PUBLIC_REPOSITORY_HEAD_REVISION_CACHE_LIMIT
    ):
        oldest_key = next(iter(_PUBLIC_REPOSITORY_HEAD_REVISION_CACHE))
        _PUBLIC_REPOSITORY_HEAD_REVISION_CACHE.pop(oldest_key, None)
    _PUBLIC_REPOSITORY_HEAD_REVISION_CACHE[cache_key] = normalized_revision
    return normalized_revision


def _store_reusable_public_repository_checkout(*, repo_path: Path) -> bool:
    cache_key = _public_repository_reusable_checkout_cache_key(repo_path)
    if len(_PUBLIC_REPOSITORY_REUSABLE_CHECKOUT_CACHE) >= (
        _PUBLIC_REPOSITORY_REUSABLE_CHECKOUT_CACHE_LIMIT
    ):
        oldest_key = next(iter(_PUBLIC_REPOSITORY_REUSABLE_CHECKOUT_CACHE))
        _PUBLIC_REPOSITORY_REUSABLE_CHECKOUT_CACHE.pop(oldest_key, None)
    _PUBLIC_REPOSITORY_REUSABLE_CHECKOUT_CACHE[cache_key] = True
    return True


def _cached_public_repository_tracked_relative_files(repo_path: Path) -> list[str] | None:
    cached_relative_paths = _PUBLIC_REPOSITORY_TRACKED_RELATIVE_FILES_CACHE.get(
        _public_repository_tracked_relative_files_cache_key(repo_path)
    )
    if cached_relative_paths is None:
        return None
    return list(cached_relative_paths)


def _cache_public_repository_tracked_relative_files(
    *,
    repo_path: Path,
    normalized_relative_paths: tuple[str, ...],
) -> list[str]:
    cache_key = _public_repository_tracked_relative_files_cache_key(repo_path)
    if len(_PUBLIC_REPOSITORY_TRACKED_RELATIVE_FILES_CACHE) >= (
        _PUBLIC_REPOSITORY_TRACKED_RELATIVE_FILES_CACHE_LIMIT
    ):
        oldest_key = next(iter(_PUBLIC_REPOSITORY_TRACKED_RELATIVE_FILES_CACHE))
        _PUBLIC_REPOSITORY_TRACKED_RELATIVE_FILES_CACHE.pop(oldest_key, None)
    _PUBLIC_REPOSITORY_TRACKED_RELATIVE_FILES_CACHE[cache_key] = normalized_relative_paths
    return list(normalized_relative_paths)


def _normalized_public_repository_tracked_relative_files(
    relative_paths: list[str],
) -> list[str]:
    """Normalize + dedup tracked relative paths, preserving the input order."""
    return list(
        dict.fromkeys(
            normalized_relative_path
            for raw_relative_path in relative_paths
            if (
                normalized_relative_path := probe_module.repository_service._normalize_repository_relative_path(
                    raw_relative_path
                )
            )
        )
    )


def _store_public_repository_tracked_relative_files(
    *,
    repo_path: Path,
    relative_paths: list[str],
) -> list[str]:
    # The generic listing (e.g. from ``git ls-tree``) has no meaningful order, so the cached
    # tracked listing is sorted for deterministic downstream consumption. Order-significant
    # callers (sparse/materialized focus walks) cache their own order via the helper below.
    normalized_relative_paths = tuple(
        sorted(_normalized_public_repository_tracked_relative_files(relative_paths))
    )
    return _cache_public_repository_tracked_relative_files(
        repo_path=repo_path,
        normalized_relative_paths=normalized_relative_paths,
    )


def _focused_public_repository_inventory_paths_from_cache(
    *,
    repo_path: Path,
    focus_paths: list[str],
) -> list[str] | None:
    tracked_relative_paths = _cached_public_repository_tracked_relative_files(repo_path)
    if tracked_relative_paths is None:
        return None
    normalized_focus_paths = _normalized_public_repository_focus_paths(focus_paths)
    if not normalized_focus_paths:
        return list(tracked_relative_paths)
    return [
        relative_path
        for relative_path in tracked_relative_paths
        if probe_module._matches_focus_paths(relative_path, normalized_focus_paths)
    ]


def _public_repository_seed_plan_result_cache_fingerprint() -> str:
    return repository_cache._analysis_implementation_fingerprint()


def _public_repository_seed_plan_result_cache_key(
    *,
    case: PublicRepositoryCase,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
) -> tuple[str, str, str, tuple[str, ...], int]:
    return (
        str(repo_path.resolve()),
        _public_repository_case_key(case),
        _public_repository_seed_plan_result_cache_fingerprint(),
        tuple(_normalized_public_repository_focus_paths(focus_paths)),
        max_files,
    )


def _cached_public_repository_seed_plan_result(
    *,
    case: PublicRepositoryCase,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
) -> dict[str, Any] | None:
    cached_result = _PUBLIC_REPOSITORY_SEED_PLAN_RESULT_CACHE.get(
        _public_repository_seed_plan_result_cache_key(
            case=case,
            repo_path=repo_path,
            focus_paths=focus_paths,
            max_files=max_files,
        )
    )
    if cached_result is None:
        return None
    return deepcopy(cached_result)


def _store_public_repository_seed_plan_result(
    *,
    case: PublicRepositoryCase,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    cache_key = _public_repository_seed_plan_result_cache_key(
        case=case,
        repo_path=repo_path,
        focus_paths=focus_paths,
        max_files=max_files,
    )
    if len(_PUBLIC_REPOSITORY_SEED_PLAN_RESULT_CACHE) >= (
        _PUBLIC_REPOSITORY_SEED_PLAN_RESULT_CACHE_LIMIT
    ):
        oldest_key = next(iter(_PUBLIC_REPOSITORY_SEED_PLAN_RESULT_CACHE))
        _PUBLIC_REPOSITORY_SEED_PLAN_RESULT_CACHE.pop(oldest_key, None)
    cached_result = deepcopy(result)
    _PUBLIC_REPOSITORY_SEED_PLAN_RESULT_CACHE[cache_key] = cached_result
    return deepcopy(cached_result)


def _cached_public_repository_explicit_focus_seed_plan_result(
    *,
    case: PublicRepositoryCase,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
) -> tuple[bool, dict[str, Any] | None]:
    cache_key = _public_repository_seed_plan_result_cache_key(
        case=case,
        repo_path=repo_path,
        focus_paths=focus_paths,
        max_files=max_files,
    )
    if cache_key not in _PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE:
        return False, None
    cached_result = _PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE[cache_key]
    if cached_result is None:
        return True, None
    return True, deepcopy(cached_result)


def _store_public_repository_explicit_focus_seed_plan_result(
    *,
    case: PublicRepositoryCase,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
    result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    cache_key = _public_repository_seed_plan_result_cache_key(
        case=case,
        repo_path=repo_path,
        focus_paths=focus_paths,
        max_files=max_files,
    )
    if len(_PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE) >= (
        _PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE_LIMIT
    ):
        oldest_key = next(iter(_PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE))
        _PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE.pop(oldest_key, None)
    cached_result = deepcopy(result) if result is not None else None
    _PUBLIC_REPOSITORY_EXPLICIT_FOCUS_SEED_PLAN_RESULT_CACHE[cache_key] = cached_result
    return deepcopy(cached_result) if cached_result is not None else None


def _public_repository_refined_unscoped_probe_plan_cache_key(
    *,
    case: PublicRepositoryCase,
    repo_path: Path,
    max_files: int,
) -> tuple[str, str, str, int]:
    return (
        str(_normalized_public_repository_repo_path(repo_path)),
        _public_repository_case_key(case),
        _public_repository_seed_plan_result_cache_fingerprint(),
        max_files,
    )


def _cached_public_repository_refined_unscoped_probe_plan(
    *,
    case: PublicRepositoryCase,
    repo_path: Path,
    max_files: int,
) -> tuple[dict[str, Any], list[str]] | None:
    cached_plan = _PUBLIC_REPOSITORY_REFINED_UNSCOPED_PROBE_PLAN_CACHE.get(
        _public_repository_refined_unscoped_probe_plan_cache_key(
            case=case,
            repo_path=repo_path,
            max_files=max_files,
        )
    )
    if cached_plan is None:
        return None
    cached_seed_plan_result, cached_probe_focus_paths = cached_plan
    return deepcopy(cached_seed_plan_result), list(cached_probe_focus_paths)


def _store_public_repository_refined_unscoped_probe_plan(
    *,
    case: PublicRepositoryCase,
    repo_path: Path,
    max_files: int,
    seed_plan_result: dict[str, Any],
    probe_focus_paths: list[str],
) -> tuple[dict[str, Any], list[str]]:
    cache_key = _public_repository_refined_unscoped_probe_plan_cache_key(
        case=case,
        repo_path=repo_path,
        max_files=max_files,
    )
    # The derived probe focus paths are already a deliberate, ordered slice (a seed-plan can
    # legitimately list both a support root and a more specific descendant, e.g.
    # ``resources/views`` and ``resources/views/pages``). Normalize + dedup while preserving
    # order, but do NOT ancestor-collapse here — that would discard the narrower focus.
    normalized_probe_focus_paths = tuple(
        dict.fromkeys(
            normalized_focus_path
            for raw_focus_path in probe_focus_paths
            if (
                normalized_focus_path := str(raw_focus_path or "")
                .strip()
                .replace("\\", "/")
                .strip("/")
            )
            and normalized_focus_path != "."
        )
    )
    cached_plan = (
        deepcopy(seed_plan_result),
        normalized_probe_focus_paths,
    )
    if len(_PUBLIC_REPOSITORY_REFINED_UNSCOPED_PROBE_PLAN_CACHE) >= (
        _PUBLIC_REPOSITORY_REFINED_UNSCOPED_PROBE_PLAN_CACHE_LIMIT
    ):
        oldest_key = next(iter(_PUBLIC_REPOSITORY_REFINED_UNSCOPED_PROBE_PLAN_CACHE))
        _PUBLIC_REPOSITORY_REFINED_UNSCOPED_PROBE_PLAN_CACHE.pop(oldest_key, None)
    _PUBLIC_REPOSITORY_REFINED_UNSCOPED_PROBE_PLAN_CACHE[cache_key] = cached_plan
    return deepcopy(cached_plan[0]), list(cached_plan[1])


def _public_repository_prepass_focus_path_cache_key(
    *,
    repo_path: Path,
    expected_primary_ecosystem: str,
) -> tuple[str, str | None]:
    return (
        str(repo_path.resolve()),
        _canonical_ecosystem_name(expected_primary_ecosystem),
    )


def _cached_public_repository_prepass_focus_paths(
    *,
    repo_path: Path,
    expected_primary_ecosystem: str,
) -> list[str] | None:
    cached_focus_paths = _PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE.get(
        _public_repository_prepass_focus_path_cache_key(
            repo_path=repo_path,
            expected_primary_ecosystem=expected_primary_ecosystem,
        )
    )
    if cached_focus_paths is None:
        return None
    return list(cached_focus_paths)


def _store_public_repository_prepass_focus_paths(
    *,
    repo_path: Path,
    expected_primary_ecosystem: str,
    focus_paths: list[str],
) -> list[str]:
    cache_key = _public_repository_prepass_focus_path_cache_key(
        repo_path=repo_path,
        expected_primary_ecosystem=expected_primary_ecosystem,
    )
    normalized_focus_paths = tuple(
        _normalized_public_repository_focus_paths(focus_paths)
    )
    if not normalized_focus_paths:
        _PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE.pop(cache_key, None)
        return []
    cached_focus_paths = _PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE.get(cache_key)
    if cached_focus_paths is not None and _should_preserve_cached_prepass_focus_paths(
        cached_focus_paths,
        normalized_focus_paths,
    ):
        return list(cached_focus_paths)
    if len(_PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE) >= (
        _PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE_LIMIT
    ):
        oldest_key = next(iter(_PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE))
        _PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE.pop(oldest_key, None)
    _PUBLIC_REPOSITORY_PREPASS_FOCUS_PATH_CACHE[cache_key] = normalized_focus_paths
    return list(normalized_focus_paths)


def _should_preserve_cached_prepass_focus_paths(
    cached_focus_paths: tuple[str, ...],
    candidate_focus_paths: tuple[str, ...],
) -> bool:
    if cached_focus_paths == candidate_focus_paths:
        return True
    if _prepass_focus_paths_cover(cached_focus_paths, candidate_focus_paths):
        return False
    if _prepass_focus_paths_cover(candidate_focus_paths, cached_focus_paths):
        return True
    return _prepass_focus_path_specificity_score(
        cached_focus_paths
    ) >= _prepass_focus_path_specificity_score(candidate_focus_paths)


def _prepass_focus_paths_cover(
    covering_focus_paths: tuple[str, ...],
    covered_focus_paths: tuple[str, ...],
) -> bool:
    return all(
        any(
            covered_focus_path == covering_focus_path
            or covered_focus_path.startswith(f"{covering_focus_path}/")
            for covering_focus_path in covering_focus_paths
        )
        for covered_focus_path in covered_focus_paths
    )


def _prepass_focus_path_specificity_score(
    focus_paths: tuple[str, ...],
) -> tuple[int, int, int]:
    return (
        sum(len(PurePosixPath(path).parts) for path in focus_paths),
        len(focus_paths),
        sum(len(path) for path in focus_paths),
    )


def _canonical_ecosystem_name(ecosystem: str | None) -> str | None:
    canonical_ecosystem = canonical_repository_language(ecosystem)
    return canonical_ecosystem or None


def _path_candidate_ecosystems(
    path: str,
    *,
    repo_path: Path,
) -> set[str]:
    normalized_path = str(path or "").strip().replace("\\", "/").strip("/")
    if not normalized_path:
        return set()
    cache_key = (
        str(_normalized_public_repository_repo_path(repo_path)),
        normalized_path,
    )
    cached_ecosystems = _PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE.get(cache_key)
    if cached_ecosystems is not None:
        return set(cached_ecosystems)
    candidate_ecosystems = {
        canonical_ecosystem
        for ecosystem in probe_module._candidate_ecosystems_for_path(
            normalized_path,
            repo_path=repo_path,
        )
        if (canonical_ecosystem := _canonical_ecosystem_name(ecosystem))
    }
    if len(_PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE) >= (
        _PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE_LIMIT
    ):
        oldest_key = next(iter(_PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE))
        _PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE.pop(oldest_key, None)
    _PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE[cache_key] = frozenset(
        candidate_ecosystems
    )
    return set(candidate_ecosystems)


_EXPECTED_ECOSYSTEM_ADAPTER_NAME_OVERRIDES = {
    "4d": "four_d_adapter",
    "vb6": "classic_visual_basic_adapter",
}


def _expected_ecosystem_adapter_name(ecosystem: str) -> str:
    override = _EXPECTED_ECOSYSTEM_ADAPTER_NAME_OVERRIDES.get(ecosystem)
    if override:
        return override
    return f"{ecosystem.replace('-', '_')}_adapter"


def _expected_ecosystem_hint_metadata(
    ecosystem: str,
) -> _ExpectedEcosystemHintMetadata:
    cached_metadata = _EXPECTED_ECOSYSTEM_HINT_METADATA_CACHE.get(ecosystem)
    if cached_metadata is not None:
        return cached_metadata

    adapter_name = _expected_ecosystem_adapter_name(ecosystem)
    path_hint_predicate = None
    path_hint_supports_path_keyword = False
    config_basenames: frozenset[str] = frozenset()
    suffixes: frozenset[str] = frozenset()
    try:
        adapter = repository_compat_exports.get_export(adapter_name)
    except AttributeError:
        adapter = None
    if adapter is not None:
        path_hint_predicate = getattr(adapter, f"has_{ecosystem}_path_hints", None)
        if not callable(path_hint_predicate):
            path_hint_predicate = None
        path_hint_supports_path_keyword = (
            _path_hint_predicate_supports_path_keyword(path_hint_predicate)
            if callable(path_hint_predicate)
            else False
        )
        adapter_prefix = adapter_name.removesuffix("_adapter").upper()
        config_basenames = frozenset(
            str(candidate).lower()
            for candidate in getattr(adapter, f"{adapter_prefix}_CONFIG_BASENAMES", ())
        )
        suffixes = frozenset(
            str(candidate).lower()
            for suffix_attr in (f"{adapter_prefix}_SUFFIXES", f"{adapter_prefix}_SOURCE_SUFFIXES")
            for candidate in getattr(adapter, suffix_attr, ())
        )
    inferred_suffixes = (
        frozenset()
        if suffixes
        else frozenset(_expected_ecosystem_static_hint_suffixes(ecosystem))
    )
    metadata = (
        path_hint_predicate,
        path_hint_supports_path_keyword,
        config_basenames,
        frozenset({*suffixes, *inferred_suffixes}),
    )
    _EXPECTED_ECOSYSTEM_HINT_METADATA_CACHE[ecosystem] = metadata
    return metadata


@lru_cache(maxsize=512)
def _expected_ecosystem_static_hint_suffixes(ecosystem: str) -> tuple[str, ...]:
    canonical_ecosystem = _canonical_ecosystem_name(ecosystem)
    if canonical_ecosystem is None:
        return ()
    ordered_suffixes: list[str] = []
    seen_suffixes: set[str] = set()
    candidate_suffixes = sorted(
        {
            str(candidate).strip().lower()
            for candidate in repository_file_selection.TEXT_FILE_SUFFIXES
            if str(candidate).strip().startswith(".")
        }
    )
    for suffix in candidate_suffixes:
        if len(suffix) <= 1 or suffix in seen_suffixes:
            continue
        if _static_language_hint_for_path(f"probe{suffix}") != canonical_ecosystem:
            continue
        seen_suffixes.add(suffix)
        ordered_suffixes.append(suffix)
    return tuple(ordered_suffixes)


@lru_cache(maxsize=512)
def _expected_ecosystem_hint_pathspecs(
    expected_primary_ecosystem: str,
) -> tuple[str, ...]:
    canonical_expected_ecosystem = _canonical_ecosystem_name(expected_primary_ecosystem)
    if canonical_expected_ecosystem is None:
        return ()
    _path_hint_predicate, _supports_path_keyword, config_basenames, suffixes = (
        _expected_ecosystem_hint_metadata(canonical_expected_ecosystem)
    )
    ordered_pathspecs: list[str] = []
    seen_pathspecs: set[str] = set()

    def _append_pathspec(pathspec: str) -> None:
        normalized_pathspec = str(pathspec or "").strip()
        if not normalized_pathspec or normalized_pathspec in seen_pathspecs:
            return
        seen_pathspecs.add(normalized_pathspec)
        ordered_pathspecs.append(normalized_pathspec)

    for basename in sorted(config_basenames):
        normalized_basename = str(basename or "").strip().lower()
        if not normalized_basename:
            continue
        _append_pathspec(normalized_basename)
        _append_pathspec(f":(glob)**/{normalized_basename}")
    for suffix in sorted(suffixes):
        normalized_suffix = str(suffix or "").strip().lower()
        if not normalized_suffix.startswith(".") or len(normalized_suffix) <= 1:
            continue
        _append_pathspec(f":(glob)*{normalized_suffix}")
        _append_pathspec(f":(glob)**/*{normalized_suffix}")
    return tuple(ordered_pathspecs)


def _path_hint_predicate_supports_path_keyword(path_hint_predicate: Any) -> bool:
    try:
        parameters = tuple(inspect.signature(path_hint_predicate).parameters.values())
    except (TypeError, ValueError):
        parameters = ()
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return True
    return any(
        parameter.name == "path"
        and parameter.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
        for parameter in parameters
    )


def _call_path_hint_predicate(
    path_hint_predicate: Any,
    candidate_path: Path,
    *,
    supports_path_keyword: bool,
) -> bool:
    if supports_path_keyword:
        return bool(path_hint_predicate(path=candidate_path))
    return bool(path_hint_predicate(candidate_path))


@lru_cache(maxsize=131_072)
def _path_basename_and_suffix(path: str) -> tuple[str, str]:
    normalized_path = str(path).replace("\\", "/")
    basename = normalized_path.rsplit("/", 1)[-1].lower()
    suffix_index = basename.rfind(".")
    suffix = basename[suffix_index:] if suffix_index > 0 else ""
    return basename, suffix


@lru_cache(maxsize=131_072)
def _static_language_hint_for_path(path: str) -> str | None:
    normalized_path = str(path or "").strip().replace("\\", "/").strip("/")
    if not normalized_path:
        return None
    basename, suffix = _path_basename_and_suffix(normalized_path)
    direct_language_hint = _canonical_ecosystem_name(
        _profile_path_classification_support_module()._direct_probe_language_hint(
            basename=basename,
            suffix=suffix,
        )
    )
    if direct_language_hint is not None:
        return direct_language_hint
    candidate_language = _canonical_ecosystem_name(
        repository_indexing._language_for_path(PurePosixPath(normalized_path))
    )
    return candidate_language or None


@lru_cache(maxsize=262_144)
def _path_matches_expected_ecosystem_hint_cached(
    path: str,
    expected_primary_ecosystem: str,
) -> bool:
    normalized_path = str(path or "").strip().replace("\\", "/").strip("/")
    canonical_expected_ecosystem = _canonical_ecosystem_name(expected_primary_ecosystem)
    if not normalized_path or canonical_expected_ecosystem is None:
        return False
    (
        path_hint_predicate,
        path_hint_supports_path_keyword,
        config_basenames,
        suffixes,
    ) = _expected_ecosystem_hint_metadata(
        canonical_expected_ecosystem
    )
    basename, suffix = _path_basename_and_suffix(normalized_path)
    if basename in config_basenames:
        return True
    if suffix in suffixes:
        return True
    if callable(path_hint_predicate) and _call_path_hint_predicate(
        path_hint_predicate,
        Path(normalized_path),
        supports_path_keyword=path_hint_supports_path_keyword,
    ):
        return True
    return _static_language_hint_for_path(normalized_path) == canonical_expected_ecosystem


def _path_matches_expected_ecosystem_hint(
    path: str,
    *,
    expected_primary_ecosystem: str,
) -> bool:
    return _path_matches_expected_ecosystem_hint_cached(
        path,
        expected_primary_ecosystem=expected_primary_ecosystem,
    )


def _path_supports_expected_ecosystem(
    path: str,
    *,
    repo_path: Path,
    expected_primary_ecosystem: str,
) -> bool:
    canonical_expected_ecosystem = _canonical_ecosystem_name(expected_primary_ecosystem)
    if canonical_expected_ecosystem is None:
        return False
    if _path_matches_expected_ecosystem_hint(
        path,
        expected_primary_ecosystem=canonical_expected_ecosystem,
    ):
        return True
    if canonical_expected_ecosystem in _path_candidate_ecosystems(
        path,
        repo_path=repo_path,
    ):
        return True
    return False


def _path_primary_ecosystem(
    path: str,
    *,
    repo_path: Path,
    expected_primary_ecosystem: str,
) -> str | None:
    if _path_supports_expected_ecosystem(
        path,
        repo_path=repo_path,
        expected_primary_ecosystem=expected_primary_ecosystem,
    ):
        return _canonical_ecosystem_name(expected_primary_ecosystem)
    return _canonical_ecosystem_name(
        probe_module._probe_language_for_path(
            str(path),
            repo_path=repo_path,
        )
    )


def _ecosystems_match(left: str | None, right: str | None) -> bool:
    canonical_left = _canonical_ecosystem_name(left)
    canonical_right = _canonical_ecosystem_name(right)
    return canonical_left is not None and canonical_left == canonical_right


def _public_repository_case_match_targets(
    *,
    language: str | None,
    expected_primary_ecosystem: str | None,
) -> tuple[str, ...]:
    targets: list[str] = []
    for candidate in (expected_primary_ecosystem, language):
        canonical_candidate = _canonical_ecosystem_name(candidate)
        if canonical_candidate and canonical_candidate not in targets:
            targets.append(canonical_candidate)
    return tuple(targets)


def _ecosystem_matches_public_repository_case(
    ecosystem: str | None,
    *,
    language: str | None,
    expected_primary_ecosystem: str | None,
) -> bool:
    canonical_ecosystem = _canonical_ecosystem_name(ecosystem)
    return canonical_ecosystem is not None and canonical_ecosystem in (
        _public_repository_case_match_targets(
            language=language,
            expected_primary_ecosystem=expected_primary_ecosystem,
        )
    )


def _versionish_signature_and_priority(part: str) -> tuple[str | None, tuple[int | str, ...] | None]:
    normalized_part = str(part or "").strip()
    if not normalized_part:
        return None, None
    if _VERSIONISH_PATH_PART_RE.fullmatch(normalized_part):
        signature_part = ""
        version_part = normalized_part
    else:
        alpha_prefixed_match = _EMBEDDED_ALPHA_PREFIXED_VERSIONISH_PATH_PART_RE.fullmatch(
            normalized_part
        )
        if alpha_prefixed_match is not None:
            prefix_part = alpha_prefixed_match.group("prefix").strip(" ._-")
            family_part = alpha_prefixed_match.group("family").strip(" ._-")
            if not prefix_part or not family_part:
                return None, None
            signature_part = f"{prefix_part} {family_part.upper()}".strip()
            version_part = alpha_prefixed_match.group("version")
        else:
            match = _EMBEDDED_VERSIONISH_PATH_PART_RE.fullmatch(normalized_part)
            if match is None:
                return None, None
            signature_part = match.group("prefix").strip(" ._-")
            version_part = match.group("version")
            if not signature_part:
                return None, None
    normalized_version = version_part.lower().lstrip("v").replace("-", ".").replace("_", ".")
    tokens: list[int | str] = []
    for token in re.findall(r"\d+|[a-z]+", normalized_version):
        tokens.append(int(token) if token.isdigit() else token)
    return signature_part, tuple(tokens)


def _prefer_expected_primary_ecosystem_on_tied_top_score(
    ordered_ecosystems: list[str],
    *,
    ecosystem_scores: Counter[str],
    expected_primary_ecosystem: str,
) -> list[str]:
    canonical_expected_ecosystem = canonical_repository_language(expected_primary_ecosystem)
    normalized_scores: Counter[str] = Counter()
    for ecosystem, score in ecosystem_scores.items():
        canonical_ecosystem = canonical_repository_language(ecosystem)
        if not canonical_ecosystem:
            continue
        normalized_scores[canonical_ecosystem] += score
    if (
        canonical_expected_ecosystem is None
        or canonical_expected_ecosystem not in normalized_scores
        or not ordered_ecosystems
        or ordered_ecosystems[0] == canonical_expected_ecosystem
    ):
        return ordered_ecosystems
    top_score = max(normalized_scores.values(), default=0)
    if normalized_scores.get(canonical_expected_ecosystem, 0) != top_score:
        return ordered_ecosystems
    return [canonical_expected_ecosystem, *[
        ecosystem
        for ecosystem in ordered_ecosystems
        if ecosystem != canonical_expected_ecosystem
    ]]


@dataclass(frozen=True)
class PublicRepositoryCase:
    language: str
    repository_url: str
    expected_primary_ecosystem: str
    focus_paths: tuple[str, ...] = ()
    notes: str | None = None


def _public_repository_case_key(case: PublicRepositoryCase | dict[str, Any]) -> str:
    language = str(case["language"] if isinstance(case, dict) else case.language)
    repository_url = str(
        case["repository_url"] if isinstance(case, dict) else case.repository_url
    ).rstrip("/")
    return f"{language}:{repository_url}"


DEFAULT_PUBLIC_REPOSITORY_CASES: tuple[PublicRepositoryCase, ...] = (
    PublicRepositoryCase(
        language="typescript",
        repository_url="https://github.com/sindresorhus/ky.git",
        expected_primary_ecosystem="typescript",
    ),
    PublicRepositoryCase(
        language="typescript",
        repository_url="https://github.com/sindresorhus/type-fest.git",
        expected_primary_ecosystem="typescript",
    ),
    PublicRepositoryCase(
        language="python",
        repository_url="https://github.com/pallets/click.git",
        expected_primary_ecosystem="python",
    ),
    PublicRepositoryCase(
        language="python",
        repository_url="https://github.com/psf/requests.git",
        expected_primary_ecosystem="python",
    ),
    PublicRepositoryCase(
        language="dockerfile",
        repository_url="https://github.com/jessfraz/dockerfiles.git",
        expected_primary_ecosystem="dockerfile",
    ),
    PublicRepositoryCase(
        language="dockerfile",
        repository_url="https://github.com/docker-library/hello-world.git",
        expected_primary_ecosystem="dockerfile",
    ),
    PublicRepositoryCase(
        language="cython",
        repository_url="https://github.com/strawlab/python-pcl.git",
        expected_primary_ecosystem="cython",
    ),
    PublicRepositoryCase(
        language="cython",
        repository_url="https://github.com/cython/cython.git",
        expected_primary_ecosystem="cython",
    ),
    PublicRepositoryCase(
        language="stan",
        repository_url="https://github.com/stan-dev/example-models.git",
        expected_primary_ecosystem="stan",
    ),
    PublicRepositoryCase(
        language="javascript",
        repository_url="https://github.com/expressjs/express.git",
        expected_primary_ecosystem="node",
    ),
    PublicRepositoryCase(
        language="javascript",
        repository_url="https://github.com/lodash/lodash.git",
        expected_primary_ecosystem="node",
    ),
    PublicRepositoryCase(
        language="vue",
        repository_url="https://github.com/coreui/coreui-free-vue-admin-template.git",
        expected_primary_ecosystem="vue",
    ),
    PublicRepositoryCase(
        language="vue",
        repository_url="https://github.com/vuejs/pinia.git",
        expected_primary_ecosystem="vue",
    ),
    PublicRepositoryCase(
        language="svelte",
        repository_url="https://github.com/sveltejs/realworld.git",
        expected_primary_ecosystem="svelte",
    ),
    PublicRepositoryCase(
        language="svelte",
        repository_url="https://github.com/sveltejs/svelte.dev.git",
        expected_primary_ecosystem="svelte",
    ),
    PublicRepositoryCase(
        language="astro",
        repository_url="https://github.com/withastro/astro.build.git",
        expected_primary_ecosystem="astro",
    ),
    PublicRepositoryCase(
        language="astro",
        repository_url="https://github.com/withastro/starlight.git",
        expected_primary_ecosystem="astro",
    ),
    PublicRepositoryCase(
        language="pug",
        repository_url="https://github.com/StartBootstrap/startbootstrap-sb-admin.git",
        expected_primary_ecosystem="pug",
    ),
    PublicRepositoryCase(
        language="pug",
        repository_url="https://github.com/StartBootstrap/startbootstrap-freelancer.git",
        expected_primary_ecosystem="pug",
    ),
    PublicRepositoryCase(
        language="ejs",
        repository_url="https://github.com/jaywcjlove/github-rank.git",
        expected_primary_ecosystem="ejs",
    ),
    PublicRepositoryCase(
        language="ejs",
        repository_url="https://github.com/mde/ejs.git",
        expected_primary_ecosystem="ejs",
    ),
    PublicRepositoryCase(
        language="blade",
        repository_url="https://github.com/laravel/laravel.git",
        expected_primary_ecosystem="blade",
    ),
    PublicRepositoryCase(
        language="php",
        repository_url="https://github.com/Seldaek/monolog.git",
        expected_primary_ecosystem="php",
    ),
    PublicRepositoryCase(
        language="php",
        repository_url="https://github.com/laravel/framework.git",
        expected_primary_ecosystem="php",
    ),
    PublicRepositoryCase(
        language="erb",
        repository_url="https://github.com/redmine/redmine.git",
        expected_primary_ecosystem="erb",
    ),
    PublicRepositoryCase(
        language="erb",
        repository_url="https://github.com/coskuntekin/middleman_starter_kit.git",
        expected_primary_ecosystem="erb",
    ),
    PublicRepositoryCase(
        language="mustache",
        repository_url="https://github.com/janl/mustache.js.git",
        expected_primary_ecosystem="mustache",
    ),
    PublicRepositoryCase(
        language="mustache",
        repository_url="https://github.com/swagger-api/swagger-codegen.git",
        expected_primary_ecosystem="mustache",
    ),
    PublicRepositoryCase(
        language="nunjucks",
        repository_url="https://github.com/11ty/eleventy-base-blog.git",
        expected_primary_ecosystem="nunjucks",
    ),
    PublicRepositoryCase(
        language="nunjucks",
        repository_url="https://github.com/madrilene/eleventy-excellent.git",
        expected_primary_ecosystem="nunjucks",
    ),
    PublicRepositoryCase(
        language="twig",
        repository_url="https://github.com/timber/starter-theme.git",
        expected_primary_ecosystem="twig",
    ),
    PublicRepositoryCase(
        language="twig",
        repository_url="https://github.com/symfony/web-profiler-bundle.git",
        expected_primary_ecosystem="twig",
    ),
    PublicRepositoryCase(
        language="haml",
        repository_url="https://github.com/mpv-player/mpv.io.git",
        expected_primary_ecosystem="haml",
    ),
    PublicRepositoryCase(
        language="haml",
        repository_url="https://github.com/olivierlacan/keep-a-changelog.git",
        expected_primary_ecosystem="haml",
    ),
    PublicRepositoryCase(
        language="slim",
        repository_url="https://github.com/betagouv/rdv-service-public.git",
        expected_primary_ecosystem="slim",
    ),
    PublicRepositoryCase(
        language="slim",
        repository_url="https://github.com/slim-template/slim.git",
        expected_primary_ecosystem="slim",
    ),
    PublicRepositoryCase(
        language="smarty",
        repository_url="https://github.com/prestashop/classic-theme.git",
        expected_primary_ecosystem="smarty",
    ),
    PublicRepositoryCase(
        language="smarty",
        repository_url="https://github.com/smarty-php/smarty.git",
        expected_primary_ecosystem="smarty",
    ),
    PublicRepositoryCase(
        language="graphviz",
        repository_url="https://github.com/abruzzi/graphviz-scripts.git",
        expected_primary_ecosystem="graphviz",
    ),
    PublicRepositoryCase(
        language="mermaid",
        repository_url="https://github.com/mermaid-js/mermaid-cli.git",
        expected_primary_ecosystem="mermaid",
    ),
    PublicRepositoryCase(
        language="plantuml",
        repository_url="https://github.com/plantuml-stdlib/C4-PlantUML.git",
        expected_primary_ecosystem="plantuml",
    ),
    PublicRepositoryCase(
        language="openqasm",
        repository_url="https://github.com/pnnl/QASMBench.git",
        expected_primary_ecosystem="openqasm",
    ),
    PublicRepositoryCase(
        language="answer set programming",
        repository_url="https://github.com/potassco/guide.git",
        expected_primary_ecosystem="answer set programming",
        focus_paths=("examples",),
    ),
    PublicRepositoryCase(
        language="alloy",
        repository_url="https://github.com/AlloyTools/models.git",
        expected_primary_ecosystem="alloy",
    ),
    PublicRepositoryCase(
        language="aiken",
        repository_url="https://github.com/aiken-lang/stdlib.git",
        expected_primary_ecosystem="aiken",
    ),
    PublicRepositoryCase(
        language="asl",
        repository_url="https://github.com/jardenliu/XPS15-9560-Ventura.git",
        expected_primary_ecosystem="asl",
        focus_paths=("OC/ACPI/Origin",),
    ),
    PublicRepositoryCase(
        language="ats",
        repository_url="https://github.com/ats-lang/ATS-CodeBook.git",
        expected_primary_ecosystem="ats",
    ),
    PublicRepositoryCase(
        language="freemarker",
        repository_url="https://github.com/lenve/CoolMeeting.git",
        expected_primary_ecosystem="freemarker",
    ),
    PublicRepositoryCase(
        language="mako",
        repository_url="https://github.com/sqlalchemy/mako.git",
        expected_primary_ecosystem="mako",
        focus_paths=("test/templates",),
    ),
    PublicRepositoryCase(
        language="4d",
        repository_url="https://github.com/4d/4D-NetKit.git",
        expected_primary_ecosystem="4d",
        focus_paths=("Project/Sources",),
    ),
    PublicRepositoryCase(
        language="4d",
        repository_url="https://github.com/4d/Build4D.git",
        expected_primary_ecosystem="4d",
    ),
    PublicRepositoryCase(
        language="less",
        repository_url="https://github.com/jerrykuku/luci-theme-argon.git",
        expected_primary_ecosystem="less",
    ),
    PublicRepositoryCase(
        language="less",
        repository_url="https://github.com/Remix-Design/RemixIcon.git",
        expected_primary_ecosystem="less",
    ),
    PublicRepositoryCase(
        language="stylus",
        repository_url="https://github.com/theme-next/hexo-theme-next.git",
        expected_primary_ecosystem="stylus",
    ),
    PublicRepositoryCase(
        language="stylus",
        repository_url="https://github.com/probberechts/hexo-theme-cactus.git",
        expected_primary_ecosystem="stylus",
    ),
    PublicRepositoryCase(
        language="java",
        repository_url="https://github.com/google/gson.git",
        expected_primary_ecosystem="java",
    ),
    PublicRepositoryCase(
        language="java",
        repository_url="https://github.com/square/okhttp.git",
        expected_primary_ecosystem="java",
    ),
    PublicRepositoryCase(
        language="cs",
        repository_url="https://github.com/dotnet/command-line-api.git",
        expected_primary_ecosystem="dotnet",
    ),
    PublicRepositoryCase(
        language="cs",
        repository_url="https://github.com/dotnet/BenchmarkDotNet.git",
        expected_primary_ecosystem="dotnet",
    ),
    PublicRepositoryCase(
        language="asp.net",
        repository_url="https://github.com/nahidbinashraf/An-Online-Examination-System-Project.git",
        expected_primary_ecosystem="asp.net",
        focus_paths=("onlinexamsystem",),
    ),
    PublicRepositoryCase(
        language="angelscript",
        repository_url="https://github.com/urho3d/Urho3D.git",
        expected_primary_ecosystem="angelscript",
        focus_paths=("bin/Data/Scripts",),
    ),
    PublicRepositoryCase(
        language="hack",
        repository_url="https://github.com/hhvm/hsl.git",
        expected_primary_ecosystem="hack",
    ),
    PublicRepositoryCase(
        language="hack",
        repository_url="https://github.com/hhvm/xhp-lib.git",
        expected_primary_ecosystem="hack",
    ),
    PublicRepositoryCase(
        language="eiffel",
        repository_url="https://github.com/ttencate/aoc2017.git",
        expected_primary_ecosystem="eiffel",
    ),
    PublicRepositoryCase(
        language="eiffel",
        repository_url="https://github.com/gobo-eiffel/gobo.git",
        expected_primary_ecosystem="eiffel",
    ),
    PublicRepositoryCase(
        language="shell",
        repository_url="https://github.com/ohmyzsh/ohmyzsh.git",
        expected_primary_ecosystem="shell",
    ),
    PublicRepositoryCase(
        language="shell",
        repository_url="https://github.com/tmux-plugins/tpm.git",
        expected_primary_ecosystem="shell",
    ),
    PublicRepositoryCase(
        language="graphql",
        repository_url="https://github.com/graphql/swapi-graphql.git",
        expected_primary_ecosystem="graphql",
        focus_paths=("doc/example_queries",),
    ),
    PublicRepositoryCase(
        language="fish",
        repository_url="https://github.com/jorgebucaran/fisher.git",
        expected_primary_ecosystem="fish",
    ),
    PublicRepositoryCase(
        language="fish",
        repository_url="https://github.com/PatrickF1/fzf.fish.git",
        expected_primary_ecosystem="fish",
    ),
    PublicRepositoryCase(
        language="c",
        repository_url="https://github.com/tmux/tmux.git",
        expected_primary_ecosystem="c",
    ),
    PublicRepositoryCase(
        language="c",
        repository_url="https://github.com/libgit2/libgit2.git",
        expected_primary_ecosystem="c",
    ),
    PublicRepositoryCase(
        language="cpp",
        repository_url="https://github.com/progschj/ThreadPool.git",
        expected_primary_ecosystem="cpp",
    ),
    PublicRepositoryCase(
        language="cpp",
        repository_url="https://github.com/fmtlib/fmt.git",
        expected_primary_ecosystem="cpp",
    ),
    PublicRepositoryCase(
        language="cuda",
        repository_url="https://github.com/NVIDIA/cuda-samples.git",
        expected_primary_ecosystem="cuda",
    ),
    PublicRepositoryCase(
        language="cuda",
        repository_url="https://github.com/NVIDIA/CUDALibrarySamples.git",
        expected_primary_ecosystem="cuda",
    ),
    PublicRepositoryCase(
        language="opencl",
        repository_url="https://github.com/bgaster/opencl-book-samples.git",
        expected_primary_ecosystem="opencl",
    ),
    PublicRepositoryCase(
        language="opencl",
        repository_url="https://github.com/KhronosGroup/OpenCL-SDK.git",
        expected_primary_ecosystem="opencl",
    ),
    PublicRepositoryCase(
        language="cmake",
        repository_url="https://github.com/ttroy50/cmake-examples.git",
        expected_primary_ecosystem="cmake",
    ),
    PublicRepositoryCase(
        language="cmake",
        repository_url="https://github.com/pr0g/cmake-examples.git",
        expected_primary_ecosystem="cmake",
    ),
    PublicRepositoryCase(
        language="protobuf",
        repository_url="https://github.com/googleapis/api-common-protos.git",
        expected_primary_ecosystem="protobuf",
    ),
    PublicRepositoryCase(
        language="protobuf",
        repository_url="https://github.com/googleapis/googleapis.git",
        expected_primary_ecosystem="protobuf",
    ),
    PublicRepositoryCase(
        language="meson",
        repository_url="https://github.com/tiernemi/meson-sample-project.git",
        expected_primary_ecosystem="meson",
    ),
    PublicRepositoryCase(
        language="meson",
        repository_url="https://github.com/frida/frida.git",
        expected_primary_ecosystem="meson",
    ),
    PublicRepositoryCase(
        language="qmake",
        repository_url="https://github.com/horsicq/XPEViewer.git",
        expected_primary_ecosystem="qmake",
    ),
    PublicRepositoryCase(
        language="qmake",
        repository_url="https://github.com/codyps/qmake-protobuf-example.git",
        expected_primary_ecosystem="qmake",
    ),
    PublicRepositoryCase(
        language="qml",
        repository_url="https://github.com/Qt-QML/QmlFlightInstruments.git",
        expected_primary_ecosystem="qml",
    ),
    PublicRepositoryCase(
        language="qml",
        repository_url="https://github.com/qmlbook/qmlbook.git",
        expected_primary_ecosystem="qml",
    ),
    PublicRepositoryCase(
        language="shaderlab",
        repository_url="https://github.com/poiyomi/PoiyomiToonShader.git",
        expected_primary_ecosystem="shaderlab",
    ),
    PublicRepositoryCase(
        language="scratch",
        repository_url="https://github.com/https-sharif/Scratch-Game.git",
        expected_primary_ecosystem="scratch",
    ),
    PublicRepositoryCase(
        language="go",
        repository_url="https://github.com/spf13/cobra.git",
        expected_primary_ecosystem="go",
    ),
    PublicRepositoryCase(
        language="go",
        repository_url="https://github.com/gin-gonic/gin.git",
        expected_primary_ecosystem="go",
    ),
    PublicRepositoryCase(
        language="rust",
        repository_url="https://github.com/sharkdp/fd.git",
        expected_primary_ecosystem="rust",
    ),
    PublicRepositoryCase(
        language="rust",
        repository_url="https://github.com/BurntSushi/ripgrep.git",
        expected_primary_ecosystem="rust",
    ),
    PublicRepositoryCase(
        language="assembly",
        repository_url="https://github.com/microsoft/MS-DOS.git",
        expected_primary_ecosystem="assembly",
    ),
    PublicRepositoryCase(
        language="ruby",
        repository_url="https://github.com/sinatra/sinatra.git",
        expected_primary_ecosystem="ruby",
    ),
    PublicRepositoryCase(
        language="ruby",
        repository_url="https://github.com/rails/rails.git",
        expected_primary_ecosystem="ruby",
    ),
    PublicRepositoryCase(
        language="prolog",
        repository_url="https://github.com/Anniepoo/prolog-examples.git",
        expected_primary_ecosystem="prolog",
    ),
    PublicRepositoryCase(
        language="prolog",
        repository_url="https://github.com/triska/clpfd.git",
        expected_primary_ecosystem="prolog",
    ),
    PublicRepositoryCase(
        language="logtalk",
        repository_url="https://github.com/LogtalkDotOrg/talkshow.git",
        expected_primary_ecosystem="logtalk",
    ),
    PublicRepositoryCase(
        language="logtalk",
        repository_url="https://github.com/LogtalkDotOrg/logtalk3.git",
        expected_primary_ecosystem="logtalk",
    ),
    PublicRepositoryCase(
        language="chapel",
        repository_url="https://github.com/chapel-lang/Crypto.git",
        expected_primary_ecosystem="chapel",
    ),
    PublicRepositoryCase(
        language="chapel",
        repository_url="https://github.com/chapel-lang/chapel.git",
        expected_primary_ecosystem="chapel",
    ),
    PublicRepositoryCase(
        language="swift",
        repository_url="https://github.com/pointfreeco/swift-parsing.git",
        expected_primary_ecosystem="swift",
    ),
    PublicRepositoryCase(
        language="swift",
        repository_url="https://github.com/apple/swift-argument-parser.git",
        expected_primary_ecosystem="swift",
    ),
    PublicRepositoryCase(
        language="scss",
        repository_url="https://github.com/pages-themes/minimal.git",
        expected_primary_ecosystem="scss",
    ),
    PublicRepositoryCase(
        language="scss",
        repository_url="https://github.com/IanLunn/Hover.git",
        expected_primary_ecosystem="scss",
    ),
    PublicRepositoryCase(
        language="sass",
        repository_url="https://github.com/readthedocs/sphinx_rtd_theme.git",
        expected_primary_ecosystem="sass",
    ),
    PublicRepositoryCase(
        language="sass",
        repository_url="https://github.com/pradyunsg/furo.git",
        expected_primary_ecosystem="sass",
    ),
    PublicRepositoryCase(
        language="jinja",
        repository_url="https://github.com/netbootxyz/netboot.xyz.git",
        expected_primary_ecosystem="jinja",
    ),
    PublicRepositoryCase(
        language="liquid",
        repository_url="https://github.com/Shopify/dawn.git",
        expected_primary_ecosystem="liquid",
    ),
    PublicRepositoryCase(
        language="liquid",
        repository_url="https://github.com/uicrooks/shopify-foundation-theme.git",
        expected_primary_ecosystem="liquid",
    ),
    PublicRepositoryCase(
        language="handlebars",
        repository_url="https://github.com/TryGhost/Source.git",
        expected_primary_ecosystem="handlebars",
    ),
    PublicRepositoryCase(
        language="handlebars",
        repository_url="https://github.com/TryGhost/Casper.git",
        expected_primary_ecosystem="handlebars",
    ),
    PublicRepositoryCase(
        language="tex",
        repository_url="https://github.com/posquit0/Awesome-CV.git",
        expected_primary_ecosystem="tex",
    ),
    PublicRepositoryCase(
        language="tex",
        repository_url="https://github.com/HarisIqbal88/PlotNeuralNet.git",
        expected_primary_ecosystem="tex",
    ),
    PublicRepositoryCase(
        language="rst",
        repository_url="https://github.com/godotengine/godot-docs.git",
        expected_primary_ecosystem="rst",
    ),
    PublicRepositoryCase(
        language="rst",
        repository_url="https://github.com/python/peps.git",
        expected_primary_ecosystem="rst",
    ),
    PublicRepositoryCase(
        language="asciidoc",
        repository_url="https://github.com/cartabinaria/asciidoc-thesis.git",
        expected_primary_ecosystem="asciidoc",
    ),
    PublicRepositoryCase(
        language="asciidoc",
        repository_url="https://github.com/lnbook/lnbook.git",
        expected_primary_ecosystem="asciidoc",
    ),
        PublicRepositoryCase(
            language="org",
            repository_url="https://github.com/lujun9972/emacs-document.git",
            expected_primary_ecosystem="org",
        ),
        PublicRepositoryCase(
            language="org",
            repository_url="https://github.com/tecosaur/emacs-config.git",
            expected_primary_ecosystem="org",
        ),
    PublicRepositoryCase(
        language="delphi",
        repository_url="https://github.com/VSoftTechnologies/DUnitX.git",
        expected_primary_ecosystem="delphi",
    ),
    PublicRepositoryCase(
        language="delphi",
        repository_url="https://github.com/project-jedi/jvcl.git",
        expected_primary_ecosystem="delphi",
    ),
    PublicRepositoryCase(
        language="sql",
        repository_url="https://github.com/dbt-labs/jaffle-shop-classic.git",
        expected_primary_ecosystem="sql",
    ),
    PublicRepositoryCase(
        language="sql",
        repository_url="https://github.com/ben-nour/SQL-tips-and-tricks.git",
        expected_primary_ecosystem="sql",
    ),
    PublicRepositoryCase(
        language="tsql",
        repository_url="https://github.com/BrentOzarULTD/SQL-Server-First-Responder-Kit.git",
        expected_primary_ecosystem="tsql",
    ),
    PublicRepositoryCase(
        language="tsql",
        repository_url="https://github.com/olahallengren/sql-server-maintenance-solution.git",
        expected_primary_ecosystem="tsql",
    ),
    PublicRepositoryCase(
        language="vb6",
        repository_url="https://github.com/badcodes/vb6.git",
        expected_primary_ecosystem="vb6",
    ),
    PublicRepositoryCase(
        language="vba",
        repository_url="https://github.com/VBA-tools/VBA-JSON.git",
        expected_primary_ecosystem="vba",
    ),
    PublicRepositoryCase(
        language="vba",
        repository_url="https://github.com/ivankokan/Excel2LaTeX.git",
        expected_primary_ecosystem="vba",
    ),
    PublicRepositoryCase(
        language="plsql",
        repository_url="https://github.com/mortenbra/alexandria-plsql-utils.git",
        expected_primary_ecosystem="plsql",
    ),
    PublicRepositoryCase(
        language="plsql",
        repository_url="https://github.com/utPLSQL/utPLSQL.git",
        expected_primary_ecosystem="plsql",
    ),
    PublicRepositoryCase(
        language="plpgsql",
        repository_url="https://github.com/pgmq/pgmq.git",
        expected_primary_ecosystem="plpgsql",
        focus_paths=("pgmq-extension/sql",),
    ),
    PublicRepositoryCase(
        language="ada",
        repository_url="https://github.com/alire-project/alire.git",
        expected_primary_ecosystem="ada",
    ),
    PublicRepositoryCase(
        language="cobol",
        repository_url="https://github.com/openmainframeproject/cobol-programming-course.git",
        expected_primary_ecosystem="cobol",
    ),
    PublicRepositoryCase(
        language="sas",
        repository_url="https://github.com/friendly/SAS-macros.git",
        expected_primary_ecosystem="sas",
    ),
    PublicRepositoryCase(
        language="ml",
        repository_url="https://github.com/minoki/LunarML.git",
        expected_primary_ecosystem="sml",
    ),
    PublicRepositoryCase(
        language="sml",
        repository_url="https://github.com/SMLFamily/BasisLibrary.git",
        expected_primary_ecosystem="sml",
    ),
    PublicRepositoryCase(
        language="abap",
        repository_url="https://github.com/abapGit/abapGit.git",
        expected_primary_ecosystem="abap",
    ),
    PublicRepositoryCase(
        language="abapcds",
        repository_url="https://github.com/SAP-samples/abap-platform-analytics-data-modeling.git",
        expected_primary_ecosystem="abapcds",
    ),
    PublicRepositoryCase(
        language="1centerprise",
        repository_url="https://github.com/oscript-library/opm.git",
        expected_primary_ecosystem="1centerprise",
    ),
    PublicRepositoryCase(
        language="kotlin",
        repository_url="https://github.com/square/kotlinpoet.git",
        expected_primary_ecosystem="kotlin",
    ),
    PublicRepositoryCase(
        language="kotlin",
        repository_url="https://github.com/Kotlin/kotlinx.serialization.git",
        expected_primary_ecosystem="kotlin",
    ),
    PublicRepositoryCase(
        language="scala",
        repository_url="https://github.com/playframework/play-json.git",
        expected_primary_ecosystem="scala",
    ),
    PublicRepositoryCase(
        language="scala",
        repository_url="https://github.com/typelevel/cats.git",
        expected_primary_ecosystem="scala",
    ),
    PublicRepositoryCase(
        language="dart",
        repository_url="https://github.com/dart-lang/http.git",
        expected_primary_ecosystem="dart",
    ),
    PublicRepositoryCase(
        language="dart",
        repository_url="https://github.com/felangel/bloc.git",
        expected_primary_ecosystem="dart",
    ),
    PublicRepositoryCase(
        language="groovy",
        repository_url="https://github.com/apache/groovy.git",
        expected_primary_ecosystem="groovy",
    ),
    PublicRepositoryCase(
        language="groovy",
        repository_url="https://github.com/spockframework/spock.git",
        expected_primary_ecosystem="groovy",
    ),
    PublicRepositoryCase(
        language="xtend",
        repository_url="https://github.com/tobykurien/Xtendroid.git",
        expected_primary_ecosystem="xtend",
        focus_paths=("Xtendroid/src",),
    ),
    PublicRepositoryCase(
        language="aspectj",
        repository_url="https://github.com/astefanutti/metrics-aspectj.git",
        expected_primary_ecosystem="aspectj",
        focus_paths=("impl/src/main/aspect",),
    ),
    PublicRepositoryCase(
        language="codeql",
        repository_url="https://github.com/github/codeql.git",
        expected_primary_ecosystem="codeql",
        focus_paths=("python/ql/src",),
    ),
    PublicRepositoryCase(
        language="brightscript",
        repository_url="https://github.com/rokudev/scenegraph-master-sample.git",
        expected_primary_ecosystem="brightscript",
        focus_paths=("DeepLinking",),
    ),
    PublicRepositoryCase(
        language="gnuplot",
        repository_url="https://github.com/gnuplot/gnuplot.git",
        expected_primary_ecosystem="gnuplot",
        focus_paths=("demo",),
    ),
    PublicRepositoryCase(
        language="dataweave",
        repository_url="https://github.com/mulesoft/docs-dataweave.git",
        expected_primary_ecosystem="dataweave",
        focus_paths=("modules/ROOT/pages/_partials/cookbook-dw",),
    ),
    PublicRepositoryCase(
        language="common workflow language",
        repository_url="https://github.com/common-workflow-language/user_guide.git",
        expected_primary_ecosystem="common workflow language",
        focus_paths=("src/_includes/cwl",),
    ),
    PublicRepositoryCase(
        language="earthly",
        repository_url="https://github.com/earthly/earthly.git",
        expected_primary_ecosystem="earthly",
        focus_paths=("tests/import",),
    ),
    PublicRepositoryCase(
        language="maven",
        repository_url="https://github.com/apache/maven.git",
        expected_primary_ecosystem="maven",
        focus_paths=("pom.xml", ".mvn"),
    ),
    PublicRepositoryCase(
        language="ampl",
        repository_url="https://github.com/ampl/ampl.github.io.git",
        expected_primary_ecosystem="ampl",
        focus_paths=("models",),
    ),
    PublicRepositoryCase(
        language="openedge",
        repository_url="https://github.com/CameronWills/OEUnit.git",
        expected_primary_ecosystem="openedge",
        focus_paths=("src/OEUnit",),
    ),
    PublicRepositoryCase(
        language="processing",
        repository_url="https://github.com/processing/processing-examples.git",
        expected_primary_ecosystem="processing",
    ),
    PublicRepositoryCase(
        language="nsis",
        repository_url="https://github.com/bmatzelle/gow.git",
        expected_primary_ecosystem="nsis",
    ),
    PublicRepositoryCase(
        language="apacheconf",
        repository_url="https://github.com/quangdung92/apache2-config.git",
        expected_primary_ecosystem="apacheconf",
    ),
    PublicRepositoryCase(
        language="nginx",
        repository_url="https://github.com/nginx/nginx.git",
        expected_primary_ecosystem="nginx",
        focus_paths=("conf",),
    ),
    PublicRepositoryCase(
        language="aidl",
        repository_url="https://github.com/nexus-lab/relf-client-aidl.git",
        expected_primary_ecosystem="aidl",
    ),
    PublicRepositoryCase(
        language="nextflow",
        repository_url="https://github.com/nf-core/rnaseq.git",
        expected_primary_ecosystem="nextflow",
    ),
    PublicRepositoryCase(
        language="nextflow",
        repository_url="https://github.com/nf-core/atacseq.git",
        expected_primary_ecosystem="nextflow",
    ),
    PublicRepositoryCase(
        language="robotframework",
        repository_url="https://github.com/robotframework/WebDemo.git",
        expected_primary_ecosystem="robotframework",
    ),
    PublicRepositoryCase(
        language="robotframework",
        repository_url="https://github.com/robotframework/RobotDemo.git",
        expected_primary_ecosystem="robotframework",
    ),
    PublicRepositoryCase(
        language="gherkin",
        repository_url="https://github.com/FriendsOfBehat/SymfonyExtension.git",
        expected_primary_ecosystem="gherkin",
    ),
    PublicRepositoryCase(
        language="antlr",
        repository_url="https://github.com/drforr/perl6-ANTLR4.git",
        expected_primary_ecosystem="antlr",
    ),
    PublicRepositoryCase(
        language="typst",
        repository_url="https://github.com/typst/packages.git",
        expected_primary_ecosystem="typst",
    ),
    PublicRepositoryCase(
        language="typst",
        repository_url="https://github.com/typst/templates.git",
        expected_primary_ecosystem="typst",
    ),
    PublicRepositoryCase(
        language="lua",
        repository_url="https://github.com/luarocks/luarocks.git",
        expected_primary_ecosystem="lua",
    ),
    PublicRepositoryCase(
        language="lua",
        repository_url="https://github.com/kikito/middleclass.git",
        expected_primary_ecosystem="lua",
    ),
    PublicRepositoryCase(
        language="luau",
        repository_url="https://github.com/Ukendio/jecs.git",
        expected_primary_ecosystem="luau",
    ),
    PublicRepositoryCase(
        language="lisp",
        repository_url="https://github.com/fukamachi/clack.git",
        expected_primary_ecosystem="lisp",
    ),
    PublicRepositoryCase(
        language="lisp",
        repository_url="https://github.com/edicl/cl-ppcre.git",
        expected_primary_ecosystem="lisp",
    ),
    PublicRepositoryCase(
        language="puppet",
        repository_url="https://github.com/puppetlabs/puppetlabs-apache.git",
        expected_primary_ecosystem="puppet",
    ),
    PublicRepositoryCase(
        language="bitbake",
        repository_url="https://github.com/openembedded/meta-openembedded.git",
        expected_primary_ecosystem="bitbake",
    ),
    PublicRepositoryCase(
        language="janet",
        repository_url="https://github.com/janet-lang/jpm.git",
        expected_primary_ecosystem="janet",
    ),
    PublicRepositoryCase(
        language="scheme",
        repository_url="https://github.com/ashinn/irregex.git",
        expected_primary_ecosystem="scheme",
    ),
    PublicRepositoryCase(
        language="racket",
        repository_url="https://github.com/mbutterick/pollen.git",
        expected_primary_ecosystem="racket",
    ),
    PublicRepositoryCase(
        language="gdscript",
        repository_url="https://github.com/Orama-Interactive/Pixelorama.git",
        expected_primary_ecosystem="gdscript",
    ),
    PublicRepositoryCase(
        language="pawn",
        repository_url="https://github.com/Southclaws/ScavengeSurvive.git",
        expected_primary_ecosystem="pawn",
        focus_paths=("gamemodes", "filterscripts"),
    ),
    PublicRepositoryCase(
        language="postscript",
        repository_url="https://github.com/kenjihiranabe/The-Art-of-Linear-Algebra.git",
        expected_primary_ecosystem="postscript",
        focus_paths=("figs",),
    ),
    PublicRepositoryCase(
        language="smali",
        repository_url="https://github.com/phhusson/treble_experimentations.git",
        expected_primary_ecosystem="smali",
        focus_paths=("vendor-HAL/Huawei/fingerprint-nav/out",),
    ),
    PublicRepositoryCase(
        language="motoko",
        repository_url="https://github.com/dfinity/motoko-base.git",
        expected_primary_ecosystem="motoko",
        focus_paths=("src",),
    ),
    PublicRepositoryCase(
        language="m4",
        repository_url="https://github.com/autotools-mirror/autoconf.git",
        expected_primary_ecosystem="m4",
        focus_paths=("lib/autoconf",),
    ),
    PublicRepositoryCase(
        language="forth",
        repository_url="https://github.com/forthy42/gforth.git",
        expected_primary_ecosystem="forth",
        focus_paths=("kernel",),
    ),
    PublicRepositoryCase(
        language="isabelle",
        repository_url="https://github.com/seL4/l4v.git",
        expected_primary_ecosystem="isabelle",
        focus_paths=("proof",),
    ),
    PublicRepositoryCase(
        language="mercury",
        repository_url="https://github.com/Mercury-Language/mercury.git",
        expected_primary_ecosystem="mercury",
        focus_paths=("library",),
    ),
    PublicRepositoryCase(
        language="red",
        repository_url="https://github.com/red/red.git",
        expected_primary_ecosystem="red",
        focus_paths=("encapper", "runtime"),
    ),
    PublicRepositoryCase(
        language="apl",
        repository_url="https://github.com/aplteam/Tatin.git",
        expected_primary_ecosystem="apl",
        focus_paths=("APLSource",),
    ),
    PublicRepositoryCase(
        language="apl",
        repository_url="https://github.com/Dyalog/documentation.git",
        expected_primary_ecosystem="apl",
        focus_paths=("tools/buildgui",),
    ),
    PublicRepositoryCase(
        language="hoon",
        repository_url="https://github.com/urbit/urbit.git",
        expected_primary_ecosystem="hoon",
        focus_paths=("pkg/arvo/app", "pkg/arvo/gen"),
    ),
    PublicRepositoryCase(
        language="sed",
        repository_url="https://github.com/vlajos/misspell-fixer.git",
        expected_primary_ecosystem="sed",
        focus_paths=("rules",),
    ),
    PublicRepositoryCase(
        language="metal",
        repository_url="https://github.com/twostraws/Inferno.git",
        expected_primary_ecosystem="metal",
        focus_paths=("Sources/Inferno/Shaders",),
    ),
    PublicRepositoryCase(
        language="bqn",
        repository_url="https://github.com/mlochbaum/bqn-libs.git",
        expected_primary_ecosystem="bqn",
    ),
    PublicRepositoryCase(
        language="rebol",
        repository_url="https://github.com/gchiu/Rebol3.git",
        expected_primary_ecosystem="rebol",
    ),
    PublicRepositoryCase(
        language="dm",
        repository_url="https://github.com/BurgerLUA/burgerstation.git",
        expected_primary_ecosystem="dm",
    ),
    PublicRepositoryCase(
        language="gml",
        repository_url="https://github.com/Gizmo199/BehaviorTree.git",
        expected_primary_ecosystem="gml",
    ),
    PublicRepositoryCase(
        language="vbscript",
        repository_url="https://github.com/susam/aes.vbs.git",
        expected_primary_ecosystem="vbscript",
    ),
    PublicRepositoryCase(
        language="elixir",
        repository_url="https://github.com/phoenixframework/phoenix.git",
        expected_primary_ecosystem="elixir",
    ),
    PublicRepositoryCase(
        language="elixir",
        repository_url="https://github.com/elixir-ecto/ecto.git",
        expected_primary_ecosystem="elixir",
    ),
    PublicRepositoryCase(
        language="ladder",
        repository_url="https://github.com/JeremyMedders/LogixLibraries.git",
        expected_primary_ecosystem="ladder",
    ),
    PublicRepositoryCase(
        language="solidity",
        repository_url="https://github.com/OpenZeppelin/openzeppelin-contracts.git",
        expected_primary_ecosystem="solidity",
    ),
    PublicRepositoryCase(
        language="glsl",
        repository_url="https://github.com/ashima/webgl-noise.git",
        expected_primary_ecosystem="glsl",
    ),
    PublicRepositoryCase(
        language="hlsl",
        repository_url="https://github.com/crosire/reshade-shaders.git",
        expected_primary_ecosystem="hlsl",
    ),
    PublicRepositoryCase(
        language="wgsl",
        repository_url="https://github.com/alphastrata/shadplay.git",
        expected_primary_ecosystem="wgsl",
    ),
    PublicRepositoryCase(
        language="verilog",
        repository_url="https://github.com/TimRudy/uart-verilog.git",
        expected_primary_ecosystem="verilog",
    ),
    PublicRepositoryCase(
        language="systemverilog",
        repository_url="https://github.com/pulp-platform/axi.git",
        expected_primary_ecosystem="systemverilog",
    ),
    PublicRepositoryCase(
        language="vhdl",
        repository_url="https://github.com/kevinpt/vhdl-extras.git",
        expected_primary_ecosystem="vhdl",
    ),
    PublicRepositoryCase(
        language="qsharp",
        repository_url="https://github.com/microsoft/QuantumLibraries.git",
        expected_primary_ecosystem="qsharp",
    ),
    PublicRepositoryCase(
        language="qsharp",
        repository_url="https://github.com/microsoft/qsharp.git",
        expected_primary_ecosystem="qsharp",
    ),
    PublicRepositoryCase(
        language="clojurescript",
        repository_url="https://github.com/reagent-project/reagent.git",
        expected_primary_ecosystem="clojurescript",
    ),
    PublicRepositoryCase(
        language="erlang",
        repository_url="https://github.com/erlang/rebar3.git",
        expected_primary_ecosystem="erlang",
    ),
    PublicRepositoryCase(
        language="clojure",
        repository_url="https://github.com/babashka/babashka.git",
        expected_primary_ecosystem="clojure",
    ),
    PublicRepositoryCase(
        language="clojure",
        repository_url="https://github.com/clojure/clojure.git",
        expected_primary_ecosystem="clojure",
    ),
    PublicRepositoryCase(
        language="r",
        repository_url="https://github.com/tidyverse/ggplot2.git",
        expected_primary_ecosystem="r",
    ),
    PublicRepositoryCase(
        language="cfml",
        repository_url="https://github.com/ghidinelli/cfpayment.git",
        expected_primary_ecosystem="cfml",
    ),
    PublicRepositoryCase(
        language="xpp",
        repository_url="https://github.com/TrudAX/XppTools.git",
        expected_primary_ecosystem="xpp",
    ),
    PublicRepositoryCase(
        language="al",
        repository_url="https://github.com/microsoft/ALAppExtensions.git",
        expected_primary_ecosystem="al",
    ),
    PublicRepositoryCase(
        language="matlab",
        repository_url="https://github.com/matlab2tikz/matlab2tikz.git",
        expected_primary_ecosystem="matlab",
    ),
    PublicRepositoryCase(
        language="objectivec",
        repository_url="https://github.com/AFNetworking/AFNetworking.git",
        expected_primary_ecosystem="objectivec",
    ),
    PublicRepositoryCase(
        language="julia",
        repository_url="https://github.com/JuliaData/DataFrames.jl.git",
        expected_primary_ecosystem="julia",
    ),
    PublicRepositoryCase(
        language="haskell",
        repository_url="https://github.com/commercialhaskell/stack.git",
        expected_primary_ecosystem="haskell",
    ),
    PublicRepositoryCase(
        language="lean",
        repository_url="https://github.com/leanprover-community/batteries.git",
        expected_primary_ecosystem="lean",
    ),
    PublicRepositoryCase(
        language="agda",
        repository_url="https://github.com/agda/agda-stdlib.git",
        expected_primary_ecosystem="agda",
    ),
    PublicRepositoryCase(
        language="dafny",
        repository_url="https://github.com/dafny-lang/libraries.git",
        expected_primary_ecosystem="dafny",
        focus_paths=("src", "examples"),
    ),
    PublicRepositoryCase(
        language="coq",
        repository_url="https://github.com/coq-community/coq-art.git",
        expected_primary_ecosystem="coq",
    ),
    PublicRepositoryCase(
        language="idris",
        repository_url="https://github.com/stefan-hoeck/idris2-pack.git",
        expected_primary_ecosystem="idris",
    ),
    PublicRepositoryCase(
        language="haxe",
        repository_url="https://github.com/HaxeFoundation/hscript.git",
        expected_primary_ecosystem="haxe",
    ),
    PublicRepositoryCase(
        language="move",
        repository_url="https://github.com/aave/aptos-aave-v3.git",
        expected_primary_ecosystem="move",
    ),
    PublicRepositoryCase(
        language="sway",
        repository_url="https://github.com/FuelLabs/sway-libs.git",
        expected_primary_ecosystem="sway",
    ),
    PublicRepositoryCase(
        language="odin",
        repository_url="https://github.com/odin-lang/examples.git",
        expected_primary_ecosystem="odin",
    ),
    PublicRepositoryCase(
        language="ocaml",
        repository_url="https://github.com/ocaml-community/utop.git",
        expected_primary_ecosystem="ocaml",
    ),
    PublicRepositoryCase(
        language="ocamllex",
        repository_url="https://github.com/let-def/ocamllex-refill.git",
        expected_primary_ecosystem="ocamllex",
        focus_paths=("lexer.mll",),
    ),
    PublicRepositoryCase(
        language="ocamlyacc",
        repository_url="https://github.com/amblafont/sedlex-menhir.git",
        expected_primary_ecosystem="ocamlyacc",
        focus_paths=("ocamllex-ocamlyacc/parser.mly",),
    ),
    PublicRepositoryCase(
        language="thrift",
        repository_url="https://github.com/apache/thrift.git",
        expected_primary_ecosystem="thrift",
        focus_paths=("test", "tutorial"),
    ),
    PublicRepositoryCase(
        language="perl",
        repository_url="https://github.com/dagolden/Path-Tiny.git",
        expected_primary_ecosystem="perl",
    ),
    PublicRepositoryCase(
        language="raku",
        repository_url="https://github.com/ugexe/zef.git",
        expected_primary_ecosystem="raku",
    ),
    PublicRepositoryCase(
        language="powershell",
        repository_url="https://github.com/Pester/Pester.git",
        expected_primary_ecosystem="powershell",
    ),
    PublicRepositoryCase(
        language="just",
        repository_url="https://github.com/ublue-os/image-template.git",
        expected_primary_ecosystem="just",
    ),
    PublicRepositoryCase(
        language="makefile",
        repository_url="https://github.com/lindenb/makefile2graph.git",
        expected_primary_ecosystem="makefile",
    ),
    PublicRepositoryCase(
        language="batchfile",
        repository_url="https://github.com/npocmaka/batch.scripts.git",
        expected_primary_ecosystem="batchfile",
    ),
    PublicRepositoryCase(
        language="autohotkey",
        repository_url="https://github.com/thqby/ahk2_lib.git",
        expected_primary_ecosystem="autohotkey",
    ),
    PublicRepositoryCase(
        language="autoit",
        repository_url="https://github.com/rcmaehl/WhyNotWin11.git",
        expected_primary_ecosystem="autoit",
    ),
    PublicRepositoryCase(
        language="squirrel",
        repository_url="https://github.com/p2r3/HTTPortal.git",
        expected_primary_ecosystem="squirrel",
    ),
    PublicRepositoryCase(
        language="starlark",
        repository_url="https://github.com/bazelbuild/bazel-skylib.git",
        expected_primary_ecosystem="starlark",
    ),
    PublicRepositoryCase(
        language="hcl",
        repository_url="https://github.com/terraform-aws-modules/terraform-aws-vpc.git",
        expected_primary_ecosystem="hcl",
    ),
    PublicRepositoryCase(
        language="vcl",
        repository_url="https://github.com/varnishcache/varnish-cache.git",
        expected_primary_ecosystem="vcl",
        focus_paths=("etc", "bin/varnishd"),
    ),
    PublicRepositoryCase(
        language="tlaplus",
        repository_url="https://github.com/tlaplus/Examples.git",
        expected_primary_ecosystem="tlaplus",
    ),
    PublicRepositoryCase(
        language="bicep",
        repository_url="https://github.com/Azure/bicep-registry-modules.git",
        expected_primary_ecosystem="bicep",
    ),
    PublicRepositoryCase(
        language="cue",
        repository_url="https://github.com/cue-labs/cue-by-example.git",
        expected_primary_ecosystem="cue",
    ),
    PublicRepositoryCase(
        language="dhall",
        repository_url="https://github.com/regadas/github-actions-dhall.git",
        expected_primary_ecosystem="dhall",
    ),
    PublicRepositoryCase(
        language="rego",
        repository_url="https://github.com/open-policy-agent/library.git",
        expected_primary_ecosystem="rego",
    ),
    PublicRepositoryCase(
        language="yara",
        repository_url="https://github.com/YARA-Rules/rules.git",
        expected_primary_ecosystem="yara",
    ),
    PublicRepositoryCase(
        language="nix",
        repository_url="https://github.com/numtide/flake-utils.git",
        expected_primary_ecosystem="nix",
    ),
    PublicRepositoryCase(
        language="jsonnet",
        repository_url="https://github.com/jsonnet-libs/k8s-libsonnet.git",
        expected_primary_ecosystem="jsonnet",
    ),
    PublicRepositoryCase(
        language="jsonnet",
        repository_url="https://github.com/grafana/grafonnet.git",
        expected_primary_ecosystem="jsonnet",
        focus_paths=("gen/grafonnet-latest", "custom"),
    ),
    PublicRepositoryCase(
        language="openscad",
        repository_url="https://github.com/BelfrySCAD/BOSL2.git",
        expected_primary_ecosystem="openscad",
    ),
    PublicRepositoryCase(
        language="xslt",
        repository_url="https://github.com/docbook/xslt20-stylesheets.git",
        expected_primary_ecosystem="xslt",
    ),
    PublicRepositoryCase(
        language="yacc",
        repository_url="https://github.com/jengelsma/yacc-tutorial.git",
        expected_primary_ecosystem="yacc",
    ),
    PublicRepositoryCase(
        language="lex",
        repository_url="https://github.com/andanciu/LexicalScanner.git",
        expected_primary_ecosystem="lex",
    ),
    PublicRepositoryCase(
        language="xquery",
        repository_url="https://github.com/robwhitby/xray.git",
        expected_primary_ecosystem="xquery",
    ),
    PublicRepositoryCase(
        language="q",
        repository_url="https://github.com/DataIntellectTech/TorQ.git",
        expected_primary_ecosystem="q",
        focus_paths=("code", "config/settings"),
    ),
    PublicRepositoryCase(
        language="j",
        repository_url="https://github.com/jsoftware/base9.git",
        expected_primary_ecosystem="j",
    ),
    PublicRepositoryCase(
        language="factor",
        repository_url="https://github.com/bjourne/playground-factor.git",
        expected_primary_ecosystem="factor",
    ),
    PublicRepositoryCase(
        language="purescript",
        repository_url="https://github.com/purescript/purescript-prelude.git",
        expected_primary_ecosystem="purescript",
    ),
    PublicRepositoryCase(
        language="rescript",
        repository_url="https://github.com/glennsl/rescript-json-combinators.git",
        expected_primary_ecosystem="rescript",
    ),
    PublicRepositoryCase(
        language="reasonml",
        repository_url="https://github.com/reasonml-community/bs-json.git",
        expected_primary_ecosystem="reasonml",
    ),
    PublicRepositoryCase(
        language="roc",
        repository_url="https://github.com/roc-lang/book-of-examples.git",
        expected_primary_ecosystem="roc",
    ),
    PublicRepositoryCase(
        language="moonbit",
        repository_url="https://github.com/moonbitlang/core.git",
        expected_primary_ecosystem="moonbit",
    ),
    PublicRepositoryCase(
        language="hy",
        repository_url="https://github.com/hylang/hydiomatic.git",
        expected_primary_ecosystem="hy",
    ),
    PublicRepositoryCase(
        language="wren",
        repository_url="https://github.com/exercism/wren.git",
        expected_primary_ecosystem="wren",
    ),
    PublicRepositoryCase(
        language="fennel",
        repository_url="https://github.com/bakpakin/Fennel.git",
        expected_primary_ecosystem="fennel",
    ),
    PublicRepositoryCase(
        language="vyper",
        repository_url="https://github.com/curvefi/tricrypto-ng.git",
        expected_primary_ecosystem="vyper",
    ),
    PublicRepositoryCase(
        language="clarity",
        repository_url="https://github.com/friedger/clarity-smart-contracts.git",
        expected_primary_ecosystem="clarity",
        focus_paths=("contracts", "owned-profiles/contracts", "test"),
    ),
    PublicRepositoryCase(
        language="circom",
        repository_url="https://github.com/iden3/circomlib.git",
        expected_primary_ecosystem="circom",
        focus_paths=("circuits", "test"),
    ),
    PublicRepositoryCase(
        language="circom",
        repository_url="https://github.com/0xPARC/circom-ecdsa.git",
        expected_primary_ecosystem="circom",
    ),
    PublicRepositoryCase(
        language="cairo",
        repository_url="https://github.com/OpenZeppelin/cairo-contracts.git",
        expected_primary_ecosystem="cairo",
    ),
    PublicRepositoryCase(
        language="modelica",
        repository_url="https://github.com/modelica/ModelicaStandardLibrary.git",
        expected_primary_ecosystem="modelica",
    ),
    PublicRepositoryCase(
        language="gleam",
        repository_url="https://github.com/gleam-lang/stdlib.git",
        expected_primary_ecosystem="gleam",
    ),
    PublicRepositoryCase(
        language="ballerina",
        repository_url="https://github.com/ballerina-platform/module-ballerina-http.git",
        expected_primary_ecosystem="ballerina",
    ),
    PublicRepositoryCase(
        language="webassembly",
        repository_url="https://github.com/WebAssembly/spec.git",
        expected_primary_ecosystem="webassembly",
        focus_paths=("test/core",),
    ),
    PublicRepositoryCase(
        language="nushell",
        repository_url="https://github.com/nushell/nu_scripts.git",
        expected_primary_ecosystem="nushell",
    ),
    PublicRepositoryCase(
        language="pkl",
        repository_url="https://github.com/apple/pkl.git",
        expected_primary_ecosystem="pkl",
        focus_paths=("pkl-core/src/test/files/LanguageSnippetTests/input",),
    ),
    PublicRepositoryCase(
        language="apex",
        repository_url="https://github.com/apex-enterprise-patterns/fflib-apex-common.git",
        expected_primary_ecosystem="apex",
    ),
    PublicRepositoryCase(
        language="labview",
        repository_url="https://github.com/LabVIEW-Open-Source/ui-tools.git",
        expected_primary_ecosystem="labview",
    ),
    PublicRepositoryCase(
        language="tcl",
        repository_url="https://github.com/tcltk/tcllib.git",
        expected_primary_ecosystem="tcl",
    ),
    PublicRepositoryCase(
        language="v",
        repository_url="https://github.com/vlang/ui.git",
        expected_primary_ecosystem="v",
    ),
    PublicRepositoryCase(
        language="vala",
        repository_url="https://github.com/GNOME/vala.git",
        expected_primary_ecosystem="vala",
    ),
    PublicRepositoryCase(
        language="smalltalk",
        repository_url="https://github.com/pharo-spec/Spec.git",
        expected_primary_ecosystem="smalltalk",
    ),
    PublicRepositoryCase(
        language="visualbasic",
        repository_url="https://github.com/kimmknight/remoteapptool.git",
        expected_primary_ecosystem="visualbasic",
    ),
    PublicRepositoryCase(
        language="mql5",
        repository_url="https://github.com/geraked/metatrader5.git",
        expected_primary_ecosystem="mql5",
    ),
    PublicRepositoryCase(
        language="gams",
        repository_url="https://github.com/psztorc/DICE.git",
        expected_primary_ecosystem="gams",
    ),
    PublicRepositoryCase(
        language="wolfram",
        repository_url="https://github.com/WolframResearch/PacletCICD.git",
        expected_primary_ecosystem="wolfram",
    ),
    PublicRepositoryCase(
        language="rpg",
        repository_url="https://github.com/IBM/bob-recursive-example.git",
        expected_primary_ecosystem="rpg",
    ),
    PublicRepositoryCase(
        language="actionscript",
        repository_url="https://github.com/Gamua/Starling-Framework.git",
        expected_primary_ecosystem="actionscript",
    ),
    PublicRepositoryCase(
        language="applescript",
        repository_url="https://github.com/unforswearing/applescript.git",
        expected_primary_ecosystem="applescript",
    ),
    PublicRepositoryCase(
        language="awk",
        repository_url="https://github.com/step-/JSON.awk.git",
        expected_primary_ecosystem="awk",
    ),
    PublicRepositoryCase(
        language="coffeescript",
        repository_url="https://github.com/jashkenas/coffeescript.git",
        expected_primary_ecosystem="coffeescript",
    ),
    PublicRepositoryCase(
        language="moonscript",
        repository_url="https://github.com/leafo/moonscript.git",
        expected_primary_ecosystem="moonscript",
        focus_paths=("moon", "moonscript", "bin"),
    ),
    PublicRepositoryCase(
        language="templ",
        repository_url="https://github.com/a-h/templ.git",
        expected_primary_ecosystem="templ",
        focus_paths=("examples", "generator/test-templ-files"),
    ),
    PublicRepositoryCase(
        language="elm",
        repository_url="https://github.com/elm/core.git",
        expected_primary_ecosystem="elm",
    ),
    PublicRepositoryCase(
        language="emacslisp",
        repository_url="https://github.com/magnars/dash.el.git",
        expected_primary_ecosystem="emacslisp",
    ),
    PublicRepositoryCase(
        language="vimscript",
        repository_url="https://github.com/tpope/vim-fugitive.git",
        expected_primary_ecosystem="vimscript",
    ),
    PublicRepositoryCase(
        language="zig",
        repository_url="https://github.com/zigtools/zls.git",
        expected_primary_ecosystem="zig",
    ),
    PublicRepositoryCase(
        language="nim",
        repository_url="https://github.com/nim-lang/nimble.git",
        expected_primary_ecosystem="nim",
    ),
    PublicRepositoryCase(
        language="crystal",
        repository_url="https://github.com/crystal-lang/crystal.git",
        expected_primary_ecosystem="crystal",
    ),
    PublicRepositoryCase(
        language="fsharp",
        repository_url="https://github.com/fsprojects/FSharp.Data.git",
        expected_primary_ecosystem="fsharp",
    ),
    PublicRepositoryCase(
        language="foxpro",
        repository_url="https://github.com/Irwin1985/FoxBarcode.git",
        expected_primary_ecosystem="foxpro",
    ),
    PublicRepositoryCase(
        language="foxpro",
        repository_url="https://github.com/VFPX/nfJson.git",
        expected_primary_ecosystem="foxpro",
    ),
    PublicRepositoryCase(
        language="pascal",
        repository_url="https://github.com/transmission-remote-gui/transgui.git",
        expected_primary_ecosystem="pascal",
    ),
    PublicRepositoryCase(
        language="freebasic",
        repository_url="https://github.com/freebasic/fbc.git",
        expected_primary_ecosystem="freebasic",
        focus_paths=("examples", "inc", "src"),
    ),
    PublicRepositoryCase(
        language="purebasic",
        repository_url="https://github.com/fantaisie-software/purebasic.git",
        expected_primary_ecosystem="purebasic",
        focus_paths=("PureBasicIDE", "Residents"),
    ),
    PublicRepositoryCase(
        language="pony",
        repository_url="https://github.com/ponylang/http.git",
        expected_primary_ecosystem="pony",
        focus_paths=("http", "examples"),
    ),
    PublicRepositoryCase(
        language="fortran",
        repository_url="https://github.com/fortran-lang/fpm.git",
        expected_primary_ecosystem="fortran",
    ),
    PublicRepositoryCase(
        language="mojo",
        repository_url="https://github.com/gabrieldemarmiesse/mojo-stdlib-extensions.git",
        expected_primary_ecosystem="mojo",
    ),
    PublicRepositoryCase(
        language="d",
        repository_url="https://github.com/dlang/phobos.git",
        expected_primary_ecosystem="d",
    ),
)


def _case_checkout_name(case: PublicRepositoryCase) -> str:
    parsed = urlparse(case.repository_url)
    path_parts = [part for part in parsed.path.removesuffix(".git").split("/") if part]
    if len(path_parts) < 2:
        raise ValueError(f"repository_url must include owner/repo: {case.repository_url}")
    owner, repo = path_parts[-2], path_parts[-1]
    return f"{case.language}-{owner}-{repo}"


def ordered_public_repository_cases(
    *,
    cases: tuple[PublicRepositoryCase, ...] = DEFAULT_PUBLIC_REPOSITORY_CASES,
    languages: tuple[str, ...] = (),
    limit: int | None = None,
) -> list[PublicRepositoryCase]:
    allowed_languages = {
        canonical_language
        for language in languages
        if (canonical_language := canonical_repository_language(language))
    }
    filtered_cases = [
        case
        for case in cases
        if (
            not allowed_languages
            or canonical_repository_language(case.language) in allowed_languages
        )
    ]
    language_order = sort_repository_languages(case.language for case in filtered_cases)
    language_index = {language: index for index, language in enumerate(language_order)}
    ordered_cases = sorted(
        filtered_cases,
        key=lambda case: (
            language_index.get(case.language, len(language_index)),
            case.language,
            _case_checkout_name(case),
        ),
    )
    if limit is None:
        return ordered_cases
    return ordered_cases[: max(0, limit)]


def configured_public_repository_case_languages(
    *,
    cases: tuple[PublicRepositoryCase, ...] = DEFAULT_PUBLIC_REPOSITORY_CASES,
) -> tuple[str, ...]:
    return tuple(sort_repository_languages({case.language for case in cases}))


def missing_supported_public_repository_languages(
    *,
    cases: tuple[PublicRepositoryCase, ...] = DEFAULT_PUBLIC_REPOSITORY_CASES,
) -> tuple[str, ...]:
    covered_languages = set(configured_public_repository_case_languages(cases=cases))
    return tuple(
        language for language in supported_repository_languages() if language not in covered_languages
    )


def _validated_public_repository_url(repository_url: str) -> str:
    parsed = urlparse(repository_url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise ValueError(
            f"Only https://github.com public repositories are supported: {repository_url}"
        )
    if len([part for part in parsed.path.removesuffix(".git").split("/") if part]) < 2:
        raise ValueError(f"repository_url must include owner/repo: {repository_url}")
    return repository_url


def _public_repository_checkout_lock_path(checkout_path: Path) -> Path:
    return checkout_path.parent / f"{checkout_path.name}.lock"


def _acquire_public_repository_checkout_lock(checkout_path: Path) -> Path:
    checkout_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _public_repository_checkout_lock_path(checkout_path)
    deadline = time.monotonic() + _PUBLIC_REPOSITORY_CHECKOUT_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock_path.mkdir()
            return lock_path
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    json.dumps(
                        {
                            "error": {
                                "code": "public_repo_checkout_lock_timeout",
                                "message": (
                                    f"Timed out waiting for checkout lock for {checkout_path.name}."
                                ),
                                "details": {
                                    "checkout_path": str(checkout_path),
                                    "lock_path": str(lock_path),
                                },
                            }
                        }
                    )
                )
            time.sleep(_PUBLIC_REPOSITORY_CHECKOUT_LOCK_POLL_INTERVAL_SECONDS)


def _clone_public_repository_case_unlocked(
    case: PublicRepositoryCase,
    *,
    checkout_root: Path,
    refresh: bool = False,
) -> Path:
    checkout_path = checkout_root / _case_checkout_name(case)
    if checkout_path.exists() and refresh:
        _invalidate_public_repository_checkout_caches(checkout_path)
        shutil.rmtree(checkout_path)
    if _is_reusable_public_repository_checkout(checkout_path):
        _warm_public_repository_reusable_checkout_caches(
            case=case,
            checkout_path=checkout_path,
        )
        return checkout_path
    if checkout_path.exists():
        _invalidate_public_repository_checkout_caches(checkout_path)
        shutil.rmtree(checkout_path)
    checkout_root.mkdir(parents=True, exist_ok=True)
    validated_repository_url = _validated_public_repository_url(case.repository_url)
    git_executable = _git_executable()
    clone_error_payload: dict[str, Any] | None = None
    for attempt in range(_PUBLIC_REPOSITORY_CLONE_ATTEMPTS):
        completed = subprocess.run(  # noqa: S603
            _public_repository_clone_command(
                git_executable=git_executable,
                repository_url=validated_repository_url,
                checkout_path=checkout_path,
            ),
            capture_output=True,
            check=False,
            encoding="utf-8",
            env=_public_repository_clone_environment(),
            text=True,
            timeout=300,
        )
        if completed.returncode == 0:
            try:
                _materialize_public_repository_checkout(
                    case,
                    git_executable=git_executable,
                    checkout_path=checkout_path,
                    repository_url=validated_repository_url,
                )
            except RuntimeError as exc:
                clone_error_payload = json.loads(str(exc))
            else:
                if _is_reusable_public_repository_checkout(checkout_path):
                    return checkout_path
                clone_error_payload = {
                    "error": {
                        "code": "public_repo_checkout_incomplete",
                        "message": (
                            f"Clone of {validated_repository_url} did not produce a reusable checkout."
                        ),
                        "details": {},
                    }
                }
        else:
            clone_error_payload = {
                "error": {
                    "code": "public_repo_clone_failed",
                    "message": f"Failed to clone {validated_repository_url}.",
                    "details": {
                        "returncode": completed.returncode,
                        "stderr": completed.stderr.strip(),
                    },
                }
            }
        if checkout_path.exists():
            shutil.rmtree(checkout_path)
        if attempt + 1 >= _PUBLIC_REPOSITORY_CLONE_ATTEMPTS:
            break
    if clone_error_payload is None:
        clone_error_payload = {
            "error": {
                "code": "public_repo_clone_failed",
                "message": f"Failed to clone {validated_repository_url}.",
                "details": {},
            }
        }
    raise RuntimeError(json.dumps(clone_error_payload))


@contextmanager
def _public_repository_checkout_context(
    case: PublicRepositoryCase,
    *,
    checkout_root: Path,
    refresh: bool = False,
):
    checkout_path = checkout_root / _case_checkout_name(case)
    lock_path = _acquire_public_repository_checkout_lock(checkout_path)
    try:
        yield _clone_public_repository_case_unlocked(
            case,
            checkout_root=checkout_root,
            refresh=refresh,
        )
    finally:
        if lock_path.exists():
            shutil.rmtree(lock_path, ignore_errors=True)


def _git_executable() -> str:
    git_path = shutil.which("git")
    if not git_path:
        raise RuntimeError(
            json.dumps(
                {
                    "error": {
                        "code": "git_not_found",
                        "message": "The public repository matrix requires git to be installed.",
                        "details": {},
                    }
                }
            )
        )
    return git_path


def _public_repository_clone_command(
    *,
    git_executable: str,
    repository_url: str,
    checkout_path: Path,
) -> list[str]:
    return [
        git_executable,
        "clone",
        "--depth",
        "1",
        "--filter=blob:none",
        "--single-branch",
        "--no-tags",
        "--no-checkout",
        repository_url,
        str(checkout_path),
    ]


def _public_repository_clone_environment() -> dict[str, str]:
    clone_environment = dict(os.environ)
    clone_environment["GIT_LFS_SKIP_SMUDGE"] = "1"
    clone_environment["GIT_TERMINAL_PROMPT"] = "0"
    return clone_environment


def _public_repository_checkout_command(
    *,
    git_executable: str,
    checkout_path: Path,
    git_args: list[str],
) -> list[str]:
    return [git_executable, "-C", str(checkout_path), *git_args]


def _run_public_repository_checkout_command(
    *,
    git_executable: str,
    checkout_path: Path,
    git_args: list[str],
    timeout_seconds: int = 300,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        _public_repository_checkout_command(
            git_executable=git_executable,
            checkout_path=checkout_path,
            git_args=git_args,
        ),
        capture_output=True,
        check=False,
        encoding="utf-8",
        env=_public_repository_clone_environment(),
        text=True,
        timeout=timeout_seconds,
    )


def _raise_public_repository_checkout_error(
    *,
    repository_url: str,
    stage: str,
    code: str,
    message: str,
    details: dict[str, Any],
) -> None:
    raise RuntimeError(
        json.dumps(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": {
                        "repository_url": repository_url,
                        "stage": stage,
                        **details,
                    },
                }
            }
        )
    )


def _public_repository_tracked_relative_files(
    *,
    git_executable: str,
    checkout_path: Path,
    repository_url: str,
) -> list[str]:
    completed = _run_public_repository_checkout_command(
        git_executable=git_executable,
        checkout_path=checkout_path,
        git_args=["ls-tree", "-r", "--name-only", "--full-tree", "HEAD"],
        timeout_seconds=180,
    )
    if completed.returncode != 0:
        _raise_public_repository_checkout_error(
            repository_url=repository_url,
            stage="ls_tree",
            code="public_repo_checkout_prepass_failed",
            message=f"Failed to enumerate tracked files for {repository_url}.",
            details={
                "returncode": completed.returncode,
                "stderr": completed.stderr.strip(),
            },
        )
    repository_service = probe_module.repository_service
    tracked_relative_paths: list[str] = []
    seen_relative_paths: set[str] = set()
    for line in completed.stdout.splitlines():
        normalized_path = repository_service._normalize_repository_relative_path(line)
        if not normalized_path or normalized_path in seen_relative_paths:
            continue
        seen_relative_paths.add(normalized_path)
        tracked_relative_paths.append(normalized_path)
    # Cache the (deterministically sorted) listing, but return the original git ``ls-tree``
    # order so callers that need to derive an ordered focus slice (e.g. top-level code roots)
    # can do so before the order is lost to the sorted cache.
    _store_public_repository_tracked_relative_files(
        repo_path=checkout_path,
        relative_paths=tracked_relative_paths,
    )
    return tracked_relative_paths


def _public_repository_head_revision(
    *,
    git_executable: str,
    checkout_path: Path,
    repository_url: str,
) -> str:
    cached_revision = _cached_public_repository_head_revision(checkout_path)
    if cached_revision is not None:
        return cached_revision
    completed = _run_public_repository_checkout_command(
        git_executable=git_executable,
        checkout_path=checkout_path,
        git_args=["rev-parse", "HEAD"],
        timeout_seconds=30,
    )
    if completed.returncode != 0:
        _raise_public_repository_checkout_error(
            repository_url=repository_url,
            stage="rev_parse_head",
            code="public_repo_checkout_revision_failed",
            message=f"Failed to resolve HEAD revision for {repository_url}.",
            details={
                "returncode": completed.returncode,
                "stderr": completed.stderr.strip(),
            },
        )
    resolved_revision = str(completed.stdout).strip().lower()
    if _PUBLIC_REPOSITORY_RESOLVED_OID_RE.fullmatch(resolved_revision) is None:
        _raise_public_repository_checkout_error(
            repository_url=repository_url,
            stage="rev_parse_head",
            code="public_repo_checkout_revision_invalid",
            message=f"HEAD revision for {repository_url} was not a 40-character git object id.",
            details={"stdout": completed.stdout.strip()},
        )
    return _store_public_repository_head_revision(
        repo_path=checkout_path,
        resolved_revision=resolved_revision,
    )


def _materialized_public_repository_focus_paths(checkout_path: Path) -> list[str]:
    sparse_checkout_path = checkout_path / ".git" / "info" / "sparse-checkout"
    try:
        raw_lines = sparse_checkout_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    materialized_focus_paths: list[str] = []
    parseable = True
    for raw_line in raw_lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line in {"/*", "/"} or line.startswith("!"):
            parseable = False
            break
        if line.endswith("/**"):
            line = line[:-3]
        normalized_focus_path = line.strip("/")
        if not normalized_focus_path or "*" in normalized_focus_path:
            parseable = False
            break
        materialized_focus_paths.append(normalized_focus_path)
    if not parseable:
        return []
    return list(dict.fromkeys(materialized_focus_paths))


def _store_public_repository_materialized_tracked_relative_files(
    *,
    checkout_path: Path,
    focus_paths: list[str],
) -> list[str]:
    materialized_relative_paths: list[str] = []
    seen_relative_paths: set[str] = set()
    for normalized_focus_path in _normalized_public_repository_focus_paths(focus_paths):
        candidate_path = checkout_path / normalized_focus_path
        if not candidate_path.exists():
            continue
        if candidate_path.is_file():
            normalized_relative_path = str(candidate_path.relative_to(checkout_path)).replace(
                "\\",
                "/",
            )
            if normalized_relative_path not in seen_relative_paths:
                seen_relative_paths.add(normalized_relative_path)
                materialized_relative_paths.append(normalized_relative_path)
            continue
        for dirpath, dirnames, filenames in os.walk(candidate_path):
            dirnames[:] = [dirname for dirname in dirnames if dirname != ".git"]
            for filename in filenames:
                relative_path = str((Path(dirpath) / filename).relative_to(checkout_path)).replace(
                    "\\",
                    "/",
                )
                if relative_path in seen_relative_paths:
                    continue
                seen_relative_paths.add(relative_path)
                materialized_relative_paths.append(relative_path)
    # Preserve focus-path order (lib before examples, …) — a materialized/sparse focus walk is
    # an ordered slice, not the unordered full listing, so it must not be re-sorted.
    return _cache_public_repository_tracked_relative_files(
        repo_path=checkout_path,
        normalized_relative_paths=tuple(
            _normalized_public_repository_tracked_relative_files(materialized_relative_paths)
        ),
    )


def _warm_public_repository_reusable_checkout_caches(
    *,
    case: PublicRepositoryCase,
    checkout_path: Path,
) -> None:
    normalized_case_focus_paths = _normalized_public_repository_focus_paths(
        list(case.focus_paths)
    )
    cached_tracked_relative_paths = _cached_public_repository_tracked_relative_files(checkout_path)
    cached_focus_paths = _cached_public_repository_prepass_focus_paths(
        repo_path=checkout_path,
        expected_primary_ecosystem=case.expected_primary_ecosystem,
    )
    if (
        _cached_public_repository_head_revision(checkout_path) is not None
        and cached_tracked_relative_paths is not None
        and cached_focus_paths is not None
        and (
            not normalized_case_focus_paths
            or _should_preserve_cached_prepass_focus_paths(
                tuple(cached_focus_paths),
                tuple(normalized_case_focus_paths),
            )
        )
    ):
        return
    git_executable = _git_executable()
    if (
        _cached_public_repository_head_revision(checkout_path) is None
        and (checkout_path / ".git" / "HEAD").exists()
    ):
        _public_repository_head_revision(
            git_executable=git_executable,
            checkout_path=checkout_path,
            repository_url=case.repository_url,
        )
    materialized_focus_paths = (
        normalized_case_focus_paths
        if normalized_case_focus_paths
        else _materialized_public_repository_focus_paths(checkout_path)
    )
    git_order_tracked_relative_paths: list[str] | None = None
    if cached_tracked_relative_paths is None:
        if materialized_focus_paths:
            _store_public_repository_materialized_tracked_relative_files(
                checkout_path=checkout_path,
                focus_paths=materialized_focus_paths,
            )
        elif (checkout_path / ".git" / "HEAD").exists():
            # Only enumerate tracked files when there is a resolvable HEAD — without it there
            # is no revision to ``ls-tree`` (and a reusable checkout that merely has a ``.git``
            # dir + working files must not be re-cloned just to warm caches).
            git_order_tracked_relative_paths = _public_repository_tracked_relative_files(
                git_executable=git_executable,
                checkout_path=checkout_path,
                repository_url=case.repository_url,
            )
    if materialized_focus_paths:
        _store_public_repository_prepass_focus_paths(
            repo_path=checkout_path,
            expected_primary_ecosystem=case.expected_primary_ecosystem,
            focus_paths=materialized_focus_paths,
        )
        _store_public_repository_materialized_tracked_relative_files(
            checkout_path=checkout_path,
            focus_paths=materialized_focus_paths,
        )
        return
    # Full checkout: the prepass focus is the top-level code directory roots of the tracked
    # listing in repository (git) order — covering every code root, not only the ones our
    # ecosystem hint happens to match (e.g. a C project's ``include`` holds ``.h`` files).
    if git_order_tracked_relative_paths:
        directory_roots = _public_repository_tracked_directory_roots(
            git_order_tracked_relative_paths,
            limit=_PUBLIC_REPOSITORY_PREPASS_FOCUS_LIMIT,
        )
        if directory_roots:
            _store_public_repository_prepass_focus_paths(
                repo_path=checkout_path,
                expected_primary_ecosystem=case.expected_primary_ecosystem,
                focus_paths=directory_roots,
            )
            return
    tracked_relative_paths = _cached_public_repository_tracked_relative_files(checkout_path)
    if tracked_relative_paths:
        ranked_focus_paths = _expected_ecosystem_prepass_focus_paths(
            repo_path=checkout_path,
            expected_primary_ecosystem=case.expected_primary_ecosystem,
            limit=_PUBLIC_REPOSITORY_PREPASS_FOCUS_LIMIT,
        )
        if ranked_focus_paths:
            _store_public_repository_prepass_focus_paths(
                repo_path=checkout_path,
                expected_primary_ecosystem=case.expected_primary_ecosystem,
                focus_paths=ranked_focus_paths,
            )


def _normalized_public_repository_focus_paths(
    focus_paths: tuple[str, ...] | list[str],
) -> list[str]:
    repository_service = probe_module.repository_service
    normalized_focus_paths: list[str] = []
    seen_focus_paths: set[str] = set()
    for raw_focus_path in focus_paths:
        normalized_focus_path = repository_service._normalize_repository_relative_path(
            raw_focus_path
        )
        if not normalized_focus_path or normalized_focus_path in seen_focus_paths:
            continue
        if any(
            normalized_focus_path == parent_path
            or normalized_focus_path.startswith(f"{parent_path}/")
            for parent_path in normalized_focus_paths
        ):
            continue
        descendant_paths = [
            existing_path
            for existing_path in normalized_focus_paths
            if existing_path.startswith(f"{normalized_focus_path}/")
        ]
        if descendant_paths:
            insertion_index = min(
                normalized_focus_paths.index(existing_path)
                for existing_path in descendant_paths
            )
            normalized_focus_paths = [
                existing_path
                for existing_path in normalized_focus_paths
                if existing_path not in descendant_paths
            ]
            seen_focus_paths.difference_update(descendant_paths)
            normalized_focus_paths.insert(insertion_index, normalized_focus_path)
            seen_focus_paths.add(normalized_focus_path)
            continue
        seen_focus_paths.add(normalized_focus_path)
        normalized_focus_paths.append(normalized_focus_path)
    return normalized_focus_paths


def _public_repository_sparse_checkout_focus_paths(
    case: PublicRepositoryCase,
    *,
    git_executable: str,
    checkout_path: Path,
    repository_url: str,
) -> list[str]:
    normalized_focus_paths = _normalized_public_repository_focus_paths(case.focus_paths)
    if normalized_focus_paths:
        return _store_public_repository_prepass_focus_paths(
            repo_path=checkout_path,
            expected_primary_ecosystem=case.expected_primary_ecosystem,
            focus_paths=normalized_focus_paths,
        )
    tracked_relative_paths = _public_repository_tracked_relative_files(
        git_executable=git_executable,
        checkout_path=checkout_path,
        repository_url=repository_url,
    )
    if not tracked_relative_paths:
        return []
    # Seed the tracked-files cache from the listing we just enumerated so the prepass below
    # reuses it instead of re-listing the repository (the clone-time enumeration is the single
    # source of truth for this checkout's tracked files).
    if _cached_public_repository_tracked_relative_files(checkout_path) is None:
        _store_public_repository_tracked_relative_files(
            repo_path=checkout_path,
            relative_paths=list(tracked_relative_paths),
        )
    derived_focus_paths = _expected_ecosystem_prepass_focus_paths(
        repo_path=checkout_path,
        expected_primary_ecosystem=case.expected_primary_ecosystem,
    )
    return _store_public_repository_prepass_focus_paths(
        repo_path=checkout_path,
        expected_primary_ecosystem=case.expected_primary_ecosystem,
        focus_paths=derived_focus_paths,
    )


def _public_repository_sparse_checkout_patterns(
    focus_paths: list[str],
) -> list[str]:
    repository_service = probe_module.repository_service
    patterns: list[str] = []
    seen_patterns: set[str] = set()
    for raw_focus_path in focus_paths:
        normalized_focus_path = repository_service._normalize_repository_relative_path(
            raw_focus_path
        )
        if not normalized_focus_path:
            continue
        for pattern in (
            f"/{normalized_focus_path}",
            f"/{normalized_focus_path}/**",
        ):
            if pattern in seen_patterns:
                continue
            seen_patterns.add(pattern)
            patterns.append(pattern)
    return patterns


def _materialize_public_repository_checkout(
    case: PublicRepositoryCase,
    *,
    git_executable: str,
    checkout_path: Path,
    repository_url: str,
) -> None:
    sparse_focus_paths = _public_repository_sparse_checkout_focus_paths(
        case,
        git_executable=git_executable,
        checkout_path=checkout_path,
        repository_url=repository_url,
    )
    materialization_commands: list[list[str]]
    materialization_stage = "checkout"
    if sparse_focus_paths:
        sparse_checkout_patterns = _public_repository_sparse_checkout_patterns(
            sparse_focus_paths
        )
        materialization_stage = "sparse_checkout"
        materialization_commands = [
            ["sparse-checkout", "init", "--no-cone"],
            ["sparse-checkout", "set", "--no-cone", *sparse_checkout_patterns],
            ["checkout", "--force", "HEAD"],
        ]
    else:
        materialization_commands = [["checkout", "--force", "HEAD"]]
    for git_args in materialization_commands:
        completed = _run_public_repository_checkout_command(
            git_executable=git_executable,
            checkout_path=checkout_path,
            git_args=git_args,
        )
        if completed.returncode == 0:
            continue
        _raise_public_repository_checkout_error(
            repository_url=repository_url,
            stage=materialization_stage,
            code="public_repo_checkout_materialization_failed",
            message=f"Failed to materialize checkout for {repository_url}.",
            details={
                "command": git_args,
                "returncode": completed.returncode,
                "stderr": completed.stderr.strip(),
            },
        )
    if _is_reusable_public_repository_checkout(checkout_path):
        if (checkout_path / ".git" / "HEAD").exists():
            _public_repository_head_revision(
                git_executable=git_executable,
                checkout_path=checkout_path,
                repository_url=repository_url,
            )
        if case.focus_paths and sparse_focus_paths:
            _store_public_repository_materialized_tracked_relative_files(
                checkout_path=checkout_path,
                focus_paths=sparse_focus_paths,
            )
        return
    _raise_public_repository_checkout_error(
        repository_url=repository_url,
        stage=materialization_stage,
        code="public_repo_checkout_incomplete",
        message=f"Checkout of {repository_url} did not produce a reusable worktree.",
        details={"focus_paths": sparse_focus_paths},
    )


def _is_reusable_public_repository_checkout(checkout_path: Path) -> bool:
    git_dir = checkout_path / ".git"
    if not checkout_path.is_dir() or not git_dir.is_dir():
        _PUBLIC_REPOSITORY_REUSABLE_CHECKOUT_CACHE.pop(
            _public_repository_reusable_checkout_cache_key(checkout_path),
            None,
        )
        return False
    if _cached_reusable_public_repository_checkout(checkout_path):
        return True
    if any(git_dir.rglob("*.lock")):
        return False
    # Reusable when the checkout has materialized working-tree files OR a valid git HEAD
    # (a freshly-cloned full checkout whose tracked files are warmed lazily via ls-tree has
    # only ``.git`` on disk). An in-progress clone is excluded by the ``*.lock`` guard above.
    has_working_tree_files = any(path.name != ".git" for path in checkout_path.iterdir())
    has_git_head = (git_dir / "HEAD").exists()
    if not has_working_tree_files and not has_git_head:
        return False
    return _store_reusable_public_repository_checkout(repo_path=checkout_path)


def _ecosystem_summary(
    *,
    detected_ecosystems: list[str],
    operational_ecosystems: list[str],
    language: str,
    expected_primary_ecosystem: str,
) -> dict[str, Any]:
    primary_detected_ecosystem = detected_ecosystems[0] if detected_ecosystems else None
    primary_operational_ecosystem = (
        operational_ecosystems[0] if operational_ecosystems else primary_detected_ecosystem
    )
    detected_primary_match = _ecosystem_matches_public_repository_case(
        primary_detected_ecosystem,
        language=language,
        expected_primary_ecosystem=expected_primary_ecosystem,
    )
    return {
        "detected_ecosystems": detected_ecosystems,
        "operational_ecosystems": operational_ecosystems,
        "primary_detected_ecosystem": primary_detected_ecosystem,
        "detected_primary_match": detected_primary_match,
        "primary_operational_ecosystem": primary_operational_ecosystem,
        "detection_correction_applied": not _ecosystems_match(
            primary_detected_ecosystem,
            primary_operational_ecosystem,
        ),
        "primary_ecosystem": primary_operational_ecosystem,
        "primary_match": _ecosystem_matches_public_repository_case(
            primary_operational_ecosystem,
            language=language,
            expected_primary_ecosystem=expected_primary_ecosystem,
        ),
    }


def _run_with_case_timeout(
    *,
    timeout_seconds: int | None,
    callback,
) -> Any:
    if timeout_seconds is None or timeout_seconds <= 0:
        return callback()
    if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
        return callback()

    def _timeout_handler(_signum: int, _frame: object) -> None:
        raise PublicRepositoryCaseTimeoutError(
            f"Public repository case exceeded timeout of {timeout_seconds} seconds."
        )

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, float(timeout_seconds))
    try:
        return callback()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer != (0.0, 0.0):
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def clone_public_repository_case(
    case: PublicRepositoryCase,
    *,
    checkout_root: Path,
    refresh: bool = False,
) -> Path:
    with _public_repository_checkout_context(
        case,
        checkout_root=checkout_root,
        refresh=refresh,
    ) as repo_path:
        return repo_path


def _run_public_repository_seed_plan_for_checkout(
    case: PublicRepositoryCase,
    *,
    repo_path: Path,
    max_files: int = 512,
    focus_paths: list[str] | None = None,
) -> dict[str, Any]:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    repo_path = _normalized_public_repository_repo_path(repo_path)
    normalized_focus_paths = list(
        _normalized_public_repository_focus_paths(
            list(case.focus_paths if focus_paths is None else focus_paths)
        )
    )
    cached_seed_plan_result = _cached_public_repository_seed_plan_result(
        case=case,
        repo_path=repo_path,
        focus_paths=normalized_focus_paths,
        max_files=max_files,
    )
    if cached_seed_plan_result is not None:
        return cached_seed_plan_result

    collection_support.begin_git_repo_relative_files_cache_scope()
    try:
        collection_support.set_git_repo_assume_clean_clone(repo_path, True)
        tracked_relative_paths = _cached_public_repository_tracked_relative_files(repo_path)
        if tracked_relative_paths:
            collection_support.seed_git_repo_relative_files_cache(
                repo_path,
                tracked_relative_paths,
                relative_paths_are_canonical=True,
            )
        seed_plan = probe_module._derive_operational_seed_plan_without_diagnostics(
            repo_path=repo_path,
            focus_paths=normalized_focus_paths,
            max_files=max_files,
        )
    finally:
        collection_support.end_git_repo_relative_files_cache_scope()
    detected_ecosystems = list(seed_plan["detected_ecosystems"])
    operational_ecosystems = list(
        seed_plan.get("operational_ecosystems") or detected_ecosystems
    )
    return _store_public_repository_seed_plan_result(
        case=case,
        repo_path=repo_path,
        focus_paths=normalized_focus_paths,
        max_files=max_files,
        result={
        "case": asdict(case),
        "case_key": _public_repository_case_key(case),
        "repo_path": str(repo_path),
        **_ecosystem_summary(
            detected_ecosystems=detected_ecosystems,
            operational_ecosystems=operational_ecosystems,
            language=case.language,
            expected_primary_ecosystem=case.expected_primary_ecosystem,
        ),
        "entrypoint_files": list(seed_plan["entrypoint_files"]),
        "support_roots": list(seed_plan["support_roots"]),
        "config_paths": list(seed_plan["config_paths"]),
        "candidate_file_paths": list(seed_plan["candidate_file_paths"]),
        "candidate_file_count": len(seed_plan["candidate_file_paths"]),
        },
    )


@lru_cache(maxsize=262_144)
def _compacted_public_repository_focus_path(relative_path: str) -> str:
    normalized_path = str(relative_path or "").strip().replace("\\", "/").strip("/")
    if not normalized_path:
        return ""
    parent_path = PurePosixPath(normalized_path).parent
    if str(parent_path) in {"", "."}:
        return normalized_path
    parent_path_str = str(parent_path)
    parent_parts = list(parent_path.parts)
    for index in range(len(parent_parts) - 1, -1, -1):
        signature_part, part_version_tokens = _versionish_signature_and_priority(parent_parts[index])
        if part_version_tokens is None:
            continue
        collapsed_parts = parent_parts[:index]
        if signature_part:
            collapsed_parts.append(signature_part)
        if collapsed_parts:
            collapsed_path = "/".join(collapsed_parts)
            if parent_path_str == collapsed_path or parent_path_str.startswith(collapsed_path):
                return collapsed_path
            return parent_path_str
        break
    return parent_path_str


def _public_repository_tracked_directory_roots(
    relative_paths: list[str],
    *,
    limit: int = _PUBLIC_REPOSITORY_PREPASS_FOCUS_LIMIT,
) -> list[str]:
    """Top-level code directory roots of ``relative_paths`` in their given order.

    Root-level files (no directory component) are excluded — a full-checkout warm prepass
    targets the directories that hold code, not loose root files. Order is preserved so the
    caller (which passes the git ``ls-tree`` listing) keeps repository order.
    """
    directory_roots: list[str] = []
    seen_directory_roots: set[str] = set()
    for relative_path in relative_paths:
        normalized_path = str(relative_path or "").strip().replace("\\", "/").strip("/")
        if "/" not in normalized_path:
            continue
        compacted_focus_path = _compacted_public_repository_focus_path(normalized_path)
        if not compacted_focus_path or compacted_focus_path in seen_directory_roots:
            continue
        seen_directory_roots.add(compacted_focus_path)
        directory_roots.append(compacted_focus_path)
        if len(directory_roots) >= limit:
            break
    return directory_roots


def _expected_ecosystem_focus_paths_from_relative_files(
    *,
    relative_paths: list[str],
    repo_path: Path,
    expected_primary_ecosystem: str,
    limit: int = _PUBLIC_REPOSITORY_PREPASS_FOCUS_LIMIT,
) -> list[str]:
    canonical_expected_ecosystem = _canonical_ecosystem_name(expected_primary_ecosystem)
    if canonical_expected_ecosystem is None:
        return []
    matching_path_budget = max(limit * 16, limit)
    matching_path_rank_buffer = max(limit * 3, limit)
    matching_paths: list[str] = []
    deferred_paths: list[str] = []
    seen_matching_paths: set[str] = set()
    compacted_hint_focus_paths: set[str] = set()

    def _ranked_focus_paths(candidate_paths: list[str]) -> list[str]:
        ranked_matching_paths = sorted(
            candidate_paths,
            key=lambda path: probe_module._probe_collection_rank(
                path,
                repo_path=repo_path,
            ),
        )
        focus_paths: list[str] = []
        seen_focus_paths: set[str] = set()
        for candidate_path in ranked_matching_paths:
            compacted_focus_path = _compacted_public_repository_focus_path(candidate_path)
            if not compacted_focus_path or compacted_focus_path in seen_focus_paths:
                continue
            seen_focus_paths.add(compacted_focus_path)
            focus_paths.append(compacted_focus_path)
            if len(focus_paths) >= limit:
                break
        return focus_paths

    for relative_path in relative_paths:
        normalized_path = str(relative_path or "").strip().replace("\\", "/").strip("/")
        if not normalized_path or normalized_path in seen_matching_paths:
            continue
        if _path_matches_expected_ecosystem_hint(
            normalized_path,
            expected_primary_ecosystem=canonical_expected_ecosystem,
        ):
            seen_matching_paths.add(normalized_path)
            matching_paths.append(normalized_path)
            compacted_focus_path = _compacted_public_repository_focus_path(normalized_path)
            if compacted_focus_path:
                compacted_hint_focus_paths.add(compacted_focus_path)
            if len(matching_paths) >= matching_path_budget:
                break
            if (
                len(compacted_hint_focus_paths) >= limit
                and len(matching_paths) >= matching_path_rank_buffer
            ):
                break
            continue
        deferred_paths.append(normalized_path)
    hinted_focus_paths = _ranked_focus_paths(matching_paths)
    if len(hinted_focus_paths) >= limit:
        return hinted_focus_paths
    if len(matching_paths) < matching_path_budget:
        for normalized_path in deferred_paths:
            if canonical_expected_ecosystem not in _path_candidate_ecosystems(
                normalized_path,
                repo_path=repo_path,
            ):
                continue
            seen_matching_paths.add(normalized_path)
            matching_paths.append(normalized_path)
            if len(matching_paths) >= matching_path_budget:
                break
    return _ranked_focus_paths(matching_paths)


def _expected_ecosystem_prepass_focus_paths(
    *,
    repo_path: Path,
    expected_primary_ecosystem: str,
    limit: int = _PUBLIC_REPOSITORY_PREPASS_FOCUS_LIMIT,
) -> list[str]:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    cached_focus_paths = _cached_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem=expected_primary_ecosystem,
    )
    if cached_focus_paths:
        return cached_focus_paths[:limit]
    matching_path_rank_buffer = max(limit * 3, limit)
    tracked_relative_paths = _cached_public_repository_tracked_relative_files(repo_path)

    def _rank_focus_paths(relative_paths: list[str]) -> list[str]:
        return _expected_ecosystem_focus_paths_from_relative_files(
            relative_paths=relative_paths,
            repo_path=repo_path,
            expected_primary_ecosystem=expected_primary_ecosystem,
            limit=limit,
        )

    def _hinted_focus_paths_include_directory_roots(
        focus_paths: list[str],
        relative_paths: list[str],
    ) -> bool:
        normalized_focus_paths = _normalized_public_repository_focus_paths(focus_paths)
        for focus_path in normalized_focus_paths:
            focus_prefix = f"{focus_path}/"
            if any(relative_path.startswith(focus_prefix) for relative_path in relative_paths):
                return True
        return False

    if tracked_relative_paths is not None:
        hinted_tracked_relative_paths = [
            relative_path
            for relative_path in tracked_relative_paths
            if _path_matches_expected_ecosystem_hint(
                relative_path,
                expected_primary_ecosystem=expected_primary_ecosystem,
            )
        ]
        # The cached tracked listing is matched against the expected ecosystem by a coarse
        # suffix hint. When that hinted slice is small it is a confident, complete picture and
        # we short-circuit on it. When it is large (>= the rank buffer) the suffix hint is too
        # coarse to trust, so we defer to the precise ``ls-files`` pathspec query below rather
        # than ranking the (possibly over-broad) cached slice.
        if (
            hinted_tracked_relative_paths
            and len(hinted_tracked_relative_paths) < matching_path_rank_buffer
        ):
            hinted_focus_paths = _rank_focus_paths(hinted_tracked_relative_paths)
            if hinted_focus_paths and (
                len(hinted_focus_paths) >= limit
                or _hinted_focus_paths_include_directory_roots(
                    hinted_focus_paths,
                    hinted_tracked_relative_paths,
                )
            ):
                return _store_public_repository_prepass_focus_paths(
                    repo_path=repo_path,
                    expected_primary_ecosystem=expected_primary_ecosystem,
                    focus_paths=hinted_focus_paths,
                )

    hint_pathspecs = _expected_ecosystem_hint_pathspecs(expected_primary_ecosystem)
    if hint_pathspecs:
        try:
            hinted_output = str(
                repository_service._git_command(
                    [
                        "git",
                        "-C",
                        str(repo_path),
                        "ls-files",
                        "--",
                        *hint_pathspecs,
                    ],
                    timeout=120.0,
                )
            )
        except RepositoryIntelligenceError:
            hinted_relative_paths: list[str] = []
        else:
            hinted_relative_paths = collection_support._normalize_git_listing_lines(
                hinted_output.splitlines(),
                normalize_path=repository_service._normalize_repository_relative_path,
            )
        if hinted_relative_paths:
            hinted_focus_paths = _rank_focus_paths(hinted_relative_paths)
            if hinted_focus_paths and (
                len(hinted_focus_paths) >= limit
                or len(hinted_relative_paths) >= matching_path_rank_buffer
            ):
                return _store_public_repository_prepass_focus_paths(
                    repo_path=repo_path,
                    expected_primary_ecosystem=expected_primary_ecosystem,
                    focus_paths=hinted_focus_paths,
                )

    if tracked_relative_paths is not None:
        return _store_public_repository_prepass_focus_paths(
            repo_path=repo_path,
            expected_primary_ecosystem=expected_primary_ecosystem,
            focus_paths=_rank_focus_paths(tracked_relative_paths),
        )

    relative_paths = probe_module._git_repo_relative_files(repo_path)
    if not relative_paths:
        return []
    return _store_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem=expected_primary_ecosystem,
        focus_paths=_rank_focus_paths(relative_paths),
    )


def _versionish_path_priority(path: str) -> tuple[tuple[int | str, ...], ...]:
    normalized_path = str(path or "").strip().replace("\\", "/").strip("/")
    version_tokens: list[tuple[int | str, ...]] = []
    for part in PurePosixPath(normalized_path).parts:
        _signature_part, part_version_tokens = _versionish_signature_and_priority(part)
        if part_version_tokens is None:
            continue
        version_tokens.append(part_version_tokens)
    return tuple(version_tokens)


def _collapse_versioned_focus_paths(focus_paths: list[str]) -> list[str]:
    ordered_focus_paths = [
        normalized_path
        for focus_path in focus_paths
        if (
            normalized_path := str(focus_path or "").strip().replace("\\", "/").strip("/")
        )
    ]
    if not ordered_focus_paths:
        return []

    winners_by_signature: dict[str, tuple[tuple[tuple[int | str, ...], ...], int, str]] = {}
    passthrough_paths: list[tuple[int, str]] = []
    for index, path in enumerate(ordered_focus_paths):
        parts = PurePosixPath(path).parts
        versionless_parts: list[str] = []
        has_versionish_part = False
        for part in parts:
            signature_part, part_version_tokens = _versionish_signature_and_priority(part)
            if part_version_tokens is None:
                versionless_parts.append(part)
                continue
            has_versionish_part = True
            if signature_part:
                versionless_parts.append(signature_part)
        if not has_versionish_part:
            passthrough_paths.append((index, path))
            continue
        signature = "/".join(versionless_parts)
        version_priority = _versionish_path_priority(path)
        existing = winners_by_signature.get(signature)
        if (
            existing is None
            or version_priority > existing[0]
            or (version_priority == existing[0] and index < existing[1])
        ):
            winners_by_signature[signature] = (version_priority, index, path)

    collapsed_paths: list[tuple[int, str]] = list(passthrough_paths)
    collapsed_paths.extend((index, path) for _priority, index, path in winners_by_signature.values())
    collapsed_paths.sort(key=lambda item: item[0])
    return [path for _index, path in collapsed_paths]


def _derived_probe_focus_paths_from_seed_plan(
    *,
    seed_plan_result: dict[str, Any],
    repo_path: Path,
    expected_primary_ecosystem: str,
) -> list[str]:
    has_primary_ecosystem_root_entrypoint = False
    primary_ecosystem_entrypoint_parents: list[str] = []
    primary_ecosystem_seen: set[str] = set()
    primary_ecosystem_support_roots: list[str] = []
    primary_ecosystem_support_root_seen: set[str] = set()
    candidate_focus_paths: list[str] = []
    seen_paths: set[str] = set()

    def _append_focus_path(raw_path: str) -> None:
        normalized_path = str(raw_path or "").strip().replace("\\", "/").strip("/")
        if not normalized_path or normalized_path == "." or normalized_path in seen_paths:
            return
        seen_paths.add(normalized_path)
        candidate_focus_paths.append(normalized_path)

    def _append_primary_entrypoint_parent(raw_path: str) -> None:
        normalized_path = str(raw_path or "").strip().replace("\\", "/").strip("/")
        if (
            not normalized_path
            or normalized_path == "."
            or normalized_path in primary_ecosystem_seen
        ):
            return
        primary_ecosystem_seen.add(normalized_path)
        primary_ecosystem_entrypoint_parents.append(normalized_path)

    def _append_primary_support_root(raw_path: str) -> None:
        normalized_path = str(raw_path or "").strip().replace("\\", "/").strip("/")
        if (
            not normalized_path
            or normalized_path == "."
            or normalized_path in primary_ecosystem_support_root_seen
        ):
            return
        primary_ecosystem_support_root_seen.add(normalized_path)
        primary_ecosystem_support_roots.append(normalized_path)

    for entrypoint_file in seed_plan_result.get("entrypoint_files", []):
        normalized_entrypoint = str(entrypoint_file or "").strip().replace("\\", "/")
        if not normalized_entrypoint:
            continue
        if not _path_supports_expected_ecosystem(
            normalized_entrypoint,
            repo_path=repo_path,
            expected_primary_ecosystem=expected_primary_ecosystem,
        ):
            continue
        parent_path = str(PurePosixPath(normalized_entrypoint).parent)
        if str(parent_path).strip().replace("\\", "/").strip("/") in {"", "."}:
            has_primary_ecosystem_root_entrypoint = True
        _append_primary_entrypoint_parent(parent_path)

    normalized_support_roots = [
        normalized_path
        for support_root in seed_plan_result.get("support_roots", [])
        if (
            normalized_path := str(support_root or "").strip().replace("\\", "/").strip("/")
        )
    ]
    for support_root in normalized_support_roots:
        if any(
            probe_module._matches_focus_paths(candidate_path, [support_root])
            and _path_supports_expected_ecosystem(
                candidate_path,
                repo_path=repo_path,
                expected_primary_ecosystem=expected_primary_ecosystem,
            )
            for candidate_path in seed_plan_result.get("candidate_file_paths", [])
        ):
            _append_primary_support_root(support_root)
    if has_primary_ecosystem_root_entrypoint:
        return []
    if primary_ecosystem_entrypoint_parents:
        combined_primary_focus_paths = list(primary_ecosystem_entrypoint_parents)
        for support_root in primary_ecosystem_support_roots:
            if support_root in primary_ecosystem_seen:
                continue
            primary_ecosystem_seen.add(support_root)
            combined_primary_focus_paths.append(support_root)
        return _collapse_versioned_focus_paths(combined_primary_focus_paths)[:12]
    if primary_ecosystem_support_roots:
        return _collapse_versioned_focus_paths(primary_ecosystem_support_roots)[:12]

    for support_root in seed_plan_result.get("support_roots", []):
        _append_focus_path(str(support_root))
    for entrypoint_file in seed_plan_result.get("entrypoint_files", []):
        parent_path = str(PurePosixPath(str(entrypoint_file)).parent)
        _append_focus_path(parent_path)
    for config_path in seed_plan_result.get("config_paths", []):
        parent_path = str(PurePosixPath(str(config_path)).parent)
        _append_focus_path(parent_path)
    return _collapse_versioned_focus_paths(candidate_focus_paths)[:12]


def _uncached_heuristic_prepass_probe_focus_is_sufficient(
    *,
    seed_focus_paths: list[str],
    probe_focus_paths: list[str],
) -> bool:
    normalized_seed_focus_paths = _normalized_public_repository_focus_paths(seed_focus_paths)
    normalized_probe_focus_paths = _normalized_public_repository_focus_paths(probe_focus_paths)
    if not normalized_probe_focus_paths:
        return False
    sufficient_focus_path_count = min(
        _PUBLIC_REPOSITORY_PREPASS_FOCUS_LIMIT,
        max(4, len(normalized_seed_focus_paths) + 2),
    )
    return len(normalized_probe_focus_paths) >= sufficient_focus_path_count


def _focused_seed_plan_result(
    *,
    seed_plan_result: dict[str, Any],
    repo_path: Path,
    focus_paths: list[str],
    language: str | None = None,
    expected_primary_ecosystem: str,
) -> dict[str, Any] | None:
    normalized_focus_paths = [
        normalized_path
        for focus_path in focus_paths
        if (
            normalized_path := str(focus_path or "").strip().replace("\\", "/").strip("/")
        )
    ]
    if not normalized_focus_paths:
        return None

    normalized_path_cache: dict[str, str] = {}
    within_focus_cache: dict[str, bool] = {}
    operational_candidate_cache: dict[str, bool] = {}
    expected_ecosystem_support_cache: dict[str, bool] = {}
    primary_ecosystem_cache: dict[str, str | None] = {}

    def _normalized_path(path: str) -> str:
        cached_path = normalized_path_cache.get(path)
        if cached_path is not None:
            return cached_path
        normalized = str(path or "").strip().replace("\\", "/").strip("/")
        normalized_path_cache[path] = normalized
        return normalized

    def _within_focus(path: str) -> bool:
        normalized = _normalized_path(path)
        if not normalized:
            return False
        cached_match = within_focus_cache.get(normalized)
        if cached_match is not None:
            return cached_match
        match = probe_module._matches_focus_paths(normalized, normalized_focus_paths)
        within_focus_cache[normalized] = match
        return match

    def _is_operational_candidate(path: str) -> bool:
        normalized = _normalized_path(path)
        if not normalized:
            return False
        cached_result = operational_candidate_cache.get(normalized)
        if cached_result is not None:
            return cached_result
        result = (
            probe_module._is_repo_profile_code_candidate(
                normalized,
                repo_path=repo_path,
            )
            or probe_module._is_operational_profile_entrypoint_candidate(
                normalized,
                repo_path=repo_path,
            )
        )
        operational_candidate_cache[normalized] = result
        return result

    def _path_supports_expected_ecosystem_cached(path: str) -> bool:
        normalized = _normalized_path(path)
        if not normalized:
            return False
        cached_result = expected_ecosystem_support_cache.get(normalized)
        if cached_result is not None:
            return cached_result
        result = _path_supports_expected_ecosystem(
            normalized,
            repo_path=repo_path,
            expected_primary_ecosystem=expected_primary_ecosystem,
        )
        expected_ecosystem_support_cache[normalized] = result
        return result

    def _path_primary_ecosystem_cached(path: str) -> str | None:
        normalized = _normalized_path(path)
        if not normalized:
            return None
        if normalized in primary_ecosystem_cache:
            return primary_ecosystem_cache[normalized]
        ecosystem = _path_primary_ecosystem(
            normalized,
            repo_path=repo_path,
            expected_primary_ecosystem=expected_primary_ecosystem,
        )
        primary_ecosystem_cache[normalized] = ecosystem
        return ecosystem

    def _primary_ecosystem_for_paths(paths: list[str]) -> str | None:
        ecosystem_scores: Counter[str] = Counter()
        for path in paths:
            ecosystem = _path_primary_ecosystem_cached(str(path))
            if ecosystem:
                ecosystem_scores[ecosystem] += 1
        if not ecosystem_scores:
            return None
        ordered_ecosystems = sort_repository_languages_by_score(
            ecosystem_scores.keys(),
            scores=ecosystem_scores,
        )
        ordered_ecosystems = _prefer_expected_primary_ecosystem_on_tied_top_score(
            ordered_ecosystems,
            ecosystem_scores=ecosystem_scores,
            expected_primary_ecosystem=expected_primary_ecosystem,
        )
        return ordered_ecosystems[0] if ordered_ecosystems else None

    def _support_roots_from_paths(paths: list[str]) -> list[str]:
        support_roots: list[str] = []
        seen_support_roots: set[str] = set()
        for path in paths:
            normalized_path = _normalized_path(path)
            if not normalized_path:
                continue
            parent_path = str(PurePosixPath(normalized_path).parent).strip().replace("\\", "/")
            normalized_parent_path = parent_path.strip("/")
            if (
                not normalized_parent_path
                or normalized_parent_path == "."
                or normalized_parent_path in seen_support_roots
            ):
                continue
            seen_support_roots.add(normalized_parent_path)
            support_roots.append(normalized_parent_path)
        return support_roots

    raw_filtered_candidate_file_paths = [
        path
        for path in seed_plan_result.get("candidate_file_paths", [])
        if _within_focus(str(path))
    ]
    filtered_candidate_file_paths = list(raw_filtered_candidate_file_paths)
    operational_candidate_file_paths = [
        path for path in filtered_candidate_file_paths if _is_operational_candidate(str(path))
    ]
    if operational_candidate_file_paths:
        filtered_candidate_file_paths = operational_candidate_file_paths
    filtered_entrypoint_files = [
        path for path in seed_plan_result.get("entrypoint_files", []) if _within_focus(str(path))
    ]
    operational_entrypoint_files = [
        path for path in filtered_entrypoint_files if _is_operational_candidate(str(path))
    ]
    if operational_entrypoint_files:
        filtered_entrypoint_files = operational_entrypoint_files
    original_filtered_entrypoint_files = list(filtered_entrypoint_files)
    raw_expected_ecosystem_candidate_file_paths = [
        path
        for path in raw_filtered_candidate_file_paths
        if _path_supports_expected_ecosystem_cached(str(path))
    ]
    if not raw_expected_ecosystem_candidate_file_paths:
        focused_inventory_paths = _focused_public_repository_inventory_paths_from_cache(
            repo_path=repo_path,
            focus_paths=list(normalized_focus_paths),
        )
        if focused_inventory_paths is None:
            focused_inventory_paths = probe_module._git_repo_relative_files_for_focus_paths(
                repo_path,
                focus_paths=list(normalized_focus_paths),
            )
            if focused_inventory_paths is None:
                focused_inventory_paths = [
                    path
                    for path in (probe_module._git_repo_relative_files(repo_path) or [])
                    if _within_focus(str(path))
                ]
        derived_expected_ecosystem_candidate_file_paths = [
            path
            for path in focused_inventory_paths
            if _path_matches_expected_ecosystem_hint(
                str(path),
                expected_primary_ecosystem=expected_primary_ecosystem,
            )
        ]
        if not derived_expected_ecosystem_candidate_file_paths:
            derived_expected_ecosystem_candidate_file_paths = [
                path
                for path in focused_inventory_paths
                if _path_supports_expected_ecosystem_cached(str(path))
            ]
        operational_derived_expected_ecosystem_candidate_file_paths = [
            path
            for path in derived_expected_ecosystem_candidate_file_paths
            if _is_operational_candidate(str(path))
        ]
        if operational_derived_expected_ecosystem_candidate_file_paths:
            derived_expected_ecosystem_candidate_file_paths = (
                operational_derived_expected_ecosystem_candidate_file_paths
            )
        raw_expected_ecosystem_candidate_file_paths = (
            derived_expected_ecosystem_candidate_file_paths[:64]
        )
    expected_ecosystem_candidate_file_paths = [
        path
        for path in filtered_candidate_file_paths
        if _path_supports_expected_ecosystem_cached(str(path))
    ]
    if not expected_ecosystem_candidate_file_paths:
        expected_ecosystem_candidate_file_paths = list(raw_expected_ecosystem_candidate_file_paths)
    expected_ecosystem_entrypoint_files = [
        path
        for path in filtered_entrypoint_files
        if _path_supports_expected_ecosystem_cached(str(path))
    ]
    preferred_support_roots: list[str] = []
    entrypoint_primary_ecosystem = _primary_ecosystem_for_paths(filtered_entrypoint_files)
    if expected_ecosystem_candidate_file_paths and not _ecosystem_matches_public_repository_case(
        entrypoint_primary_ecosystem,
        language=language,
        expected_primary_ecosystem=expected_primary_ecosystem,
    ):
        filtered_entrypoint_files = expected_ecosystem_candidate_file_paths[:12]
        filtered_candidate_file_paths = list(expected_ecosystem_candidate_file_paths)
        preferred_support_roots = _support_roots_from_paths(filtered_entrypoint_files)
    elif not filtered_entrypoint_files:
        filtered_entrypoint_files = expected_ecosystem_candidate_file_paths[:12]
        filtered_candidate_file_paths = list(expected_ecosystem_candidate_file_paths)
        preferred_support_roots = _support_roots_from_paths(filtered_entrypoint_files)
        if not filtered_entrypoint_files:
            return None
    elif expected_ecosystem_entrypoint_files and len(expected_ecosystem_entrypoint_files) < len(
        original_filtered_entrypoint_files
    ) and _ecosystem_matches_public_repository_case(
        entrypoint_primary_ecosystem,
        language=language,
        expected_primary_ecosystem=expected_primary_ecosystem,
    ) and (
        len(expected_ecosystem_candidate_file_paths) * 2 > len(filtered_candidate_file_paths)
    ):
        filtered_entrypoint_files = expected_ecosystem_entrypoint_files
        filtered_candidate_file_paths = list(expected_ecosystem_candidate_file_paths)
        preferred_support_roots = _support_roots_from_paths(filtered_entrypoint_files)
    filtered_support_roots = [
        path for path in seed_plan_result.get("support_roots", []) if _within_focus(str(path))
    ]
    if preferred_support_roots:
        filtered_support_roots = preferred_support_roots
    filtered_config_paths = [
        path for path in seed_plan_result.get("config_paths", []) if _within_focus(str(path))
    ]

    ecosystem_scores: Counter[str] = Counter()
    for entrypoint_file in filtered_entrypoint_files:
        ecosystem = _path_primary_ecosystem_cached(str(entrypoint_file))
        if ecosystem:
            ecosystem_scores[ecosystem] += 1
    if not ecosystem_scores:
        return None

    ordered_ecosystems = sort_repository_languages_by_score(
        ecosystem_scores.keys(),
        scores=ecosystem_scores,
    )
    ordered_ecosystems = _prefer_expected_primary_ecosystem_on_tied_top_score(
        ordered_ecosystems,
        ecosystem_scores=ecosystem_scores,
        expected_primary_ecosystem=expected_primary_ecosystem,
    )
    primary_ecosystem = ordered_ecosystems[0] if ordered_ecosystems else None
    return {
        **seed_plan_result,
        "entrypoint_files": filtered_entrypoint_files,
        "support_roots": filtered_support_roots or list(normalized_focus_paths),
        "config_paths": filtered_config_paths,
        "candidate_file_paths": filtered_candidate_file_paths or filtered_entrypoint_files,
        "candidate_file_count": len(filtered_candidate_file_paths or filtered_entrypoint_files),
        "detected_ecosystems": ordered_ecosystems,
        "operational_ecosystems": ordered_ecosystems,
        "primary_detected_ecosystem": primary_ecosystem,
        "detected_primary_match": _ecosystem_matches_public_repository_case(
            primary_ecosystem,
            language=language,
            expected_primary_ecosystem=expected_primary_ecosystem,
        ),
        "primary_operational_ecosystem": primary_ecosystem,
        "detection_correction_applied": False,
        "primary_ecosystem": primary_ecosystem,
        "primary_match": _ecosystem_matches_public_repository_case(
            primary_ecosystem,
            language=language,
            expected_primary_ecosystem=expected_primary_ecosystem,
        ),
    }


def _refine_seed_plan_result_for_unscoped_case(
    case: PublicRepositoryCase,
    *,
    repo_path: Path,
    max_files: int,
) -> tuple[dict[str, Any], list[str]]:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    repo_path = _normalized_public_repository_repo_path(repo_path)
    cached_refined_plan = _cached_public_repository_refined_unscoped_probe_plan(
        case=case,
        repo_path=repo_path,
        max_files=max_files,
    )
    if cached_refined_plan is not None:
        return cached_refined_plan
    collection_support.begin_git_repo_relative_files_cache_scope()
    try:
        cached_seed_plan_focus_paths = _cached_public_repository_prepass_focus_paths(
            repo_path=repo_path,
            expected_primary_ecosystem=case.expected_primary_ecosystem,
        )
        seed_plan_focus_paths = (
            list(cached_seed_plan_focus_paths)
            if cached_seed_plan_focus_paths is not None
            else _expected_ecosystem_prepass_focus_paths(
                repo_path=repo_path,
                expected_primary_ecosystem=case.expected_primary_ecosystem,
            )
        )

        def _bootstrapped_seed_plan_from_unscoped_seed(
            *,
            initial_seed_plan_result: dict[str, Any] | None = None,
        ) -> tuple[dict[str, Any] | None, list[str]]:
            bootstrap_seed_plan_result = initial_seed_plan_result
            if bootstrap_seed_plan_result is None:
                bootstrap_seed_plan_result = _run_public_repository_seed_plan_for_checkout(
                    case,
                    repo_path=repo_path,
                    max_files=_public_repository_probe_focus_prepass_max_files(max_files),
                    focus_paths=[],
                )
            bootstrap_probe_focus_paths = _derived_probe_focus_paths_from_seed_plan(
                seed_plan_result=bootstrap_seed_plan_result,
                repo_path=repo_path,
                expected_primary_ecosystem=case.expected_primary_ecosystem,
            )
            if not bootstrap_probe_focus_paths:
                return bootstrap_seed_plan_result, []
            refined_bootstrap_seed_plan_result = _run_public_repository_seed_plan_for_checkout(
                case,
                repo_path=repo_path,
                max_files=_public_repository_probe_focus_prepass_max_files(max_files),
                focus_paths=bootstrap_probe_focus_paths,
            )
            if refined_bootstrap_seed_plan_result["entrypoint_files"]:
                bootstrap_seed_plan_result = refined_bootstrap_seed_plan_result
                refined_bootstrap_probe_focus_paths = _derived_probe_focus_paths_from_seed_plan(
                    seed_plan_result=bootstrap_seed_plan_result,
                    repo_path=repo_path,
                    expected_primary_ecosystem=case.expected_primary_ecosystem,
                )
                if refined_bootstrap_probe_focus_paths:
                    bootstrap_probe_focus_paths = refined_bootstrap_probe_focus_paths
            _store_public_repository_prepass_focus_paths(
                repo_path=repo_path,
                expected_primary_ecosystem=case.expected_primary_ecosystem,
                focus_paths=bootstrap_probe_focus_paths,
            )
            return bootstrap_seed_plan_result, bootstrap_probe_focus_paths

        seed_plan_result = _run_public_repository_seed_plan_for_checkout(
            case,
            repo_path=repo_path,
            max_files=_public_repository_probe_focus_prepass_max_files(max_files),
            focus_paths=seed_plan_focus_paths,
        )
        probe_focus_paths = _derived_probe_focus_paths_from_seed_plan(
            seed_plan_result=seed_plan_result,
            repo_path=repo_path,
            expected_primary_ecosystem=case.expected_primary_ecosystem,
        )
        focused_seed_plan_result = None
        if not probe_focus_paths:
            probe_focus_paths = list(seed_plan_focus_paths)
        elif not seed_plan_focus_paths:
            bootstrap_seed_plan_result, bootstrap_probe_focus_paths = (
                _bootstrapped_seed_plan_from_unscoped_seed(
                    initial_seed_plan_result=seed_plan_result,
                )
            )
            if (
                bootstrap_seed_plan_result is not None
                and bootstrap_seed_plan_result["entrypoint_files"]
            ):
                seed_plan_result = bootstrap_seed_plan_result
                if bootstrap_probe_focus_paths:
                    probe_focus_paths = bootstrap_probe_focus_paths
        elif (
            cached_seed_plan_focus_paths is None
            and seed_plan_result["primary_match"]
            and seed_plan_result["entrypoint_files"]
        ):
            focused_seed_plan_result = _focused_seed_plan_result(
                seed_plan_result=seed_plan_result,
                repo_path=repo_path,
                focus_paths=probe_focus_paths,
                language=case.language,
                expected_primary_ecosystem=case.expected_primary_ecosystem,
            )
            if _uncached_heuristic_prepass_probe_focus_is_sufficient(
                seed_focus_paths=seed_plan_focus_paths,
                probe_focus_paths=probe_focus_paths,
            ) or (
                focused_seed_plan_result is not None
                and focused_seed_plan_result["primary_match"]
                and focused_seed_plan_result["entrypoint_files"]
            ):
                _store_public_repository_prepass_focus_paths(
                    repo_path=repo_path,
                    expected_primary_ecosystem=case.expected_primary_ecosystem,
                    focus_paths=probe_focus_paths,
                )
            else:
                bootstrap_seed_plan_result, bootstrap_probe_focus_paths = (
                    _bootstrapped_seed_plan_from_unscoped_seed()
                )
                if (
                    bootstrap_seed_plan_result is not None
                    and bootstrap_seed_plan_result["entrypoint_files"]
                ):
                    seed_plan_result = bootstrap_seed_plan_result
                    if bootstrap_probe_focus_paths:
                        probe_focus_paths = bootstrap_probe_focus_paths
        if focused_seed_plan_result is None:
            focused_seed_plan_result = _focused_seed_plan_result(
                seed_plan_result=seed_plan_result,
                repo_path=repo_path,
                focus_paths=probe_focus_paths,
                language=case.language,
                expected_primary_ecosystem=case.expected_primary_ecosystem,
            )
        if focused_seed_plan_result is not None and focused_seed_plan_result["primary_match"]:
            seed_plan_result = focused_seed_plan_result
            refined_probe_focus_paths = _derived_probe_focus_paths_from_seed_plan(
                repo_path=repo_path,
                seed_plan_result=seed_plan_result,
                expected_primary_ecosystem=case.expected_primary_ecosystem,
            )
            if refined_probe_focus_paths:
                probe_focus_paths = refined_probe_focus_paths
            return _store_public_repository_refined_unscoped_probe_plan(
                case=case,
                repo_path=repo_path,
                max_files=max_files,
                seed_plan_result=seed_plan_result,
                probe_focus_paths=probe_focus_paths,
            )

        if probe_focus_paths != seed_plan_focus_paths and (
            focused_seed_plan_result is None or not seed_plan_result["primary_match"]
        ):
            refined_seed_plan_result = _run_public_repository_seed_plan_for_checkout(
                case,
                repo_path=repo_path,
                max_files=_public_repository_probe_focus_prepass_max_files(max_files),
                focus_paths=probe_focus_paths,
            )
            if refined_seed_plan_result["entrypoint_files"]:
                seed_plan_result = refined_seed_plan_result
            focused_seed_plan_result = _focused_seed_plan_result(
                seed_plan_result=seed_plan_result,
                repo_path=repo_path,
                focus_paths=probe_focus_paths,
                language=case.language,
                expected_primary_ecosystem=case.expected_primary_ecosystem,
            )
        if focused_seed_plan_result is not None and (
            focused_seed_plan_result["primary_match"] or not seed_plan_result["primary_match"]
        ):
            seed_plan_result = focused_seed_plan_result
            refined_probe_focus_paths = _derived_probe_focus_paths_from_seed_plan(
                repo_path=repo_path,
                seed_plan_result=seed_plan_result,
                expected_primary_ecosystem=case.expected_primary_ecosystem,
            )
            if refined_probe_focus_paths:
                probe_focus_paths = refined_probe_focus_paths
        return _store_public_repository_refined_unscoped_probe_plan(
            case=case,
            repo_path=repo_path,
            max_files=max_files,
            seed_plan_result=seed_plan_result,
            probe_focus_paths=probe_focus_paths,
        )
    finally:
        collection_support.end_git_repo_relative_files_cache_scope()


def _run_seed_plan_case_for_checkout(
    case: PublicRepositoryCase,
    *,
    repo_path: Path,
    max_files: int = 512,
) -> dict[str, Any]:
    if case.focus_paths:
        seed_plan_result = _run_public_repository_seed_plan_for_checkout(
            case,
            repo_path=repo_path,
            max_files=max_files,
        )
        focused_seed_plan_result = _focused_seed_plan_result(
            seed_plan_result=seed_plan_result,
            repo_path=repo_path,
            focus_paths=list(case.focus_paths),
            language=case.language,
            expected_primary_ecosystem=case.expected_primary_ecosystem,
        )
        return focused_seed_plan_result or seed_plan_result
    seed_plan_result, _focus_paths = _refine_seed_plan_result_for_unscoped_case(
        case,
        repo_path=repo_path,
        max_files=max_files,
    )
    return seed_plan_result


def _public_repository_operational_seed_plan(
    seed_plan_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "entrypoint_files": list(seed_plan_result["entrypoint_files"]),
        "support_roots": list(seed_plan_result["support_roots"]),
        "config_paths": list(seed_plan_result["config_paths"]),
        "candidate_file_paths": list(seed_plan_result.get("candidate_file_paths") or []),
        "detected_ecosystems": list(seed_plan_result.get("detected_ecosystems") or []),
        "operational_ecosystems": list(
            seed_plan_result.get("operational_ecosystems")
            or seed_plan_result.get("detected_ecosystems")
            or []
        ),
    }


def _run_public_repository_probe_from_seed_plan(
    case: PublicRepositoryCase,
    *,
    repo_path: Path,
    runtime_root: Path,
    probe_focus_paths: list[str],
    operational_seed_plan: dict[str, Any],
    max_files: int,
    max_file_size_bytes: int,
    max_total_bytes: int,
    connected_file_count_mode: Literal["seed_files", "snapshot"] = "seed_files",
) -> dict[str, Any]:
    from benchmarks import repository_intelligence_real_repo_probe_runtime_support as runtime_support

    runtime_dir = runtime_root / _case_checkout_name(case)
    seed_files = list(operational_seed_plan["entrypoint_files"])
    config_focus_paths = _cached_public_repository_candidate_config_focus_paths(
        repo_path=repo_path,
        focus_paths=probe_focus_paths,
        diagnostic_base_path=repo_path,
        diagnostic_project_path=None,
    )
    if config_focus_paths is None:
        config_focus_paths = _store_public_repository_candidate_config_focus_paths(
            repo_path=repo_path,
            focus_paths=probe_focus_paths,
            diagnostic_base_path=repo_path,
            diagnostic_project_path=None,
            config_focus_paths=probe_module._candidate_config_focus_paths(
                repo_path=repo_path,
                focus_paths=probe_focus_paths,
                diagnostic_base_path=repo_path,
                diagnostic_project_path=None,
            ),
        )
    effective_focus_paths = probe_module._effective_focus_paths_for_snapshot(
        diagnostics=[],
        connected_files=seed_files,
        fallback_focus_paths=list(probe_focus_paths),
        config_focus_paths=config_focus_paths,
    )
    snapshot_request = RepositorySnapshotCreateRequest(
        focus_paths=effective_focus_paths,
        prefer_concrete_focus_paths=runtime_support._should_prefer_concrete_snapshot_focus_paths(
            repo_path=repo_path,
            focus_paths=effective_focus_paths,
        ),
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        exclude_patterns=probe_module.DEFAULT_EXCLUDE_PATTERNS,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_total_bytes=max_total_bytes,
    )
    connector = probe_module._repository_connector(
        repo_path,
        assume_clean_git_clone=True,
        resolved_revision=_cached_public_repository_head_revision(repo_path),
    )
    original_runtime_dir = os.environ.get("ALGENTA_RUNTIME_DIR")
    original_shared_runtime_dir = os.environ.get(_SHARED_RUNTIME_DIR_ENV)
    os.environ["ALGENTA_RUNTIME_DIR"] = str(runtime_dir)
    if original_shared_runtime_dir is None:
        os.environ[_SHARED_RUNTIME_DIR_ENV] = str(
            _public_repository_case_shared_runtime_dir(
                runtime_root=runtime_root,
                case=case,
            ).resolve()
        )
    try:
        snapshot = repository_service.create_repository_snapshot(
            connector=connector,
            request=snapshot_request,
        )
    finally:
        if original_runtime_dir is None:
            os.environ.pop("ALGENTA_RUNTIME_DIR", None)
        else:
            os.environ["ALGENTA_RUNTIME_DIR"] = original_runtime_dir
        if original_shared_runtime_dir is None:
            os.environ.pop(_SHARED_RUNTIME_DIR_ENV, None)
        else:
            os.environ[_SHARED_RUNTIME_DIR_ENV] = original_shared_runtime_dir
    connected_file_count = (
        int(snapshot.file_count)
        if connected_file_count_mode == "snapshot"
        else len(seed_files)
    )
    return {
        "planner_status": "not_attempted_no_diagnostics",
        "operational_seed_plan": {
            "detected_ecosystems": list(operational_seed_plan["detected_ecosystems"]),
            "operational_ecosystems": list(operational_seed_plan["operational_ecosystems"]),
        },
        "snapshot": {"file_count": int(snapshot.file_count)},
        "connected_map": {
            "connected_file_count": connected_file_count,
            "seed_files": seed_files,
        },
    }


def _seed_plan_result_for_explicit_focus_case(
    case: PublicRepositoryCase,
    *,
    repo_path: Path,
    max_files: int,
) -> dict[str, Any] | None:
    repo_path = _normalized_public_repository_repo_path(repo_path)
    if not case.focus_paths:
        return None
    normalized_focus_paths = list(_normalized_public_repository_focus_paths(list(case.focus_paths)))
    cached_result_exists, cached_result = (
        _cached_public_repository_explicit_focus_seed_plan_result(
            case=case,
            repo_path=repo_path,
            focus_paths=normalized_focus_paths,
            max_files=max_files,
        )
    )
    if cached_result_exists:
        return cached_result
    seed_plan_result = _run_public_repository_seed_plan_for_checkout(
        case,
        repo_path=repo_path,
        max_files=_public_repository_probe_focus_prepass_max_files(max_files),
        focus_paths=normalized_focus_paths,
    )
    focused_seed_plan_result = _focused_seed_plan_result(
        seed_plan_result=seed_plan_result,
        repo_path=repo_path,
        focus_paths=normalized_focus_paths,
        language=case.language,
        expected_primary_ecosystem=case.expected_primary_ecosystem,
    )
    # The focused pass *narrows* an already-matching seed plan to the in-focus expected
    # ecosystem; it must not *resurrect* a missed seed plan into a hit from candidate files
    # whose entrypoints fell outside the focus. When the underlying seed plan missed, defer to
    # the direct fallback probe (return None) rather than adopting a manufactured match.
    if focused_seed_plan_result is not None and seed_plan_result.get("primary_match"):
        seed_plan_result = focused_seed_plan_result
    if not seed_plan_result["primary_match"] or not seed_plan_result["entrypoint_files"]:
        return _store_public_repository_explicit_focus_seed_plan_result(
            case=case,
            repo_path=repo_path,
            focus_paths=normalized_focus_paths,
            max_files=max_files,
            result=None,
        )
    return _store_public_repository_explicit_focus_seed_plan_result(
        case=case,
        repo_path=repo_path,
        focus_paths=normalized_focus_paths,
        max_files=max_files,
        result=seed_plan_result,
    )


def _run_public_repository_probe_for_checkout(
    case: PublicRepositoryCase,
    *,
    repo_path: Path,
    runtime_root: Path,
    max_files: int = 256,
    max_file_size_bytes: int = 250_000,
    max_total_bytes: int = 8_000_000,
    max_dependency_depth: int = 3,
    max_connected_files: int = 64,
) -> dict[str, Any]:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support
    from benchmarks import (
        repository_intelligence_real_repo_probe_profile_path_classification_support as classification_support,
    )

    repo_path = _normalized_public_repository_repo_path(repo_path)
    collection_support.begin_git_repo_relative_files_cache_scope()
    classification_support.begin_repo_file_stat_cache_scope()
    try:
        collection_support.set_git_repo_assume_clean_clone(repo_path, True)
        tracked_relative_paths = _cached_public_repository_tracked_relative_files(repo_path)
        if tracked_relative_paths:
            collection_support.seed_git_repo_relative_files_cache(
                repo_path,
                tracked_relative_paths,
                relative_paths_are_canonical=True,
            )
        probe_focus_paths = list(case.focus_paths)
        seed_plan_result: dict[str, Any] | None = None
        connected_file_count_mode: Literal["seed_files", "snapshot"] = "seed_files"
        if probe_focus_paths:
            seed_plan_result = _seed_plan_result_for_explicit_focus_case(
                case,
                repo_path=repo_path,
                max_files=max_files,
            )
            if seed_plan_result is not None:
                connected_file_count_mode = "snapshot"
        else:
            seed_plan_result, probe_focus_paths = _refine_seed_plan_result_for_unscoped_case(
                case,
                repo_path=repo_path,
                max_files=max_files,
            )
        operational_seed_plan = (
            None
            if seed_plan_result is None
            else _public_repository_operational_seed_plan(seed_plan_result)
        )
        if (
            seed_plan_result is not None
            and bool(seed_plan_result.get("primary_match"))
            and bool(operational_seed_plan["entrypoint_files"])
        ):
            probe_result = _run_public_repository_probe_from_seed_plan(
                case,
                repo_path=repo_path,
                runtime_root=runtime_root,
                probe_focus_paths=probe_focus_paths,
                operational_seed_plan=operational_seed_plan,
                max_files=max_files,
                max_file_size_bytes=max_file_size_bytes,
                max_total_bytes=max_total_bytes,
                connected_file_count_mode=connected_file_count_mode,
            )
        else:
            probe_result = probe_module.run_probe(
                repo_path=repo_path,
                focus_paths=probe_focus_paths,
                operational_seed_plan=operational_seed_plan,
                use_seed_files_as_connected_map=seed_plan_result is not None,
                diagnostic_command=None,
                diagnostic_base_path=None,
                planner_model=None,
                runtime_dir=runtime_root / _case_checkout_name(case),
                reuse_existing_state=False,
                max_files=max_files,
                max_file_size_bytes=max_file_size_bytes,
                max_total_bytes=max_total_bytes,
                max_dependency_depth=max_dependency_depth,
                max_connected_files=max_connected_files,
                assume_clean_git_clone=True,
                resolved_revision=_cached_public_repository_head_revision(repo_path),
                perform_warm_snapshot=False,
                load_graph_summary=False,
            )
        detected_ecosystems = list(probe_result["operational_seed_plan"]["detected_ecosystems"])
        operational_ecosystems = list(
            probe_result["operational_seed_plan"].get("operational_ecosystems")
            or detected_ecosystems
        )
        return {
            "case": asdict(case),
            "case_key": _public_repository_case_key(case),
            "repo_path": str(repo_path),
            "planner_status": probe_result["planner_status"],
            **_ecosystem_summary(
                detected_ecosystems=detected_ecosystems,
                operational_ecosystems=operational_ecosystems,
                language=case.language,
                expected_primary_ecosystem=case.expected_primary_ecosystem,
            ),
            "snapshot_file_count": int(probe_result["snapshot"]["file_count"]),
            "connected_file_count": int(probe_result["connected_map"]["connected_file_count"]),
            "seed_files": list(probe_result["connected_map"]["seed_files"]),
        }
    finally:
        classification_support.end_repo_file_stat_cache_scope()
        collection_support.end_git_repo_relative_files_cache_scope()


def run_public_repository_seed_plan_case(
    case: PublicRepositoryCase,
    *,
    checkout_root: Path,
    refresh: bool = False,
    max_files: int = 512,
) -> dict[str, Any]:
    with _public_repository_checkout_context(
        case,
        checkout_root=checkout_root,
        refresh=refresh,
    ) as repo_path:
        return _run_seed_plan_case_for_checkout(
            case,
            repo_path=repo_path,
            max_files=max_files,
        )


def run_public_repository_probe_case(
    case: PublicRepositoryCase,
    *,
    checkout_root: Path,
    runtime_root: Path,
    refresh: bool = False,
    max_files: int = 256,
    max_file_size_bytes: int = 250_000,
    max_total_bytes: int = 8_000_000,
    max_dependency_depth: int = 3,
    max_connected_files: int = 64,
) -> dict[str, Any]:
    with _public_repository_checkout_context(
        case,
        checkout_root=checkout_root,
        refresh=refresh,
    ) as repo_path:
        prime_public_repository_probe_runtime()
        return _run_public_repository_probe_for_checkout(
            case,
            repo_path=repo_path,
            runtime_root=runtime_root,
            max_files=max_files,
            max_file_size_bytes=max_file_size_bytes,
            max_total_bytes=max_total_bytes,
            max_dependency_depth=max_dependency_depth,
            max_connected_files=max_connected_files,
        )


def run_public_repository_matrix(
    *,
    mode: MatrixMode,
    checkout_root: Path,
    runtime_root: Path,
    refresh: bool = False,
    languages: tuple[str, ...] = (),
    cases: list[PublicRepositoryCase] | None = None,
    limit: int | None = None,
    ranked_target_language_count: int = DEFAULT_REAL_LANGUAGE_RANK_TARGET,
    case_timeout_seconds: int | None = None,
) -> dict[str, Any]:
    ordered_cases = (
        list(cases)
        if cases is not None
        else ordered_public_repository_cases(
            languages=languages,
            limit=limit,
        )
    )
    configured_case_languages = configured_public_repository_case_languages()
    support_progress = repository_language_support_progress(
        ranked_target_language_count=ranked_target_language_count
    )
    probe_runtime_primed = False
    results: list[dict[str, Any]] = []
    for case in ordered_cases:
        try:
            with _public_repository_checkout_context(
                case,
                checkout_root=checkout_root,
                refresh=refresh,
            ) as repo_path:
                if mode == "probe" and not probe_runtime_primed:
                    prime_public_repository_probe_runtime()
                    probe_runtime_primed = True
                result = _run_with_case_timeout(
                    timeout_seconds=case_timeout_seconds,
                    callback=lambda: (
                        _run_seed_plan_case_for_checkout(
                            case,
                            repo_path=repo_path,
                        )
                        if mode == "seed_plan"
                        else _run_public_repository_probe_for_checkout(
                            case,
                            repo_path=repo_path,
                            runtime_root=runtime_root,
                        )
                    )
                )
        except Exception as exc:
            result = {
                "case": asdict(case),
                "case_key": _public_repository_case_key(case),
                "error": {
                    "code": exc.__class__.__name__,
                    "message": str(exc),
                    "details": {},
                },
            }
        results.append(result)
    selected_case_keys = [_public_repository_case_key(case) for case in ordered_cases]
    passing_case_keys = [
        str(result.get("case_key") or _public_repository_case_key(result["case"]))
        for result in results
        if result.get("primary_match") is True
    ]
    return {
        "mode": mode,
        "case_count": len(ordered_cases),
        "support_progress": {
            "supported_real_language_count": support_progress.supported_real_language_count,
            "ranked_target_language_count": support_progress.ranked_target_language_count,
            "requested_ranked_target_language_count": (
                support_progress.requested_ranked_target_language_count
            ),
            "available_ranked_real_language_count": (
                support_progress.available_ranked_real_language_count
            ),
            "target_clamped_to_available_ranked_real_languages": (
                support_progress.target_clamped_to_available_ranked_real_languages
            ),
            "progress_fraction": support_progress.progress_fraction,
            "progress_label": support_progress.progress_label,
        },
        "public_case_progress": {
            "configured_real_language_count": len(configured_case_languages),
            "ranked_target_language_count": support_progress.ranked_target_language_count,
            "requested_ranked_target_language_count": (
                support_progress.requested_ranked_target_language_count
            ),
            "available_ranked_real_language_count": (
                support_progress.available_ranked_real_language_count
            ),
            "target_clamped_to_available_ranked_real_languages": (
                support_progress.target_clamped_to_available_ranked_real_languages
            ),
            "configured_progress_fraction": len(configured_case_languages)
            / float(support_progress.ranked_target_language_count),
            "configured_progress_label": (
                f"{len(configured_case_languages)} / "
                f"{support_progress.ranked_target_language_count}"
            ),
            "selected_case_count": len(ordered_cases),
            "selected_case_keys": selected_case_keys,
            "selected_case_language_count": len({case.language for case in ordered_cases}),
            "passing_case_count": len(passing_case_keys),
            "passing_case_keys": passing_case_keys,
            "passing_case_language_count": len(
                {
                    result["case"]["language"]
                    for result in results
                    if result.get("primary_match") is True
                }
            ),
            "missing_real_languages": list(missing_supported_public_repository_languages()),
        },
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the ranked public GitHub repository matrix for Repository Intelligence."
    )
    parser.add_argument(
        "--mode",
        choices=("seed_plan", "probe"),
        default="seed_plan",
    )
    parser.add_argument(
        "--language",
        dest="languages",
        action="append",
        default=[],
        help="Optional language/ecosystem filter. May be passed multiple times.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--case-timeout-seconds", type=int, default=None)
    parser.add_argument(
        "--checkout-root",
        type=Path,
        default=DEFAULT_CHECKOUT_ROOT,
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=PROJECT_ROOT / "build" / "repository_intelligence_public_repo_matrix_runtime",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--rank-target",
        type=int,
        default=DEFAULT_REAL_LANGUAGE_RANK_TARGET,
        help="Display real-language support progress against this ranked-language total.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = run_public_repository_matrix(
        mode=args.mode,
        checkout_root=args.checkout_root,
        runtime_root=args.runtime_root,
        refresh=bool(args.refresh),
        languages=tuple(args.languages),
        limit=args.limit,
        ranked_target_language_count=args.rank_target,
        case_timeout_seconds=args.case_timeout_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
