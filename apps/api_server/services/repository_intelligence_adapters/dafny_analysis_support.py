from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    dafny_primitives as repository_dafny_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_dafny_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_dafny_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_dafny_primitives.ResolveSuffixMatch

DAFNY_SUFFIXES = repository_dafny_primitives.DAFNY_SUFFIXES
candidate_module_keys = repository_dafny_primitives.candidate_module_keys
collect_symbols = repository_dafny_primitives.collect_symbols
has_dafny_path_hints = repository_dafny_primitives.has_dafny_path_hints
is_probable_dafny_source = repository_dafny_primitives.is_probable_dafny_source
iter_import_entries = repository_dafny_primitives.iter_import_entries
iter_include_entries = repository_dafny_primitives.iter_include_entries
iter_module_entries = repository_dafny_primitives.iter_module_entries
iter_reference_entries = repository_dafny_primitives.iter_reference_entries
iter_symbol_entries = repository_dafny_primitives.iter_symbol_entries
module_aliases_for_path = repository_dafny_primitives.module_aliases_for_path
module_name_from_path = repository_dafny_primitives.module_name_from_path
resolve_import_module = repository_dafny_primitives.resolve_import_module
resolve_include = repository_dafny_primitives.resolve_include
source_symbol_name_for_line = repository_dafny_primitives.source_symbol_name_for_line
strip_comments = repository_dafny_primitives.strip_comments


def _extract_dependency_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    imported_bindings: dict[str, _ImportedSymbolBinding] = {}
    seen_dependencies: set[tuple[str | None, str, int, str]] = set()
    for include_target, line_number in iter_include_entries(text):
        target_file = resolve_include(
            include_target,
            file_path,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_name = Path(target_file).stem if target_file else Path(include_target).stem
        dependency_key = (target_file, include_target, line_number, "includes")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        if target_file and target_name:
            imported_bindings.setdefault(
                target_name,
                _ImportedSymbolBinding(
                    alias=target_name,
                    target_file=target_file,
                    target_names=(target_name,),
                ),
            )
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": include_target,
                        "kind": "includes",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="includes",
            )
        )
    for import_target, alias, line_number in iter_import_entries(text):
        target_file = resolve_import_module(
            import_target,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_name = alias or import_target.rsplit(".", 1)[-1]
        dependency_key = (target_file, import_target, line_number, "imports")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        if target_file and target_name:
            imported_bindings.setdefault(
                target_name,
                _ImportedSymbolBinding(
                    alias=target_name,
                    target_file=target_file,
                    target_names=(target_name,),
                ),
            )
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "kind": "imports",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="imports",
            )
        )
    return tuple(dependencies), imported_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_dafny_source(path=Path(file_path), text=text):
        return ()
    dependencies, _bindings = _extract_dependency_bindings(
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
    if not is_probable_dafny_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    dependencies, import_bindings = _extract_dependency_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    imported_target_files = tuple(
        dict.fromkeys(
            dependency.target_file
            for dependency in dependencies
            if dependency.target_file and dependency.target_file != file_path
        )
    )
    symbol_entries = iter_symbol_entries(text)
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols[1:]}
    default_source_symbol_id = symbols[0].symbol_id
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str | None]] = set()

    for target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        if target_name in symbol_ids_by_name:
            reference_key = (file_path, target_name, source_symbol_id)
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
            continue
        binding = import_bindings.get(target_name)
        target_file = binding.target_file if binding is not None else module_index.get(target_name)
        if target_file is None and len(imported_target_files) == 1:
            target_file = imported_target_files[0]
        if not target_file:
            continue
        reference_key = (target_file, target_name, source_symbol_id)
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
                        "target_name": target_name,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(references)


__all__ = [
    "DAFNY_SUFFIXES",
    "NormalizeRepositoryRelativePath",
    "ResolveSuffixMatch",
    "StableIdentifier",
    "candidate_module_keys",
    "collect_symbols",
    "has_dafny_path_hints",
    "is_probable_dafny_source",
    "iter_import_entries",
    "iter_include_entries",
    "iter_module_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import_module",
    "resolve_include",
    "source_symbol_name_for_line",
    "strip_comments",
]
