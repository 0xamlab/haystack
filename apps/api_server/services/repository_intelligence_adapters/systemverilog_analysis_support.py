from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    systemverilog_primitives as repository_systemverilog_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_systemverilog_primitives.StableIdentifier
NormalizeRepositoryRelativePath = (
    repository_systemverilog_primitives.NormalizeRepositoryRelativePath
)
ResolveSuffixMatch = repository_systemverilog_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_systemverilog_primitives._KNOWN_SUFFIXES
_INCLUDE_RE = repository_systemverilog_primitives._INCLUDE_RE
_IMPORT_RE = repository_systemverilog_primitives._IMPORT_RE
_IMPORT_ITEM_RE = repository_systemverilog_primitives._IMPORT_ITEM_RE
_QUALIFIED_REFERENCE_RE = repository_systemverilog_primitives._QUALIFIED_REFERENCE_RE
_INSTANTIATION_RE = repository_systemverilog_primitives._INSTANTIATION_RE
_RESERVED_REFERENCE_NAMES = (
    repository_systemverilog_primitives._RESERVED_REFERENCE_NAMES
)

_collect_primary_symbols = repository_systemverilog_primitives._collect_primary_symbols
_collect_routine_symbols = repository_systemverilog_primitives._collect_routine_symbols
_line_number = repository_systemverilog_primitives._line_number
_normalized_path_aliases = (
    repository_systemverilog_primitives._normalized_path_aliases
)
_ordered_symbols = repository_systemverilog_primitives._ordered_symbols
has_systemverilog_path_hints = (
    repository_systemverilog_primitives.has_systemverilog_path_hints
)
is_probable_systemverilog_source = (
    repository_systemverilog_primitives.is_probable_systemverilog_source
)
strip_comments = repository_systemverilog_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return set()
    stripped_text = strip_comments(text)
    if not is_probable_systemverilog_source(path=path, text=text, stripped_text=stripped_text):
        return set()
    aliases = _normalized_path_aliases(path)
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    primary_symbols = _collect_primary_symbols(
        file_path=file_path,
        text=stripped_text,
        stable_identifier=stable_identifier,
    )
    for symbol in primary_symbols:
        aliases.add(symbol.symbol_name)
        aliases.add(f"{symbol.symbol_kind}:{symbol.symbol_name}")
    return {alias for alias in aliases if alias}


def _resolve_symbol_target(
    *,
    symbol_name: str,
    symbol_kind: str | None,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_name = str(symbol_name or "").strip()
    if not normalized_name:
        return None
    candidate_aliases = []
    if symbol_kind:
        candidate_aliases.append(f"{symbol_kind}:{normalized_name}")
    candidate_aliases.append(normalized_name)
    for candidate_alias in candidate_aliases:
        resolved = module_index.get(candidate_alias)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{normalized_name}.sv",
            f"{normalized_name}.svh",
            f"{normalized_name}.v",
            f"{normalized_name}.vh",
        ],
    )


def _resolve_include_target(
    *,
    current_file: str,
    include_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(include_target or "").strip().replace("\\", "/")
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    candidate_suffixes = [
        normalize_repository_relative_path(str(current_dir / normalized_target)),
        normalize_repository_relative_path(normalized_target),
    ]
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=candidate_suffixes,
    )


def _iter_import_targets(text: str) -> tuple[tuple[str, str], ...]:
    import_targets: list[tuple[str, str]] = []
    for match in _IMPORT_RE.finditer(text):
        for item_match in _IMPORT_ITEM_RE.finditer(str(match.group("body") or "")):
            package_name = str(item_match.group("package") or "").strip()
            symbol_name = str(item_match.group("name") or "").strip()
            if not package_name:
                continue
            import_targets.append((package_name, symbol_name))
    return tuple(import_targets)


