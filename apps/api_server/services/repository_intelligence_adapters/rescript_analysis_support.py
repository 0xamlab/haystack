from __future__ import annotations

from collections import defaultdict
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    rescript_primitives as repository_rescript_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_rescript_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_rescript_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_rescript_primitives.ResolveSuffixMatch

RESCRIPT_CONFIG_BASENAMES = repository_rescript_primitives.RESCRIPT_CONFIG_BASENAMES
RESCRIPT_SUFFIXES = repository_rescript_primitives.RESCRIPT_SUFFIXES
_CALL_RE = repository_rescript_primitives._CALL_RE
_CollectedSymbol = repository_rescript_primitives._CollectedSymbol
_MODULE_ALIAS_RE = repository_rescript_primitives._MODULE_ALIAS_RE
_MODULE_DECL_RE = repository_rescript_primitives._MODULE_DECL_RE
_OPEN_RE = repository_rescript_primitives._OPEN_RE
_QUALIFIED_REFERENCE_RE = repository_rescript_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_rescript_primitives._RESERVED_SYMBOL_NAMES
_TYPE_REFERENCE_RE = repository_rescript_primitives._TYPE_REFERENCE_RE
_VALUE_REFERENCE_RE = repository_rescript_primitives._VALUE_REFERENCE_RE
_line_count = repository_rescript_primitives._line_count
_line_number = repository_rescript_primitives._line_number
has_rescript_path_hints = repository_rescript_primitives.has_rescript_path_hints
is_probable_rescript_config = repository_rescript_primitives.is_probable_rescript_config
is_probable_rescript_source = repository_rescript_primitives.is_probable_rescript_source
iter_symbol_entries = repository_rescript_primitives.iter_symbol_entries
module_name_from_path = repository_rescript_primitives.module_name_from_path
strip_comments = repository_rescript_primitives.strip_comments


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
            {
                "file_path": file_path,
                "symbol_name": module_name,
                "symbol_kind": "module",
                "start_line": 1,
            },
        ),
        symbol_name=module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"module {module_name}" if module_name else None,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
            qualified_names=(module_name,) if module_name else (),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
        qualified_names = repository_rescript_primitives._ordered_names(
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
        if index + 1 < len(collected_symbols):
            end_line = max(
                collected_symbols[index + 1].local_start_line - 1,
                collected_symbol.local_start_line,
            )
        else:
            end_line = final_line
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
    if (
        path.suffix.lower() not in RESCRIPT_SUFFIXES
        and path.name.lower() not in RESCRIPT_CONFIG_BASENAMES
    ):
        return set()
    aliases = {
        file_path,
        _without_suffix_path(path),
        _without_suffix_path(path).replace("/", "."),
        path.stem,
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if path.name.lower() in RESCRIPT_CONFIG_BASENAMES:
        return {alias for alias in aliases if alias}
    if not is_probable_rescript_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
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
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    module_path = normalized_target.replace(".", "/")
    candidate_keys = [
        normalized_target,
        module_path,
        f"{module_path}.res",
        f"{module_path}.resi",
        f"src/{module_path}.res",
        f"src/{module_path}.resi",
        f"lib/{module_path}.res",
        f"lib/{module_path}.resi",
        f"test/{module_path}.res",
        f"test/{module_path}.resi",
        f"tests/{module_path}.res",
        f"tests/{module_path}.resi",
        f"examples/{module_path}.res",
        f"examples/{module_path}.resi",
    ]
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{module_path}.res",
            f"/{module_path}.res",
            f"{module_path}.resi",
            f"/{module_path}.resi",
        ],
    )


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[_Dependency, ...],
    dict[str, _ImportedSymbolBinding],
    tuple[str, ...],
]:
    stripped_text = strip_comments(text)
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    unqualified_import_targets: set[str] = set()

    for match in _OPEN_RE.finditer(stripped_text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        target_file = resolve_import(
            import_target,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "line": _line_number(stripped_text, match.start()),
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=import_target.rsplit(".", 1)[-1],
                    dependency_type="imports",
                )
            )
        import_bindings.setdefault(
            import_target,
            _ImportedSymbolBinding(alias=import_target, target_file=target_file, target_names=()),
        )
        if target_file is not None:
            unqualified_import_targets.add(target_file)

    for match in _MODULE_ALIAS_RE.finditer(stripped_text):
        alias = str(match.group("name") or "").strip()
        import_target = str(match.group("target") or "").strip()
        if not alias or not import_target:
            continue
        target_file = resolve_import(
            import_target,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "line": _line_number(stripped_text, match.start()),
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=import_target.rsplit(".", 1)[-1],
                    dependency_type="imports",
                )
            )
        import_bindings.setdefault(
            alias,
            _ImportedSymbolBinding(alias=alias, target_file=target_file, target_names=()),
        )
    return tuple(dependencies), import_bindings, tuple(sorted(unqualified_import_targets))


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies, _bindings, _targets = extract_import_bindings(
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
    if not is_probable_rescript_source(path=Path(file_path), text=text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    symbols_by_name: dict[str, list[_Symbol]] = defaultdict(list)
    for symbol in symbols:
        symbols_by_name[symbol.symbol_name].append(symbol)
    dependencies, import_bindings, unqualified_import_targets = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    stripped_text = strip_comments(text)
    lines = stripped_text.splitlines()

    def _record_reference_candidate(
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
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in _QUALIFIED_REFERENCE_RE.finditer(snippet):
            binding = import_bindings.get(str(match.group("alias") or "").strip())
            if binding is None:
                continue
            target_name = str(match.group("name") or "").strip()
            if not target_name:
                continue
            _record_reference_candidate(
                source_symbol_id=symbol.symbol_id,
                target_symbol_id=None,
                target_file=binding.target_file,
                target_names=(target_name,),
            )
        for regex in (_TYPE_REFERENCE_RE, _VALUE_REFERENCE_RE, _CALL_RE):
            for match in regex.finditer(snippet):
                target_name = str(match.group("name") or "").strip()
                if (
                    not target_name
                    or target_name == symbol.symbol_name
                    or target_name in _RESERVED_SYMBOL_NAMES
                ):
                    continue
                binding = import_bindings.get(target_name)
                if binding is not None and binding.target_file is not None:
                    target_names = binding.target_names or (target_name,)
                    _record_reference_candidate(
                        source_symbol_id=symbol.symbol_id,
                        target_symbol_id=None,
                        target_file=binding.target_file,
                        target_names=target_names,
                    )
                for target_symbol in symbols_by_name.get(target_name, ()):
                    if target_symbol.symbol_id == symbol.symbol_id:
                        continue
                    _record_reference_candidate(
                        source_symbol_id=symbol.symbol_id,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=file_path,
                        target_names=(target_symbol.symbol_name,),
                    )
                for target_file in unqualified_import_targets:
                    _record_reference_candidate(
                        source_symbol_id=symbol.symbol_id,
                        target_symbol_id=None,
                        target_file=target_file,
                        target_names=(target_name,),
                    )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

