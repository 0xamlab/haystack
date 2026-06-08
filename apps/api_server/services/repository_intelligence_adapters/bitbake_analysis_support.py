from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    bitbake_primitives as repository_bitbake_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_bitbake_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_bitbake_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_bitbake_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_bitbake_primitives._KNOWN_SUFFIXES
_KNOWN_CONFIG_SUFFIXES = repository_bitbake_primitives._KNOWN_CONFIG_SUFFIXES
BITBAKE_CONFIG_BASENAMES = repository_bitbake_primitives.BITBAKE_CONFIG_BASENAMES
_line_count = repository_bitbake_primitives._line_count
_ordered_names = repository_bitbake_primitives._ordered_names
has_bitbake_path_hints = repository_bitbake_primitives.has_bitbake_path_hints
is_probable_bitbake_source = repository_bitbake_primitives.is_probable_bitbake_source
iter_include_targets = repository_bitbake_primitives.iter_include_targets
iter_inherit_targets = repository_bitbake_primitives.iter_inherit_targets
iter_reference_names = repository_bitbake_primitives.iter_reference_names
iter_symbol_entries = repository_bitbake_primitives.iter_symbol_entries
module_name_from_path = repository_bitbake_primitives.module_name_from_path
normalize_import_target = repository_bitbake_primitives.normalize_import_target
strip_comments = repository_bitbake_primitives.strip_comments


def _recipe_aliases(path: PurePosixPath) -> set[str]:
    aliases = {path.stem}
    if path.suffix.lower() in {".bb", ".bbappend"}:
        recipe_name = module_name_from_path(str(path))
        if recipe_name:
            aliases.add(recipe_name)
            aliases.add(f"recipe:{recipe_name}")
    if path.suffix.lower() == ".bbclass":
        aliases.add(f"class:{path.stem}")
    return {alias for alias in aliases if alias}


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_bitbake_path_hints(path):
        return set()
    aliases = {
        file_path,
        str(path.with_suffix("")) if path.suffix else file_path,
        str(path.with_suffix("")).replace("/", ".") if path.suffix else file_path.replace("/", "."),
        *(_recipe_aliases(path)),
    }
    text_data = text
    if text_data is None:
        try:
            text_data = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text_data = ""
    if text_data and not is_probable_bitbake_source(path=path, text=text_data):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(file_path)
    if module_name:
        aliases.add(module_name)
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text_data):
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
    del stable_identifier
    return {alias for alias in aliases if alias}


def resolve_include_target(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_import_target(import_target)
    if (
        not normalized_target
        or "${" in normalized_target
        or normalized_target.startswith("/")
        or normalized_target.startswith("~")
        or "://" in normalized_target
    ):
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    if current_dir:
        candidate_keys.append(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / normalized_target))
        )
    target_path = PurePosixPath(normalized_target)
    if target_path.suffix.lower() not in _KNOWN_SUFFIXES | _KNOWN_CONFIG_SUFFIXES:
        for suffix in sorted(_KNOWN_SUFFIXES | _KNOWN_CONFIG_SUFFIXES):
            candidate_keys.extend(
                {
                    f"{normalized_target}{suffix}",
                    normalize_repository_relative_path(
                        str(PurePosixPath(current_dir or "") / f"{normalized_target}{suffix}")
                    ),
                }
            )
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    target_name = target_path.name or normalized_target
    suffixes = [f"/{target_name}"]
    if target_path.suffix.lower() not in _KNOWN_SUFFIXES | _KNOWN_CONFIG_SUFFIXES:
        suffixes.extend(
            f"/{target_name}{suffix}" for suffix in sorted(_KNOWN_SUFFIXES | _KNOWN_CONFIG_SUFFIXES)
        )
    return resolve_suffix_match(module_index=module_index, suffixes=tuple(dict.fromkeys(suffixes)))


def resolve_inherit_target(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_import_target(import_target)
    if not normalized_target or "${" in normalized_target:
        return None
    candidate_keys = [
        f"classes/{normalized_target}.bbclass",
        f"classes-recipe/{normalized_target}.bbclass",
        f"{normalized_target}.bbclass",
    ]
    inherited = resolve_include_target(
        current_file=current_file,
        import_target=normalized_target,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    if inherited is not None:
        return inherited
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(f"/{PurePosixPath(candidate).name}" for candidate in candidate_keys),
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
    path = PurePosixPath(file_path)
    if not is_probable_bitbake_source(path=path, text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str | None, str]] = set()
    for dependency_kind, import_target, line_number in iter_include_targets(text):
        target_file = resolve_include_target(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_symbol = (
            module_name_from_path(import_target)
            or PurePosixPath(import_target).stem
            or None
        )
        dependency_key = (target_file, target_symbol, dependency_kind)
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
                        "kind": dependency_kind,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type=dependency_kind,
            )
        )
    for dependency_kind, import_target, line_number in iter_inherit_targets(text):
        target_file = resolve_inherit_target(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_symbol = import_target
        dependency_key = (target_file, target_symbol, dependency_kind)
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
                        "kind": dependency_kind,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type=dependency_kind,
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
    if not is_probable_bitbake_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path) or path.name
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name,
                "symbol_kind": "bitbake",
                "start": 1,
            },
        ),
        symbol_name=module_name,
        symbol_kind="bitbake",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"bitbake {module_name}",
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
        symbol.symbol_name: symbol.symbol_id for symbol in finalized_symbols if symbol.symbol_name
    }
    lines = stripped_text.splitlines()
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in finalized_symbols:
        if symbol.symbol_kind == "bitbake":
            continue
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
            for dependency in dependencies:
                if dependency.target_symbol != target_name or not dependency.target_file:
                    continue
                edge_id = stable_identifier(
                    "symref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": symbol.symbol_id,
                        "target_file": dependency.target_file,
                        "target_name": target_name,
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
                        target_file=dependency.target_file,
                        target_names=(target_name,),
                        reference_type="references_imported_symbol",
                    ),
                )
    return tuple(finalized_symbols), dependencies, tuple(reference_candidates.values())
