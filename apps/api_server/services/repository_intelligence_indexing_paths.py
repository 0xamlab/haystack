# ruff: noqa: I001
from __future__ import annotations
from functools import lru_cache
from fnmatch import fnmatchcase


def _normalize_repository_relative_path(value: str) -> str:
    return _normalize_repository_relative_path_cached(str(value))


@lru_cache(maxsize=16_384)
def _normalize_repository_relative_path_cached(value: str) -> str:
    raw_parts = value.replace("\\", "/").split("/")
    normalized_parts: list[str] = []
    for part in raw_parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)
def _normalize_repository_relative_pattern(value: str) -> str:
    wildcard_sentinel = "__ALGENTA_WILDCARD__"
    normalized = _normalize_repository_relative_path(str(value).replace("*", wildcard_sentinel))
    return normalized.replace(wildcard_sentinel, "*")


def _matches_repository_scope(relative_path: str, scope: str) -> bool:
    normalized_scope = _normalize_repository_relative_path(scope)
    if not normalized_scope:
        return True
    return relative_path == normalized_scope or relative_path.startswith(f"{normalized_scope}/")
def _matches_repository_pattern(relative_path: str, pattern: str) -> bool:
    normalized_pattern = _normalize_repository_relative_path(pattern)
    if not normalized_pattern:
        return True
    if _matches_repository_scope(relative_path, normalized_pattern):
        return True
    pattern_variants = {normalized_pattern}
    pending_patterns = [normalized_pattern]
    while pending_patterns:
        candidate_pattern = pending_patterns.pop()
        if "/**/" not in candidate_pattern:
            continue
        direct_variant = candidate_pattern.replace("/**/", "/", 1)
        if direct_variant not in pattern_variants:
            pattern_variants.add(direct_variant)
            pending_patterns.append(direct_variant)
    return any(fnmatchcase(relative_path, candidate_pattern) for candidate_pattern in sorted(pattern_variants))
