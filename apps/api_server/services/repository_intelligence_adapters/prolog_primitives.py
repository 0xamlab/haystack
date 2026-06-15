from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveImport = Callable[[str, str, dict[str, str]], str | None]
ResolveTarget = Callable[[str, str, dict[str, str]], str | None]

_KNOWN_PROLOG_SUFFIXES = (".pl", ".prolog")
_PROLOG_SOURCE_ROOTS = ("src", "lib", "prolog", "app")
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "!",
        "call",
        "consult",
        "dynamic",
        "ensure_loaded",
        "fail",
        "false",
        "findall",
        "forall",
        "format",
        "if",
        "include",
        "initialization",
        "is",
        "module",
        "multifile",
        "nl",
        "not",
        "once",
        "op",
        "phrase",
        "reexport",
        "repeat",
        "set_prolog_flag",
        "true",
        "use_module",
        "var",
        "write",
        "writeln",
    }
)
_PROLOG_DIRECTIVE_PREFIXES = frozenset(
    {
        "consult",
        "dynamic",
        "discontiguous",
        "ensure_loaded",
        "include",
        "initialization",
        "module",
        "multifile",
        "op",
        "reexport",
        "set_prolog_flag",
        "use_module",
    }
)
_PERL_MARKER_RE = re.compile(
    r"\b(?:use\s+strict|use\s+warnings|sub\s+[A-Za-z_][A-Za-z0-9_]*|"
    r"package\s+[A-Za-z_:][A-Za-z0-9_:]*|my\s+\$|our\s+\$|shift\b)\b",
    re.IGNORECASE,
)
_HEAD_RE = re.compile(
    r"^(?:(?P<module>[a-z][A-Za-z0-9_]*)\s*:\s*)?"
    r"(?P<name>[a-z][A-Za-z0-9_]*)"
    r"(?:\s*\((?P<args>.*)\))?$"
)
_MODULE_DIRECTIVE_RE = re.compile(
    r"^\s*:-\s*module\s*\(\s*(?P<name>[a-z][A-Za-z0-9_]*)\s*(?:,|$)",
    re.IGNORECASE,
)
_USE_MODULE_DIRECTIVE_RE = re.compile(
    r"^\s*:-\s*(?P<kind>use_module|reexport)\s*\(\s*(?P<target>.+?)\s*\)\s*$",
    re.IGNORECASE,
)
_LOAD_DIRECTIVE_RE = re.compile(
    r"^\s*:-\s*(?P<kind>consult|ensure_loaded|include)\s*\(\s*(?P<target>.+?)\s*\)\s*$",
    re.IGNORECASE,
)
_LIST_LOAD_DIRECTIVE_RE = re.compile(
    r"^\s*:-\s*\[(?P<body>[^\]]+)\]\s*$",
    re.IGNORECASE,
)
_IMPORT_NAME_RE = re.compile(r"(?P<name>[a-z][A-Za-z0-9_]*)(?:\s*/\s*\d+)?")
_QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<module>[a-z][A-Za-z0-9_]*)\s*:\s*(?P<name>[a-z][A-Za-z0-9_]*)\s*(?=\()"
)
_CALL_RE = re.compile(r"\b(?P<name>[a-z][A-Za-z0-9_]*)\s*(?=\()")


def _replace_with_spaces(value: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in value)


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


def normalize_identifier(raw_name: str) -> str:
    normalized = str(raw_name or "").strip().strip(".")
    if not normalized:
        return ""
    return normalized.lower()


