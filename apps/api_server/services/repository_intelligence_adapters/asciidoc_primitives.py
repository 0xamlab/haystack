from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _ImportedSymbolBinding,
    _Symbol,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

ASCIIDOC_SUFFIXES = frozenset({".adoc", ".asciidoc", ".asc"})
ASCIIDOC_INDEX_BASENAMES = frozenset(
    {
        "contents.adoc",
        "contents.asciidoc",
        "index.adoc",
        "index.asciidoc",
        "readme.adoc",
        "readme.asciidoc",
    }
)
_COMMON_MODULE_ROOTS = frozenset(
    {
        "api",
        "doc",
        "docs",
        "documentation",
        "guide",
        "guides",
        "howto",
        "reference",
        "references",
        "source",
        "src",
        "tutorial",
        "tutorials",
    }
)
_SECTION_RE = re.compile(r"(?m)^(?P<level>={1,6})[ \t]+(?P<title>[^\r\n]+?)\s*$")
_BLOCK_ANCHOR_RE = re.compile(r"(?m)^[ \t]*\[\[(?P<name>[^\],\s][^\]]*)\]\][ \t]*$")
_INLINE_ANCHOR_RE = re.compile(r"(?m)^[ \t]*\[#(?P<name>[^\],\s][^\]]*)\][ \t]*$")
_INCLUDE_RE = re.compile(r"(?m)^[ \t]*include::(?P<target>[^\[\r\n]+)\[[^\r\n]*\][ \t]*$")
_XREF_RE = re.compile(r"xref:(?P<target>[^\[\s]+)\[[^\]]*\]")
_DOUBLE_ANGLE_XREF_RE = re.compile(r"<<(?P<target>[^>,]+)(?:,[^>]+)?>>")


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


@lru_cache(maxsize=256)
def _line_start_offsets(text: str) -> tuple[int, ...]:
    offsets = [0]
    for index, character in enumerate(text):
        if character == "\n":
            offsets.append(index + 1)
    return tuple(offsets)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return bisect_right(_line_start_offsets(text), bounded_offset)


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


@lru_cache(maxsize=256)
def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def has_asciidoc_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in ASCIIDOC_SUFFIXES


def is_probable_asciidoc_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in ASCIIDOC_SUFFIXES or not text or _looks_binaryish(text):
        return False
    return bool(text.strip())


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
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    if parts and parts[-1].lower() == "index":
        parts = parts[:-1]
    return ".".join(parts) if parts else without_suffix.stem


def _normalize_reference_target(value: str) -> str:
    return normalize_identifier(value).lstrip("#")


def _normalize_section_name(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_identifier(value))


def split_reference_target(value: str) -> tuple[str | None, str | None]:
    normalized = _normalize_reference_target(value)
    if not normalized:
        return None, None
    if "#" in normalized:
        path_part, anchor_part = normalized.split("#", 1)
        path_part = normalize_identifier(path_part)
        anchor_part = normalize_identifier(anchor_part)
        return path_part or None, anchor_part or None
    if "/" in normalized or PurePosixPath(normalized).suffix.lower() in ASCIIDOC_SUFFIXES:
        return normalized, None
    return None, normalized


@lru_cache(maxsize=256)
def _section_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _SECTION_RE.finditer(text):
        title = _normalize_section_name(str(match.group("title") or ""))
        if not title:
            continue
        entry = (title, "section", _line_number(text, match.start()))
        if entry in seen:
            continue
        seen.add(entry)
        entries.append(entry)
    return tuple(entries)


