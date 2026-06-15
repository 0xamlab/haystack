from __future__ import annotations

from bisect import bisect_right
import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

VYPER_SUFFIXES = frozenset({".vy", ".vyi"})
_SOURCE_MARKER_RE = re.compile(
    r"(?mi)^\s*(?:import\s+[A-Za-z_][A-Za-z0-9_.]*\s+as\s+[A-Za-z_][A-Za-z0-9_]*|"
    r"from\s+[.A-Za-z_][A-Za-z0-9_.]*\s+import\s+.+|"
    r"def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(|"
    r"(?:event|flag|interface|struct)\s+[A-Za-z_][A-Za-z0-9_]*\s*:|"
    r"(?:implements|initializes|uses|exports)\s*:)"
)
_IMPORT_RE = re.compile(
    r"(?mi)^\s*import\s+(?P<target>[A-Za-z_][A-Za-z0-9_.]*)\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*$"
)
_FROM_IMPORT_RE = re.compile(
    r"(?mi)^\s*from\s+(?P<module>[.A-Za-z_][A-Za-z0-9_.]*)\s+import\s+(?P<body>[^\n#]+)"
)
_DIRECTIVE_RE = re.compile(
    r"(?mi)^\s*(?P<kind>implements|initializes|uses|exports)\s*:\s*(?P<body>[^\n#]+)"
)
_TYPE_RE = re.compile(
    r"(?mi)^\s*(?P<kind>event|flag|interface|struct)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:"
)
_FUNCTION_RE = re.compile(r"(?mi)^\s*def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<qualifier>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_UNQUALIFIED_CALL_RE = re.compile(r"(?<![.:])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_STRING_RE = re.compile(
    # Exclude the backslash from the negated classes ([^"\\] / [^'\\]) so a
    # backslash is only ever consumed by the `\\.` escape branch. Without that,
    # a backslash matches *either* `\\.` *or* `[^"]`, and that ambiguity makes
    # the engine explore exponentially many partitions on a run of escapes,
    # i.e. catastrophic backtracking (py/redos). The set of well-formed string
    # literals matched is unchanged; only the redundant backtracking path is gone.
    r"(\"\"\".*?\"\"\"|'''.*?'''|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')",
    re.DOTALL,
)
_DECLARATION_LINE_RE = re.compile(
    r"(?mi)^\s*(?:def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(|"
    r"(?:event|flag|interface|struct)\s+[A-Za-z_][A-Za-z0-9_]*\s*:|"
    r"import\s+[A-Za-z_][A-Za-z0-9_.]*\s+as\s+[A-Za-z_][A-Za-z0-9_]*|"
    r"from\s+[.A-Za-z_][A-Za-z0-9_.]*\s+import\s+.+|"
    r"(?:implements|initializes|uses|exports)\s*:)"
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "Bool",
        "Bytes",
        "Bytes32",
        "Decimal",
        "DynArray",
        "HashMap",
        "String",
        "address",
        "assert",
        "block",
        "break",
        "chain",
        "concat",
        "continue",
        "convert",
        "create_from_blueprint",
        "create_minimal_proxy_to",
        "empty",
        "event",
        "exports",
        "flag",
        "for",
        "if",
        "implements",
        "import",
        "initializes",
        "interface",
        "len",
        "log",
        "max",
        "method_id",
        "min",
        "pow_mod256",
        "print",
        "range",
        "raw_call",
        "return",
        "selfdestruct",
        "send",
        "slice",
        "struct",
        "unsafe_add",
        "unsafe_div",
        "unsafe_mul",
        "unsafe_sub",
        "uses",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _mask_strings(text: str) -> str:
    return _STRING_RE.sub(lambda match: " " * len(match.group(0)), text)


def strip_comments(text: str) -> str:
    masked = _mask_strings(text)
    if "#" not in masked:
        return text
    output: list[str] = []
    last_index = 0
    for match in re.finditer(r"#[^\n]*", masked):
        start, end = match.span()
        output.append(text[last_index:start])
        output.append(" " * (end - start))
        last_index = end
    output.append(text[last_index:])
    return "".join(output)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def clean_import_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if not cleaned or "://" in cleaned:
        return ""
    return cleaned


def has_vyper_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in VYPER_SUFFIXES


def is_probable_vyper_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in VYPER_SUFFIXES or not text or _looks_binaryish(text):
        return False
    prepared_text = stripped_text if stripped_text is not None else strip_comments(text)
    if not prepared_text.strip():
        return False
    return _SOURCE_MARKER_RE.search(prepared_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def _line_starts(text: str) -> tuple[int, ...]:
    starts = [0]
    for index, character in enumerate(text):
        if character == "\n":
            starts.append(index + 1)
    return tuple(starts)


def _line_number(line_starts: tuple[int, ...], offset: int) -> int:
    return bisect_right(line_starts, max(0, offset))


def _prepare_source_text(text: str) -> tuple[str, tuple[int, ...]]:
    stripped_text = strip_comments(text)
    return stripped_text, _line_starts(stripped_text)


def _resolve_module_candidate(
    *,
    module_candidate: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_candidate = clean_import_target(module_candidate)
    if not normalized_candidate:
        return None
    for alias in (
        normalized_candidate,
        normalized_candidate.replace("/", "."),
        PurePosixPath(normalized_candidate).name,
    ):
        direct_match = module_index.get(alias)
        if direct_match is not None:
            return direct_match
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(
            f"{normalized_candidate}{suffix}" for suffix in sorted(VYPER_SUFFIXES)
        ),
    )


def resolve_module_import(
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
    leading_dots = len(cleaned_target) - len(cleaned_target.lstrip("."))
    module_body = cleaned_target.lstrip(".")
    if not module_body:
        return None
    direct_match = module_index.get(cleaned_target)
    if direct_match is not None:
        return direct_match
    current_dir = PurePosixPath(current_file).parent
    if leading_dots:
        base_dir = current_dir
        for _ in range(max(0, leading_dots - 1)):
            base_dir = base_dir.parent
        relative_candidate = normalize_repository_relative_path(
            str(base_dir / module_body.replace(".", "/"))
        )
        if relative_candidate is not None:
            resolved = _resolve_module_candidate(
                module_candidate=relative_candidate,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            if resolved is not None:
                return resolved
    absolute_candidate = normalize_repository_relative_path(module_body.replace(".", "/"))
    if absolute_candidate is None:
        return None
    return _resolve_module_candidate(
        module_candidate=absolute_candidate,
        module_index=module_index,
        resolve_suffix_match=resolve_suffix_match,
    )


def resolve_symbol_import(
    *,
    current_file: str,
    module_target: str,
    symbol_name: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, tuple[str, ...]]:
    normalized_symbol = normalize_identifier(symbol_name)
    if not normalized_symbol:
        return None, ()
    module_file = resolve_module_import(
        current_file=current_file,
        import_target=module_target,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    cleaned_module = clean_import_target(module_target)
    leading_dots = len(cleaned_module) - len(cleaned_module.lstrip("."))
    module_body = cleaned_module.lstrip(".")
    symbol_candidates: list[str] = []
    if module_body:
        symbol_candidates.append(f"{module_body}.{normalized_symbol}")
        module_path = module_body.replace(".", "/")
        symbol_candidates.append(f"{module_path}/{normalized_symbol}")
        if leading_dots:
            current_dir = PurePosixPath(current_file).parent
            base_dir = current_dir
            for _ in range(max(0, leading_dots - 1)):
                base_dir = base_dir.parent
            relative_symbol = normalize_repository_relative_path(
                str(base_dir / module_path / normalized_symbol)
            )
            if relative_symbol is not None:
                symbol_candidates.insert(0, relative_symbol)
    symbol_candidates.append(normalized_symbol)
    for candidate in symbol_candidates:
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match, (normalized_symbol,)
        suffix_match = resolve_suffix_match(
            module_index=module_index,
            suffixes=tuple(f"{candidate}{suffix}" for suffix in sorted(VYPER_SUFFIXES)),
        )
        if suffix_match is not None:
            return suffix_match, (normalized_symbol,)
    return module_file, (normalized_symbol,) if module_file is not None else ()


def resolve_dependency_target(
    *,
    current_file: str,
    dependency_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, str]:
    cleaned_target = clean_import_target(dependency_target)
    if not cleaned_target:
        return None, ""
    if "." in cleaned_target.lstrip("."):
        module_target, symbol_name = cleaned_target.rsplit(".", 1)
        resolved_file, target_names = resolve_symbol_import(
            current_file=current_file,
            module_target=module_target,
            symbol_name=symbol_name,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if resolved_file is not None and target_names:
            return resolved_file, target_names[0]
    direct_match = module_index.get(cleaned_target)
    if direct_match is not None:
        return direct_match, cleaned_target.rsplit(".", 1)[-1]
    current_dir = PurePosixPath(current_file).parent
    relative_candidate = normalize_repository_relative_path(str(current_dir / cleaned_target))
    if relative_candidate is not None:
        suffix_match = resolve_suffix_match(
            module_index=module_index,
            suffixes=tuple(
                f"{relative_candidate}{suffix}" for suffix in sorted(VYPER_SUFFIXES)
            ),
        )
        if suffix_match is not None:
            return suffix_match, PurePosixPath(relative_candidate).name
    module_file = resolve_module_import(
        current_file=current_file,
        import_target=cleaned_target,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    return module_file, cleaned_target.rsplit(".", 1)[-1]


def iter_dependency_entries(
    text: str,
    *,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, str, str | None, str | None, int], ...]:
    prepared_text = stripped_text if stripped_text is not None else strip_comments(text)
    prepared_line_starts = line_starts if line_starts is not None else _line_starts(prepared_text)
    entries: list[tuple[str, str, str | None, str | None, int]] = []
    for match in _IMPORT_RE.finditer(prepared_text):
        target = clean_import_target(match.group("target") or "")
        alias = normalize_identifier(match.group("alias") or "") or None
        if not target:
            continue
        entries.append(
            ("import", target, alias, None, _line_number(prepared_line_starts, match.start()))
        )
    for match in _FROM_IMPORT_RE.finditer(prepared_text):
        module_target = clean_import_target(match.group("module") or "")
        if not module_target:
            continue
        for raw_entry in str(match.group("body") or "").split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            source_name = entry
            alias_name = entry
            alias_match = re.match(
                r"^(?P<source>[A-Za-z_][A-Za-z0-9_]*)\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)$",
                entry,
                re.IGNORECASE,
            )
            if alias_match is not None:
                source_name = str(alias_match.group("source") or "")
                alias_name = str(alias_match.group("alias") or "")
            normalized_source = normalize_identifier(source_name)
            normalized_alias = normalize_identifier(alias_name) or normalized_source
            if not normalized_source or not normalized_alias:
                continue
            entries.append(
                (
                    "from_import",
                    module_target,
                    normalized_alias,
                    normalized_source,
                    _line_number(prepared_line_starts, match.start()),
                )
            )
    for match in _DIRECTIVE_RE.finditer(prepared_text):
        directive_kind = normalize_identifier(match.group("kind") or "").lower()
        raw_body = str(match.group("body") or "")
        for raw_entry in raw_body.split(","):
            cleaned = normalize_identifier(raw_entry).split("[", 1)[0].strip()
            if cleaned:
                entries.append(
                    (
                        directive_kind,
                        cleaned,
                        None,
                        None,
                        _line_number(prepared_line_starts, match.start()),
                    )
                )
    return tuple(entries)


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, str, int], ...]:
    prepared_text = stripped_text if stripped_text is not None else strip_comments(text)
    prepared_line_starts = line_starts if line_starts is not None else _line_starts(prepared_text)
    entries: list[tuple[str, str, int]] = []
    seen_entries: set[tuple[str, str, int]] = set()
    for match in _TYPE_RE.finditer(prepared_text):
        name = normalize_identifier(match.group("name") or "")
        kind = normalize_identifier(match.group("kind") or "").lower()
        if not name or not kind:
            continue
        entry = (name, kind, _line_number(prepared_line_starts, match.start()))
        if entry not in seen_entries:
            seen_entries.add(entry)
            entries.append(entry)
    for match in _FUNCTION_RE.finditer(prepared_text):
        name = normalize_identifier(match.group("name") or "")
        if not name:
            continue
        entry = (name, "function", _line_number(prepared_line_starts, match.start()))
        if entry not in seen_entries:
            seen_entries.add(entry)
            entries.append(entry)
    return tuple(sorted(entries, key=lambda item: (item[2], item[1], item[0])))


def iter_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
    symbol_entries: tuple[tuple[str, str, int], ...] | None = None,
) -> tuple[tuple[str | None, str, int], ...]:
    prepared_text = stripped_text if stripped_text is not None else strip_comments(text)
    entries: list[tuple[str | None, str, int]] = []
    seen_entries: set[tuple[str | None, str, int]] = set()
    declaration_lines = {
        line_number
        for _symbol_name, _symbol_kind, line_number in (
            symbol_entries
            if symbol_entries is not None
            else iter_symbol_entries(text, stripped_text=prepared_text)
        )
    }
    for line_number, raw_line in enumerate(prepared_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if (
            not stripped_line
            or line_number in declaration_lines
            or _DECLARATION_LINE_RE.match(stripped_line)
        ):
            continue
        for match in _QUALIFIED_CALL_RE.finditer(stripped_line):
            qualifier = normalize_identifier(match.group("qualifier") or "")
            name = normalize_identifier(match.group("name") or "")
            if not qualifier or not name or name in _RESERVED_REFERENCE_NAMES:
                continue
            entry = (qualifier, name, line_number)
            if entry not in seen_entries:
                seen_entries.add(entry)
                entries.append(entry)
        for match in _UNQUALIFIED_CALL_RE.finditer(stripped_line):
            name = normalize_identifier(match.group("name") or "")
            start = match.start()
            if (
                not name
                or name in _RESERVED_REFERENCE_NAMES
                or (start > 0 and stripped_line[start - 1] == ".")
            ):
                continue
            entry = (None, name, line_number)
            if entry not in seen_entries:
                seen_entries.add(entry)
                entries.append(entry)
    return tuple(entries)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, str, int]],
    *,
    line_number: int,
) -> str | None:
    active_name: str | None = None
    active_line = -1
    for name, _kind, symbol_line in symbol_entries:
        if symbol_line > line_number:
            break
        if symbol_line >= active_line:
            active_name = name
            active_line = symbol_line
    return active_name


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    del stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in VYPER_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    if text is None:
        try:
            text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    if text:
        stripped_text, line_starts = _prepare_source_text(text)
    else:
        stripped_text, line_starts = "", (0,)
    if text and is_probable_vyper_source(path=normalized_path, text=text, stripped_text=stripped_text):
        for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(
            text,
            stripped_text=stripped_text,
            line_starts=line_starts,
        ):
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
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "symbol",
            {"file_path": file_path, "symbol_name": module_name, "kind": "vyper"},
        ),
        symbol_name=module_name,
        symbol_kind="vyper",
        start_line=1,
        end_line=line_count,
        parent_symbol_id=None,
        signature=f"vyper {module_name}".strip(),
    )
    module_symbol_id = module_symbol.symbol_id
    symbols = [module_symbol]
    for symbol_name, symbol_kind, line_number in (
        symbol_entries if symbol_entries is not None else iter_symbol_entries(text)
    ):
        signature = (
            f"def {symbol_name}"
            if symbol_kind == "function"
            else f"{symbol_kind} {symbol_name}"
        )
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
                signature=signature,
            )
        )
    return tuple(symbols)
