from __future__ import annotations

import re
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    nginx_primitives as repository_nginx_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_nginx_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_nginx_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_nginx_primitives.ResolveSuffixMatch

NGINX_INDEX_BASENAMES = repository_nginx_primitives.NGINX_INDEX_BASENAMES
NGINX_SUFFIXES = repository_nginx_primitives.NGINX_SUFFIXES
collect_symbols = repository_nginx_primitives.collect_symbols
has_nginx_path_hints = repository_nginx_primitives.has_nginx_path_hints
is_probable_nginx_source = repository_nginx_primitives.is_probable_nginx_source
iter_dependency_entries = repository_nginx_primitives.iter_dependency_entries
iter_reference_entries = repository_nginx_primitives.iter_reference_entries
iter_symbol_entries = repository_nginx_primitives.iter_symbol_entries
module_aliases_for_path = repository_nginx_primitives.module_aliases_for_path
module_name_from_path = repository_nginx_primitives.module_name_from_path
source_symbol_name_for_line = repository_nginx_primitives.source_symbol_name_for_line
strip_comments = repository_nginx_primitives.strip_comments

_VARIABLE_RE = re.compile(r"\$\{[^}]+\}")


def resolve_include_targets(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str, ...]:
    stripped_target = _VARIABLE_RE.sub("", import_target).strip().strip("\"'")
    if not stripped_target or stripped_target.startswith("/"):
        return ()
    current_parent = PurePosixPath(current_file).parent
    candidate_patterns = [
        normalize_repository_relative_path(str(current_parent / stripped_target)),
        normalize_repository_relative_path(stripped_target),
    ]
    resolved_targets: set[str] = set()
    module_values = tuple(sorted(set(module_index.values())))
    for candidate_pattern in candidate_patterns:
        if not candidate_pattern:
            continue
        if any(token in candidate_pattern for token in "*?["):
            for target_file in module_values:
                if fnmatchcase(target_file, candidate_pattern):
                    resolved_targets.add(target_file)
            continue
        resolved_target = module_index.get(candidate_pattern)
        if resolved_target is not None:
            resolved_targets.add(resolved_target)
            continue
        resolved_target = resolve_suffix_match(
            module_index=module_index,
            suffixes=(candidate_pattern, PurePosixPath(candidate_pattern).name),
        )
        if resolved_target is not None:
            resolved_targets.add(resolved_target)
    return tuple(sorted(resolved_targets))


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_nginx_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependency_keys: set[tuple[str | None, str]] = set()
    for import_target, line_number in iter_dependency_entries(text):
        resolved_targets = resolve_include_targets(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if not resolved_targets:
            resolved_targets = (None,)
        for target_file in resolved_targets:
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
                            "type": "include",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=Path(import_target).stem or None,
                    dependency_type="include",
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
    if not is_probable_nginx_source(path=Path(file_path), text=text):
        return (), (), ()
    symbols = collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier)
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
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
    return symbols, dependencies, tuple(references)