@lru_cache(maxsize=256)
def _iter_import_entries_cached(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _INCLUDE_RE.finditer(text):
        target = normalize_identifier(str(match.group("target") or ""))
        if not target:
            continue
        entry = ("include", target, _line_number(text, match.start()))
        if entry in seen:
            continue
        seen.add(entry)
        entries.append(entry)
    for pattern in (_XREF_RE, _DOUBLE_ANGLE_XREF_RE):
        for match in pattern.finditer(text):
            target = normalize_identifier(str(match.group("target") or ""))
            path_part, _anchor_part = split_reference_target(target)
            if not path_part:
                continue
            entry = ("xref", path_part, _line_number(text, match.start()))
            if entry in seen:
                continue
            seen.add(entry)
            entries.append(entry)
    return tuple(entries)


def iter_import_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    return _iter_import_entries_cached(text)


@lru_cache(maxsize=256)
def _iter_symbol_entries_cached(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = list(_section_entries(text))
    seen = {(name, kind, line) for name, kind, line in entries}
    for pattern in (_BLOCK_ANCHOR_RE, _INLINE_ANCHOR_RE):
        for match in pattern.finditer(text):
            anchor_name = normalize_identifier(str(match.group("name") or ""))
            if not anchor_name:
                continue
            entry = (anchor_name, "anchor", _line_number(text, match.start()))
            if entry in seen:
                continue
            seen.add(entry)
            entries.append(entry)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    return _iter_symbol_entries_cached(text)


@lru_cache(maxsize=256)
def _iter_reference_entries_cached(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for pattern in (_XREF_RE, _DOUBLE_ANGLE_XREF_RE):
        for match in pattern.finditer(text):
            target = normalize_identifier(str(match.group("target") or ""))
            if not target:
                continue
            entry = ("xref", target, _line_number(text, match.start()))
            if entry in seen:
                continue
            seen.add(entry)
            entries.append(entry)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    return _iter_reference_entries_cached(text)


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


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    target_path, _anchor_part = split_reference_target(import_target)
    candidate_target = target_path or normalize_identifier(import_target)
    if not candidate_target:
        return None
    if candidate_target in module_index:
        return module_index[candidate_target]
    current_parent = PurePosixPath(current_file).parent
    raw_target_path = PurePosixPath(candidate_target)
    candidate_paths: list[str] = []
    if raw_target_path.is_absolute():
        candidate_paths.append(normalize_repository_relative_path(str(raw_target_path)))
    else:
        candidate_paths.append(
            normalize_repository_relative_path(str(current_parent / raw_target_path))
        )
        candidate_paths.append(normalize_repository_relative_path(str(raw_target_path)))
    for candidate_path in candidate_paths:
        if not candidate_path:
            continue
        if candidate_path in module_index:
            return module_index[candidate_path]
        resolved = resolve_suffix_match(
            module_index=module_index,
            suffixes=tuple(
                normalize_repository_relative_path(f"{candidate_path}{suffix}")
                for suffix in sorted(ASCIIDOC_SUFFIXES)
            ),
        )
        if resolved is not None:
            return resolved
        resolved_index = resolve_suffix_match(
            module_index=module_index,
            suffixes=tuple(
                normalize_repository_relative_path(f"{candidate_path}/index{suffix}")
                for suffix in sorted(ASCIIDOC_SUFFIXES)
            ),
        )
        if resolved_index is not None:
            return resolved_index
    stem_name = normalize_identifier(Path(candidate_target).stem)
    if stem_name in module_index:
        return module_index[stem_name]
    return None


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    symbol_entries: tuple[tuple[str, str, int], ...] | None = None,
) -> tuple[_Symbol, ...]:
    if not is_probable_asciidoc_source(path=Path(file_path), text=text):
        return ()
    root_symbol = _Symbol(
        symbol_id=stable_identifier("sym", {"file_path": file_path, "name": module_name_from_path(file_path)}),
        symbol_name=module_name_from_path(file_path),
        symbol_kind="asciidoc",
        start_line=1,
        end_line=_line_count(text),
        parent_symbol_id=None,
        signature=None,
    )
    symbols: list[_Symbol] = [root_symbol]
    seen_symbol_names = {root_symbol.symbol_name}
    for symbol_name, symbol_kind, start_line in (
        symbol_entries if symbol_entries is not None else iter_symbol_entries(text)
    ):
        if symbol_name in seen_symbol_names:
            continue
        seen_symbol_names.add(symbol_name)
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "kind": symbol_kind,
                        "line": start_line,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=start_line,
                end_line=start_line,
                parent_symbol_id=root_symbol.symbol_id,
                signature=None,
            )
        )
    return tuple(symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
) -> set[str]:
    if text is None:
        candidate_path = root_path / file_path
        try:
            text = candidate_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    aliases = {
        normalize_identifier(file_path),
        normalize_identifier(PurePosixPath(file_path).name),
        normalize_identifier(PurePosixPath(file_path).stem),
        normalize_identifier(module_name_from_path(file_path)),
    }
    module_name = normalize_identifier(module_name_from_path(file_path))
    for symbol_name, symbol_kind, _line in iter_symbol_entries(text):
        aliases.add(symbol_name)
        if module_name and symbol_kind in {"section", "anchor"}:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    import_entries: tuple[tuple[str, str, int], ...] | None = None,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for _dependency_type, import_target, _line_number_value in (
        import_entries if import_entries is not None else iter_import_entries(text)
    ):
        target_file = resolve_import(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None:
            continue
        target_path, target_anchor = split_reference_target(import_target)
        module_name = module_name_from_path(target_file)
        stem_name = normalize_identifier(Path(target_file).stem)
        target_names = _ordered_names(target_anchor or "", stem_name, module_name)
        for alias in _ordered_names(
            stem_name,
            module_name,
            normalize_identifier(target_path or ""),
            normalize_identifier(Path(target_path or target_file).stem),
        ):
            bindings.setdefault(
                alias,
                _ImportedSymbolBinding(
                    alias=alias,
                    target_file=target_file,
                    target_names=target_names,
                ),
            )
    return bindings
