from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    qsharp_primitives as repository_qsharp_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_qsharp_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_qsharp_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_qsharp_primitives.ResolveSuffixMatch

QSHARP_SUFFIXES = repository_qsharp_primitives.QSHARP_SUFFIXES
QSHARP_CONFIG_BASENAMES = repository_qsharp_primitives.QSHARP_CONFIG_BASENAMES
clean_import_target = repository_qsharp_primitives.clean_import_target
collect_symbols = repository_qsharp_primitives.collect_symbols
has_qsharp_path_hints = repository_qsharp_primitives.has_qsharp_path_hints
is_probable_qsharp_config = repository_qsharp_primitives.is_probable_qsharp_config
is_probable_qsharp_source = repository_qsharp_primitives.is_probable_qsharp_source
iter_dependency_entries = repository_qsharp_primitives.iter_dependency_entries
iter_namespace_entries = repository_qsharp_primitives.iter_namespace_entries
iter_reference_entries = repository_qsharp_primitives.iter_reference_entries
iter_symbol_entries = repository_qsharp_primitives.iter_symbol_entries
module_aliases_for_path = repository_qsharp_primitives.module_aliases_for_path
module_name_from_path = repository_qsharp_primitives.module_name_from_path
primary_namespace_name = repository_qsharp_primitives.primary_namespace_name
resolve_import = repository_qsharp_primitives.resolve_import
source_symbol_name_for_line = repository_qsharp_primitives.source_symbol_name_for_line
strip_comments = repository_qsharp_primitives.strip_comments


def _extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding], tuple[str, ...]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    imported_target_files: list[str] = []
    seen_dependencies: set[tuple[str | None, str, str, int]] = set()
    for dependency_kind, import_target, binding_alias, line_number in iter_dependency_entries(text):
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
        target_symbol = import_target or None
        if target_file:
            imported_target_files.append(target_file)
            for alias in (
                binding_alias,
                import_target.rsplit(".", 1)[-1],
                import_target,
            ):
                normalized_alias = clean_import_target(alias or "")
                if not normalized_alias:
                    continue
                import_bindings[normalized_alias] = _ImportedSymbolBinding(
                    alias=normalized_alias,
                    target_file=target_file,
                    target_names=(normalized_alias,),
                )
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
                target_symbol=target_symbol,
                dependency_type=dependency_kind,
            )
        )
    return tuple(dependencies), import_bindings, tuple(dict.fromkeys(imported_target_files))


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    path = Path(file_path)
    if path.suffix.lower() in QSHARP_SUFFIXES:
        if not is_probable_qsharp_source(path=path, text=text):
            return ()
    elif path.name.lower() not in QSHARP_CONFIG_BASENAMES or not is_probable_qsharp_config(
        path=path, text=text
    ):
        return ()
    dependencies, _bindings, _imported_target_files = _extract_import_bindings(
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
    path = Path(file_path)
    if path.suffix.lower() in QSHARP_SUFFIXES:
        if not is_probable_qsharp_source(path=path, text=text):
            return (), (), ()
    elif path.name.lower() in QSHARP_CONFIG_BASENAMES:
        if not is_probable_qsharp_config(path=path, text=text):
            return (), (), ()
        return (), (), ()
    else:
        return (), (), ()

    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    dependencies, import_bindings, imported_target_files = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {
        symbol.symbol_name: symbol.symbol_id for symbol in symbols if symbol.symbol_kind != "qsharp"
    }
    local_symbol_names = set(symbol_ids_by_name)
    default_source_symbol_id = symbols[0].symbol_id
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()

    for dependency in dependencies:
        if dependency.target_file is None or dependency.target_symbol is None:
            continue
        reference_key = (dependency.target_file, dependency.target_symbol, default_source_symbol_id)
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

    for qualifier, target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        target_file = file_path if target_name in local_symbol_names else None
        target_symbol_id = symbol_ids_by_name.get(target_name) if target_file == file_path else None
        target_names = (target_name,)
        if target_file is None and qualifier:
            binding = import_bindings.get(qualifier)
            if binding is not None:
                target_file = binding.target_file
                target_names = (target_name,)
        if target_file is None and qualifier is None and len(imported_target_files) == 1:
            target_file = imported_target_files[0]
            target_names = (target_name,)
        if target_file is None:
            continue
        reference_key = (target_file, target_names[0], source_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "line": line_number,
                        "source_symbol_id": source_symbol_id,
                        "target_file": target_file,
                        "target_name": target_names[0],
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(symbol_references)
