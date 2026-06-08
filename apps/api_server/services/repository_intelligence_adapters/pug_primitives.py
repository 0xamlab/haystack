from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

PUG_SUFFIXES = frozenset({".jade", ".pug"})
_COMMON_MODULE_ROOTS = frozenset(
    {"components", "includes", "layouts", "mixins", "pages", "partials", "templates", "views"}
)
_COMMENT_LINE_RE = re.compile(r"(?m)^[ \t]*//-?.*$")
_DEPENDENCY_RE = re.compile(r"(?m)^(?P<indent>[ \t]*)(?P<kind>extends|include)\s+(?P<target>[^\s]+)")
_MIXIN_DEF_RE = re.compile(r"(?m)^(?P<indent>[ \t]*)mixin\s+(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_MIXIN_CALL_RE = re.compile(r"(?m)^(?P<indent>[ \t]*)\+(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_LIKELY_PUG_RE = re.compile(
    r"(?m)^[ \t]*(doctype\b|html\b|head\b|body\b|extends\b|include\b|mixin\b|\+[A-Za-z_]|[A-Za-z][A-Za-z0-9:_-]*[.#( ]?)"
)
_RESOLVER_DIRS = ("partials", "layouts", "templates", "components", "views", "includes", "mixins")


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_LINE_RE.sub("", text)


def has_pug_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in PUG_SUFFIXES


def is_probable_pug_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in PUG_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_LIKELY_PUG_RE.search(stripped_text))


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
    for match in _DEPENDENCY_RE.finditer(stripped_text):
        dependency_kind = normalize_identifier(str(match.group("kind") or ""))
        import_target = normalize_identifier(str(match.group("target") or ""))
        if not dependency_kind or not import_target:
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        item = (dependency_kind, import_target, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _MIXIN_CALL_RE.finditer(stripped_text):
        target_name = normalize_identifier(str(match.group("name") or ""))
        if not target_name:
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        item = (target_name, line_number)
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
    best_name: str | None = None
    best_line = -1
    for symbol_name, symbol_kind, symbol_line in symbol_entries:
        if symbol_kind != "mixin" or symbol_line > line_number or symbol_line < best_line:
            continue
        best_name, best_line = symbol_name, symbol_line
    return best_name


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in PUG_SUFFIXES:
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
    if text and not is_probable_pug_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(normalized_path)
    if module_name:
        aliases.add(module_name)
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
    candidates: list[str] = [normalized_target, str(current_parent / normalized_target)]
    if "/" not in normalized_target:
        candidates.extend(f"{directory}/{normalized_target}" for directory in _RESOLVER_DIRS)
    if not any(PurePosixPath(candidate).suffix.lower() in PUG_SUFFIXES for candidate in candidates):
        candidates.extend(f"{candidate}.pug" for candidate in tuple(candidates))
        candidates.extend(f"{candidate}.jade" for candidate in tuple(candidates))
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
    suffixes = tuple(
        f"/{PurePosixPath(candidate).name}"
        for candidate in seen_candidates
        if PurePosixPath(candidate).suffix.lower() in PUG_SUFFIXES
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes) if suffixes else None


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    line_count = max(1, len(text.splitlines()) or 1)
    module_name = module_name_from_path(file_path) or PurePosixPath(file_path).stem or "template"
    symbols = [
        _Symbol(
            symbol_id=stable_identifier("sym", {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "pug"}),
            symbol_name=module_name,
            symbol_kind="pug",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"pug {module_name}",
        )
    ]
    for match in _MIXIN_DEF_RE.finditer(strip_comments(text)):
        mixin_name = normalize_identifier(str(match.group("name") or ""))
        if not mixin_name:
            continue
        start_line = text.count("\n", 0, match.start()) + 1
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier("sym", {"file_path": file_path, "symbol_name": mixin_name, "symbol_kind": "mixin"}),
                symbol_name=mixin_name,
                symbol_kind="mixin",
                start_line=start_line,
                end_line=start_line,
                parent_symbol_id=symbols[0].symbol_id,
                signature=f"mixin {mixin_name}",
            )
        )
    return tuple(symbols)
