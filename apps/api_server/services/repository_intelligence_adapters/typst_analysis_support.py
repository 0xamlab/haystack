from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    typst_primitives as repository_typst_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_typst_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_typst_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_typst_primitives.ResolveSuffixMatch

TYPST_CONFIG_BASENAMES = repository_typst_primitives.TYPST_CONFIG_BASENAMES
TYPST_SUFFIXES = repository_typst_primitives.TYPST_SUFFIXES
collect_symbols = repository_typst_primitives.collect_symbols
has_typst_path_hints = repository_typst_primitives.has_typst_path_hints
imported_symbol_bindings = repository_typst_primitives.imported_symbol_bindings
include_statements = repository_typst_primitives.include_statements
is_probable_typst_config = repository_typst_primitives.is_probable_typst_config
is_probable_typst_source = repository_typst_primitives.is_probable_typst_source
iter_import_entries = repository_typst_primitives.iter_import_entries
iter_reference_entries = repository_typst_primitives.iter_reference_entries
iter_symbol_entries = repository_typst_primitives.iter_symbol_entries
module_aliases_for_path = repository_typst_primitives.module_aliases_for_path
module_name_from_path = repository_typst_primitives.module_name_from_path
normalize_identifier = repository_typst_primitives.normalize_identifier
resolve_import = repository_typst_primitives.resolve_import
source_symbol_name_for_line = repository_typst_primitives.source_symbol_name_for_line
strip_comments = repository_typst_primitives.strip_comments


def _extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    bindings = imported_symbol_bindings(
        current_file=file_path,
        text=text,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str]] = set()
    for include_target, line_number in include_statements(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=include_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, include_target, "includes")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
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
                target_symbol=PurePosixPath(include_target).stem or None,
                dependency_type="includes",
            )
        )
    for import_target, selectors, alias, line_number in iter_import_entries(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, "imports")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        target_symbol = None
        if selectors:
            target_symbol = selectors[0][0]
        elif alias:
            target_symbol = alias
        else:
            target_symbol = PurePosixPath(import_target).stem or None
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
                target_symbol=target_symbol,
                dependency_type="imports",
            )
        )
    return tuple(dependencies), bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_typst_source(path=Path(file_path), text=text):
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
    if not is_probable_typst_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    dependencies, import_bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {
        symbol.symbol_name: symbol.symbol_id
        for symbol in symbols
        if symbol.symbol_kind != "typst"
    }
    local_symbol_names = set(symbol_ids_by_name)
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()

    for _reference_kind, owner, target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", symbols[0].symbol_id)
        target_file = file_path if target_name in local_symbol_names else None
        target_symbol_id = symbol_ids_by_name.get(target_name) if target_file == file_path else None
        resolved_target_name = target_name
        if target_file is None:
            if owner:
                binding = import_bindings.get(owner)
                if binding is None:
                    continue
                target_file = binding.target_file
            else:
                binding = import_bindings.get(target_name)
                if binding is None:
                    continue
                target_file = binding.target_file
                if binding.target_names:
                    resolved_target_name = binding.target_names[0]
        reference_key = (target_file, resolved_target_name, source_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": source_symbol_id,
                        "target_file": target_file,
                        "target_name": resolved_target_name,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=(resolved_target_name,),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(symbol_references)
