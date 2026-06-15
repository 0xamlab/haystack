from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    lisp_support as repository_lisp_support,
)

StableIdentifier = repository_lisp_support.StableIdentifier
NormalizeRepositoryRelativePath = repository_lisp_support.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_lisp_support.ResolveSuffixMatch

_KNOWN_SCHEME_SUFFIXES = (".scm", ".ss", ".sld", ".sps")
_SCHEME_MANIFEST_BASENAMES = frozenset({"package.scm"})
_SCHEME_MARKER_RE = re.compile(
    r"(?im)^\s*#!(?:r6rs|r7rs|chezscheme)\b|"
    r"^\s*#lang\s+(?:scheme|r6rs|r7rs|chezscheme)\b|"
    r"\(\s*(?:define-library|library|module|import|export|"
    r"define(?:-syntax(?:-rule)?|-record-type|-values)?|include(?:-ci)?|load)\b"
)
_DEFINITION_LINE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"^\s*\(\s*define-syntax(?:-rule)?\s+"
            r"(?P<name>[A-Za-z*+!<>=/?$%&_.:-][A-Za-z0-9*+!<>=/?$%&_.:-]*)",
            re.IGNORECASE,
        ),
        "function",
    ),
    (
        re.compile(
            r"^\s*\(\s*define-record-type\s+"
            r"(?:\(\s*(?P<name_list>[A-Za-z*+!<>=/?$%&_.:-][A-Za-z0-9*+!<>=/?$%&_.:-]*)"
            r"[^\)]*\)|"
            r"(?P<name>[A-Za-z*+!<>=/?$%&_.:-][A-Za-z0-9*+!<>=/?$%&_.:-]*))",
            re.IGNORECASE,
        ),
        "type",
    ),
    (
        re.compile(
            r"^\s*\(\s*define-values\s+\(\s*"
            r"(?P<name>[A-Za-z*+!<>=/?$%&_.:-][A-Za-z0-9*+!<>=/?$%&_.:-]*)",
            re.IGNORECASE,
        ),
        "variable",
    ),
    (
        re.compile(
            r"^\s*\(\s*define\s+\(\s*"
            r"(?P<name>[A-Za-z*+!<>=/?$%&_.:-][A-Za-z0-9*+!<>=/?$%&_.:-]*)",
            re.IGNORECASE,
        ),
        "function",
    ),
    (
        re.compile(
            r"^\s*\(\s*define\s+"
            r"(?P<name>[A-Za-z*+!<>=/?$%&_.:-][A-Za-z0-9*+!<>=/?$%&_.:-]*)",
            re.IGNORECASE,
        ),
        "variable",
    ),
)
_IMPORT_FORM_HEADS = frozenset({"import"})
_LOAD_FORM_HEADS = frozenset({"include", "include-ci", "load"})
_IMPORT_WRAPPER_HEADS = frozenset(
    {
        "except",
        "for",
        "for-syntax",
        "meta",
        "only",
        "only-meta",
        "prefix",
        "rename",
    }
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<prefix>[A-Za-z][A-Za-z0-9_.-]*)\s*:\s*"
    r"(?P<name>[A-Za-z*+!<>=/?$%&_.-][A-Za-z0-9*+!<>=/?$%&_.-]*)"
)
_UNQUALIFIED_REFERENCE_RE = repository_lisp_support._UNQUALIFIED_REFERENCE_RE
_SCHEME_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "...",
        "and",
        "begin",
        "case",
        "cond",
        "define",
        "define-library",
        "define-record-type",
        "define-syntax",
        "define-syntax-rule",
        "define-values",
        "delay",
        "do",
        "else",
        "export",
        "guard",
        "if",
        "import",
        "include",
        "include-ci",
        "lambda",
        "let",
        "let*",
        "let-values",
        "letrec",
        "letrec*",
        "letrec-syntax",
        "library",
        "load",
        "module",
        "or",
        "quasiquote",
        "quote",
        "set!",
        "syntax-rules",
        "unless",
        "unquote",
        "unquote-splicing",
        "when",
    }
)
RESERVED_SYMBOL_NAMES = (
    repository_lisp_support.RESERVED_SYMBOL_NAMES | _SCHEME_RESERVED_SYMBOL_NAMES
)

_extract_top_level_forms = repository_lisp_support._extract_top_level_forms
_form_head = repository_lisp_support._form_head
_normalize_repository_relative_path = (
    repository_lisp_support._normalize_repository_relative_path
)
_parse_form = repository_lisp_support._parse_form
_path_aliases = repository_lisp_support._path_aliases
normalize_identifier = repository_lisp_support.normalize_identifier
normalize_symbol_name = repository_lisp_support.normalize_symbol_name
strip_comments = repository_lisp_support.strip_comments


