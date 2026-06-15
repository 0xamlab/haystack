from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    coffeescript_primitives as repository_coffeescript_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_coffeescript_primitives.StableIdentifier
NormalizeRepositoryRelativePath = (
    repository_coffeescript_primitives.NormalizeRepositoryRelativePath
)
ResolveSuffixMatch = repository_coffeescript_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_coffeescript_primitives._KNOWN_SUFFIXES
_CLASS_DECL_RE = repository_coffeescript_primitives._CLASS_DECL_RE
_REQUIRE_ASSIGN_RE = repository_coffeescript_primitives._REQUIRE_ASSIGN_RE
_REQUIRE_SIDE_EFFECT_RE = repository_coffeescript_primitives._REQUIRE_SIDE_EFFECT_RE
_IMPORT_FROM_RE = repository_coffeescript_primitives._IMPORT_FROM_RE
_IMPORT_SIDE_EFFECT_RE = repository_coffeescript_primitives._IMPORT_SIDE_EFFECT_RE
_QUALIFIED_CALL_RE = repository_coffeescript_primitives._QUALIFIED_CALL_RE
_BARE_CALL_RE = repository_coffeescript_primitives._BARE_CALL_RE
_NEW_RE = repository_coffeescript_primitives._NEW_RE
_INSTANCE_ASSIGN_RE = repository_coffeescript_primitives._INSTANCE_ASSIGN_RE
_RESERVED_SYMBOL_NAMES = repository_coffeescript_primitives._RESERVED_SYMBOL_NAMES
_CollectedSymbol = repository_coffeescript_primitives._CollectedSymbol

_normalize_source_text = repository_coffeescript_primitives._normalize_source_text
_normalize_import_target = repository_coffeescript_primitives._normalize_import_target
_line_number = repository_coffeescript_primitives._line_number
collect_symbol_entries = repository_coffeescript_primitives.collect_symbol_entries
has_coffeescript_path_hints = repository_coffeescript_primitives.has_coffeescript_path_hints
has_coffeescript_shebang = repository_coffeescript_primitives.has_coffeescript_shebang
import_targets_for_text = repository_coffeescript_primitives.import_targets_for_text
is_probable_coffeescript_source = (
    repository_coffeescript_primitives.is_probable_coffeescript_source
)
module_symbol_name = repository_coffeescript_primitives.module_symbol_name
normalize_identifier = repository_coffeescript_primitives.normalize_identifier
strip_comments = repository_coffeescript_primitives.strip_comments
_raw_symbol_entries = repository_coffeescript_primitives._raw_symbol_entries


def _without_suffix_aliases(path: PurePosixPath) -> set[str]:
    aliases = {path.stem or path.name}
    without_suffix_path = str(path.with_suffix(""))
    if without_suffix_path:
        aliases.add(without_suffix_path)
        aliases.add(without_suffix_path.replace("/", "."))
    if path.suffix.lower() == ".litcoffee":
        litless_path = without_suffix_path.removesuffix(".lit")
        if litless_path:
            aliases.add(litless_path)
            aliases.add(litless_path.replace("/", "."))
            aliases.add(PurePosixPath(litless_path).name)
    return {alias for alias in aliases if alias}


def _source_text_for_analysis(*, file_path: str, text: str) -> str:
    normalized_text = _normalize_source_text(path=Path(file_path), text=text)
    return strip_comments(normalized_text)


def _parse_object_binding_names(body: str) -> tuple[tuple[str, str], ...]:
    bindings: list[tuple[str, str]] = []
    for raw_segment in str(body or "").split(","):
        normalized_segment = str(raw_segment or "").strip()
        if not normalized_segment:
            continue
        if ":" in normalized_segment:
            target_name, alias_name = normalized_segment.split(":", 1)
            target_name = normalize_identifier(target_name)
            alias_name = normalize_identifier(alias_name)
        else:
            target_name = normalize_identifier(normalized_segment)
            alias_name = target_name
        if not target_name or not alias_name:
            continue
        bindings.append((alias_name, target_name))
    return tuple(bindings)


