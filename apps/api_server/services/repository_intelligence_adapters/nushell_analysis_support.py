from __future__ import annotations

from collections import defaultdict
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    nushell_primitives as repository_nushell_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_nushell_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_nushell_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_nushell_primitives.ResolveSuffixMatch

_BUILTIN_MODULE_NAMES = repository_nushell_primitives._BUILTIN_MODULE_NAMES
_COMMAND_REFERENCE_RE = repository_nushell_primitives._COMMAND_REFERENCE_RE
_DEF_RE = repository_nushell_primitives._DEF_RE
_KNOWN_SUFFIXES = repository_nushell_primitives._KNOWN_SUFFIXES
_MODULE_RE = repository_nushell_primitives._MODULE_RE
_RESERVED_SYMBOL_NAMES = repository_nushell_primitives._RESERVED_SYMBOL_NAMES
_SOURCE_RE = repository_nushell_primitives._SOURCE_RE
_USE_RE = repository_nushell_primitives._USE_RE
_CollectedSymbol = repository_nushell_primitives._CollectedSymbol

_line_count = repository_nushell_primitives._line_count
_line_number = repository_nushell_primitives._line_number
has_nushell_path_hints = repository_nushell_primitives.has_nushell_path_hints
is_probable_nushell_source = repository_nushell_primitives.is_probable_nushell_source
iter_symbol_entries = repository_nushell_primitives.iter_symbol_entries
module_name_from_path = repository_nushell_primitives.module_name_from_path
parse_use_targets = repository_nushell_primitives.parse_use_targets
strip_comments = repository_nushell_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name or PurePosixPath(file_path).stem,
                "symbol_kind": "module",
                "start_line": 1,
            },
        ),
        symbol_name=module_name or PurePosixPath(file_path).stem,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"module {module_name}" if module_name else None,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
            qualified_names=(module_name, module_name.replace("/", " ")) if module_name else (),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
        qualified_names = repository_nushell_primitives._ordered_names(
            symbol_name,
            f"{module_name}/{symbol_name}" if module_name else "",
            f"{module_name} {symbol_name}" if module_name else "",
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
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        _without_suffix_path(path),
        path.stem,
        module_name,
        module_name.replace("/", " "),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_nushell_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip().strip("\"'")
    if not normalized_target or normalized_target in _BUILTIN_MODULE_NAMES:
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    target_path = PurePosixPath(normalized_target)
    candidate_keys: list[str] = []
    if current_dir:
        relative_base = normalize_repository_relative_path(
            str(PurePosixPath(current_dir) / normalized_target)
        )
        if relative_base:
            candidate_keys.extend(
                [relative_base, f"{relative_base}.nu", f"{relative_base}/mod.nu"]
            )
    candidate_keys.extend(
        [
            normalized_target,
            f"{normalized_target}.nu",
            f"{normalized_target}/mod.nu",
            f"src/{normalized_target}.nu",
            f"src/{normalized_target}/mod.nu",
            f"scripts/{normalized_target}.nu",
            f"modules/{normalized_target}.nu",
            f"modules/{normalized_target}/mod.nu",
        ]
    )
    seen_keys: set[str] = set()
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate or normalized_candidate in seen_keys:
            continue
        seen_keys.add(normalized_candidate)
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{target_path.name}.nu",
            f"{target_path.name}/mod.nu",
            f"/{target_path.name}.nu",
            f"/{target_path.name}/mod.nu",
        ],
    )


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    stripped_text = strip_comments(text)
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for regex in (_SOURCE_RE, _USE_RE):
        for match in regex.finditer(stripped_text):
            import_target = str(match.group("target") or "").strip()
            if not import_target:
                continue
            target_file = resolve_import(
                current_file=file_path,
                import_target=import_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if import_target in _BUILTIN_MODULE_NAMES and target_file is None:
                continue
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
                                "line": _line_number(stripped_text, match.start()),
                            },
                        ),
                        source_file=file_path,
                        target_file=target_file,
                        target_symbol=PurePosixPath(import_target).stem,
                        dependency_type="imports",
                    )
                )
            target_stem = PurePosixPath(import_target).stem
            if regex is _USE_RE and target_stem:
                import_bindings.setdefault(
                    target_stem,
                    _ImportedSymbolBinding(
                        alias=target_stem,
                        target_file=target_file,
                        target_names=(),
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
    if not is_probable_nushell_source(path=Path(file_path), text=text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
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
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    stripped_text = strip_comments(text)
    lines = stripped_text.splitlines()
    source_target_files = tuple(
        dict.fromkeys(
            resolved_target
            for match in _SOURCE_RE.finditer(stripped_text)
            for resolved_target in (
                resolve_import(
                    current_file=file_path,
                    import_target=str(match.group("target") or "").strip(),
                    module_index=module_index,
                    normalize_repository_relative_path=normalize_repository_relative_path,
                    resolve_suffix_match=resolve_suffix_match,
                ),
            )
            if resolved_target is not None and resolved_target != file_path
        )
    )

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
        for match in _COMMAND_REFERENCE_RE.finditer(snippet):
            reference_name = str(match.group("name") or "").strip()
            if (
                not reference_name
                or reference_name == symbol.symbol_name
                or reference_name in _RESERVED_SYMBOL_NAMES
                or reference_name in _BUILTIN_MODULE_NAMES
            ):
                continue
            binding = import_bindings.get(reference_name)
            if binding is not None and binding.target_file is not None:
                _record_reference_candidate(
                    source_symbol_id=symbol.symbol_id,
                    target_symbol_id=None,
                    target_file=binding.target_file,
                    target_names=binding.target_names or (reference_name,),
                )
            elif source_target_files:
                for target_file in source_target_files:
                    _record_reference_candidate(
                        source_symbol_id=symbol.symbol_id,
                        target_symbol_id=None,
                        target_file=target_file,
                        target_names=(reference_name,),
                    )
            for target_symbol in symbols_by_name.get(reference_name, ()):
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
