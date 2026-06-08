from __future__ import annotations

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

NUNJUCKS_SUFFIXES = frozenset({".njk", ".nunj", ".nunjucks"})
_COMMON_MODULE_ROOTS = frozenset(
    {
        "_components",
        "_includes",
        "_layouts",
        "components",
        "includes",
        "layouts",
        "partials",
        "snippets",
        "template",
        "templates",
        "views",
    }
)

_line_count = repository_jinja_primitives._line_count
_line_number = repository_jinja_primitives._line_number
_ordered_names = repository_jinja_primitives._ordered_names
_looks_binaryish = repository_jinja_primitives._looks_binaryish
_normalize_repository_relative_path = repository_jinja_primitives._normalize_repository_relative_path
_normalize_import_target = repository_jinja_primitives._normalize_import_target
iter_dependency_entries = repository_jinja_primitives.iter_dependency_entries
iter_reference_entries = repository_jinja_primitives.iter_reference_entries
iter_symbol_entries = repository_jinja_primitives.iter_symbol_entries
normalize_identifier = repository_jinja_primitives.normalize_identifier
source_symbol_name_for_line = repository_jinja_primitives.source_symbol_name_for_line
strip_comments = repository_jinja_primitives.strip_comments


def has_nunjucks_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in NUNJUCKS_SUFFIXES


def is_probable_nunjucks_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in NUNJUCKS_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return any(marker in stripped_text for marker in ("{{", "{%", "{#"))


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in NUNJUCKS_SUFFIXES:
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
    if text and not is_probable_nunjucks_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(file_path)
    aliases.add(module_name)
    aliases.add(module_name.replace("/", "."))
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
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
        if PurePosixPath(candidate).suffix.lower() not in NUNJUCKS_SUFFIXES:
            expanded_candidates.extend(
                f"{candidate}{suffix}" for suffix in sorted(NUNJUCKS_SUFFIXES)
            )
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
    for _kind, import_target, selectors, alias, _line_number in iter_dependency_entries(text):
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
) -> tuple[_Symbol, ...]:
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path) or PurePosixPath(file_path).stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "nunjucks"},
        ),
        symbol_name=module_name,
        symbol_kind="nunjucks",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"nunjucks {module_name}",
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
