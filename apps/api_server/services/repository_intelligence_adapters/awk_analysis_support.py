from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    awk_primitives as repository_awk_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_awk_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_awk_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_awk_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_awk_primitives._KNOWN_SUFFIXES
_CALL_RE = repository_awk_primitives._CALL_RE
_CollectedSymbol = repository_awk_primitives._CollectedSymbol

_line_number = repository_awk_primitives._line_number
_line_count = repository_awk_primitives._line_count
_iter_block_entries = repository_awk_primitives._iter_block_entries
_iter_function_entries = repository_awk_primitives._iter_function_entries
_normalize_import_target = repository_awk_primitives._normalize_import_target
is_operational_reference_name = repository_awk_primitives.is_operational_reference_name
has_awk_shebang = repository_awk_primitives.has_awk_shebang
is_probable_awk_source = repository_awk_primitives.is_probable_awk_source
import_targets_for_text = repository_awk_primitives.import_targets_for_text
module_symbol_name = repository_awk_primitives.module_symbol_name
strip_comments = repository_awk_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    if path.suffix:
        return str(path.with_suffix(""))
    return str(path)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    module_name = module_symbol_name(file_path)
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
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=None,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
        )
    ]
    for function_name, start_line, end_line in _iter_function_entries(stripped_text):
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": function_name,
                            "symbol_kind": "function",
                            "start_line": start_line,
                        },
                    ),
                    symbol_name=function_name,
                    symbol_kind="function",
                    start_line=start_line,
                    end_line=end_line,
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=f"function {function_name}()",
                ),
                local_start_line=start_line,
                local_end_line=end_line,
            )
        )
    for block_name, start_line, end_line in _iter_block_entries(stripped_text):
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": block_name,
                            "symbol_kind": "block",
                            "start_line": start_line,
                        },
                    ),
                    symbol_name=block_name,
                    symbol_kind="block",
                    start_line=start_line,
                    end_line=end_line,
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=block_name,
                ),
                local_start_line=start_line,
                local_end_line=end_line,
            )
        )
    return tuple(
        sorted(
            collected_symbols,
            key=lambda item: (
                item.local_start_line,
                item.local_end_line,
                0 if item.symbol.symbol_kind == "module" else 1,
                item.symbol.symbol_name,
            ),
        )
    )


