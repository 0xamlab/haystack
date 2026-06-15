from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    stylus_primitives as repository_stylus_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_stylus_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_stylus_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_stylus_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_stylus_primitives._KNOWN_SUFFIXES
_line_count = repository_stylus_primitives._line_count
_ordered_names = repository_stylus_primitives._ordered_names
has_stylus_path_hints = repository_stylus_primitives.has_stylus_path_hints
is_probable_stylus_source = repository_stylus_primitives.is_probable_stylus_source
iter_import_entries = repository_stylus_primitives.iter_import_entries
iter_reference_entries = repository_stylus_primitives.iter_reference_entries
iter_symbol_entries = repository_stylus_primitives.iter_symbol_entries
module_name_from_path = repository_stylus_primitives.module_name_from_path
source_symbol_name_for_line = repository_stylus_primitives.source_symbol_name_for_line
strip_comments = repository_stylus_primitives.strip_comments


def _candidate_import_paths(import_target: str) -> tuple[str, ...]:
    target_path = PurePosixPath(import_target)
    if target_path.suffix.lower() in _KNOWN_SUFFIXES:
        exact_name = target_path.name
        partial_name = exact_name if exact_name.startswith("_") else f"_{exact_name}"
        candidates = [str(target_path), str(target_path.with_name(partial_name))]
    else:
        parent = target_path.parent
        stem = target_path.name
        candidates = [
            str(parent / f"{stem}.styl") if str(parent) != "." else f"{stem}.styl",
            str(parent / f"_{stem}.styl") if str(parent) != "." else f"_{stem}.styl",
            str(target_path / "index.styl"),
            str(target_path / "_index.styl"),
        ]
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate))


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if not has_stylus_path_hints(path):
        return set()
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        module_name,
        module_name.replace("/", "."),
        path.stem,
        path.stem.lstrip("_"),
    }
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    if text and not is_probable_stylus_source(
        path=path,
        text=text,
        stripped_text=stripped_text,
    ):
        return {alias for alias in aliases if alias}
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(
        text,
        stripped_text=stripped_text,
    ):
        aliases.add(symbol_name)
        aliases.add(f"{module_name.replace('/', '.')}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import_target(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if (
        not normalized_target
        or normalized_target.startswith(("http://", "https://", "//"))
        or normalized_target.endswith(".css")
    ):
        return None
    candidate_keys = list(_candidate_import_paths(normalized_target))
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
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
    suffixes = tuple(f"/{PurePosixPath(candidate).name}" for candidate in candidate_keys)
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def _extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[tuple[_Dependency, ...], tuple[str, ...]]:
    dependencies: list[_Dependency] = []
    wildcard_targets: list[str] = []
    seen_dependencies: set[tuple[str, str | None, str | None]] = set()
    for dependency_kind, import_target, line_number in iter_import_entries(
        text,
        stripped_text=stripped_text,
    ):
        target_file = resolve_import_target(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_symbol = module_name_from_path(target_file or import_target).split("/")[-1] or None
        dependency_type = "requires" if dependency_kind == "require" else "imports"
        dependency_key = (dependency_type, target_file, target_symbol)
        if dependency_key not in seen_dependencies:
            seen_dependencies.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "kind": dependency_type,
                            "line": line_number,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=target_symbol,
                    dependency_type=dependency_type,
                )
            )
        if target_file is not None:
            wildcard_targets.append(target_file)
    return tuple(dependencies), tuple(dict.fromkeys(wildcard_targets))


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[_Dependency, ...]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    if not is_probable_stylus_source(
        path=PurePosixPath(file_path),
        text=text,
        stripped_text=stripped_text,
    ):
        return ()
    dependencies, _wildcard_targets = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
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
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    stripped_text = strip_comments(text)
    if not is_probable_stylus_source(
        path=PurePosixPath(file_path),
        text=text,
        stripped_text=stripped_text,
    ):
        return (), (), ()
    module_name = module_name_from_path(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier("sym", {"file_path": file_path, "symbol_name": module_name}),
        symbol_name=module_name,
        symbol_kind="stylus",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=module_name,
    )
    symbols: list[_Symbol] = [module_symbol]
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(
        text,
        stripped_text=stripped_text,
    ):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                        "line": line_number,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol.symbol_id,
                signature=symbol_name,
            )
        )

    dependencies, wildcard_targets = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    local_symbol_ids = {symbol.symbol_name: symbol.symbol_id for symbol in symbols[1:]}
    symbol_entries = iter_symbol_entries(text, stripped_text=stripped_text)
    references: list[_SymbolReferenceCandidate] = []
    seen_references: set[tuple[str, str | None, str, str]] = set()

    def _append_reference(
        *,
        source_symbol_id: str,
        target_file: str | None,
        target_name: str,
        target_symbol_id: str | None = None,
    ) -> None:
        normalized_target_name = str(target_name or "").strip()
        if not normalized_target_name:
            return
        reference_key = (source_symbol_id, target_file, normalized_target_name, target_symbol_id or "")
        if reference_key in seen_references:
            return
        seen_references.add(reference_key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": source_symbol_id,
                        "target_file": target_file,
                        "target_name": normalized_target_name,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=(normalized_target_name,),
                reference_type="references_symbol",
            )
        )

    for _reference_kind, _owner, target_name, line_number in iter_reference_entries(
        text,
        stripped_text=stripped_text,
    ):
        source_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = local_symbol_ids.get(source_name or "", module_symbol.symbol_id)
        target_symbol_id = local_symbol_ids.get(target_name)
        if target_symbol_id is not None:
            _append_reference(
                source_symbol_id=source_symbol_id,
                target_file=file_path,
                target_name=target_name,
                target_symbol_id=target_symbol_id,
            )
            continue
        for wildcard_target in wildcard_targets:
            _append_reference(
                source_symbol_id=source_symbol_id,
                target_file=wildcard_target,
                target_name=target_name,
            )
    return tuple(symbols), dependencies, tuple(references)
