from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    prolog_primitives as repository_prolog_primitives,
)

StableIdentifier = repository_prolog_primitives.StableIdentifier
ResolveSuffixMatch = repository_prolog_primitives.ResolveSuffixMatch
ResolveImport = repository_prolog_primitives.ResolveImport
ResolveTarget = repository_prolog_primitives.ResolveTarget

_KNOWN_PROLOG_SUFFIXES = repository_prolog_primitives._KNOWN_PROLOG_SUFFIXES
_QUALIFIED_CALL_RE = repository_prolog_primitives._QUALIFIED_CALL_RE
_CALL_RE = repository_prolog_primitives._CALL_RE
RESERVED_SYMBOL_NAMES = repository_prolog_primitives.RESERVED_SYMBOL_NAMES

normalize_identifier = repository_prolog_primitives.normalize_identifier
has_prolog_markers = repository_prolog_primitives.has_prolog_markers
_module_name_from_text = repository_prolog_primitives._module_name_from_text
_parse_clause_head = repository_prolog_primitives._parse_clause_head
_split_clauses = repository_prolog_primitives._split_clauses
_path_aliases = repository_prolog_primitives._path_aliases
_candidate_import_keys = repository_prolog_primitives._candidate_import_keys
_candidate_reference_names = repository_prolog_primitives._candidate_reference_names
_normalize_target_name = repository_prolog_primitives._normalize_target_name
_split_use_module_target_and_imports = (
    repository_prolog_primitives._split_use_module_target_and_imports
)
_import_aliases = repository_prolog_primitives._import_aliases
_USE_MODULE_DIRECTIVE_RE = repository_prolog_primitives._USE_MODULE_DIRECTIVE_RE
_LOAD_DIRECTIVE_RE = repository_prolog_primitives._LOAD_DIRECTIVE_RE
_LIST_LOAD_DIRECTIVE_RE = repository_prolog_primitives._LIST_LOAD_DIRECTIVE_RE


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    module_name = _module_name_from_text(text)
    file_alias = normalize_identifier(PurePosixPath(file_path).stem)
    stripped_text = repository_prolog_primitives.strip_comments(text)
    final_line = len(stripped_text.splitlines()) if stripped_text else 1
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int]] = set()
    for line_no, clause in _split_clauses(stripped_text):
        _declared_module, symbol_name, signature = _parse_clause_head(clause)
        if not symbol_name:
            continue
        symbol_key = (symbol_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        qualified_names = {symbol_name}
        if module_name:
            qualified_names.add(f"{module_name}.{symbol_name}")
            qualified_names.add(f"{module_name}:{symbol_name}")
        if file_alias and file_alias != symbol_name:
            qualified_names.add(f"{file_alias}.{symbol_name}")
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "kind": "function",
                        "line": line_no,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": "function",
                "start_line": line_no,
                "end_line": line_no,
                "signature": signature,
                "qualified_names": tuple(sorted(qualified_names)),
            }
        )
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_PROLOG_SUFFIXES:
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if path.suffix.lower() == ".pl" and text and not has_prolog_markers(text):
        return set()
    aliases = set(_path_aliases(path))
    module_name = _module_name_from_text(text)
    if module_name:
        aliases.add(module_name)
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(str(alias).lower() for alias in symbol_entry["qualified_names"] if alias)
    return {alias for alias in aliases if alias}


def resolve_import(
    current_file: str,
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    candidate_keys = _candidate_import_keys(import_target, current_file=current_file)
    if not candidate_keys:
        return None
    for candidate_key in candidate_keys:
        direct_match = module_index.get(candidate_key)
        if direct_match is not None:
            return direct_match
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_keys)


