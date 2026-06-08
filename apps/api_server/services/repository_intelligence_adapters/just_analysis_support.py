from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    just_primitives as repository_just_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_just_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_just_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_just_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_just_primitives._KNOWN_SUFFIXES
JUSTFILE_BASENAMES = repository_just_primitives.JUSTFILE_BASENAMES
_line_count = repository_just_primitives._line_count
_ordered_names = repository_just_primitives._ordered_names
has_just_path_hints = repository_just_primitives.has_just_path_hints
is_probable_just_source = repository_just_primitives.is_probable_just_source
iter_import_targets = repository_just_primitives.iter_import_targets
iter_mod_targets = repository_just_primitives.iter_mod_targets
iter_reference_names = repository_just_primitives.iter_reference_names
iter_symbol_entries = repository_just_primitives.iter_symbol_entries
module_name_from_path = repository_just_primitives.module_name_from_path
normalize_import_target = repository_just_primitives.normalize_import_target
strip_comments = repository_just_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if not has_just_path_hints(path):
        return set()
    aliases = {
        file_path,
        path.name,
        str(path.with_suffix("")) if path.suffix else file_path,
        str(path.with_suffix("")).replace("/", ".") if path.suffix else file_path.replace("/", "."),
        path.stem,
    }
    if path.name.lower() in JUSTFILE_BASENAMES and path.parent != PurePosixPath("."):
        aliases.add(str(path.parent))
        aliases.add(str(path.parent).replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_just_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(file_path)
    aliases.add(module_name)
    aliases.add(module_name.replace("/", "."))
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name.replace('/', '.')}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
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
        or normalized_target.startswith("/")
        or normalized_target.startswith("~")
        or "$" in normalized_target
    ):
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    normalized_path = PurePosixPath(normalized_target)
    lowered_name = normalized_path.name.lower()
    if lowered_name not in JUSTFILE_BASENAMES and normalized_path.suffix.lower() not in _KNOWN_SUFFIXES:
        candidate_keys.extend(
            (
                f"{normalized_target}.just",
                f"{normalized_target}/justfile",
                f"{normalized_target}/Justfile",
                f"{normalized_target}/.justfile",
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
    target_name = normalized_path.stem or normalized_path.name
    suffixes = [f"/{target_name}.just", f"/{target_name}/justfile", f"/{target_name}/Justfile"]
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
    if not is_probable_just_source(path=path, text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str | None, str]] = set()
    for module_name, import_target, line_number in iter_mod_targets(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_symbol = module_name or PurePosixPath(import_target).stem or None
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
                        "module": module_name,
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
    for import_target, line_number in iter_import_targets(text):
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
    if not is_probable_just_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path) or path.name
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name,
                "symbol_kind": "just",
                "start": 1,
            },
        ),
        symbol_name=module_name,
        symbol_kind="just",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"just {module_name}",
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
    lines = stripped_text.splitlines()
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in finalized_symbols:
        if symbol.symbol_kind == "just":
            continue
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for target_name, line_number in iter_reference_names(snippet):
            module_target = target_name.split("::", 1)[0] if "::" in target_name else target_name
            leaf_target = target_name.rsplit("::", 1)[-1]
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
            imported_target_file = imported_target_files.get(module_target) or imported_target_files.get(
                leaf_target
            )
            if imported_target_file is None and "::" in target_name:
                imported_target_file = resolve_import(
                    current_file=file_path,
                    import_target=module_target,
                    module_index=module_index,
                    normalize_repository_relative_path=normalize_repository_relative_path,
                    resolve_suffix_match=resolve_suffix_match,
                )
            if imported_target_file is None:
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
