from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    wren_primitives as repository_wren_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_wren_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_wren_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_wren_primitives.ResolveSuffixMatch

WREN_SUFFIXES = repository_wren_primitives.WREN_SUFFIXES
_QUALIFIED_REFERENCE_RE = repository_wren_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_wren_primitives._RESERVED_SYMBOL_NAMES
_SymbolEntry = repository_wren_primitives._SymbolEntry
_UNQUALIFIED_REFERENCE_RE = repository_wren_primitives._UNQUALIFIED_REFERENCE_RE

has_wren_path_hints = repository_wren_primitives.has_wren_path_hints
is_probable_wren_source = repository_wren_primitives.is_probable_wren_source
iter_symbol_entries = repository_wren_primitives.iter_symbol_entries
module_name_from_path = repository_wren_primitives.module_name_from_path
parse_import_entries = repository_wren_primitives.parse_import_entries
strip_comments = repository_wren_primitives.strip_comments


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _normalize_import_target(raw_target: str) -> str:
    return str(raw_target or "").strip().strip('"').strip("'")


def _candidate_import_keys(
    *,
    file_path: str,
    import_target: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_target = _normalize_import_target(import_target)
    if not normalized_target:
        return ()
    target_path = PurePosixPath(normalized_target)
    current_directory = PurePosixPath(file_path).parent
    candidate_keys: list[str] = []
    if normalized_target.startswith(("./", "../")):
        resolved_path = current_directory.joinpath(target_path).as_posix()
        candidate_keys.extend(
            (
                resolved_path,
                f"{resolved_path}.wren",
                f"{resolved_path}/module.wren",
                f"{resolved_path}/main.wren",
            )
        )
    else:
        candidate_keys.extend(
            (
                normalized_target,
                f"{normalized_target}.wren",
                f"{normalized_target}/module.wren",
                f"{normalized_target}/main.wren",
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
    final_line = max(1, text.count("\n") + 1)
    module_name = module_name_from_path(file_path)
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
    entries = iter_symbol_entries(file_path, text)
    class_ids = {
        entry.name: stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": entry.name,
                "symbol_kind": entry.kind,
                "start_line": entry.start_line,
            },
        )
        for entry in entries
        if entry.kind == "class"
    }
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=final_line,
            qualified_names=repository_wren_primitives._ordered_names(
                module_name,
                module_name.replace("/", ".") if module_name else "",
            ),
        )
    ]
    for entry in entries:
        parent_symbol_id = (
            class_ids.get(entry.parent_name, module_symbol.symbol_id)
            if entry.parent_name is not None
            else module_symbol.symbol_id
        )
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=class_ids.get(entry.name)
                    if entry.kind == "class"
                    else stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": entry.name,
                            "symbol_kind": entry.kind,
                            "start_line": entry.start_line,
                            "parent": entry.parent_name,
                        },
                    ),
                    symbol_name=entry.name,
                    symbol_kind=entry.kind,
                    start_line=entry.start_line,
                    end_line=entry.end_line,
                    parent_symbol_id=parent_symbol_id,
                    signature=entry.name,
                ),
                local_start_line=entry.start_line,
                local_end_line=entry.end_line,
                qualified_names=entry.qualified_names,
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
    if path.suffix.lower() not in WREN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        _without_suffix_path(path),
        _without_suffix_path(path).replace("/", "."),
        path.stem,
    }
    module_name = module_name_from_path(file_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_wren_source(path=Path(file_path), text=text):
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
    dependency_keys: set[tuple[str | None, str, int]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_target, imported_symbols, line_number in parse_import_entries(text):
        target_file = resolve_import(
            file_path=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, line_number)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "kind": "import",
                            "line": line_number,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=PurePosixPath(import_target).name,
                    dependency_type="imports",
                )
            )
        if imported_symbols:
            for imported_symbol in imported_symbols:
                import_bindings.setdefault(
                    imported_symbol,
                    _ImportedSymbolBinding(
                        alias=imported_symbol,
                        target_file=target_file,
                        target_names=(imported_symbol,),
                    ),
                )
            continue
        module_alias = PurePosixPath(_normalize_import_target(import_target)).name
        if module_alias and module_alias not in _RESERVED_SYMBOL_NAMES:
            import_bindings.setdefault(
                module_alias,
                _ImportedSymbolBinding(
                    alias=module_alias,
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
    if not is_probable_wren_source(path=Path(file_path), text=text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    symbols_by_name: dict[str, list[_Symbol]] = defaultdict(list)
    qualified_local_symbols: dict[str, _Symbol] = {}
    for collected_symbol in collected_symbols:
        symbols_by_name[collected_symbol.symbol.symbol_name].append(collected_symbol.symbol)
        for qualified_name in collected_symbol.qualified_names:
            qualified_local_symbols.setdefault(qualified_name, collected_symbol.symbol)
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
        if symbol.symbol_kind in {"module", "class"}:
            continue
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in _QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias = str(match.group("alias") or "").strip()
            target_name = str(match.group("name") or "").strip()
            if not alias or not target_name or target_name in _RESERVED_SYMBOL_NAMES:
                continue
            local_target = qualified_local_symbols.get(f"{alias}.{target_name}")
            if local_target is not None and local_target.symbol_id != symbol.symbol_id:
                _record_reference_candidate(
                    source_symbol_id=symbol.symbol_id,
                    target_symbol_id=local_target.symbol_id,
                    target_file=file_path,
                    target_names=(local_target.symbol_name,),
                )
                continue
            binding = import_bindings.get(alias)
            if binding is None:
                continue
            _record_reference_candidate(
                source_symbol_id=symbol.symbol_id,
                target_symbol_id=None,
                target_file=binding.target_file,
                target_names=(target_name,),
            )
        for match in _UNQUALIFIED_REFERENCE_RE.finditer(snippet):
            target_name = str(match.group("name") or "").strip()
            if (
                not target_name
                or target_name == symbol.symbol_name
                or target_name in _RESERVED_SYMBOL_NAMES
            ):
                continue
            binding = import_bindings.get(target_name)
            if binding is not None:
                _record_reference_candidate(
                    source_symbol_id=symbol.symbol_id,
                    target_symbol_id=None,
                    target_file=binding.target_file,
                    target_names=binding.target_names or (target_name,),
                )
                continue
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