def _parse_import_clause_bindings(clause: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    normalized_clause = str(clause or "").strip()
    if not normalized_clause:
        return ()
    if normalized_clause.startswith("* as "):
        alias_name = normalize_identifier(normalized_clause.removeprefix("* as "))
        return ((alias_name, ()),) if alias_name else ()
    bindings: list[tuple[str, tuple[str, ...]]] = []
    default_clause = normalized_clause
    named_clause = ""
    if "{" in normalized_clause and "}" in normalized_clause:
        brace_start = normalized_clause.index("{")
        brace_end = normalized_clause.rindex("}")
        default_clause = normalized_clause[:brace_start].rstrip(" ,")
        named_clause = normalized_clause[brace_start + 1 : brace_end]
    default_alias = normalize_identifier(default_clause.rstrip(","))
    if default_alias:
        bindings.append((default_alias, (default_alias,)))
    for raw_segment in named_clause.split(","):
        normalized_segment = normalize_identifier(raw_segment)
        if not normalized_segment:
            continue
        if " as " in normalized_segment:
            target_name, alias_name = normalized_segment.split(" as ", 1)
            target_name = normalize_identifier(target_name)
            alias_name = normalize_identifier(alias_name)
        else:
            target_name = normalized_segment
            alias_name = normalized_segment
        if not target_name or not alias_name:
            continue
        bindings.append((alias_name, (target_name,)))
    return tuple(bindings)


def _class_relation_targets(text: str) -> dict[int, tuple[str, ...]]:
    relation_targets: dict[int, tuple[str, ...]] = {}
    for match in _CLASS_DECL_RE.finditer(text):
        extends_target = normalize_identifier(match.group("extends") or "")
        if not extends_target:
            continue
        relation_targets[_line_number(text, match.start())] = (extends_target,)
    return relation_targets


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES and path.name.lower() != "cakefile":
        return set()
    aliases = {
        file_path,
        file_path.lower(),
        *_without_suffix_aliases(path),
    }
    aliases.update(alias.lower() for alias in tuple(aliases))
    loaded_text = text
    if loaded_text is None:
        try:
            loaded_text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return {alias for alias in aliases if alias}
    candidate_stripped_text = (
        stripped_text
        if stripped_text is not None
        else _source_text_for_analysis(file_path=file_path, text=loaded_text)
    )
    if not is_probable_coffeescript_source(path=Path(file_path), text=loaded_text):
        return {alias for alias in aliases if alias}
    module_name = module_symbol_name(file_path)
    for symbol_name, symbol_kind, _start_line, _end_line, _parent_name, _signature in _raw_symbol_entries(
        file_path=file_path,
        text=loaded_text,
        stripped_text=candidate_stripped_text,
    ):
        if symbol_kind == "module":
            continue
        aliases.add(symbol_name)
        aliases.add(symbol_name.lower())
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
            aliases.add(f"{module_name.lower()}.{symbol_name.lower()}")
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_import_target(import_target)
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    suffixes = tuple(sorted(_KNOWN_SUFFIXES))
    raw_candidates = [normalized_target]
    if normalized_target.startswith(".") or "/" in normalized_target:
        raw_candidates.append(str(current_dir / normalized_target))
    if PurePosixPath(normalized_target).suffix.lower() not in _KNOWN_SUFFIXES:
        for suffix in suffixes:
            raw_candidates.append(f"{normalized_target}{suffix}")
            raw_candidates.append(f"{normalized_target}/index{suffix}")
            if normalized_target.startswith(".") or "/" in normalized_target:
                raw_candidates.append(str(current_dir / f"{normalized_target}{suffix}"))
                raw_candidates.append(str(current_dir / f"{normalized_target}/index{suffix}"))
    candidate_keys: list[str] = []
    seen_candidates: set[str] = set()
    for raw_candidate in raw_candidates:
        normalized_candidate = normalize_repository_relative_path(raw_candidate)
        if not normalized_candidate or normalized_candidate in seen_candidates:
            continue
        seen_candidates.add(normalized_candidate)
        candidate_keys.append(normalized_candidate)
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    basename = PurePosixPath(normalized_target).name
    lookup_suffixes = [*candidate_keys, basename]
    if PurePosixPath(normalized_target).suffix.lower() not in _KNOWN_SUFFIXES and basename:
        lookup_suffixes.extend(f"{basename}{suffix}" for suffix in suffixes)
        lookup_suffixes.extend(f"{basename}/index{suffix}" for suffix in suffixes)
    return resolve_suffix_match(module_index=module_index, suffixes=lookup_suffixes)


def _source_symbol_id_for_line(
    *,
    line_number: int,
    collected_symbols: tuple[_CollectedSymbol, ...],
) -> str | None:
    matching_symbols = [
        collected_symbol
        for collected_symbol in collected_symbols
        if collected_symbol.local_start_line <= line_number <= collected_symbol.local_end_line
    ]
    if not matching_symbols:
        return None
    ranked_symbols = sorted(
        matching_symbols,
        key=lambda item: (
            0 if item.symbol.symbol_kind != "module" else 1,
            (item.local_end_line - item.local_start_line),
            item.local_start_line,
            item.symbol.symbol_id,
        ),
    )
    return ranked_symbols[0].symbol.symbol_id


def _import_bindings_for_text(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, tuple[str | None, tuple[str, ...]]]:
    bindings: dict[str, tuple[str | None, tuple[str, ...]]] = {}
    for match in _REQUIRE_ASSIGN_RE.finditer(text):
        import_target = _normalize_import_target(str(match.group("target") or ""))
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        object_body = str(match.group("object") or "").strip()
        if object_body:
            for alias_name, target_name in _parse_object_binding_names(
                object_body.strip("{}")
            ):
                bindings[alias_name] = (target_file, (target_name,))
            continue
        alias_name = normalize_identifier(match.group("alias") or "")
        if alias_name:
            bindings[alias_name] = (target_file, ())
    for match in _IMPORT_FROM_RE.finditer(text):
        import_target = _normalize_import_target(str(match.group("target") or ""))
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        for alias_name, target_names in _parse_import_clause_bindings(match.group("clause") or ""):
            bindings[alias_name] = (target_file, target_names)
    return bindings


def _instance_type_bindings_for_text(
    text: str,
) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for match in _INSTANCE_ASSIGN_RE.finditer(text):
        alias_name = normalize_identifier(match.group("alias") or "")
        type_name = normalize_identifier(match.group("name") or "")
        if alias_name and type_name:
            bindings[alias_name] = type_name
    return bindings


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
                    "line": line_number,
                    "type": dependency_type,
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
    imported_bindings: dict[str, tuple[str | None, tuple[str, ...]]] | None = None,
    instance_bindings: dict[str, str] | None = None,
) -> tuple[_Dependency, ...]:
    if not is_probable_coffeescript_source(path=Path(file_path), text=text):
        return ()
    candidate_stripped_text = (
        stripped_text
        if stripped_text is not None
        else _source_text_for_analysis(file_path=file_path, text=text)
    )
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str | None, str]] = set()
    resolved_imported_bindings = (
        imported_bindings
        if imported_bindings is not None
        else _import_bindings_for_text(
            file_path=file_path,
            text=candidate_stripped_text,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
    )
    for import_target in import_targets_for_text(candidate_stripped_text):
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
            line_number=1,
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )
    for line_number, relation_targets in sorted(_class_relation_targets(candidate_stripped_text).items()):
        for target_name in relation_targets:
            target_binding = resolved_imported_bindings.get(target_name)
            _register_dependency(
                file_path=file_path,
                target_file=target_binding[0] if target_binding else None,
                target_symbol=target_name,
                dependency_type="imports",
                target_hint=target_name,
                line_number=line_number,
                stable_identifier=stable_identifier,
                dependency_keys=dependency_keys,
                dependencies=dependencies,
            )
    resolved_instance_bindings = (
        instance_bindings
        if instance_bindings is not None
        else _instance_type_bindings_for_text(candidate_stripped_text)
    )
    for match in _NEW_RE.finditer(candidate_stripped_text):
        target_name = normalize_identifier(match.group("name") or "")
        if not target_name:
            continue
        target_binding = resolved_imported_bindings.get(target_name)
        _register_dependency(
            file_path=file_path,
            target_file=target_binding[0] if target_binding else None,
            target_symbol=target_name,
            dependency_type="references",
            target_hint=target_name,
            line_number=_line_number(candidate_stripped_text, match.start()),
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )
    for match in _QUALIFIED_CALL_RE.finditer(candidate_stripped_text):
        owner_name = normalize_identifier(match.group("owner") or "")
        method_name = normalize_identifier(match.group("name") or "")
        if not owner_name or not method_name:
            continue
        owner_binding = resolved_imported_bindings.get(owner_name)
        if owner_binding is None and owner_name in resolved_instance_bindings:
            owner_binding = resolved_imported_bindings.get(resolved_instance_bindings[owner_name])
        if owner_binding is None:
            continue
        _register_dependency(
            file_path=file_path,
            target_file=owner_binding[0],
            target_symbol=method_name,
            dependency_type="references",
            target_hint=f"{owner_name}.{method_name}",
            line_number=_line_number(candidate_stripped_text, match.start()),
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )
    for match in _BARE_CALL_RE.finditer(candidate_stripped_text):
        target_name = normalize_identifier(match.group("name") or "")
        if not target_name or target_name in _RESERVED_SYMBOL_NAMES:
            continue
        target_binding = resolved_imported_bindings.get(target_name)
        if target_binding is None or not target_binding[1]:
            continue
        _register_dependency(
            file_path=file_path,
            target_file=target_binding[0],
            target_symbol=target_binding[1][0],
            dependency_type="references",
            target_hint=target_name,
            line_number=_line_number(candidate_stripped_text, match.start()),
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )
    return tuple(dependencies)


