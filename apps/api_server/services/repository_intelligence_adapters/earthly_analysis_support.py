from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    earthly_primitives as repository_earthly_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_earthly_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_earthly_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_earthly_primitives.ResolveSuffixMatch

EARTHLY_BASENAMES = repository_earthly_primitives.EARTHLY_BASENAMES
collect_symbols = repository_earthly_primitives.collect_symbols
has_earthly_path_hints = repository_earthly_primitives.has_earthly_path_hints
is_probable_earthly_source = repository_earthly_primitives.is_probable_earthly_source
iter_import_entries = repository_earthly_primitives.iter_import_entries
iter_target_reference_entries = repository_earthly_primitives.iter_target_reference_entries
module_aliases_for_path = repository_earthly_primitives.module_aliases_for_path
module_name_from_path = repository_earthly_primitives.module_name_from_path
resolve_import = repository_earthly_primitives.resolve_import
resolve_target_reference = repository_earthly_primitives.resolve_target_reference
strip_comments = repository_earthly_primitives.strip_comments


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_earthly_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    import_aliases: dict[str, str] = {}
    seen_dependencies: set[tuple[str | None, str | None, str, int]] = set()
    for import_alias, import_target, line_number in iter_import_entries(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is not None:
            import_aliases[import_alias] = target_file
        dependency_key = (target_file, import_alias, "imports", line_number)
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
                        "alias": import_alias,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=module_name_from_path(target_file) if target_file else None,
                dependency_type="imports",
            )
        )
    for dependency_kind, target_reference, line_number in iter_target_reference_entries(text):
        target_file, target_symbol = resolve_target_reference(
            current_file=file_path,
            target_reference=target_reference,
            module_index=module_index,
            import_aliases=import_aliases,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, target_symbol, dependency_kind, line_number)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target_reference,
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
    if not is_probable_earthly_source(path=Path(file_path), text=text):
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
    default_source_symbol_id = symbols[0].symbol_id
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str]] = set()
    for dependency in dependencies:
        if dependency.target_file is None or dependency.target_symbol is None:
            continue
        reference_key = (dependency.target_file, dependency.target_symbol)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        source_symbol_id = symbol_ids_by_name.get(dependency.target_symbol, default_source_symbol_id)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": source_symbol_id,
                        "target_file": dependency.target_file,
                        "target_name": dependency.target_symbol,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=(dependency.target_symbol,),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(symbol_references)
