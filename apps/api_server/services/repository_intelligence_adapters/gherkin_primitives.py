from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

GHERKIN_SUFFIXES = frozenset({".feature"})
GHERKIN_INDEX_BASENAMES = frozenset({"index.feature", "readme.feature"})
_COMMON_MODULE_ROOTS = frozenset(
    {
        "acceptance",
        "acceptance_tests",
        "bdd",
        "doc",
        "docs",
        "feature",
        "features",
        "spec",
        "specs",
        "test",
        "tests",
    }
)
_COMMENT_RE = re.compile(r"(?m)^[ \t]*#.*$")
_KEYWORD_PREFIXES = {
    "feature:": "feature",
    "rule:": "rule",
    "background:": "background",
    "scenario outline:": "scenario_outline",
    "scenario:": "scenario",
    "examples:": "examples",
    "example:": "examples",
}


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def has_gherkin_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in GHERKIN_SUFFIXES


def is_probable_gherkin_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in GHERKIN_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    lowered_text = stripped_text.lower()
    return any(prefix in lowered_text for prefix in _KEYWORD_PREFIXES)


def normalize_identifier(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).strip(":")


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


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


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


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    if parts and parts[-1].lower() == "index":
        parts = parts[:-1]
    return ".".join(parts) if parts else without_suffix.stem


def _keyword_entry_for_line(raw_line: str) -> tuple[str, str] | None:
    stripped_line = raw_line.strip()
    if not stripped_line or stripped_line.startswith("@") or ":" not in stripped_line:
        return None
    lowered_line = stripped_line.lower()
    for prefix, kind in _KEYWORD_PREFIXES.items():
        if lowered_line.startswith(prefix):
            return kind, normalize_identifier(stripped_line[len(prefix) :])
    return None


def _background_symbol_name(*, feature_name: str | None, rule_name: str | None, raw_name: str) -> str:
    base_name = raw_name or "Background"
    if rule_name:
        return normalize_identifier(f"{rule_name}::{base_name}")
    if feature_name:
        return normalize_identifier(f"{feature_name}::{base_name}")
    return base_name


def _examples_symbol_name(*, outline_name: str | None, raw_name: str, ordinal: int) -> str:
    base_name = raw_name or f"Examples {ordinal}"
    if outline_name:
        return normalize_identifier(f"{outline_name}::{base_name}")
    return base_name


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    current_feature_name: str | None = None
    current_rule_name: str | None = None
    scenario_count = 0
    outline_count = 0
    examples_count = 0
    for line_number, raw_line in enumerate(strip_comments(text).splitlines(), start=1):
        keyword_entry = _keyword_entry_for_line(raw_line)
        if keyword_entry is None:
            continue
        kind, raw_name = keyword_entry
        if kind == "feature":
            current_feature_name = raw_name or "Feature"
            current_rule_name = None
            entries.append((current_feature_name, kind, line_number))
            continue
        if kind == "rule":
            current_rule_name = raw_name or "Rule"
            entries.append((current_rule_name, kind, line_number))
            continue
        if kind == "background":
            entries.append(
                (
                    _background_symbol_name(
                        feature_name=current_feature_name,
                        rule_name=current_rule_name,
                        raw_name=raw_name,
                    ),
                    kind,
                    line_number,
                )
            )
            continue
        if kind == "scenario_outline":
            outline_count += 1
            entries.append((raw_name or f"Scenario Outline {outline_count}", kind, line_number))
            continue
        if kind == "scenario":
            scenario_count += 1
            entries.append((raw_name or f"Scenario {scenario_count}", kind, line_number))
            continue
        if kind == "examples":
            examples_count += 1
            outline_name = next(
                (
                    name
                    for name, symbol_kind, symbol_line in reversed(entries)
                    if symbol_kind == "scenario_outline" and symbol_line < line_number
                ),
                None,
            )
            entries.append(
                (
                    _examples_symbol_name(
                        outline_name=outline_name,
                        raw_name=raw_name,
                        ordinal=examples_count,
                    ),
                    kind,
                    line_number,
                )
            )
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    current_feature_name: str | None = None
    current_rule_name: str | None = None
    feature_background_name: str | None = None
    rule_background_name: str | None = None
    current_outline_name: str | None = None
    scenario_count = 0
    outline_count = 0
    examples_count = 0
    for line_number, raw_line in enumerate(strip_comments(text).splitlines(), start=1):
        keyword_entry = _keyword_entry_for_line(raw_line)
        if keyword_entry is None:
            continue
        kind, raw_name = keyword_entry
        if kind == "feature":
            current_feature_name = raw_name or "Feature"
            current_rule_name = None
            feature_background_name = None
            rule_background_name = None
            current_outline_name = None
            continue
        if kind == "rule":
            current_rule_name = raw_name or "Rule"
            rule_background_name = None
            current_outline_name = None
            continue
        if kind == "background":
            background_name = _background_symbol_name(
                feature_name=current_feature_name,
                rule_name=current_rule_name,
                raw_name=raw_name,
            )
            if current_rule_name:
                rule_background_name = background_name
            else:
                feature_background_name = background_name
            continue
        if kind == "scenario_outline":
            outline_count += 1
            current_outline_name = raw_name or f"Scenario Outline {outline_count}"
            active_background = rule_background_name or feature_background_name
            if active_background:
                entries.append(("background", active_background, line_number))
            continue
        if kind == "scenario":
            scenario_count += 1
            current_outline_name = None
            active_background = rule_background_name or feature_background_name
            if active_background:
                entries.append(("background", active_background, line_number))
            continue
        if kind == "examples":
            examples_count += 1
            if current_outline_name:
                entries.append(("scenario_outline", current_outline_name, line_number))
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
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in GHERKIN_SUFFIXES:
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
    module_name = module_name_from_path(normalized_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and is_probable_gherkin_source(path=path, text=text):
        for symbol_name, symbol_kind, _line_number in iter_symbol_entries(text):
            if symbol_kind == "gherkin":
                continue
            aliases.update(_ordered_names(symbol_name, f"{module_name}.{symbol_name}" if module_name else ""))
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    line_count = _line_count(text)
    module_name = module_name_from_path(file_path) or PurePosixPath(file_path).stem or "feature"
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "gherkin"},
        ),
        symbol_name=module_name,
        symbol_kind="gherkin",
        start_line=1,
        end_line=line_count,
        parent_symbol_id=None,
        signature=f"gherkin {module_name}",
    )
    symbols: list[_Symbol] = [module_symbol]
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                        "line": line_number,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol.symbol_id,
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)
