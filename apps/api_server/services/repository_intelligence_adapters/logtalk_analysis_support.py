from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    logtalk_primitives as repository_logtalk_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_logtalk_primitives.repository_prolog_primitives.StableIdentifier
ResolveSuffixMatch = repository_logtalk_primitives.repository_prolog_primitives.ResolveSuffixMatch

_KNOWN_LOGTALK_SUFFIXES = repository_logtalk_primitives._KNOWN_LOGTALK_SUFFIXES
_split_top_level_segments = repository_logtalk_primitives._split_top_level_segments
has_logtalk_path_hints = repository_logtalk_primitives.has_logtalk_path_hints
has_logtalk_markers = repository_logtalk_primitives.has_logtalk_markers
is_probable_logtalk_source = repository_logtalk_primitives.is_probable_logtalk_source
iter_symbol_entries = repository_logtalk_primitives.iter_symbol_entries
module_name_from_path = repository_logtalk_primitives.module_name_from_path
module_name_from_text = repository_logtalk_primitives.module_name_from_text
normalize_identifier = repository_logtalk_primitives.normalize_identifier
parse_load_statements = repository_logtalk_primitives.parse_load_statements
parse_reference_targets = repository_logtalk_primitives.parse_reference_targets
parse_relation_statements = repository_logtalk_primitives.parse_relation_statements
parse_uses_statements = repository_logtalk_primitives.parse_uses_statements
strip_comments = repository_logtalk_primitives.strip_comments


def _path_aliases(path: PurePosixPath) -> set[str]:
    without_suffix = str(path.with_suffix(""))
    aliases = {
        str(path),
        without_suffix,
        without_suffix.replace("/", "."),
        path.stem,
    }
    parts = list(path.with_suffix("").parts)
    if parts and parts[0].lower() in repository_logtalk_primitives._LOGTALK_SOURCE_ROOTS:
        parts = parts[1:]
    if parts:
        dotted = ".".join(parts)
        aliases.add(dotted)
        aliases.add(parts[-1])
    return {alias for alias in aliases if alias}


def _candidate_import_keys(import_target: str, *, current_file: str) -> tuple[str, ...]:
    normalized_target = normalize_identifier(import_target)
    if not normalized_target:
        return ()
    current_parent = PurePosixPath(current_file).parent
    raw_candidates = [normalized_target.replace(".", "/")]
    raw_candidates.extend(f"{raw_candidates[0]}{suffix}" for suffix in _KNOWN_LOGTALK_SUFFIXES)
    candidate_keys: list[str] = []
    seen: set[str] = set()
    for raw_candidate in raw_candidates:
        for candidate in (
            raw_candidate,
            str(current_parent / raw_candidate),
            f"source/{raw_candidate}",
            f"src/{raw_candidate}",
            f"lib/{raw_candidate}",
            f"examples/{raw_candidate}",
            f"contributions/{raw_candidate}",
        ):
            normalized_candidate = str(PurePosixPath(candidate)).replace("\\", "/").strip("/")
            if normalized_candidate and normalized_candidate not in seen:
                seen.add(normalized_candidate)
                candidate_keys.append(normalized_candidate)
    return tuple(candidate_keys)


def resolve_import(
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    candidate_keys = _candidate_import_keys(import_target, current_file=current_file)
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_keys)


