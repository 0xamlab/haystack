from __future__ import annotations

from collections import defaultdict
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    cfml_primitives as repository_cfml_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_cfml_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_cfml_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_cfml_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_cfml_primitives._KNOWN_SUFFIXES
_CollectedSymbol = repository_cfml_primitives._CollectedSymbol
_CREATE_OBJECT_BINDING_RE = repository_cfml_primitives._CREATE_OBJECT_BINDING_RE
_NEW_BINDING_RE = repository_cfml_primitives._NEW_BINDING_RE
_QUALIFIED_REFERENCE_RE = repository_cfml_primitives._QUALIFIED_REFERENCE_RE
_UNQUALIFIED_CALL_RE = repository_cfml_primitives._UNQUALIFIED_CALL_RE
_BUILTIN_QUALIFIED_ROOTS = repository_cfml_primitives._BUILTIN_QUALIFIED_ROOTS

_line_count = repository_cfml_primitives._line_count
_line_number = repository_cfml_primitives._line_number
_normalize_target = repository_cfml_primitives._normalize_target
component_name_from_path = repository_cfml_primitives.component_name_from_path
component_extends_targets = repository_cfml_primitives.component_extends_targets
declared_component_name = repository_cfml_primitives.declared_component_name
has_cfml_path_hints = repository_cfml_primitives.has_cfml_path_hints
import_targets_for_text = repository_cfml_primitives.import_targets_for_text
is_operational_reference_name = repository_cfml_primitives.is_operational_reference_name
is_probable_cfml_source = repository_cfml_primitives.is_probable_cfml_source
iter_create_object_targets = repository_cfml_primitives.iter_create_object_targets
iter_function_entries = repository_cfml_primitives.iter_function_entries
iter_new_expression_targets = repository_cfml_primitives.iter_new_expression_targets
strip_comments = repository_cfml_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    if path.suffix:
        return str(path.with_suffix(""))
    return str(path)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    component_name = declared_component_name(
        text=text,
        file_path=file_path,
        stripped_text=stripped_text,
    )
    component_kind = (
        "component"
        if PurePosixPath(file_path).suffix.lower() == ".cfc"
        else "template"
    )
    component_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": component_name,
                "symbol_kind": component_kind,
                "start_line": 1,
            },
        ),
        symbol_name=component_name,
        symbol_kind=component_kind,
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"component {component_name}" if component_name else None,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=component_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
        )
    ]
    for function_name, start_line, end_line in iter_function_entries(
        text,
        stripped_text=stripped_text,
    ):
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": function_name,
                            "symbol_kind": "function",
                            "start_line": start_line,
                        },
                    ),
                    symbol_name=function_name,
                    symbol_kind="function",
                    start_line=start_line,
                    end_line=end_line,
                    parent_symbol_id=component_symbol.symbol_id,
                    signature=f"function {function_name}()",
                ),
                local_start_line=start_line,
                local_end_line=end_line,
            )
        )
    final_line = _line_count(stripped_text)
    finalized_symbols: list[_CollectedSymbol] = []
    for index, collected_symbol in enumerate(collected_symbols):
        symbol = collected_symbol.symbol
        if symbol.symbol_kind != "function":
            finalized_symbols.append(
                _CollectedSymbol(
                    symbol=_Symbol(
                        symbol_id=symbol.symbol_id,
                        symbol_name=symbol.symbol_name,
                        symbol_kind=symbol.symbol_kind,
                        start_line=symbol.start_line,
                        end_line=final_line,
                        parent_symbol_id=symbol.parent_symbol_id,
                        signature=symbol.signature,
                    ),
                    local_start_line=1,
                    local_end_line=final_line,
                )
            )
            continue
        next_start_line = next(
            (
                candidate.local_start_line
                for candidate in collected_symbols[index + 1 :]
                if candidate.symbol.symbol_kind == "function"
            ),
            final_line + 1,
        )
        finalized_end_line = max(
            symbol.end_line,
            min(next_start_line - 1, final_line),
            symbol.start_line,
        )
        finalized_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=symbol.symbol_id,
                    symbol_name=symbol.symbol_name,
                    symbol_kind=symbol.symbol_kind,
                    start_line=symbol.start_line,
                    end_line=finalized_end_line,
                    parent_symbol_id=symbol.parent_symbol_id,
                    signature=symbol.signature,
                ),
                local_start_line=symbol.start_line,
                local_end_line=finalized_end_line,
            )
        )
    return tuple(finalized_symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        path.stem,
        _without_suffix_path(path),
        _without_suffix_path(path).replace("/", "."),
    }
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    stripped_text = strip_comments(text)
    component_name = declared_component_name(
        text=text,
        file_path=file_path,
        stripped_text=stripped_text,
    )
    if component_name:
        aliases.add(component_name)
        aliases.add(component_name.rsplit(".", 1)[-1])
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    ):
        if collected_symbol.symbol.symbol_kind != "function":
            continue
        symbol_name = collected_symbol.symbol.symbol_name
        aliases.add(symbol_name)
        if component_name:
            aliases.add(f"{component_name}.{symbol_name}")
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
    candidate_keys = [normalized_target]
    if normalized_target.startswith("/"):
        repo_root_target = normalize_repository_relative_path(normalized_target.lstrip("/"))
        if repo_root_target:
            candidate_keys.append(repo_root_target)
    else:
        relative_target = normalize_repository_relative_path(str(current_dir / normalized_target))
        if relative_target:
            candidate_keys.append(relative_target)
    if PurePosixPath(normalized_target).suffix.lower() not in _KNOWN_SUFFIXES:
        expanded_keys: list[str] = []
        for candidate_key in list(candidate_keys):
            expanded_keys.extend(f"{candidate_key}{suffix}" for suffix in sorted(_KNOWN_SUFFIXES))
        candidate_keys.extend(expanded_keys)
    seen_candidate_keys: set[str] = set()
    ordered_candidate_keys: list[str] = []
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate or normalized_candidate in seen_candidate_keys:
            continue
        seen_candidate_keys.add(normalized_candidate)
        ordered_candidate_keys.append(normalized_candidate)
    for candidate_key in ordered_candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    target_name = PurePosixPath(normalized_target).stem or normalized_target.rsplit("/", 1)[-1]
    suffixes = [
        normalized_target,
        target_name,
        f"/{target_name}.cfc",
        f"/{target_name}.cfm",
        f"/{target_name}.cfml",
    ]
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=suffixes,
    )


