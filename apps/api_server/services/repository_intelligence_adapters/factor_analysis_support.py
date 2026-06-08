from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    factor_primitives as repository_factor_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_factor_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_factor_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_factor_primitives.ResolveSuffixMatch

FACTOR_CONFIG_BASENAMES = repository_factor_primitives.FACTOR_CONFIG_BASENAMES
FACTOR_FILE_SUFFIXES = repository_factor_primitives.FACTOR_FILE_SUFFIXES
RESERVED_SYMBOL_NAMES = repository_factor_primitives.RESERVED_SYMBOL_NAMES
_CollectedSymbol = repository_factor_primitives._CollectedSymbol
_ImportStatement = repository_factor_primitives._ImportStatement
_line_count = repository_factor_primitives._line_count
_ordered_names = repository_factor_primitives._ordered_names
has_factor_path_hints = repository_factor_primitives.has_factor_path_hints
is_probable_factor_source = repository_factor_primitives.is_probable_factor_source
iter_symbol_entries = repository_factor_primitives.iter_symbol_entries
parse_import_statements = repository_factor_primitives.parse_import_statements
parse_reference_targets = repository_factor_primitives.parse_reference_targets
strip_comments = repository_factor_primitives.strip_comments
vocabulary_name_from_text = repository_factor_primitives.vocabulary_name_from_text


def _path_vocabulary_aliases(file_path: str) -> tuple[str, ...]:
    path = PurePosixPath(file_path).with_suffix("")
    parts = path.parts
    aliases = {".".join(parts), ".".join(parts[1:]) if len(parts) > 1 else ""}
    if path.parent.name == path.stem:
        aliases.add(".".join(path.parent.parts))
        aliases.add(".".join(path.parent.parts[1:]) if len(path.parent.parts) > 1 else "")
    return tuple(alias for alias in aliases if alias)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    vocabulary_name = vocabulary_name_from_text(stripped_text, file_path=file_path)
    vocabulary_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": vocabulary_name, "symbol_kind": "vocabulary"},
        ),
        symbol_name=vocabulary_name,
        symbol_kind="vocabulary",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=vocabulary_name,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=vocabulary_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
            qualified_names=_ordered_names(
                vocabulary_name,
                file_path,
                str(PurePosixPath(file_path).with_suffix("")),
                PurePosixPath(file_path).stem,
                *_path_vocabulary_aliases(file_path),
            ),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": symbol_name,
                            "symbol_kind": symbol_kind,
                            "start_line": start_line,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=start_line,
                    end_line=start_line,
                    parent_symbol_id=vocabulary_symbol.symbol_id,
                    signature=symbol_name,
                ),
                local_start_line=start_line,
                local_end_line=start_line,
                qualified_names=_ordered_names(symbol_name, f"{vocabulary_name}.{symbol_name}"),
            )
        )
    final_line = _line_count(stripped_text)
    finalized: list[_CollectedSymbol] = []
    for index, collected_symbol in enumerate(collected_symbols):
        end_line = (
            max(
                collected_symbols[index + 1].local_start_line - 1,
                collected_symbol.local_start_line,
            )
            if index + 1 < len(collected_symbols)
            else final_line
        )
        symbol = collected_symbol.symbol
        finalized.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=symbol.symbol_id,
                    symbol_name=symbol.symbol_name,
                    symbol_kind=symbol.symbol_kind,
                    start_line=symbol.start_line,
                    end_line=end_line,
                    parent_symbol_id=symbol.parent_symbol_id,
                    signature=symbol.signature,
                ),
                local_start_line=collected_symbol.local_start_line,
                local_end_line=end_line,
                qualified_names=collected_symbol.qualified_names,
            )
        )
    return tuple(finalized)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    aliases = {
        file_path,
        str(path.with_suffix("")),
        path.stem,
        *_path_vocabulary_aliases(file_path),
    }
    if path.suffix.lower() not in FACTOR_FILE_SUFFIXES:
        return {alias for alias in aliases if alias}
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_factor_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    vocabulary_name = vocabulary_name_from_text(text, file_path=file_path)
    aliases.add(vocabulary_name)
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if not normalized_target:
        return None
    candidate_targets = (
        normalized_target,
        normalized_target.replace(".", "/"),
        normalized_target.rsplit(".", 1)[-1].strip(),
    )
    for candidate in candidate_targets:
        target_file = module_index.get(candidate)
        if target_file is not None:
            return target_file
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_targets)


