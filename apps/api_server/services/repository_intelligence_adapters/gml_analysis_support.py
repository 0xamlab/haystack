from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from apps.api_server.services import (
    repository_intelligence_contracts as repository_contracts,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gml_primitives as repository_gml_primitives,
)

_Dependency = repository_contracts._Dependency
_Symbol = repository_contracts._Symbol
_SymbolReferenceCandidate = repository_contracts._SymbolReferenceCandidate

StableIdentifier = repository_gml_primitives.StableIdentifier
_KNOWN_SUFFIXES = repository_gml_primitives._KNOWN_SUFFIXES
_line_number = repository_gml_primitives._line_number
_normalize_name = repository_gml_primitives._normalize_name
_ordered_names = repository_gml_primitives._ordered_names
event_symbol_name = repository_gml_primitives.event_symbol_name
has_gml_path_hints = repository_gml_primitives.has_gml_path_hints
is_probable_gml_source = repository_gml_primitives.is_probable_gml_source
is_probable_operational_entrypoint = repository_gml_primitives.is_probable_operational_entrypoint
load_game_maker_json = repository_gml_primitives.load_game_maker_json
module_symbol_name = repository_gml_primitives.module_symbol_name
object_resource_name = repository_gml_primitives.object_resource_name
script_resource_name = repository_gml_primitives.script_resource_name
strip_comments = repository_gml_primitives.strip_comments

_FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:static\s+)?function\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_FUNCTION_ASSIGN_RE = re.compile(
    r"^\s*(?:static\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*function\s*\(",
    re.MULTILINE,
)
_ENUM_DECL_RE = re.compile(
    r"^\s*enum\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_MACRO_DECL_RE = re.compile(
    r"^\s*#macro\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_UNQUALIFIED_CALL_RE = re.compile(
    r"(?<!\.)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
)
_QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
)
_RESERVED_CALL_NAMES = frozenset(
    {
        "and",
        "break",
        "constructor",
        "continue",
        "delete",
        "div",
        "do",
        "enum",
        "exit",
        "false",
        "for",
        "function",
        "if",
        "macro",
        "mod",
        "new",
        "not",
        "or",
        "repeat",
        "return",
        "self",
        "static",
        "switch",
        "true",
        "until",
        "var",
        "while",
        "with",
        "xor",
    }
)
_RESERVED_QUALIFIED_OWNERS = frozenset({"global", "self"})


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    start_line: int
    end_line: int


@dataclass(frozen=True)
class _DeclaredFunction:
    name: str
    offset: int
    line_no: int


def _declared_functions(text: str) -> tuple[_DeclaredFunction, ...]:
    entries: list[_DeclaredFunction] = []
    seen: set[tuple[str, int]] = set()
    for pattern in (_FUNCTION_DECL_RE, _FUNCTION_ASSIGN_RE):
        for match in pattern.finditer(text):
            name = _normalize_name(match.group("name"))
            if not name:
                continue
            offset = match.start("name")
            line_no = _line_number(text, offset)
            key = (name, line_no)
            if key in seen:
                continue
            seen.add(key)
            entries.append(_DeclaredFunction(name=name, offset=offset, line_no=line_no))
    return tuple(sorted(entries, key=lambda entry: (entry.offset, entry.name)))


def _declared_names(text: str, pattern: re.Pattern[str]) -> tuple[tuple[str, int], ...]:
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in pattern.finditer(text):
        name = _normalize_name(match.group("name"))
        if not name:
            continue
        line_no = _line_number(text, match.start("name"))
        key = (name, line_no)
        if key in seen:
            continue
        seen.add(key)
        entries.append(key)
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        path.stem,
    }
    script_name = script_resource_name(file_path)
    object_name = object_resource_name(file_path)
    event_name = event_symbol_name(file_path)
    aliases.update(_ordered_names(script_name, f"script:{script_name}"))
    aliases.update(_ordered_names(object_name, f"object:{object_name}"))
    aliases.update(_ordered_names(event_name, f"event:{event_name}"))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    stripped_text = strip_comments(text)
    for function in _declared_functions(stripped_text):
        aliases.add(function.name)
        if script_name and function.name != script_name:
            aliases.add(f"{script_name}.{function.name}")
        if object_name:
            aliases.add(f"{object_name}.{function.name}")
    for enum_name, _line_no in _declared_names(stripped_text, _ENUM_DECL_RE):
        aliases.add(enum_name)
        aliases.add(f"enum:{enum_name}")
    for macro_name, _line_no in _declared_names(stripped_text, _MACRO_DECL_RE):
        aliases.add(macro_name)
        aliases.add(f"macro:{macro_name}")
    return {alias for alias in aliases if alias}


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[tuple[_Symbol, ...], tuple[_CollectedSymbol, ...], set[str], set[int]]:
    final_line = max(1, text.count("\n") + (1 if text else 0))
    script_name = script_resource_name(file_path)
    primary_name = module_symbol_name(file_path)
    declared_functions = _declared_functions(text)
    declared_function_names = {entry.name for entry in declared_functions}
    declaration_offsets = {entry.offset for entry in declared_functions}

    primary_kind = "module"
    if script_name and script_name not in declared_function_names:
        primary_kind = "function"
    primary_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "name": primary_name,
                "kind": primary_kind,
                "line": 1,
            },
        ),
        symbol_name=primary_name,
        symbol_kind=primary_kind,
        start_line=1,
        end_line=final_line,
        parent_symbol_id=None,
        signature=primary_name,
    )
    symbols: list[_Symbol] = [primary_symbol]
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=primary_symbol,
            start_line=primary_symbol.start_line,
            end_line=primary_symbol.end_line,
        )
    ]
    local_callable_names: set[str] = set()
    if primary_kind == "function":
        local_callable_names.add(primary_name)

    for enum_name, line_no in _declared_names(text, _ENUM_DECL_RE):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": enum_name,
                        "kind": "enum",
                        "line": line_no,
                    },
                ),
                symbol_name=enum_name,
                symbol_kind="enum",
                start_line=line_no,
                end_line=line_no,
                parent_symbol_id=primary_symbol.symbol_id,
                signature=enum_name,
            )
        )
    for macro_name, line_no in _declared_names(text, _MACRO_DECL_RE):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": macro_name,
                        "kind": "constant",
                        "line": line_no,
                    },
                ),
                symbol_name=macro_name,
                symbol_kind="constant",
                start_line=line_no,
                end_line=line_no,
                parent_symbol_id=primary_symbol.symbol_id,
                signature=macro_name,
            )
        )

    for index, function in enumerate(declared_functions):
        if function.name == primary_name and primary_kind == "function":
            continue
        start_line = function.line_no
        if index + 1 < len(declared_functions):
            end_line = max(declared_functions[index + 1].line_no - 1, start_line)
        else:
            end_line = final_line
        function_symbol = _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "name": function.name,
                    "kind": "function",
                    "line": start_line,
                },
            ),
            symbol_name=function.name,
            symbol_kind="function",
            start_line=start_line,
            end_line=end_line,
            parent_symbol_id=primary_symbol.symbol_id,
            signature=function.name,
        )
        symbols.append(function_symbol)
        collected_symbols.append(
            _CollectedSymbol(
                symbol=function_symbol,
                start_line=start_line,
                end_line=end_line,
            )
        )
        local_callable_names.add(function.name)

    if script_name:
        local_callable_names.add(script_name)
    return (
        tuple(symbols),
        tuple(collected_symbols),
        local_callable_names,
        declaration_offsets,
    )


