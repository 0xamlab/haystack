from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

ERB_SUFFIXES = frozenset({".erb", ".rhtml"})
_COMMON_MODULE_ROOTS = (
    ("app", "views"),
    ("views",),
    ("templates",),
)
_ERB_COMMENT_RE = re.compile(r"<%#.*?%>", re.DOTALL)
_RENDER_RE = re.compile(
    r"""(?msx)
    <%(?:=|-)?\s*render(?:\s*\()?\s*
    (?:
        (?:(?P<kind>partial|layout|template)\s*:\s*)?
        ["'](?P<target>[^"']+)["']
    )
    """
)
_CONTENT_FOR_RE = re.compile(
    r"""(?msx)
    <%(?:=|-)?\s*content_for\s*
    (?:\(\s*)?
    (?:
        :(?P<symbol_name>[A-Za-z_][A-Za-z0-9_-]*) |
        ["'](?P<quoted_name>[^"']+)["']
    )
    """
)
_YIELD_RE = re.compile(
    r"""(?msx)
    <%(?:=|-)?\s*yield\s*
    (?:\(\s*)?
    (?:
        :(?P<symbol_name>[A-Za-z_][A-Za-z0-9_-]*) |
        ["'](?P<quoted_name>[^"']+)["']
    )
    """
)
_RESOLVER_DIRS = (
    "app/views",
    "app/views/layouts",
    "app/views/pages",
    "app/views/shared",
    "app/views/components",
    "views",
    "layouts",
    "pages",
    "partials",
    "shared",
    "components",
    "templates",
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _ERB_COMMENT_RE.sub("", text)


def has_erb_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    suffix = normalized_path.suffix.lower()
    return suffix in ERB_SUFFIXES or normalized_path.name.lower().endswith(".html.erb")


def is_probable_erb_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_erb_path_hints(normalized_path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip())


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
    lowered_parts = [part.lower() for part in parts]
    for common_root in _COMMON_MODULE_ROOTS:
        root_length = len(common_root)
        if tuple(lowered_parts[:root_length]) == common_root:
            parts = parts[root_length:]
            break
    return ".".join(parts) if parts else without_suffix.name


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _RENDER_RE.finditer(stripped_text):
        dependency_kind = normalize_identifier(str(match.group("kind") or "partial")) or "partial"
        import_target = normalize_identifier(str(match.group("target") or ""))
        if not import_target:
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        item = (dependency_kind, import_target, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def _symbol_name_from_match(match: re.Match[str]) -> str:
    return normalize_identifier(
        str(match.group("symbol_name") or match.group("quoted_name") or "")
    )


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _CONTENT_FOR_RE.finditer(stripped_text):
        symbol_name = _symbol_name_from_match(match)
        if not symbol_name:
            continue
        item = (symbol_name, "section", stripped_text.count("\n", 0, match.start()) + 1)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for _dependency_kind, import_target, line_number in iter_dependency_entries(stripped_text):
        item = ("render", import_target, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    for match in _YIELD_RE.finditer(stripped_text):
        target_name = _symbol_name_from_match(match)
        if not target_name:
            continue
        item = ("section", target_name, stripped_text.count("\n", 0, match.start()) + 1)
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
    active_name: str | None = None
    active_line = -1
    for symbol_name, _symbol_kind, start_line in symbol_entries:
        if start_line <= line_number and start_line >= active_line:
            active_name = symbol_name
            active_line = start_line
    return active_name


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = _normalize_repository_relative_path(file_path)
    if not normalized_path or not has_erb_path_hints(PurePosixPath(normalized_path)):
        return set()
    aliases = {
        normalized_path,
        PurePosixPath(normalized_path).name,
        str(PurePosixPath(normalized_path).with_suffix("")),
        str(PurePosixPath(normalized_path).with_suffix("")).replace("/", "."),
    }
    try:
        text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_erb_source(path=normalized_path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(normalized_path)
    if module_name:
        aliases.add(module_name)
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
        aliases.add(symbol_name)
    return {alias for alias in aliases if alias}


def _candidate_paths_for_target(current_file: str, import_target: str) -> tuple[str, ...]:
    normalized_target = normalize_identifier(import_target).replace(".", "/")
    if not normalized_target:
        return ()
    target_path = PurePosixPath(normalized_target)
    base_candidates = {
        normalized_target,
        str(PurePosixPath(current_file).parent / normalized_target),
    }
    if target_path.name:
        partial_name = f"_{target_path.name}"
        partial_target = str(target_path.with_name(partial_name))
        base_candidates.add(partial_target)
        base_candidates.add(str(PurePosixPath(current_file).parent / partial_target))
    expanded: list[str] = []
    for candidate in sorted(base_candidates):
        expanded.append(candidate)
        for prefix in _RESOLVER_DIRS:
            expanded.append(str(PurePosixPath(prefix) / candidate))
    with_suffixes: list[str] = []
    for candidate in expanded:
        candidate_path = PurePosixPath(candidate)
        if candidate_path.suffix.lower() in ERB_SUFFIXES or candidate_path.name.lower().endswith(
            ".html.erb"
        ):
            with_suffixes.append(candidate)
            continue
        with_suffixes.append(f"{candidate}.erb")
        with_suffixes.append(f"{candidate}.html.erb")
    return tuple(dict.fromkeys(with_suffixes))


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
    candidates = _candidate_paths_for_target(current_file, import_target)
    seen_candidates: set[str] = set()
    for candidate in candidates:
        normalized_candidate = normalize_repository_relative_path(candidate)
        if not normalized_candidate or normalized_candidate in seen_candidates:
            continue
        seen_candidates.add(normalized_candidate)
        if normalized_candidate in module_index.values():
            return normalized_candidate
        resolved = module_index.get(normalized_candidate)
        if resolved is not None:
            return resolved
    suffixes = tuple(
        f"/{PurePosixPath(candidate).name}"
        for candidate in seen_candidates
        if PurePosixPath(candidate).suffix.lower() in ERB_SUFFIXES
        or PurePosixPath(candidate).name.lower().endswith(".html.erb")
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
            symbol_id=stable_identifier(
                "sym",
                {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "erb"},
            ),
            symbol_name=module_name,
            symbol_kind="erb",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"erb {module_name}",
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=start_line,
                end_line=start_line,
                parent_symbol_id=symbols[0].symbol_id,
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)
