from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    erb_primitives as repository_erb_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_erb_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_erb_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_erb_primitives.ResolveSuffixMatch

ERB_SUFFIXES = repository_erb_primitives.ERB_SUFFIXES
collect_symbols = repository_erb_primitives.collect_symbols
has_erb_path_hints = repository_erb_primitives.has_erb_path_hints
is_probable_erb_source = repository_erb_primitives.is_probable_erb_source
iter_dependency_entries = repository_erb_primitives.iter_dependency_entries
iter_reference_entries = repository_erb_primitives.iter_reference_entries
iter_symbol_entries = repository_erb_primitives.iter_symbol_entries
module_aliases_for_path = repository_erb_primitives.module_aliases_for_path
module_name_from_path = repository_erb_primitives.module_name_from_path
normalize_identifier = repository_erb_primitives.normalize_identifier
resolve_import = repository_erb_primitives.resolve_import
source_symbol_name_for_line = repository_erb_primitives.source_symbol_name_for_line
strip_comments = repository_erb_primitives.strip_comments


def _extract_dependencies(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, str]]:
    dependencies: list[_Dependency] = []
    resolved_targets: dict[str, str] = {}
    seen_dependencies: set[tuple[str, str | None, str]] = set()
    for dependency_kind, import_target, line_number in iter_dependency_entries(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            dependency_kind=dependency_kind,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (dependency_kind, target_file, import_target)
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
                target_symbol=(
                    module_name_from_path(target_file)
                    if target_file is not None
                    else normalize_identifier(import_target)
                ),
                dependency_type=dependency_kind,
            )
        )
        if target_file is not None:
            resolved_targets[import_target] = target_file
    return tuple(dependencies), resolved_targets


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_erb_source(path=Path(file_path), text=text):
        return ()
    dependencies, _resolved_targets = _extract_dependencies(
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
    if not is_probable_erb_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    dependencies, resolved_targets = _extract_dependencies(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {
        symbol.symbol_name: symbol.symbol_id for symbol in symbols if symbol.symbol_kind != "erb"
    }
    root_symbol_id = symbols[0].symbol_id if symbols else None
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str | None]] = set()
    for reference_kind, target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", root_symbol_id)
        target_file = None
        target_symbol_id = None
        resolved_target_name = target_name
        if reference_kind == "section":
            target_file = file_path if target_name in symbol_ids_by_name else None
            target_symbol_id = symbol_ids_by_name.get(target_name)
        else:
            target_file = resolved_targets.get(target_name)
            if target_file is not None:
                resolved_target_name = module_name_from_path(target_file) or target_name
        reference_key = (target_file, resolved_target_name, source_symbol_id)
        if source_symbol_id is None or reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        references.append(
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
    return symbols, dependencies, tuple(references)
