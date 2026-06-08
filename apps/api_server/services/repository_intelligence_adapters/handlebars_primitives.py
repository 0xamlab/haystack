from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

HANDLEBARS_SUFFIXES = frozenset({".hbs", ".handlebars"})
_COMMON_MODULE_ROOTS = frozenset(
    {"components", "includes", "layouts", "pages", "partials", "templates", "views"}
)
_COMMENT_RE = re.compile(r"\{\{!--.*?--\}\}|\{\{!.*?\}\}", re.S)
_EXPRESSION_RE = re.compile(r"\{\{(?P<body>.*?)\}\}", re.S)
_IDENTIFIER_RE = re.compile(r"(?<![\w.])(?P<name>[A-Za-z_][A-Za-z0-9_-]*)")
_QUOTED_TARGET_RE = re.compile(r"""['"](?P<target>[^'"]+)['"]""")
_TARGET_TOKEN_RE = re.compile(r"(?P<target>@?[A-Za-z0-9_./-]+)")
_REFERENCE_EXCLUDES = frozenset(
    {
        "@index",
        "@key",
        "@root",
        "@first",
        "@last",
        "else",
        "each",
        "if",
        "ifEquals",
        "unless",
        "with",
        "lookup",
        "log",
    }
)
_RESOLVER_DIRS = ("partials", "layouts", "templates", "components", "views", "includes")


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)), text)


def has_handlebars_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in HANDLEBARS_SUFFIXES


def is_probable_handlebars_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in HANDLEBARS_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return "{{" in stripped_text and "}}" in stripped_text


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


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


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _EXPRESSION_RE.finditer(stripped_text):
        body = str(match.group("body") or "").strip()
        if not body:
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        dependency_kind: str | None = None
        target_text = body
        if body.startswith("#>"):
            dependency_kind = "partial"
            target_text = body[2:].strip()
        elif body.startswith(">"):
            dependency_kind = "partial"
            target_text = body[1:].strip()
        if dependency_kind is None:
            continue
        target_match = _QUOTED_TARGET_RE.search(target_text) or _TARGET_TOKEN_RE.search(target_text)
        if not target_match:
            continue
        target = normalize_identifier(str(target_match.group("target") or ""))
        if not target or target.startswith("@") or target.startswith("("):
            continue
        item = (dependency_kind, target, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _EXPRESSION_RE.finditer(stripped_text):
        body = str(match.group("body") or "")
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        if body.lstrip().startswith((">", "#>")):
            continue
        for identifier_match in _IDENTIFIER_RE.finditer(body):
            name = normalize_identifier(str(identifier_match.group("name") or ""))
            if not name or name in _REFERENCE_EXCLUDES or name.startswith("@"):
                continue
            item = (name, line_number)
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, str, int]],
    *,
    line_number: int,
) -> str | None:
    del symbol_entries, line_number
    return None


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in HANDLEBARS_SUFFIXES:
        return set()
    normalized_path = _normalize_repository_relative_path(file_path)
    if not normalized_path:
        return set()
    aliases = {
        normalized_path,
        path.name,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_handlebars_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(normalized_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.replace("/", "."))
    stem = PurePosixPath(normalized_path).stem
    if stem:
        aliases.add(stem)
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    dependency_kind: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    del dependency_kind
    normalized_target = normalize_identifier(import_target)
    if not normalized_target:
        return None
    current_parent = PurePosixPath(current_file).parent
    candidates: list[str] = [normalized_target]
    if "/" not in normalized_target:
        candidates.extend(f"{directory}/{normalized_target}" for directory in _RESOLVER_DIRS)
    candidates.append(str(current_parent / normalized_target))
    if not any(PurePosixPath(candidate).suffix.lower() in HANDLEBARS_SUFFIXES for candidate in candidates):
        candidates.extend(f"{candidate}.hbs" for candidate in tuple(candidates))
    seen_candidates: set[str] = set()
    for candidate in candidates:
        normalized_candidate = normalize_repository_relative_path(candidate)
        if not normalized_candidate or normalized_candidate in seen_candidates:
            continue
        seen_candidates.add(normalized_candidate)
        if normalized_candidate in module_index.values():
            return normalized_candidate
        if normalized_candidate in module_index:
            return module_index[normalized_candidate]
        if normalized_candidate in module_index.values():
            return normalized_candidate
    suffixes = tuple(
        f"/{PurePosixPath(candidate).name}"
        for candidate in seen_candidates
        if PurePosixPath(candidate).suffix.lower() in HANDLEBARS_SUFFIXES
    )
    if suffixes:
        return resolve_suffix_match(module_index=module_index, suffixes=suffixes)
    return None


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    line_count = max(1, len(text.splitlines()) or 1)
    module_name = module_name_from_path(file_path) or PurePosixPath(file_path).stem or "template"
    module_symbol = _Symbol(
        symbol_id=stable_identifier("sym", {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "handlebars"}),
        symbol_name=module_name,
        symbol_kind="handlebars",
        start_line=1,
        end_line=line_count,
        parent_symbol_id=None,
        signature=f"handlebars {module_name}",
    )
    return (module_symbol,)
