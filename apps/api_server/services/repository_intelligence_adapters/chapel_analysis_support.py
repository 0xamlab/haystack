from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    chapel_primitives as repository_chapel_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_chapel_primitives.StableIdentifier
ResolveSuffixMatch = repository_chapel_primitives.ResolveSuffixMatch

_CollectedSymbol = repository_chapel_primitives._CollectedSymbol
_RESERVED_SYMBOL_NAMES = repository_chapel_primitives._RESERVED_SYMBOL_NAMES
_line_count = repository_chapel_primitives._line_count
_ordered_names = repository_chapel_primitives._ordered_names
has_chapel_path_hints = repository_chapel_primitives.has_chapel_path_hints
is_probable_chapel_source = repository_chapel_primitives.is_probable_chapel_source
iter_symbol_entries = repository_chapel_primitives.iter_symbol_entries
module_name_from_path = repository_chapel_primitives.module_name_from_path
module_name_from_text = repository_chapel_primitives.module_name_from_text
parse_reference_targets = repository_chapel_primitives.parse_reference_targets
parse_use_import_statements = repository_chapel_primitives.parse_use_import_statements
strip_comments = repository_chapel_primitives.strip_comments


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
    if not has_chapel_path_hints(path):
        return set()
    aliases = {file_path, str(path.with_suffix("")), path.stem}
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_chapel_source(path=Path(file_path), text=text):
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


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if not normalized_target:
        return None
    stem = normalized_target.rsplit(".", 1)[-1]
    candidate_targets = (
        normalized_target,
        stem,
        f"{normalized_target}.chpl",
        f"{stem}.chpl",
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
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    dependency_keys: set[tuple[str, str, str | None]] = set()
    for statement_kind, import_target, alias, line_number in parse_use_import_statements(text):
        target_file = resolve_import(
            import_target,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        binding_alias = alias or import_target.rsplit(".", 1)[-1]
        dependency_key = (statement_kind, binding_alias, target_file)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": binding_alias,
                            "line": line_number,
                            "type": statement_kind,
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
            target_names=_ordered_names(import_target, binding_alias),
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


def resolve_target(
    target_name: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    return resolve_import(
        target_name,
        module_index,
        resolve_suffix_match=resolve_suffix_match,
    )


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
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    symbol_name_to_id = {
        collected_symbol.symbol.symbol_name: collected_symbol.symbol.symbol_id
        for collected_symbol in collected_symbols
    }
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str | None, str, str]] = set()
    for qualifier, symbol_name, line_number in parse_reference_targets(text):
        if symbol_name in _RESERVED_SYMBOL_NAMES:
            continue
        source_symbol = next(
            (
                collected_symbol.symbol
                for collected_symbol in reversed(collected_symbols)
                if collected_symbol.local_start_line <= line_number
                <= collected_symbol.local_end_line
            ),
            collected_symbols[0].symbol,
        )
        candidate_targets: list[tuple[str | None, str | None, tuple[str, ...]]] = []
        if qualifier:
            import_binding = import_bindings.get(qualifier)
            candidate_targets.append(
                (
                    import_binding.target_file if import_binding else None,
                    None,
                    _ordered_names(symbol_name, f"{qualifier}.{symbol_name}"),
                )
            )
        else:
            import_binding = import_bindings.get(symbol_name)
            if symbol_name in symbol_name_to_id:
                candidate_targets.append(
                    (file_path, symbol_name_to_id.get(symbol_name), (symbol_name,))
                )
            elif import_binding is not None:
                candidate_targets.append(
                    (
                        import_binding.target_file,
                        None,
                        _ordered_names(symbol_name, *import_binding.target_names),
                    )
                )
            else:
                imported_targets = [
                    binding
                    for binding in import_bindings.values()
                    if binding.target_file is not None
                ]
                if imported_targets:
                    candidate_targets.extend(
                        (
                            binding.target_file,
                            None,
                            _ordered_names(symbol_name, *binding.target_names),
                        )
                        for binding in imported_targets
                    )
                else:
                    candidate_targets.append((None, None, (symbol_name,)))
        for target_file, target_symbol_id, target_names in candidate_targets:
            if target_file == file_path and target_symbol_id is None:
                target_symbol_id = symbol_name_to_id.get(symbol_name)
            reference_key = (
                source_symbol.symbol_id,
                target_file,
                target_symbol_id,
                "|".join(target_names),
            )
            if reference_key in seen_reference_keys:
                continue
            seen_reference_keys.add(reference_key)
            references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "source_symbol_id": source_symbol.symbol_id,
                            "target_symbol_id": target_symbol_id,
                            "target_file": target_file,
                            "target_names": target_names,
                            "type": "references_symbol",
                        },
                    ),
                    source_symbol_id=source_symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=target_symbol_id,
                    target_file=target_file,
                    target_names=target_names,
                    reference_type="references_symbol",
                )
            )
    return (
        tuple(collected_symbol.symbol for collected_symbol in collected_symbols),
        dependencies,
        tuple(references),
    )
