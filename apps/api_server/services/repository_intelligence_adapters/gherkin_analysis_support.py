from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    gherkin_primitives as repository_gherkin_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_gherkin_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_gherkin_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_gherkin_primitives.ResolveSuffixMatch

GHERKIN_SUFFIXES = repository_gherkin_primitives.GHERKIN_SUFFIXES
GHERKIN_INDEX_BASENAMES = repository_gherkin_primitives.GHERKIN_INDEX_BASENAMES
collect_symbols = repository_gherkin_primitives.collect_symbols
has_gherkin_path_hints = repository_gherkin_primitives.has_gherkin_path_hints
is_probable_gherkin_source = repository_gherkin_primitives.is_probable_gherkin_source
iter_reference_entries = repository_gherkin_primitives.iter_reference_entries
iter_symbol_entries = repository_gherkin_primitives.iter_symbol_entries
module_aliases_for_path = repository_gherkin_primitives.module_aliases_for_path
module_name_from_path = repository_gherkin_primitives.module_name_from_path
normalize_identifier = repository_gherkin_primitives.normalize_identifier
source_symbol_name_for_line = repository_gherkin_primitives.source_symbol_name_for_line


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    del module_index, stable_identifier, normalize_repository_relative_path, resolve_suffix_match
    if not is_probable_gherkin_source(path=Path(file_path), text=text):
        return ()
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
    if not is_probable_gherkin_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    dependencies: tuple[_Dependency, ...] = ()
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols}
    module_symbol_id = symbols[0].symbol_id if symbols else None
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str, str | None]] = set()
    for _reference_kind, target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", module_symbol_id)
        target_symbol_id = symbol_ids_by_name.get(target_name)
        if not source_symbol_id or not target_symbol_id:
            continue
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
                        "source_symbol_id": source_symbol_id,
                        "target_file": file_path,
                        "target_name": target_name,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=file_path,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(references)
