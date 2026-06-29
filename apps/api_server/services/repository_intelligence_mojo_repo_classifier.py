from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.compute.mojo_adapter import invoke_engine_sync
from apps.api_server.compute.mojo_errors import MojoEngineError
from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_compat_exports as repository_compat_exports,
)
from apps.api_server.services.repository_intelligence_file_selection import (
    TEXT_FILE_BASENAMES,
    TEXT_FILE_SUFFIXES,
)
from apps.api_server.services.repository_intelligence_runtime_language_support import (
    repository_runtime_language_route_index,
)
from apps.api_server.services.repository_language_priority import (
    canonical_repository_language,
    repository_language_priority,
    supported_repository_languages,
)

_ENGINE_TYPE = "repo_classifier"
_DEFAULT_BATCH_SIZE = 256
_DEFAULT_TOP_K = 4
_DEFAULT_TIMEOUT_SECONDS = 30.0
_MAX_CONTENT_HINT_BYTES = 512
_MAX_HINT_TOKENS = 24
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_LANGUAGE_METADATA_ATTR_SUFFIXES = (
    "SUFFIXES",
    "SOURCE_SUFFIXES",
    "BASENAMES",
    "CONFIG_BASENAMES",
    "FILE_BASENAMES",
)


@dataclass(frozen=True)
class RepositoryMojoRepoClassifierLanguage:
    language: str
    rank: int
    aliases: tuple[str, ...]
    route_families: tuple[str, ...]
    suffixes: tuple[str, ...]
    basenames: tuple[str, ...]
    tokens: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "rank": self.rank,
            "aliases": list(self.aliases),
            "route_families": list(self.route_families),
            "suffixes": list(self.suffixes),
            "basenames": list(self.basenames),
            "tokens": list(self.tokens),
        }


@dataclass(frozen=True)
class RepositoryMojoRepoClassifierFileHint:
    path: str
    basename: str
    suffix: str
    path_tokens: tuple[str, ...]
    content_tokens: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "basename": self.basename,
            "suffix": self.suffix,
            "path_tokens": list(self.path_tokens),
            "content_tokens": list(self.content_tokens),
        }


@dataclass(frozen=True)
class RepositoryMojoRepoClassifierMatch:
    language: str
    score: float
    suffix_match: bool
    basename_match: bool
    path_token_hits: int
    content_token_hits: int


@dataclass(frozen=True)
class RepositoryMojoRepoClassifierResult:
    path: str
    primary_language: str
    primary_score: float
    matches: tuple[RepositoryMojoRepoClassifierMatch, ...]


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _tokenize_text(value: str, *, limit: int = _MAX_HINT_TOKENS) -> tuple[str, ...]:
    tokens = _ordered_unique(_TOKEN_RE.findall(value.lower()))
    return tokens[:limit]


def _language_token_candidates(
    *,
    language: str,
    aliases: tuple[str, ...],
    route_families: tuple[str, ...],
    suffixes: tuple[str, ...],
    basenames: tuple[str, ...],
) -> tuple[str, ...]:
    token_inputs: list[str] = [language, *aliases, *route_families]
    token_inputs.extend(suffix.removeprefix(".") for suffix in suffixes)
    token_inputs.extend(PurePosixPath(basename).stem for basename in basenames)
    tokens: list[str] = []
    for value in token_inputs:
        tokens.extend(_tokenize_text(value, limit=_MAX_HINT_TOKENS))
    return _ordered_unique(tokens)


def _candidate_adapter_export_names(
    language: str, raw_language_keys: tuple[str, ...]
) -> tuple[str, ...]:
    candidates: list[str] = []
    for raw_name in (language, *raw_language_keys):
        normalized = re.sub(r"[^a-z0-9]+", "_", raw_name.strip().lower()).strip("_")
        if normalized:
            candidates.append(f"{normalized}_adapter")
    return _ordered_unique(candidates)


def _resolve_language_adapter(language: str, raw_language_keys: tuple[str, ...]) -> Any | None:
    for export_name in _candidate_adapter_export_names(language, raw_language_keys):
        try:
            return repository_compat_exports.get_export(export_name)
        except AttributeError:
            continue
    return None