def resolve_target(
    current_file: str,
    reference_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    del current_file
    candidate_names = (
        repository_logtalk_primitives.repository_prolog_primitives._candidate_reference_names(
            reference_target
        )
    )
    suffixes: list[str] = []
    for candidate_name in candidate_names:
        direct_match = module_index.get(candidate_name)
        if direct_match is not None:
            return direct_match
        raw_candidate = candidate_name.replace(".", "/").replace(":", "/")
        suffixes.extend(
            [
                candidate_name,
                raw_candidate,
                f"{raw_candidate}.lgt",
                f"{raw_candidate}.logtalk",
                f"source/{raw_candidate}.lgt",
                f"src/{raw_candidate}.lgt",
                f"lib/{raw_candidate}.lgt",
            ]
        )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def _collect_symbol_entries(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[dict[str, Any], ...]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    final_line = max(1, stripped_text.count("\n") + 1)
    module_name = module_name_from_text(
        text,
        stripped_text=stripped_text,
    ) or module_name_from_path(file_path)
    symbol_entries: list[dict[str, Any]] = []
    seen_names: set[tuple[str, int, str]] = set()
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(
        text,
        file_path=file_path,
        stripped_text=stripped_text,
        module_name=module_name,
    ):
        key = (symbol_name, start_line, symbol_kind)
        if not symbol_name or key in seen_names:
            continue
        seen_names.add(key)
        qualified_names = {symbol_name}
        if module_name and symbol_name != module_name:
            qualified_names.update(
                {
                    f"{module_name}.{symbol_name}",
                    f"{module_name}:{symbol_name}",
                }
            )
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "kind": symbol_kind,
                        "line": start_line,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": start_line,
                "end_line": start_line,
                "signature": (
                    f"{symbol_kind} {symbol_name}"
                    if symbol_kind in {"object", "protocol", "category", "module"}
                    else symbol_name
                ),
                "qualified_names": tuple(sorted(qualified_names)),
            }
        )
    for index, entry in enumerate(symbol_entries):
        entry["end_line"] = (
            max(int(symbol_entries[index + 1]["start_line"]) - 1, int(entry["start_line"]))
            if index + 1 < len(symbol_entries)
            else final_line
        )
    return tuple(symbol_entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
    symbol_entries: tuple[dict[str, Any], ...] | None = None,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_LOGTALK_SUFFIXES:
        return set()
    aliases = set(_path_aliases(path))
    loaded_text = text
    if loaded_text is None:
        try:
            loaded_text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            loaded_text = ""
    candidate_stripped_text = (
        stripped_text if stripped_text is not None else strip_comments(loaded_text)
    )
    if not is_probable_logtalk_source(
        path=path,
        text=loaded_text,
        stripped_text=candidate_stripped_text,
    ):
        return aliases
    module_name = module_name_from_text(
        loaded_text,
        stripped_text=candidate_stripped_text,
    )
    if module_name:
        aliases.add(module_name)
    resolved_symbol_entries = symbol_entries
    if resolved_symbol_entries is None:
        resolved_symbol_entries = _collect_symbol_entries(
            file_path=file_path,
            text=loaded_text,
            stable_identifier=stable_identifier,
            stripped_text=candidate_stripped_text,
        )
    for symbol_entry in resolved_symbol_entries:
        aliases.add(symbol_entry["symbol_name"])
        aliases.update(str(alias) for alias in symbol_entry["qualified_names"] if alias)
    return {alias for alias in aliases if alias}


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[tuple[_Dependency, ...], dict[str, dict[str, Any]]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, dict[str, Any]] = {}

    def _register_dependency(
        *,
        target_name: str,
        line_no: int,
        dependency_type: str,
        imported_names: tuple[str, ...] = (),
    ) -> None:
        target_file = resolve_import(
            file_path,
            target_name,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_symbol = normalize_identifier(PurePosixPath(target_name.replace(".", "/")).stem)
        dependency_key = (target_file, target_symbol, dependency_type)
        if dependency_key in dependency_keys or not target_symbol:
            return
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target_name,
                        "line": line_no,
                        "kind": dependency_type,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type=dependency_type,
            )
        )
        binding_names = imported_names or (target_symbol,)
        for binding_name in binding_names:
            import_bindings.setdefault(
                binding_name,
                {
                    "alias": binding_name,
                    "target_file": target_file,
                    "target_names": tuple(
                        name for name in (binding_name, f"{target_symbol}.{binding_name}") if name
                    ),
                },
            )

    for target_name, line_no in parse_load_statements(text, stripped_text=stripped_text):
        _register_dependency(target_name=target_name, line_no=line_no, dependency_type="imports")
    for target_name, imported_names, line_no in parse_uses_statements(
        text,
        stripped_text=stripped_text,
    ):
        _register_dependency(
            target_name=target_name,
            line_no=line_no,
            dependency_type="imports",
            imported_names=imported_names,
        )
    for target_name, line_no in parse_relation_statements(text, stripped_text=stripped_text):
        _register_dependency(target_name=target_name, line_no=line_no, dependency_type="imports")
    return tuple(dependencies), import_bindings