def _resolve_component_target(
    *,
    current_file: str,
    component_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_target(component_target).replace("/", ".")
    if not normalized_target:
        return None
    module_path = normalized_target.replace(".", "/")
    candidate_keys = [
        normalized_target,
        module_path,
        f"{module_path}.cfc",
        f"{module_path}.cfm",
        f"{module_path}.cfml",
    ]
    if "." not in normalized_target and "/" not in normalized_target:
        current_dir = PurePosixPath(current_file).parent
        for suffix in sorted(_KNOWN_SUFFIXES):
            candidate_keys.append(str(current_dir / f"{normalized_target}{suffix}"))
    seen_candidate_keys: set[str] = set()
    ordered_candidate_keys: list[str] = []
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate or normalized_candidate in seen_candidate_keys:
            continue
        seen_candidate_keys.add(normalized_candidate)
        ordered_candidate_keys.append(normalized_candidate)
    for candidate_key in ordered_candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    target_name = module_path.rsplit("/", 1)[-1]
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            normalized_target,
            module_path,
            f"{module_path}.cfc",
            f"{module_path}.cfm",
            f"{module_path}.cfml",
            f"/{target_name}.cfc",
            f"/{target_name}.cfm",
            f"/{target_name}.cfml",
        ],
    )


@repository_cfml_primitives.lru_cache(maxsize=256)
def _variable_binding_entries_for_stripped_text(
    stripped_text: str,
) -> tuple[tuple[str, str], ...]:
    bindings: dict[str, str] = {}
    for pattern in (_CREATE_OBJECT_BINDING_RE, _NEW_BINDING_RE):
        for match in pattern.finditer(stripped_text):
            alias = _normalize_target(match.group("alias") or "").lower()
            target = _normalize_target(match.group("target") or "").replace("/", ".")
            if alias and target:
                bindings[alias] = target
    return tuple(sorted(bindings.items()))


def _variable_bindings_for_text(
    text: str,
    *,
    stripped_text: str | None = None,
) -> dict[str, str]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    return dict(_variable_binding_entries_for_stripped_text(stripped_text))


