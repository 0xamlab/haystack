from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    openedge_primitives as repository_openedge_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_openedge_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_openedge_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_openedge_primitives.ResolveSuffixMatch

OPENEDGE_SUFFIXES = repository_openedge_primitives.OPENEDGE_SUFFIXES
clean_dependency_target = repository_openedge_primitives.clean_dependency_target
collect_symbols = repository_openedge_primitives.collect_symbols
has_openedge_path_hints = repository_openedge_primitives.has_openedge_path_hints
is_probable_openedge_source = repository_openedge_primitives.is_probable_openedge_source
iter_dependency_entries = repository_openedge_primitives.iter_dependency_entries
module_aliases_for_path = repository_openedge_primitives.module_aliases_for_path
module_name_from_path = repository_openedge_primitives.module_name_from_path


def resolve_dependency(
    *,
    current_file: str,
    dependency_kind: str,
    dependency_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    cleaned_target = clean_dependency_target(dependency_target)
    if not cleaned_target or cleaned_target.endswith(".*"):
        return None
    direct_aliases = [cleaned_target]
    dotted_target = cleaned_target.replace("/", ".")
    if dotted_target != cleaned_target:
        direct_aliases.append(dotted_target)
    slash_target = cleaned_target.replace(".", "/")
    if slash_target != cleaned_target:
        direct_aliases.append(slash_target)
    for alias in direct_aliases:
        direct_match = module_index.get(alias)
        if direct_match is not None:
            return direct_match

    candidate_values: list[PurePosixPath] = []
    current_dir = PurePosixPath(current_file).parent
    target_path = PurePosixPath(cleaned_target)
    if dependency_kind in {"include", "run"}:
        candidate_values.extend((target_path, current_dir / target_path))
    elif dependency_kind in {"using", "inherits", "implements"}:
        class_path = PurePosixPath(*cleaned_target.split("."))
        candidate_values.append(class_path.with_suffix(".cls"))
    suffixes_by_kind = {
        "include": (".i", ".p", ".w"),
        "run": (".p", ".w", ".cls"),
        "using": (".cls",),
        "inherits": (".cls",),
        "implements": (".cls",),
    }
    seen_candidates: set[str] = set()
    for candidate_value in candidate_values:
        normalized_candidate = normalize_repository_relative_path(str(candidate_value))
        if not normalized_candidate or normalized_candidate in seen_candidates:
            continue
        seen_candidates.add(normalized_candidate)
        direct_match = module_index.get(normalized_candidate)
        if direct_match is not None:
            return direct_match
        suffixes = (
            (normalized_candidate,)
            if PurePosixPath(normalized_candidate).suffix.lower() in OPENEDGE_SUFFIXES
            else tuple(
                f"{normalized_candidate}{suffix}"
                for suffix in suffixes_by_kind.get(dependency_kind, OPENEDGE_SUFFIXES)
            )
        )
        suffix_match = resolve_suffix_match(module_index=module_index, suffixes=suffixes)
        if suffix_match is not None:
            return suffix_match
    return None


def _dependency_symbol_name(dependency_target: str, target_file: str | None) -> str:
    if target_file:
        return module_name_from_path(target_file)
    cleaned_target = clean_dependency_target(dependency_target)
    if "." in cleaned_target and "/" not in cleaned_target:
        return cleaned_target.rsplit(".", 1)[-1]
    return PurePosixPath(cleaned_target).stem or cleaned_target.rsplit(".", 1)[-1]


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
            dependency_kind=dependency_kind,
            dependency_target=dependency_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, dependency_target, dependency_kind, line_number)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
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
                target_symbol=_dependency_symbol_name(dependency_target, target_file),
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
    if not is_probable_openedge_source(path=Path(file_path), text=text):
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
    if not is_probable_openedge_source(path=Path(file_path), text=text):
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
    default_source_symbol_id = (
        symbols[1].symbol_id if len(symbols) > 1 and symbols[1].symbol_kind in {"class", "interface"} else symbols[0].symbol_id
    )
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, tuple[str, ...], str]] = set()
    for dependency in dependencies:
        if dependency.target_symbol is None:
            continue
        target_names = (dependency.target_symbol,)
        reference_key = (dependency.target_file, target_names, default_source_symbol_id)
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
                target_names=target_names,
                reference_type="references_symbol",
            )
        )
    return symbols, dependencies, tuple(references)

