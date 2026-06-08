from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

OPENQASM_SUFFIXES = frozenset({".qasm"})
_COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
_DIRECTIVE_RE = re.compile(
    r"(?mi)^\s*(?:OPENQASM\b|include\b|gate\b|def\b|defcal\b|extern\b|qubit\b|bit\b|measure\b)"
)
_INCLUDE_RE = re.compile(r'(?mi)^\s*include\s+"(?P<target>[^"]+)"\s*;')
_GATE_SYMBOL_RE = re.compile(r"(?mi)^\s*gate\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_CALLABLE_SYMBOL_RE = re.compile(
    r"(?mi)^\s*(?P<kind>def|defcal|extern)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_REGISTER_SYMBOL_RE = re.compile(
    r"(?mi)^\s*(?P<kind>qubit|bit)\s*(?:\[\s*[^]]+\s*\])?\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_OPERATION_PREFIX_RE = re.compile(
    r"^(?:(?:ctrl|negctrl)\s*(?:@\s*\([^)]*\))?\s*@\s*|inv\s*@\s*|pow\s*\([^)]*\)\s*@\s*|box\s+)*"
)
_OPERATION_TARGET_RE = re.compile(r"^(?P<target>[A-Za-z_][A-Za-z0-9_]*)\b")
_ASSIGNMENT_TARGET_RE = re.compile(r"^(?:let|const)?\s*[A-Za-z_][A-Za-z0-9_]*(?:\[[^]]+\])?\s*=\s*")
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "OPENQASM",
        "angle",
        "array",
        "barrier",
        "bit",
        "bool",
        "box",
        "break",
        "const",
        "continue",
        "creg",
        "def",
        "defcal",
        "defcalgrammar",
        "delay",
        "duration",
        "end",
        "extern",
        "float",
        "for",
        "gate",
        "gphase",
        "if",
        "include",
        "input",
        "int",
        "inv",
        "let",
        "measure",
        "output",
        "pow",
        "qreg",
        "qubit",
        "readonly",
        "reset",
        "return",
        "stretch",
        "uint",
        "while",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_openqasm_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in OPENQASM_SUFFIXES


def is_probable_openqasm_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).suffix.lower() not in OPENQASM_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return _DIRECTIVE_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def clean_import_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if "://" in cleaned:
        return ""
    return cleaned


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    cleaned_target = clean_import_target(import_target)
    if not cleaned_target:
        return None
    candidate_path = PurePosixPath(cleaned_target)
    current_dir = PurePosixPath(current_file).parent
    normalized_candidate = normalize_repository_relative_path(
        candidate_path if candidate_path.is_absolute() else current_dir / candidate_path
    )
    if not normalized_candidate:
        return None
    direct_match = module_index.get(normalized_candidate)
    if direct_match is not None:
        return direct_match
    suffixes = (
        (normalized_candidate,)
        if PurePosixPath(normalized_candidate).suffix.lower() in OPENQASM_SUFFIXES
        else tuple(f"{normalized_candidate}{suffix}" for suffix in sorted(OPENQASM_SUFFIXES))
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    for match in _INCLUDE_RE.finditer(strip_comments(text)):
        target = clean_import_target(match.group("target") or "")
        if not target:
            continue
        line_number = text.count("\n", 0, match.start()) + 1
        entries.append(("includes", target, line_number))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for pattern, default_kind in (
        (_GATE_SYMBOL_RE, "gate"),
        (_CALLABLE_SYMBOL_RE, None),
        (_REGISTER_SYMBOL_RE, None),
    ):
        for match in pattern.finditer(stripped_text):
            name = normalize_identifier(match.group("name") or "")
            kind = normalize_identifier(match.groupdict().get("kind") or default_kind or "symbol")
            if not name or not kind or name in seen_names:
                continue
            seen_names.add(name)
            entries.append((name, kind.lower(), stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def _operation_target_for_line(raw_line: str) -> str:
    stripped_line = raw_line.strip()
    if not stripped_line or stripped_line.startswith("{") or stripped_line.startswith("}"):
        return ""
    if stripped_line.endswith(":"):
        return ""
    if not stripped_line.endswith(";"):
        return ""
    statement = stripped_line[:-1].strip()
    if not statement:
        return ""
    statement = _ASSIGNMENT_TARGET_RE.sub("", statement)
    statement = _OPERATION_PREFIX_RE.sub("", statement)
    match = _OPERATION_TARGET_RE.match(statement)
    return normalize_identifier(match.group("target") or "") if match else ""


def iter_operation_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(strip_comments(text).splitlines(), start=1):
        target_name = _operation_target_for_line(raw_line)
        if not target_name or target_name in _RESERVED_REFERENCE_NAMES:
            continue
        entry = (target_name, line_number)
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
    del root_path, stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in OPENQASM_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    module_name = module_name_from_path(file_path)
    line_count = _line_count(text)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "openqasm"},
            ),
            symbol_name=module_name,
            symbol_kind="openqasm",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"openqasm {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": symbol_name, "kind": symbol_kind},
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, str, int]],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line <= line_number:
            current_name = symbol_name
    return current_name
