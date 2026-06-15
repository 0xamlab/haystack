from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    bqn_primitives as repository_bqn_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_bqn_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_bqn_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_bqn_primitives.ResolveSuffixMatch

BQN_SUFFIXES = repository_bqn_primitives.BQN_SUFFIXES
candidate_module_keys = repository_bqn_primitives.candidate_module_keys
collect_symbols = repository_bqn_primitives.collect_symbols
has_bqn_path_hints = repository_bqn_primitives.has_bqn_path_hints
is_probable_bqn_source = repository_bqn_primitives.is_probable_bqn_source
iter_dependency_entries = repository_bqn_primitives.iter_dependency_entries
iter_reference_entries = repository_bqn_primitives.iter_reference_entries
iter_symbol_entries = repository_bqn_primitives.iter_symbol_entries
module_aliases_for_path = repository_bqn_primitives.module_aliases_for_path
module_name_from_path = repository_bqn_primitives.module_name_from_path
resolve_import_module = repository_bqn_primitives.resolve_import_module
source_symbol_name_for_line = repository_bqn_primitives.source_symbol_name_for_line
strip_comments = repository_bqn_primitives.strip_comments


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_bqn_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_keys: set[tuple[str | None, str | None, int]] = set()
    for import_target, binding, line_number in iter_dependency_entries(text):
        target_file = resolve_import_module(
            import_target,
            file_path,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        key = (target_file, binding, line_number)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "kind": "imports",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=binding,
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
    if not is_probable_bqn_source(path=Path(file_path), text=text):
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
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols[1:]}
    symbol_kinds_by_name = {symbol_name: symbol_kind for symbol_name, symbol_kind, _line in symbol_entries}
    default_source_symbol_id = symbols[0].symbol_id
    dependency_targets_by_name = {
        dependency.target_symbol: dependency.target_file
        for dependency in dependencies
        if dependency.target_symbol and dependency.target_file
    }
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str | None]] = set()

    for target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        dependency_target_file = dependency_targets_by_name.get(target_name)
        if (
            target_name in symbol_ids_by_name
            and not (
                dependency_target_file
                and symbol_kinds_by_name.get(target_name) == "import_binding"
            )
        ):
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
        if not dependency_target_file:
            continue
        reference_key = (dependency_target_file, target_name, source_symbol_id)
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
                        "target_file": dependency_target_file,
                        "target_name": target_name,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency_target_file,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(references)
