from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    common_workflow_language_primitives as repository_common_workflow_language_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_common_workflow_language_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_common_workflow_language_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_common_workflow_language_primitives.ResolveSuffixMatch

COMMON_WORKFLOW_LANGUAGE_SUFFIXES = (
    repository_common_workflow_language_primitives.COMMON_WORKFLOW_LANGUAGE_SUFFIXES
)
clean_import_target = repository_common_workflow_language_primitives.clean_import_target
collect_symbols = repository_common_workflow_language_primitives.collect_symbols
has_common_workflow_language_path_hints = (
    repository_common_workflow_language_primitives.has_common_workflow_language_path_hints
)
is_probable_common_workflow_language_source = (
    repository_common_workflow_language_primitives.is_probable_common_workflow_language_source
)
iter_dependency_entries = repository_common_workflow_language_primitives.iter_dependency_entries
iter_symbol_entries = repository_common_workflow_language_primitives.iter_symbol_entries
module_aliases_for_path = repository_common_workflow_language_primitives.module_aliases_for_path
module_name_from_path = repository_common_workflow_language_primitives.module_name_from_path
resolve_import = repository_common_workflow_language_primitives.resolve_import
strip_comments = repository_common_workflow_language_primitives.strip_comments


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_common_workflow_language_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str, int]] = set()
    for dependency_kind, import_target, line_number in iter_dependency_entries(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, dependency_kind, line_number)
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
                target_symbol=module_name_from_path(target_file) if target_file else None,
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
    if not is_probable_common_workflow_language_source(path=Path(file_path), text=text):
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
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": default_source_symbol_id,
                        "target_file": dependency.target_file,
                        "target_name": dependency.target_symbol,
                    },
                ),
                source_symbol_id=default_source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=(dependency.target_symbol,),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(symbol_references)
