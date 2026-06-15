from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    circom_primitives as repository_circom_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_circom_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_circom_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_circom_primitives.ResolveSuffixMatch

CIRCOM_SUFFIXES = repository_circom_primitives.CIRCOM_SUFFIXES
candidate_module_keys = repository_circom_primitives.candidate_module_keys
collect_symbols = repository_circom_primitives.collect_symbols
has_circom_path_hints = repository_circom_primitives.has_circom_path_hints
is_probable_circom_source = repository_circom_primitives.is_probable_circom_source
iter_include_entries = repository_circom_primitives.iter_include_entries
iter_reference_entries = repository_circom_primitives.iter_reference_entries
iter_symbol_entries = repository_circom_primitives.iter_symbol_entries
module_aliases_for_path = repository_circom_primitives.module_aliases_for_path
module_name_from_path = repository_circom_primitives.module_name_from_path
resolve_include = repository_circom_primitives.resolve_include
source_symbol_name_for_line = repository_circom_primitives.source_symbol_name_for_line
strip_comments = repository_circom_primitives.strip_comments


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_circom_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_keys: set[tuple[str | None, str, int]] = set()
    for include_target, line_number in iter_include_entries(text):
        target_file = resolve_include(
            include_target,
            file_path,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_name = Path(target_file).stem if target_file else Path(include_target).stem
        key = (target_file, include_target, line_number)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": include_target,
                        "kind": "includes",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="includes",
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
    if not is_probable_circom_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    imported_target_files = tuple(
        dict.fromkeys(
            dependency.target_file
            for dependency in dependencies
            if dependency.target_file and dependency.target_file != file_path
        )
    )
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols[1:]}
    default_source_symbol_id = symbols[0].symbol_id
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str | None]] = set()

    for target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        if target_name in symbol_ids_by_name:
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
            continue
        target_file = module_index.get(target_name)
        if target_file is None and len(imported_target_files) == 1:
            target_file = imported_target_files[0]
        if not target_file:
            continue
        reference_key = (target_file, target_name, source_symbol_id)
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
                        "target_file": target_file,
                        "target_name": target_name,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(references)


__all__ = [
    "CIRCOM_SUFFIXES",
    "NormalizeRepositoryRelativePath",
    "ResolveSuffixMatch",
    "StableIdentifier",
    "candidate_module_keys",
    "collect_symbols",
    "has_circom_path_hints",
    "is_probable_circom_source",
    "iter_include_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_include",
    "source_symbol_name_for_line",
    "strip_comments",
]
