from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    apacheconf_primitives as repository_apacheconf_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_apacheconf_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_apacheconf_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_apacheconf_primitives.ResolveSuffixMatch

APACHECONF_INDEX_BASENAMES = repository_apacheconf_primitives.APACHECONF_INDEX_BASENAMES
APACHECONF_SUFFIXES = repository_apacheconf_primitives.APACHECONF_SUFFIXES
has_apacheconf_path_hints = repository_apacheconf_primitives.has_apacheconf_path_hints
is_probable_apacheconf_source = repository_apacheconf_primitives.is_probable_apacheconf_source
iter_dependency_entries = repository_apacheconf_primitives.iter_dependency_entries
iter_reference_entries = repository_apacheconf_primitives.iter_reference_entries
iter_symbol_entries = repository_apacheconf_primitives.iter_symbol_entries
module_name_from_path = repository_apacheconf_primitives.module_name_from_path
path_aliases_for_file = repository_apacheconf_primitives.path_aliases_for_file
resolve_include_targets = repository_apacheconf_primitives.resolve_include_targets
strip_comments = repository_apacheconf_primitives.strip_comments
_line_count = repository_apacheconf_primitives._line_count


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    aliases = path_aliases_for_file(file_path)
    absolute_path = root_path / file_path
    try:
        text = absolute_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return aliases
    if not is_probable_apacheconf_source(path=Path(file_path), text=text):
        return aliases
    for _symbol_kind, symbol_name, _line_number in iter_symbol_entries(text):
        aliases.add(symbol_name)
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_apacheconf_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str]] = set()
    for dependency_kind, import_target, line_number in iter_dependency_entries(text):
        resolved_targets = resolve_include_targets(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_files = resolved_targets or (None,)
        for target_file in target_files:
            dependency_key = (target_file, import_target, dependency_kind)
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
                            "kind": dependency_kind,
                            "line": line_number,
                            "resolved_target": target_file,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=import_target,
                    dependency_type=dependency_kind,
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
    if not is_probable_apacheconf_source(path=Path(file_path), text=text):
        return (), (), ()
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "symbol",
            {"file_path": file_path, "name": module_name_from_path(file_path)},
        ),
        symbol_name=module_name_from_path(file_path),
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(text),
        parent_symbol_id=None,
        signature=file_path,
    )
    symbols: list[_Symbol] = [module_symbol]
    symbol_ids_by_name = {module_symbol.symbol_name: module_symbol.symbol_id}
    for symbol_kind, symbol_name, line_number in iter_symbol_entries(text):
        symbol_id = stable_identifier(
            "symbol",
            {"file_path": file_path, "name": symbol_name, "kind": symbol_kind, "line": line_number},
        )
        symbols.append(
            _Symbol(
                symbol_id=symbol_id,
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol.symbol_id,
                signature=None,
            )
        )
        symbol_ids_by_name[symbol_name] = symbol_id
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()
    for dependency in dependencies:
        if not dependency.target_file:
            continue
        target_name = module_name_from_path(dependency.target_file)
        reference_key = (dependency.target_file, target_name, module_symbol.symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": module_symbol.symbol_id,
                        "target_file": dependency.target_file,
                        "target_name": target_name,
                    },
                ),
                source_symbol_id=module_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    for reference_kind, target_name, line_number in iter_reference_entries(text):
        source_symbol_id = module_symbol.symbol_id
        target_symbol_id = symbol_ids_by_name.get(target_name)
        target_file = file_path if target_symbol_id else module_index.get(target_name)
        reference_key = (target_file or file_path, target_name, source_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": source_symbol_id,
                        "target_file": target_file or file_path,
                        "target_name": target_name,
                        "kind": reference_kind,
                        "line": line_number,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file or file_path,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return tuple(symbols), dependencies, tuple(references)


__all__ = [
    "APACHECONF_INDEX_BASENAMES",
    "APACHECONF_SUFFIXES",
    "has_apacheconf_path_hints",
    "is_probable_apacheconf_source",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_include_targets",
    "strip_comments",
]
