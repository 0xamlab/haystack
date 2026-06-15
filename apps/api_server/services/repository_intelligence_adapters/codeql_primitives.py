from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

CODEQL_SOURCE_SUFFIXES = frozenset({".ql", ".qll"})
CODEQL_CONFIG_BASENAMES = frozenset(
    {"qlpack.yml", "qlpack.yaml", "codeql-pack.yml", "codeql-pack.yaml"}
)
_TRIMMED_MODULE_ROOTS = (
    ("ql", "lib"),
    ("ql", "src"),
    ("lib",),
    ("src",),
    ("queries",),
)
_COMMENT_RE = re.compile(r"(?m)//.*?$|/\*.*?\*/", re.S)
_IMPORT_RE = re.compile(
    r"(?im)^\s*(?:private\s+)?import\s+(?P<target>[A-Za-z_][A-Za-z0-9_.]*)\s*$"
)
_DECLARATION_RE = re.compile(
    r"(?im)^\s*(?:private\s+|cached\s+|query\s+|final\s+|abstract\s+)*"
    r"(?P<kind>class|module|predicate|query)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
_CALL_RE = re.compile(r"(?<![.\w])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_QUALIFIED_RE = re.compile(
    r"(?<![\w.])(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
_CONFIG_SIGNAL_RE = re.compile(
    r"(?im)^\s*(?:name|version|library|extractor|dependencies)\s*:"
)
_SOURCE_SIGNAL_RE = re.compile(
    r"(?im)\b(?:import|from|where|select|predicate|class|module)\b"
)
_RESERVED_CALL_NAMES = frozenset(
    {"count", "exists", "forall", "if", "max", "min", "not", "pragma", "select", "sum"}
)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", str(text or ""))


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


def _normalize_path(value: str) -> str:
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


def has_codeql_path_hints(path: Path | PurePosixPath | str) -> bool:
    pure_path = PurePosixPath(path)
    return (
        pure_path.suffix.lower() in CODEQL_SOURCE_SUFFIXES
        or pure_path.name.lower() in CODEQL_CONFIG_BASENAMES
    )


def is_probable_codeql_config(*, path: Path | PurePosixPath, text: str) -> bool:
    pure_path = PurePosixPath(path)
    if pure_path.name.lower() not in CODEQL_CONFIG_BASENAMES or not text or _looks_binaryish(text):
        return False
    return bool(_CONFIG_SIGNAL_RE.search(text))


def is_probable_codeql_source(*, path: Path | PurePosixPath, text: str) -> bool:
    pure_path = PurePosixPath(path)
    if pure_path.suffix.lower() not in CODEQL_SOURCE_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text).strip()
    if not stripped_text:
        return False
    return bool(_SOURCE_SIGNAL_RE.search(stripped_text))


def _trimmed_module_parts(file_path: str) -> tuple[str, ...]:
    parts = tuple(PurePosixPath(file_path).with_suffix("").parts)
    lowered_parts = tuple(part.lower() for part in parts)
    for root_parts in _TRIMMED_MODULE_ROOTS:
        root_size = len(root_parts)
        for index in range(len(lowered_parts) - root_size + 1):
            if lowered_parts[index : index + root_size] == root_parts:
                trimmed_parts = parts[index + root_size :]
                if trimmed_parts:
                    return trimmed_parts
    return parts


def module_name_from_path(file_path: str) -> str:
    parts = _trimmed_module_parts(_normalize_path(file_path))
    return ".".join(parts) if parts else PurePosixPath(file_path).stem


def path_aliases_for_file(file_path: str) -> set[str]:
    normalized_path = _normalize_path(file_path)
    pure_path = PurePosixPath(normalized_path)
    without_suffix = pure_path.with_suffix("")
    trimmed_parts = _trimmed_module_parts(normalized_path)
    aliases = {
        normalized_path,
        str(without_suffix),
        pure_path.name,
        without_suffix.name,
        ".".join(without_suffix.parts),
        module_name_from_path(normalized_path),
        ".".join(trimmed_parts),
        "/".join(trimmed_parts),
    }
    return {alias for alias in aliases if alias}


def iter_declared_symbol_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    stripped_text = strip_comments(text)
    entries: list[dict[str, object]] = []
    for match in _DECLARATION_RE.finditer(stripped_text):
        kind = str(match.group("kind") or "").strip().lower()
        name = str(match.group("name") or "").strip()
        if not kind or not name:
            continue
        line_number = _line_number(stripped_text, match.start())
        entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_kind": kind,
                        "symbol_name": name,
                        "line": line_number,
                    },
                ),
                "symbol_name": name,
                "symbol_kind": kind,
                "start_line": line_number,
                "end_line": line_number,
                "signature": match.group(0).strip(),
            }
        )
    return tuple(entries)


def iter_import_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (str(match.group("target") or "").strip(), _line_number(stripped_text, match.start()))
        for match in _IMPORT_RE.finditer(stripped_text)
        if str(match.group("target") or "").strip()
    )


def iter_reference_entries(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str | None, str, int]] = []
    seen: set[tuple[str | None, str, int]] = set()
    for match in _QUALIFIED_RE.finditer(stripped_text):
        item = (
            str(match.group("owner") or "").strip() or None,
            str(match.group("name") or "").strip(),
            _line_number(stripped_text, match.start()),
        )
        if item[1] and item not in seen:
            seen.add(item)
            references.append(item)
    for match in _CALL_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        if not name or name in _RESERVED_CALL_NAMES:
            continue
        item = (None, name, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            references.append(item)
    return tuple(references)


def resolve_import(
    file_path: str,
    target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return None
    direct_target = module_index.get(normalized_target)
    if direct_target:
        return direct_target
    path_target = normalize_repository_relative_path(normalized_target.replace(".", "/"))
    if path_target in module_index:
        return module_index[path_target]
    candidate_paths = [path_target]
    candidate_paths.extend(
        f"{path_target}{suffix}" for suffix in sorted(CODEQL_SOURCE_SUFFIXES)
    )
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_paths)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = _normalize_path(file_path)
    aliases = path_aliases_for_file(normalized_path)
    absolute_path = root_path / normalized_path
    try:
        text = absolute_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return aliases
    pure_path = PurePosixPath(normalized_path)
    if pure_path.name.lower() in CODEQL_CONFIG_BASENAMES:
        return aliases
    if not is_probable_codeql_source(path=Path(normalized_path), text=text):
        return aliases
    for entry in iter_declared_symbol_entries(
        text=text,
        file_path=normalized_path,
        stable_identifier=lambda _kind, _payload: "",
    ):
        aliases.add(str(entry["symbol_name"]))
    return {alias for alias in aliases if alias}


def source_symbol_name_for_line(
    symbol_entries: Iterable[dict[str, object]],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for entry in symbol_entries:
        symbol_line = int(entry.get("start_line") or 0)
        if symbol_line <= line_number:
            current_name = str(entry.get("symbol_name") or "")
    return current_name or None
