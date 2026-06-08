from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

ANTLR_SUFFIXES = frozenset({".g4"})
ANTLR_INDEX_BASENAMES = frozenset({"grammar.g4", "index.g4", "lexer.g4", "parser.g4"})
_COMMON_MODULE_ROOTS = frozenset(
    {"antlr", "antlr4", "grammar", "grammars", "lexer", "lexers", "parser", "parsers", "syntax"}
)
_GRAMMAR_DECLARATION_RE = re.compile(
    r"(?m)^\s*(?:(lexer|parser)\s+)?grammar\s+([A-Za-z_][A-Za-z0-9_]*)\s*;"
)
_IMPORT_RE = re.compile(r"(?m)^\s*import\s+([^;]+);")
_TOKEN_VOCAB_RE = re.compile(r"\btokenVocab\s*=\s*([A-Za-z_][A-Za-z0-9_]*)")
_RULE_RE = re.compile(r"(?m)^\s*(fragment\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*:")
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"(?m)//.*$")
_ANTLR_KEYWORDS = frozenset(
    {
        "catch",
        "channel",
        "channels",
        "else",
        "finally",
        "fragment",
        "grammar",
        "import",
        "lexer",
        "locals",
        "mode",
        "options",
        "parser",
        "returns",
        "skip",
        "throws",
        "tokens",
    }
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


def has_antlr_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in ANTLR_SUFFIXES


def normalize_identifier(value: str) -> str:
    return str(value or "").strip()


def grammar_name_from_text(text: str) -> str | None:
    match = _GRAMMAR_DECLARATION_RE.search(strip_comments(text))
    if match is None:
        return None
    return normalize_identifier(match.group(2))


def is_probable_antlr_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).suffix.lower() not in ANTLR_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if _GRAMMAR_DECLARATION_RE.search(stripped_text):
        return True
    return len(tuple(_RULE_RE.finditer(stripped_text))) >= 2


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_identifier(value)
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


def iter_rule_entries(text: str) -> tuple[tuple[str, str, int, int, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int, int, int]] = []
    for match in _RULE_RE.finditer(stripped_text):
        name = normalize_identifier(match.group(2))
        if not name:
            continue
        rule_kind = "fragment_rule" if match.group(1) else (
            "lexer_rule" if name[:1].isupper() else "parser_rule"
        )
        line_number = stripped_text[: match.start()].count("\n") + 1
        entries.append((name, rule_kind, line_number, match.start(), match.end()))
    return tuple(entries)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    for match in _IMPORT_RE.finditer(stripped_text):
        line_number = stripped_text[: match.start()].count("\n") + 1
        for import_target in match.group(1).split(","):
            normalized = normalize_identifier(import_target)
            if normalized:
                entries.append(("import", normalized, line_number))
    for match in _TOKEN_VOCAB_RE.finditer(stripped_text):
        line_number = stripped_text[: match.start()].count("\n") + 1
        entries.append(("token_vocab", normalize_identifier(match.group(1)), line_number))
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    rule_entries = iter_rule_entries(stripped_text)
    known_rule_names = {name for name, _kind, _line, _start, _body_start in rule_entries}
    references: list[tuple[str, str, int]] = []
    seen_references: set[tuple[str, str, int]] = set()
    for index, (source_name, _kind, _line_number, _start, body_start) in enumerate(rule_entries):
        body_end = rule_entries[index + 1][3] if index + 1 < len(rule_entries) else len(stripped_text)
        body_text = stripped_text[body_start:body_end]
        base_offset = body_start
        for match in _IDENTIFIER_RE.finditer(body_text):
            target_name = normalize_identifier(match.group(0))
            if (
                not target_name
                or target_name == source_name
                or target_name not in known_rule_names
                or target_name.lower() in _ANTLR_KEYWORDS
            ):
                continue
            line_number = stripped_text[: base_offset + match.start()].count("\n") + 1
            reference_entry = (source_name, target_name, line_number)
            if reference_entry in seen_references:
                continue
            seen_references.add(reference_entry)
            references.append(reference_entry)
    return tuple(references)


def source_symbol_name_for_line(
    rule_entries: Iterable[tuple[str, str, int, int, int]],
    *,
    line_number: int,
) -> str | None:
    entries = tuple(rule_entries)
    for index, (name, _kind, start_line, _start, _body_start) in enumerate(entries):
        end_line = entries[index + 1][2] - 1 if index + 1 < len(entries) else line_number
        if start_line <= line_number <= max(start_line, end_line):
            return name
    return None


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_file_path = _normalize_repository_relative_path(file_path)
    if not normalized_file_path:
        return set()
    aliases = {
        normalized_file_path,
        PurePosixPath(normalized_file_path).stem,
        module_name_from_path(normalized_file_path),
    }
    resolved_path = root_path / normalized_file_path
    try:
        if resolved_path.is_file():
            text = resolved_path.read_text(encoding="utf-8", errors="replace")
            grammar_name = grammar_name_from_text(text)
            if grammar_name:
                aliases.add(grammar_name)
    except OSError:
        pass
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(import_target)
    if not normalized_target:
        return None
    current_parent = PurePosixPath(current_file).parent
    local_candidate = normalize_repository_relative_path(str(current_parent / f"{normalized_target}.g4"))
    if local_candidate and local_candidate in module_index.values():
        return local_candidate
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=(
            normalized_target,
            f"{normalized_target}.g4",
            local_candidate,
        ),
    )


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    stripped_text = strip_comments(text)
    grammar_name = grammar_name_from_text(stripped_text) or module_name_from_path(file_path)
    line_count = _line_count(text)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "symbol",
            {"file_path": file_path, "symbol_name": grammar_name, "kind": "antlr"},
        ),
        symbol_name=grammar_name,
        symbol_kind="antlr",
        start_line=1,
        end_line=line_count,
        parent_symbol_id=None,
        signature="antlr grammar",
    )
    entries = iter_rule_entries(stripped_text)
    child_symbols: list[_Symbol] = []
    for index, (name, rule_kind, start_line, _start, _body_start) in enumerate(entries):
        end_line = entries[index + 1][2] - 1 if index + 1 < len(entries) else line_count
        child_symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": name, "kind": rule_kind},
                ),
                symbol_name=name,
                symbol_kind=rule_kind,
                start_line=start_line,
                end_line=max(start_line, end_line),
                parent_symbol_id=module_symbol.symbol_id,
                signature=rule_kind,
            )
        )
    return (module_symbol, *child_symbols)


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

