from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_PUPPET_SUFFIXES = frozenset({".pp"})
_PUPPET_MANIFEST_BASENAMES = frozenset({"puppetfile", "modulefile", "metadata.json"})
_PUPPET_SOURCE_ROOTS = frozenset(
    {"manifests", "modules", "site", "plans", "types", "functions", "tasks"}
)
_PUPPET_DEFINITION_RE = re.compile(
    r"(?mi)^\s*(?P<kind>class|define|plan|application|type)\s+"
    r"(?P<name>(?:::)?[a-z][a-z0-9_:]*)"
    r"(?:\s*\([^)]*\))?"
    r"(?:\s+inherits\s+(?P<inherits>(?:::)?[a-z][a-z0-9_:]*))?"
)
_PUPPET_NODE_RE = re.compile(r"(?mi)^\s*node\s+(?P<name>[^ \t\r\n{]+)")
_PUPPET_INCLUDE_RE = re.compile(
    r"(?mi)^\s*(?P<kind>include|contain|require)\s+(?P<name>(?:::)?[a-z][a-z0-9_:]*)"
)
_PUPPET_CLASS_RESOURCE_RE = re.compile(
    r"(?mi)\bclass\s*\{\s*['\"](?P<name>(?:::)?[A-Za-z][A-Za-z0-9_:.-]*)['\"]\s*:"
)
_PUPPET_IMPORT_RE = re.compile(r"(?mi)^\s*import\s+['\"](?P<name>[^'\"]+)['\"]")
_PUPPET_METADATA_NAME_RE = re.compile(
    r'(?mi)"name"\s*:\s*"(?P<name>[a-z0-9_.-]+(?:/[a-z0-9_.-]+)?)"'
)
_PUPPET_METADATA_MARKER_RE = re.compile(
    r'(?mi)"(?:dependencies|operatingsystem_support|issues_url|project_page)"\s*:'
)
_PUPPETFILE_MARKER_RE = re.compile(r"(?mi)^\s*(?:forge\b|mod\s+['\"])")
_MODULEFILE_MARKER_RE = re.compile(r"(?mi)^\s*(?:name|dependency)\s+['\"]")
_PUPPET_STATEMENT_KEYWORDS = (
    "class",
    "define",
    "plan",
    "application",
    "type",
    "node",
    "include",
    "contain",
    "require",
    "import",
)
_PASCAL_STATEMENT_KEYWORDS = (
    "program",
    "unit",
    "interface",
    "implementation",
    "uses",
    "begin",
    "procedure",
    "function",
    "const",
    "type",
    "var",
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "application",
        "class",
        "contain",
        "define",
        "import",
        "include",
        "node",
        "plan",
        "require",
        "type",
    }
)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _ordered_names(*raw_names: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_name in raw_names:
        candidate = str(raw_name or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return tuple(ordered)


def strip_comments(text: str) -> str:
    output: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_single:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "'":
                in_single = False
            index += 1
            continue
        if in_double:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_double = False
            index += 1
            continue
        if character == "#":
            while index < len(text) and text[index] != "\n":
                output.append(" ")
                index += 1
            continue
        if character == "'":
            in_single = True
        elif character == '"':
            in_double = True
        output.append(character)
        index += 1
    return "".join(output)


def _normalize_target_name(raw_name: str) -> str:
    normalized = str(raw_name or "").strip().strip("'").strip('"')
    normalized = normalized.replace("/", "::")
    while normalized.startswith("::"):
        normalized = normalized[2:]
    if normalized.endswith(".pp"):
        normalized = normalized[:-3]
    return normalized.strip().lower()


def _starts_with_statement_keyword(line: str, keywords: tuple[str, ...]) -> bool:
    lowered_line = line.lower()
    for keyword in keywords:
        if not lowered_line.startswith(keyword):
            continue
        suffix = lowered_line[len(keyword) : len(keyword) + 1]
        if not suffix or suffix.isspace() or suffix in "{('\"":
            return True
    return False


def _has_puppet_variable_reference(line: str) -> bool:
    for index, character in enumerate(line[:-1]):
        if character != "$":
            continue
        next_character = line[index + 1]
        if next_character.isalnum() or next_character in "_{":
            return True
    return False


def _is_probable_puppet_class_resource_line(line: str) -> bool:
    lowered_line = line.lower()
    class_index = lowered_line.find("class")
    if class_index < 0:
        return False
    suffix = lowered_line[class_index + len("class") : class_index + len("class") + 1]
    if suffix and not suffix.isspace():
        return False
    brace_index = line.find("{", class_index)
    if brace_index < 0:
        return False
    resource_slice = line[brace_index + 1 :]
    return "'" in resource_slice or '"' in resource_slice


def _has_puppet_constructs(stripped_text: str) -> bool:
    for raw_line in stripped_text.splitlines():
        line = raw_line.lstrip()
        if not line:
            continue
        if _starts_with_statement_keyword(line, _PUPPET_STATEMENT_KEYWORDS):
            return True
        if _is_probable_puppet_class_resource_line(line):
            return True
        if "::" in line or "=>" in line or _has_puppet_variable_reference(line):
            return True
    return False


def _has_pascal_constructs(stripped_text: str) -> bool:
    for raw_line in stripped_text.splitlines():
        line = raw_line.lstrip()
        if line and _starts_with_statement_keyword(line, _PASCAL_STATEMENT_KEYWORDS):
            return True
    return False


def has_puppet_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    suffix = normalized_path.suffix.lower()
    if suffix in _KNOWN_PUPPET_SUFFIXES:
        return True
    if normalized_path.name.lower() in _PUPPET_MANIFEST_BASENAMES:
        return True
    return bool({part.lower() for part in normalized_path.parts} & _PUPPET_SOURCE_ROOTS)


def _is_probable_puppet_metadata(text: str) -> bool:
    if _PUPPET_METADATA_MARKER_RE.search(text) is None:
        return False
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        return False
    return True


def is_probable_puppet_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    basename = normalized_path.name.lower()
    stripped_text = strip_comments(text)
    if basename == "puppetfile":
        return _PUPPETFILE_MARKER_RE.search(stripped_text) is not None
    if basename == "modulefile":
        return _MODULEFILE_MARKER_RE.search(stripped_text) is not None
    if basename == "metadata.json":
        return _is_probable_puppet_metadata(stripped_text)
    if normalized_path.suffix.lower() != ".pp":
        return False
    has_puppet_constructs = _has_puppet_constructs(stripped_text)
    if not has_puppet_constructs:
        return False
    path_tokens = {part.lower() for part in normalized_path.parts}
    has_puppet_path_context = bool(path_tokens & _PUPPET_SOURCE_ROOTS)
    has_pascal_constructs = _has_pascal_constructs(stripped_text)
    if has_pascal_constructs and not has_puppet_path_context:
        if _PUPPET_CLASS_RESOURCE_RE.search(stripped_text) is None and "::" not in stripped_text:
            return False
    return True


def puppet_metadata_name(text: str) -> str | None:
    if not _is_probable_puppet_metadata(text):
        return None
    match = _PUPPET_METADATA_NAME_RE.search(text)
    if match is None:
        return None
    return str(match.group("name") or "").strip().lower() or None


def module_name_from_metadata_name(name: str) -> str:
    normalized = str(name or "").strip().lower().strip("/")
    if not normalized:
        return ""
    if "/" in normalized:
        normalized = normalized.rsplit("/", 1)[-1]
    if "-" in normalized:
        normalized = normalized.rsplit("-", 1)[-1]
    return normalized


def iter_definition_entries(text: str) -> tuple[tuple[str, str, int, str | None], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int, str | None]] = []
    seen: set[tuple[str, int]] = set()
    for match in _PUPPET_DEFINITION_RE.finditer(stripped_text):
        kind = str(match.group("kind") or "").strip().lower()
        name = _normalize_target_name(str(match.group("name") or ""))
        if not name or name in _RESERVED_SYMBOL_NAMES:
            continue
        line_number = _line_number(stripped_text, match.start())
        key = (name, line_number)
        if key in seen:
            continue
        seen.add(key)
        inherits = _normalize_target_name(str(match.group("inherits") or ""))
        entries.append((kind, name, line_number, inherits or None))
    for match in _PUPPET_NODE_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip().strip("'").strip('"')
        if not name:
            continue
        line_number = _line_number(stripped_text, match.start())
        key = (name, line_number)
        if key in seen:
            continue
        seen.add(key)
        entries.append(("node", name, line_number, None))
    return tuple(entries)


def iter_dependency_targets(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    targets: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for _, _, line_number, inherits in iter_definition_entries(stripped_text):
        if not inherits:
            continue
        item = (inherits, line_number)
        if item not in seen:
            seen.add(item)
            targets.append(item)
    for regex in (_PUPPET_INCLUDE_RE, _PUPPET_CLASS_RESOURCE_RE, _PUPPET_IMPORT_RE):
        for match in regex.finditer(stripped_text):
            raw_name = (
                match.groupdict().get("name")
                if isinstance(match.groupdict(), dict)
                else None
            )
            target_name = _normalize_target_name(str(raw_name or ""))
            if not target_name:
                continue
            item = (target_name, _line_number(stripped_text, match.start()))
            if item not in seen:
                seen.add(item)
                targets.append(item)
    return tuple(targets)


def _symbol_kind_for_definition(kind: str) -> str:
    if kind == "plan":
        return "function"
    return "module"


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int, str | None], ...]:
    return tuple(
        (name, _symbol_kind_for_definition(kind), line_number, inherits)
        for kind, name, line_number, inherits in iter_definition_entries(text)
    )


def path_aliases(path: PurePosixPath) -> tuple[str, ...]:
    aliases = {
        str(path).lower(),
        str(path.with_suffix("")).lower() if path.suffix else str(path).lower(),
        str(path.with_suffix("")).replace("/", "::").lower() if path.suffix else "",
        path.stem.lower() if path.suffix else path.name.lower(),
    }
    return tuple(sorted(alias for alias in aliases if alias and alias not in {".", "/"}))
