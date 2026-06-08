from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

EJS_SUFFIXES = frozenset({".ejs"})
_COMMON_MODULE_ROOTS = frozenset(
    {"components", "includes", "layouts", "pages", "partials", "templates", "views"}
)
_COMMENT_RE = re.compile(r"<%#.*?%>", re.S)
_BLOCK_RE = re.compile(r"<%(?P<prefix>[=-]?)(?P<body>.*?)%>", re.S)
_FUNCTION_DEF_RE = re.compile(r"\bfunction\s+(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s*\(")
_FUNCTION_CALL_RE = re.compile(r"(?<![\w.])(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s*\(")
_INCLUDE_CALL_RE = re.compile(r"""(?<![\w.])include\s*\(\s*['"](?P<target>[^'"]+)['"]""")
_INCLUDE_STMT_RE = re.compile(r"(?<![\w.])include\s+(?P<target>[A-Za-z0-9_./-]+)")
_LIKELY_EJS_RE = re.compile(r"<%[-=#]?(?:.|\n)*?%>")
_REFERENCE_EXCLUDES = frozenset(
    {
        "catch",
        "else",
        "for",
        "function",
        "if",
        "include",
        "locals",
        "Math",
        "Promise",
        "require",
        "return",
        "switch",
        "while",
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
    return _COMMENT_RE.sub(
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
        text,
    )


def has_ejs_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in EJS_SUFFIXES


def is_probable_ejs_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in EJS_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_LIKELY_EJS_RE.search(stripped_text))


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


def _iter_blocks(text: str) -> tuple[tuple[str, int, int], ...]:
    stripped_text = strip_comments(text)
    blocks: list[tuple[str, int, int]] = []
    for match in _BLOCK_RE.finditer(stripped_text):
        body = str(match.group("body") or "")
        if not body.strip():
            continue
        blocks.append((body, match.start(), stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(blocks)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for body, _offset, line_number in _iter_blocks(text):
        for target_match in _INCLUDE_CALL_RE.finditer(body):
            import_target = normalize_identifier(str(target_match.group("target") or ""))
            if not import_target:
                continue
            item = ("include", import_target, line_number)
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
        for target_match in _INCLUDE_STMT_RE.finditer(body):
            import_target = normalize_identifier(str(target_match.group("target") or ""))
            if not import_target:
                continue
            item = ("include", import_target, line_number)
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for body, _offset, line_number in _iter_blocks(text):
        for call_match in _FUNCTION_CALL_RE.finditer(body):
            name = normalize_identifier(str(call_match.group("name") or ""))
            if not name or name in _REFERENCE_EXCLUDES:
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
    best_name: str | None = None
    best_line = -1
    for symbol_name, symbol_kind, symbol_line in symbol_entries:
        if symbol_kind != "function" or symbol_line > line_number or symbol_line < best_line:
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
    if path.suffix.lower() not in EJS_SUFFIXES:
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
    if text and not is_probable_ejs_source(path=path, text=text):
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
    if not any(PurePosixPath(candidate).suffix.lower() in EJS_SUFFIXES for candidate in candidates):
        candidates.extend(f"{candidate}.ejs" for candidate in tuple(candidates))
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
        if PurePosixPath(candidate).suffix.lower() in EJS_SUFFIXES
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
                {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "ejs"},
            ),
            symbol_name=module_name,
            symbol_kind="ejs",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"ejs {module_name}",
        )
    ]
    for body, offset, _line_number in _iter_blocks(text):
        for match in _FUNCTION_DEF_RE.finditer(body):
            function_name = normalize_identifier(str(match.group("name") or ""))
            if not function_name:
                continue
            start_offset = offset + match.start()
            start_line = text.count("\n", 0, start_offset) + 1
            symbols.append(
                _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": function_name,
                            "symbol_kind": "function",
                        },
                    ),
                    symbol_name=function_name,
                    symbol_kind="function",
                    start_line=start_line,
                    end_line=start_line,
                    parent_symbol_id=symbols[0].symbol_id,
                    signature=f"function {function_name}",
                )
            )
    return tuple(symbols)
