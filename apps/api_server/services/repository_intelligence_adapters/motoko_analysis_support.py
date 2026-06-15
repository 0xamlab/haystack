from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    motoko_primitives as repository_motoko_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_motoko_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_motoko_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_motoko_primitives.ResolveSuffixMatch

MOTOKO_SUFFIXES = repository_motoko_primitives.MOTOKO_SUFFIXES
clean_import_target = repository_motoko_primitives.clean_import_target
collect_symbols = repository_motoko_primitives.collect_symbols
has_motoko_path_hints = repository_motoko_primitives.has_motoko_path_hints
is_probable_motoko_source = repository_motoko_primitives.is_probable_motoko_source
iter_dependency_entries = repository_motoko_primitives.iter_dependency_entries
iter_reference_entries = repository_motoko_primitives.iter_reference_entries
iter_symbol_entries = repository_motoko_primitives.iter_symbol_entries
module_aliases_for_path = repository_motoko_primitives.module_aliases_for_path
module_name_from_path = repository_motoko_primitives.module_name_from_path
resolve_import = repository_motoko_primitives.resolve_import
source_symbol_name_for_line = repository_motoko_primitives.source_symbol_name_for_line
strip_comments = repository_motoko_primitives.strip_comments


def _extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
    line_start_offsets: tuple[int, ...] | None = None,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    imported_bindings: dict[str, _ImportedSymbolBinding] = {}
    seen_dependencies: set[tuple[str | None, str, str, int, str | None]] = set()
    for dependency_kind, import_target, alias, line_number in iter_dependency_entries(
        text,
        stripped_text=stripped_text,
        line_start_offsets=line_start_offsets,
    ):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, dependency_kind, line_number, alias)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        target_symbol = None
        if target_file:
            target_symbol = module_name_from_path(target_file) or Path(target_file).stem
            target_names = tuple(
                name
                for name in {alias, Path(target_file).stem, module_name_from_path(target_file)}
                if name
            )
            for binding_name in target_names:
                imported_bindings.setdefault(
                    binding_name,
                    _ImportedSymbolBinding(
                        alias=binding_name,
                        target_file=target_file,
                        target_names=target_names,
                    ),
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
    stripped_text = strip_comments(text)
    if not is_probable_motoko_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return ()
    dependencies, _bindings = _extract_import_bindings(
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
    stripped_text = strip_comments(text)
    if not is_probable_motoko_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return (), (), ()
    line_start_offsets = repository_motoko_primitives._line_start_offsets(stripped_text)
    symbol_entries = iter_symbol_entries(
        text,
        stripped_text=stripped_text,
        line_start_offsets=line_start_offsets,
    )
    symbols = collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        symbol_entries=symbol_entries,
    )
    dependencies, import_bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
        line_start_offsets=line_start_offsets,
    )
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols[1:]}
    default_source_symbol_id = symbols[0].symbol_id
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()

    for dependency in dependencies:
        if dependency.target_file is None or dependency.target_symbol is None:
            continue
        reference_key = (dependency.target_file, dependency.target_symbol, default_source_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        references.append(
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

    for target_name, line_number in iter_reference_entries(
        text,
        stripped_text=stripped_text,
    ):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        target_file = file_path if target_name in symbol_ids_by_name else None
        target_symbol_id = symbol_ids_by_name.get(target_name) if target_file == file_path else None
        target_names = (target_name,)
        if target_file is None:
            binding = import_bindings.get(target_name)
            if binding is None:
                continue
            target_file = binding.target_file
            target_names = binding.target_names or (target_name,)
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
