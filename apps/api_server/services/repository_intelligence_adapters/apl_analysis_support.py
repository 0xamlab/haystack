from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    apl_primitives as repository_apl_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_apl_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_apl_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_apl_primitives.ResolveSuffixMatch

APL_SUFFIXES = repository_apl_primitives.APL_SUFFIXES
collect_symbols = repository_apl_primitives.collect_symbols
has_apl_path_hints = repository_apl_primitives.has_apl_path_hints
is_probable_apl_source = repository_apl_primitives.is_probable_apl_source
iter_dependency_entries = repository_apl_primitives.iter_dependency_entries
iter_reference_entries = repository_apl_primitives.iter_reference_entries
iter_symbol_entries = repository_apl_primitives.iter_symbol_entries
module_aliases_for_path = repository_apl_primitives.module_aliases_for_path
module_name_from_path = repository_apl_primitives.module_name_from_path
source_symbol_name_for_line = repository_apl_primitives.source_symbol_name_for_line
strip_comments = repository_apl_primitives.strip_comments


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    del file_path
    del text
    del module_index
    del stable_identifier
    del normalize_repository_relative_path
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
    del module_index
    del normalize_repository_relative_path
    del resolve_suffix_match
    if not is_probable_apl_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols[1:]}
    default_source_symbol_id = symbols[0].symbol_id
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()

    for target_name, line_number in iter_reference_entries(text):
        if target_name not in symbol_ids_by_name:
            continue
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        reference_key = (file_path, target_name, source_symbol_id)
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