def _extract_top_level_forms_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[int, str], ...]:
    forms: list[tuple[int, str]] = []
    depth = 0
    start_index: int | None = None
    start_line = 1
    line_no = 1
    in_string = False
    escaped = False
    for index, character in enumerate(stripped_text):
        if character == "\n":
            line_no += 1
        if in_string:
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            continue
        if character == "(":
            if depth == 0:
                start_index = index
                start_line = line_no
            depth += 1
            continue
        if character != ")":
            continue
        if depth <= 0:
            continue
        depth -= 1
        if depth == 0 and start_index is not None:
            forms.append((start_line, stripped_text[start_index : index + 1].strip()))
            start_index = None
    return tuple(forms)


def _prepared_top_level_forms(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[int, str, Any], ...]:
    normalized_text = stripped_text if stripped_text is not None else strip_comments(text)
    return tuple(
        (line_no, form_text, _parse_form(form_text))
        for line_no, form_text in _extract_top_level_forms_from_stripped_text(normalized_text)
    )


def _string_literal_value(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        return text[1:-1]
    return text


def _normalize_library_token(value: Any) -> str:
    normalized = normalize_symbol_name(str(value))
    if not normalized:
        normalized = normalize_identifier(str(value)).lstrip(":")
    return normalized.strip().lower()


def _library_spec_name(value: Any) -> str:
    if isinstance(value, list):
        parts = [
            part
            for item in value
            if (part := _library_spec_name(item))
        ]
        return ".".join(parts)
    return _normalize_library_token(_string_literal_value(value))


def _declared_library_aliases(
    text: str,
    *,
    stripped_text: str | None = None,
    prepared_forms: tuple[tuple[int, str, Any], ...] | None = None,
) -> tuple[str, ...]:
    aliases: set[str] = set()
    for _line_no, _form_text, parsed_form in (
        prepared_forms
        if prepared_forms is not None
        else _prepared_top_level_forms(text, stripped_text=stripped_text)
    ):
        if not isinstance(parsed_form, list) or len(parsed_form) < 2:
            continue
        head = _form_head(parsed_form)
        if head in {"define-library", "library", "module"}:
            alias = _library_spec_name(parsed_form[1])
            if alias:
                aliases.add(alias)
    return tuple(sorted(aliases))


def has_scheme_path_hints(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in _KNOWN_SCHEME_SUFFIXES:
        return True
    return path.name.lower() in _SCHEME_MANIFEST_BASENAMES


def is_probable_scheme_source(
    *,
    path: Path,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    suffix = path.suffix.lower()
    if (
        suffix not in _KNOWN_SCHEME_SUFFIXES
        and path.name.lower() not in _SCHEME_MANIFEST_BASENAMES
    ):
        return False
    return bool(_SCHEME_MARKER_RE.search(stripped_text if stripped_text is not None else strip_comments(text)))


def _module_symbol_aliases(
    path: PurePosixPath,
    symbol_name: str,
    *,
    library_aliases: tuple[str, ...],
) -> tuple[str, ...]:
    aliases = {symbol_name}
    for path_alias in _path_aliases(path):
        normalized_alias = normalize_identifier(path_alias)
        if normalized_alias:
            aliases.add(f"{normalized_alias}.{symbol_name}")
    for library_alias in library_aliases:
        normalized_library_alias = normalize_identifier(library_alias)
        if normalized_library_alias:
            aliases.add(f"{normalized_library_alias}.{symbol_name}")
    return tuple(sorted(alias for alias in aliases if alias))


def _definition_name_and_kind(line: str) -> tuple[str, str]:
    for pattern, symbol_kind in _DEFINITION_LINE_PATTERNS:
        match = pattern.search(line)
        if match is None:
            continue
        symbol_name = normalize_symbol_name(
            str(match.groupdict().get("name") or match.groupdict().get("name_list") or "")
        )
        if symbol_name:
            return symbol_name, symbol_kind
    return "", ""


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
    library_aliases: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SCHEME_SUFFIXES:
        return []
    normalized_text = stripped_text if stripped_text is not None else strip_comments(text)
    resolved_library_aliases = (
        library_aliases
        if library_aliases is not None
        else _declared_library_aliases(text, stripped_text=normalized_text)
    )
    stripped_lines = normalized_text.splitlines()
    final_line = len(stripped_lines) if stripped_lines else 1
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int]] = set()
    for line_no, line in enumerate(stripped_lines, start=1):
        symbol_name, symbol_kind = _definition_name_and_kind(line)
        if not symbol_name or not symbol_kind:
            continue
        symbol_key = (symbol_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "kind": symbol_kind,
                        "line": line_no,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": line_no,
                "end_line": line_no,
                "signature": line.strip(),
                "qualified_names": _module_symbol_aliases(
                    path,
                    symbol_name,
                    library_aliases=resolved_library_aliases,
                ),
            }
        )
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def _candidate_import_keys(import_target: str, *, current_file: str) -> tuple[str, ...]:
    normalized_target = _string_literal_value(import_target).replace("\\", "/").strip()
    if not normalized_target:
        normalized_target = normalize_identifier(import_target)
    normalized_target = normalized_target.strip()
    if not normalized_target:
        return ()
    target_path = normalized_target.replace(".", "/")
    current_parent = PurePosixPath(current_file).parent
    raw_candidates = [normalized_target, target_path]
    if not PurePosixPath(target_path).suffix:
        for base in (normalized_target, target_path):
            raw_candidates.extend(f"{base}{suffix}" for suffix in _KNOWN_SCHEME_SUFFIXES)
        raw_candidates.extend(
            f"{target_path}/main{suffix}" for suffix in _KNOWN_SCHEME_SUFFIXES
        )
    candidate_keys: list[str] = []
    seen_candidates: set[str] = set()
    for raw_candidate in raw_candidates:
        for candidate in (
            raw_candidate,
            str(current_parent / raw_candidate),
            f"src/{raw_candidate}",
            f"lib/{raw_candidate}",
            f"scheme/{raw_candidate}",
            f"s/{raw_candidate}",
        ):
            normalized_candidate = _normalize_repository_relative_path(candidate).lower()
            if not normalized_candidate or normalized_candidate in seen_candidates:
                continue
            seen_candidates.add(normalized_candidate)
            candidate_keys.append(normalized_candidate)
    return tuple(candidate_keys)


