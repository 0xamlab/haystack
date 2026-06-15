from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _ImportedSymbolBinding,
    _Symbol,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

JINJA_SUFFIXES = frozenset({".j2", ".jinja", ".jinja2"})
_COMMON_MODULE_ROOTS = frozenset(
    {"jinja", "jinja2", "partials", "roles", "snippets", "template", "templates", "views"}
)
_STATEMENT_RE = re.compile(r"\{%-?\s*(?P<body>.*?)\s*-?%\}", re.S)
_EXPRESSION_RE = re.compile(
    r"(\{\{(?P<expression>.*?)\}\}|\{%-?\s*(?P<statement>.*?)\s*-?%\})",
    re.S,
)
_QUOTED_TARGET_RE = re.compile(r"""['"](?P<target>[^'"]+)['"]""")
_MACRO_RE = re.compile(r"\{%-?\s*macro\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(", re.S)
_QUALIFIED_CALL_RE = re.compile(
    r"(?<![.\w])(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_CALL_RE = re.compile(r"(?<![.\w])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_SKIPPED_REFERENCE_PREFIXES = frozenset({"extends", "from", "import", "include", "macro"})
_RESERVED_CALL_NAMES = frozenset(
    {"caller", "cycler", "dict", "joiner", "lipsum", "loop", "namespace", "range", "super"}
)


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


@lru_cache(maxsize=1024)
def _strip_comments_cached(text: str) -> str:
    characters = list(text)
    index = 0
    while index < len(characters):
        if text.startswith("{#", index):
            comment_end = text.find("#}", index + 2)
            if comment_end < 0:
                comment_end = len(text) - 2
            for replace_index in range(index, min(comment_end + 2, len(characters))):
                if characters[replace_index] != "\n":
                    characters[replace_index] = " "
            index = comment_end + 2
            continue
        index += 1
    return "".join(characters)


def strip_comments(text: str) -> str:
    if "{#" not in text:
        return text
    return _strip_comments_cached(text)


def has_jinja_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in JINJA_SUFFIXES


def is_probable_jinja_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in JINJA_SUFFIXES or not text or _looks_binaryish(text):
        return False
    candidate_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    if not candidate_stripped_text.strip():
        return False
    return any(marker in candidate_stripped_text for marker in ("{{", "{%", "{#"))


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


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def _normalize_import_target(raw_target: str) -> str:
    normalized_target = normalize_identifier(raw_target)
    return _normalize_repository_relative_path(normalized_target) if normalized_target else ""


def iter_dependency_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int], ...]:
    candidate_text = stripped_text if stripped_text is not None else strip_comments(text)
    entries: list[tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int]] = []
    seen: set[tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int]] = set()
    for match in _STATEMENT_RE.finditer(candidate_text):
        body = str(match.group("body") or "").strip()
        if not body:
            continue
        line_number = _line_number(candidate_text, match.start())
        for kind, target, selectors, alias in _dependency_entries_for_statement(body):
            item = (kind, target, selectors, alias, line_number)
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def _dependency_entries_for_statement(
    body: str,
) -> tuple[tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...], str | None], ...]:
    lowered_body = body.lower()
    if lowered_body.startswith("include ") or lowered_body.startswith("extends "):
        kind = "includes" if lowered_body.startswith("include ") else "extends"
        return tuple((kind, target, (), None) for target in _quoted_targets(body))
    if lowered_body.startswith("import "):
        target = next(iter(_quoted_targets(body)), "")
        if not target:
            return ()
        alias_match = re.search(r"\bas\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\b", body)
        alias = normalize_identifier(str(alias_match.group("alias") or "")) if alias_match else None
        return (("imports", target, (), alias or None),)
    if lowered_body.startswith("from "):
        target = next(iter(_quoted_targets(body)), "")
        if not target:
            return ()
        import_match = re.search(r"\bimport\s+(?P<selectors>.+)$", body, re.S)
        selectors = _selector_aliases(import_match.group("selectors") if import_match else "")
        return (("imports", target, selectors, None),) if selectors else ()
    return ()


