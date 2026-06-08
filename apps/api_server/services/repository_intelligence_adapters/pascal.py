from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "absolute",
        "and",
        "array",
        "as",
        "asm",
        "begin",
        "case",
        "class",
        "const",
        "constructor",
        "destructor",
        "dispinterface",
        "div",
        "do",
        "downto",
        "else",
        "end",
        "except",
        "exports",
        "false",
        "file",
        "finalization",
        "finally",
        "for",
        "function",
        "goto",
        "if",
        "implementation",
        "in",
        "inherited",
        "initialization",
        "inline",
        "interface",
        "is",
        "label",
        "library",
        "mod",
        "nil",
        "not",
        "object",
        "of",
        "operator",
        "or",
        "out",
        "packed",
        "procedure",
        "program",
        "property",
        "raise",
        "read",
        "readln",
        "record",
        "repeat",
        "resourcestring",
        "result",
        "set",
        "shl",
        "shr",
        "then",
        "threadvar",
        "to",
        "true",
        "try",
        "type",
        "unit",
        "until",
        "uses",
        "var",
        "while",
        "with",
        "write",
        "writeln",
        "xor",
    }
)
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
UNIT_DECL_RE = re.compile(
    r"^\s*(?:unit|program|library|package)\s+(?P<name>[A-Za-z_][A-Za-z0-9_\.]*)\s*;",
    re.MULTILINE | re.IGNORECASE,
)
USES_RE = re.compile(
    r"\buses\b(?P<body>.*?);",
    re.IGNORECASE | re.DOTALL,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:packed\s+)?"
    r"(?:class|record|interface|object|dispinterface)\b",
    re.MULTILINE | re.IGNORECASE,
)
ROUTINE_DECL_RE = re.compile(
    r"^\s*(?:class\s+)?(?:function|procedure|constructor|destructor|operator)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_\.]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
UNQUALIFIED_CALL_RE = re.compile(
    r"(?<!\.)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.IGNORECASE,
)


def normalize_target(raw_target: str) -> str:
    normalized_target = re.sub(
        r"\bin\s+['\"][^'\"]+['\"]",
        "",
        raw_target,
        flags=re.IGNORECASE,
    ).strip()
    return normalized_target.strip(" .")


def normalize_symbol_name(raw_name: str) -> str:
    normalized_name = raw_name.strip()
    if "." in normalized_name:
        normalized_name = normalized_name.rsplit(".", 1)[-1].strip()
    return normalized_name


def strip_comments(text: str) -> str:
    def _replace_block_comment(match: re.Match[str]) -> str:
        return "\n" * str(match.group(0)).count("\n")

    without_curly_comments = re.sub(
        r"\{.*?\}",
        _replace_block_comment,
        text,
        flags=re.DOTALL,
    )
    without_paren_comments = re.sub(
        r"\(\*.*?\*\)",
        _replace_block_comment,
        without_curly_comments,
        flags=re.DOTALL,
    )
    return re.sub(r"//.*$", "", without_paren_comments, flags=re.MULTILINE)


def unit_name(text: str) -> str:
    match = UNIT_DECL_RE.search(strip_comments(text))
    if match is None:
        return ""
    return normalize_target(str(match.group("name") or "")).lower()


def uses_targets(text: str) -> tuple[str, ...]:
    targets: list[str] = []
    stripped_text = strip_comments(text)
    for match in USES_RE.finditer(stripped_text):
        body = str(match.group("body") or "")
        for raw_segment in body.split(","):
            candidate = normalize_target(raw_segment)
            if (
                not candidate
                or not IDENTIFIER_RE.fullmatch(candidate)
                or candidate.lower() in RESERVED_SYMBOL_NAMES
            ):
                continue
            targets.append(candidate)
    return tuple(dict.fromkeys(targets))


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, str]] = set()
    stripped_text = strip_comments(text)
    current_unit = unit_name(text)
    final_line = len(stripped_text.splitlines()) if stripped_text else 1
    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        symbol_kind: str | None = None
        symbol_name: str | None = None
        unit_match = UNIT_DECL_RE.match(stripped_line)
        if unit_match is not None:
            symbol_kind = "module"
            symbol_name = normalize_symbol_name(str(unit_match.group("name") or ""))
        else:
            type_match = TYPE_DECL_RE.match(stripped_line)
            if type_match is not None:
                symbol_kind = "type"
                symbol_name = normalize_symbol_name(str(type_match.group("name") or ""))
            else:
                routine_match = ROUTINE_DECL_RE.match(stripped_line)
                if routine_match is not None:
                    symbol_kind = "function"
                    symbol_name = normalize_symbol_name(
                        str(routine_match.group("name") or "")
                    )
        canonical_symbol_name = symbol_name.lower() if symbol_name else ""
        if (
            symbol_kind is None
            or not symbol_name
            or not canonical_symbol_name
            or canonical_symbol_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        qualified_names = {canonical_symbol_name}
        if current_unit and symbol_kind != "module":
            qualified_names.add(f"{current_unit}.{canonical_symbol_name}")
        symbol_key = (symbol_kind, canonical_symbol_name, stripped_line.lower())
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
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
                "signature": stripped_line,
                "qualified_names": tuple(sorted(qualified_names)),
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
    if path.suffix.lower() not in {".pas", ".pp", ".lpr", ".dpr", ".dpk"}:
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
        return {alias for alias in aliases if alias and alias not in {".", "/"}}
    current_unit = unit_name(text)
    if current_unit:
        aliases.add(current_unit)
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(str(alias).lower() for alias in symbol_entry["qualified_names"] if alias)
    return {alias for alias in aliases if alias and alias not in {".", "/"}}
