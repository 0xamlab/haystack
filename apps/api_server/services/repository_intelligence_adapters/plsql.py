from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from . import sql as sql_adapter

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

RESERVED_SYMBOL_NAMES = frozenset(
    set(sql_adapter.RESERVED_SYMBOL_NAMES)
    | {
        "begin",
        "body",
        "cursor",
        "declare",
        "elsif",
        "exception",
        "execute",
        "immediate",
        "is",
        "loop",
        "package",
        "pragma",
        "raise",
        "record",
        "return",
        "trigger",
    }
)
IDENTIFIER_SEGMENT_PATTERN = sql_adapter.IDENTIFIER_SEGMENT_PATTERN
COMPOUND_IDENTIFIER_PATTERN = sql_adapter.COMPOUND_IDENTIFIER_PATTERN
CREATE_DECL_RE = re.compile(
    r"\bcreate\s+(?:or\s+replace\s+)?(?:editionable\s+|noneditionable\s+)?"
    r"(?P<kind>package(?:\s+body)?|procedure|function|trigger|type|materialized\s+view|table|view)\s+"
    r"(?P<name>"
    + COMPOUND_IDENTIFIER_PATTERN
    + r")",
    re.IGNORECASE,
)
ROUTINE_DECL_RE = re.compile(
    r"^\s*(?P<kind>procedure|function)\s+(?P<name>" + IDENTIFIER_SEGMENT_PATTERN + r")\b",
    re.IGNORECASE | re.MULTILINE,
)
RELATION_REFERENCE_RE = re.compile(
    r"\b(?:from|join|insert\s+into|update|delete\s+from|merge\s+into|truncate\s+table|"
    r"alter\s+table|references)\s+(?:only\s+)?(?P<name>"
    + COMPOUND_IDENTIFIER_PATTERN
    + r")",
    re.IGNORECASE,
)
CALL_RE = re.compile(
    r"\b(?:call|exec|execute)\s+(?P<name>" + COMPOUND_IDENTIFIER_PATTERN + r")\s*\(",
    re.IGNORECASE,
)
QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<name>"
    + IDENTIFIER_SEGMENT_PATTERN
    + r"(?:\s*\.\s*"
    + IDENTIFIER_SEGMENT_PATTERN
    + r"){1,2})\s*(?:\(|;)",
    re.IGNORECASE,
)
FALLBACK_SYMBOL_RE = sql_adapter.FALLBACK_SYMBOL_RE
_KNOWN_PLSQL_SUFFIXES = (".pkb", ".pks", ".pls", ".prc", ".fnc", ".trg")
_KNOWN_PLSQL_IMPORT_SUFFIXES = (".pks", ".pkb", ".pls", ".prc", ".fnc", ".trg")


def strip_comments(text: str) -> str:
    return sql_adapter.strip_comments(text)


def normalize_identifier(raw_name: str) -> str:
    return sql_adapter.normalize_identifier(raw_name)


def symbol_name_parts(symbol_name: str) -> tuple[str, str]:
    return sql_adapter.symbol_name_parts(symbol_name)


def _preferred_resolution_suffixes(
    normalized_target: str,
    leaf_name: str,
    *,
    suffix_order: Sequence[str],
) -> list[str]:
    namespace_path = normalized_target.replace(".", "/")
    suffixes: list[str] = []
    for suffix in (*suffix_order, ".sql"):
        for base in (normalized_target, namespace_path, leaf_name):
            if base:
                suffixes.append(f"{base}{suffix}")
    return suffixes


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target, leaf_name = symbol_name_parts(import_target)
    if not normalized_target:
        return None
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=_preferred_resolution_suffixes(
            normalized_target,
            leaf_name,
            suffix_order=_KNOWN_PLSQL_IMPORT_SUFFIXES,
        ),
    )
    if resolved is not None:
        return resolved
    for candidate in (normalized_target, leaf_name):
        if not candidate:
            continue
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match
    return None


