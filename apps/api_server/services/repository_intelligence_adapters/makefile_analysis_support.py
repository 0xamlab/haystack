from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    makefile_primitives as repository_makefile_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_makefile_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_makefile_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_makefile_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_makefile_primitives._KNOWN_SUFFIXES
_MAKEFILE_BASENAMES = repository_makefile_primitives._MAKEFILE_BASENAMES
_line_count = repository_makefile_primitives._line_count
_ordered_names = repository_makefile_primitives._ordered_names
has_makefile_path_hints = repository_makefile_primitives.has_makefile_path_hints
is_operational_target_name = repository_makefile_primitives.is_operational_target_name
is_probable_makefile_source = repository_makefile_primitives.is_probable_makefile_source
iter_include_targets = repository_makefile_primitives.iter_include_targets
iter_reference_names = repository_makefile_primitives.iter_reference_names
iter_symbol_entries = repository_makefile_primitives.iter_symbol_entries
module_name_from_path = repository_makefile_primitives.module_name_from_path
normalize_include_target = repository_makefile_primitives.normalize_include_target
strip_comments = repository_makefile_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if not has_makefile_path_hints(path):
        return set()
    aliases = {
        file_path,
        str(path.with_suffix("")) if path.suffix else file_path,
        str(path.with_suffix("")).replace("/", ".") if path.suffix else file_path.replace("/", "."),
        path.stem,
    }
    if path.name.lower() in _MAKEFILE_BASENAMES and path.parent != PurePosixPath("."):
        aliases.add(str(path.parent))
        aliases.add(str(path.parent).replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_makefile_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(file_path)
    aliases.add(module_name)
    aliases.add(module_name.replace("/", "."))
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
    normalized_target = normalize_include_target(import_target)
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
    candidate_keys = [normalized_target]
    if current_dir:
        candidate_keys.append(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / normalized_target))
        )
    target_name = PurePosixPath(normalized_target).name
    if PurePosixPath(normalized_target).suffix.lower() not in _KNOWN_SUFFIXES:
        candidate_keys.extend(f"{normalized_target}{suffix}" for suffix in sorted(_KNOWN_SUFFIXES))
        candidate_keys.extend(
            f"{normalized_target}/{basename}"
            for basename in ("Makefile", "makefile", "GNUmakefile")
        )
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    suffixes = [f"/{target_name}"]
    if "." not in target_name:
        suffixes.extend(f"/{target_name}{suffix}" for suffix in sorted(_KNOWN_SUFFIXES))
    suffixes.extend(
        f"/{basename}" for basename in ("Makefile", "makefile", "GNUmakefile")
    )
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
    if not is_probable_makefile_source(path=path, text=text):
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
    if not is_probable_makefile_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path) or path.name
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name,
                "symbol_kind": "makefile",
                "start": 1,
            },
        ),
        symbol_name=module_name,
        symbol_kind="makefile",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"makefile {module_name}",
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
                    signature=f"{symbol_name}:",
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
    dependency_targets = tuple(dependencies)
    imported_target_files = tuple(
        dependency.target_file for dependency in dependency_targets if dependency.target_file
    )
    lines = stripped_text.splitlines()
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in finalized_symbols:
        if symbol.symbol_kind == "makefile":
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
            for target_file in imported_target_files or (None,):
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
        for dependency in dependency_targets:
            if dependency.target_file is None or dependency.target_file == file_path:
                continue
            target_name = dependency.target_symbol or PurePosixPath(dependency.target_file).stem
            edge_id = stable_identifier(
                "symref",
                {
                    "file_path": file_path,
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": dependency.target_file,
                    "target_names": (target_name,),
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
                    target_names=_ordered_names(target_name),
                    reference_type="references_symbol",
                ),
            )
    return (
        tuple(finalized_symbols),
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
