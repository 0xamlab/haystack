from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    smali_primitives as repository_smali_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_smali_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_smali_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_smali_primitives.ResolveSuffixMatch

SMALI_SUFFIXES = repository_smali_primitives.SMALI_SUFFIXES
collect_symbols = repository_smali_primitives.collect_symbols
descriptor_to_class_name = repository_smali_primitives.descriptor_to_class_name
descriptor_to_dotted_name = repository_smali_primitives.descriptor_to_dotted_name
descriptor_to_path = repository_smali_primitives.descriptor_to_path
has_smali_path_hints = repository_smali_primitives.has_smali_path_hints
is_probable_smali_source = repository_smali_primitives.is_probable_smali_source
iter_dependency_entries = repository_smali_primitives.iter_dependency_entries
iter_reference_entries = repository_smali_primitives.iter_reference_entries
iter_symbol_entries = repository_smali_primitives.iter_symbol_entries
module_aliases_for_path = repository_smali_primitives.module_aliases_for_path
module_name_from_path = repository_smali_primitives.module_name_from_path
resolve_descriptor = repository_smali_primitives.resolve_descriptor
source_symbol_name_for_line = repository_smali_primitives.source_symbol_name_for_line
strip_comments = repository_smali_primitives.strip_comments


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_smali_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str, int]] = set()
    for dependency_kind, descriptor, line_number in iter_dependency_entries(text):
        target_file = resolve_descriptor(
            descriptor=descriptor,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_symbol = descriptor_to_class_name(descriptor)
        dependency_key = (target_file, descriptor, dependency_kind, line_number)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": descriptor,
                        "kind": dependency_kind,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type=dependency_kind,
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
    if not is_probable_smali_source(path=Path(file_path), text=text):
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
    default_source_symbol_id = symbols[0].symbol_id
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()

    for descriptor, target_name, line_number in iter_reference_entries(text):
        target_file = resolve_descriptor(
            descriptor=descriptor,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        target_symbol_id = None
        if target_file == file_path:
            target_symbol_id = symbol_ids_by_name.get(target_name)
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
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=(target_name, descriptor_to_class_name(descriptor)),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(references)