def _adapter_metadata_strings(adapter: Any | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if adapter is None:
        return (), ()
    suffixes: list[str] = []
    basenames: list[str] = []
    for attr_name in dir(adapter):
        if not attr_name.endswith(_LANGUAGE_METADATA_ATTR_SUFFIXES):
            continue
        value = getattr(adapter, attr_name, None)
        if not isinstance(value, tuple | list | set | frozenset):
            continue
        for candidate in value:
            normalized = str(candidate).strip().lower()
            if not normalized:
                continue
            if normalized.startswith("."):
                suffixes.append(normalized)
            elif "/" not in normalized and "\\" not in normalized:
                basenames.append(normalized)
    return _ordered_unique(suffixes), _ordered_unique(basenames)


def _probe_classifier_suffix_language(suffix: str) -> str:
    path = Path(f"probe{suffix}")
    language = canonical_repository_language(repository_service._language_for_path(path))
    if language:
        return language
    try:
        return canonical_repository_language(
            repository_service._language_for_path(
                path,
                text="module package namespace class function import export",
            )
        )
    except Exception:
        return ""


def _probe_classifier_basename_language(basename: str) -> str:
    path = Path(basename)
    language = canonical_repository_language(repository_service._language_for_path(path))
    if language:
        return language
    try:
        return canonical_repository_language(
            repository_service._language_for_path(
                path,
                text="module package namespace class function import export",
            )
        )
    except Exception:
        return ""


@lru_cache(maxsize=1)
def _discovered_classifier_suffixes() -> dict[str, tuple[str, ...]]:
    suffixes_by_language: dict[str, list[str]] = {}
    candidate_suffixes = {
        *(str(item).lower() for item in TEXT_FILE_SUFFIXES),
        *repository_service._DIRECT_TEXT_SUFFIX_LANGUAGE_MAP,
    }
    for suffix in sorted(candidate_suffixes):
        if not suffix.startswith("."):
            continue
        language = _probe_classifier_suffix_language(suffix)
        if language:
            suffixes_by_language.setdefault(language, []).append(suffix)
    return {
        language: _ordered_unique(suffixes)
        for language, suffixes in suffixes_by_language.items()
    }


@lru_cache(maxsize=1)
def _discovered_classifier_basenames() -> dict[str, tuple[str, ...]]:
    basenames_by_language: dict[str, list[str]] = {}
    candidate_basenames = sorted(
        {
            *(str(item).lower() for item in TEXT_FILE_BASENAMES),
            *(str(item).lower() for item in repository_service._SHELL_FILE_BASENAMES),
        }
    )
    for basename in candidate_basenames:
        language = _probe_classifier_basename_language(basename)
        if language:
            basenames_by_language.setdefault(language, []).append(basename)
    return {
        language: _ordered_unique(basenames)
        for language, basenames in basenames_by_language.items()
    }


@lru_cache(maxsize=1)
def build_repository_mojo_repo_classifier_language_catalog() -> tuple[
    RepositoryMojoRepoClassifierLanguage, ...
]:
    route_index = repository_runtime_language_route_index()
    direct_text_suffixes = repository_service._DIRECT_TEXT_SUFFIX_LANGUAGE_MAP
    discovered_suffixes = _discovered_classifier_suffixes()
    discovered_basenames = _discovered_classifier_basenames()
    catalog_languages = {
        *supported_repository_languages(),
        *discovered_suffixes,
        *discovered_basenames,
    }
    catalog_languages.discard("unknown")

    catalog: list[RepositoryMojoRepoClassifierLanguage] = []
    for language in sorted(catalog_languages, key=repository_language_priority):
        route = route_index.get(language)
        raw_language_keys = _ordered_unique(
            [
                *(route.file_plane.raw_language_keys if route is not None else ()),
                *(route.dependency_plane.raw_language_keys if route is not None else ()),
            ]
        )
        aliases = _ordered_unique([language, *raw_language_keys])
        adapter = _resolve_language_adapter(language, raw_language_keys)
        adapter_suffixes, adapter_basenames = _adapter_metadata_strings(adapter)
        direct_suffixes = tuple(
            suffix
            for suffix, mapped_language in direct_text_suffixes.items()
            if canonical_repository_language(mapped_language) == language
        )
        route_families = _ordered_unique(
            [
                *(route.file_plane.route_family for route in (route,) if route is not None),
                *(route.dependency_plane.route_family for route in (route,) if route is not None),
            ]
        )
        suffixes = _ordered_unique(
            [
                *adapter_suffixes,
                *direct_suffixes,
                *discovered_suffixes.get(language, ()),
            ]
        )
        basenames = _ordered_unique(
            [
                *adapter_basenames,
                *discovered_basenames.get(language, ()),
                *(
                    repository_service._SHELL_FILE_BASENAMES
                    if language == "shell"
                    else ()
                ),
            ]
        )
        tokens = _language_token_candidates(
            language=language,
            aliases=aliases,
            route_families=route_families,
            suffixes=suffixes,
            basenames=basenames,
        )
        catalog.append(
            RepositoryMojoRepoClassifierLanguage(
                language=language,
                rank=repository_language_priority(language)[0],
                aliases=aliases,
                route_families=route_families,
                suffixes=suffixes,
                basenames=basenames,
                tokens=tokens,
            )
        )
    return tuple(catalog)


def _read_content_hint_tokens(repo_path: Path, relative_path: str) -> tuple[str, ...]:
    file_path = repo_path / relative_path
    try:
        raw = file_path.read_bytes()[:_MAX_CONTENT_HINT_BYTES]
    except OSError:
        return ()
    if not raw:
        return ()
    return _tokenize_text(raw.decode("utf-8", errors="replace"))


def build_repository_mojo_repo_classifier_file_hints(
    candidate_file_paths: list[str],
    *,
    repo_path: Path,
) -> tuple[RepositoryMojoRepoClassifierFileHint, ...]:
    hints: list[RepositoryMojoRepoClassifierFileHint] = []
    for candidate_path in candidate_file_paths:
        normalized_path = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_path:
            continue
        pure_path = PurePosixPath(normalized_path)
        hints.append(
            RepositoryMojoRepoClassifierFileHint(
                path=normalized_path,
                basename=pure_path.name.lower(),
                suffix=pure_path.suffix.lower(),
                path_tokens=_tokenize_text(normalized_path),
                content_tokens=_read_content_hint_tokens(repo_path, normalized_path),
            )
        )
    return tuple(hints)


def _chunk_file_hints(
    file_hints: tuple[RepositoryMojoRepoClassifierFileHint, ...],
    *,
    batch_size: int,
) -> tuple[tuple[RepositoryMojoRepoClassifierFileHint, ...], ...]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    return tuple(
        file_hints[index : index + batch_size]
        for index in range(0, len(file_hints), batch_size)
    )


def _coerce_repo_classifier_match(
    match_payload: dict[str, Any]
) -> RepositoryMojoRepoClassifierMatch:
    language = canonical_repository_language(match_payload.get("language"))
    if not language:
        raise MojoEngineError(
            "Mojo repo_classifier returned a match without a canonical language.",
            code="invalid_response",
            recoverable=False,
            engine_type=_ENGINE_TYPE,
            stage="decode",
            details={"match": match_payload},
        )
    return RepositoryMojoRepoClassifierMatch(
        language=language,
        score=float(match_payload.get("score") or 0.0),
        suffix_match=bool(match_payload.get("suffix_match")),
        basename_match=bool(match_payload.get("basename_match")),
        path_token_hits=int(match_payload.get("path_token_hits") or 0),
        content_token_hits=int(match_payload.get("content_token_hits") or 0),
    )


def _coerce_repo_classifier_response(
    response: dict[str, Any],
    *,
    expected_paths: tuple[str, ...],
) -> tuple[RepositoryMojoRepoClassifierResult, ...]:
    if response.get("engine") != "mojo" or response.get("engine_type") != _ENGINE_TYPE:
        raise MojoEngineError(
            "Mojo repo_classifier returned an unexpected response envelope.",
            code="invalid_response",
            recoverable=False,
            engine_type=_ENGINE_TYPE,
            stage="decode",
            details={"response": response},
        )
    raw_results = response.get("results")
    if not isinstance(raw_results, list):
        raise MojoEngineError(
            "Mojo repo_classifier response is missing a results list.",
            code="invalid_response",
            recoverable=False,
            engine_type=_ENGINE_TYPE,
            stage="decode",
            details={"response": response},
        )

    result_by_path: dict[str, RepositoryMojoRepoClassifierResult] = {}
    for raw_result in raw_results:
        if not isinstance(raw_result, dict):
            raise MojoEngineError(
                "Mojo repo_classifier emitted a non-object result entry.",
                code="invalid_response",
                recoverable=False,
                engine_type=_ENGINE_TYPE,
                stage="decode",
                details={"result": raw_result},
            )
        path = repository_service._normalize_repository_relative_path(raw_result.get("path"))
        if not path:
            raise MojoEngineError(
                "Mojo repo_classifier emitted a result without a normalized path.",
                code="invalid_response",
                recoverable=False,
                engine_type=_ENGINE_TYPE,
                stage="decode",
                details={"result": raw_result},
            )
        raw_matches = raw_result.get("matches")
        if not isinstance(raw_matches, list):
            raise MojoEngineError(
                "Mojo repo_classifier emitted a result without a matches list.",
                code="invalid_response",
                recoverable=False,
                engine_type=_ENGINE_TYPE,
                stage="decode",
                details={"result": raw_result},
            )
        matches = tuple(_coerce_repo_classifier_match(match) for match in raw_matches)
        primary_language = canonical_repository_language(raw_result.get("primary_language")) or (
            matches[0].language if matches else "unknown"
        )
        result_by_path[path] = RepositoryMojoRepoClassifierResult(
            path=path,
            primary_language=primary_language,
            primary_score=float(raw_result.get("primary_score") or 0.0),
            matches=matches,
        )

    missing_paths = [path for path in expected_paths if path not in result_by_path]
    unexpected_paths = [path for path in result_by_path if path not in expected_paths]
    if missing_paths or unexpected_paths:
        raise MojoEngineError(
            "Mojo repo_classifier response paths did not match the requested batch.",
            code="invalid_response",
            recoverable=False,
            engine_type=_ENGINE_TYPE,
            stage="decode",
            details={
                "missing_paths": missing_paths,
                "unexpected_paths": unexpected_paths,
            },
        )
    return tuple(result_by_path[path] for path in expected_paths)


def classify_repository_paths_with_mojo(
    candidate_file_paths: list[str],
    *,
    repo_path: Path,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    top_k: int = _DEFAULT_TOP_K,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, RepositoryMojoRepoClassifierResult]:
    file_hints = build_repository_mojo_repo_classifier_file_hints(
        candidate_file_paths,
        repo_path=repo_path,
    )
    if not file_hints:
        return {}

    language_catalog = build_repository_mojo_repo_classifier_language_catalog()
    catalog_payload = [entry.to_payload() for entry in language_catalog]
    results: dict[str, RepositoryMojoRepoClassifierResult] = {}
    for batch in _chunk_file_hints(file_hints, batch_size=batch_size):
        batch_paths = tuple(file_hint.path for file_hint in batch)
        payload = {
            "engine_type": _ENGINE_TYPE,
            "top_k": top_k,
            "languages": catalog_payload,
            "files": [file_hint.to_payload() for file_hint in batch],
        }
        response = invoke_engine_sync(payload, timeout=timeout)
        for result in _coerce_repo_classifier_response(response, expected_paths=batch_paths):
            results[result.path] = result
    return results


# ── Shared-snapshot priming ───────────────────────────────────────────────────────────────────────
# The snapshot workflow classifies the WHOLE file set. Rather than run the per-file Python classifier
# (`_language_for_path`) on every file, prime once via the compiled mojo repo_classifier (batch,
# native scoring) and cache the per-path primary language; `_language_for_path` then returns the mojo
# result for primed paths. A cache miss or any mojo issue falls through to the Python classifier — the
# SAME correct classification, just not accelerated (no regression, no silent cloud fallback).
import threading as _threading

_PRIMED_LANG: dict[tuple[str, str], str] = {}
_PRIMED_LOCK = _threading.Lock()


def prime_repository_mojo_classification(repo_path: Path, relative_paths: list[str]) -> int:
    """Batch-classify ``relative_paths`` via the compiled mojo kernel and cache the primary language
    per (repo_root, normalized_path). Returns the count primed. NEVER raises — a mojo problem leaves
    the cache empty and the per-file Python classifier handles everything."""
    try:
        results = classify_repository_paths_with_mojo(list(relative_paths), repo_path=repo_path)
    except Exception:  # noqa: BLE001 — accelerator only; must never break a snapshot
        return 0
    root = str(repo_path)
    primed = 0
    with _PRIMED_LOCK:
        for rel, result in results.items():
            if result.primary_language and result.primary_language != "unknown":
                _PRIMED_LANG[(root, rel)] = result.primary_language
                primed += 1
    return primed


def mojo_primed_language(repo_path: Path, relative_path: str) -> str | None:
    """Look up a primed primary language. ``relative_path`` is normalized to match the prime keys."""
    rel = repository_service._normalize_repository_relative_path(relative_path)
    if not rel:
        return None
    with _PRIMED_LOCK:
        return _PRIMED_LANG.get((str(repo_path), rel))
