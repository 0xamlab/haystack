from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    hoon_primitives as repository_hoon_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_hoon_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_hoon_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_hoon_primitives.ResolveSuffixMatch

HOON_SUFFIXES = repository_hoon_primitives.HOON_SUFFIXES
collect_symbols = repository_hoon_primitives.collect_symbols
has_hoon_path_hints = repository_hoon_primitives.has_hoon_path_hints
is_probable_hoon_source = repository_hoon_primitives.is_probable_hoon_source
iter_dependency_entries = repository_hoon_primitives.iter_dependency_entries
iter_reference_entries = repository_hoon_primitives.iter_reference_entries
iter_symbol_entries = repository_hoon_primitives.iter_symbol_entries
module_aliases_for_path = repository_hoon_primitives.module_aliases_for_path
module_name_from_path = repository_hoon_primitives.module_name_from_path
normalize_identifier = repository_hoon_primitives.normalize_identifier
source_symbol_name_for_line = repository_hoon_primitives.source_symbol_name_for_line
strip_comments = repository_hoon_primitives.strip_comments


def resolve_import_module(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(import_target)
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    raw_candidates = [
        normalized_target,
        f"{normalized_target}.hoon",
        str(current_dir / normalized_target),
        str(current_dir / f"{normalized_target}.hoon"),
        str(current_dir.parent / normalized_target),
        str(current_dir.parent / f"{normalized_target}.hoon"),
    ]
    candidate_values: list[str] = []
    for raw_candidate in raw_candidates:
        normalized_candidate = normalize_repository_relative_path(raw_candidate)
        if normalized_candidate:
            candidate_values.append(normalized_candidate)
    deduped_candidates = tuple(dict.fromkeys(candidate_values))
    for candidate in deduped_candidates:
        resolved = module_index.get(candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=list(deduped_candidates))


def _extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    bindings: dict[str, _ImportedSymbolBinding] = {}
    seen_dependencies: set[tuple[str | None, str]] = set()
    for import_target, _kind, line_number in iter_dependency_entries(text):
        target_file = resolve_import_module(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
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
                        "kind": "imports",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=import_target or None,
                dependency_type="imports",
            )
        )
        bindings[import_target] = _ImportedSymbolBinding(
            alias=import_target,
            target_file=target_file,
            target_names=(import_target,),
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
    if not is_probable_hoon_source(path=Path(file_path), text=text):
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
    if not is_probable_hoon_source(path=Path(file_path), text=text):
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
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols[1:]}
    default_source_symbol_id = symbols[0].symbol_id
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()

    for target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
        if target_name in symbol_ids_by_name:
            target_file = file_path
            target_symbol_id = symbol_ids_by_name[target_name]
        else:
            binding = import_bindings.get(target_name)
            if binding is None:
                continue
            target_file = binding.target_file
            target_symbol_id = None
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
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(references)
