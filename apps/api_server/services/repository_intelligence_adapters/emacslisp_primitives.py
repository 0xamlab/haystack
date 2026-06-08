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

_KNOWN_EMACSLISP_SUFFIXES = (".el",)
_EMACSLISP_MANIFEST_BASENAMES = frozenset({"cask"})
_EMACSLISP_SOURCE_ROOTS = ("lisp", "site-lisp", "extensions", "modules", "src", "lib")
_EMACSLISP_MARKER_RE = re.compile(
    r"(?im)^\s*;;;.*lexical-binding:|"
    r"^\s*\(\s*(?:defun|cl-defun|defmacro|cl-defmacro|defsubst|"
    r"defvar|defconst|defcustom|defface|define-(?:derived-mode|minor-mode|"
    r"globalized-minor-mode|inline)|require|provide(?:-theme)?|load(?:-library)?|"
    r"autoload|use-package|package-file|depends-on|source)\b"
)
_DEFINITION_HEAD_KINDS = {
    "cl-defmacro": "function",
    "cl-defun": "function",
    "defface": "variable",
    "defconst": "variable",
    "defcustom": "variable",
    "define-derived-mode": "function",
    "define-globalized-minor-mode": "function",
    "define-inline": "function",
    "define-minor-mode": "function",
    "defmacro": "function",
    "defsubst": "function",
    "defun": "function",
    "defvar": "variable",
}
_IMPORT_FORM_HEADS = frozenset(
    {
        "autoload",
        "load",
        "load-library",
        "require",
        "use-package",
    }
)
_QUALIFIED_REFERENCE_RE = repository_lisp_support._QUALIFIED_REFERENCE_RE
_UNQUALIFIED_REFERENCE_RE = repository_lisp_support._UNQUALIFIED_REFERENCE_RE
_EMACSLISP_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "autoload",
        "car",
        "cdr",
        "cl-defmacro",
        "cl-defun",
        "condition-case",
        "defface",
        "defconst",
        "defcustom",
        "define-derived-mode",
        "define-globalized-minor-mode",
        "define-inline",
        "define-minor-mode",
        "defmacro",
        "defsubst",
        "defun",
        "defvar",
        "funcall",
        "function",
        "if-let*",
        "interactive",
        "load-library",
        "mapc",
        "mapcar",
        "message",
        "package-file",
        "pcase",
        "prog1",
        "provide",
        "provide-theme",
        "push",
        "require",
        "save-current-buffer",
        "save-excursion",
        "save-match-data",
        "source",
        "setq",
        "setq-local",
        "unless",
        "use-package",
        "when-let*",
        "while",
        "with-current-buffer",
        "with-temp-buffer",
        "depends-on",
    }
)
RESERVED_SYMBOL_NAMES = (
    repository_lisp_support.RESERVED_SYMBOL_NAMES | _EMACSLISP_RESERVED_SYMBOL_NAMES
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


def _quoted_form_symbol(value: Any) -> str:
    if isinstance(value, list):
        if len(value) >= 2 and _form_head(value) == "quote":
            return normalize_identifier(str(value[1]))
        if value:
            return normalize_identifier(str(value[0]))
        return ""
    return normalize_identifier(str(value))


def _string_or_symbol_value(value: Any) -> str:
    if isinstance(value, list):
        if len(value) >= 2 and _form_head(value) == "quote":
            return normalize_identifier(str(value[1]))
        return ""
    return normalize_identifier(str(value))


def _definition_name(parsed_form: Any) -> str:
    if not isinstance(parsed_form, list) or len(parsed_form) < 2:
        return ""
    head = _form_head(parsed_form)
    if head not in _DEFINITION_HEAD_KINDS:
        return ""
    name_value = parsed_form[1]
    if isinstance(name_value, list):
        if not name_value:
            return ""
        return normalize_symbol_name(str(name_value[0]))
    return normalize_symbol_name(str(name_value))


def provided_features(text: str) -> tuple[str, ...]:
    features: list[str] = []
    seen_features: set[str] = set()
    for _line_no, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        head = _form_head(parsed_form)
        if head not in {"provide", "provide-theme"} or len(parsed_form) < 2:
            continue
        feature_name = _quoted_form_symbol(parsed_form[1])
        if not feature_name or feature_name in seen_features:
            continue
        seen_features.add(feature_name)
        features.append(feature_name)
    return tuple(features)


def cask_package_file_entries(text: str) -> tuple[str, ...]:
    entries: list[str] = []
    seen_entries: set[str] = set()
    for _line_no, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        if _form_head(parsed_form) != "package-file" or len(parsed_form) < 2:
            continue
        entry_path = _string_or_symbol_value(parsed_form[1])
        if not entry_path or entry_path in seen_entries:
            continue
        seen_entries.add(entry_path)
        entries.append(entry_path)
    return tuple(entries)


def has_emacslisp_path_hints(path: Path) -> bool:
    return (
        path.suffix.lower() in _KNOWN_EMACSLISP_SUFFIXES
        or path.name.lower() in _EMACSLISP_MANIFEST_BASENAMES
    )


def is_probable_emacslisp_source(*, path: Path, text: str) -> bool:
    if not has_emacslisp_path_hints(path):
        return False
    return bool(_EMACSLISP_MARKER_RE.search(strip_comments(text)))


def _module_symbol_aliases(
    path: PurePosixPath,
    symbol_name: str,
    *,
    feature_names: tuple[str, ...],
) -> tuple[str, ...]:
    aliases = {symbol_name}
    for path_alias in _path_aliases(path):
        normalized_alias = normalize_identifier(path_alias)
        if normalized_alias:
            aliases.add(f"{normalized_alias}.{symbol_name}")
    for feature_name in feature_names:
        normalized_feature_name = normalize_identifier(feature_name)
        if normalized_feature_name:
            aliases.add(f"{normalized_feature_name}.{symbol_name}")
    return tuple(sorted(alias for alias in aliases if alias))


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_EMACSLISP_SUFFIXES:
        return []
    stripped_text = strip_comments(text)
    feature_names = provided_features(text)
    final_line = len(stripped_text.splitlines()) if stripped_text else 1
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int]] = set()
    for line_no, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        symbol_kind = _DEFINITION_HEAD_KINDS.get(_form_head(parsed_form))
        symbol_name = _definition_name(parsed_form)
        if symbol_kind is None or not symbol_name:
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
                "end_line": min(final_line, line_no + form_text.count("\n")),
                "signature": form_text.splitlines()[0].strip(),
                "qualified_names": _module_symbol_aliases(
                    path,
                    symbol_name,
                    feature_names=feature_names,
                ),
            }
        )
    return symbol_entries
