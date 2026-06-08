from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    hcl_primitives as repository_hcl_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_hcl_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_hcl_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_hcl_primitives.ResolveSuffixMatch

_BlockEntry = repository_hcl_primitives._BlockEntry
_CollectedSymbol = repository_hcl_primitives._CollectedSymbol
_DATA_REF_RE = repository_hcl_primitives._DATA_REF_RE
_LOCAL_REF_RE = repository_hcl_primitives._LOCAL_REF_RE
_MODULE_REF_RE = repository_hcl_primitives._MODULE_REF_RE
_PREFERRED_DIRECTORY_ENTRY_BASENAMES = (
    repository_hcl_primitives._PREFERRED_DIRECTORY_ENTRY_BASENAMES
)
_RESOURCE_REF_RE = repository_hcl_primitives._RESOURCE_REF_RE
_RESERVED_REFERENCE_ROOTS = repository_hcl_primitives._RESERVED_REFERENCE_ROOTS
_VAR_REF_RE = repository_hcl_primitives._VAR_REF_RE
_line_count = repository_hcl_primitives._line_count
_ordered_names = repository_hcl_primitives._ordered_names
has_hcl_path_hints = repository_hcl_primitives.has_hcl_path_hints
is_probable_hcl_source = repository_hcl_primitives.is_probable_hcl_source
iter_block_entries = repository_hcl_primitives.iter_block_entries
iter_local_assignments = repository_hcl_primitives.iter_local_assignments
iter_module_source_statements = repository_hcl_primitives.iter_module_source_statements
module_name_from_path = repository_hcl_primitives.module_name_from_path
strip_comments = repository_hcl_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _symbol_identity(block: _BlockEntry) -> tuple[str, str, tuple[str, ...]]:
    if block.kind == "module" and block.label1:
        return (
            "module",
            f"module.{block.label1}",
            _ordered_names(f"module.{block.label1}", block.label1),
        )
    if block.kind == "variable" and block.label1:
        return (
            "variable",
            f"var.{block.label1}",
            _ordered_names(f"var.{block.label1}", block.label1),
        )
    if block.kind == "output" and block.label1:
        return (
            "output",
            f"output.{block.label1}",
            _ordered_names(f"output.{block.label1}", block.label1),
        )
    if block.kind == "provider" and block.label1:
        return (
            "provider",
            f"provider.{block.label1}",
            _ordered_names(f"provider.{block.label1}", block.label1),
        )
    if block.kind == "resource" and block.label1 and block.label2:
        name = f"{block.label1}.{block.label2}"
        return "resource", name, _ordered_names(name, f"resource.{name}", block.label2)
    if block.kind == "data" and block.label1 and block.label2:
        name = f"data.{block.label1}.{block.label2}"
        return "data", name, _ordered_names(name, f"{block.label1}.{block.label2}", block.label2)
    return block.kind or "block", block.kind or "block", _ordered_names(block.kind or "block")


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    file_module_name = module_name_from_path(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym", {"file_path": file_path, "symbol_name": file_module_name}
        ),
        symbol_name=file_module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=file_module_name,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
            qualified_names=_ordered_names(
                file_module_name,
                file_path,
                _without_suffix_path(PurePosixPath(file_path)),
            ),
        )
    ]
    for block in iter_block_entries(text):
        symbol_kind, symbol_name, aliases = _symbol_identity(block)
        block_symbol = _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "symbol_name": symbol_name,
                    "start_line": block.start_line,
                },
            ),
            symbol_name=symbol_name,
            symbol_kind=symbol_kind,
            start_line=block.start_line,
            end_line=block.end_line,
            parent_symbol_id=module_symbol.symbol_id,
            signature=symbol_name,
        )
        collected_symbols.append(
            _CollectedSymbol(
                symbol=block_symbol,
                local_start_line=block.start_line,
                local_end_line=block.end_line,
                qualified_names=aliases,
            )
        )
        if block.kind != "locals":
            continue
        local_entries = iter_local_assignments(block)
        for index, (local_name, start_line) in enumerate(local_entries):
            if index + 1 < len(local_entries):
                end_line = local_entries[index + 1][1] - 1
            else:
                end_line = block.end_line
            collected_symbols.append(
                _CollectedSymbol(
                    symbol=_Symbol(
                        symbol_id=stable_identifier(
                            "sym",
                            {
                                "file_path": file_path,
                                "symbol_name": f"local.{local_name}",
                                "start_line": start_line,
                            },
                        ),
                        symbol_name=f"local.{local_name}",
                        symbol_kind="local",
                        start_line=start_line,
                        end_line=max(start_line, end_line),
                        parent_symbol_id=block_symbol.symbol_id,
                        signature=local_name,
                    ),
                    local_start_line=start_line,
                    local_end_line=max(start_line, end_line),
                    qualified_names=_ordered_names(f"local.{local_name}", local_name),
                )
            )
    return tuple(collected_symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_hcl_path_hints(path):
        return set()
    aliases = {file_path, _without_suffix_path(path), path.stem}
    if (
        path.name.lower() in _PREFERRED_DIRECTORY_ENTRY_BASENAMES
        and str(path.parent) not in {"", "."}
    ):
        aliases.add(str(path.parent))
        aliases.add(path.parent.name)
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_hcl_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    aliases.add(module_name_from_path(file_path))
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def resolve_module_source(
    source_target: str,
    current_file: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(source_target or "").strip()
    if not normalized_target or not normalized_target.startswith(("./", "../")):
        return None
    normalized_root = normalize_repository_relative_path(
        str(PurePosixPath(current_file).parent / normalized_target)
    )
    if not normalized_root:
        return None
    candidate_targets = (
        normalized_root,
        f"{normalized_root}/main.tf",
        f"{normalized_root}/main.hcl",
        f"{normalized_root}/terragrunt.hcl",
        f"{normalized_root}/versions.tf",
    )
    for candidate in candidate_targets:
        target_file = module_index.get(candidate)
        if target_file is not None:
            return target_file
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_targets)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str, str, str | None]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for block in iter_block_entries(text):
        if block.kind != "module" or not block.label1:
            continue
        module_alias = f"module.{block.label1}"
        target_file: str | None = None
        for source_target, line_number in iter_module_source_statements(block):
            resolved_target = resolve_module_source(
                source_target,
                file_path,
                module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            dependency_key = ("module", module_alias, resolved_target)
            if dependency_key not in dependency_keys:
                dependency_keys.add(dependency_key)
                dependencies.append(
                    _Dependency(
                        dependency_edge_id=stable_identifier(
                            "dep",
                            {"file_path": file_path, "target": module_alias, "line": line_number},
                        ),
                        source_file=file_path,
                        target_file=resolved_target,
                        target_symbol=module_alias,
                        dependency_type="imports",
                    )
                )
            if resolved_target is not None:
                target_file = resolved_target
        import_bindings[module_alias] = _ImportedSymbolBinding(
            alias=module_alias,
            target_file=target_file,
            target_names=(module_alias, block.label1),
        )
    return tuple(dependencies), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies, _bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
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
    if not is_probable_hcl_source(path=Path(file_path), text=text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    local_symbols_by_alias: dict[str, _Symbol] = {}
    same_file_resource_roots: set[str] = set()
    for collected_symbol in collected_symbols:
        for alias in collected_symbol.qualified_names:
            local_symbols_by_alias.setdefault(alias, collected_symbol.symbol)
        if collected_symbol.symbol.symbol_kind in {"resource", "data"}:
            root_name = collected_symbol.symbol.symbol_name.split(".", 1)[0]
            if root_name not in {"data", "module", "var", "local", "output", "provider"}:
                same_file_resource_roots.add(root_name)
    stripped_lines = strip_comments(text).splitlines()
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}

    def _record_reference(
        *,
        source_symbol_id: str,
        target_symbol_id: str | None,
        target_file: str | None,
        target_names: tuple[str, ...],
    ) -> None:
        edge_id = stable_identifier(
            "ref",
            {
                "source_symbol_id": source_symbol_id,
                "target_symbol_id": target_symbol_id,
                "target_file": target_file,
                "target_names": target_names,
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            _SymbolReferenceCandidate(
                reference_edge_id=edge_id,
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            ),
        )

    for collected_symbol in collected_symbols:
        symbol = collected_symbol.symbol
        if symbol.symbol_kind == "module":
            continue
        snippet = "\n".join(
            stripped_lines[max(symbol.start_line - 1, 0) : max(symbol.end_line, symbol.start_line)]
        )
        for match in _MODULE_REF_RE.finditer(snippet):
            alias = f"module.{str(match.group('name') or '').strip()}"
            binding = import_bindings.get(alias)
            target_symbol = local_symbols_by_alias.get(alias)
            _record_reference(
                source_symbol_id=symbol.symbol_id,
                target_symbol_id=(
                    None
                    if binding and binding.target_file
                    else getattr(target_symbol, "symbol_id", None)
                ),
                target_file=(
                    binding.target_file if binding else file_path if target_symbol else None
                ),
                target_names=(alias,),
            )
        for regex, alias_prefix in ((_VAR_REF_RE, "var"), (_LOCAL_REF_RE, "local")):
            for match in regex.finditer(snippet):
                alias = f"{alias_prefix}.{str(match.group('name') or '').strip()}"
                target_symbol = local_symbols_by_alias.get(alias)
                if target_symbol is None:
                    continue
                _record_reference(
                    source_symbol_id=symbol.symbol_id,
                    target_symbol_id=target_symbol.symbol_id,
                    target_file=file_path,
                    target_names=(alias,),
                )
        for match in _DATA_REF_RE.finditer(snippet):
            alias = (
                f"data.{str(match.group('type') or '').strip()}."
                f"{str(match.group('name') or '').strip()}"
            )
            if alias.endswith("."):
                continue
            target_symbol = local_symbols_by_alias.get(alias)
            _record_reference(
                source_symbol_id=symbol.symbol_id,
                target_symbol_id=getattr(target_symbol, "symbol_id", None),
                target_file=file_path if target_symbol else module_index.get(alias),
                target_names=(alias,),
            )
        for match in _RESOURCE_REF_RE.finditer(snippet):
            root = str(match.group("type") or "").strip()
            if not root or root in _RESERVED_REFERENCE_ROOTS or (
                root not in same_file_resource_roots and "_" not in root
            ):
                continue
            alias = f"{root}.{str(match.group('name') or '').strip()}"
            target_symbol = local_symbols_by_alias.get(alias)
            if target_symbol is None and module_index.get(alias) is None:
                continue
            _record_reference(
                source_symbol_id=symbol.symbol_id,
                target_symbol_id=getattr(target_symbol, "symbol_id", None),
                target_file=file_path if target_symbol else module_index.get(alias),
                target_names=(alias,),
            )
    return (
        tuple(item.symbol for item in collected_symbols),
        tuple(dependencies),
        tuple(reference_candidates.values()),
    )
