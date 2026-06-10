from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

QSHARP_SUFFIXES = frozenset({".qs"})
QSHARP_CONFIG_BASENAMES = frozenset({"qsharp.json"})
_COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
_NAMESPACE_RE = re.compile(
    r"(?mi)^\s*(?:\ufeff)?namespace\s+(?P<name>[A-Za-z_][A-Za-z0-9_.]*)\s*(?:\{|;)"
)
_OPEN_RE = re.compile(
    r"(?mi)^\s*open\s+(?P<target>[A-Za-z_][A-Za-z0-9_.]*)(?:\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?\s*;"
)
_SYMBOL_RE = re.compile(
    r"(?mi)^\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:internal\s+)?(?P<kind>operation|function|newtype)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<qualifier>[A-Z][A-Za-z0-9_]*)\.(?P<name>[A-Z][A-Za-z0-9_]*)\b"
)
_UNQUALIFIED_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_]*)\b")
_REFERENCE_SKIP_PREFIXES = (
    "namespace ",
    "open ",
    "operation ",
    "function ",
    "newtype ",
    "internal operation ",
    "internal function ",
    "internal newtype ",
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "Adj",
        "BigInt",
        "Bool",
        "Controlled",
        "Ctl",
        "Double",
        "Fail",
        "False",
        "Int",
        "LittleEndian",
        "One",
        "Pauli",
        "Qubit",
        "QubitArray",
        "Range",
        "Result",
        "Unit",
        "Zero",
        "borrow",
        "body",
        "controlled",
        "distribute",
        "for",
        "if",
        "import",
        "internal",
        "in",
        "is",
        "let",
        "mutable",
        "namespace",
        "newtype",
        "open",
        "operation",
        "repeat",
        "return",
        "set",
        "until",
        "use",
        "while",
        "within",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text).replace("\ufeff", "")


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_qsharp_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in QSHARP_SUFFIXES
        or normalized_path.name.lower() in QSHARP_CONFIG_BASENAMES
    )


def is_probable_qsharp_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in QSHARP_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return _NAMESPACE_RE.search(stripped_text) is not None or _SYMBOL_RE.search(stripped_text) is not None


def is_probable_qsharp_config(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.name.lower() not in QSHARP_CONFIG_BASENAMES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text).strip()
    return stripped_text.startswith("{") and stripped_text.endswith("}")


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def primary_namespace_name(text: str, *, file_path: str) -> str:
    entries = iter_namespace_entries(text)
    if entries:
        return entries[0][0]
    return module_name_from_path(file_path)


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
    direct_match = module_index.get(cleaned_target)
    if direct_match is not None:
        return direct_match
    namespace_path = normalize_repository_relative_path(cleaned_target.replace(".", "/"))
    if namespace_path:
        direct_match = module_index.get(namespace_path)
        if direct_match is not None:
            return direct_match
        dotted_path = module_index.get(namespace_path.replace("/", "."))
        if dotted_path is not None:
            return dotted_path
        suffix_match = resolve_suffix_match(
            module_index=module_index,
            suffixes=tuple(
                f"{namespace_path}{suffix}" for suffix in sorted(QSHARP_SUFFIXES)
            ),
        )
        if suffix_match is not None:
            return suffix_match
    current_dir = PurePosixPath(current_file).parent
    candidate_path = normalize_repository_relative_path(current_dir / cleaned_target)
    if candidate_path is None:
        return None
    direct_match = module_index.get(candidate_path)
    if direct_match is not None:
        return direct_match
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(f"{candidate_path}{suffix}" for suffix in sorted(QSHARP_SUFFIXES)),
    )


def iter_namespace_entries(text: str) -> tuple[tuple[str, int], ...]:
    entries: list[tuple[str, int]] = []
    for match in _NAMESPACE_RE.finditer(strip_comments(text)):
        name = normalize_identifier(match.group("name") or "")
        if not name:
            continue
        entries.append((name, strip_comments(text).count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, str | None, int]] = []
    for match in _OPEN_RE.finditer(stripped_text):
        target = clean_import_target(match.group("target") or "")
        alias = normalize_identifier(match.group("alias") or "") or None
        if not target:
            continue
        entries.append(("opens", target, alias, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _SYMBOL_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        kind = normalize_identifier(match.group("kind") or "")
        if not name or not kind or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, kind.lower(), stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str | None, str, int]] = []
    seen_entries: set[tuple[str | None, str, int]] = set()
    declaration_lines = {
        line_number for _symbol_name, _symbol_kind, line_number in iter_symbol_entries(text)
    }
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if (
            not stripped_line
            or line_number in declaration_lines
            or any(stripped_line.startswith(prefix) for prefix in _REFERENCE_SKIP_PREFIXES)
        ):
            continue
        for match in _QUALIFIED_REFERENCE_RE.finditer(stripped_line):
            qualifier = normalize_identifier(match.group("qualifier") or "")
            name = normalize_identifier(match.group("name") or "")
            if not qualifier or not name or name in _RESERVED_REFERENCE_NAMES:
                continue
            entry = (qualifier, name, line_number)
            if entry not in seen_entries:
                seen_entries.add(entry)
                entries.append(entry)
        for match in _UNQUALIFIED_REFERENCE_RE.finditer(stripped_line):
            name = normalize_identifier(match.group("name") or "")
            if (
                not name
                or name in _RESERVED_REFERENCE_NAMES
                or name in {entry_name for _qualifier, entry_name, _line in entries if _line == line_number}
            ):
                continue
            start = match.start()
            if start > 0 and stripped_line[start - 1] == ".":
                continue
            entry = (None, name, line_number)
            if entry not in seen_entries:
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
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    if normalized_path.name.lower() in QSHARP_CONFIG_BASENAMES:
        aliases.add("qsharp")
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    module_name = primary_namespace_name(text, file_path=file_path)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "qsharp"},
            ),
            symbol_name=module_name,
            symbol_kind="qsharp",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"qsharp {module_name}".strip(),
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
    symbol_entries: Iterable[tuple[str, str, int]],
    *,
    line_number: int,
) -> str | None:
    active_name: str | None = None
    active_line = -1
    for symbol_name, _symbol_kind, start_line in symbol_entries:
        if start_line <= line_number and start_line >= active_line:
            active_name = symbol_name
            active_line = start_line
    return active_name
