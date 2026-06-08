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

_KNOWN_RACKET_SUFFIXES = (".rkt", ".rktl")
_RACKET_MANIFEST_BASENAMES = frozenset({"info.rkt"})
_RACKET_MARKER_RE = re.compile(
    r"(?im)^\s*#lang\b|"
    r"\(\s*(?:module\*?|module\+|require|provide|"
    r"define(?:/contract|-syntax(?:-rule|-parser)?|-values|-type)?|"
    r"define/public|define/private|define/override|"
    r"define-syntax-parameter|struct|define-struct|class)\b"
)
_DEFINITION_HEAD_KINDS = {
    "class": "type",
    "define": "variable",
    "define-type": "type",
    "define-values": "variable",
    "define/contract": "variable",
    "define-struct": "type",
    "define-syntax": "function",
    "define-syntax-parameter": "variable",
    "define-syntax-parser": "function",
    "define-syntax-rule": "function",
    "struct": "type",
}
_REQUIRE_FORM_HEADS = frozenset({"require"})
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<prefix>[A-Za-z][A-Za-z0-9_.-]*)\s*:\s*"
    r"(?P<name>[A-Za-z*+!<>=/?$%&_.-][A-Za-z0-9*+!<>=/?$%&_.-]*)"
)
_UNQUALIFIED_REFERENCE_RE = repository_lisp_support._UNQUALIFIED_REFERENCE_RE
_FOR_WRAPPER_HEADS = frozenset({"for-label", "for-meta", "for-syntax", "for-template"})
_RACKET_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "begin",
        "case",
        "class",
        "cond",
        "define",
        "define-syntax",
        "define-syntax-rule",
        "define-values",
        "define/contract",
        "else",
        "if",
        "lambda",
        "let",
        "let*",
        "let-values",
        "module",
        "module*",
        "module+",
        "new",
        "or",
        "provide",
        "quote",
        "quasiquote",
        "require",
        "send",
        "set!",
        "struct",
        "super-new",
        "syntax-case",
        "syntax-rules",
        "unquote",
        "when",
        "with-handlers",
    }
)
RESERVED_SYMBOL_NAMES = (
    repository_lisp_support.RESERVED_SYMBOL_NAMES | _RACKET_RESERVED_SYMBOL_NAMES
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


def has_racket_path_hints(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in _KNOWN_RACKET_SUFFIXES:
        return True
    return path.name.lower() in _RACKET_MANIFEST_BASENAMES


def is_probable_racket_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if (
        suffix not in _KNOWN_RACKET_SUFFIXES
        and path.name.lower() not in _RACKET_MANIFEST_BASENAMES
    ):
        return False
    return bool(_RACKET_MARKER_RE.search(strip_comments(text)))


def _string_literal_value(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        return text[1:-1]
    return text


def _definition_name_and_kind(parsed_form: Any) -> tuple[str, str]:
    if not isinstance(parsed_form, list) or len(parsed_form) < 2:
        return "", ""
    head = _form_head(parsed_form)
    if head in {"define", "define/contract"}:
        name_value = parsed_form[1]
        if isinstance(name_value, list):
            if not name_value:
                return "", ""
            return normalize_symbol_name(str(name_value[0])), "function"
        return normalize_symbol_name(str(name_value)), "variable"
    if head == "define-values":
        name_value = parsed_form[1]
        if isinstance(name_value, list):
            for candidate in name_value:
                normalized = normalize_symbol_name(str(candidate))
                if normalized:
                    return normalized, "variable"
            return "", ""
        return normalize_symbol_name(str(name_value)), "variable"
    symbol_kind = _DEFINITION_HEAD_KINDS.get(head)
    if symbol_kind is None:
        return "", ""
    name_value = parsed_form[1]
    if isinstance(name_value, list):
        if not name_value:
            return "", ""
        return normalize_symbol_name(str(name_value[0])), symbol_kind
    return normalize_symbol_name(str(name_value)), symbol_kind


def _module_symbol_aliases(path: PurePosixPath, symbol_name: str) -> tuple[str, ...]:
    aliases = {symbol_name}
    for path_alias in _path_aliases(path):
        normalized_alias = normalize_identifier(path_alias)
        if normalized_alias:
            aliases.add(f"{normalized_alias}.{symbol_name}")
    return tuple(sorted(alias for alias in aliases if alias))


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_RACKET_SUFFIXES:
        return []
    stripped_text = strip_comments(text)
    final_line = len(stripped_text.splitlines()) if stripped_text else 1
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int]] = set()
    for line_no, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        symbol_name, symbol_kind = _definition_name_and_kind(parsed_form)
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
                "signature": form_text.splitlines()[0].strip(),
                "qualified_names": _module_symbol_aliases(path, symbol_name),
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
    if not normalized_target:
        return ()
    current_parent = PurePosixPath(current_file).parent
    raw_candidates = [normalized_target]
    if not PurePosixPath(normalized_target).suffix:
        raw_candidates.extend(
            f"{normalized_target}{suffix}" for suffix in _KNOWN_RACKET_SUFFIXES
        )
        raw_candidates.append(f"{normalized_target}/main.rkt")
    candidate_keys: list[str] = []
    seen_candidates: set[str] = set()
    for raw_candidate in raw_candidates:
        for candidate in (raw_candidate, str(current_parent / raw_candidate)):
            normalized_candidate = _normalize_repository_relative_path(candidate).lower()
            if not normalized_candidate or normalized_candidate in seen_candidates:
                continue
            seen_candidates.add(normalized_candidate)
            candidate_keys.append(normalized_candidate)
    return tuple(candidate_keys)


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


def _require_entries(spec: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(spec, list):
        head = _form_head(spec)
        if head in {"file", "submod"} and len(spec) >= 2:
            return _require_entries(spec[1])
        if head in _FOR_WRAPPER_HEADS | {"combine-in"}:
            entries: list[dict[str, Any]] = []
            for value in spec[1:]:
                entries.extend(_require_entries(value))
            return tuple(entries)
        if head == "prefix-in" and len(spec) >= 3:
            prefix = normalize_identifier(str(spec[1])).rstrip(":")
            entries = []
            for entry in _require_entries(spec[2]):
                updated_entry = dict(entry)
                updated_entry["prefix"] = prefix
                entries.append(updated_entry)
            return tuple(entries)
        if head == "only-in" and len(spec) >= 2:
            bindings = _binding_pairs(list(spec[2:]))
            entries = []
            for entry in _require_entries(spec[1]):
                updated_entry = dict(entry)
                updated_bindings = dict(updated_entry.get("bindings", {}))
                updated_bindings.update(bindings)
                updated_entry["bindings"] = tuple(updated_bindings.items())
                entries.append(updated_entry)
            return tuple(entries)
        if head == "rename-in" and len(spec) >= 2:
            entries = []
            for entry in _require_entries(spec[1]):
                updated_entry = dict(entry)
                updated_bindings = dict(updated_entry.get("bindings", {}))
                updated_bindings.update(_binding_pairs(list(spec[2:])))
                updated_entry["bindings"] = tuple(updated_bindings.items())
                entries.append(updated_entry)
            return tuple(entries)
        if head == "except-in" and len(spec) >= 2:
            return _require_entries(spec[1])
        return ()
    import_target = _string_literal_value(spec)
    if not import_target:
        return ()
    return ({"import_target": import_target, "prefix": "", "bindings": ()},)


def _candidate_target_names(target_file: str, symbol_name: str) -> tuple[str, ...]:
    path = PurePosixPath(target_file)
    aliases = {normalize_symbol_name(symbol_name)}
    for path_alias in _path_aliases(path):
        normalized_alias = normalize_identifier(path_alias)
        if normalized_alias:
            aliases.add(f"{normalized_alias}.{normalize_symbol_name(symbol_name)}")
    return tuple(sorted(alias for alias in aliases if alias))


def _is_candidate_reference_symbol(symbol_name: str) -> bool:
    normalized = normalize_symbol_name(symbol_name)
    if not normalized or normalized.startswith("#:"):
        return False
    return normalized not in RESERVED_SYMBOL_NAMES
