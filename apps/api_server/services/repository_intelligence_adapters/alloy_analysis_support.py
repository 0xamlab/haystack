from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    alloy_primitives as repository_alloy_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_alloy_primitives.StableIdentifier
ResolveSuffixMatch = repository_alloy_primitives.ResolveSuffixMatch

ALLOY_SUFFIXES = repository_alloy_primitives.ALLOY_SUFFIXES
has_alloy_path_hints = repository_alloy_primitives.has_alloy_path_hints
is_probable_alloy_source = repository_alloy_primitives.is_probable_alloy_source
iter_declared_symbol_entries = repository_alloy_primitives.iter_declared_symbol_entries
iter_reference_targets = repository_alloy_primitives.iter_reference_targets
module_declaration = repository_alloy_primitives.module_declaration
normalize_module_name = repository_alloy_primitives.normalize_module_name
open_statements = repository_alloy_primitives.open_statements
path_aliases_for_file = repository_alloy_primitives.path_aliases_for_file
resolve_target = repository_alloy_primitives.resolve_target
_line_count = repository_alloy_primitives._line_count


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
    if not is_probable_alloy_source(path=Path(file_path), text=text):
        return aliases
    declared_module_name, _declared_module_line = module_declaration(text)
    if declared_module_name:
        aliases.add(declared_module_name)
        aliases.add(declared_module_name.replace("/", "."))
        aliases.add(PurePosixPath(declared_module_name).name)
    for entry in iter_declared_symbol_entries(
        text=text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.add(str(entry["symbol_name"]))
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_alloy_source(path=PurePosixPath(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependency_keys: set[tuple[str | None, str]] = set()
    for target_name, _alias, line_number in open_statements(text):
        target_file = resolve_target(
            file_path,
            target_name,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, target_name.lower())
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
                        "dependency_type": "opens",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="opens",
            )
        )
    return tuple(dependencies)


def _source_symbol_id_for_line(
    *,
    line_number: int,
    declared_symbol_entries: tuple[dict[str, object], ...],
    module_symbol_id: str,
) -> str:
    for entry in declared_symbol_entries:
        if int(entry["start_line"]) <= line_number <= int(entry["end_line"]):
            return str(entry["symbol_id"])
    return module_symbol_id


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
    if not is_probable_alloy_source(path=PurePosixPath(file_path), text=text):
        return (), (), ()
    declared_module_name, _declared_module_line = module_declaration(text)
    module_name = declared_module_name or PurePosixPath(file_path).stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier("sym", {"file_path": file_path, "symbol_kind": "module"}),
        symbol_name=module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(text),
        parent_symbol_id=None,
        signature=module_name,
    )
    declared_symbol_entries = iter_declared_symbol_entries(
        text=text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    symbols = [module_symbol]
    for entry in declared_symbol_entries:
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
    seen_reference_keys: set[tuple[str, str | None, tuple[str, ...], str]] = set()
    for dependency in dependencies:
        if not dependency.target_symbol:
            continue
        reference_key = (
            module_symbol.symbol_id,
            dependency.target_file,
            (dependency.target_symbol,),
            "opens_module",
        )
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
                        "target_names": (dependency.target_symbol,),
                        "reference_type": "opens_module",
                    },
                ),
                source_symbol_id=module_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=(dependency.target_symbol,),
                reference_type="opens_module",
            )
        )
    for target_name, line_number in iter_reference_targets(
        text,
        declared_symbol_entries=declared_symbol_entries,
    ):
        source_symbol_id = _source_symbol_id_for_line(
            line_number=line_number,
            declared_symbol_entries=declared_symbol_entries,
            module_symbol_id=module_symbol.symbol_id,
        )
        reference_key = (
            source_symbol_id,
            None,
            (target_name,),
            "references_symbol",
        )
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
                        "target_names": (target_name,),
                        "reference_type": "references_symbol",
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=None,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return tuple(symbols), dependencies, tuple(references)