def _iter_component_reference_matches(
    *,
    text: str,
    file_path: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
):
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    bindings = _variable_bindings_for_text(text, stripped_text=stripped_text)
    seen: set[tuple[str | None, tuple[str, ...], int]] = set()
    resolved_component_targets: dict[str, str | None] = {}

    def _resolve_component_target_cached(component_target: str) -> str | None:
        if component_target not in resolved_component_targets:
            resolved_component_targets[component_target] = _resolve_component_target(
                current_file=file_path,
                component_target=component_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
        return resolved_component_targets[component_target]

    def _emit(component_target: str, target_name: str | None, line_number: int):
        target_file = _resolve_component_target_cached(component_target)
        if target_file is None:
            return ()
        final_target_name = (
            target_name
            or component_target.rsplit(".", 1)[-1].rsplit("/", 1)[-1]
        )
        target_names = (final_target_name,) if final_target_name else ()
        key = (target_file, target_names, line_number)
        if key in seen:
            return ()
        seen.add(key)
        return ((target_file, target_names, line_number),)

    for extends_target in component_extends_targets(text, stripped_text=stripped_text):
        yield from _emit(extends_target, extends_target.rsplit(".", 1)[-1], 1)
    for component_target, method_name, line_number in iter_create_object_targets(
        text,
        stripped_text=stripped_text,
    ):
        yield from _emit(component_target, method_name, line_number)
    for component_target, method_name, line_number in iter_new_expression_targets(
        text,
        stripped_text=stripped_text,
    ):
        yield from _emit(component_target, method_name, line_number)
    for match in _QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        alias = _normalize_target(match.group("alias") or "")
        target_name = _normalize_target(match.group("name") or "")
        if not alias or not target_name:
            continue
        resolved_target = bindings.get(alias.lower())
        if resolved_target:
            yield from _emit(
                resolved_target,
                target_name,
                _line_number(stripped_text, match.start()),
            )
            continue
        alias_root = alias.split(".", 1)[0].lower()
        if alias_root in _BUILTIN_QUALIFIED_ROOTS:
            continue
        if _resolve_component_target_cached(alias):
            yield from _emit(
                alias,
                target_name,
                _line_number(stripped_text, match.start()),
            )


def _register_dependency(
    *,
    file_path: str,
    target_file: str | None,
    target_symbol: str | None,
    dependency_type: str,
    target_hint: str,
    line_number: int,
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
                    "line": line_number,
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
    stripped_text: str | None = None,
    import_targets: tuple[str, ...] | None = None,
    component_reference_matches: tuple[tuple[str | None, tuple[str, ...], int], ...] | None = None,
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str | None, str]] = set()
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    for import_target in (
        import_targets
        if import_targets is not None
        else import_targets_for_text(text, stripped_text=stripped_text)
    ):
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
            target_hint=import_target,
            line_number=max(1, _line_number(stripped_text, stripped_text.find(import_target))),
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )
    for target_file, target_names, line_number in (
        component_reference_matches
        if component_reference_matches is not None
        else _iter_component_reference_matches(
            text=text,
            file_path=file_path,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
            stripped_text=stripped_text,
        )
    ):
        _register_dependency(
            file_path=file_path,
            target_file=target_file,
            target_symbol=target_names[0] if target_names else None,
            dependency_type="references",
            target_hint=target_names[0] if target_names else target_file or "",
            line_number=line_number,
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
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    stripped_text = strip_comments(text)
    import_targets = import_targets_for_text(text, stripped_text=stripped_text)
    component_reference_matches = tuple(
        _iter_component_reference_matches(
            text=text,
            file_path=file_path,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
            stripped_text=stripped_text,
        )
    )
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
        import_targets=import_targets,
        component_reference_matches=component_reference_matches,
    )
    symbols_by_name: dict[str, list[_Symbol]] = defaultdict(list)
    for symbol in symbols:
        if symbol.symbol_kind != "function":
            continue
        symbols_by_name[symbol.symbol_name.lower()].append(symbol)
    declaration_line_names = {
        (symbol.start_line, symbol.symbol_name.lower())
        for symbol in symbols
        if symbol.symbol_kind == "function"
    }
    lines = stripped_text.splitlines()
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
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in _UNQUALIFIED_CALL_RE.finditer(snippet):
            target_name = _normalize_target(match.group("name") or "")
            if not is_operational_reference_name(target_name):
                continue
            line_number = symbol.start_line + _line_number(snippet, match.start()) - 1
            if (line_number, target_name.lower()) in declaration_line_names:
                continue
            for target_symbol in symbols_by_name.get(target_name.lower(), ()):
                if target_symbol.symbol_id == symbol.symbol_id:
                    continue
                _record_reference(
                    source_symbol_id=symbol.symbol_id,
                    target_symbol_id=target_symbol.symbol_id,
                    target_file=file_path,
                    target_names=(target_symbol.symbol_name,),
                )
        for target_file, target_names, line_number in component_reference_matches:
            if line_number < symbol.start_line or line_number > symbol.end_line:
                continue
            _record_reference(
                source_symbol_id=symbol.symbol_id,
                target_symbol_id=None,
                target_file=target_file,
                target_names=target_names,
            )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
