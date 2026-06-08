from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveInclude = Callable[[str, str, dict[str, str]], str | None]
ResolveTarget = Callable[[str, dict[str, str]], str | None]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abstract",
        "alias",
        "and",
        "append",
        "assign",
        "break-point",
        "call",
        "case",
        "catch",
        "changing",
        "check",
        "class",
        "class-data",
        "class-methods",
        "clear",
        "constants",
        "continue",
        "create",
        "data",
        "define",
        "delete",
        "do",
        "else",
        "elseif",
        "endat",
        "endcase",
        "endclass",
        "enddo",
        "endenhancement-section",
        "endform",
        "endfunction",
        "endif",
        "endinterface",
        "endloop",
        "endmethod",
        "endmodule",
        "endselect",
        "endtry",
        "endwhile",
        "exporting",
        "false",
        "field-symbols",
        "final",
        "form",
        "function",
        "function-pool",
        "if",
        "importing",
        "include",
        "inherits",
        "inheriting",
        "interface",
        "interfaces",
        "loop",
        "method",
        "methods",
        "module",
        "new",
        "not",
        "or",
        "perform",
        "private",
        "protected",
        "public",
        "raise",
        "raising",
        "read",
        "report",
        "returning",
        "select",
        "static",
        "structures",
        "try",
        "type",
        "types",
        "using",
        "value",
        "when",
        "while",
    }
)
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
METHOD_NAME_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:~[A-Za-z_][A-Za-z0-9_]*)?$"
)
CLASS_RE = re.compile(
    r"^CLASS\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+"
    r"(?:DEFINITION|IMPLEMENTATION)\b",
    re.IGNORECASE,
)
INTERFACE_RE = re.compile(
    r"^INTERFACE\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
PROGRAM_RE = re.compile(
    r"^(?:REPORT|PROGRAM|FUNCTION-POOL)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
FORM_RE = re.compile(r"^FORM\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE)
FUNCTION_RE = re.compile(
    r"^FUNCTION\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
METHOD_IMPL_RE = re.compile(
    r"^METHOD\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:~[A-Za-z_][A-Za-z0-9_]*)?)\b",
    re.IGNORECASE,
)
METHOD_DECL_RE = re.compile(
    r"^(?:CLASS-)?METHODS?\s*:?\s*(?P<body>.+)$",
    re.IGNORECASE,
)
INCLUDE_RE = re.compile(
    r"^INCLUDE\s+(?!TYPE\b)(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
    r"(?:\s+IF\s+FOUND)?$",
    re.IGNORECASE,
)
STATIC_CALL_RE = re.compile(
    r"\b(?P<prefix>[A-Za-z_][A-Za-z0-9_]*)=>(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.IGNORECASE,
)
PERFORM_RE = re.compile(
    r"\bPERFORM\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
CALL_FUNCTION_RE = re.compile(
    r"\bCALL\s+FUNCTION\s+(?:'(?P<single>[^']+)'|`(?P<backtick>[^`]+)`)",
    re.IGNORECASE,
)
INTERFACES_RE = re.compile(r"^INTERFACES\s*:?\s*(?P<body>.+)$", re.IGNORECASE)
INHERITING_RE = re.compile(
    r"\bINHERITING\s+FROM\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
TYPE_REF_RE = re.compile(
    r"\bTYPE\s+REF\s+TO\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
NEW_RE = re.compile(r"\bNEW\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(", re.IGNORECASE)
KNOWN_ABAP_SUFFIXES = (".abap",)


def normalize_identifier(raw_name: str) -> str:
    return raw_name.strip().strip(".").lower()


def normalize_leaf_name(raw_name: str) -> str:
    normalized_name = normalize_identifier(raw_name)
    if not normalized_name:
        return ""
    return normalized_name.rsplit("~", 1)[-1].rsplit(".", 1)[-1]


def normalize_target(raw_target: str) -> str:
    return normalize_identifier(raw_target.replace("\\", "/"))


def _normalize_repository_relative_path(value: str) -> str:
    raw_parts = PurePosixPath(str(value).replace("\\", "/")).parts
    normalized_parts: list[str] = []
    for part in raw_parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def strip_comments(text: str) -> str:
    processed_lines: list[str] = []
    for raw_line in text.splitlines(keepends=True):
        if raw_line.lstrip().startswith("*"):
            processed_lines.append(
                "".join("\n" if character == "\n" else " " for character in raw_line)
            )
            continue
        line_parts: list[str] = []
        in_single_quote = False
        in_backtick = False
        index = 0
        while index < len(raw_line):
            character = raw_line[index]
            if character == "\n":
                line_parts.append("\n")
                index += 1
                continue
            if character == "'" and not in_backtick:
                if (
                    in_single_quote
                    and index + 1 < len(raw_line)
                    and raw_line[index + 1] == "'"
                ):
                    line_parts.append("''")
                    index += 2
                    continue
                in_single_quote = not in_single_quote
                line_parts.append(character)
                index += 1
                continue
            if character == "`" and not in_single_quote:
                if (
                    in_backtick
                    and index + 1 < len(raw_line)
                    and raw_line[index + 1] == "`"
                ):
                    line_parts.append("``")
                    index += 2
                    continue
                in_backtick = not in_backtick
                line_parts.append(character)
                index += 1
                continue
            if character == '"' and not in_single_quote and not in_backtick:
                line_parts.extend(
                    " " if value != "\n" else "\n" for value in raw_line[index:]
                )
                break
            line_parts.append(character)
            index += 1
        processed_lines.append("".join(line_parts))
    return "".join(processed_lines)


def _is_statement_terminator(line: str, index: int) -> bool:
    if line[index] != ".":
        return False
    if index + 1 < len(line) and not line[index + 1].isspace():
        return False
    return True


def statement_entries(text: str) -> tuple[tuple[int, str], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[int, str]] = []
    buffer_parts: list[str] = []
    buffer_start_line: int | None = None
    in_single_quote = False
    in_backtick = False
    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        index = 0
        while index < len(raw_line):
            character = raw_line[index]
            if buffer_start_line is None and not character.isspace():
                buffer_start_line = line_no
            if character == "'" and not in_backtick:
                if (
                    in_single_quote
                    and index + 1 < len(raw_line)
                    and raw_line[index + 1] == "'"
                ):
                    buffer_parts.append("''")
                    index += 2
                    continue
                in_single_quote = not in_single_quote
                buffer_parts.append(character)
                index += 1
                continue
            if character == "`" and not in_single_quote:
                if (
                    in_backtick
                    and index + 1 < len(raw_line)
                    and raw_line[index + 1] == "`"
                ):
                    buffer_parts.append("``")
                    index += 2
                    continue
                in_backtick = not in_backtick
                buffer_parts.append(character)
                index += 1
                continue
            if (
                not in_single_quote
                and not in_backtick
                and _is_statement_terminator(raw_line, index)
            ):
                statement = " ".join("".join(buffer_parts).split())
                if statement:
                    statements.append((buffer_start_line or line_no, statement))
                buffer_parts = []
                buffer_start_line = None
                index += 1
                continue
            buffer_parts.append(character)
            index += 1
        if buffer_parts:
            buffer_parts.append(" ")
    trailing_statement = " ".join("".join(buffer_parts).split())
    if trailing_statement:
        statements.append((buffer_start_line or 1, trailing_statement))
    return tuple(statements)


def _stem_without_abap(path: PurePosixPath) -> str:
    if path.suffix.lower() not in KNOWN_ABAP_SUFFIXES:
        return ""
    return path.name[: -len(".abap")].lower()


def owning_object_name_for_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    stem_without_abap = _stem_without_abap(path)
    if not stem_without_abap:
        return path.stem.lower()
    for suffix in (
        ".clas.locals_def",
        ".clas.locals_imp",
        ".clas.testclasses",
        ".clas",
        ".intf",
        ".prog",
    ):
        if stem_without_abap.endswith(suffix):
            return stem_without_abap[: -len(suffix)]
    if ".fugr." in stem_without_abap:
        return stem_without_abap.split(".fugr.", 1)[0]
    return path.stem.lower()


def include_member_name_for_path(file_path: str) -> str:
    stem_without_abap = _stem_without_abap(PurePosixPath(file_path))
    if ".fugr." not in stem_without_abap:
        return ""
    return stem_without_abap.split(".fugr.", 1)[1]


def is_primary_object_file(file_path: str) -> bool:
    stem_without_abap = _stem_without_abap(PurePosixPath(file_path))
    if not stem_without_abap:
        return False
    if stem_without_abap.endswith((".clas", ".intf", ".prog")):
        return True
    if ".fugr." not in stem_without_abap:
        return False
    return stem_without_abap.split(".fugr.", 1)[1].startswith("sapl")


def iter_method_declaration_names(statement: str) -> tuple[str, ...]:
    match = METHOD_DECL_RE.match(statement)
    if match is None:
        return ()
    body = str(match.group("body") or "").strip()
    if not body:
        return ()
    method_names: list[str] = []
    seen_names: set[str] = set()
    for segment in body.split(","):
        candidate = segment.strip()
        if not candidate:
            continue
        raw_name = candidate.split()[0].strip()
        normalized_name = normalize_identifier(raw_name)
        if (
            not normalized_name
            or normalized_name in RESERVED_SYMBOL_NAMES
            or normalized_name in seen_names
            or METHOD_NAME_RE.fullmatch(raw_name) is None
        ):
            continue
        seen_names.add(normalized_name)
        method_names.append(normalized_name)
    return tuple(method_names)


def iter_interface_targets(statement: str) -> tuple[str, ...]:
    match = INTERFACES_RE.match(statement)
    if match is None:
        return ()
    body = str(match.group("body") or "").strip()
    if not body:
        return ()
    targets: list[str] = []
    seen_targets: set[str] = set()
    for segment in body.split(","):
        raw_name = segment.strip().split()[0] if segment.strip() else ""
        normalized_name = normalize_identifier(raw_name)
        if (
            not normalized_name
            or normalized_name in RESERVED_SYMBOL_NAMES
            or normalized_name in seen_targets
            or IDENTIFIER_RE.fullmatch(raw_name) is None
        ):
            continue
        seen_targets.add(normalized_name)
        targets.append(normalized_name)
    return tuple(targets)