def _extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], tuple[tuple[_ImportStatement, str | None], ...]]:
    dependencies: list[_Dependency] = []
    resolved_imports: list[tuple[_ImportStatement, str | None]] = []
    seen_dependency_keys: set[tuple[str, str | None]] = set()
    for import_statement in parse_import_statements(text):
        target_file = resolve_import(
            import_statement.target,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (import_statement.target, target_file)
        if dependency_key not in seen_dependency_keys:
            seen_dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_statement.target,
                            "line": import_statement.line_number,
                            "type": "imports",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=import_statement.target,
                    dependency_type="imports",
                )
            )
        resolved_imports.append((import_statement, target_file))
    return tuple(dependencies), tuple(resolved_imports)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    _ = normalize_repository_relative_path
    dependencies, _resolved_imports = _extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
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
    _ = normalize_repository_relative_path
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    vocabulary_name = vocabulary_name_from_text(text, file_path=file_path)
    symbol_name_to_id = {
        collected_symbol.symbol.symbol_name: collected_symbol.symbol.symbol_id
        for collected_symbol in collected_symbols
    }
    dependencies, resolved_imports = _extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str | None, str, str]] = set()
    for qualifier, symbol_name, line_number in parse_reference_targets(text):
        if symbol_name in RESERVED_SYMBOL_NAMES:
            continue
        source_symbol = next(
            (
                collected_symbol.symbol
                for collected_symbol in reversed(collected_symbols)
                if collected_symbol.symbol.symbol_kind != "vocabulary"
                and collected_symbol.local_start_line <= line_number
                <= collected_symbol.local_end_line
            ),
            collected_symbols[0].symbol,
        )
        candidate_targets: list[tuple[str | None, str | None, tuple[str, ...]]] = []
        if qualifier:
            for import_statement, target_file in resolved_imports:
                if qualifier not in {import_statement.qualifier, import_statement.target}:
                    continue
                candidate_targets.append(
                    (
                        target_file,
                        None,
                        _ordered_names(symbol_name, f"{import_statement.target}.{symbol_name}"),
                    )
                )
            target_file = module_index.get(qualifier)
            if target_file is not None:
                candidate_targets.append(
                    (
                        target_file,
                        None,
                        _ordered_names(symbol_name, f"{qualifier}.{symbol_name}"),
                    )
                )
        else:
            local_symbol_id = symbol_name_to_id.get(symbol_name)
            if local_symbol_id is not None and local_symbol_id != source_symbol.symbol_id:
                candidate_targets.append((file_path, local_symbol_id, (symbol_name,)))
            vocabulary_target = module_index.get(f"{vocabulary_name}.{symbol_name}")
            if vocabulary_target is not None:
                candidate_targets.append(
                    (
                        vocabulary_target,
                        (
                            symbol_name_to_id.get(symbol_name)
                            if vocabulary_target == file_path
                            else None
                        ),
                        _ordered_names(symbol_name, f"{vocabulary_name}.{symbol_name}"),
                    )
                )
            for import_statement, target_file in resolved_imports:
                if (
                    import_statement.imported_names
                    and symbol_name not in import_statement.imported_names
                ):
                    continue
                candidate_targets.append(
                    (
                        target_file,
                        None,
                        _ordered_names(symbol_name, f"{import_statement.target}.{symbol_name}"),
                    )
                )
        for target_file, target_symbol_id, target_names in candidate_targets:
            if target_file is None:
                continue
            reference_key = (
                source_symbol.symbol_id,
                target_symbol_id,
                target_file,
                "|".join(target_names),
            )
            if reference_key in seen_reference_keys:
                continue
            seen_reference_keys.add(reference_key)
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": source_symbol.symbol_id,
                    "target_file": target_file,
                    "target_names": target_names,
                    "type": "references_symbol",
                },
            )
            references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=edge_id,
                    source_symbol_id=source_symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=target_symbol_id,
                    target_file=target_file,
                    target_names=target_names,
                    reference_type="references_symbol",
                )
            )
    return (
        tuple(collected_symbol.symbol for collected_symbol in collected_symbols),
        dependencies,
        tuple(references),
    )
