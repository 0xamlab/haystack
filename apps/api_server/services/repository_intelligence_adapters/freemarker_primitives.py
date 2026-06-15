from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

FREEMARKER_SUFFIXES = frozenset({".ftl", ".ftlh", ".ftlx"})
_COMMON_MODULE_ROOTS = frozenset(
    {
        "components",
        "emails",
        "freemarker",
        "ftl",
        "includes",
        "layouts",
        "macros",
        "mail",
        "partials",
        "templates",
        "views",
        "web-inf",
    }
)
_COMMENT_RE = re.compile(r"<#--.*?-->", re.S)
_DIRECTIVE_RE = re.compile(
    r'(?P<open><|\[)#(?P<kind>include|import|macro|function)\s+(?P<body>.*?)(?P<close>>|\])',
    re.I | re.S,
)
_QUOTED_TARGET_RE = re.compile(r"""['"](?P<target>[^'"]+)['"]""")
_ALIAS_RE = re.compile(r"\bas\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\b")
_MACRO_CALL_RE = re.compile(
    r'(?P<open><|\[)@(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)(?=[\s/>|\]])'
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(
        lambda match: "".join("\n" if character == "\n" else " " for character in match.group(0)),
        text,
    )


def has_freemarker_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in FREEMARKER_SUFFIXES


def is_probable_freemarker_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in FREEMARKER_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return any(marker in stripped_text for marker in ("<#", "${", "<@", "[#", "[@"))


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


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


def _normalize_import_target(value: str) -> str:
    normalized = normalize_identifier(value)
    if normalized.startswith("root://"):
        normalized = normalized[len("root://") :]
    if normalized.startswith("classpath:"):
        normalized = normalized[len("classpath:") :]
    return normalized.lstrip("/")


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    trim_index = 0
    for index, part in enumerate(parts):
        if part.lower() in _COMMON_MODULE_ROOTS:
            trim_index = index + 1
    trimmed_parts = parts[trim_index:]
    return ".".join(trimmed_parts) if trimmed_parts else without_suffix.name


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, str | None, int]] = []
    seen: set[tuple[str, str, str | None, int]] = set()
    for match in _DIRECTIVE_RE.finditer(stripped_text):
        kind = normalize_identifier(str(match.group("kind") or "")).lower()
        if kind not in {"include", "import"}:
            continue
        body = str(match.group("body") or "")
        target_match = _QUOTED_TARGET_RE.search(body)
        if target_match is None:
            continue
        target = _normalize_import_target(str(target_match.group("target") or ""))
        if not target:
            continue
        alias_match = _ALIAS_RE.search(body)
        alias = (
            normalize_identifier(str(alias_match.group("alias") or "")) if alias_match else None
        ) or None
        line_number = _line_number(stripped_text, match.start())
        item = (kind, target, alias, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _DIRECTIVE_RE.finditer(stripped_text):
        kind = normalize_identifier(str(match.group("kind") or "")).lower()
        if kind not in {"macro", "function"}:
            continue
        body = str(match.group("body") or "")
        name_match = re.match(r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)", body.strip())
        if name_match is None:
            continue
        name = normalize_identifier(str(name_match.group("name") or ""))
        if not name:
            continue
        line_number = _line_number(stripped_text, match.start())
        item = (name, kind, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str | None, str, int]] = []
    seen: set[tuple[str, str | None, str, int]] = set()
    for match in _MACRO_CALL_RE.finditer(stripped_text):
        target = normalize_identifier(str(match.group("target") or ""))
        if not target:
            continue
        owner, _, name = target.partition(".")
        line_number = _line_number(stripped_text, match.start())
        item = ("call", owner or None if name else None, name or owner, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


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


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in FREEMARKER_SUFFIXES:
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
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_freemarker_source(path=path, text=text):
        return set()
    module_name = module_name_from_path(normalized_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.split(".")[-1])
    without_suffix_parts = list(PurePosixPath(normalized_path).with_suffix("").parts)
    for index, part in enumerate(without_suffix_parts[:-1]):
        if part.lower() not in _COMMON_MODULE_ROOTS:
            continue
        trimmed_parts = without_suffix_parts[index + 1 :]
        if trimmed_parts:
            aliases.add(".".join(trimmed_parts))
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
        aliases.add(symbol_name)
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_import_target(import_target)
    if not normalized_target:
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    if current_dir:
        candidate_keys.append(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / normalized_target))
        )
    if "/" not in normalized_target:
        candidate_keys.extend(
            normalize_repository_relative_path(f"{directory}/{normalized_target}")
            for directory in (
                "templates",
                "views",
                "macros",
                "partials",
                "layouts",
                "ftl",
                "WEB-INF/ftl",
            )
        )
    expanded_candidates: list[str] = []
    for candidate in candidate_keys:
        if not candidate:
            continue
        expanded_candidates.append(candidate)
        if PurePosixPath(candidate).suffix.lower() not in FREEMARKER_SUFFIXES:
            expanded_candidates.extend(
                f"{candidate}{suffix}" for suffix in sorted(FREEMARKER_SUFFIXES)
            )
    seen_candidates: set[str] = set()
    for candidate in expanded_candidates:
        normalized_candidate = normalize_repository_relative_path(candidate)
        if not normalized_candidate or normalized_candidate in seen_candidates:
            continue
        seen_candidates.add(normalized_candidate)
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
        if normalized_candidate in module_index.values():
            return normalized_candidate
    suffixes = tuple(
        f"/{PurePosixPath(candidate).name}"
        for candidate in seen_candidates
        if PurePosixPath(candidate).suffix.lower() in FREEMARKER_SUFFIXES
    )
    if suffixes:
        return resolve_suffix_match(module_index=module_index, suffixes=suffixes)
    return None


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    line_count = max(1, len(text.splitlines()) or 1)
    module_name = module_name_from_path(file_path) or PurePosixPath(file_path).stem or "template"
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "freemarker"},
        ),
        symbol_name=module_name,
        symbol_kind="freemarker",
        start_line=1,
        end_line=line_count,
        parent_symbol_id=None,
        signature=f"freemarker {module_name}",
    )
    symbols = [module_symbol]
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
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
