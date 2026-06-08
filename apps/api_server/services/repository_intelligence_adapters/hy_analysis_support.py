from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    hy_primitives as repository_hy_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_hy_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_hy_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_hy_primitives.ResolveSuffixMatch

HY_SUFFIXES = repository_hy_primitives.HY_SUFFIXES
_CollectedSymbol = repository_hy_primitives._CollectedSymbol
_QUALIFIED_REFERENCE_RE = repository_hy_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_hy_primitives._RESERVED_SYMBOL_NAMES
_UNQUALIFIED_REFERENCE_RE = repository_hy_primitives._UNQUALIFIED_REFERENCE_RE

_line_count = repository_hy_primitives._line_count
has_hy_path_hints = repository_hy_primitives.has_hy_path_hints
is_probable_hy_source = repository_hy_primitives.is_probable_hy_source
iter_symbol_entries = repository_hy_primitives.iter_symbol_entries
module_name_from_path = repository_hy_primitives.module_name_from_path
normalize_identifier = repository_hy_primitives.normalize_identifier
normalize_symbol_name = repository_hy_primitives.normalize_symbol_name
parse_import_entries = repository_hy_primitives.parse_import_entries
strip_comments = repository_hy_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _candidate_import_keys(
    *,
    file_path: str,
    import_target: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_target = normalize_identifier(import_target)
    if not normalized_target:
        return ()
    dotted_target = normalized_target.replace(".", "/")
    current_dir = PurePosixPath(file_path).parent
    candidate_keys: list[str] = []
    if normalized_target.startswith("."):
        relative_parts = [part for part in normalized_target.split(".") if part]
        resolved_path = current_dir.joinpath(*relative_parts).as_posix()
        candidate_keys.extend(
            (resolved_path, f"{resolved_path}.hy", f"{resolved_path}/hy_init.hy", f"{resolved_path}/__init__.hy")
        )
    else:
        candidate_keys.extend(
            (
                dotted_target,
                f"{dotted_target}.hy",
                f"{dotted_target}/hy_init.hy",
                f"{dotted_target}/__init__.hy",
                normalized_target,
            )
        )
    normalized_candidates: list[str] = []
    seen: set[str] = set()
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if normalized_candidate and normalized_candidate not in seen:
            seen.add(normalized_candidate)
            normalized_candidates.append(normalized_candidate)
    return tuple(normalized_candidates)


def resolve_import(
    *,
    file_path: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    candidate_keys = _candidate_import_keys(
        file_path=file_path,
        import_target=import_target,
        normalize_repository_relative_path=normalize_repository_relative_path,
    )
    if not candidate_keys:
        return None
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_keys)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path)
    final_line = _line_count(stripped_text)
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
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=final_line,
            qualified_names=(module_name,) if module_name else (),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
        qualified_names = repository_hy_primitives._ordered_names(
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
    if path.suffix.lower() not in HY_SUFFIXES:
        return set()
    aliases = {
        file_path,
        _without_suffix_path(path),
        path.stem,
    }
    module_name = module_name_from_path(file_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.replace(".", "/"))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_hy_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


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
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_kind, import_target, import_alias, imported_names, line_number in parse_import_entries(text):
        target_file = resolve_import(
            file_path=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, import_kind)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "kind": import_kind,
                            "line": line_number,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=import_target.rsplit(".", 1)[-1],
                    dependency_type="imports",
                )
            )
        module_alias = import_alias or import_target.rsplit(".", 1)[-1]
        if module_alias and module_alias not in _RESERVED_SYMBOL_NAMES:
            import_bindings.setdefault(
                module_alias,
                _ImportedSymbolBinding(
                    alias=module_alias,
                    target_file=target_file,
                    target_names=(),
                ),
            )
        for imported_name, imported_alias in imported_names:
            if imported_name == "*":
                continue
            alias_name = imported_alias or imported_name
            if not alias_name or alias_name in _RESERVED_SYMBOL_NAMES:
                continue
            import_bindings.setdefault(
                alias_name,
                _ImportedSymbolBinding(
                    alias=alias_name,
                    target_file=target_file,
                    target_names=(imported_name,),
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
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        stripped_text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=stripped_text,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    local_symbol_ids: dict[str, str] = {}
    for collected_symbol in collected_symbols[1:]:
        local_symbol_ids.setdefault(collected_symbol.symbol.symbol_name, collected_symbol.symbol.symbol_id)
        for qualified_name in collected_symbol.qualified_names:
            local_symbol_ids.setdefault(qualified_name, collected_symbol.symbol.symbol_id)
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}

    def _record_reference(
        *,
        source_symbol_id: str,
        target_symbol_id: str | None,
        target_file: str | None,
        target_names: tuple[str, ...],
    ) -> None:
        if target_symbol_id is None and target_file is None and not target_names:
            return
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

    lines = stripped_text.splitlines()
    for collected_symbol in collected_symbols[1:]:
        symbol_lines = lines[
            max(0, collected_symbol.local_start_line - 1) : collected_symbol.local_end_line
        ]
        symbol_text = "\n".join(symbol_lines)
        for match in _QUALIFIED_REFERENCE_RE.finditer(symbol_text):
            alias = normalize_identifier(match.group("alias"))
            member_name = normalize_symbol_name(match.group("name"))
            if not alias or not member_name:
                continue
            binding = import_bindings.get(alias)
            if binding is None:
                continue
            _record_reference(
                source_symbol_id=collected_symbol.symbol.symbol_id,
                target_symbol_id=None,
                target_file=binding.target_file,
                target_names=(member_name,),
            )
        for match in _UNQUALIFIED_REFERENCE_RE.finditer(symbol_text):
            referenced_name = normalize_symbol_name(match.group("name"))
            if not referenced_name or referenced_name in _RESERVED_SYMBOL_NAMES:
                continue
            binding = import_bindings.get(referenced_name)
            if binding is not None:
                _record_reference(
                    source_symbol_id=collected_symbol.symbol.symbol_id,
                    target_symbol_id=None,
                    target_file=binding.target_file,
                    target_names=binding.target_names or (referenced_name,),
                )
                continue
            target_symbol_id = local_symbol_ids.get(referenced_name)
            if target_symbol_id is None or target_symbol_id == collected_symbol.symbol.symbol_id:
                continue
            _record_reference(
                source_symbol_id=collected_symbol.symbol.symbol_id,
                target_symbol_id=target_symbol_id,
                target_file=file_path,
                target_names=(referenced_name,),
            )
    return symbols, dependencies, tuple(reference_candidates.values())
