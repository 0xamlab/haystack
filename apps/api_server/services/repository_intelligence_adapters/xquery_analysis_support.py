from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    xquery_primitives as repository_xquery_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_xquery_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_xquery_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_xquery_primitives.ResolveSuffixMatch

XQUERY_SUFFIXES = repository_xquery_primitives.XQUERY_SUFFIXES
collect_symbols = repository_xquery_primitives.collect_symbols
has_xquery_path_hints = repository_xquery_primitives.has_xquery_path_hints
is_probable_xquery_source = repository_xquery_primitives.is_probable_xquery_source
iter_dependency_entries = repository_xquery_primitives.iter_dependency_entries
iter_reference_entries = repository_xquery_primitives.iter_reference_entries
iter_symbol_entries = repository_xquery_primitives.iter_symbol_entries
module_aliases_for_path = repository_xquery_primitives.module_aliases_for_path
module_name_from_path = repository_xquery_primitives.module_name_from_path
resolve_xquery_target = repository_xquery_primitives.resolve_xquery_target
source_symbol_name_for_line = repository_xquery_primitives.source_symbol_name_for_line


def _extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    imported_bindings: dict[str, _ImportedSymbolBinding] = {}
    seen_dependencies: set[tuple[str | None, str, str, int]] = set()
    for dependency_kind, prefix, target, line_number in iter_dependency_entries(text):
        target_file = resolve_xquery_target(
            current_file=file_path,
            target=target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, prefix, target, line_number)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        target_symbol = module_name_from_path(target_file) if target_file else None
        target_names = (prefix,) if prefix else ()
        if prefix and target_file:
            imported_bindings[prefix] = _ImportedSymbolBinding(
                alias=prefix,
                target_file=target_file,
                target_names=target_names,
            )
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "prefix": prefix,
                        "target": target,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type=dependency_kind,
            )
        )
    return tuple(dependencies), imported_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_xquery_source(path=Path(file_path), text=text):
        return ()
    dependencies, _bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    return dependencies


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
    if not is_probable_xquery_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    dependencies, import_bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols[1:]}
    local_symbol_names = set(symbol_ids_by_name)
    default_source_symbol_id = symbols[0].symbol_id
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()

    for dependency in dependencies:
        if dependency.target_file is None or dependency.target_symbol is None:
            continue
        reference_key = (dependency.target_file, dependency.target_symbol, default_source_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": default_source_symbol_id,
                        "target_file": dependency.target_file,
                        "target_name": dependency.target_symbol,
                    },
                ),
                source_symbol_id=default_source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=(dependency.target_symbol,),
                reference_type="references_symbol",
            )
        )

    for target_name, line_number in iter_reference_entries(
        text,
        local_symbol_names=local_symbol_names,
        imported_prefixes=set(import_bindings),
    ):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        target_file = file_path if target_name in local_symbol_names else None
        target_symbol_id = symbol_ids_by_name.get(target_name) if target_file == file_path else None
        target_names = (target_name,)
        if target_file is None and ":" in target_name:
            prefix = target_name.split(":", 1)[0]
            binding = import_bindings.get(prefix)
            if binding is None:
                continue
            target_file = binding.target_file
            target_names = binding.target_names or (prefix,)
        reference_key = (target_file, target_names[0], source_symbol_id)
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
                        "target_name": target_names[0],
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(references)
