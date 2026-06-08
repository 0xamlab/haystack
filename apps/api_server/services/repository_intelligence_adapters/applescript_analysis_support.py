from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    applescript_primitives as repository_applescript_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_applescript_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_applescript_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_applescript_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_applescript_primitives._KNOWN_SUFFIXES
_SET_LOAD_BINDING_RE = repository_applescript_primitives._SET_LOAD_BINDING_RE
_PROPERTY_LOAD_BINDING_RE = repository_applescript_primitives._PROPERTY_LOAD_BINDING_RE
_CollectedSymbol = repository_applescript_primitives._CollectedSymbol
_line_number = repository_applescript_primitives._line_number
collect_symbol_entries = repository_applescript_primitives.collect_symbol_entries
has_applescript_path_hints = repository_applescript_primitives.has_applescript_path_hints
import_targets_for_text = repository_applescript_primitives.import_targets_for_text
is_probable_applescript_source = repository_applescript_primitives.is_probable_applescript_source
normalize_identifier = repository_applescript_primitives.normalize_identifier
strip_comments = repository_applescript_primitives.strip_comments
_module_symbol_name = repository_applescript_primitives._module_symbol_name
_normalize_import_target = repository_applescript_primitives._normalize_import_target

_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*'s\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
_OF_REFERENCE_RE = re.compile(
    r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+of\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
_TELL_SCRIPT_CALL_RE = re.compile(
    r"\btell\s+script\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s+to\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
_RUN_SCRIPT_RE = re.compile(
    r"\brun\s+script\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
_MY_CALL_RE = re.compile(
    r"\bmy\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b(?=\s*(?:\(|$))",
    re.IGNORECASE,
)
_BARE_CALL_RE = re.compile(
    r"(?m)^\s*(?:return\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b(?=\s*\()",
    re.IGNORECASE,
)
_RESERVED_REFERENCE_NAMES = (
    repository_applescript_primitives._RESERVED_SYMBOL_NAMES
    | frozenset({"activate", "beep", "close", "count", "display", "open", "quit"})
)


def _without_suffix_aliases(path: PurePosixPath) -> set[str]:
    aliases = {path.stem or path.name}
    without_suffix_path = str(path.with_suffix(""))
    if without_suffix_path:
        aliases.add(without_suffix_path)
        aliases.add(without_suffix_path.replace("/", "."))
    return {alias for alias in aliases if alias}


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {file_path, file_path.lower(), *_without_suffix_aliases(path)}
    aliases.update(alias.lower() for alias in tuple(aliases))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    if not is_probable_applescript_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    module_name = _module_symbol_name(file_path)
    for collected_symbol in collect_symbol_entries(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        if collected_symbol.symbol.symbol_kind == "module":
            continue
        symbol_name = collected_symbol.symbol.symbol_name
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
    if "/" in normalized_target or normalized_target.startswith("."):
        raw_candidates.append(str(current_dir / normalized_target))
    if PurePosixPath(normalized_target).suffix.lower() not in _KNOWN_SUFFIXES:
        raw_candidates.extend(f"{normalized_target}{suffix}" for suffix in suffixes)
        if "/" in normalized_target or normalized_target.startswith("."):
            raw_candidates.extend(
                str(current_dir / f"{normalized_target}{suffix}") for suffix in suffixes
            )
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
    return resolve_suffix_match(module_index=module_index, suffixes=lookup_suffixes)


def _resolve_symbol_target(
    *,
    symbol_name: str,
    current_file: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_name = normalize_identifier(symbol_name)
    if not normalized_name:
        return None
    suffixes = tuple(sorted(_KNOWN_SUFFIXES))
    candidate_keys: list[str] = [
        normalized_name,
        normalized_name.lower(),
    ]
    for suffix in suffixes:
        candidate_keys.extend(
            (
                f"{normalized_name}{suffix}",
                f"{normalized_name.lower()}{suffix}",
            )
        )
    seen_keys: set[str] = set()
    ordered_keys: list[str] = []
    for candidate_key in candidate_keys:
        if not candidate_key or candidate_key in seen_keys:
            continue
        seen_keys.add(candidate_key)
        ordered_keys.append(candidate_key)
    for candidate_key in ordered_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"/{normalized_name}",
            f"/{normalized_name.lower()}",
            *(f"/{normalized_name}{suffix}" for suffix in suffixes),
            *(f"/{normalized_name.lower()}{suffix}" for suffix in suffixes),
        ],
    )


def _script_bindings_for_text(
    *,
    text: str,
    file_path: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, str]:
    bindings: dict[str, str] = {}
    stripped_text = strip_comments(text)
    for pattern in (_PROPERTY_LOAD_BINDING_RE, _SET_LOAD_BINDING_RE):
        for match in pattern.finditer(stripped_text):
            alias_name = normalize_identifier(match.group("alias") or "").lower()
            import_target = normalize_identifier(match.group("target") or "")
            if not alias_name:
                continue
            target_file = resolve_import(
                current_file=file_path,
                import_target=import_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if target_file is not None:
                bindings[alias_name] = target_file
    return bindings


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


def _local_handler_names(collected_symbols: tuple[_CollectedSymbol, ...]) -> set[str]:
    return {
        collected_symbol.symbol.symbol_name.lower()
        for collected_symbol in collected_symbols
        if collected_symbol.symbol.symbol_kind == "function"
    }


def _is_operational_reference_name(symbol_name: str) -> bool:
    normalized_name = normalize_identifier(symbol_name)
    if not normalized_name:
        return False
    return normalized_name.lower() not in _RESERVED_REFERENCE_NAMES


def _register_dependency(
    *,
    file_path: str,
    import_target: str,
    target_file: str | None,
    stable_identifier: StableIdentifier,
    dependency_keys: set[tuple[str | None, str | None, str]],
    dependencies: list[_Dependency],
) -> None:
    dependency_key = (target_file, None, "imports")
    if dependency_key in dependency_keys:
        return
    dependency_keys.add(dependency_key)
    dependencies.append(
        _Dependency(
            dependency_edge_id=stable_identifier(
                "dep",
                {
                    "file_path": file_path,
                    "target": import_target,
                    "kind": "imports",
                },
            ),
            source_file=file_path,
            target_file=target_file,
            target_symbol=None,
            dependency_type="imports",
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
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str | None, str]] = set()
    for import_target in import_targets_for_text(text):
        _register_dependency(
            file_path=file_path,
            import_target=import_target,
            target_file=resolve_import(
                current_file=file_path,
                import_target=import_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            ),
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
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES or not is_probable_applescript_source(
        path=Path(file_path),
        text=text,
    ):
        return (), (), ()
    stripped_text = strip_comments(text)
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    collected_symbols = collect_symbol_entries(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    local_handler_names = _local_handler_names(collected_symbols)
    declaration_lines = {
        (collected_symbol.local_start_line, collected_symbol.symbol.symbol_name.lower())
        for collected_symbol in collected_symbols
        if collected_symbol.symbol.symbol_kind != "module"
    }
    imported_target_files = tuple(
        sorted(
            {
                dependency.target_file
                for dependency in dependencies
                if dependency.target_file and dependency.target_file != file_path
            }
        )
    )
    script_bindings = _script_bindings_for_text(
        text=text,
        file_path=file_path,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    seen_reference_keys: set[tuple[str, str | None, tuple[str, ...]]] = set()
    symbol_references: list[_SymbolReferenceCandidate] = []

    def _register_reference_for_match(
        *,
        target_file: str | None,
        target_names: tuple[str, ...],
        offset: int,
    ) -> None:
        line_number = _line_number(stripped_text, offset)
        source_symbol_id = _source_symbol_id_for_line(
            line_number=line_number,
            collected_symbols=collected_symbols,
        )
        if source_symbol_id is None:
            return
        _register_reference(
            source_symbol_id=source_symbol_id,
            source_file=file_path,
            target_file=target_file,
            target_names=target_names,
            line_number=line_number,
            stable_identifier=stable_identifier,
            seen_reference_keys=seen_reference_keys,
            symbol_references=symbol_references,
        )

    for pattern in (_QUALIFIED_REFERENCE_RE, _OF_REFERENCE_RE, _TELL_SCRIPT_CALL_RE):
        for match in pattern.finditer(stripped_text):
            alias_name = normalize_identifier(match.group("alias") or "").lower()
            reference_name = normalize_identifier(match.group("name") or "")
            if not alias_name or not _is_operational_reference_name(reference_name):
                continue
            target_file = script_bindings.get(alias_name)
            if target_file is None:
                target_file = _resolve_symbol_target(
                    symbol_name=alias_name,
                    current_file=file_path,
                    module_index=module_index,
                    resolve_suffix_match=resolve_suffix_match,
                )
            if target_file is None:
                continue
            _register_reference_for_match(
                target_file=target_file,
                target_names=(reference_name,),
                offset=match.start(),
            )

    for match in _RUN_SCRIPT_RE.finditer(stripped_text):
        alias_name = normalize_identifier(match.group("alias") or "").lower()
        if not alias_name:
            continue
        target_file = script_bindings.get(alias_name)
        if target_file is None:
            target_file = _resolve_symbol_target(
                symbol_name=alias_name,
                current_file=file_path,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
        if target_file is None:
            continue
        _register_reference_for_match(
            target_file=target_file,
            target_names=(PurePosixPath(target_file).stem,),
            offset=match.start(),
        )

    for pattern in (_MY_CALL_RE, _BARE_CALL_RE):
        for match in pattern.finditer(stripped_text):
            reference_name = normalize_identifier(match.group("name") or "")
            if not _is_operational_reference_name(reference_name):
                continue
            line_number = _line_number(stripped_text, match.start())
            if (line_number, reference_name.lower()) in declaration_lines:
                continue
            target_file: str | None = None
            if reference_name.lower() in local_handler_names:
                target_file = file_path
            else:
                target_file = _resolve_symbol_target(
                    symbol_name=reference_name,
                    current_file=file_path,
                    module_index=module_index,
                    resolve_suffix_match=resolve_suffix_match,
                )
            if target_file is None and len(imported_target_files) == 1:
                target_file = imported_target_files[0]
            if target_file is None:
                continue
            _register_reference_for_match(
                target_file=target_file,
                target_names=(reference_name,),
                offset=match.start(),
            )

    return symbols, dependencies, tuple(symbol_references)
