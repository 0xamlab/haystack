from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    ballerina_primitives as repository_ballerina_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_ballerina_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_ballerina_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_ballerina_primitives.ResolveSuffixMatch

BALLERINA_SUFFIXES = repository_ballerina_primitives.BALLERINA_SUFFIXES
BALLERINA_CONFIG_BASENAMES = repository_ballerina_primitives.BALLERINA_CONFIG_BASENAMES
clean_import_target = repository_ballerina_primitives.clean_import_target
collect_symbols = repository_ballerina_primitives.collect_symbols
has_ballerina_path_hints = repository_ballerina_primitives.has_ballerina_path_hints
import_alias_for_target = repository_ballerina_primitives.import_alias_for_target
is_probable_ballerina_config = repository_ballerina_primitives.is_probable_ballerina_config
is_probable_ballerina_source = repository_ballerina_primitives.is_probable_ballerina_source
iter_import_entries = repository_ballerina_primitives.iter_import_entries
iter_reference_entries = repository_ballerina_primitives.iter_reference_entries
iter_symbol_entries = repository_ballerina_primitives.iter_symbol_entries
module_aliases_for_path = repository_ballerina_primitives.module_aliases_for_path
module_name_from_path = repository_ballerina_primitives.module_name_from_path
resolve_import = repository_ballerina_primitives.resolve_import
source_symbol_name_for_line = repository_ballerina_primitives.source_symbol_name_for_line
strip_comments = repository_ballerina_primitives.strip_comments


def _extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding], tuple[str, ...]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    imported_target_files: list[str] = []
    seen_dependencies: set[tuple[str | None, str, int]] = set()
    for import_target, alias, line_number in iter_import_entries(
        text,
        stripped_text=stripped_text,
    ):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, line_number)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        if target_file is not None:
            imported_target_files.append(target_file)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=import_target,
                dependency_type="imports",
            )
        )
        for binding_name in (
            alias,
            import_alias_for_target(import_target),
            import_target,
        ):
            normalized_binding = clean_import_target(binding_name or "")
            if not normalized_binding or target_file is None:
                continue
            import_bindings[normalized_binding] = _ImportedSymbolBinding(
                alias=normalized_binding,
                target_file=target_file,
                target_names=(normalized_binding,),
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
    if path.suffix.lower() in BALLERINA_SUFFIXES:
        stripped_text = strip_comments(text)
        if not is_probable_ballerina_source(path=path, text=text, stripped_text=stripped_text):
            return ()
    elif path.name.lower() not in BALLERINA_CONFIG_BASENAMES or not is_probable_ballerina_config(
        path=path,
        text=text,
    ):
        return ()
    else:
        stripped_text = None
    dependencies, _import_bindings, _imported_target_files = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
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
    if path.suffix.lower() in BALLERINA_SUFFIXES:
        stripped_text = strip_comments(text)
        if not is_probable_ballerina_source(path=path, text=text, stripped_text=stripped_text):
            return (), (), ()
    elif path.name.lower() in BALLERINA_CONFIG_BASENAMES:
        if not is_probable_ballerina_config(path=path, text=text):
            return (), (), ()
        return (), (), ()
    else:
        return (), (), ()

    symbols = collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    dependencies, import_bindings, imported_target_files = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    symbol_entries = iter_symbol_entries(text, stripped_text=stripped_text)
    symbol_ids_by_name = {
        symbol.symbol_name: symbol.symbol_id for symbol in symbols if symbol.symbol_kind != "module"
    }
    local_symbol_names = set(symbol_ids_by_name)
    default_source_symbol_id = symbols[0].symbol_id
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()

    for qualifier, target_name, line_number in iter_reference_entries(
        text,
        stripped_text=stripped_text,
    ):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        target_file: str | None = None
        target_symbol_id: str | None = None
        target_names = (target_name,)
        if qualifier is None and target_name in local_symbol_names:
            target_file = file_path
            target_symbol_id = symbol_ids_by_name.get(target_name)
        elif qualifier is not None:
            binding = import_bindings.get(qualifier)
            if binding is not None:
                target_file = binding.target_file
        elif len(imported_target_files) == 1:
            target_file = imported_target_files[0]
        if target_file is None:
            continue
        reference_key = (target_file, target_names[0], source_symbol_id)
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
    return symbols, dependencies, tuple(references)
