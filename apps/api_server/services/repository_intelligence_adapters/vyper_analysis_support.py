from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    vyper_primitives as repository_vyper_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_vyper_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_vyper_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_vyper_primitives.ResolveSuffixMatch

VYPER_SUFFIXES = repository_vyper_primitives.VYPER_SUFFIXES
clean_import_target = repository_vyper_primitives.clean_import_target
collect_symbols = repository_vyper_primitives.collect_symbols
has_vyper_path_hints = repository_vyper_primitives.has_vyper_path_hints
is_probable_vyper_source = repository_vyper_primitives.is_probable_vyper_source
iter_dependency_entries = repository_vyper_primitives.iter_dependency_entries
iter_reference_entries = repository_vyper_primitives.iter_reference_entries
iter_symbol_entries = repository_vyper_primitives.iter_symbol_entries
module_aliases_for_path = repository_vyper_primitives.module_aliases_for_path
module_name_from_path = repository_vyper_primitives.module_name_from_path
resolve_dependency_target = repository_vyper_primitives.resolve_dependency_target
resolve_module_import = repository_vyper_primitives.resolve_module_import
resolve_symbol_import = repository_vyper_primitives.resolve_symbol_import
source_symbol_name_for_line = repository_vyper_primitives.source_symbol_name_for_line
strip_comments = repository_vyper_primitives.strip_comments


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
    for dependency_kind, dependency_target, binding_alias, imported_symbol, line_number in (
        iter_dependency_entries(text)
    ):
        target_file: str | None = None
        target_names: tuple[str, ...] = ()
        if dependency_kind == "import":
            target_file = resolve_module_import(
                current_file=file_path,
                import_target=dependency_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            target_names = (dependency_target.rsplit(".", 1)[-1],)
        elif dependency_kind == "from_import":
            target_file, target_names = resolve_symbol_import(
                current_file=file_path,
                module_target=dependency_target,
                symbol_name=imported_symbol or "",
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
        else:
            target_file, resolved_symbol = resolve_dependency_target(
                current_file=file_path,
                dependency_target=dependency_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            target_names = (resolved_symbol,) if resolved_symbol else ()
        target_symbol = target_names[0] if target_names else dependency_target.rsplit(".", 1)[-1]
        dependency_key = (target_file, target_symbol, dependency_kind, line_number)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        if target_file:
            imported_target_files.append(target_file)
        if dependency_kind == "import" and target_file:
            alias_name = clean_import_target(binding_alias or target_symbol)
            if alias_name:
                import_bindings[alias_name] = _ImportedSymbolBinding(
                    alias=alias_name,
                    target_file=target_file,
                    target_names=target_names or (target_symbol,),
                )
        elif dependency_kind == "from_import" and target_file:
            alias_name = clean_import_target(binding_alias or imported_symbol or target_symbol)
            if alias_name:
                import_bindings[alias_name] = _ImportedSymbolBinding(
                    alias=alias_name,
                    target_file=target_file,
                    target_names=target_names or (target_symbol,),
                )
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": dependency_target,
                        "symbol": target_symbol,
                        "kind": dependency_kind,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol or None,
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
    if path.suffix.lower() not in VYPER_SUFFIXES or not is_probable_vyper_source(path=path, text=text):
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
    if path.suffix.lower() not in VYPER_SUFFIXES or not is_probable_vyper_source(path=path, text=text):
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
        symbol.symbol_name: symbol.symbol_id for symbol in symbols if symbol.symbol_kind != "vyper"
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
        target_file: str | None = None
        target_symbol_id: str | None = None
        target_names = (target_name,)
        if qualifier == "self" and target_name in local_symbol_names:
            target_file = file_path
            target_symbol_id = symbol_ids_by_name.get(target_name)
        elif qualifier and qualifier in import_bindings:
            target_file = import_bindings[qualifier].target_file
            target_names = (target_name,)
        elif qualifier:
            target_file = module_index.get(qualifier)
            if target_file is not None:
                target_names = (target_name,)
        elif target_name in local_symbol_names:
            target_file = file_path
            target_symbol_id = symbol_ids_by_name.get(target_name)
        elif target_name in import_bindings:
            binding = import_bindings[target_name]
            target_file = binding.target_file
            target_names = binding.target_names
        elif len(imported_target_files) == 1:
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
