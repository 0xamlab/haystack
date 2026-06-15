from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    moonscript_primitives as repository_moonscript_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_moonscript_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_moonscript_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_moonscript_primitives.ResolveSuffixMatch

MOONSCRIPT_SUFFIXES = repository_moonscript_primitives.MOONSCRIPT_SUFFIXES
collect_symbols = repository_moonscript_primitives.collect_symbols
has_moonscript_path_hints = repository_moonscript_primitives.has_moonscript_path_hints
is_probable_moonscript_source = repository_moonscript_primitives.is_probable_moonscript_source
iter_dependency_entries = repository_moonscript_primitives.iter_dependency_entries
iter_reference_entries = repository_moonscript_primitives.iter_reference_entries
iter_symbol_entries = repository_moonscript_primitives.iter_symbol_entries
module_aliases_for_path = repository_moonscript_primitives.module_aliases_for_path
source_symbol_name_for_line = repository_moonscript_primitives.source_symbol_name_for_line


def _normalize_import_target(raw_target: str) -> str:
    return str(raw_target or "").strip()


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_import_target(import_target)
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    suffixes = tuple(sorted(MOONSCRIPT_SUFFIXES))
    raw_candidates = [normalized_target]
    if normalized_target.startswith(".") or "/" in normalized_target:
        raw_candidates.append(str(current_dir / normalized_target))
    if PurePosixPath(normalized_target).suffix.lower() not in MOONSCRIPT_SUFFIXES:
        for suffix in suffixes:
            raw_candidates.append(f"{normalized_target}{suffix}")
            raw_candidates.append(f"{normalized_target}/init{suffix}")
            if normalized_target.startswith(".") or "/" in normalized_target:
                raw_candidates.append(str(current_dir / f"{normalized_target}{suffix}"))
                raw_candidates.append(str(current_dir / f"{normalized_target}/init{suffix}"))
    candidate_keys: list[str] = []
    seen_candidates: set[str] = set()
    for raw_candidate in raw_candidates:
        normalized_candidate = normalize_repository_relative_path(raw_candidate)
        if not normalized_candidate or normalized_candidate in seen_candidates:
            continue
        seen_candidates.add(normalized_candidate)
        candidate_keys.append(normalized_candidate)
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    basename = PurePosixPath(normalized_target).name
    lookup_suffixes = [*candidate_keys, basename]
    if PurePosixPath(normalized_target).suffix.lower() not in MOONSCRIPT_SUFFIXES and basename:
        lookup_suffixes.extend(f"{basename}{suffix}" for suffix in suffixes)
        lookup_suffixes.extend(f"{basename}/init{suffix}" for suffix in suffixes)
    return resolve_suffix_match(module_index=module_index, suffixes=lookup_suffixes)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_moonscript_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependency_keys: set[tuple[str | None, str]] = set()
    for import_target, dependency_type, line_number in iter_dependency_entries(text):
        target_file = resolve_import(
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
                        "type": dependency_type,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=None,
                dependency_type=dependency_type,
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
    if not is_probable_moonscript_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
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
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    return symbols, dependencies, tuple(references)
