from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    qmake_primitives as repository_qmake_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_qmake_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_qmake_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_qmake_primitives.ResolveSuffixMatch

QMAKE_CONFIG_BASENAMES = repository_qmake_primitives.QMAKE_CONFIG_BASENAMES
QMAKE_SUFFIXES = repository_qmake_primitives.QMAKE_SUFFIXES
_line_count = repository_qmake_primitives._line_count
has_qmake_path_hints = repository_qmake_primitives.has_qmake_path_hints
is_probable_qmake_source = repository_qmake_primitives.is_probable_qmake_source
iter_include_targets = repository_qmake_primitives.iter_include_targets
iter_load_targets = repository_qmake_primitives.iter_load_targets
iter_reference_names = repository_qmake_primitives.iter_reference_names
iter_subdir_entries = repository_qmake_primitives.iter_subdir_entries
iter_symbol_entries = repository_qmake_primitives.iter_symbol_entries
strip_comments = repository_qmake_primitives.strip_comments


def _prepared_analysis_context(
    text: str,
) -> tuple[
    str,
    tuple[tuple[str, str, str, int], ...],
    tuple[tuple[str, str | None, tuple[str, ...], int], ...],
    tuple[tuple[str, str, int], ...],
]:
    normalized_text = repository_qmake_primitives.normalize_continuations(text)
    assignment_entries = repository_qmake_primitives.iter_assignment_entries(
        text,
        normalized_text=normalized_text,
    )
    subdir_entries = repository_qmake_primitives.iter_subdir_entries(
        text,
        assignment_entries=assignment_entries,
    )
    symbol_entries = repository_qmake_primitives.iter_symbol_entries(
        text,
        assignment_entries=assignment_entries,
        subdir_entries=subdir_entries,
    )
    return normalized_text, assignment_entries, subdir_entries, symbol_entries


