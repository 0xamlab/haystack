from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _ImportedSymbolBinding,
    _Symbol,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

CYTHON_SUFFIXES = frozenset({".pxd", ".pxi", ".pyx"})
_COMMON_MODULE_ROOTS = frozenset(
    {
        "cython",
        "cythonize",
        "include",
        "includes",
        "lib",
        "libs",
        "module",
        "modules",
        "package",
        "packages",
        "python",
        "source",
        "src",
    }
)
_MARKER_RE = re.compile(
    r"(?im)^\s*(?:from\s+\.*[A-Za-z_][A-Za-z0-9_.]*\s+cimport\b|"
    r"cimport\s+\.*[A-Za-z_][A-Za-z0-9_.]*\b|"
    r"include\s+[\"'][^\"'\r\n]+[\"']|"
    r"(?:cpdef|cdef)\s+(?:class|enum|struct|union)\b|"
    r"(?:cpdef|cdef)\s+[A-Za-z_][A-Za-z0-9_<>,\[\]\s\*]*\s+[A-Za-z_][A-Za-z0-9_]*\s*\()|"
    r"^\s*def\s+[A-Za-z_][A-Za-z0-9_]*\s*\("
)
_INCLUDE_RE = re.compile(
    r"""(?im)^\s*include\s+(?P<target>"[^"\r\n]+"|'[^'\r\n]+')"""
)
_FROM_CIMPORT_RE = re.compile(
    r"(?im)^\s*from\s+(?P<module>\.*[A-Za-z_][A-Za-z0-9_.]*)\s+cimport\s+(?P<names>[^\r\n#]+)"
)
_FROM_IMPORT_RE = re.compile(
    r"(?im)^\s*from\s+(?P<module>\.*[A-Za-z_][A-Za-z0-9_.]*)\s+import\s+(?P<names>[^\r\n#]+)"
)
_CIMPORT_RE = re.compile(r"(?im)^\s*cimport\s+(?P<names>[^\r\n#]+)")
_IMPORT_RE = re.compile(r"(?im)^\s*import\s+(?P<names>[^\r\n#]+)")
_CLASS_RE = re.compile(
    r"(?im)^\s*(?:cdef\s+class|class)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_TYPE_RE = re.compile(
    r"(?im)^\s*(?:cdef\s+|ctypedef\s+)?(?:enum|struct|union)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_FUNCTION_RE = re.compile(
    r"(?im)^\s*(?:cpdef|cdef|def)\s+(?:[A-Za-z_][A-Za-z0-9_<>,\[\]\s\*]*?\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_QUALIFIED_CALL_RE = re.compile(
    r"(?<![:.])\b(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_CALL_RE = re.compile(r"(?<![.:])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "cdef",
        "cimport",
        "class",
        "continue",
        "cpdef",
        "ctypedef",
        "def",
        "del",
        "elif",
        "else",
        "enum",
        "except",
        "False",
        "finally",
        "for",
        "from",
        "if",
        "import",
        "in",
        "include",
        "is",
        "lambda",
        "None",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "struct",
        "True",
        "try",
        "union",
        "while",
        "with",
        "yield",
    }
)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    characters: list[str] = []
    index = 0
    in_string = False
    string_delimiter = ""
    triple_quote = False
    while index < len(text):
        character = text[index]
        next_two = text[index : index + 3]
        previous_character = text[index - 1] if index > 0 else "\n"
        if in_string:
            if triple_quote and next_two == string_delimiter * 3:
                characters.extend(string_delimiter * 3)
                index += 3
                in_string = False
                string_delimiter = ""
                triple_quote = False
                continue
            characters.append(character)
            if not triple_quote and character == string_delimiter and previous_character != "\\":
                in_string = False
                string_delimiter = ""
            index += 1
            continue
        if next_two in {'"""', "'''"}:
            in_string = True
            triple_quote = True
            string_delimiter = next_two[0]
            characters.extend(next_two)
            index += 3
            continue
        if character in {'"', "'"}:
            in_string = True
            triple_quote = False
            string_delimiter = character
            characters.append(character)
            index += 1
            continue
        if character == "#":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        characters.append(character)
        index += 1
    return "".join(characters)


