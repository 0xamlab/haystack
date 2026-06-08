from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    asciidoc_primitives as repository_asciidoc_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_asciidoc_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_asciidoc_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_asciidoc_primitives.ResolveSuffixMatch

ASCIIDOC_INDEX_BASENAMES = repository_asciidoc_primitives.ASCIIDOC_INDEX_BASENAMES
ASCIIDOC_SUFFIXES = repository_asciidoc_primitives.ASCIIDOC_SUFFIXES
collect_symbols = repository_asciidoc_primitives.collect_symbols
has_asciidoc_path_hints = repository_asciidoc_primitives.has_asciidoc_path_hints
imported_symbol_bindings = repository_asciidoc_primitives.imported_symbol_bindings
is_probable_asciidoc_source = repository_asciidoc_primitives.is_probable_asciidoc_source
iter_import_entries = repository_asciidoc_primitives.iter_import_entries
iter_reference_entries = repository_asciidoc_primitives.iter_reference_entries
iter_symbol_entries = repository_asciidoc_primitives.iter_symbol_entries
module_aliases_for_path = repository_asciidoc_primitives.module_aliases_for_path
module_name_from_path = repository_asciidoc_primitives.module_name_from_path
normalize_identifier = repository_asciidoc_primitives.normalize_identifier
resolve_import = repository_asciidoc_primitives.resolve_import
source_symbol_name_for_line = repository_asciidoc_primitives.source_symbol_name_for_line
split_reference_target = repository_asciidoc_primitives.split_reference_target


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
    for dependency_type, import_target, line_number in iter_import_entries(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, dependency_type)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        target_path, target_anchor = split_reference_target(import_target)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "kind": dependency_type,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_anchor or normalize_identifier(Path(target_path or import_target).stem),
                dependency_type=dependency_type,
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
    if not is_probable_asciidoc_source(path=Path(file_path), text=text):
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
    if not is_probable_asciidoc_source(path=Path(file_path), text=text):
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
    symbol_ids_by_name = {
        symbol.symbol_name: symbol.symbol_id for symbol in symbols if symbol.symbol_kind != "asciidoc"
    }
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()
    fallback_source_symbol_id = symbols[0].symbol_id

    for _reference_kind, target_name, line_number in iter_reference_entries(text):
        target_path, target_anchor = split_reference_target(target_name)
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", fallback_source_symbol_id)
        target_file: str | None = None
        target_symbol_id: str | None = None
        resolved_target_name = normalize_identifier(target_anchor or target_name)

        if target_path is None and target_anchor and target_anchor in symbol_ids_by_name:
            target_file = file_path
            target_symbol_id = symbol_ids_by_name[target_anchor]
            resolved_target_name = target_anchor
        elif target_path is not None:
            target_file = resolve_import(
                current_file=file_path,
                import_target=target_path,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if target_file is None:
                continue
            resolved_target_name = normalize_identifier(
                target_anchor or Path(target_path).stem or Path(target_file).stem
            )
        else:
            binding = import_bindings.get(resolved_target_name)
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
