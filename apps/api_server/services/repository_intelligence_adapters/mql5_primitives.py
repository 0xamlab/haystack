from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]

_SOURCE_SUFFIXES = frozenset({".mq5", ".mqh"})
_PROJECT_SUFFIXES = frozenset({".mqproj"})
_KNOWN_SUFFIXES = _SOURCE_SUFFIXES | _PROJECT_SUFFIXES
_MQL5_KEYWORDS = (
    "#include",
    "#property",
    "class ",
    "enum ",
    "struct ",
    "input ",
    "OnInit(",
    "OnTick(",
    "OnStart(",
)
_INCLUDE_RE = re.compile(
    r'^\s*#include\s+(?:<(?P<angle>[^>]+)>|"(?P<quoted>[^"]+)")',
    re.MULTILINE,
)
_CLASS_DECL_RE = re.compile(
    r"^\s*class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
    r"(?:\s*:\s*(?:public|protected|private)\s+(?P<base>[A-Za-z_][A-Za-z0-9_]*))?",
    re.MULTILINE,
)
_FUNCTION_DECL_RE = re.compile(
    r"^\s*(?!(?:if|for|while|switch|return|else|case|break|continue|do|try|catch)\b)"
    r"(?:(?:virtual|static|inline|extern|const|final|override|public|private|protected)\s+)*"
    r"(?P<return>[A-Za-z_][A-Za-z0-9_:<>,\*\&\[\]]+)\s+"
    r"(?:(?P<owner>[A-Za-z_][A-Za-z0-9_]*)::)?"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*(?:const\b)?\s*(?:\{|;)?\s*$",
    re.MULTILINE,
)
_INSTANCE_DECL_RE = re.compile(
    r"^\s*(?!(?:if|for|while|switch|return|else|case|break|continue)\b)"
    r"(?:(?:const|static|input|extern)\s+)*"
    r"(?P<type>[A-Za-z_][A-Za-z0-9_:<>]*)\s+"
    r"(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*(?:=|;|\[|,)",
    re.MULTILINE,
)
_QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\.|::)\s*"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?=\()"
)
_BARE_CALL_RE = re.compile(
    r"(?<![.:$A-Za-z0-9_])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?=\()"
)
_PROJECT_PATH_RE = re.compile(
    r"""(?i)(?:["'](?P<quoted>[^"']+\.(?:mq5|mqh))["']|>(?P<xml>[^<>\r\n]+\.(?:mq5|mqh))<)"""
)
_BUILTIN_TYPE_NAMES = frozenset(
    {
        "bool",
        "char",
        "color",
        "datetime",
        "double",
        "float",
        "int",
        "long",
        "short",
        "string",
        "uchar",
        "uint",
        "ulong",
        "ushort",
        "void",
    }
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "alert",
        "arraycopy",
        "break",
        "case",
        "catch",
        "class",
        "continue",
        "delete",
        "do",
        "else",
        "enum",
        "extern",
        "false",
        "for",
        "if",
        "input",
        "new",
        "printf",
        "private",
        "protected",
        "public",
        "return",
        "static",
        "struct",
        "switch",
        "this",
        "true",
        "try",
        "while",
    }
)


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def strip_comments(text: str) -> str:
    result_lines: list[str] = []
    in_block_comment = False
    for raw_line in text.splitlines():
        if not raw_line:
            result_lines.append("")
            continue
        output: list[str] = []
        in_string: str | None = None
        escaped = False
        index = 0
        while index < len(raw_line):
            if in_block_comment:
                if raw_line.startswith("*/", index):
                    in_block_comment = False
                    output.append(" ")
                    output.append(" ")
                    index += 2
                    continue
                output.append(" ")
                index += 1
                continue
            character = raw_line[index]
            if in_string is not None:
                output.append(character)
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == in_string:
                    in_string = None
                index += 1
                continue
            if raw_line.startswith("//", index):
                break
            if raw_line.startswith("/*", index):
                in_block_comment = True
                output.append(" ")
                output.append(" ")
                index += 2
                continue
            if character in {'"', "'"}:
                in_string = character
                output.append(character)
                index += 1
                continue
            output.append(character)
            index += 1
        result_lines.append("".join(output).rstrip())
    return "\n".join(result_lines)


def has_mql5_path_hints(path: Path) -> bool:
    return path.suffix.lower() in _KNOWN_SUFFIXES


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


def normalize_identifier(value: str) -> str:
    return str(value or "").strip()


def normalize_import_target(value: str) -> str:
    return _normalize_repository_like_path(str(value or "").strip().strip("<>\"'"))


def project_file_entries(text: str) -> tuple[str, ...]:
    entries: list[str] = []
    seen_entries: set[str] = set()
    for match in _PROJECT_PATH_RE.finditer(text):
        normalized_entry = normalize_import_target(
            str(match.group("quoted") or match.group("xml") or "")
        )
        if not normalized_entry or normalized_entry.lower() in seen_entries:
            continue
        seen_entries.add(normalized_entry.lower())
        entries.append(normalized_entry)
    return tuple(entries)


