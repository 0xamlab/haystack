from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    four_d_primitives as repository_four_d_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_four_d_primitives.StableIdentifier
ResolveSuffixMatch = repository_four_d_primitives.ResolveSuffixMatch

FOUR_D_SUFFIXES = repository_four_d_primitives.FOUR_D_SUFFIXES
has_4d_path_hints = repository_four_d_primitives.has_4d_path_hints
is_probable_4d_source = repository_four_d_primitives.is_probable_4d_source
iter_cs_reference_entries = repository_four_d_primitives.iter_cs_reference_entries
iter_declared_symbol_entries = repository_four_d_primitives.iter_declared_symbol_entries
iter_dependency_entries = repository_four_d_primitives.iter_dependency_entries
iter_this_reference_entries = repository_four_d_primitives.iter_this_reference_entries
module_name_from_path = repository_four_d_primitives.module_name_from_path
path_aliases_for_file = repository_four_d_primitives.path_aliases_for_file
resolve_target = repository_four_d_primitives.resolve_target
strip_comments = repository_four_d_primitives.strip_comments
_line_count = repository_four_d_primitives._line_count


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
) -> set[str]:
    aliases = path_aliases_for_file(file_path)
    if text is None:
        absolute_path = root_path / file_path
        try:
            text = absolute_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return aliases
    stripped_text = strip_comments(text)
    if not is_probable_4d_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return aliases
    for entry in iter_declared_symbol_entries(
        text=text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    ):
        symbol_name = str(entry["symbol_name"])
        aliases.add(symbol_name)
        aliases.add(symbol_name.lower())
        if "/Classes/" in f"/{file_path}/":
            aliases.add(f"cs.{symbol_name}")
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
    dependency_entries: tuple[tuple[str, str, int], ...] | None = None,
) -> tuple[_Dependency, ...]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    if not is_probable_4d_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependency_keys: set[tuple[str, str | None, str]] = set()
    for dependency_kind, target_name, line_number in (
        dependency_entries
        if dependency_entries is not None
        else iter_dependency_entries(text, stripped_text=stripped_text)
    ):
        target_file = resolve_target(
            file_path,
            target_name,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (dependency_kind, target_file, target_name)
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
                        "dependency_type": dependency_kind,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=module_name_from_path(target_file) if target_file else target_name,
                dependency_type=dependency_kind,
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
    stripped_text = strip_comments(text)
    if not is_probable_4d_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return (), (), ()
    module_name = module_name_from_path(file_path) or Path(file_path).stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier("sym", {"file_path": file_path, "symbol_kind": "module"}),
        symbol_name=module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(text),
        parent_symbol_id=None,
        signature=file_path,
    )
    declared_symbol_entries = iter_declared_symbol_entries(
        text=text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    symbols = [module_symbol]
    local_symbol_ids = {module_symbol.symbol_name: module_symbol.symbol_id}
    for entry in declared_symbol_entries:
        symbol = _Symbol(
            symbol_id=str(entry["symbol_id"]),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=module_symbol.symbol_id,
            signature=str(entry["signature"]),
        )
        symbols.append(symbol)
        local_symbol_ids.setdefault(symbol.symbol_name, symbol.symbol_id)
    dependency_entries = iter_dependency_entries(text, stripped_text=stripped_text)
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
        dependency_entries=dependency_entries,
    )
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, tuple[str, ...], str]] = set()
    for dependency in dependencies:
        if not dependency.target_symbol:
            continue
        reference_key = (dependency.target_file, (dependency.target_symbol,), module_symbol.symbol_id)
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
                        "reference_type": "loads_symbol",
                    },
                ),
                source_symbol_id=module_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=(dependency.target_symbol,),
                reference_type="loads_symbol",
            )
        )
    for target_name, line_number in iter_cs_reference_entries(text, stripped_text=stripped_text):
        source_symbol_id = _source_symbol_id_for_line(
            line_number=line_number,
            declared_symbol_entries=declared_symbol_entries,
            module_symbol_id=module_symbol.symbol_id,
        )
        target_file = resolve_target(
            file_path,
            target_name,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        reference_key = (target_file, (target_name,), source_symbol_id)
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
                        "target_names": (target_name,),
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
    for target_name, line_number in iter_this_reference_entries(text, stripped_text=stripped_text):
        if target_name not in local_symbol_ids:
            continue
        source_symbol_id = _source_symbol_id_for_line(
            line_number=line_number,
            declared_symbol_entries=declared_symbol_entries,
            module_symbol_id=module_symbol.symbol_id,
        )
        reference_key = (file_path, (target_name,), source_symbol_id)
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
                        "target_names": (target_name,),
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=local_symbol_ids[target_name],
                target_file=file_path,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return tuple(symbols), dependencies, tuple(references)