def _source_symbol_id_for_line(
    *,
    line_number: int,
    collected_symbols: tuple[_CollectedSymbol, ...],
) -> str | None:
    matching_symbols = [
        collected_symbol
        for collected_symbol in collected_symbols
        if collected_symbol.local_start_line <= line_number <= collected_symbol.local_end_line
    ]
    if not matching_symbols:
        return None
    ranked_symbols = sorted(
        matching_symbols,
        key=lambda item: (
            0 if item.symbol.symbol_kind != "module" else 1,
            (item.local_end_line - item.local_start_line),
            item.local_start_line,
            item.symbol.symbol_id,
        ),
    )
    return ranked_symbols[0].symbol.symbol_id


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    aliases = {file_path, path.stem or path.name}
    without_suffix_path = _without_suffix_path(path)
    if without_suffix_path:
        aliases.add(without_suffix_path)
        aliases.add(without_suffix_path.replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    if path.suffix.lower() not in _KNOWN_SUFFIXES and not is_probable_awk_source(
        path=Path(file_path),
        text=text,
    ):
        return {alias for alias in aliases if alias}
    module_name = module_symbol_name(file_path)
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        if collected_symbol.symbol.symbol_kind == "module":
            continue
        aliases.add(collected_symbol.symbol.symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{collected_symbol.symbol.symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_import_target(import_target)
    if not normalized_target:
        return None
    normalized_current_dir = normalize_repository_relative_path(
        str(PurePosixPath(current_file).parent)
    )
    candidate_keys: list[str] = [normalized_target]
    if normalized_current_dir:
        candidate_keys.append(f"{normalized_current_dir}/{normalized_target}")
    suffixes = tuple(sorted(_KNOWN_SUFFIXES))
    if PurePosixPath(normalized_target).suffix.lower() not in _KNOWN_SUFFIXES:
        candidate_keys.extend(f"{normalized_target}{suffix}" for suffix in suffixes)
        if normalized_current_dir:
            candidate_keys.extend(
                f"{normalized_current_dir}/{normalized_target}{suffix}"
                for suffix in suffixes
            )
    seen_candidate_keys: set[str] = set()
    ordered_candidate_keys: list[str] = []
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate or normalized_candidate in seen_candidate_keys:
            continue
        seen_candidate_keys.add(normalized_candidate)
        ordered_candidate_keys.append(normalized_candidate)
    for candidate_key in ordered_candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    lookup_suffixes = [*ordered_candidate_keys, PurePosixPath(normalized_target).name]
    if PurePosixPath(normalized_target).suffix.lower() not in _KNOWN_SUFFIXES:
        lookup_suffixes.extend(
            f"{PurePosixPath(normalized_target).name}{suffix}" for suffix in suffixes
        )
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=lookup_suffixes,
    )


def _register_import_dependency(
    *,
    file_path: str,
    import_target: str,
    target_file: str | None,
    stable_identifier: StableIdentifier,
    dependency_keys: set[tuple[str | None, str | None, str]],
    dependencies: list[_Dependency],
) -> None:
    dependency_key = (target_file, None, "imports")
    if dependency_key in dependency_keys:
        return
    dependency_keys.add(dependency_key)
    dependencies.append(
        _Dependency(
            dependency_edge_id=stable_identifier(
                "dep",
                {
                    "file_path": file_path,
                    "target": import_target,
                    "kind": "imports",
                },
            ),
            source_file=file_path,
            target_file=target_file,
            target_symbol=None,
            dependency_type="imports",
        )
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    stripped_text = strip_comments(text)
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str | None, str]] = set()
    for import_target in import_targets_for_text(stripped_text):
        _register_import_dependency(
            file_path=file_path,
            import_target=import_target,
            target_file=resolve_import(
                current_file=file_path,
                import_target=import_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            ),
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )
    return tuple(dependencies)


def _direct_reference_target_file(
    *,
    reference_name: str,
    file_path: str,
    module_index: dict[str, str],
) -> str | None:
    direct_match = module_index.get(reference_name)
    if direct_match is None or direct_match == file_path:
        return None
    return direct_match


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
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    imported_target_files = tuple(
        sorted(
            {
                dependency.target_file
                for dependency in dependencies
                if dependency.target_file and dependency.target_file != file_path
            }
        )
    )
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    local_function_names = {
        collected_symbol.symbol.symbol_name
        for collected_symbol in collected_symbols
        if collected_symbol.symbol.symbol_kind == "function"
    }
    declaration_line_names = {
        (collected_symbol.local_start_line, collected_symbol.symbol.symbol_name)
        for collected_symbol in collected_symbols
        if collected_symbol.symbol.symbol_kind == "function"
    }
    seen_reference_keys: set[tuple[str, str | None, tuple[str, ...]]] = set()
    symbol_references: list[_SymbolReferenceCandidate] = []
    for match in _CALL_RE.finditer(stripped_text):
        reference_name = str(match.group("name") or "").strip()
        if not is_operational_reference_name(reference_name):
            continue
        line_number = _line_number(stripped_text, match.start())
        if (line_number, reference_name) in declaration_line_names:
            continue
        source_symbol_id = _source_symbol_id_for_line(
            line_number=line_number,
            collected_symbols=collected_symbols,
        )
        if source_symbol_id is None:
            continue
        target_files: set[str | None] = set()
        if reference_name in local_function_names:
            target_files.add(file_path)
        direct_target_file = _direct_reference_target_file(
            reference_name=reference_name,
            file_path=file_path,
            module_index=module_index,
        )
        if direct_target_file is not None:
            target_files.add(direct_target_file)
        target_files.update(imported_target_files)
        if not target_files:
            continue
        for target_file in sorted(
            target_files,
            key=lambda value: "" if value is None else value,
        ):
            if target_file == file_path and reference_name not in local_function_names:
                continue
            reference_key = (source_symbol_id, target_file, (reference_name,))
            if reference_key in seen_reference_keys:
                continue
            seen_reference_keys.add(reference_key)
            symbol_references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "source_symbol_id": source_symbol_id,
                            "target_file": target_file,
                            "target_name": reference_name,
                            "line": line_number,
                        },
                    ),
                    source_symbol_id=source_symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=(reference_name,),
                    reference_type="references_symbol",
                )
            )
    return symbols, dependencies, tuple(symbol_references)
