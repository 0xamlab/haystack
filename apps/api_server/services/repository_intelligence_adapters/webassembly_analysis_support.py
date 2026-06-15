from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    webassembly_primitives as repository_webassembly_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_webassembly_primitives.StableIdentifier

WEBASSEMBLY_SUFFIXES = repository_webassembly_primitives.WEBASSEMBLY_SUFFIXES
has_webassembly_path_hints = repository_webassembly_primitives.has_webassembly_path_hints
is_probable_webassembly_source = repository_webassembly_primitives.is_probable_webassembly_source
iter_declared_symbol_entries = repository_webassembly_primitives.iter_declared_symbol_entries
iter_import_entries = repository_webassembly_primitives.iter_import_entries
iter_reference_entries = repository_webassembly_primitives.iter_reference_entries
module_name_from_path = repository_webassembly_primitives.module_name_from_path
path_aliases_for_file = repository_webassembly_primitives.path_aliases_for_file
strip_comments = repository_webassembly_primitives.strip_comments
_line_count = repository_webassembly_primitives._line_count


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
    if not is_probable_webassembly_source(path=Path(file_path), text=text):
        return aliases
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
) -> tuple[_Dependency, ...]:
    del module_index
    if not is_probable_webassembly_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    for target_module, target_name, line_number in iter_import_entries(text):
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target_module": target_module,
                        "target_name": target_name,
                        "dependency_type": "imports",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=None,
                target_symbol=f"{target_module}::{target_name}",
                dependency_type="imports",
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    del module_index
    if not is_probable_webassembly_source(path=Path(file_path), text=text):
        return (), (), ()
    module_name = module_name_from_path(file_path) or Path(file_path).stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier("sym", {"file_path": file_path, "symbol_kind": "module"}),
        symbol_name=module_name.split(".")[-1] or module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(text),
        parent_symbol_id=None,
        signature=file_path,
    )
    declared_entries = iter_declared_symbol_entries(
        text=text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    symbols = [module_symbol]
    local_symbol_ids = {module_symbol.symbol_name: module_symbol.symbol_id}
    for entry in declared_entries:
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
    dependencies = parse_dependencies_only(
        file_path,
        text,
        {},
        stable_identifier=stable_identifier,
    )
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, tuple[str, ...]]] = set()
    for target_name, line_number in iter_reference_entries(text):
        target_file = file_path if target_name in local_symbol_ids else None
        target_symbol_id = local_symbol_ids.get(target_name)
        target_names = (target_name,)
        reference_key = (target_file, target_names)
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
                        "target_file": target_file,
                        "target_names": target_names,
                        "reference_type": "uses_symbol",
                        "line": line_number,
                    },
                ),
                source_symbol_id=module_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=target_names,
                reference_type="uses_symbol",
            )
        )
    return tuple(symbols), dependencies, tuple(references)

