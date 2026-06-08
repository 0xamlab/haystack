from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    tlaplus_primitives as repository_tlaplus_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_tlaplus_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_tlaplus_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_tlaplus_primitives.ResolveSuffixMatch

_CollectedSymbol = repository_tlaplus_primitives._CollectedSymbol
_IDENTIFIER_RE = repository_tlaplus_primitives._IDENTIFIER_RE
_PREFERRED_ENTRYPOINT_PREFIXES = repository_tlaplus_primitives._PREFERRED_ENTRYPOINT_PREFIXES
_QUALIFIED_REFERENCE_RE = repository_tlaplus_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_tlaplus_primitives._RESERVED_SYMBOL_NAMES
_line_count = repository_tlaplus_primitives._line_count
_ordered_names = repository_tlaplus_primitives._ordered_names
has_tlaplus_path_hints = repository_tlaplus_primitives.has_tlaplus_path_hints
is_probable_tlaplus_source = repository_tlaplus_primitives.is_probable_tlaplus_source
iter_symbol_entries = repository_tlaplus_primitives.iter_symbol_entries
module_name_from_path = repository_tlaplus_primitives.module_name_from_path
module_name_from_text = repository_tlaplus_primitives.module_name_from_text
parse_extended_modules = repository_tlaplus_primitives.parse_extended_modules
parse_instance_statements = repository_tlaplus_primitives.parse_instance_statements
strip_comments = repository_tlaplus_primitives.strip_comments


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    module_name = module_name_from_text(stripped_text, file_path=file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "module"},
        ),
        symbol_name=module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=module_name,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
            qualified_names=_ordered_names(
                module_name,
                file_path,
                str(PurePosixPath(file_path).with_suffix("")),
                PurePosixPath(file_path).stem,
            ),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(
        stripped_text,
        file_path=file_path,
    ):
        qualified_names = _ordered_names(
            symbol_name,
            f"{module_name}.{symbol_name}" if module_name else "",
            f"{module_name}!{symbol_name}" if module_name else "",
        )
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": symbol_name,
                            "symbol_kind": symbol_kind,
                            "start_line": start_line,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=start_line,
                    end_line=start_line,
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=symbol_name,
                ),
                local_start_line=start_line,
                local_end_line=start_line,
                qualified_names=qualified_names,
            )
        )
    final_line = _line_count(stripped_text)
    finalized_symbols: list[_CollectedSymbol] = []
    for index, collected_symbol in enumerate(collected_symbols):
        end_line = (
            max(
                collected_symbols[index + 1].local_start_line - 1,
                collected_symbol.local_start_line,
            )
            if index + 1 < len(collected_symbols)
            else final_line
        )
        symbol = collected_symbol.symbol
        finalized_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=symbol.symbol_id,
                    symbol_name=symbol.symbol_name,
                    symbol_kind=symbol.symbol_kind,
                    start_line=symbol.start_line,
                    end_line=end_line,
                    parent_symbol_id=symbol.parent_symbol_id,
                    signature=symbol.signature,
                ),
                local_start_line=collected_symbol.local_start_line,
                local_end_line=end_line,
                qualified_names=collected_symbol.qualified_names,
            )
        )
    return tuple(finalized_symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_tlaplus_path_hints(path):
        return set()
    aliases = {
        file_path,
        str(path.with_suffix("")),
        path.stem,
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_tlaplus_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_text(text, file_path=file_path)
    aliases.add(module_name)
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def resolve_module_source(
    module_name: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_name = str(module_name or "").strip()
    if not normalized_name:
        return None
    candidate_targets = (normalized_name, f"{normalized_name}.tla")
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
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str, str, str | None]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}

    for module_name, line_number in parse_extended_modules(text):
        target_file = resolve_module_source(
            module_name,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = ("extends", module_name, target_file)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": module_name,
                            "line": line_number,
                            "type": "extends",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=module_name,
                    dependency_type="imports",
                )
            )
        import_bindings[module_name] = _ImportedSymbolBinding(
            alias=module_name,
            target_file=target_file,
            target_names=(module_name,),
        )

    for alias, module_name, line_number in parse_instance_statements(text):
        binding_alias = alias or module_name
        target_file = resolve_module_source(
            module_name,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = ("instance", binding_alias, target_file)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": binding_alias,
                            "module_name": module_name,
                            "line": line_number,
                            "type": "instance",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=binding_alias,
                    dependency_type="imports",
                )
            )
        import_bindings[binding_alias] = _ImportedSymbolBinding(
            alias=binding_alias,
            target_file=target_file,
            target_names=_ordered_names(module_name, binding_alias),
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
    dependencies, _bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
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
    del normalize_repository_relative_path
    if not is_probable_tlaplus_source(path=Path(file_path), text=text):
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
        resolve_suffix_match=resolve_suffix_match,
    )
    local_symbols_by_alias: dict[str, _Symbol] = {}
    for collected_symbol in collected_symbols:
        for alias in collected_symbol.qualified_names:
            local_symbols_by_alias.setdefault(alias, collected_symbol.symbol)
        local_symbols_by_alias.setdefault(
            collected_symbol.symbol.symbol_name,
            collected_symbol.symbol,
        )
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
        seen_reference_names: set[str] = set()
        for match in _QUALIFIED_REFERENCE_RE.finditer(snippet):
            module_alias = str(match.group("module") or "").strip()
            reference_name = str(match.group("name") or "").strip()
            if (
                not module_alias
                or not reference_name
                or module_alias == symbol.symbol_name
                or reference_name in _RESERVED_SYMBOL_NAMES
            ):
                continue
            binding = import_bindings.get(module_alias)
            if binding is None:
                continue
            seen_reference_names.add(f"{module_alias}!{reference_name}")
            _record_reference(
                source_symbol_id=symbol.symbol_id,
                target_symbol_id=None,
                target_file=binding.target_file,
                target_names=_ordered_names(reference_name, f"{module_alias}!{reference_name}"),
            )
        for match in _IDENTIFIER_RE.finditer(snippet):
            reference_name = str(match.group("name") or "").strip()
            if (
                not reference_name
                or reference_name in seen_reference_names
                or reference_name in _RESERVED_SYMBOL_NAMES
                or reference_name == symbol.symbol_name
            ):
                continue
            binding = import_bindings.get(reference_name)
            target_symbol = local_symbols_by_alias.get(reference_name)
            if binding is None and target_symbol is None:
                continue
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
                target_names=(reference_name,),
            )
    return (
        tuple(item.symbol for item in collected_symbols),
        tuple(dependencies),
        tuple(reference_candidates.values()),
    )
