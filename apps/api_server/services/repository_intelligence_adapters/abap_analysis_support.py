from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters.abap_primitives import (
    CALL_FUNCTION_RE,
    CLASS_RE,
    FORM_RE,
    FUNCTION_RE,
    IDENTIFIER_RE,
    INCLUDE_RE,
    INHERITING_RE,
    INTERFACE_RE,
    METHOD_IMPL_RE,
    METHOD_NAME_RE,
    NEW_RE,
    PERFORM_RE,
    PROGRAM_RE,
    RESERVED_SYMBOL_NAMES,
    STATIC_CALL_RE,
    TYPE_REF_RE,
    ResolveInclude,
    ResolveSuffixMatch,
    ResolveTarget,
    StableIdentifier,
    _normalize_repository_relative_path,
    include_member_name_for_path,
    is_primary_object_file,
    iter_interface_targets,
    iter_method_declaration_names,
    normalize_identifier,
    normalize_leaf_name,
    normalize_target,
    owning_object_name_for_path,
    statement_entries,
    strip_comments,
)


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    owning_object = owning_object_name_for_path(file_path)
    stripped_text = strip_comments(text)
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int] | tuple[str, str]] = set()
    final_line = len(stripped_text.splitlines()) if stripped_text else 1

    def _append_symbol(
        *,
        line_no: int,
        raw_name: str,
        symbol_kind: str,
        signature: str,
    ) -> None:
        normalized_name = normalize_identifier(raw_name)
        leaf_name = normalize_leaf_name(raw_name)
        if (
            not normalized_name
            or not leaf_name
            or leaf_name in RESERVED_SYMBOL_NAMES
            or (
                METHOD_NAME_RE.fullmatch(raw_name) is None
                and IDENTIFIER_RE.fullmatch(raw_name) is None
            )
        ):
            return
        symbol_key: tuple[str, str, int] | tuple[str, str]
        if symbol_kind in {"type", "interface"}:
            symbol_key = (symbol_kind, leaf_name)
        else:
            symbol_key = (symbol_kind, leaf_name, line_no)
        if symbol_key in seen_symbol_keys:
            return
        seen_symbol_keys.add(symbol_key)
        qualified_names = {leaf_name}
        if symbol_kind in {"type", "interface"}:
            qualified_names.add(normalized_name)
        if symbol_kind == "function":
            qualified_names.add(normalized_name)
            if owning_object:
                qualified_names.add(f"{owning_object}.{leaf_name}")
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": leaf_name,
                        "kind": symbol_kind,
                        "line": line_no,
                    },
                ),
                "symbol_name": leaf_name,
                "symbol_kind": symbol_kind,
                "start_line": line_no,
                "end_line": final_line,
                "signature": signature,
                "qualified_names": tuple(
                    sorted(alias for alias in qualified_names if alias)
                ),
            }
        )

    for line_no, statement in statement_entries(text):
        normalized_statement = statement.strip()
        if not normalized_statement:
            continue
        if match := CLASS_RE.match(normalized_statement):
            _append_symbol(
                line_no=line_no,
                raw_name=str(match.group("name") or ""),
                symbol_kind="type",
                signature=normalized_statement,
            )
            continue
        if match := INTERFACE_RE.match(normalized_statement):
            _append_symbol(
                line_no=line_no,
                raw_name=str(match.group("name") or ""),
                symbol_kind="interface",
                signature=normalized_statement,
            )
            continue
        if match := PROGRAM_RE.match(normalized_statement):
            _append_symbol(
                line_no=line_no,
                raw_name=str(match.group("name") or ""),
                symbol_kind="type",
                signature=normalized_statement,
            )
            continue
        if match := FORM_RE.match(normalized_statement):
            _append_symbol(
                line_no=line_no,
                raw_name=str(match.group("name") or ""),
                symbol_kind="function",
                signature=normalized_statement,
            )
            continue
        if match := FUNCTION_RE.match(normalized_statement):
            _append_symbol(
                line_no=line_no,
                raw_name=str(match.group("name") or ""),
                symbol_kind="function",
                signature=normalized_statement,
            )
            continue
        if match := METHOD_IMPL_RE.match(normalized_statement):
            _append_symbol(
                line_no=line_no,
                raw_name=str(match.group("name") or ""),
                symbol_kind="function",
                signature=normalized_statement,
            )
            continue
        for method_name in iter_method_declaration_names(normalized_statement):
            _append_symbol(
                line_no=line_no,
                raw_name=method_name,
                symbol_kind="function",
                signature=normalized_statement,
            )

    symbol_entries.sort(
        key=lambda entry: (
            int(entry["start_line"]),
            str(entry["symbol_kind"]),
            str(entry["symbol_name"]),
            str(entry["symbol_id"]),
        )
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
    if path.suffix.lower() != ".abap":
        return set()

    aliases = {
        file_path.lower(),
        path.stem.lower(),
    }
    without_suffix_path = str(path.with_suffix("")).lower()
    aliases.add(without_suffix_path)
    aliases.add(without_suffix_path.replace("/", "."))

    primary_object_name = owning_object_name_for_path(file_path)
    if is_primary_object_file(file_path) and primary_object_name:
        aliases.add(primary_object_name)

    include_member_name = include_member_name_for_path(file_path)
    if include_member_name:
        aliases.add(include_member_name)

    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias and alias not in {".", "/"}}

    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(
            str(alias).lower() for alias in symbol_entry["qualified_names"] if alias
        )
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def iter_include_targets(text: str) -> tuple[tuple[int, str], ...]:
    targets: list[tuple[int, str]] = []
    seen_targets: set[tuple[int, str]] = set()
    for line_no, statement in statement_entries(text):
        match = INCLUDE_RE.match(statement)
        if match is None:
            continue
        normalized_target = normalize_target(str(match.group("target") or ""))
        if not normalized_target:
            continue
        target_key = (line_no, normalized_target)
        if target_key in seen_targets:
            continue
        seen_targets.add(target_key)
        targets.append((line_no, normalized_target))
    return tuple(targets)


