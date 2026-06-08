from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]

_SOURCE_SUFFIXES = frozenset({".gms", ".inc"})
_KNOWN_SUFFIXES = _SOURCE_SUFFIXES
_GAMS_KEYWORDS = (
    "$include",
    "$batinclude",
    "$libinclude",
    "sets ",
    "set ",
    "parameters ",
    "parameter ",
    "scalars ",
    "scalar ",
    "tables ",
    "table ",
    "variables ",
    "variable ",
    "equations ",
    "equation ",
    "models ",
    "model ",
    "solve ",
    "alias(",
)
_INCLUDE_RE = re.compile(
    r"^\s*\$(?:include|batinclude|libinclude)\s+"
    r'(?P<target>"[^"]+"|\'[^\']+\'|[^\s;]+)',
    re.IGNORECASE | re.MULTILINE,
)
_STATEMENT_KEYWORD_RE = re.compile(
    r"^\s*(?P<keyword>"
    r"(?:positive|negative|binary|integer|free|semicont|semiint)\s+variables?"
    r"|(?:sets?|parameters?|scalars?|tables?|equations?|models?)"
    r")\b",
    re.IGNORECASE,
)
_EQUATION_DEF_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?\s*\.\.",
    re.MULTILINE,
)
_IDENTIFIER_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_STRING_RE = re.compile(r'"[^"\n]*"|\'[^\'\n]*\'')
_SLASH_SECTION_RE = re.compile(r"/.*?/", re.DOTALL)
_BUILTIN_NAMES = frozenset(
    {
        "abort",
        "acronym",
        "alias",
        "and",
        "binary",
        "card",
        "display",
        "else",
        "equation",
        "equations",
        "execute",
        "file",
        "for",
        "free",
        "if",
        "inf",
        "integer",
        "loop",
        "model",
        "models",
        "negative",
        "no",
        "not",
        "option",
        "or",
        "parameter",
        "parameters",
        "positive",
        "put",
        "sameas",
        "scalar",
        "scalars",
        "set",
        "sets",
        "solve",
        "sum",
        "table",
        "tables",
        "variable",
        "variables",
        "yes",
    }
)
_DECLARATION_KIND_MAP = {
    "set": "set",
    "sets": "set",
    "parameter": "parameter",
    "parameters": "parameter",
    "scalar": "scalar",
    "scalars": "scalar",
    "table": "table",
    "tables": "table",
    "equation": "equation",
    "equations": "equation",
    "model": "model",
    "models": "model",
    "variable": "variable",
    "variables": "variable",
    "positive variable": "variable",
    "positive variables": "variable",
    "negative variable": "variable",
    "negative variables": "variable",
    "binary variable": "variable",
    "binary variables": "variable",
    "integer variable": "variable",
    "integer variables": "variable",
    "free variable": "variable",
    "free variables": "variable",
    "semicont variable": "variable",
    "semicont variables": "variable",
    "semiint variable": "variable",
    "semiint variables": "variable",
}


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def strip_comments(text: str) -> str:
    result_lines: list[str] = []
    in_block_comment = False
    for raw_line in text.splitlines():
        stripped_line = raw_line.lstrip()
        lowered_line = stripped_line.lower()
        if in_block_comment:
            result_lines.append("")
            if lowered_line.startswith("$offtext"):
                in_block_comment = False
            continue
        if lowered_line.startswith("$ontext"):
            in_block_comment = True
            result_lines.append("")
            continue
        if stripped_line.startswith("*"):
            result_lines.append("")
            continue
        result_lines.append(raw_line.rstrip())
    return "\n".join(result_lines)


def has_gams_path_hints(path: Path) -> bool:
    return path.suffix.lower() in _KNOWN_SUFFIXES


def normalize_identifier(value: str) -> str:
    return str(value or "").strip()


def _normalize_repository_like_path(value: str) -> str:
    normalized_parts: list[str] = []
    for part in PurePosixPath(str(value or "").replace("\\", "/")).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts and normalized_parts[-1] != "..":
                normalized_parts.pop()
            else:
                normalized_parts.append(part)
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def normalize_import_target(value: str) -> str:
    return _normalize_repository_like_path(str(value or "").strip().strip("\"'"))