def resolve_target(
    current_file: str,
    reference_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    del current_file
    candidate_names = _candidate_reference_names(reference_target)
    if not candidate_names:
        return None
    suffixes: list[str] = []
    for candidate_name in candidate_names:
        direct_match = module_index.get(candidate_name)
        if direct_match is not None:
            return direct_match
        suffixes.extend(
            [
                candidate_name,
                f"{candidate_name}.pl",
                f"{candidate_name}.prolog",
                f"src/{candidate_name}.pl",
                f"lib/{candidate_name}.pl",
                f"prolog/{candidate_name}.pl",
                f"app/{candidate_name}.pl",
            ]
        )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
    resolve_target: ResolveTarget,
) -> tuple[tuple[dict[str, Any], ...], dict[str, dict[str, Any]]]:
    del resolve_target
    dependencies: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, dict[str, Any]] = {}
    for line_no, clause in _split_clauses(text):
        normalized_clause = clause.strip()
        if not normalized_clause.startswith(":-"):
            continue
        imported_targets: list[tuple[str, tuple[str, ...]]] = []
        use_module_match = _USE_MODULE_DIRECTIVE_RE.match(normalized_clause)
        if use_module_match is not None:
            imported_targets.append(
                _split_use_module_target_and_imports(str(use_module_match.group("target") or ""))
            )
        else:
            load_match = _LOAD_DIRECTIVE_RE.match(normalized_clause)
            if load_match is not None:
                imported_targets.append((str(load_match.group("target") or ""), ()))
            else:
                list_load_match = _LIST_LOAD_DIRECTIVE_RE.match(normalized_clause)
                if list_load_match is not None:
                    for raw_target in str(list_load_match.group("body") or "").split(","):
                        if raw_target.strip():
                            imported_targets.append((raw_target.strip(), ()))
        for raw_target, imported_names in imported_targets:
            normalized_target = _normalize_target_name(raw_target)
            if not normalized_target:
                continue
            target_file = resolve_import(file_path, raw_target, module_index)
            target_symbol = PurePosixPath(normalized_target).stem.lower()
            dependency_key = (target_file, target_symbol, "imports")
            if dependency_key not in dependency_keys:
                dependency_keys.add(dependency_key)
                dependencies.append(
                    {
                        "dependency_edge_id": stable_identifier(
                            "dep",
                            {
                                "file_path": file_path,
                                "target": normalized_target,
                                "line": line_no,
                            },
                        ),
                        "source_file": file_path,
                        "target_file": target_file,
                        "target_symbol": target_symbol,
                        "dependency_type": "imports",
                    }
                )
            binding_names = imported_names or _import_aliases(raw_target)
            for binding_name in binding_names:
                import_bindings.setdefault(
                    binding_name,
                    {
                        "alias": binding_name,
                        "target_file": target_file,
                        "target_names": (binding_name,),
                    },
                )
            if target_symbol:
                import_bindings.setdefault(
                    target_symbol,
                    {
                        "alias": target_symbol,
                        "target_file": target_file,
                        "target_names": (target_symbol,),
                    },
                )
    return tuple(dependencies), import_bindings


def _body_reference_names(body: str) -> tuple[str, ...]:
    reference_names: list[str] = []
    seen_names: set[str] = set()
    for match in _QUALIFIED_CALL_RE.finditer(body):
        module_name = normalize_identifier(str(match.group("module") or ""))
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not module_name or not symbol_name or symbol_name in RESERVED_SYMBOL_NAMES:
            continue
        for candidate_name in (
            f"{module_name}.{symbol_name}",
            f"{module_name}:{symbol_name}",
            symbol_name,
        ):
            if candidate_name in seen_names:
                continue
            seen_names.add(candidate_name)
            reference_names.append(candidate_name)
    qualified_spans = {match.span() for match in _QUALIFIED_CALL_RE.finditer(body)}
    for match in _CALL_RE.finditer(body):
        if any(start <= match.start() < end for start, end in qualified_spans):
            continue
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name or symbol_name in RESERVED_SYMBOL_NAMES or symbol_name in seen_names:
            continue
        seen_names.add(symbol_name)
        reference_names.append(symbol_name)
    return tuple(reference_names)