def _source_symbol_id_for_line(
    *,
    line_no: int,
    collected_symbols: tuple[_CollectedSymbol, ...],
) -> str | None:
    matching_symbols = [
        collected_symbol
        for collected_symbol in collected_symbols
        if collected_symbol.start_line <= line_no <= collected_symbol.end_line
    ]
    if not matching_symbols:
        return None
    matching_symbols.sort(
        key=lambda collected_symbol: (
            0 if collected_symbol.symbol.symbol_kind == "function" else 1,
            -collected_symbol.start_line,
        )
    )
    return matching_symbols[0].symbol.symbol_id


def _iter_reference_targets(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    local_callable_names: set[str],
    declaration_offsets: set[int],
) -> tuple[tuple[str, str, int], ...]:
    reference_targets: list[tuple[str, str, int]] = []
    seen_keys: set[tuple[str, str, int]] = set()
    for match in _QUALIFIED_CALL_RE.finditer(text):
        owner = _normalize_name(match.group("owner"))
        name = _normalize_name(match.group("name"))
        if not owner or not name or owner in _RESERVED_QUALIFIED_OWNERS:
            continue
        target_file = module_index.get(owner)
        if target_file is None:
            continue
        line_no = _line_number(text, match.start("name"))
        key = (target_file, name, line_no)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        reference_targets.append(key)
    for match in _UNQUALIFIED_CALL_RE.finditer(text):
        name = _normalize_name(match.group("name"))
        if not name or name in _RESERVED_CALL_NAMES or match.start("name") in declaration_offsets:
            continue
        if name in local_callable_names:
            target_file = file_path
        else:
            target_file = module_index.get(name)
        if target_file is None:
            continue
        line_no = _line_number(text, match.start("name"))
        key = (target_file, name, line_no)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        reference_targets.append(key)
    return tuple(reference_targets)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
) -> tuple[_Dependency, ...]:
    path = PurePosixPath(file_path)
    if not is_probable_gml_source(path=path, text=text):
        return ()
    stripped_text = strip_comments(text)
    _, _, local_callable_names, declaration_offsets = _collect_symbols(
        file_path=file_path,
        text=stripped_text,
        stable_identifier=stable_identifier,
    )
    dependencies: list[_Dependency] = []
    seen_keys: set[tuple[str, str, int]] = set()
    for target_file, target_name, line_no in _iter_reference_targets(
        file_path=file_path,
        text=stripped_text,
        module_index=module_index,
        local_callable_names=local_callable_names,
        declaration_offsets=declaration_offsets,
    ):
        dependency_key = (target_file, target_name, line_no)
        if dependency_key in seen_keys:
            continue
        seen_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "line": line_no,
                        "target": target_file,
                        "symbol": target_name,
                        "type": "references",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="references",
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    path = PurePosixPath(file_path)
    if not is_probable_gml_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    symbols, collected_symbols, local_callable_names, declaration_offsets = _collect_symbols(
        file_path=file_path,
        text=stripped_text,
        stable_identifier=stable_identifier,
    )
    dependencies = parse_dependencies_only(
        file_path=file_path,
        text=stripped_text,
        module_index=module_index,
        stable_identifier=stable_identifier,
    )
    reference_candidates: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str, str, int]] = set()
    for target_file, target_name, line_no in _iter_reference_targets(
        file_path=file_path,
        text=stripped_text,
        module_index=module_index,
        local_callable_names=local_callable_names,
        declaration_offsets=declaration_offsets,
    ):
        source_symbol_id = _source_symbol_id_for_line(
            line_no=line_no,
            collected_symbols=collected_symbols,
        )
        if source_symbol_id is None:
            continue
        reference_key = (source_symbol_id, target_file, target_name, line_no)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        reference_candidates.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "line": line_no,
                        "symbol_id": source_symbol_id,
                        "target": target_name,
                        "type": "references_symbol",
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=_ordered_names(target_name),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(reference_candidates)