def import_targets_for_text(text: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen_targets: set[str] = set()
    for match in _INCLUDE_RE.finditer(text):
        normalized_target = normalize_import_target(str(match.group("target") or ""))
        if not normalized_target or normalized_target.lower() in seen_targets:
            continue
        seen_targets.add(normalized_target.lower())
        targets.append(normalized_target)
    return tuple(targets)


def is_probable_gams_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix not in _KNOWN_SUFFIXES:
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    lowered_text = stripped_text.lower()
    if any(keyword in lowered_text for keyword in _GAMS_KEYWORDS):
        return True
    if _EQUATION_DEF_RE.search(stripped_text):
        return True
    return suffix == ".gms"


def module_symbol_name(file_path: str) -> str:
    return PurePosixPath(file_path).stem.strip()


def _statement_blocks(text: str) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    current_lines: list[str] = []
    block_start = 1
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped_line = raw_line.lstrip()
        if not current_lines and not raw_line.strip():
            continue
        if not current_lines:
            block_start = line_number
        current_lines.append(raw_line)
        if stripped_line.startswith("$"):
            blocks.append((block_start, line_number, "\n".join(current_lines)))
            current_lines = []
            continue
        if ";" not in raw_line:
            continue
        blocks.append((block_start, line_number, "\n".join(current_lines)))
        current_lines = []
    if current_lines:
        blocks.append((block_start, _line_count(text), "\n".join(current_lines)))
    return blocks


def _clean_declaration_body(body: str) -> str:
    cleaned_body = _STRING_RE.sub(" ", body)
    cleaned_body = _SLASH_SECTION_RE.sub(" ", cleaned_body)
    cleaned_body = cleaned_body.replace(";", " ")
    return cleaned_body


def _extract_declared_names(body: str) -> tuple[str, ...]:
    names: list[str] = []
    seen_names: set[str] = set()
    for raw_line in body.splitlines():
        if not raw_line.strip():
            continue
        for clause in raw_line.split(","):
            match = _IDENTIFIER_RE.search(clause)
            if match is None:
                continue
            name = normalize_identifier(str(match.group("name") or ""))
            if not name or name.lower() in seen_names or name.lower() in _BUILTIN_NAMES:
                continue
            seen_names.add(name.lower())
            names.append(name)
    return tuple(names)


def collect_symbol_entries(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    source_text = strip_comments(text)
    if not source_text.strip():
        return []
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    module_name = module_symbol_name(file_path)

    for start_line, end_line, block_text in _statement_blocks(source_text):
        keyword_match = _STATEMENT_KEYWORD_RE.match(block_text)
        if keyword_match is None:
            continue
        raw_keyword = normalize_identifier(str(keyword_match.group("keyword") or "")).lower()
        symbol_kind = _DECLARATION_KIND_MAP.get(raw_keyword)
        if symbol_kind is None:
            continue
        body = _clean_declaration_body(block_text[keyword_match.end() :])
        for symbol_name in _extract_declared_names(body):
            symbol_key = (symbol_kind, symbol_name.lower(), start_line)
            if symbol_key in seen_symbol_keys:
                continue
            seen_symbol_keys.add(symbol_key)
            qualified_names = {symbol_name}
            if module_name:
                qualified_names.add(f"{module_name}.{symbol_name}")
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
                    "end_line": end_line,
                    "signature": block_text.strip(),
                    "parent_symbol_id": None,
                    "qualified_names": tuple(sorted(qualified_names)),
                }
            )

    for match in _EQUATION_DEF_RE.finditer(source_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name or symbol_name.lower() in _BUILTIN_NAMES:
            continue
        line_number = source_text.count("\n", 0, match.start()) + 1
        symbol_key = ("equation", symbol_name.lower(), line_number)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        statement_end = source_text.find(";", match.start())
        end_line = (
            source_text.count("\n", 0, statement_end) + 1
            if statement_end >= 0
            else _line_count(source_text)
        )
        qualified_names = {symbol_name}
        if module_name:
            qualified_names.add(f"{module_name}.{symbol_name}")
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "kind": "equation",
                        "line": line_number,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": "equation",
                "start_line": line_number,
                "end_line": end_line,
                "signature": match.group(0).strip(),
                "parent_symbol_id": None,
                "qualified_names": tuple(sorted(qualified_names)),
            }
        )

    return sorted(
        symbol_entries,
        key=lambda entry: (
            int(entry["start_line"]),
            str(entry["symbol_kind"]),
            str(entry["symbol_name"]).lower(),
            str(entry["symbol_id"]),
        ),
    )