def is_probable_mql5_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix not in _KNOWN_SUFFIXES:
        return False
    if suffix in _PROJECT_SUFFIXES:
        lowered_text = str(text or "").lower()
        return bool(project_file_entries(text) or "<project" in lowered_text)
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    lowered_text = stripped_text.lower()
    if any(keyword.lower() in lowered_text for keyword in _MQL5_KEYWORDS):
        return True
    return bool(_CLASS_DECL_RE.search(stripped_text) or _FUNCTION_DECL_RE.search(stripped_text))


def module_symbol_name(file_path: str) -> str:
    return PurePosixPath(file_path).stem.strip()


def import_targets_for_text(text: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen_targets: set[str] = set()
    for match in _INCLUDE_RE.finditer(text):
        normalized_target = normalize_import_target(
            str(match.group("angle") or match.group("quoted") or "")
        )
        if not normalized_target or normalized_target.lower() in seen_targets:
            continue
        seen_targets.add(normalized_target.lower())
        targets.append(normalized_target)
    return tuple(targets)


def collect_symbol_entries(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    source_text = strip_comments(text)
    if not source_text.strip():
        return []
    module_name = module_symbol_name(file_path)
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    class_stack: list[dict[str, Any]] = []
    brace_depth = 0
    final_line = _line_count(source_text)
    for line_no, raw_line in enumerate(source_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        opens = raw_line.count("{")
        closes = raw_line.count("}")
        if stripped_line:
            class_match = _CLASS_DECL_RE.match(stripped_line)
            if class_match is not None:
                symbol_name = normalize_identifier(str(class_match.group("name") or ""))
                if symbol_name and symbol_name.lower() not in _RESERVED_SYMBOL_NAMES:
                    symbol_key = ("type", symbol_name.lower(), line_no)
                    if symbol_key not in seen_symbol_keys:
                        seen_symbol_keys.add(symbol_key)
                        symbol_id = stable_identifier(
                            "sym",
                            {
                                "file_path": file_path,
                                "name": symbol_name,
                                "kind": "type",
                                "line": line_no,
                            },
                        )
                        qualified_names = {symbol_name}
                        if module_name:
                            qualified_names.add(f"{module_name}.{symbol_name}")
                        symbol_entries.append(
                            {
                                "symbol_id": symbol_id,
                                "symbol_name": symbol_name,
                                "symbol_kind": "type",
                                "start_line": line_no,
                                "end_line": line_no,
                                "signature": stripped_line,
                                "parent_symbol_id": None,
                                "qualified_names": tuple(sorted(qualified_names)),
                            }
                        )
                        class_stack.append(
                            {
                                "depth": brace_depth + max(opens - closes, 1),
                                "name": symbol_name,
                                "symbol_id": symbol_id,
                            }
                        )
                brace_depth = max(0, brace_depth + opens - closes)
                continue
            function_match = _FUNCTION_DECL_RE.match(stripped_line)
            if function_match is not None:
                symbol_name = normalize_identifier(str(function_match.group("name") or ""))
                owner_name = normalize_identifier(str(function_match.group("owner") or ""))
                if not owner_name and class_stack:
                    owner_name = str(class_stack[-1]["name"])
                if symbol_name and symbol_name.lower() not in _RESERVED_SYMBOL_NAMES:
                    symbol_kind = "method" if owner_name else "function"
                    symbol_key = (symbol_kind, symbol_name.lower(), line_no)
                    if symbol_key not in seen_symbol_keys:
                        seen_symbol_keys.add(symbol_key)
                        qualified_names = {symbol_name}
                        if owner_name:
                            qualified_names.add(f"{owner_name}.{symbol_name}")
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
                                        "line": line_no,
                                        "owner": owner_name or None,
                                    },
                                ),
                                "symbol_name": symbol_name,
                                "symbol_kind": symbol_kind,
                                "start_line": line_no,
                                "end_line": line_no,
                                "signature": stripped_line,
                                "parent_symbol_id": (
                                    str(class_stack[-1]["symbol_id"])
                                    if class_stack and owner_name == str(class_stack[-1]["name"])
                                    else None
                                ),
                                "qualified_names": tuple(sorted(qualified_names)),
                            }
                        )
        brace_depth = max(0, brace_depth + opens - closes)
        while class_stack and brace_depth < int(class_stack[-1]["depth"]):
            class_stack.pop()

    for index, entry in enumerate(symbol_entries):
        next_line = (
            int(symbol_entries[index + 1]["start_line"]) - 1
            if index + 1 < len(symbol_entries)
            else final_line
        )
        entry["end_line"] = max(int(entry["start_line"]), next_line)
    return symbol_entries
