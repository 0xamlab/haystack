from __future__ import annotations

import re
from functools import lru_cache
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

TWIG_SUFFIXES = frozenset({".twig"})
_COMMON_MODULE_ROOTS = frozenset(
    {
        "_components",
        "_includes",
        "_layouts",
        "blocks",
        "components",
        "includes",
        "layouts",
        "macros",
        "pages",
        "partials",
        "snippets",
        "template",
        "templates",
        "themes",
        "views",
    }
)

_line_count = repository_jinja_primitives._line_count
_line_number = repository_jinja_primitives._line_number
_ordered_names = repository_jinja_primitives._ordered_names
_looks_binaryish = repository_jinja_primitives._looks_binaryish
_MACRO_RE = repository_jinja_primitives._MACRO_RE
_normalize_repository_relative_path = repository_jinja_primitives._normalize_repository_relative_path
_normalize_import_target = repository_jinja_primitives._normalize_import_target
_quoted_targets = repository_jinja_primitives._quoted_targets
_selector_aliases = repository_jinja_primitives._selector_aliases
iter_symbol_entries = repository_jinja_primitives.iter_symbol_entries
normalize_identifier = repository_jinja_primitives.normalize_identifier
source_symbol_name_for_line = repository_jinja_primitives.source_symbol_name_for_line
strip_comments = repository_jinja_primitives.strip_comments

_STATEMENT_RE = re.compile(r"\{%-?\s*(?P<body>.*?)\s*-?%\}", re.S)
_EXPRESSION_RE = re.compile(
    r"(\{\{(?P<expression>.*?)\}\}|\{%-?\s*(?P<statement>.*?)\s*-?%\})",
    re.S,
)
_QUALIFIED_CALL_RE = re.compile(
    r"(?<![.\w])(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_CALL_RE = re.compile(r"(?<![.\w])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_SKIPPED_REFERENCE_PREFIXES = frozenset(
    {"embed", "extends", "from", "import", "include", "macro", "use"}
)
_RESERVED_CALL_NAMES = repository_jinja_primitives._RESERVED_CALL_NAMES


@lru_cache(maxsize=1024)
def _prepared_twig_source_text(*, path: Path | PurePosixPath, text: str) -> str | None:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in TWIG_SUFFIXES or not text or _looks_binaryish(text):
        return None
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return None
    return stripped_text if any(marker in stripped_text for marker in ("{{", "{%", "{#")) else None


@lru_cache(maxsize=1024)
def _iter_symbol_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _MACRO_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name:
            continue
        item = (symbol_name, "macro", _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


@lru_cache(maxsize=1024)
def _iter_reference_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[str, str | None, str, int], ...]:
    entries: list[tuple[str, str | None, str, int]] = []
    seen: set[tuple[str, str | None, str, int]] = set()
    for match in _EXPRESSION_RE.finditer(stripped_text):
        body = str(match.group("expression") or match.group("statement") or "")
        normalized_body = body.strip()
        if not normalized_body or any(
            normalized_body == prefix or normalized_body.startswith(f"{prefix} ")
            for prefix in _SKIPPED_REFERENCE_PREFIXES
        ):
            continue
        line_number = _line_number(stripped_text, match.start())
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


@lru_cache(maxsize=1024)
def _iter_dependency_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int], ...]:
    entries: list[tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int]] = []
    seen: set[tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int]] = set()
    for match in _STATEMENT_RE.finditer(stripped_text):
        body = str(match.group("body") or "").strip()
        if not body:
            continue
        line_number = _line_number(stripped_text, match.start())
        for kind, target, selectors, alias in _dependency_entries_for_statement(body):
            item = (kind, target, selectors, alias, line_number)
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def has_twig_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in TWIG_SUFFIXES


def is_probable_twig_source(*, path: Path | PurePosixPath, text: str) -> bool:
    return _prepared_twig_source_text(path=path, text=text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def iter_reference_entries(text: str) -> tuple[tuple[str, str | None, str, int], ...]:
    return _iter_reference_entries_from_stripped_text(strip_comments(text))


def iter_dependency_entries(
    text: str,
) -> tuple[tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int], ...]:
    return _iter_dependency_entries_from_stripped_text(strip_comments(text))


def _dependency_entries_for_statement(
    body: str,
) -> tuple[tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...], str | None], ...]:
    lowered_body = body.lower()
    for prefix, kind in (
        ("include ", "includes"),
        ("extends ", "extends"),
        ("embed ", "embeds"),
        ("use ", "uses"),
    ):
        if lowered_body.startswith(prefix):
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
    if normalized_target.startswith("@"):
        normalized_target = normalized_target.lstrip("@")
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    if current_dir:
        candidate_keys.append(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / normalized_target))
        )
    expanded_candidates: list[str] = []
    for candidate in candidate_keys:
        expanded_candidates.append(candidate)
        if PurePosixPath(candidate).suffix.lower() not in TWIG_SUFFIXES:
            expanded_candidates.append(f"{candidate}.twig")
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
    return _imported_symbol_bindings_from_dependency_entries(
        current_file=current_file,
        dependency_entries=_iter_dependency_entries_from_stripped_text(strip_comments(text)),
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )


def _imported_symbol_bindings_from_dependency_entries(
    *,
    current_file: str,
    dependency_entries: tuple[
        tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int],
        ...,
    ],
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for _kind, import_target, selectors, alias, _line_number in dependency_entries:
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


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in TWIG_SUFFIXES:
        return set()
    aliases = {
        file_path,
        path.name,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    if stripped_text is None and text:
        stripped_text = _prepared_twig_source_text(path=path, text=text)
    if text and stripped_text is None:
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(file_path)
    aliases.add(module_name)
    aliases.add(module_name.replace("/", "."))
    for symbol_name, _symbol_kind, _line_number in _iter_symbol_entries_from_stripped_text(
        stripped_text or ""
    ):
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[_Symbol, ...]:
    if stripped_text is None:
        stripped_text = _prepared_twig_source_text(path=PurePosixPath(file_path), text=text)
    if stripped_text is None:
        stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path) or PurePosixPath(file_path).stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "twig"},
        ),
        symbol_name=module_name,
        symbol_kind="twig",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"twig {module_name}",
    )
    symbols: list[_Symbol] = [module_symbol]
    for symbol_name, symbol_kind, line_number in _iter_symbol_entries_from_stripped_text(
        stripped_text
    ):
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