def resolve_target(
    reference_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target, leaf_name = symbol_name_parts(reference_target)
    if not normalized_target:
        return None
    for candidate in (normalized_target, leaf_name):
        if not candidate:
            continue
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=_preferred_resolution_suffixes(
            normalized_target,
            leaf_name,
            suffix_order=_KNOWN_PLSQL_SUFFIXES,
        ),
    )


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    stripped_text = strip_comments(text)
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    create_declarations: dict[int, list[tuple[str, str, str, str]]] = {}
    current_package = ""
    final_line = len(stripped_text.splitlines()) if stripped_text else 1

    for match in CREATE_DECL_RE.finditer(stripped_text):
        normalized_name, leaf_name = symbol_name_parts(str(match.group("name") or ""))
        if (
            not normalized_name
            or not leaf_name
            or leaf_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        raw_kind = re.sub(r"\s+", " ", str(match.group("kind") or "").strip().lower())
        symbol_kind = (
            "module"
            if raw_kind.startswith("package")
            else "function"
            if raw_kind in {"function", "procedure", "trigger"}
            else "type"
        )
        line_no = stripped_text.count("\n", 0, match.start()) + 1
        signature = str(match.group(0) or "").strip()
        create_declarations.setdefault(line_no, []).append(
            (raw_kind, normalized_name, leaf_name, signature)
        )

    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        for raw_kind, normalized_name, leaf_name, signature in create_declarations.get(line_no, []):
            qualified_names = {leaf_name, normalized_name}
            if raw_kind == "package body":
                qualified_names.add(f"{normalized_name}.body")
                current_package = normalized_name
            elif raw_kind == "package":
                current_package = normalized_name
            symbol_kind = (
                "module"
                if raw_kind.startswith("package")
                else "function"
                if raw_kind in {"function", "procedure", "trigger"}
                else "type"
            )
            symbol_key = (symbol_kind, normalized_name, line_no)
            if symbol_key in seen_symbol_keys:
                continue
            seen_symbol_keys.add(symbol_key)
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
                    "qualified_names": tuple(sorted(qualified_names)),
                }
            )

        routine_match = ROUTINE_DECL_RE.match(raw_line.strip())
        if routine_match is None:
            continue
        normalized_name, leaf_name = symbol_name_parts(str(routine_match.group("name") or ""))
        if (
            not normalized_name
            or not leaf_name
            or leaf_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        qualified_names = {leaf_name, normalized_name}
        if current_package:
            qualified_names.add(f"{current_package}.{leaf_name}")
        symbol_key = ("function", normalized_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": leaf_name,
                        "kind": "function",
                        "line": line_no,
                    },
                ),
                "symbol_name": leaf_name,
                "symbol_kind": "function",
                "start_line": line_no,
                "end_line": final_line,
                "signature": raw_line.strip(),
                "qualified_names": tuple(sorted(qualified_names)),
            }
        )

    if not symbol_entries:
        fallback_name = PurePosixPath(file_path).stem.lower()
        fallback_text = stripped_text.lower()
        if FALLBACK_SYMBOL_RE.fullmatch(fallback_name) and any(
            token in fallback_text
            for token in ("declare", "begin", "create ", "select ", "insert ", "update ")
        ):
            symbol_entries.append(
                {
                    "symbol_id": stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": fallback_name,
                            "kind": "type",
                            "line": 1,
                        },
                    ),
                    "symbol_name": fallback_name,
                    "symbol_kind": "type",
                    "start_line": 1,
                    "end_line": final_line,
                    "signature": fallback_name,
                    "qualified_names": (fallback_name,),
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
    suffix_lower = path.suffix.lower()
    if suffix_lower not in _KNOWN_PLSQL_SUFFIXES:
        return set()

    has_sibling_spec = suffix_lower == ".pkb" and (root_path / path.with_suffix(".pks")).is_file()
    aliases = {file_path.lower()}
    if not has_sibling_spec:
        without_suffix_path = str(path.with_suffix("")).lower()
        aliases.update(
            {
                path.stem.lower(),
                without_suffix_path,
                without_suffix_path.replace("/", "."),
            }
        )

    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias and alias not in {".", "/"}}

    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    if not has_sibling_spec:
        for symbol_entry in symbol_entries:
            aliases.update(
                str(alias).lower()
                for alias in symbol_entry["qualified_names"]
                if alias
            )
    if suffix_lower == ".pkb":
        package_names = [
            str(entry["symbol_name"]).lower()
            for entry in symbol_entries
            if str(entry["symbol_kind"]) == "module"
        ]
        for package_name in package_names:
            aliases.add(f"{package_name}.body")
            for symbol_entry in symbol_entries:
                if str(symbol_entry["symbol_kind"]) == "module":
                    continue
                symbol_name = str(symbol_entry["symbol_name"]).lower()
                if symbol_name:
                    aliases.add(f"{package_name}.body.{symbol_name}")
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def iter_package_body_imports(text: str) -> tuple[tuple[int, str], ...]:
    stripped_text = strip_comments(text)
    imports: list[tuple[int, str]] = []
    for match in CREATE_DECL_RE.finditer(stripped_text):
        raw_kind = re.sub(r"\s+", " ", str(match.group("kind") or "").strip().lower())
        if raw_kind != "package body":
            continue
        normalized_name, _leaf_name = symbol_name_parts(str(match.group("name") or ""))
        if not normalized_name:
            continue
        line_no = stripped_text.count("\n", 0, match.start()) + 1
        imports.append((line_no, normalized_name))
    return tuple(imports)


