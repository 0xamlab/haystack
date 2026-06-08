from __future__ import annotations

from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    classic_visual_basic_primitives as repository_classic_visual_basic_primitives,
)

StableIdentifier = repository_classic_visual_basic_primitives.StableIdentifier
ResolveDirectoryPrefixMatch = (
    repository_classic_visual_basic_primitives.ResolveDirectoryPrefixMatch
)
ResolveSuffixMatch = repository_classic_visual_basic_primitives.ResolveSuffixMatch

_KNOWN_CLASSIC_VISUAL_BASIC_SUFFIXES = (
    repository_classic_visual_basic_primitives._KNOWN_CLASSIC_VISUAL_BASIC_SUFFIXES
)
RESERVED_SYMBOL_NAMES = (
    repository_classic_visual_basic_primitives.RESERVED_SYMBOL_NAMES
)
BUILTIN_TYPE_NAMES = repository_classic_visual_basic_primitives.BUILTIN_TYPE_NAMES
PROJECT_NAME_RE = repository_classic_visual_basic_primitives.PROJECT_NAME_RE
ROUTINE_DECL_RE = repository_classic_visual_basic_primitives.ROUTINE_DECL_RE
TYPE_DECL_RE = repository_classic_visual_basic_primitives.TYPE_DECL_RE
VARIABLE_TYPE_BINDING_RE = (
    repository_classic_visual_basic_primitives.VARIABLE_TYPE_BINDING_RE
)
SET_NEW_BINDING_RE = repository_classic_visual_basic_primitives.SET_NEW_BINDING_RE
TYPE_REFERENCE_RE = repository_classic_visual_basic_primitives.TYPE_REFERENCE_RE
QUALIFIED_REFERENCE_RE = (
    repository_classic_visual_basic_primitives.QUALIFIED_REFERENCE_RE
)
UNQUALIFIED_CALL_RE = repository_classic_visual_basic_primitives.UNQUALIFIED_CALL_RE

_component_declaration_line = (
    repository_classic_visual_basic_primitives._component_declaration_line
)
_component_symbol_kind = (
    repository_classic_visual_basic_primitives._component_symbol_kind
)
component_name = repository_classic_visual_basic_primitives.component_name
is_probable_classic_visual_basic_source = (
    repository_classic_visual_basic_primitives.is_probable_classic_visual_basic_source
)
normalize_symbol_name = (
    repository_classic_visual_basic_primitives.normalize_symbol_name
)
normalize_target = repository_classic_visual_basic_primitives.normalize_target
project_component_entries = (
    repository_classic_visual_basic_primitives.project_component_entries
)
project_name = repository_classic_visual_basic_primitives.project_name
strip_comments = repository_classic_visual_basic_primitives.strip_comments


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    path = PurePosixPath(file_path)
    stripped_text = strip_comments(text)
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    final_line = len(stripped_text.splitlines()) if stripped_text else 1
    if path.suffix.lower() != ".vbp":
        current_component = component_name(text, file_path=file_path)
        if current_component:
            line_no = _component_declaration_line(text)
            component_kind = _component_symbol_kind(path)
            symbol_entries.append(
                {
                    "symbol_id": stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": current_component,
                            "kind": component_kind,
                            "line": line_no,
                        },
                    ),
                    "symbol_name": current_component,
                    "symbol_kind": component_kind,
                    "start_line": line_no,
                    "end_line": line_no,
                    "signature": current_component,
                    "qualified_names": (current_component.lower(),),
                }
            )
            seen_symbol_keys.add((component_kind, current_component.lower(), line_no))
        for regex, symbol_kind in ((TYPE_DECL_RE, "type"), (ROUTINE_DECL_RE, "function")):
            for match in regex.finditer(stripped_text):
                symbol_name = normalize_symbol_name(str(match.group("name") or ""))
                canonical_symbol_name = symbol_name.lower()
                if not symbol_name or canonical_symbol_name in RESERVED_SYMBOL_NAMES:
                    continue
                line_no = stripped_text.count("\n", 0, match.start()) + 1
                symbol_key = (symbol_kind, canonical_symbol_name, line_no)
                if symbol_key in seen_symbol_keys:
                    continue
                seen_symbol_keys.add(symbol_key)
                qualified_names = {canonical_symbol_name}
                if current_component and current_component.lower() != canonical_symbol_name:
                    qualified_names.add(f"{current_component.lower()}.{canonical_symbol_name}")
                symbol_entries.append(
                    {
                        "symbol_id": stable_identifier(
                            "sym",
                            {
                                "file_path": file_path,
                                "name": symbol_name,
                                "kind": symbol_kind,
                                "line": line_no,
                            },
                        ),
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                        "start_line": line_no,
                        "end_line": line_no,
                        "signature": str(match.group(0) or "").strip(),
                        "qualified_names": tuple(sorted(qualified_names)),
                    }
                )
    elif (name := project_name(text)):
        project_name_match = PROJECT_NAME_RE.search(text)
        if project_name_match is None:
            line_no = 1
        else:
            line_no = text.count("\n", 0, project_name_match.start()) + 1
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": name,
                        "kind": "module",
                        "line": line_no,
                    },
                ),
                "symbol_name": name,
                "symbol_kind": "module",
                "start_line": line_no,
                "end_line": line_no,
                "signature": name,
                "qualified_names": (name.lower(),),
            }
        )
    symbol_entries.sort(key=lambda entry: (int(entry["start_line"]), str(entry["symbol_name"])))
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
    suffix = path.suffix.lower()
    if suffix not in _KNOWN_CLASSIC_VISUAL_BASIC_SUFFIXES:
        return set()
    aliases = {
        file_path.lower(),
        path.stem.lower(),
        str(path.with_suffix("")).lower(),
        str(path.with_suffix("")).replace("/", ".").lower(),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias and alias not in {".", "/"}}
    if not is_probable_classic_visual_basic_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias and alias not in {".", "/"}}
    if suffix != ".vbp":
        current_component = component_name(text, file_path=file_path)
        if current_component:
            aliases.add(current_component.lower())
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(
            str(alias).lower()
            for alias in symbol_entry.get("qualified_names", ())
            if alias
        )
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def resolve_target(
    reference_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
    resolve_directory_prefix_match: ResolveDirectoryPrefixMatch,
) -> str | None:
    normalized_target = normalize_target(reference_target)
    if not normalized_target:
        return None
    canonical_target = normalized_target.lower()
    if canonical_target in RESERVED_SYMBOL_NAMES or canonical_target in BUILTIN_TYPE_NAMES:
        return None
    direct = module_index.get(canonical_target)
    if direct is not None:
        return direct
    leaf_name = canonical_target.rsplit(".", 1)[-1]
    direct_leaf = module_index.get(leaf_name)
    if direct_leaf is not None:
        return direct_leaf
    path_target = canonical_target.replace(".", "/")
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            canonical_target,
            leaf_name,
            path_target,
            f"{path_target}.bas",
            f"{path_target}.cls",
            f"{path_target}.frm",
            f"{path_target}.ctl",
            f"{leaf_name}.bas",
            f"{leaf_name}.cls",
            f"{leaf_name}.frm",
            f"{leaf_name}.ctl",
        ],
    )
    if resolved is not None:
        return resolved
    return resolve_directory_prefix_match(
        module_index=module_index,
        prefixes=[
            path_target,
            f"src/{path_target}",
            leaf_name,
            f"src/{leaf_name}",
        ],
    )


