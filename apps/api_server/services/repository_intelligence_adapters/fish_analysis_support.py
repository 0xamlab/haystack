from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    fish_primitives as repository_fish_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_fish_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_fish_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_fish_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_fish_primitives._KNOWN_SUFFIXES
_line_count = repository_fish_primitives._line_count
_line_number = repository_fish_primitives._line_number
_ordered_names = repository_fish_primitives._ordered_names
has_fish_path_hints = repository_fish_primitives.has_fish_path_hints
is_operational_reference_name = repository_fish_primitives.is_operational_reference_name
is_probable_fish_source = repository_fish_primitives.is_probable_fish_source
iter_reference_names = repository_fish_primitives.iter_reference_names
iter_source_statements = repository_fish_primitives.iter_source_statements
iter_symbol_entries = repository_fish_primitives.iter_symbol_entries
module_name_from_path = repository_fish_primitives.module_name_from_path
strip_comments = repository_fish_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        path.stem,
        module_name,
        module_name.replace("/", "."),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_fish_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
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
    if (
        not normalized_target
        or normalized_target.startswith("/")
        or normalized_target.startswith("~")
        or "$" in normalized_target
        or "*" in normalized_target
        or "?" in normalized_target
    ):
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys: list[str] = []
    if current_dir:
        relative_base = normalize_repository_relative_path(
            str(PurePosixPath(current_dir) / normalized_target)
        )
        if relative_base:
            candidate_keys.extend([relative_base, f"{relative_base}.fish"])
    candidate_keys.extend(
        [
            normalized_target,
            f"{normalized_target}.fish",
            f"functions/{normalized_target}.fish",
            f"conf.d/{normalized_target}.fish",
            f"completions/{normalized_target}.fish",
        ]
    )
    seen_candidates: set[str] = set()
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate or normalized_candidate in seen_candidates:
            continue
        seen_candidates.add(normalized_candidate)
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    target_name = PurePosixPath(normalized_target).name
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{target_name}.fish",
            f"/{target_name}.fish",
            f"functions/{target_name}.fish",
            f"conf.d/{target_name}.fish",
            f"completions/{target_name}.fish",
        ],
    )


def _resolve_autoload_target(
    *,
    current_file: str,
    reference_name: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    return resolve_import(
        current_file=current_file,
        import_target=reference_name,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )


def _collect_source_dependencies(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], tuple[str, ...]]:
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str]] = set()
    sourced_target_files: list[str] = []
    seen_target_files: set[str] = set()
    for import_target, line_number in iter_source_statements(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, "imports")
        if dependency_key not in seen_dependencies:
            seen_dependencies.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "line": line_number,
                            "kind": "imports",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=PurePosixPath(import_target).stem or None,
                    dependency_type="imports",
                )
            )
        if target_file is not None and target_file not in seen_target_files:
            seen_target_files.add(target_file)
            sourced_target_files.append(target_file)
    return tuple(dependencies), tuple(sourced_target_files)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    path = PurePosixPath(file_path)
    if not is_probable_fish_source(path=path, text=text):
        return ()
    dependencies, sourced_target_files = _collect_source_dependencies(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependency_candidates = list(dependencies)
    seen_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_candidates
    }
    for target_name, line_number in iter_reference_names(text):
        if not is_operational_reference_name(target_name):
            continue
        target_files = set(sourced_target_files)
        autoload_target = _resolve_autoload_target(
            current_file=file_path,
            reference_name=target_name,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if autoload_target is not None:
            target_files.add(autoload_target)
        for target_file in sorted(
            candidate for candidate in target_files if candidate and candidate != file_path
        ):
            dependency_key = (target_file, target_name, "references")
            if dependency_key in seen_keys:
                continue
            seen_keys.add(dependency_key)
            dependency_candidates.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target_file": target_file,
                            "symbol": target_name,
                            "line": line_number,
                            "kind": "references",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=target_name,
                    dependency_type="references",
                )
            )
    return tuple(dependency_candidates)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    path = PurePosixPath(file_path)
    if not is_probable_fish_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path) or path.stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name,
                "symbol_kind": "module",
                "start": 1,
            },
        ),
        symbol_name=module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"module {module_name}",
    )
    collected_symbols: list[tuple[_Symbol, int]] = [(module_symbol, 1)]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
        collected_symbols.append(
            (
                _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": symbol_name,
                            "symbol_kind": symbol_kind,
                            "start": start_line,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=start_line,
                    end_line=start_line,
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=symbol_name,
                ),
                start_line,
            )
        )
    finalized_symbols: list[_Symbol] = []
    final_line = _line_count(stripped_text)
    for index, (symbol, start_line) in enumerate(collected_symbols):
        next_start = collected_symbols[index + 1][1] if index + 1 < len(collected_symbols) else None
        end_line = final_line if next_start is None else max(start_line, next_start - 1)
        finalized_symbols.append(
            _Symbol(
                symbol_id=symbol.symbol_id,
                symbol_name=symbol.symbol_name,
                symbol_kind=symbol.symbol_kind,
                start_line=symbol.start_line,
                end_line=end_line,
                parent_symbol_id=symbol.parent_symbol_id,
                signature=symbol.signature,
            )
        )
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    local_symbol_ids = {
        symbol.symbol_name: symbol.symbol_id
        for symbol in finalized_symbols
        if symbol.symbol_name
    }
    source_targets = {
        dependency.target_file
        for dependency in dependencies
        if dependency.dependency_type == "imports" and dependency.target_file
    }
    lines = stripped_text.splitlines()
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in finalized_symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for target_name, line_number in iter_reference_names(snippet):
            if (
                target_name in local_symbol_ids
                and local_symbol_ids[target_name] != symbol.symbol_id
            ):
                edge_id = stable_identifier(
                    "symref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": symbol.symbol_id,
                        "target_symbol_id": local_symbol_ids[target_name],
                        "line": line_number,
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_file=file_path,
                        source_symbol_id=symbol.symbol_id,
                        target_symbol_id=local_symbol_ids[target_name],
                        target_file=file_path,
                        target_names=(target_name,),
                        reference_type="references_symbol",
                    ),
                )
                continue
            target_files = set(source_targets)
            autoload_target = _resolve_autoload_target(
                current_file=file_path,
                reference_name=target_name,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if autoload_target is not None:
                target_files.add(autoload_target)
            for target_file in sorted(
                candidate for candidate in target_files if candidate and candidate != file_path
            ):
                edge_id = stable_identifier(
                    "symref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": symbol.symbol_id,
                        "target_file": target_file,
                        "target_names": (target_name,),
                        "line": line_number,
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_file=file_path,
                        source_symbol_id=symbol.symbol_id,
                        target_symbol_id=None,
                        target_file=target_file,
                        target_names=(target_name,),
                        reference_type="references_symbol",
                    ),
                )
    return (
        tuple(finalized_symbols),
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
