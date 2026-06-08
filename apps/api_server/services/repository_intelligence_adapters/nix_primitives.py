from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]

_KNOWN_SUFFIXES = frozenset({".nix"})
_NIX_FILE_BASENAMES = frozenset({"default.nix", "flake.nix", "shell.nix"})
_IDENTIFIER_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_'-]*)\b")
_ATTR_PATH_RE = re.compile(
    r"(?P<name>[A-Za-z_][A-Za-z0-9_'-]*(?:\.[A-Za-z0-9_+-]+)*)"
)
_ASSIGNMENT_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_'-]*(?:\.[A-Za-z0-9_+-]+)*)\s*=",
    re.MULTILINE,
)
_IMPORT_RE = re.compile(r"\bimport\s+(?P<target>\.?\.?/[-A-Za-z0-9_./+]+(?:\.nix)?)")
_CALLPACKAGE_RE = re.compile(
    r"\b(?:[A-Za-z_][A-Za-z0-9_.'-]*\.)?callPackage\s+"
    r"(?P<target>\.?\.?/[-A-Za-z0-9_./+]+(?:\.nix)?)"
)
_IMPORTS_ARRAY_RE = re.compile(r"\bimports\s*=\s*\[(?P<body>.*?)\];", re.DOTALL)
_PATH_LITERAL_RE = re.compile(r"(?P<target>\.?\.?/[-A-Za-z0-9_./+]+(?:\.nix)?)")
_IMPORT_ASSIGN_RE = re.compile(
    r"^\s*(?:let\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_'-]*)\s*=\s*"
    r"(?:import|(?:[A-Za-z_][A-Za-z0-9_.'-]*\.)?callPackage)\s+"
    r"(?P<target>\.?\.?/[-A-Za-z0-9_./+]+(?:\.nix)?)",
    re.MULTILINE,
)
_INHERIT_IMPORT_RE = re.compile(
    r"\binherit\s*\(\s*import\s+(?P<target>\.?\.?/[-A-Za-z0-9_./+]+(?:\.nix)?)\s*\)\s+"
    r"(?P<body>[^;]+);",
    re.DOTALL,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9_'])"
    r"(?P<owner>[A-Za-z_][A-Za-z0-9_'-]*)\."
    r"(?P<name>[A-Za-z_][A-Za-z0-9_'-]*)"
)
_NIX_KEYWORDS = frozenset(
    {
        "assert",
        "else",
        "false",
        "if",
        "import",
        "in",
        "inherit",
        "let",
        "null",
        "or",
        "rec",
        "then",
        "true",
        "with",
    }
)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def strip_comments(text: str) -> str:
    result: list[str] = []
    in_block_comment = False
    in_string: str | None = None
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        if in_block_comment:
            if character == "*" and next_character == "/":
                in_block_comment = False
                index += 2
                continue
            result.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string is not None:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == in_string:
                in_string = None
            index += 1
            continue
        if character in {'"', "'"}:
            in_string = character
            result.append(character)
            index += 1
            continue
        if character == "#" and character != "\n":
            while index < len(text) and text[index] != "\n":
                result.append(" ")
                index += 1
            continue
        if character == "/" and next_character == "*":
            in_block_comment = True
            result.append(" ")
            result.append(" ")
            index += 2
            continue
        result.append(character)
        index += 1
    return "".join(result)


def has_nix_path_hints(path: Path) -> bool:
    return path.suffix.lower() in _KNOWN_SUFFIXES or path.name.lower() in _NIX_FILE_BASENAMES


def normalize_identifier(value: str) -> str:
    return str(value or "").strip()


def normalize_import_target(value: str) -> str:
    normalized = str(value or "").strip().strip("\"'")
    if not normalized:
        return ""
    normalized_parts: list[str] = []
    for part in PurePosixPath(normalized.replace("\\", "/")).parts:
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


def _nix_tokens_present(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "let ",
            " in\n",
            "import ",
            "callpackage ",
            "mkShell".lower(),
            "stdenv".lower(),
            "outputs =",
            "inputs =",
        )
    )


def is_probable_nix_source(*, path: Path, text: str) -> bool:
    if not has_nix_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if path.suffix.lower() == ".nix":
        return True
    return _nix_tokens_present(stripped_text)


