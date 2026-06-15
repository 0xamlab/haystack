from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

PKL_SUFFIXES = frozenset({".pkl"})
PKL_CONFIG_BASENAMES = frozenset({"PklProject"})
_DECLARATION_RE = re.compile(
    r"(?im)^\s*(?:open\s+)?(?P<kind>class|module|function|typealias)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_PROPERTY_RE = re.compile(
    r"(?im)^\s*(?:local|hidden|fixed|const)?\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*="
)
_IMPORT_RE = re.compile(
    r"""(?im)^\s*(?P<kind>import|amends|extends)\s+["'](?P<target>[^"']+)["']"""
)
_NEW_REFERENCE_RE = re.compile(r"(?im)\bnew\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_CALL_REFERENCE_RE = re.compile(r"(?im)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\.apply\s*\(")
_FEATURE_RE = re.compile(
    r"(?im)\b(?:amends|extends|import|module|class|typealias|local|hidden|fixed|open)\b"
    r"|->"
    r"|\bnew\s+[A-Za-z_][A-Za-z0-9_]*\s*\{"
    r"|\bList\s*\("
    r"|\.apply\s*\("
)


def strip_comments(text: str) -> str:
    stripped_lines: list[str] = []
    for line in str(text or "").splitlines():
        if "//" not in line:
            stripped_lines.append(line)
            continue
        quote: str | None = None
        escaped = False
        buffer: list[str] = []
        index = 0
        while index < len(line):
            character = line[index]
            if escaped:
                buffer.append(character)
                escaped = False
                index += 1
                continue
            if character == "\\" and quote is not None:
                buffer.append(character)
                escaped = True
                index += 1
                continue
            if character in {'"', "'"}:
                if quote == character:
                    quote = None
                elif quote is None:
                    quote = character
                buffer.append(character)
                index += 1
                continue
            if character == "/" and quote is None and index + 1 < len(line) and line[index + 1] == "/":
                break
            buffer.append(character)
            index += 1
        stripped_lines.append("".join(buffer))
    return "\n".join(stripped_lines)


def _looks_binaryish(text: str) -> bool:
    sample = str(text or "")[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _line_count(text: str) -> int:
    return max(1, str(text or "").count("\n") + 1)


def has_pkl_path_hints(path: Path | PurePosixPath | str) -> bool:
    pure_path = PurePosixPath(path)
    return pure_path.suffix.lower() in PKL_SUFFIXES or pure_path.name in PKL_CONFIG_BASENAMES


def is_probable_pkl_source(*, path: Path | PurePosixPath, text: str) -> bool:
    pure_path = PurePosixPath(path)
    if pure_path.suffix.lower() not in PKL_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(_FEATURE_RE.search(stripped_text))


def is_probable_pkl_config(*, path: Path | PurePosixPath, text: str) -> bool:
    pure_path = PurePosixPath(path)
    if pure_path.name not in PKL_CONFIG_BASENAMES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip() and _FEATURE_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    if normalized_path.name in PKL_CONFIG_BASENAMES:
        return normalized_path.name
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def path_aliases_for_file(file_path: str) -> set[str]:
    normalized_path = PurePosixPath(str(file_path).replace("\\", "/"))
    aliases = {str(normalized_path).replace("\\", "/"), normalized_path.name}
    if normalized_path.name in PKL_CONFIG_BASENAMES:
        aliases.add(normalized_path.name)
    else:
        without_suffix = normalized_path.with_suffix("")
        aliases.update({".".join(without_suffix.parts), "/".join(without_suffix.parts), without_suffix.name})
    return {alias for alias in aliases if alias}


def iter_declared_symbol_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    stripped_text = strip_comments(text)
    entries: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for match in _DECLARATION_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name or symbol_name in seen_names:
            continue
        seen_names.add(symbol_name)
        line_number = _line_number(text, match.start())
        entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_kind": str(match.group("kind") or "").strip().lower(),
                        "symbol_name": symbol_name,
                        "line": line_number,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": str(match.group("kind") or "").strip().lower(),
                "start_line": line_number,
                "end_line": line_number,
                "signature": match.group(0).strip(),
            }
        )
    for match in _PROPERTY_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name or symbol_name in seen_names:
            continue
        seen_names.add(symbol_name)
        line_number = _line_number(text, match.start())
        entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_kind": "property",
                        "symbol_name": symbol_name,
                        "line": line_number,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": "property",
                "start_line": line_number,
                "end_line": line_number,
                "signature": match.group(0).strip(),
            }
        )
    return tuple(entries)


def iter_import_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            str(match.group("kind") or "").strip().lower(),
            str(match.group("target") or "").strip(),
            _line_number(text, match.start()),
        )
        for match in _IMPORT_RE.finditer(stripped_text)
        if str(match.group("target") or "").strip()
    )


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str, int]] = []
    for match in _NEW_REFERENCE_RE.finditer(stripped_text):
        references.append((str(match.group("name")), _line_number(text, match.start())))
    for match in _CALL_REFERENCE_RE.finditer(stripped_text):
        references.append((str(match.group("name")), _line_number(text, match.start())))
    return tuple(references)


def resolve_import_target(
    file_path: str,
    target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_repository_relative_path(str(target or "").strip())
    if not normalized_target or "://" in normalized_target or ":" in normalized_target.split("/", 1)[0]:
        return None
    current_parent = PurePosixPath(file_path).parent
    target_path = PurePosixPath(normalized_target)
    if not target_path.is_absolute():
        target_path = current_parent / target_path
    normalized_path = normalize_repository_relative_path(str(target_path))
    suffix = PurePosixPath(normalized_path).suffix.lower()
    candidates = [normalized_path]
    if suffix not in PKL_SUFFIXES:
        candidates.extend(f"{normalized_path}{candidate_suffix}" for candidate_suffix in sorted(PKL_SUFFIXES))
    return resolve_suffix_match(module_index=module_index, suffixes=candidates)
