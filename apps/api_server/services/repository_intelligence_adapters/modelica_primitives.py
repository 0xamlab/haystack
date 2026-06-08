from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _ImportedSymbolBinding,
    _Symbol,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

MODELICA_SUFFIXES = frozenset({".mo"})
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE_RE = re.compile(r"(?m)//.*$")
_WITHIN_RE = re.compile(r"(?mi)^\s*within\s+(?P<name>[A-Za-z_][A-Za-z0-9_.]*)\s*;")
_DECLARATION_RE = re.compile(
    r"(?mi)^\s*"
    r"(?:(?:encapsulated|final|inner|outer|partial|redeclare|replaceable)\s+)*"
    r"(?P<kind>package|model|record|function|block|connector|class|type)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_END_RE = re.compile(r"(?mi)\bend\s+[A-Za-z_][A-Za-z0-9_]*\s*;")
_IMPORT_RE = re.compile(
    r"(?mi)^\s*import\s+(?:(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)?"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_.]*)\s*;"
)
_EXTENDS_RE = re.compile(r"(?mi)^\s*extends\s+(?P<target>[A-Za-z_][A-Za-z0-9_.]*)\b")
_PACKAGE_ASSIGN_RE = re.compile(
    r"(?mi)^\s*(?:(?:redeclare|replaceable)\s+)*package\s+"
    r"[A-Za-z_][A-Za-z0-9_]*\s*=\s*(?P<target>[A-Za-z_][A-Za-z0-9_.]*)\b"
)
_QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<prefix>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\."
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?=\()"
)
_CALL_RE = re.compile(r"(?<![.])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?=\()")
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "algorithm",
        "annotation",
        "connect",
        "constrainedby",
        "der",
        "each",
        "else",
        "elseif",
        "elsewhen",
        "equation",
        "extends",
        "false",
        "for",
        "if",
        "import",
        "in",
        "initial",
        "loop",
        "not",
        "or",
        "redeclare",
        "replaceable",
        "then",
        "true",
        "when",
        "while",
    }
)


def _preserve_line_count_comment(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def strip_comments(text: str) -> str:
    without_block_comments = _COMMENT_BLOCK_RE.sub(_preserve_line_count_comment, text)
    return _COMMENT_LINE_RE.sub("", without_block_comments)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip(";").strip(".")


def has_modelica_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in MODELICA_SUFFIXES


def is_probable_modelica_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).suffix.lower() not in MODELICA_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(_WITHIN_RE.search(stripped_text) or _DECLARATION_RE.search(stripped_text)) and bool(
        _END_RE.search(stripped_text) or _IMPORT_RE.search(stripped_text) or _EXTENDS_RE.search(stripped_text)
    )


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    if normalized_path.name.lower() == "package.mo":
        parts = normalized_path.parent.parts
    else:
        parts = normalized_path.with_suffix("").parts
    return ".".join(parts) if parts else normalized_path.stem


def declared_module_name_from_text(*, file_path: str, text: str) -> str | None:
    stripped_text = strip_comments(text)
    declaration_match = _DECLARATION_RE.search(stripped_text)
    if declaration_match is None:
        return None
    declared_name = normalize_identifier(declaration_match.group("name"))
    if not declared_name:
        return None
    within_match = _WITHIN_RE.search(stripped_text)
    within_name = normalize_identifier(within_match.group("name")) if within_match else ""
    if PurePosixPath(file_path).name.lower() == "package.mo":
        return ".".join(part for part in (within_name, declared_name) if part)
    return f"{within_name}.{declared_name}".strip(".")


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _package_scopes_for_file(file_path: str) -> tuple[str, ...]:
    module_name = module_name_from_path(file_path)
    if not module_name:
        return ()
    package_name = (
        module_name
        if PurePosixPath(file_path).name.lower() == "package.mo"
        else module_name.rpartition(".")[0]
    )
    scopes: list[str] = []
    current_scope = package_name
    while current_scope:
        scopes.append(current_scope)
        if "." not in current_scope:
            break
        current_scope = current_scope.rpartition(".")[0]
    return tuple(scopes)