def _candidate_target_names(
    target_file: str,
    symbol_name: str,
    *,
    import_target: str | None = None,
) -> tuple[str, ...]:
    target_path = PurePosixPath(target_file)
    aliases = {symbol_name}
    for path_alias in _path_aliases(target_path):
        normalized_alias = normalize_identifier(path_alias)
        if normalized_alias:
            aliases.add(f"{normalized_alias}.{symbol_name}")
    if import_target:
        normalized_target = normalize_identifier(import_target)
        if normalized_target:
            aliases.add(f"{normalized_target}.{symbol_name}")
    return tuple(sorted(alias for alias in aliases if alias))


def _binding_pairs(values: list[Any]) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for value in values:
        if isinstance(value, list) and len(value) >= 2:
            source_name = normalize_symbol_name(str(value[0]))
            local_name = normalize_symbol_name(str(value[1]))
            if source_name and local_name:
                pairs.append((local_name, source_name))
            continue
        symbol_name = normalize_symbol_name(str(value))
        if symbol_name:
            pairs.append((symbol_name, symbol_name))
    return tuple(pairs)


def _import_entries(spec: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(spec, list):
        head = _form_head(spec)
        if head in {"for", "for-syntax", "meta", "only-meta"} and len(spec) >= 2:
            return _import_entries(spec[1])
        if head == "only" and len(spec) >= 2:
            names = _binding_pairs(list(spec[2:]))
            return tuple(
                {
                    **entry,
                    "bindings": names,
                }
                for entry in _import_entries(spec[1])
            )
        if head == "rename" and len(spec) >= 2:
            rename_pairs = _binding_pairs(list(spec[2:]))
            return tuple(
                {
                    **entry,
                    "bindings": rename_pairs,
                }
                for entry in _import_entries(spec[1])
            )
        if head == "prefix" and len(spec) >= 3:
            prefix = normalize_identifier(str(spec[2])).rstrip(":")
            return tuple(
                {
                    **entry,
                    "prefix": prefix,
                }
                for entry in _import_entries(spec[1])
            )
        if head == "except" and len(spec) >= 2:
            return _import_entries(spec[1])
    import_target = _library_spec_name(spec)
    if not import_target:
        return ()
    return (
        {
            "import_target": import_target,
            "bindings": (),
            "prefix": "",
        },
    )


def _load_targets(parsed_form: Any) -> tuple[str, ...]:
    head = _form_head(parsed_form)
    if head not in _LOAD_FORM_HEADS or len(parsed_form) < 2:
        return ()
    targets: list[str] = []
    for value in parsed_form[1:]:
        target = _string_literal_value(value).strip()
        if target:
            targets.append(target)
    return tuple(dict.fromkeys(targets))


def _is_candidate_reference_symbol(symbol_name: str) -> bool:
    normalized = normalize_identifier(symbol_name)
    if not normalized:
        return False
    if normalized.startswith(":") or normalized.startswith("&"):
        return False
    return normalized not in RESERVED_SYMBOL_NAMES
