from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    protobuf_primitives as repository_protobuf_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_protobuf_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_protobuf_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_protobuf_primitives.ResolveSuffixMatch

PROTOBUF_CONFIG_BASENAMES = repository_protobuf_primitives.PROTOBUF_CONFIG_BASENAMES
PROTOBUF_SUFFIXES = repository_protobuf_primitives.PROTOBUF_SUFFIXES
collect_symbols = repository_protobuf_primitives.collect_symbols
has_protobuf_path_hints = repository_protobuf_primitives.has_protobuf_path_hints
imported_symbol_bindings = repository_protobuf_primitives.imported_symbol_bindings
is_probable_protobuf_config = repository_protobuf_primitives.is_probable_protobuf_config
is_probable_protobuf_source = repository_protobuf_primitives.is_probable_protobuf_source
iter_import_entries = repository_protobuf_primitives.iter_import_entries
iter_reference_entries = repository_protobuf_primitives.iter_reference_entries
iter_symbol_entries = repository_protobuf_primitives.iter_symbol_entries
module_aliases_for_path = repository_protobuf_primitives.module_aliases_for_path
module_name_from_path = repository_protobuf_primitives.module_name_from_path
normalize_identifier = repository_protobuf_primitives.normalize_identifier
package_name_from_text = repository_protobuf_primitives.package_name_from_text
resolve_import = repository_protobuf_primitives.resolve_import
source_symbol_name_for_line = repository_protobuf_primitives.source_symbol_name_for_line
strip_comments = repository_protobuf_primitives.strip_comments


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
    seen_dependencies: set[tuple[str | None, str]] = set()
    for import_target, line_number in iter_import_entries(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
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
                target_symbol=Path(import_target).stem or None,
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
    if not is_probable_protobuf_source(path=Path(file_path), text=text):
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
    if not is_probable_protobuf_source(path=Path(file_path), text=text):
        return (), (), ()
    package_name = package_name_from_text(text)
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
        if symbol.symbol_kind != "protobuf"
    }
    local_symbol_names = set(symbol_ids_by_name)
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, tuple[str, ...], str]] = set()

    for owner, target_name, qualified_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", symbols[0].symbol_id)
        target_names = tuple(
            name
            for name in dict.fromkeys(
                [target_name, qualified_name or ""]
            )
            if name
        )
        target_file = None
        target_symbol_id = None
        owner_matches_local_package = owner is not None and owner == package_name
        if target_name in local_symbol_names and (owner is None or owner_matches_local_package):
            target_file = file_path
            target_symbol_id = symbol_ids_by_name.get(target_name)
        else:
            binding = None
            if qualified_name:
                binding = import_bindings.get(qualified_name)
            if binding is None and owner:
                binding = import_bindings.get(owner)
            if binding is None:
                binding = import_bindings.get(target_name)
            if binding is None:
                if target_name in local_symbol_names:
                    target_file = file_path
                    target_symbol_id = symbol_ids_by_name.get(target_name)
                else:
                    continue
            else:
                target_file = binding.target_file
                if binding.target_names:
                    target_names = tuple(
                        name
                        for name in dict.fromkeys((*binding.target_names, *target_names))
                        if name
                    )
        reference_key = (target_file, target_names, source_symbol_id)
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
                        "target_names": target_names,
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
    return symbols, dependencies, tuple(symbol_references)
