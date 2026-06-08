from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]

INCLUDE_RE = re.compile(
    r"^\s*(?:require|require_once|include|include_once)\s*(?:\(\s*)?['\"](?P<target>[^'\"]+)['\"]",
    re.MULTILINE,
)
NAMESPACE_RE = re.compile(
    r"^\s*namespace\s+(?P<target>[A-Za-z_\\][A-Za-z0-9_\\]*)\s*[;{]",
    re.MULTILINE,
)
USE_RE = re.compile(
    r"^\s*use\s+(?:(?:function|const)\s+)?(?P<target>[A-Za-z_\\][A-Za-z0-9_\\]+)"
    r"(?:\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?\s*;",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:abstract\s+|final\s+)?(?P<kind>class|interface|trait|enum)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:public|protected|private|static|abstract|final|readonly|\s)*function\s+&?\s*"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)::(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
TYPE_REFERENCE_RE = re.compile(
    r"\b(?:new|extends|implements|instanceof)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
TRAIT_USE_RE = re.compile(
    r"^\s*use\s+(?!function\b|const\b)(?P<body>[A-Za-z_\\][A-Za-z0-9_\\]*(?:\s*,\s*[A-Za-z_\\][A-Za-z0-9_\\]*)*)\s*;",
    re.MULTILINE,
)
DOC_TAG_RE = re.compile(
    r"^\s*\*\s*@(?P<tag>[A-Za-z0-9_-]+)\s+(?P<body>.+)$",
    re.MULTILINE,
)
DOC_TYPE_TOKEN_RE = re.compile(
    r"\\?[A-Z][A-Za-z0-9_]*(?:\\[A-Z][A-Za-z0-9_]*)*"
)
VARIABLE_TYPE_TOKEN_RE = re.compile(
    r"(?P<name>\\?[A-Z][A-Za-z0-9_]*(?:\\[A-Z][A-Za-z0-9_]*)*)(?=\s+\$[A-Za-z_][A-Za-z0-9_]*)"
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "__construct",
        "__destruct",
        "__invoke",
        "abstract",
        "and",
        "array",
        "as",
        "break",
        "callable",
        "case",
        "catch",
        "class",
        "clone",
        "const",
        "continue",
        "declare",
        "default",
        "die",
        "do",
        "echo",
        "else",
        "elseif",
        "empty",
        "enddeclare",
        "endfor",
        "endforeach",
        "endif",
        "endswitch",
        "endwhile",
        "enum",
        "eval",
        "exit",
        "extends",
        "false",
        "final",
        "finally",
        "fn",
        "for",
        "foreach",
        "function",
        "global",
        "goto",
        "if",
        "implements",
        "include",
        "include_once",
        "instanceof",
        "insteadof",
        "interface",
        "isset",
        "list",
        "match",
        "namespace",
        "new",
        "null",
        "or",
        "parent",
        "print",
        "private",
        "protected",
        "public",
        "readonly",
        "require",
        "require_once",
        "return",
        "self",
        "static",
        "switch",
        "throw",
        "trait",
        "true",
        "try",
        "unset",
        "use",
        "var",
        "while",
        "xor",
        "yield",
    }
)


def current_namespace(text: str) -> str:
    namespace_match = NAMESPACE_RE.search(text)
    if namespace_match is None:
        return ""
    return str(namespace_match.group("target") or "").strip()


def leading_docblock(text: str, *, offset: int) -> str:
    prefix = text[:offset]
    trimmed_prefix = prefix.rstrip()
    if not trimmed_prefix.endswith("*/"):
        return ""
    docblock_end = len(trimmed_prefix)
    docblock_start = prefix.rfind("/**", 0, docblock_end)
    if docblock_start < 0:
        return ""
    if prefix[docblock_end:].strip():
        return ""
    return prefix[docblock_start:docblock_end]


def symbol_declaration_header(snippet: str) -> str:
    collected_lines: list[str] = []
    for line in snippet.splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            if collected_lines:
                break
            continue
        collected_lines.append(stripped_line)
        if "{" in stripped_line or stripped_line.endswith(";"):
            break
    return " ".join(collected_lines)


def doc_type_tokens(docblock: str) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()
    for match in DOC_TAG_RE.finditer(docblock):
        body = str(match.group("body") or "").strip()
        if not body:
            continue
        for token_match in DOC_TYPE_TOKEN_RE.finditer(body):
            token = str(token_match.group(0) or "").lstrip("\\").strip()
            if not token or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tuple(tokens)


def type_tokens_from_header(header: str) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()
    for match in DOC_TYPE_TOKEN_RE.finditer(header):
        token = str(match.group(0) or "").lstrip("\\").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tuple(tokens)


def _symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier | None,
    include_symbol_kind_in_key: bool,
) -> list[dict[str, Any]]:
    lines = text.splitlines()
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int] | tuple[str, int, str]] = set()
    for regex, symbol_kind in (
        (TYPE_DECL_RE, "type"),
        (FUNCTION_DECL_RE, "function"),
    ):
        for match in regex.finditer(text):
            symbol_name = str(match.group("name") or "").strip()
            if not symbol_name or symbol_name in RESERVED_SYMBOL_NAMES:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            symbol_key: tuple[str, int] | tuple[str, int, str]
            if include_symbol_kind_in_key:
                symbol_key = (symbol_name, line_no, symbol_kind)
            else:
                symbol_key = (symbol_name, line_no)
            if symbol_key in seen_symbol_keys:
                continue
            seen_symbol_keys.add(symbol_key)
            entry: dict[str, Any] = {
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": line_no,
                "end_line": line_no,
                "signature": symbol_name,
                "match_start": match.start(),
            }
            if stable_identifier is not None:
                entry["symbol_id"] = stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "line": line_no,
                        "kind": symbol_kind,
                    },
                )
            symbol_entries.append(entry)
    symbol_entries.sort(key=lambda entry: int(entry["start_line"]))
    final_line = len(lines) if lines else 1
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries
