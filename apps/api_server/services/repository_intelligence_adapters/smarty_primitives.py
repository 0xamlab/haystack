from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    jinja_primitives as repository_jinja_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _ImportedSymbolBinding,
    _Symbol,
)

StableIdentifier = repository_jinja_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_jinja_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_jinja_primitives.ResolveSuffixMatch

SMARTY_SUFFIXES = frozenset({".tpl"})
_COMMON_MODULE_ROOTS = frozenset(
    {
        "_partials",
        "components",
        "includes",
        "layouts",
        "modules",
        "pages",
        "partials",
        "templates",
        "themes",
        "views",
    }
)
_RESOLVER_DIRS = (
    "templates",
    "templates/layouts",
    "templates/partials",
    "templates/_partials",
    "views",
    "views/layouts",
    "views/partials",
    "layouts",
    "partials",
    "_partials",
    "modules",
)
_COMMENT_RE = re.compile(r"\{\*.*?\*\}", re.S)
_DEPENDENCY_RE = re.compile(
    r"\{(?P<directive>extends|include)\b(?P<body>.*?)\}",
    re.S,
)
_FILE_TARGET_RE = re.compile(r"""(?:(?:^|\s)file\s*=\s*)['"](?P<target>[^'"]+)['"]""")
_FALLBACK_TARGET_RE = re.compile(r"""['"](?P<target>[^'"]+)['"]""")
_BLOCK_RE = re.compile(r"""\{block\b[^}]*\bname\s*=\s*['"](?P<name>[^'"]+)['"]""")
_FUNCTION_RE = re.compile(
    r"""\{function\b[^}]*\bname\s*=\s*['"]?(?P<name>[A-Za-z_][A-Za-z0-9_]*)['"]?"""
)
_CALL_NAME_RE = re.compile(
    r"""\{call\b[^}]*\bname\s*=\s*['"]?(?P<name>[A-Za-z_][A-Za-z0-9_]*)['"]?"""
)
_TAG_CALL_RE = re.compile(r"\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_LIKELY_SMARTY_MARKERS = (
    "{$",
    "{assign",
    "{block",
    "{call",
    "{capture",
    "{extends",
    "{foreach",
    "{function",
    "{if",
    "{include",
)
_RESERVED_TAG_NAMES = frozenset(
    {
        "assign",
        "block",
        "break",
        "call",
        "capture",
        "continue",
        "else",
        "elseif",
        "extends",
        "for",
        "foreach",
        "foreachelse",
        "function",
        "if",
        "include",
        "insert",
        "ldelim",
        "literal",
        "nocache",
        "php",
        "rdelim",
        "section",
        "setfilter",
        "strip",
        "while",
    }
)

_line_count = repository_jinja_primitives._line_count
_line_number = repository_jinja_primitives._line_number
_looks_binaryish = repository_jinja_primitives._looks_binaryish
_ordered_names = repository_jinja_primitives._ordered_names


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(
        lambda match: "".join("\n" if character == "\n" else " " for character in match.group(0)),
        text,
    )


def has_smarty_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in SMARTY_SUFFIXES


def is_probable_smarty_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in SMARTY_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return any(marker in stripped_text for marker in _LIKELY_SMARTY_MARKERS)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def _normalize_smarty_target(value: str) -> str:
    target = normalize_identifier(value)
    if not target or "$" in target or "`" in target:
        return ""
    if target.startswith("module:"):
        return f"modules/{target.removeprefix('module:')}"
    if target.startswith("@"):
        return target.lstrip("@")
    return target


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def iter_dependency_entries(
    text: str,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _DEPENDENCY_RE.finditer(stripped_text):
        dependency_kind = "extends" if match.group("directive") == "extends" else "includes"
        body = str(match.group("body") or "")
        target_match = _FILE_TARGET_RE.search(body) or _FALLBACK_TARGET_RE.search(body)
        if target_match is None:
            continue
        import_target = _normalize_smarty_target(str(target_match.group("target") or ""))
        if not import_target:
            continue
        line_number = _line_number(stripped_text, match.start())
        item = (dependency_kind, import_target, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for pattern, symbol_kind in ((_BLOCK_RE, "block"), (_FUNCTION_RE, "function")):
        for match in pattern.finditer(stripped_text):
            symbol_name = normalize_identifier(str(match.group("name") or ""))
            if not symbol_name:
                continue
            item = (symbol_name, symbol_kind, _line_number(stripped_text, match.start()))
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str | None, str, int]] = []
    seen: set[tuple[str, str | None, str, int]] = set()
    for match in _CALL_NAME_RE.finditer(stripped_text):
        target_name = normalize_identifier(str(match.group("name") or ""))
        if not target_name:
            continue
        item = ("call", None, target_name, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    for match in _TAG_CALL_RE.finditer(stripped_text):
        target_name = normalize_identifier(str(match.group("name") or ""))
        if not target_name or target_name in _RESERVED_TAG_NAMES:
            continue
        item = ("call", None, target_name, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    current_line = -1
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line <= line_number and symbol_line >= current_line:
            current_name = symbol_name
            current_line = symbol_line
    return current_name


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_smarty_target(import_target)
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
            normalize_repository_relative_path(str(PurePosixPath(prefix) / normalized_target))
            for prefix in _RESOLVER_DIRS
        )
    expanded_candidates: list[str] = []
    for candidate in candidate_keys:
        if not candidate:
            continue
        expanded_candidates.append(candidate)
        if PurePosixPath(candidate).suffix.lower() not in SMARTY_SUFFIXES:
            expanded_candidates.append(f"{candidate}.tpl")
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
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for _dependency_kind, import_target, _line_number_value in iter_dependency_entries(text):
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
            PurePosixPath(target_file).stem,
            PurePosixPath(target_file).name,
            str(PurePosixPath(target_file).with_suffix("")),
            module_name,
            module_name.split(".")[-1] if module_name else "",
        )
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


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in SMARTY_SUFFIXES:
        return set()
    aliases = {
        file_path,
        path.name,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_smarty_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(file_path)
    aliases.add(module_name)
    aliases.add(module_name.replace("/", "."))
    for symbol_name, _symbol_kind, _line_number_value in iter_symbol_entries(text):
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path) or PurePosixPath(file_path).stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "smarty"},
        ),
        symbol_name=module_name,
        symbol_kind="smarty",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"smarty {module_name}",
    )
    symbols: list[_Symbol] = [module_symbol]
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
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
