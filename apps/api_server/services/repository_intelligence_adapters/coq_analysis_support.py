from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    coq_primitives as repository_coq_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_coq_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_coq_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_coq_primitives.ResolveSuffixMatch

COQ_CONFIG_BASENAMES = repository_coq_primitives.COQ_CONFIG_BASENAMES
_CollectedSymbol = repository_coq_primitives._CollectedSymbol
_IDENTIFIER_RE = repository_coq_primitives._IDENTIFIER_RE
_QUALIFIED_REFERENCE_RE = repository_coq_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_coq_primitives._RESERVED_SYMBOL_NAMES
_line_count = repository_coq_primitives._line_count
_line_number = repository_coq_primitives._line_number
_ordered_names = repository_coq_primitives._ordered_names
has_coq_path_hints = repository_coq_primitives.has_coq_path_hints
is_probable_coq_source = repository_coq_primitives.is_probable_coq_source
iter_symbol_entries = repository_coq_primitives.iter_symbol_entries
module_name_from_path = repository_coq_primitives.module_name_from_path
parse_project_roots = repository_coq_primitives.parse_project_roots
parse_project_sources = repository_coq_primitives.parse_project_sources
parse_require_modules = repository_coq_primitives.parse_require_modules
strip_comments = repository_coq_primitives.strip_comments


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    module_name = module_name_from_path(file_path)
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
    path_without_suffix = str(PurePosixPath(file_path).with_suffix(""))
    path_segments = PurePosixPath(path_without_suffix).parts
    module_aliases = {module_name, path_without_suffix, PurePosixPath(file_path).stem, file_path}
    for start_index in range(len(path_segments)):
        candidate = ".".join(part for part in path_segments[start_index:] if part)
        if candidate:
            module_aliases.add(candidate)
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
            qualified_names=tuple(sorted(alias for alias in module_aliases if alias)),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
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
                qualified_names=_ordered_names(
                    symbol_name,
                    f"{module_name}.{symbol_name}" if module_name else "",
                ),
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
    text: str | None = None,
    stripped_text: str | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_coq_path_hints(path):
        return set()
    aliases = {
        file_path,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        path.stem,
        module_name_from_path(file_path),
    }
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    if not is_probable_coq_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return {alias for alias in aliases if alias}
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def resolve_require_target(
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if not normalized_target:
        return None
    candidate_targets = [
        normalized_target,
        normalized_target.replace(".", "/"),
        f"{normalized_target}.v",
        f"{normalized_target.replace('.', '/')}.v",
    ]
    for candidate in candidate_targets:
        target_file = module_index.get(candidate)
        if target_file is not None:
            return target_file
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{normalized_target}.v",
            f"{normalized_target.replace('.', '/')}.v",
            f"/{normalized_target}.v",
            f"/{normalized_target.replace('.', '/')}.v",
        ],
    )


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_target, line_number in parse_require_modules(text, stripped_text=stripped_text):
        target_file = resolve_require_target(
            import_target,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "line": line_number,
                            "type": "require",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=PurePosixPath(import_target.replace(".", "/")).name,
                    dependency_type="imports",
                )
            )
        import_bindings.setdefault(
            import_target,
            _ImportedSymbolBinding(
                alias=import_target,
                target_file=target_file,
                target_names=(import_target,),
            ),
        )
        short_name = import_target.split(".")[-1]
        import_bindings.setdefault(
            short_name,
            _ImportedSymbolBinding(
                alias=short_name,
                target_file=target_file,
                target_names=_ordered_names(import_target, short_name),
            ),
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
    del normalize_repository_relative_path
    stripped_text = strip_comments(text)
    dependencies, _bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
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
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    del normalize_repository_relative_path
    stripped_text = strip_comments(text)
    if not is_probable_coq_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    lines = text.splitlines()
    local_symbol_lookup = {
        collected_symbol.symbol.symbol_name: collected_symbol.symbol.symbol_id
        for collected_symbol in collected_symbols
        if collected_symbol.symbol.symbol_kind != "module"
    }
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, int, str, str | None]] = set()
    for collected_symbol in collected_symbols:
        source_symbol = collected_symbol.symbol
        if source_symbol.symbol_kind == "module":
            continue
        snippet_start = max(source_symbol.start_line - 1, 0)
        snippet_end = max(source_symbol.end_line, source_symbol.start_line)
        snippet = "\n".join(lines[snippet_start:snippet_end])
        for match in _QUALIFIED_REFERENCE_RE.finditer(snippet):
            module_alias = str(match.group("module") or "").strip()
            symbol_name = str(match.group("name") or "").strip()
            if not module_alias or not symbol_name:
                continue
            binding = import_bindings.get(module_alias)
            target_file = (
                binding.target_file if binding is not None else module_index.get(module_alias)
            )
            line_number = source_symbol.start_line + snippet.count("\n", 0, match.start())
            reference_key = (source_symbol.symbol_id, line_number, symbol_name, target_file)
            if reference_key in seen_reference_keys:
                continue
            seen_reference_keys.add(reference_key)
            symbol_references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "file_path": file_path,
                            "source_symbol_id": source_symbol.symbol_id,
                            "target": f"{module_alias}.{symbol_name}",
                            "line": line_number,
                            "type": "references_symbol",
                        },
                    ),
                    source_symbol_id=source_symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=_ordered_names(
                        symbol_name,
                        f"{module_alias}.{symbol_name}",
                    ),
                    reference_type="references_symbol",
                )
            )
        for match in _IDENTIFIER_RE.finditer(snippet):
            symbol_name = str(match.group("name") or "").strip()
            if (
                not symbol_name
                or symbol_name in _RESERVED_SYMBOL_NAMES
                or symbol_name == source_symbol.symbol_name
            ):
                continue
            target_symbol_id = local_symbol_lookup.get(symbol_name)
            target_file = file_path if target_symbol_id is not None else None
            binding = import_bindings.get(symbol_name)
            target_names = _ordered_names(symbol_name)
            if binding is not None:
                target_file = target_file or binding.target_file
                target_names = _ordered_names(*binding.target_names, symbol_name)
            elif target_file is None:
                resolved_target = module_index.get(symbol_name)
                if resolved_target and resolved_target != file_path:
                    target_file = resolved_target
            if target_symbol_id is None and target_file is None:
                continue
            line_number = source_symbol.start_line + snippet.count("\n", 0, match.start())
            reference_key = (source_symbol.symbol_id, line_number, symbol_name, target_file)
            if reference_key in seen_reference_keys:
                continue
            seen_reference_keys.add(reference_key)
            symbol_references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "file_path": file_path,
                            "source_symbol_id": source_symbol.symbol_id,
                            "target": symbol_name,
                            "line": line_number,
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
        tuple(symbol_references),
    )
