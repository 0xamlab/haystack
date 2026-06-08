from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    nextflow_primitives as repository_nextflow_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_nextflow_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_nextflow_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_nextflow_primitives.ResolveSuffixMatch

NEXTFLOW_SOURCE_SUFFIXES = repository_nextflow_primitives.NEXTFLOW_SOURCE_SUFFIXES
NEXTFLOW_CONFIG_BASENAMES = repository_nextflow_primitives.NEXTFLOW_CONFIG_BASENAMES
_MODULE_SYMBOL_RE = repository_nextflow_primitives._MODULE_SYMBOL_RE
_RESERVED_SYMBOL_NAMES = repository_nextflow_primitives._RESERVED_SYMBOL_NAMES
_SymbolEntry = repository_nextflow_primitives._SymbolEntry

collect_symbol_entries = repository_nextflow_primitives.collect_symbol_entries
has_nextflow_path_hints = repository_nextflow_primitives.has_nextflow_path_hints
is_probable_nextflow_source = repository_nextflow_primitives.is_probable_nextflow_source
module_name_from_path = repository_nextflow_primitives.module_name_from_path
parse_config_include_entries = repository_nextflow_primitives.parse_config_include_entries
parse_include_entries = repository_nextflow_primitives.parse_include_entries
strip_comments = repository_nextflow_primitives.strip_comments


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _normalize_include_target(raw_target: str) -> str:
    return str(raw_target or "").strip().strip('"').strip("'")


def _candidate_include_keys(
    *,
    file_path: str,
    include_target: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_target = _normalize_include_target(include_target)
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
                f"{resolved_path}.nf",
                f"{resolved_path}/main.nf",
                f"{resolved_path}/workflow.nf",
            )
        )
    else:
        candidate_keys.extend(
            (
                normalized_target,
                f"{normalized_target}.nf",
                f"{normalized_target}/main.nf",
                f"{normalized_target}/workflow.nf",
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


def _candidate_config_keys(
    *,
    file_path: str,
    include_target: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_target = _normalize_include_target(include_target)
    if not normalized_target:
        return ()
    target_path = PurePosixPath(normalized_target)
    current_directory = PurePosixPath(file_path).parent
    candidate_keys: list[str] = []
    if normalized_target.startswith(("./", "../")):
        resolved_path = current_directory.joinpath(target_path).as_posix()
        candidate_keys.extend((resolved_path, f"{resolved_path}.config"))
    else:
        candidate_keys.extend((normalized_target, f"{normalized_target}.config"))
    normalized_candidates: list[str] = []
    seen: set[str] = set()
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if normalized_candidate and normalized_candidate not in seen:
            seen.add(normalized_candidate)
            normalized_candidates.append(normalized_candidate)
    return tuple(normalized_candidates)


def resolve_include(
    *,
    file_path: str,
    include_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    candidate_keys = _candidate_include_keys(
        file_path=file_path,
        include_target=include_target,
        normalize_repository_relative_path=normalize_repository_relative_path,
    )
    if not candidate_keys:
        return None
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_keys)


def resolve_config_include(
    *,
    file_path: str,
    include_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    candidate_keys = _candidate_config_keys(
        file_path=file_path,
        include_target=include_target,
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
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=final_line,
            qualified_names=repository_nextflow_primitives._ordered_names(
                module_name,
                module_name.replace("/", ".") if module_name else "",
            ),
        )
    ]
    symbol_entries = collect_symbol_entries(file_path, text)
    for index, entry in enumerate(symbol_entries):
        end_line = (
            max(symbol_entries[index + 1].start_line - 1, entry.start_line)
            if index + 1 < len(symbol_entries)
            else final_line
        )
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": entry.name,
                            "symbol_kind": entry.kind,
                            "start_line": entry.start_line,
                        },
                    ),
                    symbol_name=entry.name,
                    symbol_kind=entry.kind,
                    start_line=entry.start_line,
                    end_line=end_line,
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=entry.name,
                ),
                local_start_line=entry.start_line,
                local_end_line=end_line,
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
    if not has_nextflow_path_hints(path):
        return set()
    aliases = {
        file_path,
        path.stem,
    }
    if path.name.lower() not in NEXTFLOW_CONFIG_BASENAMES:
        aliases.add(_without_suffix_path(path))
        aliases.add(_without_suffix_path(path).replace("/", "."))
    module_name = module_name_from_path(file_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_nextflow_source(path=Path(file_path), text=text):
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
    dependency_keys: set[tuple[str | None, str, str, int]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for include_target, imported_symbols, line_number in parse_include_entries(text):
        target_file = resolve_include(
            file_path=file_path,
            include_target=include_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, include_target, "include", line_number)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": include_target,
                            "kind": "include",
                            "line": line_number,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=PurePosixPath(include_target).name,
                    dependency_type="imports",
                )
            )
        for imported_name, alias in imported_symbols:
            bound_name = alias or imported_name
            import_bindings.setdefault(
                bound_name,
                _ImportedSymbolBinding(
                    alias=bound_name,
                    target_file=target_file,
                    target_names=(imported_name,),
                ),
            )
    for include_target, line_number in parse_config_include_entries(text):
        target_file = resolve_config_include(
            file_path=file_path,
            include_target=include_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, include_target, "include_config", line_number)
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": include_target,
                        "kind": "include_config",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=PurePosixPath(include_target).name,
                dependency_type="includes",
            )
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
    if not is_probable_nextflow_source(path=Path(file_path), text=text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    default_source_symbol_id = symbols[0].symbol_id if symbols else ""
    symbols_by_line = tuple(collected_symbols[1:] or collected_symbols)
    local_symbols: dict[str, list[_Symbol]] = defaultdict(list)
    for collected_symbol in collected_symbols:
        local_symbols[collected_symbol.symbol.symbol_name].append(collected_symbol.symbol)
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    stripped_text = strip_comments(text)
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str | None, tuple[str, ...]]] = set()
    declaration_prefixes = ("process ", "workflow", "def ", "include ", "includeConfig ")
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith(declaration_prefixes):
            continue
        source_symbol_id = default_source_symbol_id
        for collected_symbol in symbols_by_line:
            if collected_symbol.local_start_line <= line_number <= collected_symbol.local_end_line:
                source_symbol_id = collected_symbol.symbol.symbol_id
        for match in _MODULE_SYMBOL_RE.finditer(stripped_line):
            name = str(match.group("name") or "").strip()
            if not name or name in _RESERVED_SYMBOL_NAMES:
                continue
            target_file: str | None = None
            target_names: tuple[str, ...] = (name,)
            target_symbol_id: str | None = None
            binding = import_bindings.get(name)
            if binding is not None:
                target_file = binding.target_file
                target_names = binding.target_names or (name,)
            elif name in local_symbols:
                target_file = file_path
                target_symbol_id = local_symbols[name][0].symbol_id
            else:
                continue
            reference_key = (source_symbol_id, target_file, target_names)
            if reference_key in seen_reference_keys:
                continue
            seen_reference_keys.add(reference_key)
            references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "file_path": file_path,
                            "line": line_number,
                            "source_symbol_id": source_symbol_id,
                            "name": name,
                            "target_file": target_file,
                            "targets": target_names,
                        },
                    ),
                    source_file=file_path,
                    source_symbol_id=source_symbol_id,
                    target_symbol_id=target_symbol_id,
                    target_file=target_file,
                    target_names=target_names,
                    reference_type="references_symbol",
                )
            )
    return symbols, dependencies, tuple(references)