def import_targets_for_text(text: str) -> tuple[str, ...]:
    normalized_text = strip_comments(text)
    targets: list[str] = []
    seen_targets: set[str] = set()
    for pattern in (_IMPORT_RE, _CALLPACKAGE_RE):
        for match in pattern.finditer(normalized_text):
            normalized_target = normalize_import_target(str(match.group("target") or ""))
            if not normalized_target or normalized_target.lower() in seen_targets:
                continue
            seen_targets.add(normalized_target.lower())
            targets.append(normalized_target)
    for match in _IMPORTS_ARRAY_RE.finditer(normalized_text):
        body = str(match.group("body") or "")
        for path_match in _PATH_LITERAL_RE.finditer(body):
            normalized_target = normalize_import_target(str(path_match.group("target") or ""))
            if not normalized_target or normalized_target.lower() in seen_targets:
                continue
            seen_targets.add(normalized_target.lower())
            targets.append(normalized_target)
    return tuple(targets)


def module_symbol_name(file_path: str) -> str:
    path = PurePosixPath(file_path)
    return path.stem or path.name


def _statement_end_line(text: str, start_offset: int) -> int:
    in_string: str | None = None
    escaped = False
    brace_depth = 0
    bracket_depth = 0
    paren_depth = 0
    index = start_offset
    while index < len(text):
        character = text[index]
        if in_string is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == in_string:
                in_string = None
            index += 1
            continue
        if character in {'"', "'"}:
            in_string = character
            index += 1
            continue
        if character == "{":
            brace_depth += 1
        elif character == "}":
            brace_depth = max(0, brace_depth - 1)
        elif character == "[":
            bracket_depth += 1
        elif character == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif character == "(":
            paren_depth += 1
        elif character == ")":
            paren_depth = max(0, paren_depth - 1)
        elif (
            character == ";"
            and brace_depth == 0
            and bracket_depth == 0
            and paren_depth == 0
        ):
            return _line_number(text, index)
        index += 1
    return _line_count(text)


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
    seen_keys: set[tuple[str, int]] = set()
    module_name = module_symbol_name(file_path)
    for match in _ASSIGNMENT_RE.finditer(source_text):
        raw_name = normalize_identifier(str(match.group("name") or ""))
        if not raw_name:
            continue
        start_line = _line_number(source_text, match.start())
        end_line = _statement_end_line(source_text, match.end())
        leaf_name = raw_name.rsplit(".", 1)[-1]
        symbol_key = (raw_name.lower(), start_line)
        if symbol_key in seen_keys:
            continue
        seen_keys.add(symbol_key)
        qualified_names = {leaf_name, raw_name}
        if module_name:
            qualified_names.add(f"{module_name}.{leaf_name}")
            qualified_names.add(f"{module_name}.{raw_name}")
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": raw_name,
                        "line": start_line,
                        "kind": "binding",
                    },
                ),
                "symbol_name": leaf_name,
                "symbol_kind": "binding",
                "start_line": start_line,
                "end_line": end_line,
                "signature": "\n".join(
                    source_text.splitlines()[start_line - 1 : end_line]
                ).strip(),
                "qualified_names": tuple(sorted(alias for alias in qualified_names if alias)),
            }
        )
    return symbol_entries


def import_bindings_for_text(text: str) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    normalized_text = strip_comments(text)
    bindings: list[tuple[str, str, tuple[str, ...]]] = []
    seen_bindings: set[tuple[str, str, tuple[str, ...]]] = set()
    for match in _IMPORT_ASSIGN_RE.finditer(normalized_text):
        alias_name = normalize_identifier(str(match.group("name") or ""))
        import_target = normalize_import_target(str(match.group("target") or ""))
        binding = (alias_name, import_target, ())
        if alias_name and import_target and binding not in seen_bindings:
            seen_bindings.add(binding)
            bindings.append(binding)
    for match in _INHERIT_IMPORT_RE.finditer(normalized_text):
        import_target = normalize_import_target(str(match.group("target") or ""))
        body = str(match.group("body") or "")
        target_names = tuple(
            name
            for name in (
                normalize_identifier(str(name_match.group("name") or ""))
                for name_match in _IDENTIFIER_RE.finditer(body)
            )
            if name and name not in _NIX_KEYWORDS
        )
        for target_name in target_names:
            binding = (target_name, import_target, (target_name,))
            if binding not in seen_bindings:
                seen_bindings.add(binding)
                bindings.append(binding)
    return tuple(bindings)
