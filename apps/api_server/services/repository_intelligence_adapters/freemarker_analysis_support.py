from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    freemarker_primitives as repository_freemarker_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_freemarker_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_freemarker_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_freemarker_primitives.ResolveSuffixMatch

FREEMARKER_SUFFIXES = repository_freemarker_primitives.FREEMARKER_SUFFIXES
collect_symbols = repository_freemarker_primitives.collect_symbols
has_freemarker_path_hints = repository_freemarker_primitives.has_freemarker_path_hints
is_probable_freemarker_source = repository_freemarker_primitives.is_probable_freemarker_source
iter_dependency_entries = repository_freemarker_primitives.iter_dependency_entries
iter_reference_entries = repository_freemarker_primitives.iter_reference_entries
iter_symbol_entries = repository_freemarker_primitives.iter_symbol_entries
module_aliases_for_path = repository_freemarker_primitives.module_aliases_for_path
module_name_from_path = repository_freemarker_primitives.module_name_from_path
normalize_identifier = repository_freemarker_primitives.normalize_identifier
resolve_import = repository_freemarker_primitives.resolve_import
source_symbol_name_for_line = repository_freemarker_primitives.source_symbol_name_for_line
strip_comments = repository_freemarker_primitives.strip_comments


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for dependency_kind, import_target, alias, _line_number in iter_dependency_entries(text):
        if dependency_kind != "import":
            continue
        target_file = resolve_import(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None:
            continue
        alias_name = alias or Path(target_file).stem
        if not alias_name:
            continue
        bindings.setdefault(
            alias_name,
            _ImportedSymbolBinding(
                alias=alias_name,
                target_file=target_file,
                target_names=(),
            ),
        )
    return bindings


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
    for dependency_kind, import_target, alias, line_number in iter_dependency_entries(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
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
                target_symbol=alias or (Path(target_file).stem if target_file else None),
                dependency_type=dependency_kind,
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
    if not is_probable_freemarker_source(path=Path(file_path), text=text):
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
    if not is_probable_freemarker_source(path=Path(file_path), text=text):
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
        symbol.symbol_name: symbol.symbol_id
        for symbol in symbols
        if symbol.symbol_kind != "freemarker"
    }
    local_symbol_names = set(symbol_ids_by_name)
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()
    for _reference_kind, owner, target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", symbols[0].symbol_id)
        if owner:
            binding = import_bindings.get(owner)
            if binding is None:
                continue
            target_file = binding.target_file
            target_symbol_id = None
            resolved_target_name = target_name
        elif target_name in local_symbol_names:
            target_file = file_path
            target_symbol_id = symbol_ids_by_name.get(target_name)
            resolved_target_name = target_name
        else:
            continue
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
