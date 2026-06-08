from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    vbscript_primitives as repository_vbscript_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_vbscript_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_vbscript_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_vbscript_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_vbscript_primitives._KNOWN_SUFFIXES
_SET_NEW_BINDING_RE = repository_vbscript_primitives._SET_NEW_BINDING_RE
_NEW_REFERENCE_RE = repository_vbscript_primitives._NEW_REFERENCE_RE
_QUALIFIED_REFERENCE_RE = repository_vbscript_primitives._QUALIFIED_REFERENCE_RE
_CALL_RE = repository_vbscript_primitives._CALL_RE
_CALL_STATEMENT_RE = repository_vbscript_primitives._CALL_STATEMENT_RE
_RESERVED_SYMBOL_NAMES = repository_vbscript_primitives._RESERVED_SYMBOL_NAMES
_BUILTIN_OBJECT_NAMES = repository_vbscript_primitives._BUILTIN_OBJECT_NAMES
_CollectedSymbol = repository_vbscript_primitives._CollectedSymbol

is_probable_vbscript_source = repository_vbscript_primitives.is_probable_vbscript_source
_normalize_target = repository_vbscript_primitives._normalize_target
_script_units_for_text = repository_vbscript_primitives._script_units_for_text
import_targets_for_text = repository_vbscript_primitives.import_targets_for_text
_iter_declared_symbols = repository_vbscript_primitives._iter_declared_symbols
_collect_symbols_for_unit = repository_vbscript_primitives._collect_symbols_for_unit


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {file_path, path.stem}
    without_suffix_path = str(path.with_suffix(""))
    aliases.add(without_suffix_path)
    aliases.add(without_suffix_path.replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_vbscript_source(path=Path(file_path), text=text):
        return aliases
    for unit_index, unit in enumerate(_script_units_for_text(path=path, text=text)):
        for collected_symbol in _collect_symbols_for_unit(
            file_path=file_path,
            unit_text=unit.text,
            unit_start_line=unit.start_line,
            unit_index=unit_index,
            stable_identifier=stable_identifier,
        ):
            aliases.add(collected_symbol.symbol.symbol_name)
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_target(import_target)
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    candidate_keys: list[str] = [normalized_target]
    if "/" in normalized_target or "\\" in normalized_target or normalized_target.startswith("."):
        relative_base = normalize_repository_relative_path(str(current_dir / normalized_target))
        if relative_base:
            candidate_keys.extend(
                (
                    relative_base,
                    f"{relative_base}.vbs",
                    f"{relative_base}.vbe",
                    f"{relative_base}.wsf",
                )
            )
    else:
        candidate_keys.extend(
            (
                f"{normalized_target}.vbs",
                f"{normalized_target}.vbe",
                f"{normalized_target}.wsf",
            )
        )
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    stem = PurePosixPath(normalized_target).stem
    if not stem:
        return None
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"/{stem}.vbs",
            f"/{stem}.vbe",
            f"/{stem}.wsf",
        ],
    )


def _resolve_symbol_target(
    *,
    symbol_name: str,
    current_file: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_name = _normalize_target(symbol_name)
    if not normalized_name:
        return None
    for candidate_key in (
        normalized_name,
        f"{normalized_name}.vbs",
        f"{normalized_name}.vbe",
        f"{normalized_name}.wsf",
    ):
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"/{normalized_name}.vbs",
            f"/{normalized_name}.vbe",
            f"/{normalized_name}.wsf",
        ],
    )


def _variable_bindings_for_text(text: str) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for match in _SET_NEW_BINDING_RE.finditer(text):
        alias = _normalize_target(match.group("alias") or "").lower()
        target = _normalize_target(match.group("target") or "")
        if alias and target and target.lower() not in _RESERVED_SYMBOL_NAMES:
            bindings[alias] = target
    return bindings


def _local_declared_symbol_names(text: str) -> set[str]:
    return {symbol_name.lower() for _, symbol_name, _ in _iter_declared_symbols(text)}


