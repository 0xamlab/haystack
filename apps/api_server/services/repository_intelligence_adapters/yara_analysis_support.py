from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    yara_primitives as repository_yara_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_yara_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_yara_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_yara_primitives.ResolveSuffixMatch

_CollectedSymbol = repository_yara_primitives._CollectedSymbol
_condition_text_from_stripped_text = repository_yara_primitives._condition_text_from_stripped_text
_IDENTIFIER_RE = repository_yara_primitives._IDENTIFIER_RE
_is_probable_yara_source_from_stripped_text = (
    repository_yara_primitives._is_probable_yara_source_from_stripped_text
)
_iter_rule_entries_from_stripped_text = repository_yara_primitives._iter_rule_entries_from_stripped_text
_QUALIFIED_REFERENCE_RE = repository_yara_primitives._QUALIFIED_REFERENCE_RE
_parse_import_modules_from_stripped_text = (
    repository_yara_primitives._parse_import_modules_from_stripped_text
)
_parse_include_statements_from_stripped_text = (
    repository_yara_primitives._parse_include_statements_from_stripped_text
)
_RESERVED_SYMBOL_NAMES = repository_yara_primitives._RESERVED_SYMBOL_NAMES
_line_count = repository_yara_primitives._line_count
_ordered_names = repository_yara_primitives._ordered_names
condition_text = repository_yara_primitives.condition_text
has_yara_path_hints = repository_yara_primitives.has_yara_path_hints
is_probable_yara_source = repository_yara_primitives.is_probable_yara_source
iter_rule_entries = repository_yara_primitives.iter_rule_entries
module_name_from_path = repository_yara_primitives.module_name_from_path
parse_import_modules = repository_yara_primitives.parse_import_modules
parse_include_statements = repository_yara_primitives.parse_include_statements
strip_comments = repository_yara_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _collect_symbols(
    *,
    file_path: str,
    stripped_text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    module_name = module_name_from_path(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier("sym", {"file_path": file_path, "symbol_name": module_name}),
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
                _without_suffix_path(PurePosixPath(file_path)),
            ),
        )
    ]
    for symbol_name, start_line in _iter_rule_entries_from_stripped_text(stripped_text):
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": symbol_name,
                            "start_line": start_line,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind="rule",
                    start_line=start_line,
                    end_line=start_line,
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=symbol_name,
                ),
                local_start_line=start_line,
                local_end_line=start_line,
                qualified_names=_ordered_names(symbol_name, f"{module_name}.{symbol_name}"),
            )
        )
    final_line = _line_count(stripped_text)
    finalized_symbols: list[_CollectedSymbol] = []
    for index, item in enumerate(collected_symbols):
        end_line = (
            max(collected_symbols[index + 1].local_start_line - 1, item.local_start_line)
            if index + 1 < len(collected_symbols)
            else final_line
        )
        finalized_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=item.symbol.symbol_id,
                    symbol_name=item.symbol.symbol_name,
                    symbol_kind=item.symbol.symbol_kind,
                    start_line=item.symbol.start_line,
                    end_line=end_line,
                    parent_symbol_id=item.symbol.parent_symbol_id,
                    signature=item.symbol.signature,
                ),
                local_start_line=item.local_start_line,
                local_end_line=end_line,
                qualified_names=item.qualified_names,
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
    if not has_yara_path_hints(path):
        return set()
    aliases = {file_path, _without_suffix_path(path), path.stem}
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    stripped_text = strip_comments(text)
    if not _is_probable_yara_source_from_stripped_text(stripped_text):
        return {alias for alias in aliases if alias}
    aliases.add(module_name_from_path(file_path))
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        stripped_text=stripped_text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def resolve_include(
    include_target: str,
    current_file: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(include_target or "").strip()
    if not normalized_target:
        return None
    normalized_target = normalize_repository_relative_path(
        str(PurePosixPath(current_file).parent / normalized_target)
    )
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    return resolve_suffix_match(module_index=module_index, suffixes=(normalized_target,))


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    return _extract_import_bindings_from_stripped_text(
        file_path=file_path,
        stripped_text=strip_comments(text),
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )


def _extract_import_bindings_from_stripped_text(
    *,
    file_path: str,
    stripped_text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str, str, str | None]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for include_target, line_number in _parse_include_statements_from_stripped_text(stripped_text):
        target_file = resolve_include(
            include_target,
            file_path,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = ("include", include_target, target_file)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {"file_path": file_path, "target": include_target, "line": line_number},
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=PurePosixPath(include_target).stem or include_target,
                    dependency_type="includes",
                )
            )
    for module_name, line_number in _parse_import_modules_from_stripped_text(stripped_text):
        dependency_key = ("import", module_name, None)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {"file_path": file_path, "target": module_name, "line": line_number},
                    ),
                    source_file=file_path,
                    target_file=None,
                    target_symbol=module_name,
                    dependency_type="imports",
                )
            )
        import_bindings[module_name] = _ImportedSymbolBinding(
            alias=module_name,
            target_file=None,
            target_names=(module_name,),
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
    stripped_text = strip_comments(text)
    if not _is_probable_yara_source_from_stripped_text(stripped_text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        stripped_text=stripped_text,
        stable_identifier=stable_identifier,
    )
    dependencies, import_bindings = _extract_import_bindings_from_stripped_text(
        file_path=file_path,
        stripped_text=stripped_text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    local_symbols = {item.symbol.symbol_name: item.symbol for item in collected_symbols}
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str, str | None, str | None]] = set()
    stripped_lines = stripped_text.splitlines()

    def _record_reference(
        *,
        source_symbol: _Symbol,
        target_name: str,
        target_file: str | None,
        target_symbol_id: str | None,
    ) -> None:
        reference_key = (source_symbol.symbol_id, target_name, target_file, target_symbol_id)
        if reference_key in seen_reference_keys:
            return
        seen_reference_keys.add(reference_key)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "symref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": source_symbol.symbol_id,
                        "target": target_name,
                        "line": source_symbol.start_line,
                    },
                ),
                source_symbol_id=source_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=(target_name,),
                reference_type="calls",
            )
        )

    for collected_symbol in collected_symbols:
        if collected_symbol.symbol.symbol_kind != "rule":
            continue
        rule_text = "\n".join(
            stripped_lines[max(collected_symbol.local_start_line - 1, 0) : collected_symbol.local_end_line]
        )
        masked_text = list(_condition_text_from_stripped_text(rule_text))
        if not masked_text:
            continue
        current_text = "".join(masked_text)
        for match in _QUALIFIED_REFERENCE_RE.finditer(current_text):
            module_name = str(match.group("module") or "").strip()
            if module_name in import_bindings:
                for index in range(match.start(), match.end()):
                    masked_text[index] = " "
        for match in _IDENTIFIER_RE.finditer("".join(masked_text)):
            symbol_name = str(match.group("name") or "").strip()
            if (
                not symbol_name
                or symbol_name == collected_symbol.symbol.symbol_name
                or symbol_name in _RESERVED_SYMBOL_NAMES
                or symbol_name in import_bindings
            ):
                continue
            local_target = local_symbols.get(symbol_name)
            if local_target is not None:
                _record_reference(
                    source_symbol=collected_symbol.symbol,
                    target_name=symbol_name,
                    target_file=file_path,
                    target_symbol_id=local_target.symbol_id,
                )
                continue
            target_file = module_index.get(symbol_name)
            if target_file is None:
                continue
            _record_reference(
                source_symbol=collected_symbol.symbol,
                target_name=symbol_name,
                target_file=target_file,
                target_symbol_id=None,
            )
    return (
        tuple(item.symbol for item in collected_symbols),
        tuple(dependencies),
        tuple(symbol_references),
    )
