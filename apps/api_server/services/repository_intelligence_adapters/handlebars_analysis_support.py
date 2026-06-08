from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    handlebars_primitives as repository_handlebars_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_handlebars_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_handlebars_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_handlebars_primitives.ResolveSuffixMatch

HANDLEBARS_SUFFIXES = repository_handlebars_primitives.HANDLEBARS_SUFFIXES
collect_symbols = repository_handlebars_primitives.collect_symbols
has_handlebars_path_hints = repository_handlebars_primitives.has_handlebars_path_hints
is_probable_handlebars_source = repository_handlebars_primitives.is_probable_handlebars_source
iter_dependency_entries = repository_handlebars_primitives.iter_dependency_entries
iter_reference_entries = repository_handlebars_primitives.iter_reference_entries
module_aliases_for_path = repository_handlebars_primitives.module_aliases_for_path
module_name_from_path = repository_handlebars_primitives.module_name_from_path
resolve_import = repository_handlebars_primitives.resolve_import
source_symbol_name_for_line = repository_handlebars_primitives.source_symbol_name_for_line


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_handlebars_source(path=Path(file_path), text=text):
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
                target_symbol=Path(target_file).stem if target_file else import_target,
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
    if not is_probable_handlebars_source(path=Path(file_path), text=text):
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
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols}
    module_symbol_id = symbols[0].symbol_id if symbols else None
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
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    for target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line((), line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", module_symbol_id)
        if not source_symbol_id or target_name not in symbol_ids_by_name:
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
                target_symbol_id=symbol_ids_by_name[target_name],
                target_file=file_path,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(references)
