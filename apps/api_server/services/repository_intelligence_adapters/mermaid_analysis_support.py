from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    mermaid_primitives as repository_mermaid_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_mermaid_primitives.StableIdentifier

MERMAID_INDEX_BASENAMES = repository_mermaid_primitives.MERMAID_INDEX_BASENAMES
MERMAID_SUFFIXES = repository_mermaid_primitives.MERMAID_SUFFIXES
collect_symbols = repository_mermaid_primitives.collect_symbols
directive_from_text = repository_mermaid_primitives.directive_from_text
has_mermaid_path_hints = repository_mermaid_primitives.has_mermaid_path_hints
is_probable_mermaid_source = repository_mermaid_primitives.is_probable_mermaid_source
iter_edge_entries = repository_mermaid_primitives.iter_edge_entries
iter_node_entries = repository_mermaid_primitives.iter_node_entries
iter_subgraph_entries = repository_mermaid_primitives.iter_subgraph_entries
module_aliases_for_path = repository_mermaid_primitives.module_aliases_for_path
module_name_from_path = repository_mermaid_primitives.module_name_from_path
source_symbol_name_for_line = repository_mermaid_primitives.source_symbol_name_for_line


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path,
    resolve_suffix_match,
) -> tuple[_Dependency, ...]:
    del module_index, stable_identifier, normalize_repository_relative_path, resolve_suffix_match
    if not is_probable_mermaid_source(path=Path(file_path), text=text):
        return ()
    return ()


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path,
    resolve_suffix_match,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    del module_index, normalize_repository_relative_path, resolve_suffix_match
    if not is_probable_mermaid_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols}
    module_symbol_id = symbols[0].symbol_id if symbols else None
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str, str | None]] = set()
    for source_name, target_name, line_number in iter_edge_entries(text):
        source_symbol_id = symbol_ids_by_name.get(source_name, module_symbol_id)
        target_symbol_id = symbol_ids_by_name.get(target_name)
        if not source_symbol_id or not target_symbol_id:
            continue
        reference_key = (source_name, target_name, source_symbol_id)
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
    if not references and module_symbol_id:
        for target_name, line_number in iter_node_entries(text)[:1]:
            target_symbol_id = symbol_ids_by_name.get(target_name)
            if not target_symbol_id:
                continue
            references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "file_path": file_path,
                            "line": line_number,
                            "source_symbol_id": module_symbol_id,
                            "target_name": target_name,
                        },
                    ),
                    source_symbol_id=module_symbol_id,
                    source_file=file_path,
                    target_symbol_id=target_symbol_id,
                    target_file=file_path,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                )
            )
            break
    return symbols, (), tuple(references)