def _reference_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    import_bindings: dict[str, dict[str, Any]],
    resolve_target: ResolveTarget,
) -> tuple[dict[str, Any], ...]:
    bindings: list[dict[str, Any]] = []
    seen_bindings: set[tuple[int, str, tuple[str, ...]]] = set()
    for line_no, clause in _split_clauses(text):
        normalized_clause = clause.strip()
        if not normalized_clause or normalized_clause.startswith(":-"):
            continue
        separator = ":-"
        if "-->" in normalized_clause and ":-" not in normalized_clause:
            separator = "-->"
        if separator not in normalized_clause:
            continue
        _head, body = normalized_clause.split(separator, 1)
        for reference_name in _body_reference_names(body):
            binding = import_bindings.get(reference_name)
            target_names = _candidate_reference_names(reference_name)
            target_file = None
            if binding is not None and isinstance(binding.get("target_file"), str):
                target_file = str(binding["target_file"])
                target_names = tuple(
                    str(name).lower()
                    for name in binding.get("target_names", ())
                    if str(name).strip()
                ) or target_names
            if target_file is None:
                target_file = resolve_target(file_path, reference_name, module_index)
            if target_file is None or target_file == file_path:
                continue
            binding_key = (line_no, target_file, tuple(target_names))
            if binding_key in seen_bindings:
                continue
            seen_bindings.add(binding_key)
            bindings.append(
                {
                    "line_no": line_no,
                    "target_file": target_file,
                    "target_names": tuple(target_names),
                    "target_symbol": target_names[0].rsplit(".", 1)[-1].rsplit(":", 1)[-1],
                }
            )
    return tuple(bindings)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
    resolve_target: ResolveTarget,
) -> tuple[dict[str, Any], ...]:
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
        resolve_target=resolve_target,
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (entry["target_file"], entry["target_symbol"], entry["dependency_type"])
        for entry in dependency_entries
    }
    for binding in _reference_bindings(
        file_path,
        text,
        module_index,
        import_bindings=import_bindings,
        resolve_target=resolve_target,
    ):
        dependency_key = (binding["target_file"], binding["target_symbol"], "references")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": binding["target_names"],
                        "line": binding["line_no"],
                        "kind": "predicate_call",
                    },
                ),
                "source_file": file_path,
                "target_file": binding["target_file"],
                "target_symbol": binding["target_symbol"],
                "dependency_type": "references",
            }
        )
    return tuple(dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
    resolve_target: ResolveTarget,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(
        {
            "symbol_id": str(entry["symbol_id"]),
            "symbol_name": str(entry["symbol_name"]),
            "symbol_kind": str(entry["symbol_kind"]),
            "start_line": int(entry["start_line"]),
            "end_line": int(entry["end_line"]),
            "signature": str(entry["signature"]),
        }
        for entry in symbol_entries
    )
    _dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
        resolve_target=resolve_target,
    )
    dependency_entries = list(
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
            resolve_target=resolve_target,
        )
    )

    def _symbol_for_line(line_no: int) -> dict[str, Any] | None:
        for symbol_entry in reversed(symbol_entries):
            if int(symbol_entry["start_line"]) <= line_no <= int(symbol_entry["end_line"]):
                return symbol_entry
        return None

    reference_candidates: dict[str, dict[str, Any]] = {}
    for binding in _reference_bindings(
        file_path,
        text,
        module_index,
        import_bindings=import_bindings,
        resolve_target=resolve_target,
    ):
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
            {
                "reference_edge_id": edge_id,
                "source_symbol_id": str(source_symbol["symbol_id"]),
                "source_file": file_path,
                "target_symbol_id": None,
                "target_file": str(binding["target_file"]),
                "target_names": tuple(binding["target_names"]),
                "reference_type": "references_symbol",
            },
        )
    return (
        symbols,
        tuple(dependency_entries),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