def iter_reference_targets(text: str) -> tuple[tuple[int, str, str, str], ...]:
    targets: list[tuple[int, str, str, str]] = []
    seen_targets: set[tuple[int, str, str, str]] = set()

    def _add_target(
        *,
        line_no: int,
        reference_kind: str,
        lookup_target: str,
        target_symbol: str,
    ) -> None:
        normalized_lookup_target = normalize_target(lookup_target)
        normalized_target_symbol = normalize_leaf_name(target_symbol)
        if (
            not normalized_lookup_target
            or not normalized_target_symbol
            or normalized_target_symbol in RESERVED_SYMBOL_NAMES
        ):
            return
        target_key = (
            line_no,
            reference_kind,
            normalized_lookup_target,
            normalized_target_symbol,
        )
        if target_key in seen_targets:
            return
        seen_targets.add(target_key)
        targets.append(target_key)

    for line_no, statement in statement_entries(text):
        for match in STATIC_CALL_RE.finditer(statement):
            prefix = normalize_identifier(str(match.group("prefix") or ""))
            target_name = normalize_leaf_name(str(match.group("name") or ""))
            if not prefix or not target_name:
                continue
            _add_target(
                line_no=line_no,
                reference_kind="static_call",
                lookup_target=f"{prefix}.{target_name}",
                target_symbol=target_name,
            )
        for match in PERFORM_RE.finditer(statement):
            target_name = normalize_leaf_name(str(match.group("name") or ""))
            if target_name:
                _add_target(
                    line_no=line_no,
                    reference_kind="perform",
                    lookup_target=target_name,
                    target_symbol=target_name,
                )
        for match in CALL_FUNCTION_RE.finditer(statement):
            target_name = normalize_identifier(
                str(match.group("single") or match.group("backtick") or "")
            )
            if target_name:
                _add_target(
                    line_no=line_no,
                    reference_kind="call_function",
                    lookup_target=target_name,
                    target_symbol=target_name,
                )
        for interface_target in iter_interface_targets(statement):
            _add_target(
                line_no=line_no,
                reference_kind="interfaces",
                lookup_target=interface_target,
                target_symbol=interface_target,
            )
        for regex, reference_kind in (
            (INHERITING_RE, "inherits"),
            (TYPE_REF_RE, "type_ref"),
            (NEW_RE, "constructor"),
        ):
            for match in regex.finditer(statement):
                target_name = normalize_identifier(str(match.group("name") or ""))
                if not target_name:
                    continue
                _add_target(
                    line_no=line_no,
                    reference_kind=reference_kind,
                    lookup_target=target_name,
                    target_symbol=target_name,
                )
    return tuple(targets)