def _normalize_target_name(raw_target: str) -> str:
    normalized = str(raw_target or "").strip().strip("'\"")
    if not normalized:
        return ""
    library_match = re.fullmatch(
        r"library\s*\(\s*(?P<name>[^()]+)\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    if library_match is not None:
        normalized = str(library_match.group("name") or "").strip()
    normalized = normalized.replace("\\", "/")
    normalized = normalized.replace(":", "/")
    return _normalize_repository_relative_path(normalized).lower()


def _strip_inline_comment(raw_line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for index, character in enumerate(raw_line):
        if character == "\\" and (in_single or in_double):
            escaped = not escaped
            continue
        if character == "'" and not in_double and not escaped:
            in_single = not in_single
        elif character == '"' and not in_single and not escaped:
            in_double = not in_double
        elif character == "%" and not in_single and not in_double:
            return raw_line[:index]
        escaped = False
    return raw_line


def _strip_comments_uncached(text: str) -> str:
    without_block_comments = re.sub(
        r"/\*.*?\*/",
        lambda match: _replace_with_spaces(match.group(0)),
        text,
        flags=re.DOTALL,
    )
    return "\n".join(
        _strip_inline_comment(line) for line in without_block_comments.splitlines()
    )


@lru_cache(maxsize=256)
def strip_comments(text: str) -> str:
    return _strip_comments_uncached(text)


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


@lru_cache(maxsize=256)
def _split_clauses_from_stripped_text(stripped_text: str) -> tuple[tuple[int, str], ...]:
    clauses: list[tuple[int, str]] = []
    buffer: list[str] = []
    line_no = 1
    clause_start_line = 1
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0
    in_single = False
    in_double = False
    escaped = False
    for index, character in enumerate(stripped_text):
        buffer.append(character)
        if character == "\n":
            line_no += 1
        if in_single or in_double:
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if in_single and character == "'":
                in_single = False
            elif in_double and character == '"':
                in_double = False
            continue
        if character == "'":
            in_single = True
            continue
        if character == '"':
            in_double = True
            continue
        if character == "(":
            paren_depth += 1
            continue
        if character == ")":
            paren_depth = max(0, paren_depth - 1)
            continue
        if character == "[":
            bracket_depth += 1
            continue
        if character == "]":
            bracket_depth = max(0, bracket_depth - 1)
            continue
        if character == "{":
            brace_depth += 1
            continue
        if character == "}":
            brace_depth = max(0, brace_depth - 1)
            continue
        if character != "." or paren_depth or bracket_depth or brace_depth:
            continue
        previous_character = stripped_text[index - 1] if index > 0 else ""
        next_character = stripped_text[index + 1] if index + 1 < len(stripped_text) else ""
        if previous_character.isdigit() and next_character.isdigit():
            continue
        clause_text = "".join(buffer).strip()
        buffer = []
        if clause_text.endswith("."):
            clause_text = clause_text[:-1].strip()
        if clause_text:
            clauses.append((clause_start_line, clause_text))
        clause_start_line = line_no
    return tuple(clauses)


def _split_clauses(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[int, str], ...]:
    return _split_clauses_from_stripped_text(
        stripped_text if stripped_text is not None else strip_comments(text)
    )


def _module_name_from_text(text: str, *, stripped_text: str | None = None) -> str:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    for _line_no, clause in _split_clauses(text, stripped_text=stripped_text):
        module_match = _MODULE_DIRECTIVE_RE.match(clause)
        if module_match is None:
            continue
        return normalize_identifier(str(module_match.group("name") or ""))
    return ""


def _parse_clause_head(clause: str) -> tuple[str, str, str]:
    normalized_clause = clause.strip()
    if not normalized_clause or normalized_clause.startswith(":-"):
        return "", "", ""
    separator = ":-"
    if "-->" in normalized_clause and ":-" not in normalized_clause:
        separator = "-->"
    head_text = normalized_clause.split(separator, 1)[0].strip()
    match = _HEAD_RE.match(head_text)
    if match is None:
        return "", "", ""
    module_name = normalize_identifier(str(match.group("module") or ""))
    symbol_name = normalize_identifier(str(match.group("name") or ""))
    if not symbol_name or symbol_name in RESERVED_SYMBOL_NAMES:
        return "", "", ""
    return module_name, symbol_name, head_text


def has_prolog_markers(text: str) -> bool:
    if _PERL_MARKER_RE.search(text):
        return False
    stripped_text = strip_comments(text)
    if re.search(r"^\s*\?-\s*[a-z]", stripped_text, flags=re.MULTILINE):
        return True
    for _line_no, clause in _split_clauses(text, stripped_text=stripped_text):
        normalized_clause = clause.strip()
        if not normalized_clause:
            continue
        if normalized_clause.startswith(":-"):
            directive_head = normalized_clause[2:].split("(", 1)[0].strip()
            if not directive_head:
                continue
            directive_name = normalize_identifier(directive_head.split(None, 1)[0])
            if directive_name in _PROLOG_DIRECTIVE_PREFIXES:
                return True
        _module_name, symbol_name, _signature = _parse_clause_head(normalized_clause)
        if symbol_name:
            return True
    return False


def is_probable_prolog_source(*, path: PurePosixPath | Path | str, text: str) -> bool:
    suffix = PurePosixPath(str(path).replace("\\", "/")).suffix.lower()
    if suffix not in _KNOWN_PROLOG_SUFFIXES:
        return False
    if suffix == ".prolog":
        return True
    return has_prolog_markers(text)


def _path_aliases(path: PurePosixPath) -> set[str]:
    without_suffix = str(path.with_suffix("")).lower()
    aliases = {
        str(path).lower(),
        without_suffix,
        without_suffix.replace("/", "."),
        path.stem.lower(),
    }
    source_parts = list(path.parts)
    for source_root in _PROLOG_SOURCE_ROOTS:
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        derived_parts = list(source_parts[root_index + 1 :])
        if not derived_parts:
            continue
        derived_parts[-1] = PurePosixPath(derived_parts[-1]).stem
        dot_alias = ".".join(part for part in derived_parts if part).lower()
        if dot_alias:
            aliases.add(dot_alias)
            aliases.add(dot_alias.rsplit(".", 1)[-1])
        break
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def _candidate_import_keys(import_target: str, *, current_file: str) -> tuple[str, ...]:
    normalized_target = _normalize_target_name(import_target)
    if not normalized_target:
        return ()
    current_parent = PurePosixPath(current_file).parent
    raw_candidates = [normalized_target]
    if not PurePosixPath(normalized_target).suffix:
        raw_candidates.extend(
            f"{normalized_target}{suffix}" for suffix in _KNOWN_PROLOG_SUFFIXES
        )
    candidate_keys: list[str] = []
    seen_keys: set[str] = set()
    for raw_candidate in raw_candidates:
        for candidate in (
            raw_candidate,
            _normalize_repository_relative_path(str(current_parent / raw_candidate)),
            f"src/{raw_candidate}",
            f"lib/{raw_candidate}",
            f"prolog/{raw_candidate}",
            f"app/{raw_candidate}",
        ):
            normalized_candidate = candidate.lower()
            if not normalized_candidate or normalized_candidate in seen_keys:
                continue
            seen_keys.add(normalized_candidate)
            candidate_keys.append(normalized_candidate)
    return tuple(candidate_keys)


def _candidate_reference_names(reference_target: str) -> tuple[str, ...]:
    normalized_target = normalize_identifier(reference_target)
    if not normalized_target:
        return ()
    candidate_names: list[str] = []
    seen_names: set[str] = set()
    for candidate_name in (
        normalized_target,
        normalized_target.replace(":", "."),
        normalized_target.replace(".", ":"),
    ):
        cleaned_name = candidate_name.strip()
        if not cleaned_name or cleaned_name in seen_names:
            continue
        seen_names.add(cleaned_name)
        candidate_names.append(cleaned_name)
        leaf_name = cleaned_name.rsplit(".", 1)[-1].rsplit(":", 1)[-1]
        if leaf_name and leaf_name not in seen_names:
            seen_names.add(leaf_name)
            candidate_names.append(leaf_name)
    return tuple(candidate_names)


def _predicate_names_from_import_list(raw_list: str) -> tuple[str, ...]:
    imported_names: list[str] = []
    seen_names: set[str] = set()
    for match in _IMPORT_NAME_RE.finditer(raw_list):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name or symbol_name in RESERVED_SYMBOL_NAMES or symbol_name in seen_names:
            continue
        seen_names.add(symbol_name)
        imported_names.append(symbol_name)
    return tuple(imported_names)


def _split_use_module_target_and_imports(raw_target: str) -> tuple[str, tuple[str, ...]]:
    normalized_target = raw_target.strip()
    if not normalized_target:
        return "", ()
    paren_depth = 0
    bracket_depth = 0
    in_single = False
    in_double = False
    escaped = False
    for index, character in enumerate(normalized_target):
        if in_single or in_double:
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if in_single and character == "'":
                in_single = False
            elif in_double and character == '"':
                in_double = False
            continue
        if character == "'":
            in_single = True
            continue
        if character == '"':
            in_double = True
            continue
        if character == "(":
            paren_depth += 1
            continue
        if character == ")":
            paren_depth = max(0, paren_depth - 1)
            continue
        if character == "[":
            bracket_depth += 1
            continue
        if character == "]":
            bracket_depth = max(0, bracket_depth - 1)
            continue
        if character == "," and paren_depth == 0 and bracket_depth == 0:
            target = normalized_target[:index].strip()
            imported = normalized_target[index + 1 :].strip()
            if imported.startswith("[") and imported.endswith("]"):
                return target, _predicate_names_from_import_list(imported[1:-1])
            return target, ()
    return normalized_target, ()


def _import_aliases(import_target: str) -> tuple[str, ...]:
    normalized_target = _normalize_target_name(import_target)
    if not normalized_target:
        return ()
    path = PurePosixPath(normalized_target)
    aliases = set(_path_aliases(path))
    stem = normalize_identifier(path.stem)
    if stem:
        aliases.add(stem)
    return tuple(sorted(alias for alias in aliases if alias))
