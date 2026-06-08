from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]

EIFFEL_SOURCE_SUFFIXES = frozenset({".e"})
EIFFEL_CONFIG_SUFFIXES = frozenset({".ecf", ".ace"})
EIFFEL_CONFIG_VARIABLE_RE = re.compile(
    r'(?i)<variable\b[^>]*\bname="(?P<name>[^"]+)"[^>]*\bvalue="(?P<value>[^"]*)"'
)
EIFFEL_CLUSTER_LOCATION_RE = re.compile(
    r'(?i)<cluster\b[^>]*\blocation="(?P<location>[^"]+)"'
)
EIFFEL_LIBRARY_LOCATION_RE = re.compile(
    r'(?i)<library\b[^>]*\blocation="(?P<location>[^"]+)"'
)
EIFFEL_ROOT_CLASS_RE = re.compile(
    r'(?i)<root\b[^>]*\bclass="(?P<name>[A-Za-z][A-Za-z0-9_]*)"'
)
EIFFEL_SYSTEM_NAME_RE = re.compile(
    r'(?i)<system\b[^>]*\bname="(?P<name>[^"]+)"'
)
EIFFEL_ACE_ROOT_RE = re.compile(
    r"(?im)^\s*root\s+(?P<name>[A-Za-z][A-Za-z0-9_]*)\b"
)
EIFFEL_ACE_PATH_RE = re.compile(
    r'(?im)^\s*(?:cluster|library)\b.*?"(?P<location>[^"]+)"'
)
EIFFEL_CLASS_RE = re.compile(
    r"(?im)^\s*(?:deferred\s+|expanded\s+|frozen\s+|separate\s+)*class\s+"
    r"(?P<name>[A-Za-z][A-Za-z0-9_]*)\b"
)
EIFFEL_MARKER_RE = re.compile(
    r"(?i)\b(?:class|feature|inherit|create|deferred|expanded)\b"
)
EIFFEL_CONFIG_MARKER_RE = re.compile(
    r"(?i)(?:<system\b|<target\b|<cluster\b|<library\b|<root\b|\broot\b|\bcluster\b)"
)
EIFFEL_TYPE_REFERENCE_RE = re.compile(
    r"(?im)(?::\s*(?:attached|detachable|separate|expanded)\s+|create\s*\{\s*)"
    r"(?P<name>[A-Z][A-Z0-9_]*)\b"
)
_EIFFEL_FEATURE_SECTION_RE = re.compile(r"(?im)^\s*feature\b")
_EIFFEL_SECTION_HEADER_RE = re.compile(
    r"(?im)^\s*(?:note|indexing|class|inherit|insert|create|convert|feature|"
    r"obsolete|invariant|end)\b"
)
_EIFFEL_FEATURE_DECL_RE = re.compile(
    r"^\s*(?P<name>[a-z][a-z0-9_]*)(?:\s*\(|\s*:\s*|\s*$)"
)
_EIFFEL_RESERVED_FEATURE_WORDS = frozenset(
    {
        "across",
        "alias",
        "all",
        "and",
        "as",
        "attribute",
        "check",
        "create",
        "current",
        "debug",
        "deferred",
        "do",
        "else",
        "elseif",
        "end",
        "ensure",
        "expanded",
        "export",
        "external",
        "feature",
        "from",
        "if",
        "implies",
        "inherit",
        "inspect",
        "invariant",
        "like",
        "local",
        "loop",
        "not",
        "obsolete",
        "old",
        "once",
        "or",
        "rename",
        "require",
        "rescue",
        "retry",
        "select",
        "then",
        "undefine",
        "until",
        "variant",
        "when",
        "xor",
    }
)


def strip_comments(text: str) -> str:
    characters = list(text)
    index = 0
    in_string = False
    string_delimiter = ""
    while index < len(characters):
        current = characters[index]
        next_char = characters[index + 1] if index + 1 < len(characters) else ""
        if in_string:
            if current == "%" and index + 1 < len(characters):
                index += 2
                continue
            if current == string_delimiter:
                in_string = False
                string_delimiter = ""
            index += 1
            continue
        if current in {'"', "'"}:
            in_string = True
            string_delimiter = current
            index += 1
            continue
        if current == "-" and next_char == "-":
            characters[index] = " "
            characters[index + 1] = " "
            index += 2
            while index < len(characters) and characters[index] != "\n":
                characters[index] = " "
                index += 1
            continue
        index += 1
    return "".join(characters)


def has_eiffel_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in (
        EIFFEL_SOURCE_SUFFIXES | EIFFEL_CONFIG_SUFFIXES
    )


