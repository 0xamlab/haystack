from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

_KNOWN_LISP_SUFFIXES = (".asd", ".lisp", ".lsp")
_LISP_SOURCE_ROOTS = ("src", "lib", "systems", "lisp")
_LISP_MARKER_RE = re.compile(
    r"\(\s*(?:asdf:defsystem|defsystem|defpackage|uiop:define-package|in-package|"
    r"defun|defmacro|defgeneric|defmethod|defclass|defstruct|define-condition|"
    r"defparameter|defvar|defconstant)\b",
    re.IGNORECASE,
)
_DEFINITION_HEAD_KINDS = {
    "defclass": "type",
    "defconstant": "variable",
    "define-condition": "type",
    "defgeneric": "function",
    "defmacro": "function",
    "defmethod": "function",
    "defparameter": "variable",
    "defstruct": "type",
    "defun": "function",
    "defvar": "variable",
}
_PACKAGE_FORM_HEADS = frozenset({"defpackage", "uiop:define-package"})
_SYSTEM_FORM_HEADS = frozenset({"asdf:defsystem", "defsystem"})
_LOAD_FORM_HEADS = frozenset(
    {
        "asdf:load-system",
        "compile-file",
        "load",
        "ql:quickload",
        "quickload",
        "require",
        "uiop:load-system",
    }
)
_PACKAGE_USE_OPTION_HEADS = frozenset({"use", "use-reexport"})
_PACKAGE_IMPORT_OPTION_HEADS = frozenset({"import-from", "shadowing-import-from"})
_PACKAGE_LOCAL_NICKNAME_HEADS = frozenset({"local-nicknames"})
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<package>[A-Za-z][A-Za-z0-9_.-]*)\s*(?P<separator>::|:)\s*"
    r"(?P<name>[A-Za-z*+!<>=/?$%&_.-][A-Za-z0-9*+!<>=/?$%&_.-]*)"
)
_UNQUALIFIED_REFERENCE_RE = re.compile(
    r"\(\s*(?P<name>[A-Za-z*+!<>=/?$%&_.-][A-Za-z0-9*+!<>=/?$%&_.:-]*)"
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "&allow-other-keys",
        "&aux",
        "&body",
        "&environment",
        "&key",
        "&optional",
        "&rest",
        "&whole",
        "*package*",
        "and",
        "block",
        "case",
        "catch",
        "cond",
        "declare",
        "defclass",
        "defconstant",
        "define-condition",
        "defgeneric",
        "defmacro",
        "defmethod",
        "defpackage",
        "defparameter",
        "defstruct",
        "defsystem",
        "defun",
        "defvar",
        "flet",
        "funcall",
        "handler-bind",
        "handler-case",
        "if",
        "in-package",
        "labels",
        "lambda",
        "let",
        "let*",
        "list",
        "load",
        "loop",
        "make-instance",
        "multiple-value-bind",
        "not",
        "or",
        "prog1",
        "progn",
        "ql:quickload",
        "quote",
        "require",
        "setf",
        "slot-value",
        "t",
        "uiop:define-package",
        "unless",
        "unwind-protect",
        "when",
        "with-open-file",
        "with-slots",
    }
)


def _replace_with_spaces(value: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in value)


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


def strip_comments(text: str) -> str:
    output: list[str] = []
    index = 0
    block_depth = 0
    in_string = False
    escaped = False
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        if block_depth:
            if character == "#" and next_character == "|":
                block_depth += 1
                output.extend((" ", " "))
                index += 2
                continue
            if character == "|" and next_character == "#":
                block_depth = max(0, block_depth - 1)
                output.extend((" ", " "))
                index += 2
                continue
            output.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            output.append(character)
            index += 1
            continue
        if character == "#" and next_character == "|":
            block_depth = 1
            output.extend((" ", " "))
            index += 2
            continue
        if character == ";":
            while index < len(text) and text[index] != "\n":
                output.append(" ")
                index += 1
            if index < len(text) and text[index] == "\n":
                output.append("\n")
                index += 1
            continue
        output.append(character)
        index += 1
    return "".join(output)


def _normalize_atom(value: str) -> str:
    normalized = str(value or "").strip()
    while normalized.startswith(("'", "`", ",")):
        normalized = normalized[1:].strip()
    if normalized.startswith("#'"):
        normalized = normalized[2:].strip()
    if normalized.startswith("#:"):
        normalized = normalized[2:].strip()
    if normalized.startswith("|") and normalized.endswith("|") and len(normalized) >= 2:
        normalized = normalized[1:-1].strip()
    if normalized.startswith('"') and normalized.endswith('"') and len(normalized) >= 2:
        normalized = normalized[1:-1]
    return normalized.strip().lower()


