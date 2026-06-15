from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    vimscript_primitives as repository_vimscript_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_vimscript_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_vimscript_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_vimscript_primitives.ResolveSuffixMatch

autoload_target_for_name = repository_vimscript_primitives.autoload_target_for_name
has_vimscript_path_hints = repository_vimscript_primitives.has_vimscript_path_hints
is_probable_vimscript_source = repository_vimscript_primitives.is_probable_vimscript_source
iter_reference_names = repository_vimscript_primitives.iter_reference_names
iter_source_statements = repository_vimscript_primitives.iter_source_statements
iter_symbol_entries = repository_vimscript_primitives.iter_symbol_entries
module_name_from_path = repository_vimscript_primitives.module_name_from_path
normalize_identifier = repository_vimscript_primitives.normalize_identifier
strip_comments = repository_vimscript_primitives.strip_comments


def _line_count(text: str) -> int:
    return max(1, str(text or "").count("\n") + 1)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if not has_vimscript_path_hints(path):
        return set()
    aliases = {
        file_path,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
        path.stem,
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_vimscript_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(file_path)
    stripped_text = strip_comments(text)
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(
        text,
        stripped_text=stripped_text,
    ):
        aliases.add(symbol_name)
        bare_name = symbol_name.split(":", 1)[-1]
        aliases.add(bare_name)
        if module_name:
            aliases.add(f"{module_name}.{bare_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path,
    resolve_suffix_match,
) -> str | None:
    normalized_target = normalize_identifier(import_target)
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    raw_candidates = [
        normalized_target,
        str(current_dir / normalized_target),
    ]
    candidate_paths: list[str] = []
    for raw_candidate in raw_candidates:
        normalized_candidate = normalize_repository_relative_path(raw_candidate)
        if not normalized_candidate:
            continue
        candidate_paths.append(normalized_candidate)
        if not PurePosixPath(normalized_candidate).suffix:
            candidate_paths.append(
                normalize_repository_relative_path(f"{normalized_candidate}.vim")
            )
    for candidate_path in tuple(dict.fromkeys(path for path in candidate_paths if path)):
        resolved = module_index.get(candidate_path)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[path for path in dict.fromkeys(candidate_paths) if path],
    )


def _import_bindings_for_text(
    *,
    file_path: str,
    text: str,
    stripped_text: str,
    module_index: dict[str, str],
    stable_identifier,
    normalize_repository_relative_path,
    resolve_suffix_match,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str]] = set()
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_target, line_number in iter_source_statements(
        text,
        stripped_text=stripped_text,
    ):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
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
                        "kind": "imports",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=PurePosixPath(import_target).stem or None,
                dependency_type="imports",
            )
        )
    return tuple(dependencies), bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier,
    normalize_repository_relative_path,
    resolve_suffix_match,
) -> tuple[_Dependency, ...]:
    path = PurePosixPath(file_path)
    if not is_probable_vimscript_source(path=path, text=text):
        return ()
    stripped_text = strip_comments(text)
    dependencies, _bindings = _import_bindings_for_text(
        file_path=file_path,
        text=text,
        stripped_text=stripped_text,
        module_index=module_index,
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
    stable_identifier,
    normalize_repository_relative_path,
    resolve_suffix_match,
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    path = PurePosixPath(file_path)
    if not is_probable_vimscript_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path)
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
        signature=f"module {module_name}" if module_name else None,
    )
    collected_symbols: list[tuple[_Symbol, int]] = [(module_symbol, 1)]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(
        text,
        stripped_text=stripped_text,
    ):
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
    dependencies, bindings = _import_bindings_for_text(
        file_path=file_path,
        text=text,
        stripped_text=stripped_text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    symbol_lookup = {
        symbol.symbol_name: symbol.symbol_id
        for symbol in finalized_symbols
        if symbol.symbol_name
    }
    reference_candidates: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, int]] = set()
    for reference_name, line_number in iter_reference_names(
        text,
        stripped_text=stripped_text,
    ):
        binding = bindings.get(reference_name)
        target_symbol_id: str | None = None
        target_file = None
        target_names: tuple[str, ...] = (reference_name,)
        if binding is not None:
            target_file = binding.target_file
            target_names = binding.target_names or target_names
        elif reference_name in symbol_lookup:
            target_symbol_id = symbol_lookup[reference_name]
            target_file = file_path
        else:
            autoload_target = autoload_target_for_name(reference_name)
            if autoload_target:
                resolved_target = resolve_import(
                    current_file=file_path,
                    import_target=autoload_target,
                    module_index=module_index,
                    normalize_repository_relative_path=normalize_repository_relative_path,
                    resolve_suffix_match=resolve_suffix_match,
                )
                if resolved_target:
                    target_file = resolved_target
        if target_file is None and target_symbol_id is None:
            continue
        reference_key = (reference_name, line_number)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        reference_candidates.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "symref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": module_symbol.symbol_id,
                        "target": reference_name,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                source_symbol_id=module_symbol.symbol_id,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=target_names,
                reference_type="calls",
            )
        )
    return tuple(finalized_symbols), dependencies, tuple(reference_candidates)
