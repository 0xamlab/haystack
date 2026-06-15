from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    aiken_primitives as repository_aiken_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_aiken_primitives.StableIdentifier
ResolveSuffixMatch = repository_aiken_primitives.ResolveSuffixMatch

AIKEN_CONFIG_BASENAMES = repository_aiken_primitives.AIKEN_CONFIG_BASENAMES
AIKEN_SOURCE_SUFFIXES = repository_aiken_primitives.AIKEN_SOURCE_SUFFIXES
has_aiken_path_hints = repository_aiken_primitives.has_aiken_path_hints
is_probable_aiken_config = repository_aiken_primitives.is_probable_aiken_config
is_probable_aiken_source = repository_aiken_primitives.is_probable_aiken_source
iter_declared_symbol_entries = repository_aiken_primitives.iter_declared_symbol_entries
iter_reference_entries = repository_aiken_primitives.iter_reference_entries
iter_use_entries = repository_aiken_primitives.iter_use_entries
module_name_from_path = repository_aiken_primitives.module_name_from_path
path_aliases_for_file = repository_aiken_primitives.path_aliases_for_file
resolve_import_target = repository_aiken_primitives.resolve_import_target
strip_comments = repository_aiken_primitives.strip_comments
_line_count = repository_aiken_primitives._line_count


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
    if not is_probable_aiken_source(path=Path(file_path), text=text):
        return aliases
    for entry in iter_declared_symbol_entries(
        text=text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        symbol_name = str(entry["symbol_name"])
        aliases.add(symbol_name)
        aliases.add(symbol_name.lower())
    return {alias for alias in aliases if alias}


def _extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    seen_dependencies: set[tuple[str, str | None, int]] = set()
    for import_target, alias, imported_names, line_number in iter_use_entries(text):
        target_file = resolve_import_target(
            file_path,
            import_target,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (import_target, target_file, line_number)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        target_symbol = module_name_from_path(target_file) if target_file else import_target
        if alias:
            import_bindings[alias] = _ImportedSymbolBinding(
                alias=alias,
                target_file=target_file,
                target_names=(target_symbol,),
            )
        else:
            default_alias = import_target.split("/")[-1]
            import_bindings[default_alias] = _ImportedSymbolBinding(
                alias=default_alias,
                target_file=target_file,
                target_names=(target_symbol,),
            )
        for imported_name in imported_names:
            import_bindings[imported_name] = _ImportedSymbolBinding(
                alias=imported_name,
                target_file=target_file,
                target_names=(imported_name,),
            )
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "kind": "uses",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="uses",
            )
        )
    return tuple(dependencies), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_aiken_source(path=Path(file_path), text=text):
        return ()
    dependencies, _bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    return dependencies


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
    if not is_probable_aiken_source(path=Path(file_path), text=text):
        return (), (), ()
    module_name = module_name_from_path(file_path) or Path(file_path).stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier("sym", {"file_path": file_path, "symbol_kind": "module"}),
        symbol_name=module_name.split("/")[-1] or module_name,
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
    dependencies, import_bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
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
                        "reference_type": "uses_symbol",
                    },
                ),
                source_symbol_id=module_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=(dependency.target_symbol,),
                reference_type="uses_symbol",
            )
        )
    for alias_name, target_name, line_number in iter_reference_entries(text):
        source_symbol_id = _source_symbol_id_for_line(
            line_number=line_number,
            declared_symbol_entries=declared_symbol_entries,
            module_symbol_id=module_symbol.symbol_id,
        )
        target_file = file_path if target_name in local_symbol_ids else None
        target_symbol_id = local_symbol_ids.get(target_name) if target_file == file_path else None
        target_names = (target_name,)
        if alias_name:
            binding = import_bindings.get(alias_name)
            if binding is None:
                continue
            target_file = binding.target_file
            target_symbol_id = None
            target_names = (target_name,)
        elif target_file is None:
            binding = import_bindings.get(target_name)
            if binding is None:
                continue
            target_file = binding.target_file
            target_names = binding.target_names or (target_name,)
        reference_key = (target_file, target_names, source_symbol_id)
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
                        "target_names": target_names,
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
    return tuple(symbols), dependencies, tuple(references)
