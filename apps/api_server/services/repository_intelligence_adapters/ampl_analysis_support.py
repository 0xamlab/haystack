from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    ampl_primitives as repository_ampl_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_ampl_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_ampl_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_ampl_primitives.ResolveSuffixMatch

AMPL_SUFFIXES = repository_ampl_primitives.AMPL_SUFFIXES
clean_dependency_target = repository_ampl_primitives.clean_dependency_target
collect_symbols = repository_ampl_primitives.collect_symbols
has_ampl_path_hints = repository_ampl_primitives.has_ampl_path_hints
is_probable_ampl_source = repository_ampl_primitives.is_probable_ampl_source
iter_dependency_entries = repository_ampl_primitives.iter_dependency_entries
iter_reference_entries = repository_ampl_primitives.iter_reference_entries
iter_symbol_entries = repository_ampl_primitives.iter_symbol_entries
module_aliases_for_path = repository_ampl_primitives.module_aliases_for_path
module_name_from_path = repository_ampl_primitives.module_name_from_path
source_symbol_name_for_line = repository_ampl_primitives.source_symbol_name_for_line


def resolve_dependency(
    *,
    current_file: str,
    dependency_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    cleaned_target = clean_dependency_target(dependency_target)
    if not cleaned_target:
        return None
    candidate_path = PurePosixPath(cleaned_target)
    current_dir = PurePosixPath(current_file).parent
    candidate_values = (
        candidate_path,
        current_dir / candidate_path,
    )
    seen_candidates: set[str] = set()
    for candidate_value in candidate_values:
        normalized_candidate = normalize_repository_relative_path(candidate_value)
        if not normalized_candidate or normalized_candidate in seen_candidates:
            continue
        seen_candidates.add(normalized_candidate)
        direct_match = module_index.get(normalized_candidate)
        if direct_match is not None:
            return direct_match
        suffixes = (
            (normalized_candidate,)
            if PurePosixPath(normalized_candidate).suffix.lower() in AMPL_SUFFIXES
            else tuple(f"{normalized_candidate}{suffix}" for suffix in sorted(AMPL_SUFFIXES))
        )
        suffix_match = resolve_suffix_match(module_index=module_index, suffixes=suffixes)
        if suffix_match is not None:
            return suffix_match
    return None


def _extract_dependencies(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str, int]] = set()
    for dependency_kind, dependency_target, line_number in iter_dependency_entries(text):
        target_file = resolve_dependency(
            current_file=file_path,
            dependency_target=dependency_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, dependency_target, dependency_kind, line_number)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        target_symbol = None
        if target_file:
            target_symbol = module_name_from_path(target_file) or Path(target_file).stem
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": dependency_target,
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
    return tuple(dependencies)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_ampl_source(path=Path(file_path), text=text):
        return ()
    return _extract_dependencies(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )


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
    if not is_probable_ampl_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    dependencies = _extract_dependencies(
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
    seen_reference_keys: set[tuple[str, str, str]] = set()

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

    for target_name, line_number in iter_reference_entries(text):
        target_symbol_id = symbol_ids_by_name.get(target_name)
        if target_symbol_id is None:
            continue
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", default_source_symbol_id)
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
                target_symbol_id=target_symbol_id,
                target_file=file_path,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(references)
