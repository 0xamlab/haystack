from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".chpl"})
_MODULE_RE = re.compile(r"(?m)^\s*module\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_USE_IMPORT_RE = re.compile(
    r"(?m)^\s*(?:(?:public|private)\s+)?(?P<kind>use|import)\s+(?P<targets>[^;\n]+);"
)
_SYMBOL_RE = re.compile(
    r"(?m)^\s*(?:(?:public|private|override|inline|export|extern|required|config|param|type|ref|const|var)\s+)*"
    r"(?P<kind>proc|iter|class|record|union|enum|interface|operator)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*|[^\s(]+)"
)
_VARIABLE_RE = re.compile(
    r"(?m)^\s*(?:(?:public|private)\s+)?(?:(?:config|param|const|var|type)\s+)+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_STRING_OR_COMMENT_RE = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?(?:\*/|$)'
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_UNQUALIFIED_CALL_RE = re.compile(r"(?<!\.)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_MARKER_RE = re.compile(r"\b(?:module|use|import|proc|iter|class|record|enum)\b")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "align",
        "as",
        "begin",
        "borrowed",
        "break",
        "by",
        "catch",
        "class",
        "coforall",
        "config",
        "const",
        "continue",
        "delete",
        "dmapped",
        "do",
        "domain",
        "else",
        "enum",
        "except",
        "export",
        "extern",
        "for",
        "forall",
        "if",
        "implements",
        "import",
        "in",
        "index",
        "inline",
        "interface",
        "iter",
        "label",
        "lambda",
        "let",
        "local",
        "module",
        "new",
        "nil",
        "noinit",
        "on",
        "only",
        "operator",
        "otherwise",
        "override",
        "owned",
        "param",
        "private",
        "proc",
        "public",
        "record",
        "reduce",
        "ref",
        "return",
        "scan",
        "select",
        "serial",
        "shared",
        "single",
        "sparse",
        "subdomain",
        "sync",
        "then",
        "throw",
        "throws",
        "try",
        "type",
        "union",
        "unmanaged",
        "use",
        "var",
        "when",
        "where",
        "while",
        "with",
        "yield",
        "zip",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _mask_comment_match(match: re.Match[str]) -> str:
    token = match.group(0)
    if token.startswith("//"):
        return " " * len(token)
    if token.startswith("/*"):
        return "".join("\n" if character == "\n" else " " for character in token)
    return token


def strip_comments(text: str) -> str:
    if "//" not in text and "/*" not in text:
        return text
    return _STRING_OR_COMMENT_RE.sub(_mask_comment_match, text)


def has_chapel_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def module_name_from_path(file_path: str) -> str:
    return PurePosixPath(file_path).stem


def module_name_from_text(
    text: str,
    *,
    file_path: str,
    stripped_text: str | None = None,
) -> str:
    candidate_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    if "module" not in candidate_stripped_text:
        return module_name_from_path(file_path)
    match = _MODULE_RE.search(candidate_stripped_text)
    if match is not None:
        module_name = str(match.group("name") or "").strip()
        if module_name:
            return module_name
    return module_name_from_path(file_path)


def is_probable_chapel_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    if not has_chapel_path_hints(path):
        return False
    candidate_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    return bool(candidate_stripped_text.strip()) and bool(_MARKER_RE.search(candidate_stripped_text))


def _split_target_segments(raw_targets: str) -> tuple[str, ...]:
    segments: list[str] = []
    current: list[str] = []
    brace_depth = 0
    for character in raw_targets:
        if character == "{":
            brace_depth += 1
        elif character == "}":
            brace_depth = max(0, brace_depth - 1)
        if character == "," and brace_depth == 0:
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
            current = []
            continue
        current.append(character)
    tail = "".join(current).strip()
    if tail:
        segments.append(tail)
    return tuple(segments)


def _normalize_import_target(raw_target: str) -> tuple[str, str | None]:
    normalized_target = str(raw_target or "").strip()
    if not normalized_target:
        return "", None
    alias: str | None = None
    alias_match = re.search(r"\bas\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*$", normalized_target)
    if alias_match is not None:
        alias = str(alias_match.group("alias") or "").strip() or None
        normalized_target = normalized_target[: alias_match.start()].strip()
    for separator in (" only ", " except "):
        lowered = normalized_target.lower()
        index = lowered.find(separator)
        if index >= 0:
            normalized_target = normalized_target[:index].strip()
            break
    normalized_target = normalized_target.split("{", 1)[0].strip().rstrip(".")
    return normalized_target, alias


def parse_use_import_statements(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, str | None, int], ...]:
    candidate_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    if "use" not in candidate_stripped_text and "import" not in candidate_stripped_text:
        return ()
    statements: list[tuple[str, str, str | None, int]] = []
    seen: set[tuple[str, str, str | None, int]] = set()
    for line_number, raw_line in enumerate(candidate_stripped_text.splitlines(), start=1):
        candidate_line = raw_line.strip()
        if not candidate_line:
            continue
        if candidate_line.startswith("public "):
            candidate_line = candidate_line[len("public ") :].lstrip()
        elif candidate_line.startswith("private "):
            candidate_line = candidate_line[len("private ") :].lstrip()
        if candidate_line.startswith("use "):
            statement_kind = "use"
            targets = candidate_line[len("use ") :]
        elif candidate_line.startswith("import "):
            statement_kind = "import"
            targets = candidate_line[len("import ") :]
        else:
            continue
        statement_terminator = targets.find(";")
        if statement_terminator < 0:
            continue
        statement_targets = targets[:statement_terminator].strip()
        if not statement_targets:
            continue
        for segment in _split_target_segments(statement_targets):
            import_target, alias = _normalize_import_target(segment)
            if not import_target:
                continue
            item = (statement_kind, import_target, alias, line_number)
            if item in seen:
                continue
            seen.add(item)
            statements.append(item)
    return tuple(statements)


@lru_cache(maxsize=1024)
def _iter_symbol_entries_from_stripped_text(
    stripped_text: str,
    resolved_module_name: str,
) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, kind_group, name_group, default_kind in (
        (_SYMBOL_RE, "kind", "name", ""),
        (_VARIABLE_RE, "", "name", "variable"),
    ):
        for match in regex.finditer(stripped_text):
            symbol_name = str(match.group(name_group) or "").strip()
            symbol_kind = (
                str(match.group(kind_group) or "").strip().lower()
                if kind_group
                else default_kind
            )
            if (
                not symbol_name
                or symbol_name == resolved_module_name
                or symbol_name in seen_names
                or symbol_name in _RESERVED_SYMBOL_NAMES
            ):
                continue
            seen_names.add(symbol_name)
            entries.append(
                (symbol_name, symbol_kind, _line_number(stripped_text, match.start()))
            )
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_symbol_entries(
    text: str,
    *,
    file_path: str,
    stripped_text: str | None = None,
    module_name: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    candidate_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    resolved_module_name = (
        module_name
        if module_name is not None
        else module_name_from_text(
            text,
            file_path=file_path,
            stripped_text=candidate_stripped_text,
        )
    )
    return _iter_symbol_entries_from_stripped_text(
        candidate_stripped_text,
        resolved_module_name,
    )


def parse_reference_targets(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str | None, str, int], ...]:
    candidate_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    references: list[tuple[str | None, str, int]] = []
    seen: set[tuple[str | None, str, int]] = set()
    for match in _QUALIFIED_REFERENCE_RE.finditer(candidate_stripped_text):
        alias = str(match.group("alias") or "").strip()
        symbol_name = str(match.group("name") or "").strip()
        if (
            not alias
            or not symbol_name
            or alias in _RESERVED_SYMBOL_NAMES
            or symbol_name in _RESERVED_SYMBOL_NAMES
        ):
            continue
        item = (alias, symbol_name, _line_number(candidate_stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        references.append(item)
    for match in _UNQUALIFIED_CALL_RE.finditer(candidate_stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name or symbol_name in _RESERVED_SYMBOL_NAMES:
            continue
        item = (None, symbol_name, _line_number(candidate_stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        references.append(item)
    return tuple(references)
