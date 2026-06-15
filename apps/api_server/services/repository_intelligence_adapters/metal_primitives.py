from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import c_family as c_family_adapter

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

METAL_SUFFIXES = frozenset({".metal", ".metalh"})
_METAL_SOURCE_SUFFIXES = frozenset({".metal", ".metalh", ".h", ".hh", ".hpp", ".hxx", ".inc"})
_METAL_MARKER_RE = re.compile(
    r"(#\s*include\s*[<\"]metal_stdlib[>\"]|\busing\s+namespace\s+metal\b|"
    r"\[\[\s*(?:kernel|vertex|fragment|stitchable|host_name|position|stage_in|buffer|texture|sampler)\b|"
    r"\b(?:kernel|vertex|fragment)\b\s+[A-Za-z_][A-Za-z0-9_<>:&*\s]*\(|"
    r"\b(?:device|constant|threadgroup|thread_position_in_grid|thread_position_in_threadgroup|"
    r"threads_per_threadgroup|texture[123]d(?:_array|_ms)?|sampler)\b)"
)

strip_comments = c_family_adapter.strip_comments
normalize_symbol_name = c_family_adapter.normalize_symbol_name


def _normalize_repository_relative_path(value: str) -> str:
    raw_parts = PurePosixPath(str(value).replace("\\", "/")).parts
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


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def has_metal_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in METAL_SUFFIXES


def is_probable_metal_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in METAL_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(_METAL_MARKER_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    return "/".join(PurePosixPath(file_path).with_suffix("").parts)


def candidate_module_keys(
    base_path: str,
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_base = normalize_repository_relative_path(base_path)
    if not normalized_base:
        return ()
    suffix = PurePosixPath(normalized_base).suffix.lower()
    if suffix in _METAL_SOURCE_SUFFIXES:
        seen: set[str] = set()
        ordered: list[str] = []
        for candidate in (
            normalized_base,
            normalize_repository_relative_path(str(PurePosixPath(normalized_base).with_suffix(""))),
        ):
            if candidate and candidate not in seen:
                seen.add(candidate)
                ordered.append(candidate)
        return tuple(ordered)
    candidates = [normalized_base]
    candidates.extend(
        f"{normalized_base}{suffix}"
        for suffix in (".metal", ".metalh", ".h", ".hh", ".hpp", ".hxx", ".inc")
    )
    return tuple(dict.fromkeys(candidates))


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = _normalize_repository_relative_path(file_path)
    if not normalized_path:
        return set()
    aliases = {
        normalized_path,
        PurePosixPath(normalized_path).name,
        str(PurePosixPath(normalized_path).with_suffix("")),
        PurePosixPath(normalized_path).stem,
        module_name_from_path(normalized_path),
    }
    module_name = module_name_from_path(normalized_path)
    aliases.update(
        candidate_module_keys(
            normalized_path,
            normalize_repository_relative_path=_normalize_repository_relative_path,
        )
    )
    try:
        text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and is_probable_metal_source(path=Path(normalized_path), text=text):
        sanitized_text = c_family_adapter.strip_attributes(strip_comments(text))
        for regex in (c_family_adapter.TYPE_DECL_RE, c_family_adapter.FUNCTION_DECL_RE):
            for match in regex.finditer(sanitized_text):
                symbol_name = normalize_symbol_name(str(match.group("name") or ""))
                if not symbol_name or c_family_adapter.is_macro_like_symbol_name(symbol_name):
                    continue
                aliases.add(symbol_name)
                if module_name:
                    aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_include(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    candidate_keys: list[str] = []
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    relative_base = normalize_repository_relative_path(
        str(PurePosixPath(current_dir) / normalized_target)
    )
    if relative_base:
        candidate_keys.extend(
            candidate_module_keys(
                relative_base,
                normalize_repository_relative_path=normalize_repository_relative_path,
            )
        )
    direct_match = module_index.get(normalized_target)
    if direct_match is not None and direct_match != current_file:
        return direct_match
    if not normalized_target.startswith(".") and not normalized_target.startswith("/"):
        candidate_keys.extend(
            candidate_module_keys(
                normalized_target,
                normalize_repository_relative_path=normalize_repository_relative_path,
            )
        )
        for prefix in (
            "include",
            "includes",
            "shader",
            "shaders",
            "src",
            "source",
            "sources",
            "lib",
        ):
            candidate_keys.extend(
                candidate_module_keys(
                    f"{prefix}/{normalized_target}",
                    normalize_repository_relative_path=normalize_repository_relative_path,
                )
            )
    for candidate_key in candidate_keys:
        if not candidate_key:
            continue
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            normalized_target,
            PurePosixPath(normalized_target).name,
            str(PurePosixPath(normalized_target).with_suffix("")),
        ],
    )
    if resolved is not None and resolved != current_file:
        return resolved
    return None
