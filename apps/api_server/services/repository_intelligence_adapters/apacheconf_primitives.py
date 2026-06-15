from __future__ import annotations

import re
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Callable

StableIdentifier = Callable[[str, object], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[[str, dict[str, str], tuple[str, ...]], str | None]

APACHECONF_SUFFIXES = frozenset({".conf", ".load"})
APACHECONF_INDEX_BASENAMES = frozenset(
    {
        ".htaccess",
        "apache2.conf",
        "httpd.conf",
        "ports.conf",
    }
)
APACHECONF_PATH_PARTS = frozenset(
    {
        "apache",
        "apache2",
        "apache24",
        "conf-available",
        "conf-enabled",
        "conf.d",
        "httpd",
        "httpd.conf.d",
        "httpd.d",
        "mods-available",
        "mods-enabled",
        "sites-available",
        "sites-enabled",
        "vhosts.d",
    }
)
_APACHE_DIRECTIVE_NAMES = frozenset(
    {
        "alias",
        "allowoverride",
        "customlog",
        "define",
        "directoryindex",
        "documentroot",
        "errorlog",
        "errordocument",
        "header",
        "include",
        "includeoptional",
        "listen",
        "loadmodule",
        "redirect",
        "require",
        "rewriteengine",
        "rewritecond",
        "rewriterule",
        "serveradmin",
        "servername",
        "serveralias",
        "serverroot",
        "setenvif",
        "sslengine",
    }
)
_APACHE_BLOCK_NAMES = frozenset(
    {
        "directory",
        "files",
        "ifmodule",
        "location",
        "macro",
        "virtualhost",
    }
)
_HTACCESS_DIRECTIVE_NAMES = frozenset(
    {
        "allow",
        "allowoverride",
        "deny",
        "directoryindex",
        "errordocument",
        "header",
        "options",
        "order",
        "redirect",
        "require",
        "rewriteengine",
        "rewritecond",
        "rewriterule",
        "setenvif",
    }
)

_DEFINE_RE = re.compile(r"^\s*Define\s+([A-Za-z_][\w.-]*)\b", re.IGNORECASE | re.MULTILINE)
_MACRO_RE = re.compile(r"^\s*<Macro\s+([A-Za-z_][\w.-]*)\b", re.IGNORECASE | re.MULTILINE)
_USE_RE = re.compile(r"^\s*Use\s+([A-Za-z_][\w.-]*)\b", re.IGNORECASE | re.MULTILINE)
_INCLUDE_RE = re.compile(
    r"^\s*(IncludeOptional|Include)\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s#]+))",
    re.IGNORECASE | re.MULTILINE,
)
_VARIABLE_RE = re.compile(r"\$\{[^}]+\}")


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _line_count(text: str) -> int:
    return max(text.count("\n") + 1, 1)


def strip_comments(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        pieces: list[str] = []
        quote: str | None = None
        escaped = False
        for character in raw_line:
            if escaped:
                pieces.append(character)
                escaped = False
                continue
            if character == "\\":
                pieces.append(character)
                escaped = True
                continue
            if quote:
                pieces.append(character)
                if character == quote:
                    quote = None
                continue
            if character in {'"', "'"}:
                pieces.append(character)
                quote = character
                continue
            if character == "#":
                break
            pieces.append(character)
        cleaned_lines.append("".join(pieces).rstrip())
    return "\n".join(cleaned_lines)


def has_apacheconf_path_hints(path: Path) -> bool:
    lower_name = path.name.lower()
    if lower_name in APACHECONF_INDEX_BASENAMES:
        return True
    if path.suffix.lower() not in APACHECONF_SUFFIXES:
        return False
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts & APACHECONF_PATH_PARTS:
        return True
    return lower_name in {"apache2.conf", "httpd.conf", "ports.conf"}


def _iter_directive_names(text: str) -> tuple[str, ...]:
    directives: list[str] = []
    for raw_line in strip_comments(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("<"):
            directive_name = line[1:].split(None, 1)[0].rstrip(">").lower()
        else:
            directive_name = line.split(None, 1)[0].lower()
        directives.append(directive_name)
    return tuple(directives)


def is_probable_apacheconf_source(*, path: Path, text: str) -> bool:
    if not has_apacheconf_path_hints(path):
        return False
    directives = _iter_directive_names(text)
    if not directives:
        return False
    if path.name.lower() == ".htaccess":
        return any(
            directive in _HTACCESS_DIRECTIVE_NAMES or directive in _APACHE_BLOCK_NAMES
            for directive in directives
        )
    return any(
        directive in _APACHE_DIRECTIVE_NAMES or directive in _APACHE_BLOCK_NAMES
        for directive in directives
    )


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    for match in _DEFINE_RE.finditer(text):
        entries.append(("define", match.group(1), _line_number(text, match.start())))
    for match in _MACRO_RE.finditer(text):
        entries.append(("macro", match.group(1), _line_number(text, match.start())))
    return tuple(entries)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    for match in _INCLUDE_RE.finditer(text):
        raw_target = next(
            value for value in match.groups()[1:] if isinstance(value, str) and value.strip()
        )
        entries.append(
            (
                match.group(1).lower(),
                raw_target.strip(),
                _line_number(text, match.start()),
            )
        )
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    return tuple(
        ("use", match.group(1), _line_number(text, match.start()))
        for match in _USE_RE.finditer(text)
    )


def module_name_from_path(file_path: str) -> str:
    normalized_path = file_path.replace("\\", "/").strip("/")
    path = PurePosixPath(normalized_path)
    if path.name == ".htaccess":
        return ".htaccess"
    return path.stem or path.name


def path_aliases_for_file(file_path: str) -> set[str]:
    normalized_path = file_path.replace("\\", "/").strip("/")
    path = PurePosixPath(normalized_path)
    aliases = {normalized_path, path.name, module_name_from_path(normalized_path)}
    if path.name != ".htaccess":
        aliases.add(str(path.with_suffix("")))
        if str(path.parent) not in {"", "."}:
            aliases.add(f"{path.parent}/{path.stem}")
    return {alias for alias in aliases if alias}


def resolve_include_targets(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str, ...]:
    stripped_target = _VARIABLE_RE.sub("", import_target).strip().strip("\"'")
    if not stripped_target or stripped_target.startswith("/"):
        return ()
    current_parent = PurePosixPath(current_file).parent
    candidate_patterns = [
        normalize_repository_relative_path(str(current_parent / stripped_target)),
        normalize_repository_relative_path(stripped_target),
    ]
    resolved_targets: set[str] = set()
    module_values = tuple(sorted(set(module_index.values())))
    for candidate_pattern in candidate_patterns:
        if not candidate_pattern:
            continue
        if any(token in candidate_pattern for token in "*?["):
            for candidate_path in module_values:
                if fnmatchcase(candidate_path, candidate_pattern):
                    resolved_targets.add(candidate_path)
            continue
        direct_target = (
            module_index.get(candidate_pattern)
            or module_index.get(PurePosixPath(candidate_pattern).name)
        )
        if direct_target:
            resolved_targets.add(direct_target)
        if candidate_pattern in module_values:
            resolved_targets.add(candidate_pattern)
    return tuple(sorted(resolved_targets))


__all__ = [
    "APACHECONF_INDEX_BASENAMES",
    "APACHECONF_SUFFIXES",
    "NormalizeRepositoryRelativePath",
    "ResolveSuffixMatch",
    "StableIdentifier",
    "has_apacheconf_path_hints",
    "is_probable_apacheconf_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_name_from_path",
    "path_aliases_for_file",
    "resolve_include_targets",
    "strip_comments",
]
