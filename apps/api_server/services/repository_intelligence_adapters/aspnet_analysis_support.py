from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    aspnet_primitives as repository_aspnet_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_aspnet_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_aspnet_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_aspnet_primitives.ResolveSuffixMatch

ASPNET_SUFFIXES = repository_aspnet_primitives.ASPNET_SUFFIXES
_line_count = repository_aspnet_primitives._line_count
has_aspnet_path_hints = repository_aspnet_primitives.has_aspnet_path_hints
is_probable_aspnet_source = repository_aspnet_primitives.is_probable_aspnet_source
iter_declared_alias_entries = repository_aspnet_primitives.iter_declared_alias_entries
iter_dependency_entries = repository_aspnet_primitives.iter_dependency_entries
iter_directive_entries = repository_aspnet_primitives.iter_directive_entries
iter_reference_entries = repository_aspnet_primitives.iter_reference_entries
iter_symbol_entries = repository_aspnet_primitives.iter_symbol_entries
module_name_from_path = repository_aspnet_primitives.module_name_from_path
normalize_identifier = repository_aspnet_primitives.normalize_identifier
normalize_target_path = repository_aspnet_primitives.normalize_target_path
path_aliases_for_file = repository_aspnet_primitives.path_aliases_for_file
primary_directive_kind = repository_aspnet_primitives.primary_directive_kind
resolve_target = repository_aspnet_primitives.resolve_target
source_symbol_name_for_line = repository_aspnet_primitives.source_symbol_name_for_line
strip_comments = repository_aspnet_primitives.strip_comments


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
    if not is_probable_aspnet_source(path=Path(file_path), text=text):
        return aliases
    for alias_name, _symbol_kind, _line_number in iter_declared_alias_entries(text):
        aliases.add(alias_name)
        aliases.add(alias_name.lower())
    return {alias for alias in aliases if alias}


def _dependency_type_for_kind(kind: str) -> str:
    return {
        "codebehind": "loads_codebehind",
        "include_file": "includes_file",
        "include_virtual": "includes_virtual",
        "master_page": "uses_master_page",
        "master_type": "binds_master_page_type",
        "previous_page_type": "binds_previous_page_type",
        "reference_control": "references_control",
        "reference_page": "references_page",
        "reference_virtual": "references_virtual_path",
        "register_control": "loads_registered_control",
    }[kind]


def _imported_control_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for dependency_kind, import_target, target_symbol, _line_number in iter_dependency_entries(text):
        if dependency_kind != "register_control" or not target_symbol:
            continue
        target_file = resolve_target(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        bindings[target_symbol.lower()] = _ImportedSymbolBinding(
            alias=target_symbol.lower(),
            target_file=target_file,
            target_names=(target_symbol.rsplit(":", 1)[-1],),
        )
    return bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_aspnet_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependency_keys: set[tuple[str, str | None, str | None]] = set()
    for dependency_kind, import_target, target_symbol, line_number in iter_dependency_entries(text):
        dependency_type = _dependency_type_for_kind(dependency_kind)
        target_file = resolve_target(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (dependency_type, target_file, target_symbol)
        if dependency_key in seen_dependency_keys:
            continue
        seen_dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "dependency_kind": dependency_kind,
                        "file_path": file_path,
                        "line": line_number,
                        "target": import_target,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type=dependency_type,
            )
        )
    return tuple(dependencies)


def _module_symbol_kind(file_path: str, text: str) -> str:
    directive_kind = primary_directive_kind(text) or ""
    return {
        "application": "aspnet_application",
        "control": "aspnet_control",
        "master": "aspnet_master",
        "page": "aspnet_page",
        "webhandler": "aspnet_handler",
        "webservice": "aspnet_service",
    }.get(directive_kind, f"aspnet_{Path(file_path).suffix.lstrip('.') or 'file'}")


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
    if not is_probable_aspnet_source(path=Path(file_path), text=text):
        return (), (), ()
    module_symbol = _Symbol(
        symbol_id=stable_identifier("sym", {"file_path": file_path, "symbol_kind": "module"}),
        symbol_name=Path(file_path).stem,
        symbol_kind=_module_symbol_kind(file_path, text),
        start_line=1,
        end_line=_line_count(text),
        parent_symbol_id=None,
        signature=file_path,
    )
    symbols = [module_symbol]
    symbol_ids_by_name: dict[str, str] = {}
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbol = _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "line": line_number,
                    "symbol_kind": symbol_kind,
                    "symbol_name": symbol_name,
                },
            ),
            symbol_name=symbol_name,
            symbol_kind=symbol_kind,
            start_line=line_number,
            end_line=line_number,
            parent_symbol_id=module_symbol.symbol_id,
            signature=symbol_name,
        )
        symbols.append(symbol)
        symbol_ids_by_name.setdefault(symbol_name, symbol.symbol_id)
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    imported_control_bindings = _imported_control_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    master_page_target = next(
        (
            dependency.target_file
            for dependency in dependencies
            if dependency.dependency_type in {"uses_master_page", "binds_master_page_type"}
            and dependency.target_file
        ),
        None,
    )
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str | None, tuple[str, ...], str]] = set()
    for reference_kind, owner, target_name, _line_number in iter_reference_entries(text):
        target_file: str | None = None
        target_symbol_id: str | None = None
        reference_type = "references_symbol"
        if reference_kind == "registered_control_reference":
            binding = imported_control_bindings.get(f"{owner}:{target_name}".lower())
            if binding is None:
                continue
            target_file = binding.target_file
            target_names = binding.target_names or (target_name,)
        elif reference_kind == "content_placeholder_reference":
            target_file = master_page_target
            target_symbol_id = symbol_ids_by_name.get(target_name)
            target_names = (target_name,)
        else:
            target_names = (target_name,)
        reference_key = (target_file, target_symbol_id, target_names, reference_type)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "reference_kind": reference_kind,
                        "target_file": target_file,
                        "target_names": target_names,
                    },
                ),
                source_symbol_id=module_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=target_names,
                reference_type=reference_type,
            )
        )
    return tuple(symbols), dependencies, tuple(symbol_references)