def _iter_reference_matches(
    *,
    text: str,
    file_path: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
):
    local_symbol_names = _local_declared_symbol_names(text)
    variable_bindings = _variable_bindings_for_text(text)
    seen: set[tuple[str, tuple[str, ...], int]] = set()

    def _emit(
        target_file: str | None,
        target_names: tuple[str, ...],
        line_offset: int,
    ):
        if target_file is None or target_file == file_path:
            return ()
        key = (target_file, target_names, line_offset)
        if key in seen:
            return ()
        seen.add(key)
        return (key,)

    for match in _NEW_REFERENCE_RE.finditer(text):
        target_name = _normalize_target(match.group("target") or "")
        if not target_name or target_name.lower() in _RESERVED_SYMBOL_NAMES:
            continue
        yield from _emit(
            _resolve_symbol_target(
                symbol_name=target_name,
                current_file=file_path,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            ),
            (target_name,),
            match.start(),
        )
    for match in _QUALIFIED_REFERENCE_RE.finditer(text):
        alias = _normalize_target(match.group("alias") or "")
        target_name = _normalize_target(match.group("name") or "")
        if not alias or not target_name or alias.lower() in _BUILTIN_OBJECT_NAMES:
            continue
        target_type = variable_bindings.get(alias.lower(), alias)
        yield from _emit(
            _resolve_symbol_target(
                symbol_name=target_type,
                current_file=file_path,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            ),
            (target_name,),
            match.start(),
        )
    for pattern in (_CALL_RE, _CALL_STATEMENT_RE):
        for match in pattern.finditer(text):
            target_name = _normalize_target(match.group("name") or "")
            if (
                not target_name
                or target_name.lower() in _RESERVED_SYMBOL_NAMES
                or target_name.lower() in local_symbol_names
            ):
                continue
            yield from _emit(
                _resolve_symbol_target(
                    symbol_name=target_name,
                    current_file=file_path,
                    module_index=module_index,
                    resolve_suffix_match=resolve_suffix_match,
                ),
                (target_name,),
                match.start(),
            )


def _register_dependency(
    *,
    file_path: str,
    target_file: str | None,
    target_symbol: str | None,
    dependency_type: str,
    line_offset: int,
    target_hint: str,
    stable_identifier: StableIdentifier,
    dependency_keys: set[tuple[str | None, str | None, str]],
    dependencies: list[_Dependency],
) -> None:
    dependency_key = (target_file, target_symbol, dependency_type)
    if dependency_key in dependency_keys:
        return
    dependency_keys.add(dependency_key)
    dependencies.append(
        _Dependency(
            dependency_edge_id=stable_identifier(
                "dep",
                {
                    "file_path": file_path,
                    "target": target_hint,
                    "symbol": target_symbol,
                    "kind": dependency_type,
                    "line": line_offset,
                },
            ),
            source_file=file_path,
            target_file=target_file,
            target_symbol=target_symbol,
            dependency_type=dependency_type,
        )
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
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str | None, str]] = set()
    for import_target in import_targets_for_text(path=path, text=text):
        _register_dependency(
            file_path=file_path,
            target_file=resolve_import(
                current_file=file_path,
                import_target=import_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            ),
            target_symbol=None,
            dependency_type="imports",
            line_offset=text.find(import_target),
            target_hint=import_target,
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )
    for unit in _script_units_for_text(path=path, text=text):
        for target_file, target_names, line_offset in _iter_reference_matches(
            text=unit.text,
            file_path=file_path,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        ):
            _register_dependency(
                file_path=file_path,
                target_file=target_file,
                target_symbol=target_names[0],
                dependency_type="references",
                line_offset=line_offset,
                target_hint=target_names[0],
                stable_identifier=stable_identifier,
                dependency_keys=dependency_keys,
                dependencies=dependencies,
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
) -> tuple[
    tuple[repository_vbscript_primitives._Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    path = PurePosixPath(file_path)
    units = _script_units_for_text(path=path, text=text)
    collected_symbols: list[_CollectedSymbol] = []
    for unit_index, unit in enumerate(units):
        collected_symbols.extend(
            _collect_symbols_for_unit(
                file_path=file_path,
                unit_text=unit.text,
                unit_start_line=unit.start_line,
                unit_index=unit_index,
                stable_identifier=stable_identifier,
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
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for collected_symbol in collected_symbols:
        unit = units[collected_symbol.unit_index]
        unit_lines = unit.text.splitlines()
        snippet = "\n".join(
            unit_lines[
                max(collected_symbol.local_start_line - 1, 0) : max(
                    collected_symbol.local_end_line,
                    collected_symbol.local_start_line,
                )
            ]
        )
        for target_file, target_names, _ in _iter_reference_matches(
            text=snippet,
            file_path=file_path,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        ):
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": collected_symbol.symbol.symbol_id,
                    "target_file": target_file,
                    "target_names": target_names,
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                _SymbolReferenceCandidate(
                    reference_edge_id=edge_id,
                    source_symbol_id=collected_symbol.symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=target_names,
                    reference_type="references_symbol",
                ),
            )
    return (
        tuple(collected_symbol.symbol for collected_symbol in collected_symbols),
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
