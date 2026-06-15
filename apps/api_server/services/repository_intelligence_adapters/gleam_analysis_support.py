from __future__ import annotations

from collections import defaultdict
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    gleam_primitives as repository_gleam_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_gleam_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_gleam_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_gleam_primitives.ResolveSuffixMatch

_CALL_RE = repository_gleam_primitives._CALL_RE
_CONST_RE = repository_gleam_primitives._CONST_RE
_FN_RE = repository_gleam_primitives._FN_RE
_IMPORT_RE = repository_gleam_primitives._IMPORT_RE
_KNOWN_SUFFIXES = repository_gleam_primitives._KNOWN_SUFFIXES
_QUALIFIED_REFERENCE_RE = repository_gleam_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_gleam_primitives._RESERVED_SYMBOL_NAMES
_TYPE_REFERENCE_RE = repository_gleam_primitives._TYPE_REFERENCE_RE
_VALUE_REFERENCE_RE = repository_gleam_primitives._VALUE_REFERENCE_RE
_CollectedSymbol = repository_gleam_primitives._CollectedSymbol

_line_count = repository_gleam_primitives._line_count
_line_number = repository_gleam_primitives._line_number
has_gleam_path_hints = repository_gleam_primitives.has_gleam_path_hints
is_probable_gleam_source = repository_gleam_primitives.is_probable_gleam_source
iter_symbol_entries = repository_gleam_primitives.iter_symbol_entries
module_name_from_path = repository_gleam_primitives.module_name_from_path
parse_import_names = repository_gleam_primitives.parse_import_names
strip_comments = repository_gleam_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[_CollectedSymbol, ...]:
    effective_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    module_name = module_name_from_path(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name,
                "symbol_kind": "module",
                "start_line": 1,
            },
        ),
        symbol_name=module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(effective_stripped_text),
        parent_symbol_id=None,
        signature=f"module {module_name}" if module_name else None,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(effective_stripped_text),
            qualified_names=(module_name, module_name.replace("/", ".")) if module_name else (),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(
        text,
        stripped_text=effective_stripped_text,
    ):
        qualified_names = repository_gleam_primitives._ordered_names(
            symbol_name,
            f"{module_name}/{symbol_name}" if module_name else "",
            f"{module_name.replace('/', '.')}.{symbol_name}" if module_name else "",
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
    final_line = _line_count(effective_stripped_text)
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
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        _without_suffix_path(path),
        _without_suffix_path(path).replace("/", "."),
        path.stem,
        module_name,
        module_name.replace("/", "."),
    }
    effective_text = text
    if effective_text is None:
        try:
            effective_text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            effective_text = ""
    effective_stripped_text = stripped_text
    if not has_gleam_path_hints(path):
        if effective_stripped_text is None:
            effective_stripped_text = strip_comments(effective_text)
        if not is_probable_gleam_source(
            path=Path(file_path),
            text=effective_text,
            stripped_text=effective_stripped_text,
        ):
            return {alias for alias in aliases if alias}
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    if effective_stripped_text is None:
        effective_stripped_text = strip_comments(effective_text)
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=effective_text,
        stable_identifier=stable_identifier,
        stripped_text=effective_stripped_text,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    candidate_keys = [
        normalized_target,
        normalized_target.replace("/", "."),
        f"{normalized_target}.gleam",
        f"src/{normalized_target}.gleam",
        f"test/{normalized_target}.gleam",
        f"tests/{normalized_target}.gleam",
    ]
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[f"{normalized_target}.gleam", f"/{normalized_target}.gleam"],
    )


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    effective_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for match in _IMPORT_RE.finditer(effective_stripped_text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        target_file = resolve_import(
            import_target,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
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
                            "line": _line_number(effective_stripped_text, match.start()),
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=PurePosixPath(import_target).name,
                    dependency_type="imports",
                )
            )
        import_names = parse_import_names(str(match.group("imports") or "").strip())
        module_alias = str(match.group("alias") or "").strip() or PurePosixPath(import_target).name
        if module_alias:
            import_bindings.setdefault(
                module_alias,
                _ImportedSymbolBinding(
                    alias=module_alias,
                    target_file=target_file,
                    target_names=(),
                ),
            )
        for import_name in import_names:
            import_bindings.setdefault(
                import_name,
                _ImportedSymbolBinding(
                    alias=import_name,
                    target_file=target_file,
                    target_names=(import_name,),
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
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    stripped_text = strip_comments(text)
    if not is_probable_gleam_source(
        path=Path(file_path),
        text=text,
        stripped_text=stripped_text,
    ):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    symbols_by_name: dict[str, list[_Symbol]] = defaultdict(list)
    for symbol in symbols:
        symbols_by_name[symbol.symbol_name].append(symbol)
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    lines = stripped_text.splitlines()

    def _record_reference_candidate(
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
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in _QUALIFIED_REFERENCE_RE.finditer(snippet):
            binding = import_bindings.get(str(match.group("alias") or "").strip())
            if binding is None:
                continue
            target_name = str(match.group("name") or "").strip()
            if not target_name:
                continue
            _record_reference_candidate(
                source_symbol_id=symbol.symbol_id,
                target_symbol_id=None,
                target_file=binding.target_file,
                target_names=(target_name,),
            )
        for regex in (_TYPE_REFERENCE_RE, _VALUE_REFERENCE_RE, _CALL_RE):
            for match in regex.finditer(snippet):
                target_name = str(match.group("name") or "").strip()
                if (
                    not target_name
                    or target_name == symbol.symbol_name
                    or target_name in _RESERVED_SYMBOL_NAMES
                ):
                    continue
                binding = import_bindings.get(target_name)
                if binding is not None and binding.target_file is not None:
                    _record_reference_candidate(
                        source_symbol_id=symbol.symbol_id,
                        target_symbol_id=None,
                        target_file=binding.target_file,
                        target_names=binding.target_names or (target_name,),
                    )
                for target_symbol in symbols_by_name.get(target_name, ()):
                    if target_symbol.symbol_id == symbol.symbol_id:
                        continue
                    _record_reference_candidate(
                        source_symbol_id=symbol.symbol_id,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=file_path,
                        target_names=(target_symbol.symbol_name,),
                    )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
