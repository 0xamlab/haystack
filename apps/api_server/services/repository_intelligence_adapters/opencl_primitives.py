from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import c_family as c_family_adapter

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

OPENCL_SUFFIXES = frozenset({".cl", ".clh"})
_OPENCL_SOURCE_SUFFIXES = frozenset({".cl", ".clh", ".h", ".hh", ".hpp", ".hxx", ".inc"})
_OPENCL_MARKER_RE = re.compile(
    r"(__kernel\b|\bkernel\s+void\b|__global\b|__local\b|__constant\b|__private\b|"
    r"\b(?:get_global_id|get_global_size|get_local_id|get_local_size|get_group_id|get_num_groups|barrier|mem_fence|async_work_group_copy|read_image[a-z0-9_]*|write_image[a-z0-9_]*)\s*\(|"
    r"\b(?:sampler_t|image[123]d_t|image[123]d_array_t|event_t|clk_event_t)\b|"
    r"#\s*pragma\s+OPENCL|#\s*include\s*[<\"](?:CL|cl)/)",
    re.IGNORECASE,
)

strip_comments = c_family_adapter.strip_comments
normalize_symbol_name = c_family_adapter.normalize_symbol_name


def _coalesced_stripped_text(text: str, stripped_text: str | None = None) -> str:
    return stripped_text if stripped_text is not None else strip_comments(text)


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


def has_opencl_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in OPENCL_SUFFIXES


def is_probable_opencl_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in OPENCL_SUFFIXES or not text or _looks_binaryish(text):
        return False
    coalesced_stripped_text = _coalesced_stripped_text(text, stripped_text)
    if not coalesced_stripped_text.strip():
        return False
    return bool(_OPENCL_MARKER_RE.search(coalesced_stripped_text))


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
    if suffix in _OPENCL_SOURCE_SUFFIXES:
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
        for suffix in (".clh", ".cl", ".h", ".hh", ".hpp", ".hxx", ".inc")
    )
    return tuple(dict.fromkeys(candidates))


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
    include_symbol_aliases: bool = True,
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
    file_text = text
    if file_text is None:
        try:
            file_text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            file_text = ""
    coalesced_stripped_text = _coalesced_stripped_text(file_text, stripped_text)
    if file_text and is_probable_opencl_source(
        path=Path(normalized_path),
        text=file_text,
        stripped_text=coalesced_stripped_text,
    ):
        if include_symbol_aliases:
            sanitized_text = c_family_adapter.strip_attributes(coalesced_stripped_text)
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
        for prefix in ("include", "kernels", "kernel", "src", "source", "sources", "lib"):
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