def class_name_from_text(text: str, *, file_path: str) -> str:
    stripped_text = strip_comments(text)
    match = EIFFEL_CLASS_RE.search(stripped_text)
    if match is not None:
        class_name = str(match.group("name") or "").strip()
        if class_name:
            return class_name
    return PurePosixPath(file_path).stem.upper()


def system_name_from_text(text: str, *, file_path: str) -> str:
    stripped_text = strip_comments(text)
    if PurePosixPath(file_path).suffix.lower() == ".ecf":
        match = EIFFEL_SYSTEM_NAME_RE.search(stripped_text)
        if match is not None:
            system_name = str(match.group("name") or "").strip()
            if system_name:
                return system_name
    return PurePosixPath(file_path).stem


def parse_root_class_names(text: str) -> tuple[str, ...]:
    stripped_text = strip_comments(text)
    names: list[str] = []
    seen: set[str] = set()
    for pattern in (EIFFEL_ROOT_CLASS_RE, EIFFEL_ACE_ROOT_RE):
        for match in pattern.finditer(stripped_text):
            class_name = str(match.group("name") or "").strip()
            if not class_name or class_name in seen:
                continue
            seen.add(class_name)
            names.append(class_name)
    return tuple(names)


def parse_config_variables(text: str) -> dict[str, str]:
    stripped_text = strip_comments(text)
    variables: dict[str, str] = {}
    for match in EIFFEL_CONFIG_VARIABLE_RE.finditer(stripped_text):
        variable_name = str(match.group("name") or "").strip()
        variable_value = str(match.group("value") or "").strip()
        if variable_name:
            variables[variable_name] = variable_value
    return variables


def parse_config_location_targets(text: str) -> tuple[str, ...]:
    stripped_text = strip_comments(text)
    locations: list[str] = []
    seen: set[str] = set()
    for pattern in (
        EIFFEL_CLUSTER_LOCATION_RE,
        EIFFEL_LIBRARY_LOCATION_RE,
        EIFFEL_ACE_PATH_RE,
    ):
        for match in pattern.finditer(stripped_text):
            location = str(match.group("location") or "").strip()
            if not location or location in seen:
                continue
            seen.add(location)
            locations.append(location)
    return tuple(locations)


def parse_inherited_classes(text: str) -> tuple[str, ...]:
    stripped_text = strip_comments(text)
    names: list[str] = []
    seen: set[str] = set()
    in_inherit_clause = False
    for raw_line in stripped_text.splitlines():
        stripped_line = raw_line.strip()
        lowered_line = stripped_line.lower()
        if not stripped_line:
            continue
        if lowered_line.startswith("inherit"):
            in_inherit_clause = True
            continue
        if in_inherit_clause and _EIFFEL_SECTION_HEADER_RE.match(stripped_line):
            in_inherit_clause = False
        if not in_inherit_clause:
            continue
        match = re.match(r"^(?P<name>[A-Z][A-Z0-9_]*)\b", stripped_line)
        if match is None:
            continue
        name = str(match.group("name") or "").strip()
        if name and name not in seen and name != "NONE":
            seen.add(name)
            names.append(name)
    return tuple(names)


def parse_dependency_targets(text: str, *, file_path: str) -> tuple[str, ...]:
    current_class = class_name_from_text(text, file_path=file_path)
    names: list[str] = []
    seen: set[str] = set()
    for name in parse_inherited_classes(text):
        if name == current_class or name in seen:
            continue
        seen.add(name)
        names.append(name)
    stripped_text = strip_comments(text)
    for match in EIFFEL_TYPE_REFERENCE_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        if not name or name == current_class or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return tuple(names)


def iter_feature_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    in_feature_clause = False
    in_local_block = False
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        lowered_line = stripped_line.lower()
        if not stripped_line:
            continue
        if _EIFFEL_FEATURE_SECTION_RE.match(stripped_line):
            in_feature_clause = True
            in_local_block = False
            continue
        if in_feature_clause and _EIFFEL_SECTION_HEADER_RE.match(stripped_line):
            in_feature_clause = lowered_line.startswith("feature")
            in_local_block = False
            if in_feature_clause:
                continue
        if not in_feature_clause:
            continue
        if lowered_line == "local":
            in_local_block = True
            continue
        if lowered_line in {"do", "once", "external", "deferred", "attribute"}:
            in_local_block = False
            continue
        if in_local_block:
            continue
        match = _EIFFEL_FEATURE_DECL_RE.match(stripped_line)
        if match is None:
            continue
        feature_name = str(match.group("name") or "").strip()
        if not feature_name or feature_name in _EIFFEL_RESERVED_FEATURE_WORDS:
            continue
        entry = (feature_name, line_number)
        if entry in seen:
            continue
        seen.add(entry)
        entries.append(entry)
    return tuple(entries)