def _instance_bindings(
    text: str,
    *,
    resolve_target_fn: Callable[[str], str | None],
) -> dict[str, dict[str, str]]:
    bindings: dict[str, dict[str, str]] = {}
    stripped_text = strip_comments(text)
    for regex in (VARIABLE_TYPE_BINDING_RE, SET_NEW_BINDING_RE):
        for match in regex.finditer(stripped_text):
            alias = normalize_symbol_name(str(match.group("name") or "")).lower()
            target_name = normalize_target(str(match.group("type") or ""))
            if not alias or not target_name or alias in RESERVED_SYMBOL_NAMES:
                continue
            target_file = resolve_target_fn(target_name)
            if target_file is None:
                continue
            bindings[alias] = {
                "target_file": target_file,
                "target_name": target_name.rsplit(".", 1)[-1],
            }
    return bindings


def _append_dependency(
    dependency_entries: list[dict[str, Any]],
    dependency_keys: set[tuple[str | None, str, str]],
    *,
    file_path: str,
    target_file: str | None,
    target_symbol: str,
    dependency_type: str,
    stable_identifier: StableIdentifier,
    position: int,
) -> None:
    if not target_symbol:
        return
    dependency_key = (target_file, target_symbol.lower(), dependency_type)
    if dependency_key in dependency_keys:
        return
    dependency_keys.add(dependency_key)
    dependency_entries.append(
        {
            "dependency_edge_id": stable_identifier(
                "dep",
                {
                    "file_path": file_path,
                    "target": target_symbol.lower(),
                    "line": position,
                    "type": dependency_type,
                },
            ),
            "source_file": file_path,
            "target_file": target_file,
            "target_symbol": target_symbol,
            "dependency_type": dependency_type,
        }
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_target_fn: Callable[[str], str | None],
) -> tuple[dict[str, Any], ...]:
    path = PurePosixPath(file_path)
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    if path.suffix.lower() == ".vbp":
        for index, entry in enumerate(project_component_entries(text, manifest_path=file_path)):
            _append_dependency(
                dependency_entries,
                dependency_keys,
                file_path=file_path,
                target_file=str(entry["path"]),
                target_symbol=str(entry["component_name"]),
                dependency_type="imports",
                stable_identifier=stable_identifier,
                position=index,
            )
        return tuple(dependency_entries)
    local_symbol_names = {
        str(entry["symbol_name"]).lower()
        for entry in collect_symbol_entries(
            text,
            file_path=file_path,
            stable_identifier=stable_identifier,
        )
    }
    instance_bindings = _instance_bindings(text, resolve_target_fn=resolve_target_fn)
    stripped_text = strip_comments(text)
    for match in TYPE_REFERENCE_RE.finditer(stripped_text):
        target_name = normalize_target(str(match.group("name") or ""))
        leaf_name = target_name.rsplit(".", 1)[-1]
        canonical_leaf_name = leaf_name.lower()
        if (
            not target_name
            or canonical_leaf_name in RESERVED_SYMBOL_NAMES
            or canonical_leaf_name in BUILTIN_TYPE_NAMES
            or canonical_leaf_name in local_symbol_names
        ):
            continue
        target_file = resolve_target_fn(target_name)
        if target_file is None or target_file == file_path:
            continue
        _append_dependency(
            dependency_entries,
            dependency_keys,
            file_path=file_path,
            target_file=target_file,
            target_symbol=leaf_name,
            dependency_type="references",
            stable_identifier=stable_identifier,
            position=match.start(),
        )
    for match in QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        alias = normalize_symbol_name(str(match.group("alias") or "")).lower()
        target_name = normalize_symbol_name(str(match.group("name") or ""))
        if not alias or not target_name or alias in RESERVED_SYMBOL_NAMES:
            continue
        if alias in instance_bindings:
            target_file = str(instance_bindings[alias]["target_file"])
        else:
            target_file = resolve_target_fn(alias)
        if target_file is None or target_file == file_path:
            continue
        _append_dependency(
            dependency_entries,
            dependency_keys,
            file_path=file_path,
            target_file=target_file,
            target_symbol=target_name,
            dependency_type="references",
            stable_identifier=stable_identifier,
            position=match.start(),
        )
    for match in UNQUALIFIED_CALL_RE.finditer(stripped_text):
        target_name = normalize_symbol_name(str(match.group("name") or ""))
        canonical_target_name = target_name.lower()
        if (
            not target_name
            or canonical_target_name in RESERVED_SYMBOL_NAMES
            or canonical_target_name in local_symbol_names
        ):
            continue
        target_file = resolve_target_fn(target_name)
        if target_file is None or target_file == file_path:
            continue
        _append_dependency(
            dependency_entries,
            dependency_keys,
            file_path=file_path,
            target_file=target_file,
            target_symbol=target_name,
            dependency_type="references",
            stable_identifier=stable_identifier,
            position=match.start(),
        )
    return tuple(dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_target_fn: Callable[[str], str | None],
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
    dependency_entries = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_target_fn=resolve_target_fn,
    )
    path = PurePosixPath(file_path)
    if path.suffix.lower() == ".vbp":
        return symbol_entries, dependency_entries, ()
    instance_bindings = _instance_bindings(text, resolve_target_fn=resolve_target_fn)
    local_symbol_names = {str(entry["symbol_name"]).lower() for entry in symbol_entries}
    stripped_lines = strip_comments(text).splitlines()
    reference_candidates: dict[str, dict[str, Any]] = {}
    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_id = str(symbol_entry["symbol_id"])
        symbol_name = str(symbol_entry["symbol_name"]).lower()
        snippet = "\n".join(stripped_lines[start_line - 1 : end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias = normalize_symbol_name(str(match.group("alias") or "")).lower()
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            if not alias or not target_name or alias in RESERVED_SYMBOL_NAMES:
                continue
            if alias in instance_bindings:
                target_file = str(instance_bindings[alias]["target_file"])
            else:
                target_file = resolve_target_fn(alias)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (target_name,),
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
                    "target_names": (target_name,),
                    "reference_type": "references_symbol",
                },
            )
        for match in TYPE_REFERENCE_RE.finditer(snippet):
            target_name = normalize_target(str(match.group("name") or ""))
            leaf_name = target_name.rsplit(".", 1)[-1]
            canonical_leaf_name = leaf_name.lower()
            if (
                not target_name
                or canonical_leaf_name in RESERVED_SYMBOL_NAMES
                or canonical_leaf_name in BUILTIN_TYPE_NAMES
                or canonical_leaf_name == symbol_name
            ):
                continue
            target_file = resolve_target_fn(target_name)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (leaf_name,),
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
                    "target_names": (leaf_name,),
                    "reference_type": "references_symbol",
                },
            )
        for match in UNQUALIFIED_CALL_RE.finditer(snippet):
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            canonical_target_name = target_name.lower()
            if (
                not target_name
                or canonical_target_name in RESERVED_SYMBOL_NAMES
                or canonical_target_name in local_symbol_names
            ):
                continue
            target_file = resolve_target_fn(target_name)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (target_name,),
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
                    "target_names": (target_name,),
                    "reference_type": "references_symbol",
                },
            )
    return (
        symbol_entries,
        dependency_entries,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
