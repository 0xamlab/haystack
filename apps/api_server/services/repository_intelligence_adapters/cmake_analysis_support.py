from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    cmake_primitives as repository_cmake_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_cmake_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_cmake_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_cmake_primitives.ResolveSuffixMatch

_CMAKE_CONFIG_BASENAMES = repository_cmake_primitives._CMAKE_CONFIG_BASENAMES
_KNOWN_SUFFIXES = repository_cmake_primitives._KNOWN_SUFFIXES
_line_count = repository_cmake_primitives._line_count
has_cmake_path_hints = repository_cmake_primitives.has_cmake_path_hints
is_probable_cmake_source = repository_cmake_primitives.is_probable_cmake_source
iter_include_targets = repository_cmake_primitives.iter_include_targets
iter_package_targets = repository_cmake_primitives.iter_package_targets
iter_reference_names = repository_cmake_primitives.iter_reference_names
iter_subdirectory_targets = repository_cmake_primitives.iter_subdirectory_targets
iter_symbol_entries = repository_cmake_primitives.iter_symbol_entries
strip_comments = repository_cmake_primitives.strip_comments


def _ordered_names(*raw_names: str | None) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_name in raw_names:
        candidate = str(raw_name or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return tuple(ordered)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if not has_cmake_path_hints(path):
        return set()
    aliases = {
        file_path,
        str(path.with_suffix("")) if path.suffix else file_path,
        path.stem,
    }
    if path.name.lower() in _CMAKE_CONFIG_BASENAMES:
        parent = str(path.parent)
        if parent not in {"", "."}:
            aliases.add(parent)
            aliases.add(parent.replace("/", "."))
        aliases.add(path.name)
    else:
        aliases.add(str(path.with_suffix("")).replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_cmake_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
        aliases.add(symbol_name)
        if path.name.lower() in _CMAKE_CONFIG_BASENAMES and path.parent not in {
            PurePosixPath("."),
            PurePosixPath(""),
        }:
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
    if not normalized_target or normalized_target.startswith("$"):
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    if treat_as_directory:
        candidate_keys.append(f"{normalized_target}/CMakeLists.txt")
    elif PurePosixPath(normalized_target).suffix.lower() not in _KNOWN_SUFFIXES:
        candidate_keys.append(f"{normalized_target}.cmake")
        candidate_keys.append(f"{normalized_target}/CMakeLists.txt")
    if current_dir:
        relative_prefix = PurePosixPath(current_dir)
        candidate_keys.extend(
            str(relative_prefix / candidate_key).replace("\\", "/")
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
        f"/{PurePosixPath(normalized_target).name}.cmake",
        f"/{PurePosixPath(normalized_target).name}/CMakeLists.txt",
        "/CMakeLists.txt",
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
    if not is_probable_cmake_source(path=path, text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str | None, str]] = set()
    for import_target, line_number in iter_include_targets(text):
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
    for subdirectory_target, line_number in iter_subdirectory_targets(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=subdirectory_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
            treat_as_directory=True,
        )
        target_name = PurePosixPath(subdirectory_target).name or None
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
                        "target": subdirectory_target,
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
    for package_target, line_number in iter_package_targets(text):
        dependency_key = (None, package_target, "imports")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": package_target,
                        "line": line_number,
                        "kind": "imports",
                    },
                ),
                source_file=file_path,
                target_file=None,
                target_symbol=package_target,
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
    if not is_probable_cmake_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    module_name = path.parent.name if path.name.lower() in _CMAKE_CONFIG_BASENAMES and path.parent.name else path.stem or path.name
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name,
                "symbol_kind": "cmake",
                "start": 1,
            },
        ),
        symbol_name=module_name,
        symbol_kind="cmake",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"cmake {module_name}",
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
                    signature=f"{symbol_kind}({symbol_name})",
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
        if symbol.symbol_kind in {"target", "project", "function", "macro"} and symbol.symbol_name
    }
    imported_target_files = tuple(
        dependency.target_file for dependency in dependencies if dependency.target_file
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for source_target, target_name, line_number in iter_reference_names(stripped_text):
        source_symbol_id = local_symbol_ids.get(source_target, module_symbol.symbol_id)
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
        for target_file in imported_target_files or (None,):
            edge_id = stable_identifier(
                "symref",
                {
                    "file_path": file_path,
                    "source_symbol_id": source_symbol_id,
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
                    source_symbol_id=source_symbol_id,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
    for dependency in dependencies:
        target_name = dependency.target_symbol or (
            PurePosixPath(dependency.target_file).stem if dependency.target_file else None
        )
        if not target_name:
            continue
        edge_id = stable_identifier(
            "symref",
            {
                "file_path": file_path,
                "source_symbol_id": module_symbol.symbol_id,
                "target_file": dependency.target_file,
                "target_names": (target_name,),
            },
        )
        reference_candidates.setdefault(
            edge_id,
            _SymbolReferenceCandidate(
                reference_edge_id=edge_id,
                source_file=file_path,
                source_symbol_id=module_symbol.symbol_id,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=_ordered_names(target_name),
                reference_type="references_symbol",
            ),
        )
    return (
        tuple(finalized_symbols),
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

