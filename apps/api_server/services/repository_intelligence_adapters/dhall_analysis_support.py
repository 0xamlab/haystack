from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    dhall_primitives as repository_dhall_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_dhall_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_dhall_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_dhall_primitives.ResolveSuffixMatch

_CollectedSymbol = repository_dhall_primitives._CollectedSymbol
_KNOWN_SUFFIXES = repository_dhall_primitives._KNOWN_SUFFIXES
_PACKAGE_STYLE_BASENAMES = repository_dhall_primitives._PACKAGE_STYLE_BASENAMES
_QUALIFIED_REFERENCE_RE = repository_dhall_primitives._QUALIFIED_REFERENCE_RE

_line_count = repository_dhall_primitives._line_count
_line_number = repository_dhall_primitives._line_number
_ordered_names = repository_dhall_primitives._ordered_names
has_dhall_path_hints = repository_dhall_primitives.has_dhall_path_hints
is_probable_dhall_source = repository_dhall_primitives.is_probable_dhall_source
iter_symbol_entries = repository_dhall_primitives.iter_symbol_entries
module_name_from_path = repository_dhall_primitives.module_name_from_path
parse_bound_import_statements = repository_dhall_primitives.parse_bound_import_statements
parse_import_statements = repository_dhall_primitives.parse_import_statements
strip_comments = repository_dhall_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _candidate_import_keys(
    *,
    file_path: str,
    import_target: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_target = str(import_target or "").strip().strip('"').strip("'")
    if not normalized_target:
        return ()
    target_path = PurePosixPath(normalized_target)
    current_directory = PurePosixPath(file_path).parent
    if normalized_target.startswith(("./", "../")):
        resolved_path = current_directory.joinpath(target_path).as_posix()
    else:
        resolved_path = target_path.as_posix()
    candidate_keys = (
        resolved_path,
        f"{resolved_path}.dhall",
        f"{resolved_path}/package.dhall",
        f"{resolved_path}/default.dhall",
        f"{resolved_path}/defaults.dhall",
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
            qualified_names=_ordered_names(
                module_name,
                module_name.replace("/", ".") if module_name else "",
            ),
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
                    f"{module_name.replace('/', '.')}.{symbol_name}" if module_name else "",
                    f"{module_name}/{symbol_name}" if module_name else "",
                ),
            )
        )
    finalized_symbols: list[_CollectedSymbol] = []
    for index, collected_symbol in enumerate(collected_symbols):
        next_start_line = (
            collected_symbols[index + 1].local_start_line
            if index + 1 < len(collected_symbols)
            else None
        )
        end_line = (
            max(next_start_line - 1, collected_symbol.local_start_line)
            if next_start_line is not None
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


def _source_symbol_id_for_line(
    collected_symbols: tuple[_CollectedSymbol, ...],
    line_number: int,
) -> str | None:
    for collected_symbol in reversed(collected_symbols):
        if collected_symbol.local_start_line <= line_number <= collected_symbol.local_end_line:
            return collected_symbol.symbol.symbol_id
    return collected_symbols[0].symbol.symbol_id if collected_symbols else None


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        _without_suffix_path(path),
        _without_suffix_path(path).replace("/", "."),
        path.stem,
    }
    if path.name.lower() in _PACKAGE_STYLE_BASENAMES and str(path.parent) not in {"", "."}:
        aliases.add(str(path.parent))
        aliases.add(str(path.parent).replace("/", "."))
        aliases.add(path.parent.name)
    module_name = module_name_from_path(file_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_dhall_source(path=Path(file_path), text=text):
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
    for import_target, line_number in parse_import_statements(text):
        target_file = resolve_import(
            file_path=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, "imports")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "source_file": file_path,
                            "target_file": target_file,
                            "target_symbol": import_target,
                            "dependency_type": "imports",
                            "line_number": line_number,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=import_target,
                    dependency_type="imports",
                )
            )
    for alias, import_target, _line_number in parse_bound_import_statements(text):
        target_file = resolve_import(
            file_path=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        import_bindings[alias] = _ImportedSymbolBinding(
            alias=alias,
            target_file=target_file,
            target_names=(),
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
    dependencies, _ = extract_import_bindings(
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
    symbol_references: list[_SymbolReferenceCandidate] = []
    stripped_text = strip_comments(text)
    seen_reference_keys: set[tuple[str, str | None, str, int]] = set()
    for match in _QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        alias = str(match.group("alias") or "").strip()
        target_name = str(match.group("name") or "").strip()
        import_binding = import_bindings.get(alias)
        if import_binding is None or not target_name:
            continue
        line_number = _line_number(stripped_text, match.start())
        source_symbol_id = _source_symbol_id_for_line(collected_symbols, line_number)
        if source_symbol_id is None:
            continue
        reference_key = (source_symbol_id, import_binding.target_file, target_name, line_number)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "source_file": file_path,
                        "source_symbol_id": source_symbol_id,
                        "target_file": import_binding.target_file,
                        "target_names": (target_name,),
                        "reference_type": "references_symbol",
                        "line_number": line_number,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=import_binding.target_file,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )
    return (
        tuple(collected_symbol.symbol for collected_symbol in collected_symbols),
        dependencies,
        tuple(symbol_references),
    )