def _dependency_key(
    *,
    target_file: str | None,
    target_symbol: str | None,
    dependency_type: str,
) -> tuple[str | None, str | None, str]:
    return (target_file, target_symbol, dependency_type)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[_Dependency, ...]:
    path = PurePosixPath(file_path)
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    if not is_probable_systemverilog_source(path=path, text=text, stripped_text=stripped_text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str | None, str]] = set()
    for match in _INCLUDE_RE.finditer(stripped_text):
        include_target = str(match.group("target") or "").strip()
        target_file = _resolve_include_target(
            current_file=file_path,
            include_target=include_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = _dependency_key(
            target_file=target_file,
            target_symbol=include_target,
            dependency_type="imports",
        )
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": include_target,
                        "kind": "imports",
                        "line": _line_number(stripped_text, match.start()),
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=include_target,
                dependency_type="imports",
            )
        )
    for match in _IMPORT_RE.finditer(stripped_text):
        for package_name, symbol_name in _iter_import_targets(str(match.group(0) or "")):
            target_file = _resolve_symbol_target(
                symbol_name=package_name,
                symbol_kind="package",
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            target_symbol = (
                f"{package_name}::{symbol_name}"
                if symbol_name and symbol_name != "*"
                else package_name
            )
            dependency_key = _dependency_key(
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="imports",
            )
            if dependency_key in seen_dependencies:
                continue
            seen_dependencies.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": target_symbol,
                            "kind": "imports",
                            "line": _line_number(stripped_text, match.start()),
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=target_symbol,
                    dependency_type="imports",
                )
            )
    for match in _INSTANTIATION_RE.finditer(stripped_text):
        target_name = str(match.group("name") or "").strip()
        if not target_name or target_name.lower() in _RESERVED_REFERENCE_NAMES:
            continue
        target_file = _resolve_symbol_target(
            symbol_name=target_name,
            symbol_kind=None,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = _dependency_key(
            target_file=target_file,
            target_symbol=target_name,
            dependency_type="references",
        )
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target_name,
                        "kind": "references",
                        "line": _line_number(stripped_text, match.start()),
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="references",
            )
        )
    return tuple(dependencies)


def _reference_candidates_for_symbol(
    *,
    file_path: str,
    symbol: _Symbol,
    snippet: str,
    snippet_line_offset: int,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> list[_SymbolReferenceCandidate]:
    reference_candidates: list[_SymbolReferenceCandidate] = []
    seen_keys: set[tuple[str | None, tuple[str, ...], str]] = set()
    for match in _QUALIFIED_REFERENCE_RE.finditer(snippet):
        package_name = str(match.group("package") or "").strip()
        target_name = str(match.group("name") or "").strip()
        if not package_name or not target_name:
            continue
        target_file = _resolve_symbol_target(
            symbol_name=package_name,
            symbol_kind="package",
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_names = (target_name,)
        key = (target_file, target_names, symbol.symbol_id)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        reference_candidates.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "symbol_id": symbol.symbol_id,
                        "target": f"{package_name}::{target_name}",
                        "line": snippet_line_offset + _line_number(snippet, match.start()) - 1,
                        "type": "references_symbol",
                    },
                ),
                source_symbol_id=symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )
    for match in _INSTANTIATION_RE.finditer(snippet):
        target_name = str(match.group("name") or "").strip()
        if not target_name or target_name.lower() in _RESERVED_REFERENCE_NAMES:
            continue
        target_file = _resolve_symbol_target(
            symbol_name=target_name,
            symbol_kind=None,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_names = (target_name,)
        key = (target_file, target_names, symbol.symbol_id)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        reference_candidates.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "symbol_id": symbol.symbol_id,
                        "target": target_name,
                        "line": snippet_line_offset + _line_number(snippet, match.start()) - 1,
                        "type": "references_symbol",
                    },
                ),
                source_symbol_id=symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )
    return reference_candidates


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
    path = PurePosixPath(file_path)
    if not is_probable_systemverilog_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    primary_symbols = _collect_primary_symbols(
        file_path=file_path,
        text=stripped_text,
        stable_identifier=stable_identifier,
    )
    routine_symbols = _collect_routine_symbols(
        file_path=file_path,
        text=stripped_text,
        stable_identifier=stable_identifier,
        primary_symbols=primary_symbols,
    )
    symbols = _ordered_symbols(primary_symbols, routine_symbols)
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    lines = stripped_text.splitlines()
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in primary_symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for reference_candidate in _reference_candidates_for_symbol(
            file_path=file_path,
            symbol=symbol,
            snippet=snippet,
            snippet_line_offset=symbol.start_line,
            module_index=module_index,
            stable_identifier=stable_identifier,
            resolve_suffix_match=resolve_suffix_match,
        ):
            reference_candidates.setdefault(
                reference_candidate.reference_edge_id,
                reference_candidate,
            )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
