from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    dm_primitives as repository_dm_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_dm_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_dm_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_dm_primitives.ResolveSuffixMatch

DM_CONFIG_SUFFIXES = repository_dm_primitives.DM_CONFIG_SUFFIXES
DM_SOURCE_SUFFIXES = repository_dm_primitives.DM_SOURCE_SUFFIXES
DM_SUFFIXES = repository_dm_primitives.DM_SUFFIXES
_SymbolEntry = repository_dm_primitives._SymbolEntry

has_dm_path_hints = repository_dm_primitives.has_dm_path_hints
is_probable_dm_source = repository_dm_primitives.is_probable_dm_source
iter_call_reference_entries = repository_dm_primitives.iter_call_reference_entries
iter_symbol_entries = repository_dm_primitives.iter_symbol_entries
iter_type_reference_entries = repository_dm_primitives.iter_type_reference_entries
module_name_from_path = repository_dm_primitives.module_name_from_path
parse_include_entries = repository_dm_primitives.parse_include_entries
resolve_include = repository_dm_primitives.resolve_include
source_symbol_name_for_line = repository_dm_primitives.source_symbol_name_for_line
strip_comments = repository_dm_primitives.strip_comments


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[tuple[_Symbol, tuple[str, ...]], ...]:
    final_line = max(1, text.count("\n") + 1)
    module_name = module_name_from_path(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name or file_path,
                "symbol_kind": "module",
                "start_line": 1,
            },
        ),
        symbol_name=module_name or file_path,
        symbol_kind="module",
        start_line=1,
        end_line=final_line,
        parent_symbol_id=None,
        signature=f"module {module_name}" if module_name else None,
    )
    collected_symbols: list[tuple[_Symbol, tuple[str, ...]]] = [
        (
            module_symbol,
            repository_dm_primitives._ordered_names(
                module_name,
                module_name.replace("/", ".") if module_name else "",
            ),
        )
    ]
    symbol_entries = iter_symbol_entries(text, stripped_text=stripped_text)
    for index, entry in enumerate(symbol_entries):
        end_line = (
            max(symbol_entries[index + 1].start_line - 1, entry.start_line)
            if index + 1 < len(symbol_entries)
            else final_line
        )
        collected_symbols.append(
            (
                _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": entry.name,
                            "symbol_kind": entry.kind,
                            "start_line": entry.start_line,
                        },
                    ),
                    symbol_name=entry.name,
                    symbol_kind=entry.kind,
                    start_line=entry.start_line,
                    end_line=end_line,
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=entry.name,
                ),
                entry.qualified_names,
            )
        )
    return tuple(collected_symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in DM_SUFFIXES:
        return set()
    aliases = {
        file_path,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    module_name = module_name_from_path(file_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.replace("/", "."))
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    if not is_probable_dm_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return {alias for alias in aliases if alias}
    for symbol, qualified_names in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    ):
        aliases.add(symbol.symbol_name)
        aliases.update(qualified_names)
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[_Dependency, ...]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    if not is_probable_dm_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return ()
    dependencies: list[_Dependency] = []
    seen: set[tuple[str, int]] = set()
    for include_target, line_number in parse_include_entries(text, stripped_text=stripped_text):
        target_file = resolve_include(
            current_file=file_path,
            include_target=include_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        key = (include_target, line_number)
        if key in seen:
            continue
        seen.add(key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": include_target,
                        "line": line_number,
                        "kind": "include",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=None,
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
    stripped_text: str | None = None,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    if not is_probable_dm_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    symbols = tuple(symbol for symbol, _qualified_names in collected_symbols)
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    symbol_entries = iter_symbol_entries(text, stripped_text=stripped_text)
    local_symbol_ids = {symbol.symbol_name: symbol.symbol_id for symbol in symbols[1:]}
    default_source_symbol_id = symbols[0].symbol_id
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()
    for dependency in dependencies:
        if dependency.target_file is None:
            continue
        target_name = module_name_from_path(dependency.target_file) or Path(dependency.target_file).stem
        reference_key = (dependency.target_file, target_name, default_source_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": default_source_symbol_id,
                        "target_file": dependency.target_file,
                        "target_name": target_name,
                    },
                ),
                source_symbol_id=default_source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    for target_name, line_number in iter_call_reference_entries(
        text,
        stripped_text=stripped_text,
    ):
        target_symbol_id = local_symbol_ids.get(target_name)
        if target_symbol_id is None:
            continue
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = local_symbol_ids.get(source_symbol_name or "", default_source_symbol_id)
        reference_key = (file_path, target_name, source_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        symbol_references.append(
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
    for target_name, line_number in iter_type_reference_entries(
        text,
        stripped_text=stripped_text,
    ):
        target_symbol_id = local_symbol_ids.get(target_name)
        if target_symbol_id is None:
            continue
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = local_symbol_ids.get(source_symbol_name or "", default_source_symbol_id)
        reference_key = (file_path, target_name, source_symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        symbol_references.append(
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
    return symbols, dependencies, tuple(symbol_references)
