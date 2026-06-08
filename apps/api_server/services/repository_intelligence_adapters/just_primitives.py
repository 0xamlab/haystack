from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".just"})
JUSTFILE_BASENAMES = frozenset({"justfile", ".justfile"})
_SUPPORT_DIRECTORIES = frozenset({"build", "config", "just", "scripts", "tasks", "tools"})
_MARKER_RE = re.compile(
    r"(?im)^\s*(?:alias\s+\S+\s*:=|import\s+\??\s*['\"]|mod\s+\??\s*[A-Za-z_]|set\s+[A-Za-z_-]+|[A-Za-z_][A-Za-z0-9_.-]*\b[^:\n]*:(?![=]))"
)
_ALIAS_RE = re.compile(
    r"(?im)^\s*alias\s+(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\s*:=\s*(?P<target>[A-Za-z_][A-Za-z0-9_.:-]*)\s*$"
)
_IMPORT_RE = re.compile(r"""(?im)^\s*import\s+\??\s*(?P<target>['"][^'"]+['"])\s*$""")
_MOD_RE = re.compile(
    r"""(?im)^\s*mod\s+\??\s*(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\s*(?P<path>['"][^'"]+['"])?\s*$"""
)
_DEPENDENCY_TARGET_RE = re.compile(
    r"""\((?P<paren>[A-Za-z_][A-Za-z0-9_.:-]*)\b[^)]*\)|(?P<bare>[A-Za-z_][A-Za-z0-9_.:-]*)"""
)
_BODY_JUST_INVOCATION_RE = re.compile(
    r"""(?im)(?:\bjust\b|\{\{\s*just\s*\}\})\s+(?P<target>[A-Za-z_][A-Za-z0-9_./:-]*)"""
)
_TARGET_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*(?:/[A-Za-z0-9_.:-]+)*$")
_RESERVED_LINE_PREFIXES = ("[", "alias ", "export ", "import ", "mod ", "set ", "unexport ")


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        in_quote: str | None = None
        escaped = False
        result: list[str] = []
        for char in raw_line:
            if char in {'"', "'"} and not escaped:
                in_quote = None if in_quote == char else char
            if char == "#" and in_quote is None:
                break
            result.append(char)
            escaped = char == "\\" and not escaped
        lines.append("".join(result))
    return "\n".join(lines)


def has_just_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in _KNOWN_SUFFIXES
        or normalized_path.name.lower() in JUSTFILE_BASENAMES
    )


def is_probable_just_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_just_path_hints(normalized_path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and (
        bool(_MARKER_RE.search(stripped_text))
        or any(part.lower() in _SUPPORT_DIRECTORIES for part in normalized_path.parts[:-1])
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if path.name.lower() in JUSTFILE_BASENAMES:
        return path.name if path.parent == PurePosixPath(".") else str(path.parent)
    return str(path.with_suffix(""))


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


def normalize_import_target(raw_target: str) -> str:
    return str(raw_target or "").strip().strip('"').strip("'").replace("\\", "/")


def _split_recipe_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or line[:1].isspace() or stripped.startswith("#"):
        return None
    lowered = stripped.lower()
    if lowered.startswith(_RESERVED_LINE_PREFIXES):
        return None
    if ":=" in stripped:
        assignment_index = stripped.index(":=")
        colon_index = stripped.find(":")
        if 0 <= colon_index < assignment_index:
            return None
    colon_index = stripped.find(":")
    if colon_index < 0 or stripped[colon_index : colon_index + 2] == ":=":
        return None
    return stripped[:colon_index].rstrip(), stripped[colon_index + 1 :].strip()


def is_operational_target_name(name: str) -> bool:
    normalized_name = str(name or "").strip()
    return bool(normalized_name) and _TARGET_NAME_RE.match(normalized_name) is not None and not (
        normalized_name.startswith("-")
        or normalized_name.startswith("$")
        or normalized_name in {"if", "else", "just"}
        or "{{" in normalized_name
        or "}}" in normalized_name
        or "=" in normalized_name
    )


def iter_alias_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _ALIAS_RE.finditer(stripped_text):
        item = (
            str(match.group("name") or "").strip(),
            str(match.group("target") or "").strip(),
            _line_number(stripped_text, match.start()),
        )
        if item[0] and item[1] and item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_import_targets(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    imports: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        target = normalize_import_target(str(match.group("target") or ""))
        if not target or "$" in target:
            continue
        item = (target, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            imports.append(item)
    return tuple(imports)


def iter_mod_targets(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    modules: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _MOD_RE.finditer(stripped_text):
        module_name = str(match.group("name") or "").strip()
        explicit_target = normalize_import_target(str(match.group("path") or ""))
        target = explicit_target or f"{module_name}.just"
        item = (module_name, target, _line_number(stripped_text, match.start()))
        if module_name and target and item not in seen:
            seen.add(item)
            modules.append(item)
    return tuple(modules)


def iter_recipe_entries(text: str) -> tuple[tuple[str, tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, tuple[str, ...], int]] = []
    seen: set[tuple[str, tuple[str, ...], int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        split_line = _split_recipe_line(raw_line)
        if split_line is None:
            continue
        header, dependency_section = split_line
        if header.startswith("@"):
            header = header[1:].lstrip()
        recipe_name = (header.split(maxsplit=1)[0] if header else "").strip()
        if not is_operational_target_name(recipe_name):
            continue
        dependency_names: list[str] = []
        seen_dependencies: set[str] = set()
        for match in _DEPENDENCY_TARGET_RE.finditer(dependency_section):
            candidate = str(match.group("paren") or match.group("bare") or "").strip()
            if not is_operational_target_name(candidate) or candidate in seen_dependencies:
                continue
            seen_dependencies.add(candidate)
            dependency_names.append(candidate)
        item = (recipe_name, tuple(dependency_names), line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for alias_name, _target_name, line_number in iter_alias_entries(text):
        item = (alias_name, "alias", line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    for recipe_name, _dependencies, line_number in iter_recipe_entries(text):
        item = (recipe_name, "recipe", line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(sorted(entries, key=lambda item: (item[2], item[0])))


def iter_reference_names(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for _alias_name, target_name, line_number in iter_alias_entries(stripped_text):
        if is_operational_target_name(target_name):
            item = (target_name, line_number)
            if item not in seen:
                seen.add(item)
                references.append(item)
    for _recipe_name, dependency_names, line_number in iter_recipe_entries(stripped_text):
        for dependency_name in dependency_names:
            if not is_operational_target_name(dependency_name):
                continue
            item = (dependency_name, line_number)
            if item not in seen:
                seen.add(item)
                references.append(item)
    for match in _BODY_JUST_INVOCATION_RE.finditer(stripped_text):
        target_name = str(match.group("target") or "").strip()
        if not is_operational_target_name(target_name):
            continue
        item = (target_name, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            references.append(item)
    return tuple(sorted(references, key=lambda item: (item[1], item[0])))