def resolve_include(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_target(import_target)
    if not normalized_target:
        return None

    current_dir = _normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    if "/" in normalized_target:
        if current_dir:
            candidate_keys.append(
                _normalize_repository_relative_path(
                    str(PurePosixPath(current_dir) / normalized_target)
                )
            )
        candidate_keys.append(_normalize_repository_relative_path(normalized_target))
        candidate_keys.append(PurePosixPath(normalized_target).name.lower())

    ordered_candidates: list[str] = []
    seen_candidates: set[str] = set()
    for candidate_key in candidate_keys:
        if not candidate_key or candidate_key in seen_candidates:
            continue
        seen_candidates.add(candidate_key)
        ordered_candidates.append(candidate_key)

    for candidate_key in ordered_candidates:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved

    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(ordered_candidates),
    )


def resolve_target(
    reference_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_target(reference_target)
    if not normalized_target:
        return None

    candidate_keys = [normalized_target]
    if "~" in normalized_target:
        candidate_keys.append(normalized_target.replace("~", "."))
        candidate_keys.append(normalized_target.rsplit("~", 1)[0])
    if "." in normalized_target:
        candidate_keys.append(normalized_target.rsplit(".", 1)[0])
        candidate_keys.append(normalized_target.rsplit(".", 1)[-1])

    ordered_candidates: list[str] = []
    seen_candidates: set[str] = set()
    for candidate_key in candidate_keys:
        if not candidate_key or candidate_key in seen_candidates:
            continue
        seen_candidates.add(candidate_key)
        ordered_candidates.append(candidate_key)

    for candidate_key in ordered_candidates:
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved

    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(ordered_candidates),
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_include: ResolveInclude,
    resolve_target: ResolveTarget,
) -> tuple[dict[str, Any], ...]:
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()

    for line_no, import_target in iter_include_targets(text):
        target_file = resolve_include(file_path, import_target, module_index)
        target_symbol = normalize_leaf_name(import_target)
        dependency_key = (target_file, target_symbol or import_target, "imports")
        if target_file is None or target_file == file_path or dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "line": line_no,
                        "kind": "include",
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": target_symbol or import_target,
                "dependency_type": "imports",
            }
        )

    for line_no, reference_kind, lookup_target, target_symbol in iter_reference_targets(text):
        target_file = resolve_target(lookup_target, module_index)
        dependency_key = (target_file, target_symbol, "references")
        if target_file is None or target_file == file_path or dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": lookup_target,
                        "line": line_no,
                        "kind": reference_kind,
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": target_symbol,
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
    resolve_include: ResolveInclude,
    resolve_target: ResolveTarget,
) -> tuple[
    list[dict[str, Any]],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    stripped_lines = strip_comments(text).splitlines()
    reference_candidates: dict[str, dict[str, Any]] = {}

    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_id = str(symbol_entry["symbol_id"])
        snippet = "\n".join(stripped_lines[start_line - 1 : end_line])
        for _line_no, _reference_kind, lookup_target, target_symbol in iter_reference_targets(
            snippet
        ):
            target_file = resolve_target(lookup_target, module_index)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (target_symbol,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": symbol_id,
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (target_symbol,),
                    "reference_type": "references_symbol",
                },
            )

    return (
        symbol_entries,
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_include=resolve_include,
            resolve_target=resolve_target,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