def _quoted_targets(body: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen: set[str] = set()
    for match in _QUOTED_TARGET_RE.finditer(body):
        target = _normalize_import_target(str(match.group("target") or ""))
        if not target or target in seen:
            continue
        seen.add(target)
        targets.append(target)
    return tuple(targets)


def _selector_aliases(raw_selectors: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    selectors = str(raw_selectors or "").strip()
    if not selectors:
        return ()
    entries: list[tuple[str, tuple[str, ...]]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for raw_selector in selectors.split(","):
        selector = str(raw_selector or "").strip()
        if not selector:
            continue
        base_selector, _, alias_tail = selector.partition(" as ")
        symbol_name = normalize_identifier(base_selector)
        alias_name = normalize_identifier(alias_tail)
        if not symbol_name:
            continue
        item = (symbol_name, _ordered_names(alias_name, symbol_name))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    candidate_text = stripped_text if stripped_text is not None else strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _MACRO_RE.finditer(candidate_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name:
            continue
        item = (symbol_name, "macro", _line_number(candidate_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str | None, str, int], ...]:
    candidate_text = stripped_text if stripped_text is not None else strip_comments(text)
    entries: list[tuple[str, str | None, str, int]] = []
    seen: set[tuple[str, str | None, str, int]] = set()
    for match in _EXPRESSION_RE.finditer(candidate_text):
        body = str(match.group("expression") or match.group("statement") or "")
        normalized_body = body.strip()
        if not normalized_body or any(
            normalized_body == prefix or normalized_body.startswith(f"{prefix} ")
            for prefix in _SKIPPED_REFERENCE_PREFIXES
        ):
            continue
        line_number = _line_number(candidate_text, match.start())
        for pattern, owner_key in ((_QUALIFIED_CALL_RE, "owner"), (_CALL_RE, None)):
            for call_match in pattern.finditer(body):
                owner = (
                    normalize_identifier(str(call_match.group(owner_key) or ""))
                    if owner_key
                    else None
                )
                name = normalize_identifier(str(call_match.group("name") or ""))
                if not name or name in _RESERVED_CALL_NAMES:
                    continue
                item = ("call", owner or None, name, line_number)
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
    active_name: str | None = None
    active_line = -1
    for symbol_name, _symbol_kind, start_line in symbol_entries:
        if start_line <= line_number and start_line >= active_line:
            active_name = symbol_name
            active_line = start_line
    return active_name


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
    symbol_entries: tuple[tuple[str, str, int], ...] | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in JINJA_SUFFIXES:
        return set()
    aliases = {
        file_path,
        path.name,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    loaded_text = text
    if loaded_text is None:
        try:
            loaded_text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            loaded_text = ""
    candidate_stripped_text = stripped_text if stripped_text is not None else strip_comments(loaded_text)
    if loaded_text and not is_probable_jinja_source(
        path=path,
        text=loaded_text,
        stripped_text=candidate_stripped_text,
    ):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(file_path)
    aliases.add(module_name)
    aliases.add(module_name.replace("/", "."))
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    resolved_symbol_entries = symbol_entries
    if resolved_symbol_entries is None:
        resolved_symbol_entries = iter_symbol_entries(
            loaded_text,
            stripped_text=candidate_stripped_text,
        )
    for symbol_name, _symbol_kind, _line_number in resolved_symbol_entries:
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
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
    expanded_candidates: list[str] = []
    for candidate in candidate_keys:
        expanded_candidates.append(candidate)
        if PurePosixPath(candidate).suffix.lower() not in JINJA_SUFFIXES:
            expanded_candidates.extend(f"{candidate}{suffix}" for suffix in sorted(JINJA_SUFFIXES))
    for candidate_key in expanded_candidates:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(f"/{PurePosixPath(candidate).name}" for candidate in expanded_candidates),
    )


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for _kind, import_target, selectors, alias, _line_number in iter_dependency_entries(
        text,
        stripped_text=stripped_text,
    ):
        target_file = resolve_import(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None:
            continue
        module_name = module_name_from_path(target_file)
        module_aliases = _ordered_names(
            alias or "",
            PurePosixPath(target_file).stem,
            PurePosixPath(target_file).name,
            str(PurePosixPath(target_file).with_suffix("")),
            module_name,
            module_name.split(".")[-1] if module_name else "",
        )
        if selectors:
            for symbol_name, alias_names in selectors:
                for alias_name in alias_names:
                    bindings.setdefault(
                        alias_name,
                        _ImportedSymbolBinding(
                            alias=alias_name,
                            target_file=target_file,
                            target_names=(symbol_name,),
                        ),
                    )
            continue
        for alias_name in module_aliases:
            bindings.setdefault(
                alias_name,
                _ImportedSymbolBinding(
                    alias=alias_name,
                    target_file=target_file,
                    target_names=(),
                ),
            )
    return bindings


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
    symbol_entries: tuple[tuple[str, str, int], ...] | None = None,
) -> tuple[_Symbol, ...]:
    candidate_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    module_name = module_name_from_path(file_path) or PurePosixPath(file_path).stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "jinja"},
        ),
        symbol_name=module_name,
        symbol_kind="jinja",
        start_line=1,
        end_line=_line_count(candidate_stripped_text),
        parent_symbol_id=None,
        signature=f"jinja {module_name}",
    )
    symbols: list[_Symbol] = [module_symbol]
    resolved_symbol_entries = symbol_entries
    if resolved_symbol_entries is None:
        resolved_symbol_entries = iter_symbol_entries(
            text,
            stripped_text=candidate_stripped_text,
        )
    for symbol_name, symbol_kind, line_number in resolved_symbol_entries:
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                        "line": line_number,
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
