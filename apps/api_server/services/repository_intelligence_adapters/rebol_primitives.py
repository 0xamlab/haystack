from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

REBOL_SUFFIXES = frozenset({".r", ".r3", ".reb", ".rebol"})
UNAMBIGUOUS_REBOL_SUFFIXES = frozenset({".r3", ".reb", ".rebol"})
_COMMON_MODULE_ROOTS = frozenset(
    {
        "app",
        "apps",
        "benchmark",
        "benchmarks",
        "doc",
        "docs",
        "example",
        "examples",
        "lib",
        "libs",
        "plugin",
        "plugins",
        "protocol",
        "protocols",
        "script",
        "scripts",
        "src",
        "test",
        "test-framework",
        "tests",
    }
)
_HEADER_FIELD_NAMES = (
    "author",
    "created",
    "date",
    "exports",
    "file",
    "license",
    "name",
    "needs",
    "notes",
    "options",
    "purpose",
    "rights",
    "system",
    "title",
    "to-do",
    "type",
    "version",
)
_LINE_COMMENT_RE = re.compile(r"(?m);.*$")
_TOKEN_RE = r"[A-Za-z_~*+=?!<>-][A-Za-z0-9_~*+=?!<>-]*"
_DO_IMPORT_RE = re.compile(
    rf"(?mi)^\s*(?:(?P<binding>{_TOKEN_RE})\s*:\s*)?do\s+%(?P<target>[^\s\]]+)"
)
_NEEDS_RE = re.compile(r"(?is)\bNeeds:\s*\[(?P<body>.*?)\]")
_SYMBOL_RE = re.compile(
    rf"(?mi)^\s*(?P<name>{_TOKEN_RE})\s*:\s*(?P<kind>func|function|funct|does|has|context|object|make\s+object!)\b"
)
_REFERENCE_RE = re.compile(rf"(?<![%'])\b(?P<name>{_TOKEN_RE})\b")
_PROBABLE_SOURCE_RE = re.compile(
    rf"(?mi)^\s*rebol\s*\[|^\s*(?:{_TOKEN_RE})\s*:\s*(?:func|function|funct|does|has|context|object|make\s+object!)\b|^\s*do\s+%|\bNeeds:\s*\["
)
_HEADER_FIELD_LINE_RE = re.compile(
    r"(?mi)^\s*(?:"
    + "|".join(re.escape(name) for name in _HEADER_FIELD_NAMES)
    + r")\s*:"
)
_BINARYISH_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0e-\x1f]")
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "Author",
        "Created",
        "Date",
        "Exports",
        "File",
        "License",
        "Name",
        "Needs",
        "Notes",
        "Options",
        "Purpose",
        "REBOL",
        "Rebol",
        "Rights",
        "System",
        "Title",
        "Type",
        "Version",
        "all",
        "any",
        "attempt",
        "break",
        "case",
        "compose",
        "context",
        "copy",
        "do",
        "does",
        "either",
        "else",
        "exit",
        "false",
        "for",
        "forall",
        "foreach",
        "func",
        "function",
        "funct",
        "get",
        "has",
        "if",
        "load",
        "local",
        "make",
        "none",
        "object",
        "object!",
        "parse",
        "reduce",
        "repeat",
        "return",
        "self",
        "switch",
        "to",
        "true",
        "unless",
        "until",
        "use",
        "while",
        "write",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = len(_BINARYISH_CONTROL_RE.findall(sample))
    return control_count > max(2, len(sample) // 32)


def _coalesced_binaryish(text: str, binaryish: bool | None = None) -> bool:
    return _looks_binaryish(text) if binaryish is None else binaryish


def strip_comments(text: str) -> str:
    return _LINE_COMMENT_RE.sub("", text)


def _coalesced_stripped_text(text: str, stripped_text: str | None = None) -> str:
    return strip_comments(text) if stripped_text is None else stripped_text


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip().lstrip("%").lstrip("'")


def clean_import_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if not cleaned or "://" in cleaned:
        return ""
    return cleaned


def has_rebol_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in REBOL_SUFFIXES


def is_probable_rebol_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
    binaryish: bool | None = None,
) -> bool:
    if not has_rebol_path_hints(path) or not text or _coalesced_binaryish(text, binaryish):
        return False
    stripped_text = _coalesced_stripped_text(text, stripped_text)
    if not stripped_text.strip():
        return False
    return _PROBABLE_SOURCE_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.stem


