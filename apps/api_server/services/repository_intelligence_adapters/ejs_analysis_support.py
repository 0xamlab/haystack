from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    ejs_primitives as repository_ejs_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_ejs_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_ejs_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_ejs_primitives.ResolveSuffixMatch

EJS_SUFFIXES = repository_ejs_primitives.EJS_SUFFIXES
collect_symbols = repository_ejs_primitives.collect_symbols
has_ejs_path_hints = repository_ejs_primitives.has_ejs_path_hints
is_probable_ejs_source = repository_ejs_primitives.is_probable_ejs_source
iter_dependency_entries = repository_ejs_primitives.iter_dependency_entries
iter_reference_entries = repository_ejs_primitives.iter_reference_entries
module_aliases_for_path = repository_ejs_primitives.module_aliases_for_path
module_name_from_path = repository_ejs_primitives.module_name_from_path
resolve_import = repository_ejs_primitives.resolve_import
source_symbol_name_for_line = repository_ejs_primitives.source_symbol_name_for_line


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_ejs_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str]] = set()
    for dependency_kind, import_target, line_number in iter_dependency_entries(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            dependency_kind=dependency_kind,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, dependency_kind)
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
                        "kind": dependency_kind,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=module_name_from_path(target_file) if target_file else import_target,
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
    if not is_probable_ejs_source(path=Path(file_path), text=text):
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
    module_symbol_id = symbols[0].symbol_id if symbols else None
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols}
    symbol_entries = tuple((symbol.symbol_name, symbol.symbol_kind, symbol.start_line) for symbol in symbols)
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str | None]] = set()
    for dependency in dependencies:
        if not dependency.target_file or not module_symbol_id:
            continue
        target_name = module_name_from_path(dependency.target_file)
        item = (dependency.target_file, target_name, module_symbol_id)
        if item in seen_reference_keys:
            continue
        seen_reference_keys.add(item)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": module_symbol_id,
                        "target_file": dependency.target_file,
                        "target_name": target_name,
                    },
                ),
                source_symbol_id=module_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=(target_name, Path(dependency.target_file).stem),
                reference_type="references_symbol",
            )
        )
    for target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", module_symbol_id)
        target_symbol_id = symbol_ids_by_name.get(target_name)
        if not source_symbol_id or not target_symbol_id:
            continue
        item = (file_path, target_name, source_symbol_id)
        if item in seen_reference_keys:
            continue
        seen_reference_keys.add(item)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": source_symbol_id,
                        "target_file": file_path,
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
    return symbols, dependencies, tuple(references)
