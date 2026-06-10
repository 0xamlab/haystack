from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    al_primitives as repository_al_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_al_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_al_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_al_primitives.ResolveSuffixMatch

_RESERVED_CALL_NAMES = repository_al_primitives._RESERVED_CALL_NAMES
AL_OBJECT_KINDS = repository_al_primitives.AL_OBJECT_KINDS
AL_SUFFIXES = repository_al_primitives.AL_SUFFIXES
clean_object_name = repository_al_primitives.clean_object_name
collect_symbols = repository_al_primitives.collect_symbols
declared_object_entries = repository_al_primitives.declared_object_entries
declared_object_name_from_text = repository_al_primitives.declared_object_name_from_text
has_al_path_hints = repository_al_primitives.has_al_path_hints
is_probable_al_source = repository_al_primitives.is_probable_al_source
iter_dependency_entries = repository_al_primitives.iter_dependency_entries
iter_reference_entries = repository_al_primitives.iter_reference_entries
iter_symbol_entries = repository_al_primitives.iter_symbol_entries
module_aliases_for_path = repository_al_primitives.module_aliases_for_path
module_name_from_path = repository_al_primitives.module_name_from_path
normalize_identifier = repository_al_primitives.normalize_identifier
resolve_object_target = repository_al_primitives.resolve_object_target
source_symbol_name_for_line = repository_al_primitives.source_symbol_name_for_line
strip_comments = repository_al_primitives.strip_comments


def _extract_dependencies(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str]] = set()
    for dependency_kind, dependency_target, line_number in iter_dependency_entries(text):
        target_name = clean_object_name(dependency_target)
        target_file = resolve_object_target(
            dependency_target=dependency_target,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, target_name, dependency_kind)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target_name,
                        "kind": dependency_kind,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name or None,
                dependency_type=dependency_kind,
            )
        )
    return tuple(dependencies)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    del normalize_repository_relative_path
    if not is_probable_al_source(path=Path(file_path), text=text):
        return ()
    return _extract_dependencies(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )


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
    del normalize_repository_relative_path
    if not is_probable_al_source(path=Path(file_path), text=text):
        return (), (), ()

    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    dependencies = _extract_dependencies(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    symbol_entries = iter_symbol_entries(text)
    local_symbol_lookup = {
        symbol.symbol_name: symbol.symbol_id for symbol in symbols if symbol.symbol_kind != "al"
    }
    default_source_symbol_id = symbols[0].symbol_id
    local_symbol_names = set(local_symbol_lookup)
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()

    for owner, target_name, line_number in iter_reference_entries(text):
        if not target_name or target_name in _RESERVED_CALL_NAMES:
            continue
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = local_symbol_lookup.get(source_symbol_name or "", default_source_symbol_id)
        target_file = file_path if target_name in local_symbol_names else None
        target_symbol_id = local_symbol_lookup.get(target_name) if target_file == file_path else None
        if target_file is None and owner:
            target_file = module_index.get(owner)
        if target_file is None:
            continue
        reference_key = (target_file, target_name, source_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        symbol_references.append(
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
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(symbol_references)