def _reference_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    import_bindings: dict[str, dict[str, Any]],
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[dict[str, Any], ...]:
    bindings: list[dict[str, Any]] = []
    seen: set[tuple[int, str, tuple[str, ...]]] = set()
    for target_name, target_names, line_no in parse_reference_targets(
        text,
        stripped_text=stripped_text,
    ):
        binding = import_bindings.get(target_name)
        target_file = (
            str(binding["target_file"])
            if binding is not None and isinstance(binding.get("target_file"), str)
            else resolve_target(
                file_path,
                target_name,
                module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
        )
        if target_file is None or target_file == file_path:
            continue
        key = (line_no, target_file, tuple(target_names))
        if key in seen:
            continue
        seen.add(key)
        bindings.append(
            {
                "line_no": line_no,
                "target_file": target_file,
                "target_names": tuple(target_names),
                "target_symbol": target_names[0],
            }
        )
    return tuple(bindings)


def _collect_dependency_entries(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[tuple[_Dependency, ...], dict[str, dict[str, Any]], tuple[dict[str, Any], ...]]:
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (entry.target_file, entry.target_symbol, entry.dependency_type)
        for entry in dependency_entries
    }
    reference_bindings = _reference_bindings(
        file_path,
        text,
        module_index,
        import_bindings=import_bindings,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    for binding in reference_bindings:
        dependency_key = (binding["target_file"], binding["target_symbol"], "references")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": binding["target_names"],
                        "line": binding["line_no"],
                        "kind": "message_send",
                    },
                ),
                source_file=file_path,
                target_file=str(binding["target_file"]),
                target_symbol=str(binding["target_symbol"]),
                dependency_type="references",
            )
        )
    return tuple(dependency_entries), import_bindings, reference_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[_Dependency, ...]:
    candidate_stripped_text = (
        stripped_text if stripped_text is not None else strip_comments(text)
    )
    dependency_entries, _import_bindings, _reference_bindings = _collect_dependency_entries(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=candidate_stripped_text,
    )
    return dependency_entries


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    candidate_stripped_text = (
        stripped_text if stripped_text is not None else strip_comments(text)
    )
    symbol_entries = _collect_symbol_entries(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=candidate_stripped_text,
    )
    symbols = tuple(
        _Symbol(
            symbol_id=str(entry["symbol_id"]),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=None,
            signature=str(entry["signature"]),
        )
        for entry in symbol_entries
    )
    dependency_entries, import_bindings, reference_bindings = _collect_dependency_entries(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=candidate_stripped_text,
    )

    def _symbol_for_line(line_no: int) -> dict[str, Any] | None:
        for symbol_entry in reversed(symbol_entries):
            if int(symbol_entry["start_line"]) <= line_no <= int(symbol_entry["end_line"]):
                return symbol_entry
        return None

    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for binding in reference_bindings:
        source_symbol = _symbol_for_line(int(binding["line_no"]))
        if source_symbol is None:
            continue
        edge_id = stable_identifier(
            "ref",
            {
                "source_symbol_id": source_symbol["symbol_id"],
                "target_file": binding["target_file"],
                "target_names": binding["target_names"],
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            _SymbolReferenceCandidate(
                reference_edge_id=edge_id,
                source_symbol_id=str(source_symbol["symbol_id"]),
                source_file=file_path,
                target_symbol_id=None,
                target_file=str(binding["target_file"]),
                target_names=tuple(str(name) for name in binding["target_names"]),
                reference_type="references_symbol",
            ),
        )
    return (
        symbols,
        dependency_entries,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
