from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".bat", ".cmd"})
_SUPPORT_DIRECTORIES = frozenset({"bin", "scripts", "tools", "cmd", "build", "install", "deploy"})
_LABEL_RE = re.compile(r"(?im)^\s*:(?!:)(?P<name>[A-Za-z0-9_./-]+)\s*$")
_CALL_LABEL_RE = re.compile(r"(?im)^\s*call\s+:(?P<name>[A-Za-z0-9_./-]+)\b")
_GOTO_LABEL_RE = re.compile(r"(?im)^\s*goto\s+:(?P<name>[A-Za-z0-9_./-]+)\b")
_SCRIPT_CALL_RE = re.compile(
    r"(?im)^\s*(?:call\s+)?(?P<target>(?:\"[^\"]+\.(?:bat|cmd)\"|[^\s&|<>]+\.(?:bat|cmd)))\b"
)
_MARKER_RE = re.compile(r"(?im)^\s*(?:@?echo\s+off|setlocal|call|goto|if|for|set)\b")
_RESERVED_SYMBOL_NAMES = frozenset({"eof"})
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "assoc",
        "break",
        "call",
        "cd",
        "chcp",
        "cls",
        "copy",
        "del",
        "dir",
        "echo",
        "endlocal",
        "erase",
        "exit",
        "for",
        "goto",
        "if",
        "md",
        "mkdir",
        "mklink",
        "move",
        "pause",
        "popd",
        "pushd",
        "rd",
        "rem",
        "rename",
        "ren",
        "rmdir",
        "set",
        "setlocal",
        "shift",
        "start",
        "title",
        "type",
    }
)


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        stripped_line = raw_line.lstrip()
        lowered = stripped_line.lower()
        if stripped_line.startswith("::") or lowered == "rem" or lowered.startswith("rem "):
            lines.append("")
            continue
        lines.append(raw_line)
    return "\n".join(lines)


def has_batchfile_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_batchfile_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_batchfile_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and (
        bool(_MARKER_RE.search(stripped_text))
        or bool(_LABEL_RE.search(stripped_text))
        or bool(_SCRIPT_CALL_RE.search(stripped_text))
        or any(part.lower() in _SUPPORT_DIRECTORIES for part in PurePosixPath(path).parts[:-1])
    )


def module_name_from_path(file_path: str) -> str:
    return str(PurePosixPath(file_path).with_suffix("")).replace("\\", "/")


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


def normalize_call_target(raw_target: str) -> str:
    normalized_target = str(raw_target or "").strip().strip('"').strip("'").replace("\\", "/")
    for marker in ("%~dp0/", "%~dp0\\", "%~dp0"):
        normalized_target = normalized_target.replace(marker, "./")
    return normalized_target.strip()


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _LABEL_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name or symbol_name.lower() in _RESERVED_SYMBOL_NAMES:
            continue
        item = (symbol_name, "label", _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(sorted(entries, key=lambda item: (item[2], item[0])))


def iter_script_calls(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    calls: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _SCRIPT_CALL_RE.finditer(stripped_text):
        normalized_target = normalize_call_target(match.group("target") or "")
        if not normalized_target or normalized_target.startswith(":"):
            continue
        item = (normalized_target, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            calls.append(item)
    return tuple(calls)


def iter_label_references(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for regex in (_CALL_LABEL_RE, _GOTO_LABEL_RE):
        for match in regex.finditer(stripped_text):
            target_name = str(match.group("name") or "").strip()
            if not target_name or target_name.lower() in _RESERVED_REFERENCE_NAMES:
                continue
            item = (target_name, _line_number(stripped_text, match.start()))
            if item not in seen:
                seen.add(item)
                references.append(item)
    return tuple(sorted(references, key=lambda item: (item[1], item[0])))


def iter_reference_names(text: str) -> tuple[tuple[str, int], ...]:
    return iter_label_references(text)


def is_operational_reference_name(name: str) -> bool:
    normalized_name = str(name or "").strip()
    return bool(normalized_name) and normalized_name.lower() not in _RESERVED_REFERENCE_NAMES
