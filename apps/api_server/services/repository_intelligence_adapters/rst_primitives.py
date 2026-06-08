from __future__ import annotations

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

RST_SUFFIXES = frozenset({".rst", ".rest"})
RST_INDEX_BASENAMES = frozenset({"index.rst", "index.rest"})
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
_SECTION_UNDERLINE_CHARS = frozenset({"=", "-", "~", "^", '"', "#", "*", "+", "`", ":"})
_LABEL_RE = re.compile(r"(?m)^[ \t]*\.\.\s+_(?P<name>[A-Za-z0-9:_./-]+)\s*:\s*$")
_INCLUDE_RE = re.compile(
    r"(?m)^[ \t]*\.\.\s+(?P<kind>include|literalinclude)\s*::\s*(?P<target>[^\r\n]+?)\s*$"
)
_TOCTREE_RE = re.compile(r"(?m)^(?P<indent>[ \t]*)\.\.\s+toctree\s*::\s*$")
_DOC_REF_RE = re.compile(r":doc:`(?P<target>[^`]+)`")
_REF_RE = re.compile(r":ref:`(?P<target>[^`]+)`")


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


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


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def has_rst_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in RST_SUFFIXES


def is_probable_rst_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in RST_SUFFIXES or not text or _looks_binaryish(text):
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


def _normalize_doc_target(value: str) -> str:
    normalized = normalize_identifier(value)
    if "<" in normalized and normalized.endswith(">"):
        normalized = normalized.rsplit("<", 1)[-1][:-1].strip()
    return normalized


def _normalize_section_name(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_identifier(value))


def _section_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    lines = text.splitlines()
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for index in range(len(lines) - 1):
        title = lines[index].strip()
        underline = lines[index + 1].strip()
        if not title or len(underline) < len(title):
            continue
        if len(set(underline)) != 1 or underline[0] not in _SECTION_UNDERLINE_CHARS:
            continue
        entry = (_normalize_section_name(title), "section", index + 1)
        if not entry[0] or entry in seen:
            continue
        seen.add(entry)
        entries.append(entry)
    return tuple(entries)


def iter_import_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _INCLUDE_RE.finditer(text):
        target = normalize_identifier(str(match.group("target") or ""))
        if not target:
            continue
        entry = (normalize_identifier(str(match.group("kind") or "")), target, _line_number(text, match.start()))
        if entry in seen:
            continue
        seen.add(entry)
        entries.append(entry)
    lines = text.splitlines()
    for match in _TOCTREE_RE.finditer(text):
        indent = len(match.group("indent") or "")
        start_line = _line_number(text, match.start())
        for line_index in range(start_line, len(lines)):
            raw_line = lines[line_index]
            stripped = raw_line.strip()
            if not stripped:
                continue
            current_indent = len(raw_line) - len(raw_line.lstrip(" \t"))
            if current_indent <= indent:
                break
            if stripped.startswith(":"):
                continue
            target = _normalize_doc_target(stripped)
            if not target or target == "self":
                continue
            entry = ("toctree", target, line_index + 1)
            if entry in seen:
                continue
            seen.add(entry)
            entries.append(entry)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = list(_section_entries(text))
    seen = {(name, kind, line) for name, kind, line in entries}
    for match in _LABEL_RE.finditer(text):
        label_name = normalize_identifier(str(match.group("name") or ""))
        if not label_name:
            continue
        entry = (label_name, "label", _line_number(text, match.start()))
        if entry in seen:
            continue
        seen.add(entry)
        entries.append(entry)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _DOC_REF_RE.finditer(text):
        target = _normalize_doc_target(str(match.group("target") or ""))
        if not target:
            continue
        entry = ("doc", target, _line_number(text, match.start()))
        if entry in seen:
            continue
        seen.add(entry)
        entries.append(entry)
    for match in _REF_RE.finditer(text):
        target = _normalize_doc_target(str(match.group("target") or ""))
        if not target:
            continue
        entry = ("ref", target, _line_number(text, match.start()))
        if entry in seen:
            continue
        seen.add(entry)
        entries.append(entry)
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


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_doc_target(import_target).replace("\\", "/")
    if not normalized_target or normalized_target == "self":
        return None
    current_parent = PurePosixPath(current_file).parent
    candidate_paths = [
        normalized_target,
        str(current_parent / normalized_target),
    ]
    if "." not in PurePosixPath(normalized_target).name:
        candidate_paths.extend(f"{candidate}.rst" for candidate in tuple(candidate_paths))
        candidate_paths.extend(f"{candidate}.rest" for candidate in tuple(candidate_paths))
        candidate_paths.extend(f"{candidate}/index.rst" for candidate in tuple(candidate_paths[:2]))
        candidate_paths.extend(f"{candidate}/index.rest" for candidate in tuple(candidate_paths[:2]))
    for candidate in dict.fromkeys(candidate_paths):
        normalized_candidate = normalize_repository_relative_path(candidate)
        if not normalized_candidate:
            continue
        direct_match = module_index.get(normalized_candidate) or module_index.get(
            normalized_candidate.replace("/", ".")
        )
        if direct_match:
            return direct_match
        resolved = resolve_suffix_match(
            module_index=module_index,
            suffixes=(f"/{PurePosixPath(normalized_candidate).name}",),
        )
        if resolved:
            return resolved
        if normalized_candidate in module_index.values():
            return normalized_candidate
    return None


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for _dependency_kind, import_target, _line_number in iter_import_entries(text):
        target_file = resolve_import(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None:
            continue
        target_module_name = module_name_from_path(target_file)
        aliases = _ordered_names(
            import_target,
            _normalize_doc_target(import_target),
            PurePosixPath(import_target).stem,
            PurePosixPath(target_file).stem,
            target_module_name,
        )
        target_names = _ordered_names(target_module_name, PurePosixPath(target_file).stem)
        for alias in aliases:
            bindings[alias] = _ImportedSymbolBinding(
                alias=alias,
                target_file=target_file,
                target_names=target_names,
            )
    return bindings


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    line_count = _line_count(text)
    module_name = module_name_from_path(file_path) or PurePosixPath(file_path).stem
    root_symbol = _Symbol(
        symbol_id=stable_identifier("symbol", {"file_path": file_path, "name": module_name, "kind": "rst"}),
        symbol_name=module_name,
        symbol_kind="rst",
        start_line=1,
        end_line=line_count,
        parent_symbol_id=None,
        signature=None,
    )
    symbols: list[_Symbol] = [root_symbol]
    seen_names = {("rst", module_name, 1)}
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(text):
        key = (symbol_kind, symbol_name, start_line)
        if key in seen_names:
            continue
        seen_names.add(key)
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
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
) -> set[str]:
    del stable_identifier
    normalized_path = _normalize_repository_relative_path(file_path)
    if not normalized_path or not has_rst_path_hints(PurePosixPath(normalized_path)):
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
    if text and not is_probable_rst_source(path=normalized_path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(normalized_path)
    if module_name:
        aliases.add(module_name)
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
        aliases.add(symbol_name)
        aliases.add(f"{module_name}.{symbol_name}" if module_name else symbol_name)
    return {alias for alias in aliases if alias}