def iter_reference_targets(text: str) -> tuple[tuple[int, str, str], ...]:
    stripped_text = strip_comments(text)
    targets: list[tuple[int, str, str]] = []
    for regex, kind in (
        (RELATION_REFERENCE_RE, "relation"),
        (CALL_RE, "call"),
        (QUALIFIED_CALL_RE, "qualified_call"),
    ):
        for match in regex.finditer(stripped_text):
            target_name = str(match.group("name") or "").strip()
            if not target_name:
                continue
            line_no = stripped_text.count("\n", 0, match.start()) + 1
            targets.append((line_no, kind, target_name))
    return tuple(dict.fromkeys(targets))


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
    resolve_target: Callable[[str, dict[str, str]], str | None],
) -> tuple[dict[str, Any], ...]:
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for line_no, import_target in iter_package_body_imports(text):
        normalized_target, leaf_name = symbol_name_parts(import_target)
        if not normalized_target or not leaf_name:
            continue
        target_file = resolve_import(import_target, module_index)
        dependency_key = (target_file, leaf_name, "imports")
        if (
            target_file is None
            or target_file == file_path
            or dependency_key in dependency_keys
        ):
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": normalized_target,
                        "line": line_no,
                        "kind": "package_body_import",
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": leaf_name,
                "dependency_type": "imports",
            }
        )
    for line_no, reference_kind, raw_target in iter_reference_targets(text):
        normalized_target, leaf_name = symbol_name_parts(raw_target)
        if (
            not normalized_target
            or not leaf_name
            or leaf_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        target_file = resolve_target(raw_target, module_index)
        dependency_key = (target_file, leaf_name, "references")
        if (
            target_file is None
            or target_file == file_path
            or dependency_key in dependency_keys
        ):
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": normalized_target,
                        "line": line_no,
                        "kind": reference_kind,
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": leaf_name,
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
    resolve_import: Callable[[str, dict[str, str]], str | None],
    resolve_target: Callable[[str, dict[str, str]], str | None],
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
    reference_candidates: dict[str, dict[str, Any]] = {}
    stripped_lines = strip_comments(text).splitlines()
    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_name = str(symbol_entry["symbol_name"]).lower()
        symbol_id = str(symbol_entry["symbol_id"])
        snippet = "\n".join(stripped_lines[start_line - 1 : end_line])
        for _line_no, reference_kind, raw_target in iter_reference_targets(snippet):
            normalized_target, leaf_name = symbol_name_parts(raw_target)
            if (
                not normalized_target
                or not leaf_name
                or leaf_name in RESERVED_SYMBOL_NAMES
                or leaf_name == symbol_name
            ):
                continue
            target_file = resolve_target(raw_target, module_index)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (leaf_name,),
                    "type": "references_symbol",
                    "kind": reference_kind,
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
    return (
        symbol_entries,
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
            resolve_target=resolve_target,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
