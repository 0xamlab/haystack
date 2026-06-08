from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    wgsl_primitives as repository_wgsl_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_wgsl_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_wgsl_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_wgsl_primitives.ResolveSuffixMatch

WGSL_SUFFIXES = repository_wgsl_primitives.WGSL_SUFFIXES
has_wgsl_path_hints = repository_wgsl_primitives.has_wgsl_path_hints
iter_function_call_names = repository_wgsl_primitives.iter_function_call_names
iter_symbol_entries = repository_wgsl_primitives.iter_symbol_entries
parse_import_statements = repository_wgsl_primitives.parse_import_statements
parse_include_statements = repository_wgsl_primitives.parse_include_statements
strip_comments = repository_wgsl_primitives.strip_comments


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    start_line: int


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def is_probable_wgsl_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_wgsl_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(
        repository_wgsl_primitives.WGSL_MARKER_RE.search(stripped_text)
        or repository_wgsl_primitives.WGSL_FUNCTION_RE.search(stripped_text)
        or repository_wgsl_primitives.WGSL_STRUCT_RE.search(stripped_text)
    )


def _resolve_shader_target(
    raw_target: str,
    *,
    file_path: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    candidate_value = str(raw_target or "").strip()
    if not candidate_value:
        return None
    normalized_relative = (
        normalize_repository_relative_path(str(PurePosixPath(file_path).parent / candidate_value))
        if candidate_value.startswith(".") or "/" in candidate_value
        else normalize_repository_relative_path(candidate_value)
    )
    candidate_targets: list[str] = []
    for value in (candidate_value, normalized_relative):
        normalized = str(value or "").strip()
        if not normalized:
            continue
        candidate_targets.append(normalized)
        if PurePosixPath(normalized).suffix.lower() not in WGSL_SUFFIXES:
            candidate_targets.extend(f"{normalized}{suffix}" for suffix in WGSL_SUFFIXES)
    for candidate_target in candidate_targets:
        target_file = module_index.get(candidate_target)
        if target_file is not None:
            return target_file
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_targets)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    line_count = _line_count(text)
    collected_symbols: list[_CollectedSymbol] = []
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(text):
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": symbol_name,
                            "symbol_kind": symbol_kind,
                            "start_line": start_line,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=start_line,
                    end_line=line_count,
                    parent_symbol_id=None,
                    signature=symbol_name,
                ),
                start_line=start_line,
            )
        )
    finalized_symbols: list[_CollectedSymbol] = []
    for index, collected_symbol in enumerate(collected_symbols):
        end_line = (
            max(collected_symbols[index + 1].start_line - 1, collected_symbol.start_line)
            if index + 1 < len(collected_symbols)
            else line_count
        )
        symbol = collected_symbol.symbol
        finalized_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=symbol.symbol_id,
                    symbol_name=symbol.symbol_name,
                    symbol_kind=symbol.symbol_kind,
                    start_line=symbol.start_line,
                    end_line=end_line,
                    parent_symbol_id=None,
                    signature=symbol.signature,
                ),
                start_line=collected_symbol.start_line,
            )
        )
    return tuple(finalized_symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_wgsl_path_hints(path):
        return set()
    aliases = {file_path, str(path.with_suffix("")), path.stem}
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_wgsl_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    for target_path, line_number in parse_include_statements(text):
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target_path,
                        "line": line_number,
                        "type": "include",
                    },
                ),
                source_file=file_path,
                target_file=_resolve_shader_target(
                    target_path,
                    file_path=file_path,
                    module_index=module_index,
                    normalize_repository_relative_path=normalize_repository_relative_path,
                    resolve_suffix_match=resolve_suffix_match,
                ),
                target_symbol=None,
                dependency_type="includes",
            )
        )
    for target_path, alias_name, line_number in parse_import_statements(text):
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target_path,
                        "alias": alias_name,
                        "line": line_number,
                        "type": "import",
                    },
                ),
                source_file=file_path,
                target_file=_resolve_shader_target(
                    target_path,
                    file_path=file_path,
                    module_index=module_index,
                    normalize_repository_relative_path=normalize_repository_relative_path,
                    resolve_suffix_match=resolve_suffix_match,
                ),
                target_symbol=alias_name,
                dependency_type="imports",
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    local_symbol_lookup = {
        collected_symbol.symbol.symbol_name: collected_symbol.symbol.symbol_id
        for collected_symbol in collected_symbols
        if collected_symbol.symbol.symbol_kind == "function"
    }
    imported_alias_targets = {
        str(dependency.target_symbol or "").strip(): dependency.target_file
        for dependency in dependencies
        if str(dependency.target_symbol or "").strip() and dependency.target_file
    }
    lines = text.splitlines()
    symbol_references: list[_SymbolReferenceCandidate] = []
    for collected_symbol in collected_symbols:
        source_symbol = collected_symbol.symbol
        if source_symbol.symbol_kind != "function":
            continue
        end_line = max(source_symbol.end_line, source_symbol.start_line)
        snippet = "\n".join(lines[max(source_symbol.start_line - 1, 0) : end_line])
        for call_name, relative_line_number in iter_function_call_names(
            snippet,
            local_function_names={source_symbol.symbol_name},
        ):
            if not call_name or call_name == source_symbol.symbol_name:
                continue
            target_symbol_id = None
            target_file = None
            if call_name in local_symbol_lookup:
                target_symbol_id = local_symbol_lookup.get(call_name)
                target_file = file_path
            else:
                target_file = imported_alias_targets.get(call_name)
                if target_file is None:
                    resolved_target_file = module_index.get(call_name)
                    if resolved_target_file and resolved_target_file != file_path:
                        target_file = resolved_target_file
            line_number = source_symbol.start_line + relative_line_number - 1
            symbol_references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "file_path": file_path,
                            "source_symbol_id": source_symbol.symbol_id,
                            "target": call_name,
                            "line": line_number,
                            "type": "references_symbol",
                        },
                    ),
                    source_symbol_id=source_symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=target_symbol_id,
                    target_file=target_file,
                    target_names=(call_name,),
                    reference_type="references_symbol",
                )
            )
    return (
        tuple(collected_symbol.symbol for collected_symbol in collected_symbols),
        dependencies,
        tuple(symbol_references),
    )
