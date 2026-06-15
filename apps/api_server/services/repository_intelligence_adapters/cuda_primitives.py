from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import c_family as c_family_adapter

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

CUDA_SUFFIXES = frozenset({".cu", ".cuh"})
_CUDA_MARKER_RE = re.compile(
    r"(__global__|__device__|__host__|__shared__|\bcuda(?:Malloc|Memcpy|Free|LaunchKernel|Error_t|Stream_t)\b|<<<[^>\n]+>>>|#\s*include\s*[<\"]cuda)",
    re.IGNORECASE,
)

strip_comments = c_family_adapter.strip_comments
normalize_symbol_name = c_family_adapter.normalize_symbol_name
candidate_module_keys = c_family_adapter.candidate_module_keys


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


def has_cuda_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in CUDA_SUFFIXES


def is_probable_cuda_source(*, path: Path | PurePosixPath, text: str) -> bool:
    return is_probable_cuda_source_with_optional_stripped_text(path=path, text=text)


def is_probable_cuda_source_with_optional_stripped_text(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_cuda_path_hints(normalized_path) or not text or _looks_binaryish(text):
        return False
    sanitized_text = stripped_text if stripped_text is not None else strip_comments(text)
    if not sanitized_text.strip():
        return False
    return normalized_path.suffix.lower() == ".cu" or bool(_CUDA_MARKER_RE.search(sanitized_text))


def module_name_from_path(file_path: str) -> str:
    return "/".join(PurePosixPath(file_path).with_suffix("").parts)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
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
    if text is None:
        try:
            text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    stripped_text = strip_comments(text) if text else ""
    if text and is_probable_cuda_source_with_optional_stripped_text(
        path=Path(normalized_path),
        text=text,
        stripped_text=stripped_text,
    ):
        sanitized_text = c_family_adapter.strip_attributes(stripped_text)
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
    return c_family_adapter.resolve_include(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
