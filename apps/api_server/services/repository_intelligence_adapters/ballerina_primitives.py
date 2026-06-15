from __future__ import annotations

from bisect import bisect_right
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

BALLERINA_SUFFIXES = frozenset({".bal"})
BALLERINA_CONFIG_BASENAMES = frozenset({"ballerina.toml"})
_IMPORT_RE = re.compile(
    r"(?mi)^\s*import\s+"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_.]*)?)"
    r"(?:\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?\s*;"
)
_FUNCTION_RE = re.compile(
    r"(?mi)^\s*(?:public\s+)?(?:isolated\s+)?(?:remote\s+)?(?:transactional\s+)?"
    r"function\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_CLASS_RE = re.compile(
    r"(?mi)^\s*(?:public\s+)?(?:client\s+)?(?:isolated\s+)?class\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_TYPE_RE = re.compile(
    r"(?mi)^\s*(?:public\s+)?type\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_CONST_RE = re.compile(
    r"(?mi)^\s*(?:public\s+)?const\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_ENUM_RE = re.compile(
    r"(?mi)^\s*(?:public\s+)?enum\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<qualifier>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_CALL_RE = re.compile(r"(?<![:.])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b(?=\s*\()")
_CONFIG_SECTION_RE = re.compile(r"(?mi)^\s*\[(?:package|build-options|tool\.[^\]]+)\]\s*$")
_CONFIG_FIELD_RE = re.compile(r"(?mi)^\s*(?:org|name|distribution|version)\s*=")
_SOURCE_MARKER_RE = re.compile(
    r"(?mi)(?:^\s*import\s+[A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_.]*)?\s*;"
    r"|^\s*(?:public\s+)?(?:isolated\s+)?(?:remote\s+)?function\s+[A-Za-z_][A-Za-z0-9_]*\b"
    r"|^\s*(?:public\s+)?(?:client\s+)?(?:isolated\s+)?class\s+[A-Za-z_][A-Za-z0-9_]*\b"
    r"|^\s*(?:public\s+)?type\s+[A-Za-z_][A-Za-z0-9_]*\b"
    r"|^\s*(?:public\s+)?service\s+"
    r"|^\s*listener\s+"
    r"|\b[A-Za-z_][A-Za-z0-9_]*\s*:\s*[A-Za-z_][A-Za-z0-9_]*\b)"
)
_DECLARATION_PREFIXES = (
    "function ",
    "public function ",
    "isolated function ",
    "remote function ",
    "class ",
    "public class ",
    "client class ",
    "type ",
    "public type ",
    "const ",
    "public const ",
    "enum ",
    "public enum ",
)
_RESERVED_NAMES = frozenset(
    {
        "annotation",
        "as",
        "boolean",
        "break",
        "byte",
        "check",
        "checkpanic",
        "class",
        "client",
        "const",
        "continue",
        "decimal",
        "else",
        "enum",
        "error",
        "false",
        "final",
        "float",
        "foreach",
        "from",
        "function",
        "future",
        "if",
        "import",
        "in",
        "int",
        "isolated",
        "json",
        "listener",
        "map",
        "new",
        "object",
        "public",
        "readonly",
        "record",
        "remote",
        "resource",
        "return",
        "service",
        "stream",
        "string",
        "table",
        "transactional",
        "trap",
        "true",
        "type",
        "typedesc",
        "var",
        "while",
        "xml",
    }
)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return bisect_right(_line_start_offsets(text), offset)


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


@lru_cache(maxsize=1024)
def _line_start_offsets(text: str) -> tuple[int, ...]:
    starts = [0]
    search_from = 0
    while True:
        newline_index = text.find("\n", search_from)
        if newline_index < 0:
            break
        search_from = newline_index + 1
        starts.append(search_from)
    return tuple(starts)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


@lru_cache(maxsize=1024)
def _strip_comments_cached(text: str) -> str:
    characters: list[str] = []
    index = 0
    in_block_comment = False
    in_string = False
    string_delimiter = ""
    while index < len(text):
        character = text[index]
        next_two = text[index : index + 2]
        if in_block_comment:
            if next_two == "*/":
                characters.extend((" ", " "))
                index += 2
                in_block_comment = False
                continue
            characters.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string:
            characters.append(character)
            if character == string_delimiter and (index == 0 or text[index - 1] != "\\"):
                in_string = False
                string_delimiter = ""
            index += 1
            continue
        if next_two == "/*":
            characters.extend((" ", " "))
            index += 2
            in_block_comment = True
            continue
        if next_two == "//" or character == "#":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        characters.append(character)
        if character in {'"', "'", "`"}:
            in_string = True
            string_delimiter = character
        index += 1
    return "".join(characters)


def strip_comments(text: str) -> str:
    if "/*" not in text and "//" not in text and "#" not in text:
        return text
    return _strip_comments_cached(text)


def _coalesced_stripped_text(
    text: str,
    *,
    stripped_text: str | None = None,
) -> str:
    if stripped_text is not None:
        return stripped_text
    return strip_comments(text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_ballerina_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in BALLERINA_SUFFIXES
        or normalized_path.name.lower() in BALLERINA_CONFIG_BASENAMES
    )


def is_probable_ballerina_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in BALLERINA_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = _coalesced_stripped_text(text, stripped_text=stripped_text)
    return _is_probable_ballerina_source_from_stripped_text(stripped_text)


def is_probable_ballerina_config(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    if (
        normalized_path.name.lower() not in BALLERINA_CONFIG_BASENAMES
        or not text
        or _looks_binaryish(text)
    ):
        return False
    stripped_text = _coalesced_stripped_text(text, stripped_text=stripped_text)
    return _is_probable_ballerina_config_from_stripped_text(stripped_text)


@lru_cache(maxsize=1024)
def _is_probable_ballerina_source_from_stripped_text(
    stripped_text: str,
) -> bool:
    if not stripped_text.strip():
        return False
    return _SOURCE_MARKER_RE.search(stripped_text) is not None


@lru_cache(maxsize=256)
def _is_probable_ballerina_config_from_stripped_text(
    stripped_text: str,
) -> bool:
    return bool(_CONFIG_SECTION_RE.search(stripped_text) or _CONFIG_FIELD_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    for anchor in ("ballerina", "generated"):
        if anchor in parts:
            parts = parts[parts.index(anchor) + 1 :]
            break
    if "modules" in parts:
        parts = parts[parts.index("modules") + 1 :]
    if parts and parts[-1] == "main" and len(parts) > 1:
        parts = parts[:-1]
    normalized_parts = [part for part in parts if part not in {"", "."}]
    if not normalized_parts:
        return without_suffix.stem
    return ".".join(normalized_parts)


def clean_import_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if "://" in cleaned:
        return ""
    return cleaned


def import_alias_for_target(import_target: str) -> str:
    cleaned_target = clean_import_target(import_target)
    if not cleaned_target:
        return ""
    module_segment = cleaned_target.split("/", 1)[-1]
    return module_segment.split(".")[-1].strip()


def iter_import_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = _coalesced_stripped_text(text, stripped_text=stripped_text)
    entries: list[tuple[str, str | None, int]] = []
    for match in _IMPORT_RE.finditer(stripped_text):
        target = clean_import_target(match.group("target") or "")
        alias = normalize_identifier(match.group("alias") or "") or None
        if not target:
            continue
        entries.append((target, alias, _line_number(stripped_text, match.start())))
    return tuple(entries)


@lru_cache(maxsize=1024)
def _iter_symbol_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, symbol_kind in (
        (_TYPE_RE, "type"),
        (_CLASS_RE, "class"),
        (_CONST_RE, "constant"),
        (_ENUM_RE, "enum"),
        (_FUNCTION_RE, "function"),
    ):
        for match in regex.finditer(stripped_text):
            name = normalize_identifier(match.group("name") or "")
            if not name or name in seen_names or name in _RESERVED_NAMES:
                continue
            seen_names.add(name)
            entries.append((name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = _coalesced_stripped_text(text, stripped_text=stripped_text)
    return _iter_symbol_entries_from_stripped_text(stripped_text)


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[_Symbol, ...]:
    stripped_text = _coalesced_stripped_text(text, stripped_text=stripped_text)
    module_name = module_name_from_path(file_path)
    final_line = _line_count(stripped_text)
    symbols: list[_Symbol] = []
    module_symbol_id = stable_identifier(
        "sym",
        {
            "file_path": file_path,
            "symbol_name": module_name,
            "symbol_kind": "module",
            "start_line": 1,
        },
    )
    symbols.append(
        _Symbol(
            symbol_id=module_symbol_id,
            symbol_name=module_name,
            symbol_kind="module",
            start_line=1,
            end_line=final_line,
            parent_symbol_id=None,
            signature=f"module {module_name}" if module_name else None,
        )
    )
    symbol_entries = iter_symbol_entries(stripped_text, stripped_text=stripped_text)
    for index, (name, kind, start_line) in enumerate(symbol_entries):
        next_start_line = (
            symbol_entries[index + 1][2] if index + 1 < len(symbol_entries) else final_line + 1
        )
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": name,
                        "symbol_kind": kind,
                        "start_line": start_line,
                    },
                ),
                symbol_name=name,
                symbol_kind=kind,
                start_line=start_line,
                end_line=max(start_line, next_start_line - 1),
                parent_symbol_id=module_symbol_id,
                signature=name,
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    selected_name: str | None = None
    for symbol_name, _symbol_kind, start_line in symbol_entries:
        if start_line > line_number:
            break
        selected_name = symbol_name
    return selected_name


def iter_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = _coalesced_stripped_text(text, stripped_text=stripped_text)
    return _iter_reference_entries_from_stripped_text(stripped_text)


@lru_cache(maxsize=1024)
def _iter_reference_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[str | None, str, int], ...]:
    entries: list[tuple[str | None, str, int]] = []
    seen: set[tuple[str | None, str, int]] = set()
    for match in _QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        qualifier = normalize_identifier(match.group("qualifier") or "")
        name = normalize_identifier(match.group("name") or "")
        if (
            not qualifier
            or not name
            or qualifier in _RESERVED_NAMES
            or name in _RESERVED_NAMES
        ):
            continue
        entry = (qualifier, name, _line_number(stripped_text, match.start()))
        if entry not in seen:
            seen.add(entry)
            entries.append(entry)
    for match in _CALL_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in _RESERVED_NAMES:
            continue
        line_number = _line_number(stripped_text, match.start())
        line_start = stripped_text.rfind("\n", 0, match.start()) + 1
        line_text = stripped_text[line_start : stripped_text.find("\n", match.start())]
        normalized_line = line_text.strip().lower()
        if normalized_line.startswith(_DECLARATION_PREFIXES):
            continue
        entry = (None, name, line_number)
        if entry not in seen:
            seen.add(entry)
            entries.append(entry)
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    normalized_path = str(PurePosixPath(file_path))
    if PurePosixPath(normalized_path).suffix.lower() not in BALLERINA_SUFFIXES:
        return set()
    module_name = module_name_from_path(normalized_path)
    aliases = {
        normalized_path,
        PurePosixPath(normalized_path).name,
        str(PurePosixPath(normalized_path).with_suffix("")),
        PurePosixPath(normalized_path).stem,
        module_name,
        module_name.replace(".", "/"),
    }
    loaded_text = text
    if loaded_text is None:
        try:
            loaded_text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            loaded_text = ""
    candidate_stripped_text = _coalesced_stripped_text(
        loaded_text,
        stripped_text=stripped_text,
    )
    if not is_probable_ballerina_source(
        path=Path(normalized_path),
        text=loaded_text,
        stripped_text=candidate_stripped_text,
    ):
        return {alias for alias in aliases if alias}
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    for symbol_name, symbol_kind, _line_number in iter_symbol_entries(
        loaded_text,
        stripped_text=candidate_stripped_text,
    ):
        aliases.add(symbol_name)
        if module_name and symbol_kind != "module":
            aliases.add(f"{module_name}.{symbol_name}")
            aliases.add(f"{module_name.replace('.', '/')}/{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    cleaned_target = clean_import_target(import_target)
    if not cleaned_target:
        return None
    module_segment = cleaned_target.split("/", 1)[-1]
    slash_segment = module_segment.replace(".", "/")
    dot_segment = slash_segment.replace("/", ".")
    leaf = slash_segment.split("/")[-1]
    candidate_keys: list[str] = []
    for candidate in (
        cleaned_target,
        cleaned_target.replace("/", "."),
        module_segment,
        slash_segment,
        dot_segment,
        leaf,
        f"ballerina/{slash_segment}",
        f"ballerina/{dot_segment}",
        f"ballerina/modules/{slash_segment}",
        f"ballerina/modules/{slash_segment}/main",
        f"modules/{slash_segment}",
        f"modules/{slash_segment}/main",
    ):
        normalized_candidate = normalize_repository_relative_path(candidate)
        if normalized_candidate:
            candidate_keys.append(normalized_candidate)
        if candidate:
            candidate_keys.append(candidate)
    current_dir = PurePosixPath(current_file).parent
    for relative_candidate in (
        current_dir / slash_segment,
        current_dir / leaf,
        current_dir / f"{leaf}.bal",
    ):
        normalized_candidate = normalize_repository_relative_path(relative_candidate)
        if normalized_candidate:
            candidate_keys.append(normalized_candidate)
    for candidate_key in dict.fromkeys(candidate_keys):
        direct_match = module_index.get(candidate_key)
        if direct_match is not None and direct_match != current_file:
            return direct_match
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(
            dict.fromkeys(
                (
                    f"{slash_segment}.bal",
                    f"{dot_segment}.bal",
                    f"{slash_segment}/main.bal",
                    f"ballerina/{slash_segment}.bal",
                    f"ballerina/{slash_segment}/main.bal",
                    f"ballerina/modules/{slash_segment}.bal",
                    f"ballerina/modules/{slash_segment}/main.bal",
                    f"modules/{slash_segment}.bal",
                    f"modules/{slash_segment}/main.bal",
                    f"/{leaf}.bal",
                    f"/{leaf}/main.bal",
                )
            )
        ),
    )
