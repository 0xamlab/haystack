from __future__ import annotations

from bisect import bisect_right
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

MOTOKO_SUFFIXES = frozenset({".mo"})
_COMMON_MODULE_ROOTS = frozenset({"src", "motoko", "backend", "app"})
_LINE_COMMENT_RE = re.compile(r"(?m)//.*$")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_IMPORT_RE = re.compile(
    r'(?mi)^\s*import\s+(?:(?P<alias>[A-Za-z_][A-Za-z0-9_]*)|\{[^}]+\})?\s*"(?P<target>[^"]+)"'
)
_ACTOR_RE = re.compile(r"(?mi)^\s*(?:shared\s+)?actor(?:\s+class)?\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)")
_MODULE_RE = re.compile(r"(?mi)^\s*module\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)")
_CLASS_RE = re.compile(r"(?mi)^\s*class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)")
_TYPE_RE = re.compile(r"(?mi)^\s*type\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)")
_FUNC_RE = re.compile(
    r"(?mi)^\s*(?:public|private|system)?\s*(?:shared(?:\s*\([^)]*\))?\s*)?(?:query\s+|composite\s+)?func\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_LET_RE = re.compile(r"(?mi)^\s*(?:let|var)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*[:=]")
_REFERENCE_RE = re.compile(r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|\.)")
_PROBABLE_SOURCE_RE = re.compile(
    r'(?mi)\b(?:import|actor|module|shared|func|stable|type|let|var)\b|"\.?\.?/|"\w+:'
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "actor",
        "and",
        "async",
        "await",
        "break",
        "case",
        "class",
        "continue",
        "debug",
        "else",
        "false",
        "for",
        "func",
        "if",
        "import",
        "in",
        "let",
        "loop",
        "module",
        "null",
        "object",
        "or",
        "private",
        "public",
        "query",
        "return",
        "shared",
        "stable",
        "switch",
        "system",
        "true",
        "type",
        "var",
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


def _line_start_offsets(text: str) -> tuple[int, ...]:
    offsets = [0]
    for match in re.finditer(r"\n", text):
        offsets.append(match.end())
    return tuple(offsets)


def _line_number_from_offsets(line_start_offsets: tuple[int, ...], offset: int) -> int:
    return bisect_right(line_start_offsets, max(0, offset))


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_motoko_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in MOTOKO_SUFFIXES


def is_probable_motoko_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    if not has_motoko_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    if not stripped_text.strip():
        return False
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
    if not cleaned:
        return ""
    if cleaned.startswith(("mo:", "canister:")):
        return cleaned
    if "://" in cleaned:
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
    if not cleaned_target or cleaned_target.startswith(("mo:", "canister:")):
        return None
    candidate_path = PurePosixPath(cleaned_target)
    current_dir = PurePosixPath(current_file).parent
    normalized_candidate = normalize_repository_relative_path(
        candidate_path if candidate_path.is_absolute() else current_dir / candidate_path
    )
    if not normalized_candidate:
        return None
    direct_match = module_index.get(normalized_candidate)
    if direct_match is not None:
        return direct_match
    suffixes = (
        (normalized_candidate,)
        if PurePosixPath(normalized_candidate).suffix.lower() in MOTOKO_SUFFIXES
        else tuple(f"{normalized_candidate}{suffix}" for suffix in sorted(MOTOKO_SUFFIXES))
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def iter_dependency_entries(
    text: str,
    *,
    stripped_text: str | None = None,
    line_start_offsets: tuple[int, ...] | None = None,
) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    line_start_offsets = (
        _line_start_offsets(stripped_text)
        if line_start_offsets is None
        else line_start_offsets
    )
    entries: list[tuple[str, str, str | None, int]] = []
    seen_entries: set[tuple[str, str, str | None, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        import_target = clean_import_target(match.group("target") or "")
        if not import_target:
            continue
        alias = normalize_identifier(match.group("alias") or "") or None
        entry = (
            "imports",
            import_target,
            alias,
            _line_number_from_offsets(line_start_offsets, match.start("target")),
        )
        if entry in seen_entries:
            continue
        seen_entries.add(entry)
        entries.append(entry)
    return tuple(entries)


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
    line_start_offsets: tuple[int, ...] | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    line_start_offsets = (
        _line_start_offsets(stripped_text)
        if line_start_offsets is None
        else line_start_offsets
    )
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for pattern, kind in (
        (_ACTOR_RE, "actor"),
        (_MODULE_RE, "module"),
        (_CLASS_RE, "class"),
        (_TYPE_RE, "type"),
        (_FUNC_RE, "func"),
        (_LET_RE, "binding"),
    ):
        for match in pattern.finditer(stripped_text):
            name = normalize_identifier(match.group("name") or "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            entries.append(
                (
                    name,
                    kind,
                    _line_number_from_offsets(line_start_offsets, match.start("name")),
                )
            )
    return tuple(entries)


def iter_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        for match in _REFERENCE_RE.finditer(raw_line):
            name = normalize_identifier(match.group("name") or "")
            if not name or name in _RESERVED_REFERENCE_NAMES:
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
    if normalized_path.suffix.lower() not in MOTOKO_SUFFIXES:
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
    symbol_entries: tuple[tuple[str, str, int], ...] | None = None,
) -> tuple[_Symbol, ...]:
    module_name = module_name_from_path(file_path)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "motoko"},
            ),
            symbol_name=module_name,
            symbol_kind="motoko",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"motoko {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    if symbol_entries is None:
        symbol_entries = iter_symbol_entries(text)
    for symbol_name, symbol_kind, line_number in symbol_entries:
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "kind": symbol_kind,
                    },
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
    current_name: str | None = None
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line > line_number:
            break
        current_name = symbol_name
    return current_name
