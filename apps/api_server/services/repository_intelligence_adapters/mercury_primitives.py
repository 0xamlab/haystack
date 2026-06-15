from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

MERCURY_SUFFIXES = frozenset({".m"})
_COMMON_MODULE_ROOTS = frozenset({"compiler", "library", "samples", "src", "test", "tests"})
_LINE_COMMENT_RE = re.compile(r"(?m)%.*$")
_MODULE_RE = re.compile(r"(?m)^\s*:-\s*module\s+(?P<name>[a-z][A-Za-z0-9_.]*)\s*\.")
_IMPORT_RE = re.compile(
    r"(?m)^\s*:-\s*(?:import_module|use_module)\s+(?P<modules>[a-z][A-Za-z0-9_.,\s]*)\s*\."
)
_PRED_RE = re.compile(r"(?m)^\s*:-\s*pred\s+(?P<name>[a-z][A-Za-z0-9_]*)\b")
_FUNC_RE = re.compile(r"(?m)^\s*:-\s*func\s+(?P<name>[a-z][A-Za-z0-9_]*)\b")
_TYPE_RE = re.compile(r"(?m)^\s*:-\s*type\s+(?P<name>[a-z][A-Za-z0-9_]*)\b")
_QUALIFIED_REFERENCE_RE = re.compile(
    r"(?P<module>[a-z][A-Za-z0-9_.]*)\.(?P<name>[a-z][A-Za-z0-9_]*)\s*(?=\()"
)
_REFERENCE_RE = re.compile(r"(?<![\w.])(?P<name>[a-z][A-Za-z0-9_]*)\s*(?=\()")
_PROBABLE_DIRECTIVE_RE = re.compile(
    r"(?m)^\s*:-\s*(?:module|interface|implementation|pred|func|type|import_module|use_module|mode|inst|typeclass)\b"
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "all",
        "catch",
        "cc_multi",
        "cc_nondet",
        "det",
        "else",
        "fail",
        "if",
        "impure",
        "is",
        "multi",
        "nondet",
        "not",
        "promise",
        "semidet",
        "semipure",
        "some",
        "then",
        "true",
        "try",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t\f"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _LINE_COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip(".")


def has_mercury_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in MERCURY_SUFFIXES


def declared_module_name(text: str) -> str | None:
    match = _MODULE_RE.search(strip_comments(text))
    if match is None:
        return None
    name = normalize_identifier(match.group("name") or "")
    return name or None


def is_probable_mercury_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_mercury_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if declared_module_name(stripped_text):
        return True
    return len(_PROBABLE_DIRECTIVE_RE.findall(stripped_text)) >= 2


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.stem


def effective_module_name(*, file_path: str, text: str) -> str:
    declared_name = declared_module_name(text)
    return declared_name or module_name_from_path(file_path)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        modules = str(match.group("modules") or "")
        for raw_module in modules.split(","):
            module_name = normalize_identifier(raw_module)
            if not module_name:
                continue
            entry = (module_name, line_number)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append((module_name, "imports", line_number))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for pattern, kind in ((_PRED_RE, "pred"), (_FUNC_RE, "func"), (_TYPE_RE, "type")):
        for match in pattern.finditer(stripped_text):
            name = normalize_identifier(match.group("name") or "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            entries.append((name, kind, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(sorted(entries, key=lambda entry: (entry[2], entry[0])))


def iter_reference_entries(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str | None, str, int]] = []
    seen_entries: set[tuple[str | None, str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(":-"):
            continue
        if ":-" in line:
            _head, tail = line.split(":-", 1)
            line = tail
        for match in _QUALIFIED_REFERENCE_RE.finditer(line):
            module_name = normalize_identifier(match.group("module") or "")
            name = normalize_identifier(match.group("name") or "")
            if not module_name or not name or name in _RESERVED_REFERENCE_NAMES:
                continue
            entry = (module_name, name, line_number)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append(entry)
        unqualified_line = _QUALIFIED_REFERENCE_RE.sub("", line)
        for match in _REFERENCE_RE.finditer(unqualified_line):
            name = normalize_identifier(match.group("name") or "")
            if not name or name in _RESERVED_REFERENCE_NAMES:
                continue
            entry = (None, name, line_number)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append(entry)
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in MERCURY_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    try:
        text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    module_name = effective_module_name(file_path=file_path, text=text)
    if module_name:
        aliases.add(module_name)
    for symbol_name, _kind, _line in iter_symbol_entries(text):
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    module_name = effective_module_name(file_path=file_path, text=text)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "mercury"},
            ),
            symbol_name=module_name,
            symbol_kind="mercury",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"mercury {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "kind": symbol_kind,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"{symbol_kind} {symbol_name}".strip(),
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line > line_number:
            break
        current_name = symbol_name
    return current_name
