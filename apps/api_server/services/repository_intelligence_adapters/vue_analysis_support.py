from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    vue_primitives as repository_vue_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_vue_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_vue_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_vue_primitives.ResolveSuffixMatch

VUE_SUFFIXES = repository_vue_primitives.VUE_SUFFIXES
collect_symbols = repository_vue_primitives.collect_symbols
has_vue_path_hints = repository_vue_primitives.has_vue_path_hints
is_probable_vue_source = repository_vue_primitives.is_probable_vue_source
iter_import_entries = repository_vue_primitives.iter_import_entries
iter_template_component_references = repository_vue_primitives.iter_template_component_references
module_aliases_for_path = repository_vue_primitives.module_aliases_for_path
module_name_from_path = repository_vue_primitives.module_name_from_path
resolve_import = repository_vue_primitives.resolve_import


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_vue_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str]] = set()
    for binding_name, import_target, line_number in iter_import_entries(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, binding_name, "imports")
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
                        "binding": binding_name,
                        "line": line_number,
                        "kind": "imports",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=binding_name,
                dependency_type="imports",
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
    if not is_probable_vue_source(path=Path(file_path), text=text):
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
    imported_targets = {
        str(dependency.target_symbol or "").strip(): dependency.target_file
        for dependency in dependencies
        if str(dependency.target_symbol or "").strip() and dependency.target_file
    }
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str | None]] = set()
    for component_name, _line_number in iter_template_component_references(text):
        target_file = imported_targets.get(component_name)
        if not module_symbol_id or not target_file:
            continue
        target_module_name = module_name_from_path(target_file)
        target_names = tuple(
            name for name in {component_name, target_module_name, Path(target_file).stem} if name
        )
        reference_key = (target_file, component_name, module_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": module_symbol_id,
                        "target_file": target_file,
                        "target_name": component_name,
                    },
                ),
                source_symbol_id=module_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(references)