def normalize_identifier(raw_name: str) -> str:
    return _normalize_atom(raw_name)


def normalize_package_name(raw_name: str) -> str:
    normalized = _normalize_atom(raw_name)
    if normalized.startswith(":") and ":" not in normalized[1:]:
        normalized = normalized[1:].strip()
    return normalized


def _normalize_keyword(raw_name: str) -> str:
    normalized = _normalize_atom(raw_name)
    if normalized.startswith(":"):
        normalized = normalized[1:]
    return normalized


def normalize_symbol_name(raw_name: str) -> str:
    normalized = _normalize_atom(raw_name)
    if not normalized:
        return ""
    if normalized.startswith(":") and ":" not in normalized[1:]:
        normalized = normalized[1:]
    if "::" in normalized:
        normalized = normalized.rsplit("::", 1)[-1]
    elif ":" in normalized and not normalized.startswith(":"):
        normalized = normalized.rsplit(":", 1)[-1]
    return normalized


def _package_symbol_name(raw_name: str) -> tuple[str, str]:
    normalized = _normalize_atom(raw_name)
    if not normalized:
        return "", ""
    if "::" in normalized:
        package_name, symbol_name = normalized.split("::", 1)
        return normalize_package_name(package_name), normalize_symbol_name(symbol_name)
    if ":" in normalized and not normalized.startswith(":"):
        package_name, symbol_name = normalized.split(":", 1)
        return normalize_package_name(package_name), normalize_symbol_name(symbol_name)
    return "", normalize_symbol_name(normalized)


def _path_aliases(path: PurePosixPath) -> tuple[str, ...]:
    aliases = {
        str(path).lower(),
        str(path.with_suffix("")).lower(),
        str(path.with_suffix("")).replace("/", ".").lower(),
        normalize_identifier(path.stem),
    }
    return tuple(sorted(alias for alias in aliases if alias and alias not in {".", "/"}))


