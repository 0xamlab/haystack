from __future__ import annotations

import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]

QML_SUFFIXES = frozenset({".qml"})
QML_CONFIG_BASENAMES = frozenset({"qmldir"})
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_OR_STRING_RE = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*'
)
_IMPORT_RE = re.compile(
    r"""(?im)^\s*import\s+(?P<target>"[^"]+"|'[^']+'|[A-Za-z_][A-Za-z0-9_.]*)"""
    r"""(?:\s+(?P<version>\d+(?:\.\d+)?))?(?:\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?\s*$"""
)
_ROOT_COMPONENT_RE = re.compile(
    r"(?m)^(?P<indent>\s*)(?P<name>[A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)*)\s*\{"
)
_ID_RE = re.compile(r"(?m)^\s*id\s*:\s*(?P<name>[a-z_][A-Za-z0-9_]*)\b")
_FUNCTION_RE = re.compile(r"(?m)^\s*function\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_SIGNAL_RE = re.compile(r"(?m)^\s*signal\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_PROPERTY_RE = re.compile(
    r"(?m)^\s*(?:(?:default|required|readonly)\s+)*property\s+"
    r"(?:list<[^>]+>|[A-Za-z_][A-Za-z0-9_<>.]*)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_FUNCTION_CALL_RE = re.compile(
    r"(?m)(?<!\bfunction\s)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*\("
)
_PROPERTY_ACCESS_RE = re.compile(
    r"(?m)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*\."
)
_QMLDIR_MODULE_RE = re.compile(r"(?im)^\s*module\s+(?P<name>[A-Za-z0-9_.]+)\s*$")
_QMLDIR_EXPORT_RE = re.compile(
    r"(?im)^\s*(?:singleton\s+)?(?P<name>[A-Z][A-Za-z0-9_]*)\s+\d+(?:\.\d+)?\s+(?P<path>[^\s#]+\.qml)\s*$"
)
_IGNORED_REFERENCE_NAMES = frozenset(
    {
        "alias",
        "catch",
        "console",
        "else",
        "finally",
        "for",
        "function",
        "if",
        "import",
        "onCompleted",
        "property",
        "return",
        "signal",
        "switch",
        "while",
    }
)


@lru_cache(maxsize=1024)
def _strip_comments_cached(text: str) -> str:
    if "//" not in text and "/*" not in text and "#" not in text:
        return text
    normalized = _BLOCK_COMMENT_RE.sub("", text)
    lines: list[str] = []
    for raw_line in normalized.splitlines():
        if raw_line.lstrip().startswith("#"):
            lines.append("")
            continue
        lines.append(
            _LINE_COMMENT_OR_STRING_RE.sub(
                lambda match: (
                    match.group(0)
                    if match.group(0).startswith(('"', "'"))
                    else ""
                ),
                raw_line,
            )
        )
    return "\n".join(lines)


def strip_comments(text: str) -> str:
    return _strip_comments_cached(text)


def has_qml_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in QML_SUFFIXES
        or normalized_path.name.lower() in QML_CONFIG_BASENAMES
    )


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _normalize_token(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").replace("\\", "/")


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return tuple(ordered)


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if path.suffix.lower() == ".qml":
        return path.stem
    if path.name.lower() in QML_CONFIG_BASENAMES:
        return path.parent.name or "qml"
    return path.name


def iter_qmldir_module_names(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    modules: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _QMLDIR_MODULE_RE.finditer(stripped_text):
        item = (
            str(match.group("name") or "").strip(),
            _line_number(stripped_text, match.start()),
        )
        if item[0] and item not in seen:
            seen.add(item)
            modules.append(item)
    return tuple(modules)


def iter_qmldir_exports(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    exports: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _QMLDIR_EXPORT_RE.finditer(stripped_text):
        item = (
            str(match.group("name") or "").strip(),
            _normalize_token(str(match.group("path") or "")),
            _line_number(stripped_text, match.start()),
        )
        if item[0] and item[1] and item not in seen:
            seen.add(item)
            exports.append(item)
    return tuple(exports)


def is_probable_qml_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_qml_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    normalized_path = PurePosixPath(path)
    if normalized_path.name.lower() in QML_CONFIG_BASENAMES:
        return bool(iter_qmldir_module_names(stripped_text) or iter_qmldir_exports(stripped_text))
    return bool(
        _IMPORT_RE.search(stripped_text)
        or _ROOT_COMPONENT_RE.search(stripped_text)
        or _ID_RE.search(stripped_text)
        or _FUNCTION_RE.search(stripped_text)
        or _SIGNAL_RE.search(stripped_text)
        or _PROPERTY_RE.search(stripped_text)
    )


def iter_import_entries(text: str) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str | None, int]] = []
    seen: set[tuple[str, str | None, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        target = _normalize_token(str(match.group("target") or ""))
        alias = str(match.group("alias") or "").strip() or None
        if not target:
            continue
        item = (target, alias, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str, *, path: Path | PurePosixPath) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    normalized_path = PurePosixPath(path)
    symbols: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    if normalized_path.name.lower() in QML_CONFIG_BASENAMES:
        for module_name, line_number in iter_qmldir_module_names(stripped_text):
            item = (module_name, "module", line_number)
            if item not in seen:
                seen.add(item)
                symbols.append(item)
        for export_name, _export_path, line_number in iter_qmldir_exports(stripped_text):
            item = (export_name, "component", line_number)
            if item not in seen:
                seen.add(item)
                symbols.append(item)
        return tuple(symbols)
    for pattern, symbol_kind in (
        (_ID_RE, "id"),
        (_FUNCTION_RE, "function"),
        (_SIGNAL_RE, "signal"),
        (_PROPERTY_RE, "property"),
    ):
        for match in pattern.finditer(stripped_text):
            item = (
                str(match.group("name") or "").strip(),
                symbol_kind,
                _line_number(stripped_text, match.start()),
            )
            if item[0] and item not in seen:
                seen.add(item)
                symbols.append(item)
    return tuple(symbols)


def iter_reference_names(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for pattern in (_ROOT_COMPONENT_RE, _FUNCTION_CALL_RE, _PROPERTY_ACCESS_RE):
        for match in pattern.finditer(stripped_text):
            target_name = str(match.group("name") or "").strip()
            if not target_name:
                continue
            leaf_name = target_name.rsplit(".", 1)[-1]
            if leaf_name in _IGNORED_REFERENCE_NAMES or target_name in _IGNORED_REFERENCE_NAMES:
                continue
            item = (target_name, _line_number(stripped_text, match.start()))
            if item not in seen:
                seen.add(item)
                references.append(item)
    return tuple(references)
