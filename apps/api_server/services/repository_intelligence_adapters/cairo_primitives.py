from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    rust_language as repository_rust_language,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

CAIRO_SUFFIXES = frozenset({".cairo"})
CAIRO_CONFIG_BASENAMES = frozenset({"scarb.toml"})
_SOURCE_ROOTS = ("src", "contracts", "crates", "examples", "tests")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"(?m)//.*$")
_SOURCE_MARKER_RE = re.compile(
    r"(?im)^\s*(?:fn|struct|enum|trait|impl|mod|use|const|extern|type)\b|^\s*#\[|\bcontract\b"
)
_CONFIG_MARKER_RE = re.compile(
    r"(?im)^\s*\[(?:package|dependencies|dev-dependencies|scripts|tool(?:\.[A-Za-z0-9_-]+)?)\]\s*$"
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _preserve_line_count_comment(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def strip_comments(text: str) -> str:
    without_block_comments = _BLOCK_COMMENT_RE.sub(_preserve_line_count_comment, text)
    return _LINE_COMMENT_RE.sub("", without_block_comments)


def has_cairo_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in CAIRO_SUFFIXES
        or normalized_path.name.lower() in CAIRO_CONFIG_BASENAMES
    )


def is_probable_cairo_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in CAIRO_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(_SOURCE_MARKER_RE.search(stripped_text))


def is_probable_cairo_config(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).name.lower() not in CAIRO_CONFIG_BASENAMES or not text:
        return False
    stripped_text = strip_comments(text)
    return bool(_CONFIG_MARKER_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _SOURCE_ROOTS:
        parts = parts[1:]
    if parts and parts[-1].lower() in {"lib", "main", "mod"}:
        parts = parts[:-1]
    if not parts:
        return ""
    return ".".join(parts)


def declared_symbol_names(text: str) -> tuple[str, ...]:
    stripped_text = strip_comments(text)
    names: list[str] = []
    seen: set[str] = set()
    for line in stripped_text.splitlines():
        match = repository_rust_language.SYMBOL_LINE_RE.match(line.strip())
        if match is None:
            continue
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name or symbol_name in seen:
            continue
        seen.add(symbol_name)
        names.append(symbol_name)
    return tuple(names)
