from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    j_primitives as repository_j_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_j_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_j_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_j_primitives.ResolveSuffixMatch

J_SUFFIXES = repository_j_primitives.J_SUFFIXES
collect_symbols = repository_j_primitives.collect_symbols
has_j_path_hints = repository_j_primitives.has_j_path_hints
is_probable_j_source = repository_j_primitives.is_probable_j_source
iter_dependency_entries = repository_j_primitives.iter_dependency_entries
iter_reference_entries = repository_j_primitives.iter_reference_entries
iter_symbol_entries = repository_j_primitives.iter_symbol_entries
module_aliases_for_path = repository_j_primitives.module_aliases_for_path
source_symbol_name_for_line = repository_j_primitives.source_symbol_name_for_line


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    del file_path, text, module_index, stable_identifier, normalize_repository_relative_path
    del resolve_suffix_match
    return ()


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
    del module_index, normalize_repository_relative_path, resolve_suffix_match
    if not is_probable_j_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols[1:]}
    default_source_symbol_id = symbols[0].symbol_id
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str]] = set()
    for target_name, line_number in iter_reference_entries(text, local_symbol_names=set(symbol_ids_by_name)):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        reference_key = (target_name, source_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "line": line_number,
                        "source_symbol_id": source_symbol_id,
                        "target_file": file_path,
                        "target_name": target_name,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=symbol_ids_by_name[target_name],
                target_file=file_path,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return symbols, (), tuple(references)
