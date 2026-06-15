from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    qml_primitives as repository_qml_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_qml_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_qml_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_qml_primitives.ResolveSuffixMatch

QML_CONFIG_BASENAMES = repository_qml_primitives.QML_CONFIG_BASENAMES
QML_SUFFIXES = repository_qml_primitives.QML_SUFFIXES
_line_count = repository_qml_primitives._line_count
_ordered_names = repository_qml_primitives._ordered_names
has_qml_path_hints = repository_qml_primitives.has_qml_path_hints
is_probable_qml_source = repository_qml_primitives.is_probable_qml_source
iter_import_entries = repository_qml_primitives.iter_import_entries
iter_qmldir_exports = repository_qml_primitives.iter_qmldir_exports
iter_qmldir_module_names = repository_qml_primitives.iter_qmldir_module_names
iter_reference_names = repository_qml_primitives.iter_reference_names
iter_symbol_entries = repository_qml_primitives.iter_symbol_entries
module_name_from_path = repository_qml_primitives.module_name_from_path
strip_comments = repository_qml_primitives.strip_comments


def _component_module_names(*, root_path: Path, path: PurePosixPath) -> tuple[str, ...]:
    module_names: list[str] = []
    seen: set[str] = set()
    search_parts = list(path.parent.parts)
    while True:
        candidate_dir = PurePosixPath(*search_parts) if search_parts else PurePosixPath(".")
        qmldir_path = root_path / candidate_dir / "qmldir"
        try:
            qmldir_text = qmldir_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            qmldir_text = ""
        for module_name, _line_number in iter_qmldir_module_names(qmldir_text):
            if module_name not in seen:
                seen.add(module_name)
                module_names.append(module_name)
        if not search_parts:
            break
        search_parts.pop()
    return tuple(module_names)


