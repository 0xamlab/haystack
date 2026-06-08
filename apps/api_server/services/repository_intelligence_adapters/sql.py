from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveTarget = Callable[[str, dict[str, str]], str | None]

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "all",
        "alter",
        "and",
        "as",
        "by",
        "call",
        "case",
        "create",
        "cross",
        "delete",
        "desc",
        "distinct",
        "drop",
        "else",
        "end",
        "exists",
        "from",
        "full",
        "function",
        "group",
        "having",
        "if",
        "in",
        "inner",
        "insert",
        "into",
        "join",
        "left",
        "limit",
        "materialized",
        "merge",
        "not",
        "null",
        "offset",
        "on",
        "only",
        "or",
        "order",
        "outer",
        "procedure",
        "references",
        "replace",
        "returning",
        "right",
        "select",
        "set",
        "table",
        "then",
        "truncate",
        "union",
        "update",
        "using",
        "values",
        "view",
        "when",
        "where",
        "with",
    }
)
IDENTIFIER_SEGMENT_PATTERN = r'(?:`[^`]+`|"[^"]+"|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_$]*)'
COMPOUND_IDENTIFIER_PATTERN = (
    rf"{IDENTIFIER_SEGMENT_PATTERN}(?:\s*\.\s*{IDENTIFIER_SEGMENT_PATTERN}){{0,2}}"
)
CREATE_DECL_RE = re.compile(
    r"\bcreate\s+(?:or\s+(?:replace|alter)\s+)?(?:(?:temporary|temp|transient)\s+)?"
    r"(?P<kind>materialized\s+view|table|view|function|proc(?:edure)?)\s+"
    r"(?:if\s+not\s+exists\s+)?(?P<name>"
    + COMPOUND_IDENTIFIER_PATTERN
    + r")",
    re.IGNORECASE,
)
RELATION_REFERENCE_RE = re.compile(
    r"\b(?:from|join|into|update|delete\s+from|merge\s+into|truncate\s+table|"
    r"alter\s+table|references)\s+(?:only\s+)?(?P<name>"
    + COMPOUND_IDENTIFIER_PATTERN
    + r")",
    re.IGNORECASE,
)
CALL_RE = re.compile(
    r"\bcall\s+(?P<name>" + COMPOUND_IDENTIFIER_PATTERN + r")\s*\(",
    re.IGNORECASE,
)
DBT_REF_RE = re.compile(
    r"\{\{\s*ref\s*\(\s*['\"](?P<name>[^'\"]+)['\"]\s*\)\s*\}\}",
    re.IGNORECASE,
)
FALLBACK_SYMBOL_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def strip_comments(text: str) -> str:
    def _replace_block_comment(match: re.Match[str]) -> str:
        return "\n" * str(match.group(0)).count("\n")

    without_block_comments = re.sub(
        r"/\*.*?\*/",
        _replace_block_comment,
        text,
        flags=re.DOTALL,
    )
    stripped_lines = [
        raw_line.split("--", 1)[0]
        for raw_line in without_block_comments.splitlines()
    ]
    return "\n".join(stripped_lines)


def normalize_identifier(raw_name: str) -> str:
    normalized_segments: list[str] = []
    for raw_segment in re.split(r"\s*\.\s*", raw_name.strip()):
        segment = raw_segment.strip()
        if not segment:
            continue
        if (
            (segment.startswith("[") and segment.endswith("]"))
            or (segment.startswith("`") and segment.endswith("`"))
            or (segment.startswith('"') and segment.endswith('"'))
        ):
            segment = segment[1:-1].strip()
        if not segment:
            continue
        normalized_segments.append(segment.lower())
    return ".".join(normalized_segments)


def symbol_name_parts(symbol_name: str) -> tuple[str, str]:
    normalized_name = normalize_identifier(symbol_name)
    leaf_name = normalized_name.rsplit(".", 1)[-1] if normalized_name else ""
    return normalized_name, leaf_name


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    stripped_text = strip_comments(text)
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
            "function"
            if raw_kind in {"function", "proc", "procedure"}
            else "type"
        )
        line_no = stripped_text.count("\n", 0, match.start()) + 1
        symbol_key = (symbol_kind, normalized_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        signature = str(match.group(0) or "").strip()
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
                "end_line": line_no,
                "signature": signature,
                "qualified_names": tuple(sorted({leaf_name, normalized_name})),
            }
        )
    if not symbol_entries:
        fallback_name = PurePosixPath(file_path).stem.lower()
        if FALLBACK_SYMBOL_RE.fullmatch(fallback_name):
            fallback_text = stripped_text.lower()
            if any(
                token in fallback_text
                for token in ("select", "with", "insert", "update", "{{ ref(")
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
    if path.suffix.lower() != ".sql":
        return set()
    aliases = {
        file_path.lower(),
        path.stem.lower(),
    }
    without_suffix_path = str(path.with_suffix("")).lower()
    aliases.add(without_suffix_path)
    aliases.add(without_suffix_path.replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(
            str(alias).lower() for alias in symbol_entry["qualified_names"] if alias
        )
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


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
        suffixes=[
            f"{normalized_target}.sql",
            f"{normalized_target.replace('.', '/')}.sql",
            f"{leaf_name}.sql" if leaf_name else "",
        ],
    )


def iter_reference_targets(text: str) -> tuple[tuple[int, str, str], ...]:
    stripped_text = strip_comments(text)
    targets: list[tuple[int, str, str]] = []
    for match in DBT_REF_RE.finditer(stripped_text):
        target_name = str(match.group("name") or "").strip()
        if not target_name:
            continue
        line_no = stripped_text.count("\n", 0, match.start()) + 1
        targets.append((line_no, "dbt_ref", target_name))
    for regex, kind in (
        (RELATION_REFERENCE_RE, "relation"),
        (CALL_RE, "call"),
    ):
        for match in regex.finditer(stripped_text):
            target_name = str(match.group("name") or "").strip()
            if not target_name:
                continue
            line_no = stripped_text.count("\n", 0, match.start()) + 1
            targets.append((line_no, kind, target_name))
    return tuple(targets)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_target: ResolveTarget,
) -> tuple[dict[str, Any], ...]:
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
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
            resolve_target=resolve_target,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
