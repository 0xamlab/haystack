from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    codeql_primitives as repository_codeql_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_codeql_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_codeql_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_codeql_primitives.ResolveSuffixMatch

CODEQL_CONFIG_BASENAMES = repository_codeql_primitives.CODEQL_CONFIG_BASENAMES
CODEQL_SOURCE_SUFFIXES = repository_codeql_primitives.CODEQL_SOURCE_SUFFIXES
has_codeql_path_hints = repository_codeql_primitives.has_codeql_path_hints
is_probable_codeql_config = repository_codeql_primitives.is_probable_codeql_config
is_probable_codeql_source = repository_codeql_primitives.is_probable_codeql_source
iter_declared_symbol_entries = repository_codeql_primitives.iter_declared_symbol_entries
iter_import_entries = repository_codeql_primitives.iter_import_entries
iter_reference_entries = repository_codeql_primitives.iter_reference_entries
module_aliases_for_path = repository_codeql_primitives.module_aliases_for_path
module_name_from_path = repository_codeql_primitives.module_name_from_path
path_aliases_for_file = repository_codeql_primitives.path_aliases_for_file
resolve_import = repository_codeql_primitives.resolve_import
source_symbol_name_for_line = repository_codeql_primitives.source_symbol_name_for_line
strip_comments = repository_codeql_primitives.strip_comments
_line_count = repository_codeql_primitives._line_count


def _import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for target, line_number in iter_import_entries(text):
        target_file = resolve_import(
            file_path,
            target,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_symbol = target.split(".")[-1] or target
        bindings[target_symbol] = _ImportedSymbolBinding(
            alias=target_symbol,
            target_file=target_file,
            target_names=(target_symbol,),
        )
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target,
                        "dependency_type": "imports",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target,
                dependency_type="imports",
            )
        )
    return tuple(dependencies), bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    path = Path(file_path)
    if path.name.lower() in CODEQL_CONFIG_BASENAMES:
        return ()
    if not is_probable_codeql_source(path=path, text=text):
        return ()
    dependencies, _bindings = _import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    return dependencies


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
    path = Path(file_path)
    if path.name.lower() in CODEQL_CONFIG_BASENAMES:
        return (), (), ()
    if not is_probable_codeql_source(path=path, text=text):
        return (), (), ()
    module_name = module_name_from_path(file_path) or path.stem
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
    dependencies, import_bindings = _import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, tuple[str, ...], str]] = set()
    for dependency in dependencies:
        if not dependency.target_symbol:
            continue
        target_name = dependency.target_symbol.split(".")[-1]
        reference_key = (dependency.target_file, (target_name,), module_symbol.symbol_id)
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
                        "target_names": (target_name,),
                        "reference_type": "imports_symbol",
                    },
                ),
                source_symbol_id=module_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=(target_name,),
                reference_type="imports_symbol",
            )
        )
    for owner, target_name, line_number in iter_reference_entries(text):
        source_symbol_name = source_symbol_name_for_line(
            declared_entries,
            line_number=line_number,
        )
        source_symbol_id = local_symbol_ids.get(source_symbol_name or "", module_symbol.symbol_id)
        target_file = file_path if target_name in local_symbol_ids else None
        target_symbol_id = local_symbol_ids.get(target_name) if target_file == file_path else None
        if target_file is None and owner:
            binding = import_bindings.get(owner)
            if binding is not None:
                target_file = binding.target_file
        elif target_file is None:
            binding = import_bindings.get(target_name)
            if binding is not None:
                target_file = binding.target_file
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
                        "source_symbol_id": source_symbol_id,
                        "target_file": target_file,
                        "target_name": target_name,
                        "reference_type": "references_symbol",
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return tuple(symbols), dependencies, tuple(references)