def _build_dependencies_with_context(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    normalized_text: str,
    subdir_entries: tuple[tuple[str, str | None, tuple[str, ...], int], ...],
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str | None, str]] = set()
    for import_target, line_number in iter_include_targets(
        text,
        normalized_text=normalized_text,
    ):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_name = PurePosixPath(import_target).stem or PurePosixPath(import_target).name or None
        dependency_key = (target_file, target_name, "imports")
        if dependency_key in seen_dependencies:
            continue
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
                target_symbol=target_name,
                dependency_type="imports",
            )
        )
    for load_target, line_number in iter_load_targets(
        text,
        normalized_text=normalized_text,
    ):
        dependency_key = (None, load_target, "imports")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": load_target,
                        "line": line_number,
                        "kind": "imports",
                    },
                ),
                source_file=file_path,
                target_file=None,
                target_symbol=load_target,
                dependency_type="imports",
            )
        )
    for label, explicit_path, _depends, line_number in subdir_entries:
        import_target = explicit_path or label
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
            treat_as_directory=PurePosixPath(import_target).suffix.lower() not in QMAKE_SUFFIXES,
        )
        dependency_key = (target_file, label, "imports")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "symbol": label,
                        "line": line_number,
                        "kind": "imports",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=label,
                dependency_type="imports",
            )
        )
    return tuple(dependencies)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if not has_qmake_path_hints(path):
        return set()
    aliases = {
        file_path,
        path.name,
        str(path.with_suffix("")) if path.suffix else file_path,
        path.stem,
    }
    if path.parent not in {PurePosixPath("."), PurePosixPath("")}:
        aliases.add(path.parent.as_posix())
        aliases.add(path.parent.as_posix().replace("/", "."))
        aliases.add(str(path.with_suffix("")).replace("/", "."))
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    normalized_text = (
        repository_qmake_primitives.normalize_continuations(text) if text else ""
    )
    if text and not is_probable_qmake_source(path=path, text=text, normalized_text=normalized_text):
        return {alias for alias in aliases if alias}
    assignment_entries = repository_qmake_primitives.iter_assignment_entries(
        text,
        normalized_text=normalized_text,
    )
    subdir_entries = repository_qmake_primitives.iter_subdir_entries(
        text,
        assignment_entries=assignment_entries,
    )
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(
        text,
        assignment_entries=assignment_entries,
        subdir_entries=subdir_entries,
    ):
        aliases.add(symbol_name)
        if path.parent not in {PurePosixPath("."), PurePosixPath("")}:
            aliases.add(f"{path.parent.as_posix().replace('/', '.')}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    treat_as_directory: bool = False,
) -> str | None:
    normalized_target = str(import_target or "").strip().strip('"').strip("'").replace("\\", "/")
    if (
        not normalized_target
        or normalized_target.startswith("/")
        or normalized_target.startswith("~")
        or "$" in normalized_target
    ):
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    normalized_path = PurePosixPath(normalized_target)
    if treat_as_directory or normalized_path.suffix.lower() not in QMAKE_SUFFIXES:
        target_name = normalized_path.name
        candidate_keys.extend(
            (
                f"{normalized_target}.pro",
                f"{normalized_target}.pri",
                f"{normalized_target}.prf",
                f"{normalized_target}/{target_name}.pro",
                f"{normalized_target}/{target_name}.pri",
                f"{normalized_target}/{target_name}.prf",
            )
        )
    if current_dir:
        candidate_keys.extend(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / candidate_key))
            for candidate_key in tuple(candidate_keys)
        )
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    suffixes = [
        f"/{normalized_path.name}.pro",
        f"/{normalized_path.name}.pri",
        f"/{normalized_path.name}.prf",
    ]
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


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
    normalized_text, assignment_entries, subdir_entries, _symbol_entries = _prepared_analysis_context(
        text
    )
    if not is_probable_qmake_source(path=path, text=text, normalized_text=normalized_text):
        return ()
    return _build_dependencies_with_context(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        normalized_text=normalized_text,
        subdir_entries=subdir_entries,
    )


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
    normalized_text, assignment_entries, subdir_entries, symbol_entries = _prepared_analysis_context(
        text
    )
    if not is_probable_qmake_source(path=path, text=text, normalized_text=normalized_text):
        return (), (), ()
    module_name = path.stem or path.name
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "qmake", "start": 1},
        ),
        symbol_name=module_name,
        symbol_kind="qmake",
        start_line=1,
        end_line=_line_count(normalized_text),
        parent_symbol_id=None,
        signature=f"qmake {module_name}",
    )
    collected_symbols: list[tuple[_Symbol, int]] = [(module_symbol, 1)]
    for symbol_name, symbol_kind, start_line in symbol_entries:
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
                    signature=f"{symbol_kind}({symbol_name})",
                ),
                start_line,
            )
        )
    finalized_symbols: list[_Symbol] = []
    final_line = _line_count(normalized_text)
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
    dependencies = _build_dependencies_with_context(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        normalized_text=normalized_text,
        subdir_entries=subdir_entries,
    )
    local_symbol_ids = {
        symbol.symbol_name: symbol.symbol_id
        for symbol in finalized_symbols
        if symbol.symbol_kind in {"target", "subdir"} and symbol.symbol_name
    }
    imported_target_files = {
        dependency.target_symbol: dependency.target_file
        for dependency in dependencies
        if dependency.target_symbol
    }
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for source_name, target_name, line_number in iter_reference_names(
        text,
        subdir_entries=subdir_entries,
    ):
        source_symbol_id = local_symbol_ids.get(source_name, module_symbol.symbol_id)
        if target_name in local_symbol_ids and local_symbol_ids[target_name] != source_symbol_id:
            edge_id = stable_identifier(
                "symref",
                {
                    "file_path": file_path,
                    "source_symbol_id": source_symbol_id,
                    "target_symbol_id": local_symbol_ids[target_name],
                    "line": line_number,
                },
            )
            reference_candidates.setdefault(
                edge_id,
                _SymbolReferenceCandidate(
                    reference_edge_id=edge_id,
                    source_file=file_path,
                    source_symbol_id=source_symbol_id,
                    target_symbol_id=local_symbol_ids[target_name],
                    target_file=file_path,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
            continue
        target_file = imported_target_files.get(target_name)
        if target_file is None:
            continue
        edge_id = stable_identifier(
            "symref",
            {
                "file_path": file_path,
                "source_symbol_id": source_symbol_id,
                "target": target_name,
                "line": line_number,
            },
        )
        reference_candidates.setdefault(
            edge_id,
            _SymbolReferenceCandidate(
                reference_edge_id=edge_id,
                source_file=file_path,
                source_symbol_id=source_symbol_id,
                target_symbol_id=None,
                target_file=target_file,
                target_names=(target_name,),
                reference_type="references_symbol",
            ),
        )
    return tuple(finalized_symbols), dependencies, tuple(reference_candidates.values())
