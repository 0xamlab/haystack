from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    abapcds_primitives as repository_abapcds_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_abapcds_primitives.StableIdentifier
ResolveSuffixMatch = repository_abapcds_primitives.ResolveSuffixMatch

ABAPCDS_DECL_RE = repository_abapcds_primitives.ABAPCDS_DECL_RE
ABAPCDS_SUFFIXES = repository_abapcds_primitives.ABAPCDS_SUFFIXES
ASSOCIATION_TO_RE = repository_abapcds_primitives.ASSOCIATION_TO_RE
PROJECTION_ON_RE = repository_abapcds_primitives.PROJECTION_ON_RE
SELECT_FROM_RE = repository_abapcds_primitives.SELECT_FROM_RE
has_abapcds_path_hints = repository_abapcds_primitives.has_abapcds_path_hints
is_probable_abapcds_source = repository_abapcds_primitives.is_probable_abapcds_source
iter_declared_type_entries = repository_abapcds_primitives.iter_declared_type_entries
iter_reference_targets = repository_abapcds_primitives.iter_reference_targets
path_aliases_for_file = repository_abapcds_primitives.path_aliases_for_file
resolve_target = repository_abapcds_primitives.resolve_target
_entity_name_to_repository_stem = repository_abapcds_primitives._entity_name_to_repository_stem
_line_count = repository_abapcds_primitives._line_count


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    aliases = path_aliases_for_file(file_path)
    absolute_path = root_path / file_path
    try:
        text = absolute_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return aliases
    if not is_probable_abapcds_source(path=Path(file_path), text=text):
        return aliases
    for entry in iter_declared_type_entries(
        text=text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        symbol_name = str(entry["symbol_name"])
        aliases.add(symbol_name)
        aliases.add(symbol_name.lower())
        aliases.add(_entity_name_to_repository_stem(symbol_name))
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_abapcds_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependency_keys: set[tuple[str | None, str, str]] = set()
    for target_name, line_number, dependency_type in iter_reference_targets(text):
        target_file = resolve_target(
            target_name,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, target_name, dependency_type)
        if dependency_key in seen_dependency_keys:
            continue
        seen_dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target_name": target_name,
                        "line": line_number,
                        "dependency_type": dependency_type,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
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
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    if not is_probable_abapcds_source(path=Path(file_path), text=text):
        return (), (), ()
    module_symbol = _Symbol(
        symbol_id=stable_identifier("symbol", {"file_path": file_path, "kind": "module"}),
        symbol_name=Path(file_path).name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(text),
        parent_symbol_id=None,
        signature=file_path,
    )
    symbols: list[_Symbol] = [module_symbol]
    for entry in iter_declared_type_entries(
        text=text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        symbols.append(
            _Symbol(
                symbol_id=str(entry["symbol_id"]),
                symbol_name=str(entry["symbol_name"]),
                symbol_kind=str(entry["symbol_kind"]),
                start_line=int(entry["start_line"]),
                end_line=int(entry["end_line"]),
                parent_symbol_id=module_symbol.symbol_id,
                signature=str(entry["signature"] or ""),
            )
        )
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, tuple[str, ...], str]] = set()
    for dependency in dependencies:
        if not dependency.target_symbol:
            continue
        target_names = (dependency.target_symbol,)
        reference_key = (dependency.target_file, target_names, module_symbol.symbol_id)
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
                        "target_names": target_names,
                    },
                ),
                source_symbol_id=module_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )
    return tuple(symbols), dependencies, tuple(references)
