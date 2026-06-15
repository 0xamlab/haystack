from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    tex_primitives as repository_tex_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_tex_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_tex_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_tex_primitives.ResolveSuffixMatch

TEX_CONFIG_BASENAMES = repository_tex_primitives.TEX_CONFIG_BASENAMES
TEX_SUFFIXES = repository_tex_primitives.TEX_SUFFIXES
collect_symbols = repository_tex_primitives.collect_symbols
has_tex_path_hints = repository_tex_primitives.has_tex_path_hints
imported_symbol_bindings = repository_tex_primitives.imported_symbol_bindings
is_probable_tex_config = repository_tex_primitives.is_probable_tex_config
is_probable_tex_source = repository_tex_primitives.is_probable_tex_source
iter_import_entries = repository_tex_primitives.iter_import_entries
iter_reference_entries = repository_tex_primitives.iter_reference_entries
iter_symbol_entries = repository_tex_primitives.iter_symbol_entries
module_aliases_for_path = repository_tex_primitives.module_aliases_for_path
module_name_from_path = repository_tex_primitives.module_name_from_path
normalize_identifier = repository_tex_primitives.normalize_identifier
provided_module_name = repository_tex_primitives.provided_module_name
resolve_import = repository_tex_primitives.resolve_import
source_symbol_name_for_line = repository_tex_primitives.source_symbol_name_for_line
strip_comments = repository_tex_primitives.strip_comments
_prepared_tex_source_text = repository_tex_primitives._prepared_tex_source_text
_iter_import_entries_from_stripped_text = repository_tex_primitives._iter_import_entries_from_stripped_text
_imported_symbol_bindings_from_import_entries = (
    repository_tex_primitives._imported_symbol_bindings_from_import_entries
)
_iter_reference_entries_from_stripped_text = (
    repository_tex_primitives._iter_reference_entries_from_stripped_text
)
_iter_symbol_entries_from_stripped_text = repository_tex_primitives._iter_symbol_entries_from_stripped_text


def _extract_import_bindings(
    *,
    file_path: str,
    stripped_text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    import_entries = _iter_import_entries_from_stripped_text(stripped_text)
    bindings = _imported_symbol_bindings_from_import_entries(
        current_file=file_path,
        import_entries=import_entries,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str]] = set()
    for dependency_type, import_target, line_number in import_entries:
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
                target_symbol=PurePosixPath(import_target).stem or None,
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
    stripped_text = _prepared_tex_source_text(path=Path(file_path), text=text)
    if stripped_text is None:
        return ()
    dependencies, _bindings = _extract_import_bindings(
        file_path=file_path,
        stripped_text=stripped_text,
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
    stripped_text = _prepared_tex_source_text(path=Path(file_path), text=text)
    if stripped_text is None:
        return (), (), ()
    symbols = collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    dependencies, import_bindings = _extract_import_bindings(
        file_path=file_path,
        stripped_text=stripped_text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    symbol_entries = _iter_symbol_entries_from_stripped_text(stripped_text)
    symbol_ids_by_name = {
        symbol.symbol_name: symbol.symbol_id
        for symbol in symbols
        if symbol.symbol_kind != "tex"
    }
    local_symbol_names = set(symbol_ids_by_name)
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()
    fallback_source_symbol_id = symbols[0].symbol_id

    for _reference_kind, target_name, line_number in _iter_reference_entries_from_stripped_text(
        stripped_text
    ):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", fallback_source_symbol_id)
        target_file = file_path if target_name in local_symbol_names else None
        target_symbol_id = symbol_ids_by_name.get(target_name) if target_file == file_path else None
        resolved_target_name = target_name
        if target_file is None:
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