def _resolve_component_reference(
    *,
    file_path: str,
    module_index: dict[str, str],
    module_target: str,
    leaf_target: str,
    imported_target_files: dict[str, str | None],
) -> str | None:
    imported_target_file = (
        module_index.get(f"{module_target}.{leaf_target}")
        or module_index.get(module_target)
        or module_index.get(leaf_target)
        or imported_target_files.get(module_target)
        or imported_target_files.get(leaf_target)
    )
    if imported_target_file and PurePosixPath(imported_target_file).name.lower() != "qmldir":
        return imported_target_file if imported_target_file != file_path else None
    for alias, resolved_path in sorted(module_index.items()):
        if (
            resolved_path != file_path
            and PurePosixPath(resolved_path).name.lower() != "qmldir"
            and alias.rsplit(".", 1)[-1] == leaf_target
        ):
            return resolved_path
    return imported_target_file if imported_target_file != file_path else None


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if not has_qml_path_hints(path):
        return set()
    aliases = {file_path, path.name, module_name_from_path(file_path)}
    if path.suffix:
        aliases.add(str(path.with_suffix("")))
        aliases.add(str(path.with_suffix("")).replace("/", "."))
    if path.parent not in {PurePosixPath("."), PurePosixPath("")}:
        aliases.add(path.parent.as_posix())
        aliases.add(path.parent.as_posix().replace("/", "."))
        if path.suffix:
            aliases.add(f"{path.parent.as_posix().replace('/', '.')}.{path.stem}")
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    if text and not is_probable_qml_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    if path.suffix.lower() == ".qml":
        for module_name in _component_module_names(root_path=root_path, path=path):
            aliases.add(module_name)
            aliases.add(f"{module_name}.{path.stem}")
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text, path=path):
        aliases.add(symbol_name)
        if path.parent not in {PurePosixPath("."), PurePosixPath("")}:
            aliases.add(f"{path.parent.as_posix().replace('/', '.')}.{symbol_name}")
        for module_name, _line_number in iter_qmldir_module_names(text):
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
    if normalized_target == ".":
        candidate_keys = ["qmldir"]
    elif normalized_path.suffix.lower() != ".qml":
        target_name = normalized_path.name or PurePosixPath(current_file).parent.name
        candidate_keys.extend((f"{normalized_target}/qmldir", f"{normalized_target}/{target_name}.qml"))
    if current_dir:
        candidate_keys.extend(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / candidate_key))
            for candidate_key in tuple(candidate_keys)
        )
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate) or module_index.get(
            normalized_candidate.replace("/", ".")
        )
        if resolved is not None and resolved != current_file:
            return resolved
    resolved = module_index.get(normalized_target)
    if resolved is not None and resolved != current_file:
        return resolved
    suffixes = ["/qmldir", f"/{normalized_path.name}.qml"] if normalized_path.name else ["/qmldir"]
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
    if not is_probable_qml_source(path=path, text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str | None, str]] = set()
    if path.name.lower() in QML_CONFIG_BASENAMES:
        for export_name, export_path, line_number in iter_qmldir_exports(text):
            target_file = normalize_repository_relative_path(
                str(PurePosixPath(file_path).parent / export_path)
            )
            dependency_key = (target_file, export_name, "imports")
            if dependency_key in seen_dependencies:
                continue
            seen_dependencies.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": export_path,
                            "symbol": export_name,
                            "line": line_number,
                            "kind": "imports",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=export_name,
                    dependency_type="imports",
                )
            )
        return tuple(dependencies)
    for import_target, alias, line_number in iter_import_entries(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        default_symbol = PurePosixPath(import_target).stem or import_target.rsplit(".", 1)[-1] or None
        target_symbol = alias or default_symbol
        dependency_key = (target_file, target_symbol, "imports")
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
                        "alias": alias,
                        "line": line_number,
                        "kind": "imports",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="imports",
            )
        )
    return tuple(dependencies)


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
    if not is_probable_qml_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    root_name = module_name_from_path(file_path)
    root_kind = "qml_module" if path.name.lower() in QML_CONFIG_BASENAMES else "qml"
    root_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": root_name,
                "symbol_kind": root_kind,
                "start": 1,
            },
        ),
        symbol_name=root_name,
        symbol_kind=root_kind,
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"{root_kind} {root_name}",
    )
    collected_symbols: list[tuple[_Symbol, int]] = [(root_symbol, 1)]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text, path=path):
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
                    parent_symbol_id=root_symbol.symbol_id,
                    signature=f"{symbol_kind} {symbol_name}",
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
        symbol.symbol_name: symbol.symbol_id for symbol in finalized_symbols if symbol.symbol_name
    }
    imported_target_files = {
        dependency.target_symbol: dependency.target_file
        for dependency in dependencies
        if dependency.target_symbol
    }
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    lines = stripped_text.splitlines()
    for symbol in finalized_symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for target_name, line_number in iter_reference_names(snippet):
            module_target = target_name.split(".", 1)[0]
            leaf_target = target_name.rsplit(".", 1)[-1]
            target_names = _ordered_names(target_name, leaf_target)
            if leaf_target in local_symbol_ids and local_symbol_ids[leaf_target] != symbol.symbol_id:
                edge_id = stable_identifier(
                    "symref",
                    {
                        "file_path": file_path,
                        "symbol_id": symbol.symbol_id,
                        "target": leaf_target,
                        "line": line_number,
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_file=file_path,
                        source_symbol_id=symbol.symbol_id,
                        target_symbol_id=local_symbol_ids[leaf_target],
                        target_file=file_path,
                        target_names=target_names,
                        reference_type="references_symbol",
                    ),
                )
                continue
            imported_target_file = (
                module_index.get(target_name)
                or module_index.get(target_name.replace("/", "."))
                or _resolve_component_reference(
                    file_path=file_path,
                    module_index=module_index,
                    module_target=module_target,
                    leaf_target=leaf_target,
                    imported_target_files=imported_target_files,
                )
            )
            if imported_target_file is None or imported_target_file == file_path:
                continue
            edge_id = stable_identifier(
                "symref",
                {
                    "file_path": file_path,
                    "symbol_id": symbol.symbol_id,
                    "target": target_name,
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
                    target_file=imported_target_file,
                    target_names=target_names,
                    reference_type="references_symbol",
                ),
            )
    return tuple(finalized_symbols), dependencies, tuple(reference_candidates.values())