def _tokenize_form(form_text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    index = 0
    while index < len(form_text):
        character = form_text[index]
        if character.isspace():
            index += 1
            continue
        if character in {"(", ")"}:
            tokens.append(character)
            index += 1
            continue
        if character == '"':
            end_index = index + 1
            escaped = False
            while end_index < len(form_text):
                next_character = form_text[end_index]
                if escaped:
                    escaped = False
                elif next_character == "\\":
                    escaped = True
                elif next_character == '"':
                    end_index += 1
                    break
                end_index += 1
            tokens.append(form_text[index:end_index])
            index = end_index
            continue
        if character == "|":
            end_index = index + 1
            while end_index < len(form_text) and form_text[end_index] != "|":
                end_index += 1
            end_index = min(len(form_text), end_index + 1)
            tokens.append(form_text[index:end_index])
            index = end_index
            continue
        end_index = index
        while (
            end_index < len(form_text)
            and not form_text[end_index].isspace()
            and form_text[end_index] not in {"(", ")"}
        ):
            end_index += 1
        tokens.append(form_text[index:end_index])
        index = end_index
    return tuple(tokens)


def _parse_form(form_text: str) -> Any:
    tokens = _tokenize_form(form_text)
    position = 0

    def _parse_expression() -> Any:
        nonlocal position
        if position >= len(tokens):
            return None
        lexeme = tokens[position]
        position += 1
        if lexeme == "(":
            values: list[Any] = []
            while position < len(tokens) and tokens[position] != ")":
                value = _parse_expression()
                if value is not None:
                    values.append(value)
            if position < len(tokens) and tokens[position] == ")":
                position += 1
            return values
        if lexeme == ")":
            return None
        return lexeme

    return _parse_expression()


def _extract_top_level_forms(text: str) -> tuple[tuple[int, str], ...]:
    forms: list[tuple[int, str]] = []
    stripped_text = strip_comments(text)
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


def _form_head(parsed_form: Any) -> str:
    if not isinstance(parsed_form, list) or not parsed_form:
        return ""
    head = parsed_form[0]
    if not isinstance(head, str):
        return ""
    return normalize_identifier(head)


def _form_properties(values: list[Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    index = 0
    while index < len(values):
        candidate = values[index]
        if not isinstance(candidate, str):
            index += 1
            continue
        key = _normalize_keyword(candidate)
        if not key:
            index += 1
            continue
        if index + 1 < len(values):
            properties[key] = values[index + 1]
            index += 2
            continue
        properties[key] = True
        index += 1
    return properties


def _truthy_value(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value)
    normalized = normalize_identifier(str(value or ""))
    return normalized not in {"", "nil", "false"}


def _component_path(raw_value: Any) -> str:
    normalized = normalize_identifier(str(raw_value or ""))
    if not normalized:
        return ""
    normalized = normalized.replace("\\", "/")
    return _normalize_repository_relative_path(normalized)


def _normalize_component_file_path(prefix: str, component_name: str) -> str:
    normalized_name = _component_path(component_name)
    if not normalized_name:
        return ""
    path = PurePosixPath(prefix) / normalized_name if prefix else PurePosixPath(normalized_name)
    if path.suffix.lower() not in _KNOWN_LISP_SUFFIXES:
        path = path.with_suffix(".lisp")
    return _normalize_repository_relative_path(str(path))


def _component_dependency_names(raw_value: Any) -> tuple[str, ...]:
    if not isinstance(raw_value, list):
        normalized = normalize_identifier(str(raw_value or ""))
        return (normalized,) if normalized else ()
    names: list[str] = []
    seen_names: set[str] = set()
    for value in raw_value:
        normalized = normalize_identifier(str(value or ""))
        if not normalized or normalized in seen_names:
            continue
        seen_names.add(normalized)
        names.append(normalized)
    return tuple(names)


def _collect_component_entries(
    components_value: Any,
    *,
    prefix: str,
    serial: bool,
) -> list[dict[str, Any]]:
    if not isinstance(components_value, list):
        return []
    component_entries: list[dict[str, Any]] = []
    previous_component_name = ""
    for component in components_value:
        if not isinstance(component, list) or len(component) < 2:
            continue
        component_kind = _normalize_keyword(str(component[0]))
        if component_kind not in {"file", "module"}:
            continue
        properties = _form_properties(component[2:])
        if component_kind == "module":
            module_prefix = _component_path(properties.get("pathname") or component[1])
            nested_entries = _collect_component_entries(
                properties.get("components"),
                prefix=_normalize_repository_relative_path(
                    str(PurePosixPath(prefix) / module_prefix)
                )
                if prefix or module_prefix
                else "",
                serial=serial or _truthy_value(properties.get("serial")),
            )
            if serial and previous_component_name and nested_entries:
                nested_entries[0]["depends_on_names"] = tuple(
                    dict.fromkeys(
                        list(nested_entries[0]["depends_on_names"]) + [previous_component_name]
                    )
                )
            component_entries.extend(nested_entries)
            if nested_entries:
                previous_component_name = str(nested_entries[-1]["component_name"])
            continue
        normalized_path = _normalize_component_file_path(
            prefix,
            str(properties.get("pathname") or component[1]),
        )
        if not normalized_path:
            continue
        component_name = normalize_identifier(PurePosixPath(normalized_path).stem)
        depends_on_names = list(_component_dependency_names(properties.get("depends-on")))
        if serial and previous_component_name:
            depends_on_names.append(previous_component_name)
        component_entries.append(
            {
                "path": normalized_path,
                "component_name": component_name,
                "component_kind": component_kind,
                "depends_on_names": tuple(dict.fromkeys(name for name in depends_on_names if name)),
            }
        )
        previous_component_name = component_name
    return component_entries


def project_system_names(text: str) -> tuple[str, ...]:
    system_names: list[str] = []
    seen_names: set[str] = set()
    for _line_no, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        if _form_head(parsed_form) not in _SYSTEM_FORM_HEADS or len(parsed_form) < 2:
            continue
        system_name = normalize_identifier(str(parsed_form[1]))
        if not system_name or system_name in seen_names:
            continue
        seen_names.add(system_name)
        system_names.append(system_name)
    return tuple(system_names)


def project_component_entries(
    text: str,
    *,
    manifest_path: str,
) -> tuple[dict[str, Any], ...]:
    manifest_dir = PurePosixPath(
        _normalize_repository_relative_path(str(PurePosixPath(manifest_path).parent))
    )
    component_entries: list[dict[str, Any]] = []
    for _line_no, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        if _form_head(parsed_form) not in _SYSTEM_FORM_HEADS or len(parsed_form) < 2:
            continue
        properties = _form_properties(parsed_form[2:])
        root_prefix = _component_path(properties.get("pathname"))
        for entry in _collect_component_entries(
            properties.get("components"),
            prefix=root_prefix,
            serial=_truthy_value(properties.get("serial")),
        ):
            resolved_path = _normalize_repository_relative_path(
                str(manifest_dir / str(entry["path"]))
            )
            component_entries.append(
                {
                    **entry,
                    "path": resolved_path,
                }
            )
    return tuple(component_entries)

