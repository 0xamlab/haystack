from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]

QMAKE_SUFFIXES = frozenset({".pro", ".pri", ".prf"})
QMAKE_CONFIG_BASENAMES = frozenset({"qmake.conf"})
_SIGNAL_VARIABLES = frozenset(
    {
        "CONFIG",
        "HEADERS",
        "QT",
        "SOURCES",
        "SUBDIRS",
        "TARGET",
        "TEMPLATE",
    }
)
_ASSIGNMENT_RE = re.compile(
    r"(?im)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\s*(?P<op>\+=|-=|\*=|~=|=)\s*(?P<value>.+?)\s*$"
)
_INCLUDE_RE = re.compile(r"(?im)\binclude\s*\(\s*(?P<target>[^)]+?)\s*\)")
_LOAD_RE = re.compile(r"(?im)\bload\s*\(\s*(?P<target>[^)]+?)\s*\)")
_TOKEN_RE = re.compile(r"""(?P<quoted>['"][^'"]+['"])|(?P<token>[^\s]+)""")
_TARGET_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:+-]*$")
_PATH_TOKEN_RE = re.compile(r"[\\/]|(?:\.pro|\.pri|\.prf)$", re.IGNORECASE)


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        in_quote: str | None = None
        escaped = False
        result: list[str] = []
        for char in raw_line:
            if char in {'"', "'"} and not escaped:
                in_quote = None if in_quote == char else char
            if char == "#" and in_quote is None:
                break
            result.append(char)
            escaped = char == "\\" and not escaped
        lines.append("".join(result))
    return "\n".join(lines)


def normalize_continuations(text: str) -> str:
    normalized = strip_comments(text)
    while "\\\n" in normalized:
        normalized = normalized.replace("\\\n", " ")
    return normalized


def has_qmake_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in QMAKE_SUFFIXES
        or normalized_path.name.lower() in QMAKE_CONFIG_BASENAMES
    )


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _normalize_token(raw_value: str) -> str:
    return str(raw_value or "").strip().strip('"').strip("'").replace("\\", "/")


def _iter_tokens(raw_value: str) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()
    for match in _TOKEN_RE.finditer(str(raw_value or "")):
        token = _normalize_token(str(match.group("quoted") or match.group("token") or ""))
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)
    return tuple(tokens)


def _is_symbol_name(candidate: str) -> bool:
    normalized = _normalize_token(candidate)
    return (
        bool(normalized)
        and "$" not in normalized
        and _PATH_TOKEN_RE.search(normalized) is None
        and _TARGET_NAME_RE.match(normalized) is not None
    )


def _is_path_like(candidate: str) -> bool:
    normalized = _normalize_token(candidate)
    return bool(normalized) and "$" not in normalized and _PATH_TOKEN_RE.search(normalized) is not None


def _subdir_label_for_token(token: str) -> str | None:
    normalized = _normalize_token(token)
    if not normalized or "$" in normalized:
        return None
    path = PurePosixPath(normalized)
    label = path.stem if path.suffix.lower() in QMAKE_SUFFIXES else path.name
    return label if _is_symbol_name(label) else None


def iter_assignment_entries(text: str) -> tuple[tuple[str, str, str, int], ...]:
    normalized_text = normalize_continuations(text)
    entries: list[tuple[str, str, str, int]] = []
    seen: set[tuple[str, str, str, int]] = set()
    for match in _ASSIGNMENT_RE.finditer(normalized_text):
        item = (
            str(match.group("name") or "").strip(),
            str(match.group("op") or "").strip(),
            str(match.group("value") or "").strip(),
            _line_number(normalized_text, match.start()),
        )
        if item[0] and item[2] and item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def is_probable_qmake_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_qmake_path_hints(path):
        return False
    normalized_text = normalize_continuations(text)
    return any(
        assignment_name.split(".", 1)[0].upper() in _SIGNAL_VARIABLES
        or assignment_name.lower().endswith((".depends", ".file", ".subdir"))
        for assignment_name, _op, _value, _line in iter_assignment_entries(normalized_text)
    ) or bool(_INCLUDE_RE.search(normalized_text) or _LOAD_RE.search(normalized_text))


def iter_include_targets(text: str) -> tuple[tuple[str, int], ...]:
    normalized_text = normalize_continuations(text)
    includes: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _INCLUDE_RE.finditer(normalized_text):
        target = _normalize_token(str(match.group("target") or ""))
        if not target or "$" in target:
            continue
        item = (target, _line_number(normalized_text, match.start()))
        if item not in seen:
            seen.add(item)
            includes.append(item)
    return tuple(includes)


def iter_load_targets(text: str) -> tuple[tuple[str, int], ...]:
    normalized_text = normalize_continuations(text)
    loads: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _LOAD_RE.finditer(normalized_text):
        target = _normalize_token(str(match.group("target") or ""))
        if not _is_symbol_name(target):
            continue
        item = (target, _line_number(normalized_text, match.start()))
        if item not in seen:
            seen.add(item)
            loads.append(item)
    return tuple(loads)


def iter_subdir_entries(text: str) -> tuple[tuple[str, str | None, tuple[str, ...], int], ...]:
    specs: dict[str, dict[str, Any]] = {}
    for name, _op, raw_value, line_number in iter_assignment_entries(text):
        upper_name = name.upper()
        if upper_name == "SUBDIRS":
            for token in _iter_tokens(raw_value):
                label = _subdir_label_for_token(token)
                if label is None:
                    continue
                spec = specs.setdefault(label, {"path": None, "depends": [], "line": line_number})
                if spec["path"] is None and _is_path_like(token):
                    spec["path"] = token
                spec["line"] = min(int(spec["line"]), line_number)
            continue
        if "." not in name:
            continue
        label, property_name = name.split(".", 1)
        if not _is_symbol_name(label):
            continue
        property_name = property_name.lower()
        spec = specs.setdefault(label, {"path": None, "depends": [], "line": line_number})
        spec["line"] = min(int(spec["line"]), line_number)
        if property_name in {"file", "subdir"}:
            candidate_path = _normalize_token(raw_value)
            if candidate_path and "$" not in candidate_path:
                spec["path"] = candidate_path
            continue
        if property_name != "depends":
            continue
        seen_dependencies = set(spec["depends"])
        for token in _iter_tokens(raw_value):
            if not _is_symbol_name(token) or token in seen_dependencies:
                continue
            seen_dependencies.add(token)
            spec["depends"].append(token)
    return tuple(
        sorted(
            (
                (label, spec["path"], tuple(spec["depends"]), int(spec["line"]))
                for label, spec in specs.items()
            ),
            key=lambda item: (item[3], item[0]),
        )
    )


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for name, _op, raw_value, line_number in iter_assignment_entries(text):
        if name.upper() != "TARGET":
            continue
        target_name = _normalize_token(raw_value)
        if not _is_symbol_name(target_name):
            continue
        item = (target_name, "target", line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    for label, _path, _depends, line_number in iter_subdir_entries(text):
        item = (label, "subdir", line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_reference_names(text: str) -> tuple[tuple[str, str, int], ...]:
    references: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for source_name, _path, dependency_names, line_number in iter_subdir_entries(text):
        for dependency_name in dependency_names:
            item = (source_name, dependency_name, line_number)
            if item not in seen:
                seen.add(item)
                references.append(item)
    return tuple(references)