def clean_import_target(value: str) -> str:
    return normalize_identifier(value)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, str | None, int]] = []
    for pattern, dependency_kind in (
        (_IMPORT_RE, "imports"),
        (_EXTENDS_RE, "extends"),
        (_PACKAGE_ASSIGN_RE, "uses_package"),
    ):
        for match in pattern.finditer(stripped_text):
            target = clean_import_target(match.group("target") or "")
            if not target:
                continue
            alias = normalize_identifier(match.groupdict().get("alias") or "") or None
            entries.append((dependency_kind, target, alias, _line_number(stripped_text, match.start())))
    return tuple(entries)


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
    qualified_candidates = [cleaned_target]
    for scope in _package_scopes_for_file(current_file):
        qualified_candidates.append(f"{scope}.{cleaned_target}")
    ordered_candidates = tuple(dict.fromkeys(candidate for candidate in qualified_candidates if candidate))
    for candidate in ordered_candidates:
        exact_match = module_index.get(candidate)
        if exact_match is not None:
            return exact_match

    current_dir = PurePosixPath(current_file).parent
    path_suffixes: list[str] = []
    for candidate in ordered_candidates:
        dot_path = PurePosixPath(*candidate.split("."))
        path_suffixes.extend(
            (
                candidate,
                str(dot_path.with_suffix(".mo")),
                str(dot_path / "package.mo"),
            )
        )
    relative_path = PurePosixPath(*cleaned_target.split("."))
    path_suffixes.extend(
        (
            str(current_dir / relative_path.with_suffix(".mo")),
            str(current_dir / relative_path / "package.mo"),
        )
    )
    normalized_suffixes = tuple(
        suffix
        for suffix in dict.fromkeys(
            normalize_repository_relative_path(candidate) or ""
            for candidate in path_suffixes
        )
        if suffix
    )
    return resolve_suffix_match(module_index=module_index, suffixes=normalized_suffixes)


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for dependency_kind, import_target, alias, _line_number_value in iter_dependency_entries(text):
        if dependency_kind != "imports":
            continue
        target_file = resolve_import(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        binding_aliases = [alias] if alias else []
        binding_aliases.append(import_target.rsplit(".", 1)[-1])
        for binding_alias in binding_aliases:
            normalized_alias = normalize_identifier(binding_alias or "")
            if not normalized_alias or normalized_alias in bindings:
                continue
            bindings[normalized_alias] = _ImportedSymbolBinding(
                alias=normalized_alias,
                target_file=target_file,
                target_names=(),
            )
    return bindings


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _DECLARATION_RE.finditer(stripped_text):
        symbol_kind = normalize_identifier(match.group("kind")).lower()
        symbol_name = normalize_identifier(match.group("name"))
        if not symbol_name or symbol_name in seen_names:
            continue
        seen_names.add(symbol_name)
        entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str | None, str, int]] = []
    seen_entries: set[tuple[str | None, str, int]] = set()
    for match in _QUALIFIED_CALL_RE.finditer(stripped_text):
        prefix = normalize_identifier(match.group("prefix"))
        name = normalize_identifier(match.group("name"))
        if not prefix or not name or name in _RESERVED_REFERENCE_NAMES:
            continue
        entry = (prefix, name, _line_number(stripped_text, match.start()))
        if entry in seen_entries:
            continue
        seen_entries.add(entry)
        entries.append(entry)
    for match in _CALL_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name"))
        if not name or name in _RESERVED_REFERENCE_NAMES:
            continue
        entry = (None, name, _line_number(stripped_text, match.start()))
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
    if normalized_path.suffix.lower() not in MODELICA_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        module_name_from_path(file_path),
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
    }
    if normalized_path.name.lower() == "package.mo" and normalized_path.parent.name:
        aliases.add(normalized_path.parent.name)
        aliases.add(str(normalized_path.parent))
        aliases.add(".".join(normalized_path.parent.parts))
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    module_name = declared_module_name_from_text(file_path=file_path, text=text) or module_name_from_path(
        file_path
    )
    line_count = _line_count(text)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "modelica"},
            ),
            symbol_name=module_name,
            symbol_kind="modelica",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"modelica {module_name}",
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