def _register_reference(
    *,
    source_symbol_id: str,
    source_file: str,
    target_file: str | None,
    target_names: tuple[str, ...],
    line_number: int,
    stable_identifier: StableIdentifier,
    seen_reference_keys: set[tuple[str, str | None, tuple[str, ...]]],
    symbol_references: list[_SymbolReferenceCandidate],
) -> None:
    reference_key = (source_symbol_id, target_file, target_names)
    if reference_key in seen_reference_keys:
        return
    seen_reference_keys.add(reference_key)
    symbol_references.append(
        _SymbolReferenceCandidate(
            reference_edge_id=stable_identifier(
                "ref",
                {
                    "source_symbol_id": source_symbol_id,
                    "target_file": target_file,
                    "target_names": target_names,
                    "line": line_number,
                },
            ),
            source_symbol_id=source_symbol_id,
            source_file=source_file,
            target_symbol_id=None,
            target_file=target_file,
            target_names=target_names,
            reference_type="references_symbol",
        )
    )


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
    if not is_probable_coffeescript_source(path=Path(file_path), text=text):
        return (), (), ()
    stripped_text = _source_text_for_analysis(file_path=file_path, text=text)
    collected_symbols = collect_symbol_entries(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    imported_bindings = _import_bindings_for_text(
        file_path=file_path,
        text=stripped_text,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    instance_bindings = _instance_type_bindings_for_text(stripped_text)
    dependencies = parse_dependencies_only(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
        imported_bindings=imported_bindings,
        instance_bindings=instance_bindings,
    )
    local_callable_names = {
        collected_symbol.symbol.symbol_name
        for collected_symbol in collected_symbols
        if collected_symbol.symbol.symbol_kind in {"function", "method"}
    }
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str | None, tuple[str, ...]]] = set()

    for match in _QUALIFIED_CALL_RE.finditer(stripped_text):
        owner_name = normalize_identifier(match.group("owner") or "")
        method_name = normalize_identifier(match.group("name") or "")
        if not owner_name or not method_name:
            continue
        owner_binding = imported_bindings.get(owner_name)
        if owner_binding is None and owner_name in instance_bindings:
            owner_binding = imported_bindings.get(instance_bindings[owner_name])
        if owner_binding is None:
            continue
        source_symbol_id = _source_symbol_id_for_line(
            line_number=_line_number(stripped_text, match.start()),
            collected_symbols=collected_symbols,
        )
        if source_symbol_id is None:
            continue
        _register_reference(
            source_symbol_id=source_symbol_id,
            source_file=file_path,
            target_file=owner_binding[0],
            target_names=(method_name,),
            line_number=_line_number(stripped_text, match.start()),
            stable_identifier=stable_identifier,
            seen_reference_keys=seen_reference_keys,
            symbol_references=symbol_references,
        )

    for match in _BARE_CALL_RE.finditer(stripped_text):
        target_name = normalize_identifier(match.group("name") or "")
        if (
            not target_name
            or target_name in _RESERVED_SYMBOL_NAMES
            or target_name in local_callable_names
        ):
            continue
        target_binding = imported_bindings.get(target_name)
        if target_binding is None or not target_binding[1]:
            continue
        source_symbol_id = _source_symbol_id_for_line(
            line_number=_line_number(stripped_text, match.start()),
            collected_symbols=collected_symbols,
        )
        if source_symbol_id is None:
            continue
        _register_reference(
            source_symbol_id=source_symbol_id,
            source_file=file_path,
            target_file=target_binding[0],
            target_names=target_binding[1],
            line_number=_line_number(stripped_text, match.start()),
            stable_identifier=stable_identifier,
            seen_reference_keys=seen_reference_keys,
            symbol_references=symbol_references,
        )

    for match in _NEW_RE.finditer(stripped_text):
        target_name = normalize_identifier(match.group("name") or "")
        if not target_name:
            continue
        target_binding = imported_bindings.get(target_name)
        if target_binding is None:
            continue
        source_symbol_id = _source_symbol_id_for_line(
            line_number=_line_number(stripped_text, match.start()),
            collected_symbols=collected_symbols,
        )
        if source_symbol_id is None:
            continue
        _register_reference(
            source_symbol_id=source_symbol_id,
            source_file=file_path,
            target_file=target_binding[0],
            target_names=target_binding[1] or (target_name,),
            line_number=_line_number(stripped_text, match.start()),
            stable_identifier=stable_identifier,
            seen_reference_keys=seen_reference_keys,
            symbol_references=symbol_references,
        )

    return symbols, dependencies, tuple(symbol_references)
