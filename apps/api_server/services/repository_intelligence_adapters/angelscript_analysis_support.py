from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    angelscript_primitives as repository_angelscript_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_angelscript_primitives.StableIdentifier
NormalizeRepositoryRelativePath = (
    repository_angelscript_primitives.NormalizeRepositoryRelativePath
)
ResolveSuffixMatch = repository_angelscript_primitives.ResolveSuffixMatch

ANGELSCRIPT_SUFFIXES = repository_angelscript_primitives.ANGELSCRIPT_SUFFIXES
collect_symbols = repository_angelscript_primitives.collect_symbols
has_angelscript_path_hints = repository_angelscript_primitives.has_angelscript_path_hints
is_probable_angelscript_source = repository_angelscript_primitives.is_probable_angelscript_source
iter_dependency_entries = repository_angelscript_primitives.iter_dependency_entries
iter_reference_entries = repository_angelscript_primitives.iter_reference_entries
iter_symbol_entries = repository_angelscript_primitives.iter_symbol_entries
module_aliases_for_path = repository_angelscript_primitives.module_aliases_for_path
module_name_from_path = repository_angelscript_primitives.module_name_from_path
normalize_symbol_name = repository_angelscript_primitives.normalize_symbol_name
resolve_include = repository_angelscript_primitives.resolve_include
resolve_named_target = repository_angelscript_primitives.resolve_named_target
source_symbol_name_for_line = repository_angelscript_primitives.source_symbol_name_for_line
strip_comments = repository_angelscript_primitives.strip_comments


def _resolve_import_target(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    resolved_include = resolve_include(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    if resolved_include is not None:
        return resolved_include
    return resolve_named_target(
        target_name=import_target,
        module_index=module_index,
        resolve_suffix_match=resolve_suffix_match,
    )


def _extract_dependency_bindings(
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
    for dependency_kind, dependency_target, target_symbol, line_number in iter_dependency_entries(
        text
    ):
        resolved_target_file: str | None = None
        normalized_target_symbol = normalize_symbol_name(target_symbol or "")
        if dependency_kind == "include":
            resolved_target_file = resolve_include(
                current_file=file_path,
                import_target=dependency_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if not normalized_target_symbol:
                normalized_target_symbol = PurePosixPath(dependency_target).stem
        elif dependency_kind == "import":
            resolved_target_file = _resolve_import_target(
                current_file=file_path,
                import_target=dependency_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
        elif dependency_kind == "extends":
            resolved_target_file = resolve_named_target(
                target_name=dependency_target,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
        dependency_key = (
            resolved_target_file,
            normalized_target_symbol,
            dependency_kind,
            line_number,
        )
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        if resolved_target_file:
            imported_target_files.append(resolved_target_file)
            if dependency_kind == "include":
                stem_alias = PurePosixPath(resolved_target_file).stem
                import_bindings.setdefault(
                    stem_alias,
                    _ImportedSymbolBinding(
                        alias=stem_alias,
                        target_file=resolved_target_file,
                        target_names=(stem_alias,),
                    ),
                )
        if dependency_kind == "import" and resolved_target_file and normalized_target_symbol:
            import_bindings.setdefault(
                normalized_target_symbol,
                _ImportedSymbolBinding(
                    alias=normalized_target_symbol,
                    target_file=resolved_target_file,
                    target_names=(normalized_target_symbol,),
                ),
            )
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": dependency_target,
                        "symbol": normalized_target_symbol,
                        "kind": dependency_kind,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=resolved_target_file,
                target_symbol=normalized_target_symbol or None,
                dependency_type=dependency_kind,
            )
        )
    return (
        tuple(dependencies),
        import_bindings,
        tuple(dict.fromkeys(imported_target_files)),
    )


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
    if path.suffix.lower() not in ANGELSCRIPT_SUFFIXES or not is_probable_angelscript_source(
        path=path,
        text=text,
    ):
        return ()
    dependencies, _bindings, _imported_target_files = _extract_dependency_bindings(
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
    if path.suffix.lower() not in ANGELSCRIPT_SUFFIXES or not is_probable_angelscript_source(
        path=path,
        text=text,
    ):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    dependencies, import_bindings, imported_target_files = _extract_dependency_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {
        symbol.symbol_name: symbol.symbol_id for symbol in symbols if symbol.symbol_kind != "angelscript"
    }
    default_source_symbol_id = symbols[0].symbol_id
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()

    for dependency in dependencies:
        if dependency.target_file is None or dependency.target_symbol is None:
            continue
        reference_key = (
            dependency.target_file,
            dependency.target_symbol,
            default_source_symbol_id,
        )
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
        if qualifier and qualifier in import_bindings:
            binding = import_bindings[qualifier]
            target_file = binding.target_file
            target_names = (target_name,)
        elif qualifier and qualifier in symbol_ids_by_name:
            target_file = file_path
            target_symbol_id = symbol_ids_by_name.get(target_name)
        elif qualifier:
            target_file = resolve_named_target(
                target_name=qualifier,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            target_names = (target_name,)
        elif target_name in symbol_ids_by_name:
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