def has_cython_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in CYTHON_SUFFIXES


def is_probable_cython_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_cython_path_hints(normalized_path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_MARKER_RE.search(stripped_text))


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


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    if without_suffix.name == "__init__":
        without_suffix = without_suffix.parent
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def _normalize_include_target(raw_target: str) -> str:
    normalized_target = normalize_identifier(raw_target)
    if not normalized_target:
        return ""
    normalized_target = _normalize_repository_relative_path(normalized_target)
    if not normalized_target:
        return ""
    if PurePosixPath(normalized_target).suffix.lower() != ".pxi":
        normalized_target = f"{normalized_target}.pxi"
    return normalized_target


def _parse_import_spec(raw_spec: str) -> tuple[str, str]:
    cleaned_spec = normalize_identifier(raw_spec)
    if not cleaned_spec:
        return "", ""
    if " as " in cleaned_spec:
        base_name, alias_name = re.split(r"(?i)\s+as\s+", cleaned_spec, maxsplit=1)
        base_name = normalize_identifier(base_name)
        alias_name = normalize_identifier(alias_name)
        return base_name, alias_name or PurePosixPath(base_name.replace(".", "/")).name
    return cleaned_spec, PurePosixPath(cleaned_spec.replace(".", "/")).name


def include_statements(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _INCLUDE_RE.finditer(stripped_text):
        target = _normalize_include_target(str(match.group("target") or ""))
        if not target:
            continue
        item = (target, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        statements.append(item)
    return tuple(statements)


def import_statements(
    text: str,
) -> tuple[tuple[str, str, str, str, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, str, str, str, int]] = []
    seen: set[tuple[str, str, str, str, int]] = set()
    for regex, import_kind in (
        (_FROM_CIMPORT_RE, "from_cimport"),
        (_FROM_IMPORT_RE, "from_import"),
    ):
        for match in regex.finditer(stripped_text):
            module_name = normalize_identifier(str(match.group("module") or ""))
            for raw_spec in str(match.group("names") or "").split(","):
                target_name, alias_name = _parse_import_spec(raw_spec)
                if not module_name or not target_name:
                    continue
                item = (
                    import_kind,
                    module_name,
                    target_name,
                    alias_name or target_name,
                    _line_number(stripped_text, match.start()),
                )
                if item not in seen:
                    seen.add(item)
                    statements.append(item)
    for regex, import_kind in ((_CIMPORT_RE, "cimport"), (_IMPORT_RE, "import")):
        for match in regex.finditer(stripped_text):
            for raw_spec in str(match.group("names") or "").split(","):
                target_name, alias_name = _parse_import_spec(raw_spec)
                if not target_name:
                    continue
                item = (
                    import_kind,
                    "",
                    target_name,
                    alias_name or target_name,
                    _line_number(stripped_text, match.start()),
                )
                if item not in seen:
                    seen.add(item)
                    statements.append(item)
    return tuple(statements)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[tuple[str, str]] = set()
    for regex, symbol_kind in (
        (_CLASS_RE, "class"),
        (_TYPE_RE, "type"),
        (_FUNCTION_RE, "function"),
    ):
        for match in regex.finditer(stripped_text):
            symbol_name = normalize_identifier(str(match.group("name") or ""))
            if not symbol_name or (symbol_name, symbol_kind) in seen_names:
                continue
            seen_names.add((symbol_name, symbol_kind))
            entries.append(
                (symbol_name, symbol_kind, _line_number(stripped_text, match.start()))
            )
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    if not is_probable_cython_source(path=Path(file_path), text=text):
        return ()
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path)
    final_line = _line_count(stripped_text)
    symbols: list[tuple[_Symbol, int]] = [
        (
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": module_name,
                        "symbol_kind": "module",
                        "start": 1,
                    },
                ),
                symbol_name=module_name,
                symbol_kind="module",
                start_line=1,
                end_line=final_line,
                parent_symbol_id=None,
                signature=f"module {module_name}",
            ),
            1,
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
        symbols.append(
            (
                _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": symbol_name,
                            "symbol_kind": symbol_kind,
                            "start": start_line,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=start_line,
                    end_line=start_line,
                    parent_symbol_id=symbols[0][0].symbol_id,
                    signature=symbol_name,
                ),
                start_line,
            )
        )
    finalized: list[_Symbol] = []
    for index, (symbol, start_line) in enumerate(symbols):
        next_start = symbols[index + 1][1] if index + 1 < len(symbols) else None
        end_line = final_line if next_start is None else max(start_line, next_start - 1)
        finalized.append(
            _Symbol(
                symbol_id=symbol.symbol_id,
                symbol_name=symbol.symbol_name,
                symbol_kind=symbol.symbol_kind,
                start_line=symbol.start_line,
                end_line=end_line,
                parent_symbol_id=symbol.parent_symbol_id,
                signature=symbol.signature,
            )
        )
    return tuple(finalized)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_cython_path_hints(path):
        return set()
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        module_name,
        path.stem,
    }
    if path.stem == "__init__":
        aliases.add(str(path.parent))
        aliases.add(str(path.parent).replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for symbol in collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        if symbol.symbol_kind == "module":
            continue
        aliases.add(symbol.symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol.symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_include(
    *,
    current_file: str,
    include_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_include_target(include_target)
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    prefixed_targets = [
        normalized_target,
        str(current_dir / normalized_target),
        *(
            str(PurePosixPath(prefix) / normalized_target)
            for prefix in (
                "include",
                "includes",
                "lib",
                "libs",
                "src",
                "source",
                "cython",
            )
        ),
    ]
    candidates = [
        normalize_repository_relative_path(candidate)
        for candidate in prefixed_targets
        if candidate
    ]
    for candidate in tuple(dict.fromkeys(path for path in candidates if path)):
        resolved = module_index.get(candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[path for path in dict.fromkeys(candidates) if path],
    )


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    raw_target = normalize_identifier(import_target)
    if not raw_target:
        return None
    relative_level = len(raw_target) - len(raw_target.lstrip("."))
    normalized_target = raw_target.lstrip(".")
    current_module_parts = [part for part in module_name_from_path(current_file).split(".") if part]
    package_parts = current_module_parts[:-1]
    if relative_level > 0:
        trim = max(0, len(package_parts) - (relative_level - 1))
        package_parts = package_parts[:trim]
    target_parts = [part for part in normalized_target.split(".") if part]
    absolute_parts = package_parts + target_parts if relative_level > 0 else target_parts
    dotted_candidate = ".".join(absolute_parts)
    path_candidate = "/".join(absolute_parts)
    candidate_keys = [key for key in (dotted_candidate, path_candidate) if key]
    for candidate_key in tuple(dict.fromkeys(candidate_keys)):
        normalized_key = normalize_repository_relative_path(candidate_key)
        if not normalized_key:
            continue
        resolved = module_index.get(normalized_key)
        if resolved is not None and resolved != current_file:
            return resolved
    suffixes: list[str] = []
    for candidate_key in candidate_keys:
        normalized_key = normalize_repository_relative_path(candidate_key.replace(".", "/"))
        if not normalized_key:
            continue
        suffixes.extend(
            (
                f"/{normalized_key}.pyx",
                f"/{normalized_key}.pxd",
                f"/{normalized_key}/__init__.pyx",
                f"/{normalized_key}/__init__.pxd",
            )
        )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_kind, module_name, target_name, alias_name, _line_number in import_statements(text):
        target_file = resolve_import(
            current_file=current_file,
            import_target=module_name or target_name,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None:
            continue
        normalized_alias = normalize_identifier(alias_name)
        if not normalized_alias:
            continue
        if import_kind in {"from_cimport", "from_import"}:
            target_names = (normalize_identifier(target_name),)
        else:
            module_alias = module_name_from_path(target_file).split(".")[-1] or normalized_alias
            target_names = (module_alias,)
        bindings[normalized_alias] = _ImportedSymbolBinding(
            alias=normalized_alias,
            target_file=target_file,
            target_names=tuple(name for name in target_names if name),
        )
    return bindings
