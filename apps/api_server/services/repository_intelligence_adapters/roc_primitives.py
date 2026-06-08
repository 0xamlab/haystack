from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

ROC_SUFFIXES = frozenset({".roc"})
_SOURCE_ROOTS = ("src", "platform", "examples", "example", "tests", "test", "ci")
_IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<target>[A-Za-z][A-Za-z0-9_.]*)"
    r"(?:\s+exposing\s+\[(?P<imports>[^\]]*)\])?",
    re.MULTILINE,
)
_TYPE_RE = re.compile(r"^(?P<name>[A-Z][A-Za-z0-9_]*)\s*:", re.MULTILINE)
_VALUE_RE = re.compile(r"^(?P<name>[a-z_][A-Za-z0-9_]*!?)\s*:", re.MULTILINE)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Z][A-Za-z0-9_]*)\.(?P<name>[a-z_][A-Za-z0-9_]*!?)(?![A-Za-z0-9_])"
)
_CALL_RE = re.compile(
    r"(?<![./])\b(?P<name>[a-z_][A-Za-z0-9_]*!?)(?![A-Za-z0-9_])(?=\s*(?:\(|\{|[A-Z_]))"
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "app",
        "as",
        "else",
        "expect",
        "if",
        "import",
        "is",
        "module",
        "when",
    }
)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def strip_comments(text: str) -> str:
    characters: list[str] = []
    index = 0
    in_string = False
    while index < len(text):
        character = text[index]
        if in_string:
            characters.append(character)
            if character == '"' and (index == 0 or text[index - 1] != "\\"):
                in_string = False
            index += 1
            continue
        if character == "#":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        characters.append(character)
        if character == '"':
            in_string = True
        index += 1
    return "".join(characters)


def has_roc_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in ROC_SUFFIXES


def is_probable_roc_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if has_roc_path_hints(path):
        stripped_text = strip_comments(text)
        return bool(
            _IMPORT_RE.search(stripped_text)
            or _TYPE_RE.search(stripped_text)
            or _VALUE_RE.search(stripped_text)
            or stripped_text.lstrip().startswith("app ")
        )
    return False


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    for source_root in _SOURCE_ROOTS:
        if source_root not in path.parts:
            continue
        root_index = path.parts.index(source_root)
        module_parts = list(path.parts[root_index:])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem
        return ".".join(part for part in module_parts if part)
    return str(path.with_suffix("")).replace("/", ".").strip(".")


def clean_import_target(raw_target: str) -> str:
    return str(raw_target or "").strip().strip(".")


def parse_exposed_names(raw_value: str) -> tuple[str, ...]:
    names: list[str] = []
    for raw_name in str(raw_value or "").split(","):
        candidate = raw_name.strip()
        if not candidate or candidate in _RESERVED_SYMBOL_NAMES:
            continue
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]*!?$", candidate):
            continue
        names.append(candidate)
    return tuple(dict.fromkeys(names))


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
    current_dir = PurePosixPath(current_file).parent
    dot_path = PurePosixPath(*cleaned_target.split("."))
    candidates = [
        normalize_repository_relative_path(current_dir / dot_path),
        normalize_repository_relative_path(dot_path),
    ]
    final_segment = cleaned_target.split(".")[-1]
    if final_segment:
        candidates.extend(
            [
                normalize_repository_relative_path(current_dir / f"{final_segment}.roc"),
                normalize_repository_relative_path(f"{final_segment}.roc"),
                normalize_repository_relative_path(current_dir / final_segment),
                normalize_repository_relative_path(final_segment),
            ]
        )
    direct_candidates = tuple(
        candidate
        for candidate in dict.fromkeys(candidates)
        if candidate and module_index.get(candidate) is not None
    )
    if direct_candidates:
        return module_index[direct_candidates[0]]
    suffixes = tuple(
        candidate
        for candidate in dict.fromkeys(
            suffix
            for candidate in candidates
            if candidate
            for suffix in (
                candidate,
                candidate if PurePosixPath(candidate).suffix.lower() in ROC_SUFFIXES else f"{candidate}.roc",
                f"/{final_segment}.roc" if final_segment else "",
            )
            if suffix
        )
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes) if suffixes else None


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, tuple[str, ...], int]] = []
    for match in _IMPORT_RE.finditer(stripped_text):
        import_target = clean_import_target(match.group("target") or "")
        if not import_target:
            continue
        line_number = _line_number(stripped_text, match.start())
        entries.append(
            (
                import_target,
                import_target.split(".")[-1],
                parse_exposed_names(match.group("imports") or ""),
                line_number,
            )
        )
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, symbol_kind in ((_TYPE_RE, "type"), (_VALUE_RE, "function")):
        for match in regex.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if (
                not symbol_name
                or symbol_name in seen_names
                or symbol_name in _RESERVED_SYMBOL_NAMES
            ):
                continue
            seen_names.add(symbol_name)
            entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_reference_entries(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str | None, str, int]] = []
    for match in _QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        entries.append(
            (
                str(match.group("alias") or "").strip() or None,
                str(match.group("name") or "").strip(),
                _line_number(stripped_text, match.start()),
            )
        )
    for match in _CALL_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        if not name or name in _RESERVED_SYMBOL_NAMES:
            continue
        entries.append((None, name, _line_number(stripped_text, match.start())))
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del root_path, stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in ROC_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    module_name = module_name_from_path(file_path) or PurePosixPath(file_path).stem
    line_count = _line_count(text)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "roc"},
            ),
            symbol_name=module_name,
            symbol_kind="roc",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"roc {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
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
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, str, int]],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line <= line_number:
            current_name = symbol_name
    return current_name
