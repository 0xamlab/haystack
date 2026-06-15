from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    twig_primitives as repository_twig_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_twig_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_twig_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_twig_primitives.ResolveSuffixMatch

TWIG_SUFFIXES = repository_twig_primitives.TWIG_SUFFIXES
collect_symbols = repository_twig_primitives.collect_symbols
has_twig_path_hints = repository_twig_primitives.has_twig_path_hints
imported_symbol_bindings = repository_twig_primitives.imported_symbol_bindings
is_probable_twig_source = repository_twig_primitives.is_probable_twig_source
iter_dependency_entries = repository_twig_primitives.iter_dependency_entries
iter_reference_entries = repository_twig_primitives.iter_reference_entries
iter_symbol_entries = repository_twig_primitives.iter_symbol_entries
module_aliases_for_path = repository_twig_primitives.module_aliases_for_path
_imported_symbol_bindings_from_dependency_entries = (
    repository_twig_primitives._imported_symbol_bindings_from_dependency_entries
)
_iter_dependency_entries_from_stripped_text = (
    repository_twig_primitives._iter_dependency_entries_from_stripped_text
)
_iter_reference_entries_from_stripped_text = (
    repository_twig_primitives._iter_reference_entries_from_stripped_text
)
_iter_symbol_entries_from_stripped_text = (
    repository_twig_primitives._iter_symbol_entries_from_stripped_text
)
_prepared_twig_source_text = repository_twig_primitives._prepared_twig_source_text
resolve_import = repository_twig_primitives.resolve_import
source_symbol_name_for_line = repository_twig_primitives.source_symbol_name_for_line


def _extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    dependency_entries: tuple[
        tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int],
        ...,
    ],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    bindings = _imported_symbol_bindings_from_dependency_entries(
        current_file=file_path,
        dependency_entries=dependency_entries,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str]] = set()
    for dependency_kind, import_target, selectors, alias, line_number in dependency_entries:
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, dependency_kind)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        target_symbol = None
        if selectors:
            target_symbol = selectors[0][0]
        elif alias:
            target_symbol = alias
        elif target_file:
            target_symbol = Path(target_file).stem
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
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
    stripped_text = _prepared_twig_source_text(path=Path(file_path), text=text)
    if stripped_text is None:
        return ()
    dependency_entries = _iter_dependency_entries_from_stripped_text(stripped_text)
    dependencies, _bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        dependency_entries=dependency_entries,
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
    stripped_text = _prepared_twig_source_text(path=Path(file_path), text=text)
    if stripped_text is None:
        return (), (), ()
    symbols = collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    dependency_entries = _iter_dependency_entries_from_stripped_text(stripped_text)
    dependencies, import_bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        dependency_entries=dependency_entries,
    )
    symbol_entries = _iter_symbol_entries_from_stripped_text(stripped_text)
    symbol_ids_by_name = {
        symbol.symbol_name: symbol.symbol_id
        for symbol in symbols
        if symbol.symbol_kind != "twig"
    }
    local_symbol_names = set(symbol_ids_by_name)
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()
    for _reference_kind, owner, target_name, line_number in _iter_reference_entries_from_stripped_text(
        stripped_text
    ):
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
