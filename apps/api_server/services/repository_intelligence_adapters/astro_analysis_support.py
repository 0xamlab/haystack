from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    astro_primitives as repository_astro_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_astro_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_astro_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_astro_primitives.ResolveSuffixMatch

ASTRO_SUFFIXES = repository_astro_primitives.ASTRO_SUFFIXES
has_astro_path_hints = repository_astro_primitives.has_astro_path_hints
is_probable_astro_source = repository_astro_primitives.is_probable_astro_source
iter_component_references = repository_astro_primitives.iter_component_references
iter_import_entries = repository_astro_primitives.iter_import_entries
module_aliases_for_path = repository_astro_primitives.module_aliases_for_path
module_name_from_path = repository_astro_primitives.module_name_from_path
normalize_identifier = repository_astro_primitives.normalize_identifier
resolve_import = repository_astro_primitives.resolve_import


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_astro_source(path=Path(file_path), text=text):
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
    if not is_probable_astro_source(path=Path(file_path), text=text):
        return (), (), ()
    module_name = module_name_from_path(file_path)
    symbols = (
        _Symbol(
            symbol_id=stable_identifier("sym", {"file_path": file_path, "symbol_name": module_name}),
            symbol_name=module_name,
            symbol_kind="astro",
            start_line=1,
            end_line=max(1, text.count("\n") + 1),
            parent_symbol_id=None,
            signature=module_name,
        ),
    )
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    module_symbol_id = symbols[0].symbol_id
    imported_targets = {
        str(dependency.target_symbol or "").strip(): dependency.target_file
        for dependency in dependencies
        if str(dependency.target_symbol or "").strip() and dependency.target_file
    }
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str | None]] = set()
    for component_name, _line_number in iter_component_references(text):
        first_segment = component_name.split(".", 1)[0]
        target_file = imported_targets.get(first_segment)
        if not target_file:
            continue
        target_module_name = module_name_from_path(target_file)
        final_segment = component_name.split(".")[-1]
        target_names = tuple(
            name
            for name in {component_name, first_segment, final_segment, target_module_name, Path(target_file).stem}
            if name
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
