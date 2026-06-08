from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    bicep_primitives as repository_bicep_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_bicep_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_bicep_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_bicep_primitives.ResolveSuffixMatch

_CollectedSymbol = repository_bicep_primitives._CollectedSymbol
_IDENTIFIER_RE = repository_bicep_primitives._IDENTIFIER_RE
_PREFERRED_DIRECTORY_ENTRY_BASENAMES = (
    repository_bicep_primitives._PREFERRED_DIRECTORY_ENTRY_BASENAMES
)
_QUALIFIED_REFERENCE_RE = repository_bicep_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_bicep_primitives._RESERVED_SYMBOL_NAMES
_line_count = repository_bicep_primitives._line_count
_ordered_names = repository_bicep_primitives._ordered_names
has_bicep_path_hints = repository_bicep_primitives.has_bicep_path_hints
is_probable_bicep_source = repository_bicep_primitives.is_probable_bicep_source
iter_symbol_entries = repository_bicep_primitives.iter_symbol_entries
module_name_from_path = repository_bicep_primitives.module_name_from_path
parse_module_statements = repository_bicep_primitives.parse_module_statements
strip_comments = repository_bicep_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "module"},
        ),
        symbol_name=module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=module_name,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
            qualified_names=_ordered_names(
                module_name,
                module_name.replace(".", "/"),
                file_path,
                _without_suffix_path(PurePosixPath(file_path)),
            ),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
        qualified_names = _ordered_names(
            symbol_name,
            f"{module_name}.{symbol_name}" if module_name else "",
        )
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
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=symbol_name,
                ),
                local_start_line=start_line,
                local_end_line=start_line,
                qualified_names=qualified_names,
            )
        )
    final_line = _line_count(stripped_text)
    finalized_symbols: list[_CollectedSymbol] = []
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
        finalized_symbols.append(
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
    return tuple(finalized_symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_bicep_path_hints(path):
        return set()
    aliases = {
        file_path,
        _without_suffix_path(path),
        _without_suffix_path(path).replace("/", "."),
        path.stem,
    }
    if (
        path.name.lower() in _PREFERRED_DIRECTORY_ENTRY_BASENAMES
        and str(path.parent) not in {"", "."}
    ):
        aliases.add(str(path.parent))
        aliases.add(str(path.parent).replace("/", "."))
        aliases.add(path.parent.name)
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_bicep_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    aliases.add(module_name_from_path(file_path))
    aliases.add(module_name_from_path(file_path).replace(".", "/"))
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def resolve_module_source(
    source_target: str,
    current_file: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(source_target or "").strip()
    if not normalized_target.startswith(("./", "../")):
        return None
    normalized_root = normalize_repository_relative_path(
        str(PurePosixPath(current_file).parent / normalized_target)
    )
    if not normalized_root:
        return None
    candidate_targets = (
        normalized_root,
        f"{normalized_root}.bicep",
        f"{normalized_root}/main.bicep",
    )
    for candidate in candidate_targets:
        target_file = module_index.get(candidate)
        if target_file is not None:
            return target_file
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_targets)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str, str, str | None]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for module_name, source_target, line_number in parse_module_statements(text):
        target_file = resolve_module_source(
            source_target,
            file_path,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = ("module", module_name, target_file)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {"file_path": file_path, "target": module_name, "line": line_number},
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=module_name,
                    dependency_type="imports",
                )
            )
        import_bindings[module_name] = _ImportedSymbolBinding(
            alias=module_name,
            target_file=target_file,
            target_names=(module_name,),
        )
    return tuple(dependencies), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies, _bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
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
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    if not is_probable_bicep_source(path=Path(file_path), text=text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    local_symbols_by_alias: dict[str, _Symbol] = {}
    import_aliases = set(import_bindings)
    for collected_symbol in collected_symbols:
        for alias in collected_symbol.qualified_names:
            local_symbols_by_alias.setdefault(alias, collected_symbol.symbol)
        local_symbols_by_alias.setdefault(
            collected_symbol.symbol.symbol_name,
            collected_symbol.symbol,
        )
    stripped_lines = strip_comments(text).splitlines()
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}

    def _record_reference(
        *,
        source_symbol_id: str,
        target_symbol_id: str | None,
        target_file: str | None,
        target_names: tuple[str, ...],
    ) -> None:
        edge_id = stable_identifier(
            "ref",
            {
                "source_symbol_id": source_symbol_id,
                "target_symbol_id": target_symbol_id,
                "target_file": target_file,
                "target_names": target_names,
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            _SymbolReferenceCandidate(
                reference_edge_id=edge_id,
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            ),
        )

    for collected_symbol in collected_symbols:
        symbol = collected_symbol.symbol
        if symbol.symbol_kind == "module":
            continue
        snippet = "\n".join(
            stripped_lines[max(symbol.start_line - 1, 0) : max(symbol.end_line, symbol.start_line)]
        )
        seen_reference_names: set[str] = set()
        for regex in (_QUALIFIED_REFERENCE_RE, _IDENTIFIER_RE):
            for match in regex.finditer(snippet):
                reference_name = str(match.group("name") or "").strip()
                if (
                    not reference_name
                    or reference_name in seen_reference_names
                    or reference_name in _RESERVED_SYMBOL_NAMES
                    or reference_name == symbol.symbol_name
                ):
                    continue
                seen_reference_names.add(reference_name)
                binding = import_bindings.get(reference_name)
                target_symbol = local_symbols_by_alias.get(reference_name)
                if binding is None and target_symbol is None:
                    continue
                _record_reference(
                    source_symbol_id=symbol.symbol_id,
                    target_symbol_id=(
                        None
                        if binding and binding.target_file
                        else getattr(target_symbol, "symbol_id", None)
                    ),
                    target_file=(
                        binding.target_file if binding else file_path if target_symbol else None
                    ),
                    target_names=(reference_name,),
                )
        for module_alias in sorted(import_aliases):
            if module_alias == symbol.symbol_name or module_alias in seen_reference_names:
                continue
            if module_alias not in snippet:
                continue
            binding = import_bindings[module_alias]
            _record_reference(
                source_symbol_id=symbol.symbol_id,
                target_symbol_id=None,
                target_file=binding.target_file,
                target_names=(module_alias,),
            )
    return (
        tuple(item.symbol for item in collected_symbols),
        tuple(dependencies),
        tuple(reference_candidates.values()),
    )
