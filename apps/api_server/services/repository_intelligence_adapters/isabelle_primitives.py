from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

ISABELLE_SUFFIXES = frozenset({".thy"})
_COMMON_MODULE_ROOTS = frozenset({"examples", "proof", "src", "tests", "theories"})
_BLOCK_COMMENT_RE = re.compile(r"\(\*.*?\*\)", re.DOTALL)
_TOKEN_RE = re.compile(r'"[^"]+"|\S+')
_THEORY_RE = re.compile(r"(?mi)^\s*theory\s+(?P<name>[A-Za-z0-9_'.-]+)")
_SYMBOL_PATTERNS = (
    (re.compile(r"(?mi)^\s*definition\s+(?P<name>[A-Za-z0-9_'.-]+)"), "definition"),
    (re.compile(r"(?mi)^\s*abbreviation\s+(?P<name>[A-Za-z0-9_'.-]+)"), "abbreviation"),
    (re.compile(r"(?mi)^\s*fun\s+(?P<name>[A-Za-z0-9_'.-]+)"), "fun"),
    (re.compile(r"(?mi)^\s*primrec\s+(?P<name>[A-Za-z0-9_'.-]+)"), "primrec"),
    (re.compile(r"(?mi)^\s*datatype\s+(?P<name>[A-Za-z0-9_'.-]+)"), "datatype"),
    (re.compile(r"(?mi)^\s*locale\s+(?P<name>[A-Za-z0-9_'.-]+)"), "locale"),
    (re.compile(r"(?mi)^\s*(?:lemma|theorem|corollary)\s+(?P<name>[A-Za-z0-9_'.-]+)\s*:"), "lemma"),
)
_REFERENCE_RE = re.compile(r"(?P<name>[A-Za-z_][A-Za-z0-9_']*)")
_PROBABLE_SOURCE_RE = re.compile(r"(?mi)^\s*theory\s+\S+.*^\s*imports\b|^\s*theory\s+\S+.*^\s*begin\b", re.DOTALL)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "and",
        "assumes",
        "begin",
        "by",
        "datatype",
        "definition",
        "end",
        "fixes",
        "for",
        "fun",
        "imports",
        "in",
        "lemma",
        "locale",
        "obtains",
        "primrec",
        "shows",
        "theorem",
        "theory",
        "where",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t\f"
    )
    return control_count > max(2, len(sample) // 32)


@lru_cache(maxsize=1024)
def _strip_comments_cached(text: str) -> str:
    return _BLOCK_COMMENT_RE.sub("", text)


def strip_comments(text: str) -> str:
    if "(*" not in text:
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


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return bisect_right(_line_start_offsets(text), offset)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def has_isabelle_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in ISABELLE_SUFFIXES


def is_probable_isabelle_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    if not has_isabelle_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = _coalesced_stripped_text(text, stripped_text=stripped_text)
    if not stripped_text.strip():
        return False
    return _is_probable_isabelle_source_from_stripped_text(stripped_text)


@lru_cache(maxsize=1024)
def _is_probable_isabelle_source_from_stripped_text(stripped_text: str) -> bool:
    return _PROBABLE_SOURCE_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.stem


def clean_import_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if not cleaned or "://" in cleaned:
        return ""
    return cleaned


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
    candidates: list[str] = []
    if "/" in cleaned_target or cleaned_target.startswith("."):
        current_dir = PurePosixPath(current_file).parent
        normalized_candidate = normalize_repository_relative_path(current_dir / cleaned_target)
        if normalized_candidate:
            candidates.append(normalized_candidate)
    else:
        candidates.append(cleaned_target.replace(".", "/"))
        candidates.append(cleaned_target)
        if "." in cleaned_target:
            candidates.append(cleaned_target.split(".")[-1])
    for candidate in candidates:
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match
        suffixes = (
            (candidate,)
            if PurePosixPath(candidate).suffix.lower() in ISABELLE_SUFFIXES
            else tuple(f"{candidate}{suffix}" for suffix in sorted(ISABELLE_SUFFIXES))
        )
        matched = resolve_suffix_match(module_index=module_index, suffixes=suffixes)
        if matched is not None:
            return matched
    return None


def iter_dependency_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = _coalesced_stripped_text(text, stripped_text=stripped_text)
    return _iter_dependency_entries_from_stripped_text(stripped_text)


@lru_cache(maxsize=1024)
def _iter_dependency_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[str, str, str | None, int], ...]:
    lines = stripped_text.splitlines()
    entries: list[tuple[str, str, str | None, int]] = []
    seen_entries: set[tuple[str, str, str | None, int]] = set()
    line_index = 0
    while line_index < len(lines):
        raw_line = lines[line_index]
        stripped_line = raw_line.strip()
        if not stripped_line.startswith("imports"):
            line_index += 1
            continue
        payload = stripped_line[len("imports") :].strip()
        start_line = line_index + 1
        line_index += 1
        while line_index < len(lines):
            continuation = lines[line_index].strip()
            if not continuation or continuation.startswith(("begin", "chapter", "section", "subsection")):
                break
            if re.match(r"^[A-Za-z_][A-Za-z0-9_'.-]*\b", continuation) or continuation.startswith('"'):
                payload = f"{payload} {continuation}".strip()
                line_index += 1
                continue
            break
        for token in _TOKEN_RE.findall(payload):
            import_target = clean_import_target(token)
            if not import_target:
                continue
            alias = import_target.split("/")[-1].split(".")[-1]
            entry = ("imports", import_target, alias, start_line)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append(entry)
        line_index += 1
    return tuple(entries)


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = _coalesced_stripped_text(text, stripped_text=stripped_text)
    return _iter_symbol_entries_from_stripped_text(stripped_text)


@lru_cache(maxsize=1024)
def _iter_symbol_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    theory_match = _THEORY_RE.search(stripped_text)
    if theory_match is not None:
        theory_name = normalize_identifier(theory_match.group("name") or "")
        if theory_name:
            seen_names.add(theory_name)
            entries.append((theory_name, "theory", _line_number(stripped_text, theory_match.start())))
    for pattern, kind in _SYMBOL_PATTERNS:
        for match in pattern.finditer(stripped_text):
            name = normalize_identifier(match.group("name") or "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            entries.append((name, kind, _line_number(stripped_text, match.start())))
    return tuple(entries)


def iter_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coalesced_stripped_text(text, stripped_text=stripped_text)
    return _iter_reference_entries_from_stripped_text(stripped_text)


@lru_cache(maxsize=1024)
def _iter_reference_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[str, int], ...]:
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        trimmed = raw_line.strip()
        if not trimmed or trimmed.startswith(("theory", "imports")):
            continue
        for match in _REFERENCE_RE.finditer(raw_line):
            name = normalize_identifier(match.group("name") or "")
            if not name or name.lower() in _RESERVED_REFERENCE_NAMES:
                continue
            entry = (name, line_number)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append(entry)
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in ISABELLE_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    try:
        text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for symbol_name, _kind, _line in iter_symbol_entries(text):
        aliases.add(symbol_name)
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[_Symbol, ...]:
    module_name = module_name_from_path(file_path)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "isabelle"},
            ),
            symbol_name=module_name,
            symbol_kind="isabelle",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"isabelle {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(
        text,
        stripped_text=stripped_text,
    ):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": symbol_name, "kind": symbol_kind},
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"{symbol_kind} {symbol_name}".strip(),
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    if not symbol_entries:
        return None
    start_lines = tuple(start_line for _symbol_name, _symbol_kind, start_line in symbol_entries)
    index = bisect_right(start_lines, line_number) - 1
    if index < 0:
        return None
    return symbol_entries[index][0]