def candidate_module_keys(
    base_path: str,
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_base = normalize_repository_relative_path(base_path)
    if not normalized_base:
        return ()
    suffix = PurePosixPath(normalized_base).suffix.lower()
    if suffix in REBOL_SUFFIXES:
        without_suffix = normalize_repository_relative_path(
            str(PurePosixPath(normalized_base).with_suffix(""))
        )
        return tuple(candidate for candidate in (normalized_base, without_suffix) if candidate)
    return tuple(
        dict.fromkeys(
            (
                normalized_base,
                f"{normalized_base}.reb",
                f"{normalized_base}.r3",
                f"{normalized_base}.rebol",
                f"{normalized_base}.r",
            )
        )
    )


def iter_dependency_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = _coalesced_stripped_text(text, stripped_text)
    entries: list[tuple[str, str | None, int]] = []
    seen_entries: set[tuple[str, str | None, int]] = set()
    for match in _DO_IMPORT_RE.finditer(stripped_text):
        target = clean_import_target(match.group("target") or "")
        if not target:
            continue
        binding = normalize_identifier(match.group("binding") or "") or None
        entry = (target, binding, stripped_text.count("\n", 0, match.start()) + 1)
        if entry in seen_entries:
            continue
        seen_entries.add(entry)
        entries.append(entry)
    for match in _NEEDS_RE.finditer(stripped_text):
        body = str(match.group("body") or "")
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        for raw_target in re.findall(r"%?[^\s\[\]]+", body):
            target = clean_import_target(raw_target)
            if not target:
                continue
            entry = (target, None, line_number)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append(entry)
    return tuple(entries)


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = _coalesced_stripped_text(text, stripped_text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for target, binding, line_number in iter_dependency_entries(
        text,
        stripped_text=stripped_text,
    ):
        del target
        if binding and binding not in seen_names:
            seen_names.add(binding)
            entries.append((binding, "import_binding", line_number))
    for match in _SYMBOL_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        kind = normalize_identifier(match.group("kind") or "").lower() or "assignment"
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, kind, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(sorted(entries, key=lambda entry: (entry[2], entry[0], entry[1])))


def iter_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coalesced_stripped_text(text, stripped_text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        if _HEADER_FIELD_LINE_RE.match(raw_line):
            continue
        line = _DO_IMPORT_RE.sub("", raw_line, count=1)
        line = _SYMBOL_RE.sub("", line, count=1)
        for match in _REFERENCE_RE.finditer(line):
            name = normalize_identifier(match.group("name") or "")
            if not name or name in _RESERVED_REFERENCE_NAMES:
                continue
            entry = (name, line_number)
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
    text: str | None = None,
    stripped_text: str | None = None,
) -> set[str]:
    del stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in REBOL_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    if text is None:
        try:
            text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    stripped_text = _coalesced_stripped_text(text, stripped_text)
    for symbol_name, _kind, _line in iter_symbol_entries(text, stripped_text=stripped_text):
        aliases.add(symbol_name)
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[_Symbol, ...]:
    module_name = module_name_from_path(file_path)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "rebol"},
            ),
            symbol_name=module_name,
            symbol_kind="rebol",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"rebol {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    stripped_text = _coalesced_stripped_text(text, stripped_text)
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(
        text,
        stripped_text=stripped_text,
    ):
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


def resolve_import_module(
    import_target: str,
    current_file: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = clean_import_target(import_target)
    if not normalized_target:
        return None
    candidate_keys: list[str] = []
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    if current_dir:
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
    candidate_keys.extend(
        candidate_module_keys(
            normalized_target,
            normalize_repository_relative_path=normalize_repository_relative_path,
        )
    )
    for prefix in (
        "app",
        "apps",
        "lib",
        "libs",
        "plugin",
        "plugins",
        "protocol",
        "protocols",
        "script",
        "scripts",
        "src",
        "test",
        "test-framework",
        "tests",
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
