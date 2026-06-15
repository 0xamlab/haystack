from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    vcl_primitives as repository_vcl_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_vcl_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_vcl_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_vcl_primitives.ResolveSuffixMatch

VCL_SUFFIXES = repository_vcl_primitives.VCL_SUFFIXES
collect_symbols = repository_vcl_primitives.collect_symbols
has_vcl_path_hints = repository_vcl_primitives.has_vcl_path_hints
is_probable_vcl_source = repository_vcl_primitives.is_probable_vcl_source
iter_dependency_entries = repository_vcl_primitives.iter_dependency_entries
iter_reference_entries = repository_vcl_primitives.iter_reference_entries
iter_symbol_entries = repository_vcl_primitives.iter_symbol_entries
module_aliases_for_path = repository_vcl_primitives.module_aliases_for_path
module_name_from_path = repository_vcl_primitives.module_name_from_path
source_symbol_name_for_line = repository_vcl_primitives.source_symbol_name_for_line
strip_comments = repository_vcl_primitives.strip_comments


def _resolve_include_target(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_repository_relative_path(import_target)
    current_dir_target = normalize_repository_relative_path(
        str(PurePosixPath(current_file).parent / import_target)
    )
    candidates = tuple(
        candidate
        for candidate in (normalized_target, current_dir_target)
        if candidate
    )
    for candidate in candidates:
        resolved = module_index.get(candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=candidates)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_vcl_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependency_keys: set[tuple[str | None, str]] = set()
    for import_target, line_number in iter_dependency_entries(text):
        target_file = _resolve_include_target(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
        if dependency_key in seen_dependency_keys:
            continue
        seen_dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "line": line_number,
                        "type": "include",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=Path(import_target).stem or None,
                dependency_type="include",
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
    if not is_probable_vcl_source(path=Path(file_path), text=text):
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
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols[1:]}
    default_source_symbol_id = symbols[0].symbol_id
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str]] = set()
    for target_name, line_number in iter_reference_entries(text, local_symbol_names=set(symbol_ids_by_name)):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        reference_key = (target_name, source_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "line": line_number,
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
