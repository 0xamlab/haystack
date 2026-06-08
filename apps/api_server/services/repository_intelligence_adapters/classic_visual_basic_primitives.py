from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveDirectoryPrefixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

_KNOWN_CLASSIC_VISUAL_BASIC_SUFFIXES = (".bas", ".cls", ".ctl", ".frm", ".vbp")
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "alias",
        "and",
        "as",
        "attribute",
        "boolean",
        "byte",
        "byref",
        "byval",
        "call",
        "case",
        "class",
        "const",
        "date",
        "debug",
        "declare",
        "dim",
        "do",
        "double",
        "each",
        "else",
        "elseif",
        "empty",
        "end",
        "enum",
        "eqv",
        "event",
        "exit",
        "explicit",
        "false",
        "for",
        "friend",
        "function",
        "get",
        "gosub",
        "goto",
        "if",
        "implements",
        "imp",
        "integer",
        "is",
        "let",
        "lib",
        "like",
        "long",
        "loop",
        "me",
        "mod",
        "new",
        "next",
        "not",
        "nothing",
        "object",
        "on",
        "option",
        "optional",
        "or",
        "preserve",
        "private",
        "property",
        "public",
        "redim",
        "rem",
        "resume",
        "return",
        "select",
        "set",
        "single",
        "static",
        "step",
        "string",
        "sub",
        "then",
        "to",
        "true",
        "type",
        "variant",
        "wend",
        "while",
        "with",
        "withevents",
        "xor",
    }
)
BUILTIN_TYPE_NAMES = frozenset(
    {
        "boolean",
        "byte",
        "currency",
        "date",
        "double",
        "integer",
        "long",
        "object",
        "single",
        "string",
        "variant",
    }
)
ATTRIBUTE_VB_NAME_RE = re.compile(
    r'^\s*Attribute\s+VB_Name\s*=\s*"(?P<name>[^"]+)"\s*$',
    re.MULTILINE | re.IGNORECASE,
)
BEGIN_COMPONENT_RE = re.compile(
    r"^\s*(?:VERSION\s+\d+\.\d+\s+)?Begin\s+VB\."
    r"(?P<kind>Form|MDIForm|UserControl)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
CLASS_VERSION_RE = re.compile(
    r"^\s*VERSION\s+\d+\.\d+\s+CLASS\b",
    re.MULTILINE | re.IGNORECASE,
)
OPTION_EXPLICIT_RE = re.compile(r"^\s*Option\s+Explicit\b", re.MULTILINE | re.IGNORECASE)
ROUTINE_DECL_RE = re.compile(
    r"^\s*(?:(?:Public|Private|Friend|Static)\s+)*"
    r"(?:(?:Sub|Function|Event)\s+|Property\s+(?:Get|Let|Set)\s+)"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:(?:Public|Private|Friend)\s+)*(?:Enum|Type)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
PROJECT_NAME_RE = re.compile(
    r'^\s*Name\s*=\s*"?(?P<name>[^"\r\n]+)"?\s*$',
    re.MULTILINE | re.IGNORECASE,
)
PROJECT_STARTUP_RE = re.compile(
    r'^\s*Startup\s*=\s*"?(?P<name>[^"\r\n]+)"?\s*$',
    re.MULTILINE | re.IGNORECASE,
)
PROJECT_COMPONENT_RE = re.compile(
    r"^\s*(?P<kind>Class|Module|Form|MDIForm|UserControl)\s*=\s*(?P<value>.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
VARIABLE_TYPE_BINDING_RE = re.compile(
    r"^\s*(?:(?:Private|Public|Friend|Dim|Static)\s+)*(?:WithEvents\s+)?"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+As\s+(?:New\s+)?"
    r"(?P<type>[A-Za-z_][A-Za-z0-9_\.]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
SET_NEW_BINDING_RE = re.compile(
    r"\bSet\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*New\s+"
    r"(?P<type>[A-Za-z_][A-Za-z0-9_\.]*)\b",
    re.IGNORECASE,
)
TYPE_REFERENCE_RE = re.compile(
    r"\b(?:As\s+New|As|New|Implements)\s+(?P<name>[A-Za-z_][A-Za-z0-9_\.]*)\b",
    re.IGNORECASE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
UNQUALIFIED_CALL_RE = re.compile(
    r"(?<!\.)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b\s*(?=\()",
    re.IGNORECASE,
)


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


def _strip_inline_comment(raw_line: str) -> str:
    if raw_line.lstrip().lower().startswith("rem "):
        return ""
    chars: list[str] = []
    index = 0
    in_string = False
    while index < len(raw_line):
        character = raw_line[index]
        if character == '"':
            chars.append(character)
            if in_string and index + 1 < len(raw_line) and raw_line[index + 1] == '"':
                chars.append('"')
                index += 2
                continue
            in_string = not in_string
            index += 1
            continue
        if character == "'" and not in_string:
            break
        chars.append(character)
        index += 1
    return "".join(chars)


def strip_comments(text: str) -> str:
    return "\n".join(_strip_inline_comment(line) for line in text.splitlines())


def normalize_target(raw_target: str) -> str:
    return str(raw_target or "").strip().strip('";').strip()


def normalize_symbol_name(raw_name: str) -> str:
    return str(raw_name or "").strip().strip('";').strip()


def component_name(text: str, *, file_path: str | None = None) -> str:
    attribute_match = ATTRIBUTE_VB_NAME_RE.search(text)
    if attribute_match is not None:
        return normalize_symbol_name(str(attribute_match.group("name") or ""))
    begin_match = BEGIN_COMPONENT_RE.search(text)
    if begin_match is not None:
        return normalize_symbol_name(str(begin_match.group("name") or ""))
    if file_path:
        return PurePosixPath(file_path).stem
    return ""


def project_name(text: str) -> str:
    match = PROJECT_NAME_RE.search(text)
    if match is None:
        return ""
    return normalize_symbol_name(str(match.group("name") or ""))


def project_startup_name(text: str) -> str:
    match = PROJECT_STARTUP_RE.search(text)
    if match is None:
        return ""
    return normalize_symbol_name(str(match.group("name") or ""))


def is_probable_classic_visual_basic_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix not in _KNOWN_CLASSIC_VISUAL_BASIC_SUFFIXES:
        return False
    if suffix == ".vbp":
        return bool(
            PROJECT_COMPONENT_RE.search(text)
            and (PROJECT_STARTUP_RE.search(text) or PROJECT_NAME_RE.search(text))
        )
    stripped_text = strip_comments(text)
    if ATTRIBUTE_VB_NAME_RE.search(stripped_text) is not None:
        return True
    if BEGIN_COMPONENT_RE.search(stripped_text) is not None:
        return True
    if suffix == ".cls" and CLASS_VERSION_RE.search(text) is not None:
        return True
    marker_count = sum(
        1
        for condition in (
            OPTION_EXPLICIT_RE.search(stripped_text) is not None,
            ROUTINE_DECL_RE.search(stripped_text) is not None,
            TYPE_DECL_RE.search(stripped_text) is not None,
            TYPE_REFERENCE_RE.search(stripped_text) is not None,
            "End Sub" in stripped_text or "End Function" in stripped_text,
        )
        if condition
    )
    return marker_count >= 2


def _component_symbol_kind(path: PurePosixPath) -> str:
    if path.suffix.lower() in {".bas", ".vbp"}:
        return "module"
    return "type"


def _component_declaration_line(text: str) -> int:
    for regex in (ATTRIBUTE_VB_NAME_RE, BEGIN_COMPONENT_RE, CLASS_VERSION_RE):
        match = regex.search(text)
        if match is not None:
            return text.count("\n", 0, match.start()) + 1
    return 1


def project_component_entries(
    text: str,
    *,
    manifest_path: str,
) -> tuple[dict[str, str], ...]:
    normalized_manifest_path = _normalize_repository_relative_path(manifest_path)
    project_dir = PurePosixPath(normalized_manifest_path).parent
    entries: list[dict[str, str]] = []
    seen_entries: set[tuple[str, str, str]] = set()
    for match in PROJECT_COMPONENT_RE.finditer(text):
        component_kind = normalize_symbol_name(str(match.group("kind") or "")).lower()
        raw_value = str(match.group("value") or "").strip()
        if not component_kind or not raw_value:
            continue
        component_name_value = ""
        component_path_value = raw_value
        if ";" in raw_value:
            component_name_value, component_path_value = raw_value.split(";", 1)
        normalized_component_path = _normalize_repository_relative_path(
            str(project_dir / normalize_target(component_path_value))
        )
        if not normalized_component_path or normalized_component_path.startswith("/"):
            continue
        normalized_component_name = normalize_symbol_name(component_name_value)
        if not normalized_component_name:
            normalized_component_name = PurePosixPath(normalized_component_path).stem
        entry_key = (
            component_kind,
            normalized_component_name.lower(),
            normalized_component_path.lower(),
        )
        if entry_key in seen_entries:
            continue
        seen_entries.add(entry_key)
        entries.append(
            {
                "component_kind": component_kind,
                "component_name": normalized_component_name,
                "path": normalized_component_path,
            }
        )
    return tuple(entries)
