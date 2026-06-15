from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".coffee", ".litcoffee"})
_COFFEESCRIPT_SHEBANG_RE = re.compile(
    r"^#![^\n]*\b(?:coffee|iced|coffeescript)\b",
    re.IGNORECASE,
)
_CLASS_DECL_RE = re.compile(
    r"^(?P<indent>\s*)class\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)(?:\s+extends\s+(?P<extends>[A-Za-z_$][A-Za-z0-9_$.]*))?\b"
)
_FUNCTION_ASSIGN_RE = re.compile(
    r"^(?P<indent>\s*)(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*(?P<separator>[:=])\s*(?:\((?P<params>[^)]*)\)\s*)?(?P<arrow>[-=]>)(?=\s|$)"
)
_EXPORT_FUNCTION_ASSIGN_RE = re.compile(
    r"^(?P<indent>\s*)(?:module\.exports|exports)\.(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:\((?P<params>[^)]*)\)\s*)?(?P<arrow>[-=]>)(?=\s|$)"
)
_REQUIRE_ASSIGN_RE = re.compile(
    r"^(?P<indent>\s*)(?:(?P<object>\{[^}]+\})|(?P<alias>[A-Za-z_$][A-Za-z0-9_$]*))\s*=\s*require\s*(?:\(\s*)?(?P<quote>['\"])(?P<target>[^'\"]+)(?P=quote)\s*\)?",
    re.MULTILINE,
)
_REQUIRE_SIDE_EFFECT_RE = re.compile(
    r"^(?P<indent>\s*)require\s*(?:\(\s*)?(?P<quote>['\"])(?P<target>[^'\"]+)(?P=quote)\s*\)?",
    re.MULTILINE,
)
_IMPORT_FROM_RE = re.compile(
    r"^(?P<indent>\s*)import\s+(?P<clause>.+?)\s+from\s+(?P<quote>['\"])(?P<target>[^'\"]+)(?P=quote)",
    re.MULTILINE,
)
_IMPORT_SIDE_EFFECT_RE = re.compile(
    r"^(?P<indent>\s*)import\s+(?P<quote>['\"])(?P<target>[^'\"]+)(?P=quote)",
    re.MULTILINE,
)
_QUALIFIED_CALL_RE = re.compile(
    r"(?<![A-Za-z0-9_$])(?P<owner>[A-Za-z_$][A-Za-z0-9_$]*)\s*\.\s*(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*(?=\()"
)
_BARE_CALL_RE = re.compile(
    r"(?<![.$A-Za-z0-9_])(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*(?=\()"
)
_NEW_RE = re.compile(r"\bnew\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\b")
_INSTANCE_ASSIGN_RE = re.compile(
    r"^\s*(?P<alias>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*new\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\b",
    re.MULTILINE,
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "break",
        "catch",
        "class",
        "continue",
        "debugger",
        "delete",
        "do",
        "else",
        "extends",
        "false",
        "finally",
        "for",
        "if",
        "import",
        "in",
        "instanceof",
        "new",
        "null",
        "require",
        "return",
        "super",
        "switch",
        "then",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "unless",
        "until",
        "when",
        "while",
        "yes",
        "no",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _normalize_source_text(*, path: Path, text: str) -> str:
    if path.suffix.lower() != ".litcoffee":
        return text
    normalized_lines: list[str] = []
    for raw_line in text.splitlines():
        if raw_line.startswith("\t"):
            normalized_lines.append(raw_line[1:])
            continue
        if raw_line.startswith("    "):
            normalized_lines.append(raw_line[4:])
            continue
        normalized_lines.append("" if raw_line.strip() else "")
    return "\n".join(normalized_lines)


def _strip_comments_preserving_lines(text: str) -> str:
    result_lines: list[str] = []
    in_block_comment = False
    for raw_line in text.splitlines():
        if not raw_line:
            result_lines.append("")
            continue
        line = raw_line
        if in_block_comment:
            end_index = line.find("###")
            if end_index == -1:
                result_lines.append("")
                continue
            line = line[end_index + 3 :]
            in_block_comment = False
        output: list[str] = []
        in_string: str | None = None
        escaped = False
        index = 0
        while index < len(line):
            character = line[index]
            if in_string is not None:
                output.append(character)
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == in_string:
                    in_string = None
                index += 1
                continue
            if line.startswith("###", index):
                end_index = line.find("###", index + 3)
                if end_index == -1:
                    in_block_comment = True
                    break
                index = end_index + 3
                continue
            if character in {'"', "'"}:
                in_string = character
                output.append(character)
                index += 1
                continue
            if character == "#" and not (index == 0 and line.startswith("#!")):
                break
            output.append(character)
            index += 1
        result_lines.append("".join(output))
    return "\n".join(result_lines)


@lru_cache(maxsize=1024)
def _strip_comments_cached(text: str) -> str:
    return _strip_comments_preserving_lines(text)


def strip_comments(text: str) -> str:
    if "#" not in text:
        return text
    return _strip_comments_cached(text)


def has_coffeescript_path_hints(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in _KNOWN_SUFFIXES:
        return True
    return path.name.lower() == "cakefile"


def has_coffeescript_shebang(text: str) -> bool:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    return bool(_COFFEESCRIPT_SHEBANG_RE.search(first_line))


def is_probable_coffeescript_source(*, path: Path, text: str) -> bool:
    if has_coffeescript_path_hints(path):
        return True
    if has_coffeescript_shebang(text):
        return True
    normalized_text = _normalize_source_text(path=path, text=text)
    stripped_text = strip_comments(normalized_text)
    if _CLASS_DECL_RE.search(stripped_text):
        return True
    if _FUNCTION_ASSIGN_RE.search(stripped_text):
        return True
    if _EXPORT_FUNCTION_ASSIGN_RE.search(stripped_text):
        return True
    if _REQUIRE_ASSIGN_RE.search(stripped_text) or _REQUIRE_SIDE_EFFECT_RE.search(stripped_text):
        return True
    return bool(
        _IMPORT_FROM_RE.search(stripped_text)
        or _IMPORT_SIDE_EFFECT_RE.search(stripped_text)
    )


def normalize_identifier(value: str) -> str:
    return str(value or "").strip()


def module_symbol_name(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if path.name.lower() == "cakefile":
        return "Cakefile"
    stem = path.stem or path.name
    if path.suffix.lower() == ".litcoffee" and stem.endswith(".lit"):
        stem = stem[: -len(".lit")]
    return stem


def _normalize_import_target(raw_target: str) -> str:
    normalized_target = str(raw_target or "").strip()
    if not normalized_target:
        return ""
    normalized_target = normalized_target.replace("\\", "/")
    if normalized_target.startswith("./"):
        return normalized_target
    return normalized_target


def import_targets_for_text(text: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen_targets: set[str] = set()
    for pattern in (
        _REQUIRE_ASSIGN_RE,
        _REQUIRE_SIDE_EFFECT_RE,
        _IMPORT_FROM_RE,
        _IMPORT_SIDE_EFFECT_RE,
    ):
        for match in pattern.finditer(text):
            normalized_target = _normalize_import_target(str(match.group("target") or ""))
            if not normalized_target or normalized_target in seen_targets:
                continue
            seen_targets.add(normalized_target)
            targets.append(normalized_target)
    return tuple(targets)


def _indent_width(raw_line: str) -> int:
    return len(raw_line) - len(raw_line.lstrip(" "))


def _find_block_end_line(lines: tuple[str, ...], *, start_index: int, start_indent: int) -> int:
    last_content_index = start_index
    for index in range(start_index + 1, len(lines)):
        raw_line = lines[index]
        if not raw_line.strip():
            continue
        indent = _indent_width(raw_line)
        if indent <= start_indent:
            break
        last_content_index = index
    return last_content_index + 1


def _raw_symbol_entries(
    *,
    file_path: str,
    text: str,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int, int, str | None, str | None], ...]:
    path = Path(file_path)
    normalized_text = _normalize_source_text(path=path, text=text)
    candidate_stripped_text = stripped_text if stripped_text is not None else strip_comments(
        normalized_text
    )
    lines = tuple(line.expandtabs(4) for line in candidate_stripped_text.splitlines())
    module_name = module_symbol_name(file_path)
    raw_entries: list[tuple[str, str, int, int, str | None, str | None]] = [
        (module_name, "module", 1, _line_count(candidate_stripped_text), None, None)
    ]
    class_entries: list[dict[str, Any]] = []
    for index, raw_line in enumerate(lines):
        match = _CLASS_DECL_RE.match(raw_line)
        if match is None:
            continue
        class_name = normalize_identifier(match.group("name") or "")
        if not class_name:
            continue
        start_line = index + 1
        indent = len(match.group("indent") or "")
        end_line = _find_block_end_line(lines, start_index=index, start_indent=indent)
        signature = f"class {class_name}"
        raw_entries.append((class_name, "class", start_line, end_line, module_name, signature))
        class_entries.append(
            {
                "name": class_name,
                "indent": indent,
                "start_index": index,
                "end_index": max(index, end_line - 1),
            }
        )
    for index, raw_line in enumerate(lines):
        match = _FUNCTION_ASSIGN_RE.match(raw_line) or _EXPORT_FUNCTION_ASSIGN_RE.match(raw_line)
        if match is None:
            continue
        function_name = normalize_identifier(match.group("name") or "")
        if not function_name or function_name in _RESERVED_SYMBOL_NAMES:
            continue
        start_line = index + 1
        indent = len(match.group("indent") or "")
        separator = str(match.groupdict().get("separator") or "=")
        parent_name = module_name
        symbol_kind = "function"
        if separator == ":":
            parent_class = next(
                (
                    entry
                    for entry in reversed(class_entries)
                    if entry["start_index"] < index <= entry["end_index"]
                    and indent > int(entry["indent"])
                ),
                None,
            )
            if parent_class is None:
                continue
            parent_name = str(parent_class["name"])
            symbol_kind = "method"
        elif indent != 0:
            continue
        end_line = _find_block_end_line(lines, start_index=index, start_indent=indent)
        signature = f"{function_name} = {match.group('arrow') or '->'}"
        raw_entries.append(
            (function_name, symbol_kind, start_line, end_line, parent_name, signature)
        )
    return tuple(
        sorted(
            raw_entries,
            key=lambda item: (
                item[2],
                item[3],
                0 if item[1] == "module" else 1,
                item[0],
            ),
        )
    )


def collect_symbol_entries(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[_CollectedSymbol, ...]:
    raw_entries = _raw_symbol_entries(
        file_path=file_path,
        text=text,
        stripped_text=stripped_text,
    )
    symbol_ids_by_name_and_kind: dict[tuple[str, str, int], str] = {}
    for symbol_name, symbol_kind, start_line, _end_line, _parent_name, _signature in raw_entries:
        symbol_ids_by_name_and_kind[(symbol_name, symbol_kind, start_line)] = stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": start_line,
            },
        )
    collected_symbols: list[_CollectedSymbol] = []
    for symbol_name, symbol_kind, start_line, end_line, parent_name, signature in raw_entries:
        parent_symbol_id = None
        if parent_name is not None:
            if symbol_kind == "class":
                parent_symbol_id = symbol_ids_by_name_and_kind.get((parent_name, "module", 1))
            elif symbol_kind in {"function", "method"}:
                parent_kind = "class" if symbol_kind == "method" else "module"
                parent_symbol_id = symbol_ids_by_name_and_kind.get((parent_name, parent_kind, 1))
                if parent_symbol_id is None and parent_kind == "class":
                    parent_symbol_id = next(
                        (
                            stable_id
                            for (name, kind, _line), stable_id in symbol_ids_by_name_and_kind.items()
                            if name == parent_name and kind == "class"
                        ),
                        None,
                    )
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=symbol_ids_by_name_and_kind[(symbol_name, symbol_kind, start_line)],
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=start_line,
                    end_line=end_line,
                    parent_symbol_id=parent_symbol_id,
                    signature=signature,
                ),
                local_start_line=start_line,
                local_end_line=end_line,
            )
        )
    return tuple(collected_symbols)
