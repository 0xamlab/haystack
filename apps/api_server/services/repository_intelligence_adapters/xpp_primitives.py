from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".xpp", ".xpo", ".xml"})
_PATH_HINT_PARTS = frozenset(
    {
        "axclass",
        "axclassextension",
        "axformextension",
        "axtableextension",
        "axqueries",
        "axviewextension",
    }
)
_XML_SOURCE_ROOT_RE = re.compile(
    r"<(?P<tag>Ax(?:Class|ClassExtension|FormExtension|TableExtension|MapExtension|ViewExtension))\b"
)
_XML_DESCRIPTOR_ROOT_RE = re.compile(r"<AxModelInfo\b")
_XML_NAME_RE = re.compile(r"<Name>(?P<name>[^<]+)</Name>")
_XML_DECLARATION_RE = re.compile(
    r"<Declaration>\s*(?:<!\[CDATA\[(?P<cdata>.*?)\]\]>|(?P<body>.*?))\s*</Declaration>",
    re.DOTALL,
)
_XML_METHOD_RE = re.compile(
    r"<Method>\s*"
    r"<Name>(?P<name>[^<]+)</Name>"
    r".*?"
    r"<Source>\s*(?:<!\[CDATA\[(?P<cdata>.*?)\]\]>|(?P<body>.*?))\s*</Source>"
    r".*?</Method>",
    re.DOTALL,
)
_XPO_CLASS_RE = re.compile(r"^\s*CLASS\s+#(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*$", re.MULTILINE)
_XPO_SOURCE_BLOCK_RE = re.compile(
    r"^\s*SOURCE\s+#(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*$"
    r"(?P<body>.*?)"
    r"^\s*ENDSOURCE\s*$",
    re.MULTILINE | re.DOTALL,
)
_CLASS_DECL_RE = re.compile(
    r"^\s*(?:\[[^\]]+\]\s*)*"
    r"(?:(?:public|private|protected|static|final|abstract|client|server)\s+)*"
    r"class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+extends\s+(?P<extends>[A-Za-z_][A-Za-z0-9_]*))?"
    r"\s*(?:\{|$)",
    re.MULTILINE | re.IGNORECASE,
)
_METHOD_DECL_RE = re.compile(
    r"^\s*(?:public|private|protected|static|final|abstract|client|server|\s)+"
    r"(?:[A-Za-z_][A-Za-z0-9_<>]*)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_EXTENSION_OF_RE = re.compile(
    r"\[\s*ExtensionOf\s*\(\s*(?:classStr|tableStr|formStr|enumStr)\s*\(\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\)\s*\]",
    re.IGNORECASE,
)
_INCLUDE_RE = re.compile(r"^\s*#include\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
_STATIC_CALL_RE = re.compile(
    r"\b(?P<owner>[A-Z][A-Za-z0-9_]*)::(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_NEW_REFERENCE_RE = re.compile(r"\bnew\s+(?P<name>[A-Z][A-Za-z0-9_]*)\s*\(")
_TYPED_BINDING_RE = re.compile(
    r"\b(?P<type>[A-Z][A-Za-z0-9_]*)\s+"
    r"(?P<alias>[_A-Za-z][A-Za-z0-9_]*)\s*(?:[=;,\)])"
)
_INSTANCE_CALL_RE = re.compile(
    r"\b(?P<owner>[_A-Za-z][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_XPP_FEATURE_RE = re.compile(
    r"\bclass\s+[A-Za-z_][A-Za-z0-9_]*"
    r"|\[\s*ExtensionOf\s*\("
    r"|^\s*#include\s+[A-Za-z_][A-Za-z0-9_]*\b"
    r"|::[A-Za-z_][A-Za-z0-9_]*\s*\(",
    re.MULTILINE | re.IGNORECASE,
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "class",
        "delete",
        "do",
        "else",
        "for",
        "if",
        "insert",
        "new",
        "return",
        "select",
        "super",
        "switch",
        "ttsbegin",
        "ttscommit",
        "ttsabort",
        "update",
        "while",
    }
)
_RESERVED_REFERENCE_OWNERS = frozenset({"this", "super"})


@dataclass(frozen=True)
class _XppMethod:
    method_name: str
    body: str
    start_line: int


@dataclass(frozen=True)
class _XppDocument:
    object_name: str
    declaration: str
    methods: tuple[_XppMethod, ...]
    line_count: int


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    start_line: int
    end_line: int


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def clear_strip_comments_cache() -> None:
    strip_comments.cache_clear()


def _strip_comments_uncached(text: str) -> str:
    output: list[str] = []
    index = 0
    in_line_comment = False
    in_block_comment = False
    string_delim: str | None = None
    escape = False
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        if in_line_comment:
            if character == "\n":
                output.append("\n")
                in_line_comment = False
            else:
                output.append(" ")
            index += 1
            continue
        if in_block_comment:
            if character == "*" and next_character == "/":
                output.extend((" ", " "))
                index += 2
                in_block_comment = False
                continue
            output.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if string_delim is not None:
            output.append(character)
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif character == string_delim:
                string_delim = None
            index += 1
            continue
        if character in {"'", '"'}:
            output.append(character)
            string_delim = character
            index += 1
            continue
        if character == "/" and next_character == "/":
            output.extend((" ", " "))
            index += 2
            in_line_comment = True
            continue
        if character == "/" and next_character == "*":
            output.extend((" ", " "))
            index += 2
            in_block_comment = True
            continue
        output.append(character)
        index += 1
    return "".join(output)


@lru_cache(maxsize=1024)
def strip_comments(text: str) -> str:
    return _strip_comments_uncached(text)


def has_xpp_path_hints(path: Path | PurePosixPath) -> bool:
    pure_path = PurePosixPath(path)
    suffix = pure_path.suffix.lower()
    if suffix in {".xpp", ".xpo"}:
        return True
    if suffix != ".xml":
        return False
    return bool({part.lower() for part in pure_path.parts} & _PATH_HINT_PARTS)


def is_probable_xpp_descriptor_config(*, path: Path | PurePosixPath, text: str) -> bool:
    pure_path = PurePosixPath(path)
    if pure_path.suffix.lower() != ".xml":
        return False
    if pure_path.parent.name.lower() != "descriptor":
        return False
    return _XML_DESCRIPTOR_ROOT_RE.search(text) is not None


def is_probable_xpp_source(*, path: Path | PurePosixPath, text: str) -> bool:
    pure_path = PurePosixPath(path)
    suffix = pure_path.suffix.lower()
    if suffix in {".xpp", ".xpo"}:
        return True
    if suffix == ".xml":
        if _XML_SOURCE_ROOT_RE.search(text):
            return True
        if has_xpp_path_hints(pure_path) and (
            "<SourceCode>" in text or "<Declaration>" in text or "<Method>" in text
        ):
            return True
        return False
    return bool(_XPP_FEATURE_RE.search(strip_comments(text)) and has_xpp_path_hints(pure_path))


def _normalize_xml_text(value: str | None) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")


def _strip_xpo_source_prefix(body: str) -> str:
    lines: list[str] = []
    for raw_line in body.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        stripped_line = raw_line.lstrip()
        if stripped_line.startswith("#"):
            prefix_length = len(raw_line) - len(stripped_line)
            lines.append(raw_line[prefix_length + 1 :])
            continue
        lines.append(raw_line)
    return "\n".join(lines).strip("\n")


def _xpp_document_from_xml(text: str) -> _XppDocument | None:
    object_name_match = _XML_NAME_RE.search(text)
    object_name = str(object_name_match.group("name") if object_name_match else "").strip()
    declaration_match = _XML_DECLARATION_RE.search(text)
    declaration = _normalize_xml_text(
        (declaration_match.group("cdata") or declaration_match.group("body"))
        if declaration_match is not None
        else ""
    )
    methods: list[_XppMethod] = []
    for match in _XML_METHOD_RE.finditer(text):
        method_name = str(match.group("name") or "").strip()
        if not method_name:
            continue
        body = _normalize_xml_text(match.group("cdata") or match.group("body"))
        start_offset = (
            match.start("cdata")
            if match.group("cdata") is not None
            else match.start("body")
        )
        methods.append(
            _XppMethod(
                method_name=method_name,
                body=body,
                start_line=_line_number(text, start_offset),
            )
        )
    if not object_name and not declaration and not methods:
        return None
    return _XppDocument(
        object_name=object_name,
        declaration=declaration,
        methods=tuple(methods),
        line_count=_line_count(text),
    )


def _xpp_document_from_xpo(text: str) -> _XppDocument | None:
    class_match = _XPO_CLASS_RE.search(text)
    object_name = str(class_match.group("name") if class_match else "").strip()
    declaration = ""
    methods: list[_XppMethod] = []
    for match in _XPO_SOURCE_BLOCK_RE.finditer(text):
        block_name = str(match.group("name") or "").strip()
        body = _strip_xpo_source_prefix(str(match.group("body") or ""))
        start_line = _line_number(text, match.start("body"))
        if not block_name:
            continue
        if block_name.lower() == "classdeclaration":
            declaration = body
            continue
        methods.append(
            _XppMethod(
                method_name=block_name,
                body=body,
                start_line=start_line,
            )
        )
    if not object_name and not declaration and not methods:
        return None
    return _XppDocument(
        object_name=object_name,
        declaration=declaration,
        methods=tuple(methods),
        line_count=_line_count(text),
    )


def _xpp_document_from_plain_text(text: str) -> _XppDocument | None:
    stripped_text = strip_comments(text)
    class_match = _CLASS_DECL_RE.search(stripped_text)
    object_name = str(class_match.group("name") if class_match else "").strip()
    declaration = stripped_text
    methods: list[_XppMethod] = []
    for match in _METHOD_DECL_RE.finditer(stripped_text):
        method_name = str(match.group("name") or "").strip()
        if not method_name:
            continue
        methods.append(
            _XppMethod(
                method_name=method_name,
                body=stripped_text[match.start() :],
                start_line=_line_number(stripped_text, match.start()),
            )
        )
    if not object_name and not methods:
        return None
    return _XppDocument(
        object_name=object_name,
        declaration=declaration,
        methods=tuple(methods),
        line_count=_line_count(stripped_text),
    )


def parse_xpp_document(*, path: Path | PurePosixPath, text: str) -> _XppDocument | None:
    pure_path = PurePosixPath(path)
    suffix = pure_path.suffix.lower()
    if suffix == ".xml":
        return _xpp_document_from_xml(text)
    if suffix == ".xpo":
        return _xpp_document_from_xpo(text)
    return _xpp_document_from_plain_text(text)


def declared_object_name(document: _XppDocument) -> str:
    if document.object_name:
        return document.object_name
    declaration_match = _CLASS_DECL_RE.search(strip_comments(document.declaration))
    if declaration_match is None:
        return ""
    return str(declaration_match.group("name") or "").strip()


def relation_targets_for_document(document: _XppDocument) -> tuple[str, ...]:
    declaration = strip_comments(document.declaration)
    targets: list[str] = []
    seen: set[str] = set()
    class_match = _CLASS_DECL_RE.search(declaration)
    if class_match is not None:
        extends_target = str(class_match.group("extends") or "").strip()
        if extends_target and extends_target.lower() not in seen:
            seen.add(extends_target.lower())
            targets.append(extends_target)
    for match in _EXTENSION_OF_RE.finditer(declaration):
        target = str(match.group("name") or "").strip()
        if target and target.lower() not in seen:
            seen.add(target.lower())
            targets.append(target)
    return tuple(targets)


def include_targets_for_document(document: _XppDocument) -> tuple[tuple[str, int], ...]:
    targets: list[tuple[str, int]] = []
    for match in _INCLUDE_RE.finditer(strip_comments(document.declaration)):
        target = str(match.group("name") or "").strip()
        if target:
            targets.append((target, _line_number(document.declaration, match.start())))
    for method in document.methods:
        method_text = strip_comments(method.body)
        for match in _INCLUDE_RE.finditer(method_text):
            target = str(match.group("name") or "").strip()
            if target:
                targets.append(
                    (
                        target,
                        method.start_line + _line_number(method_text, match.start()) - 1,
                    )
                )
    return tuple(targets)


def typed_variable_bindings(text: str) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for match in _TYPED_BINDING_RE.finditer(strip_comments(text)):
        alias = str(match.group("alias") or "").strip().lower()
        target = str(match.group("type") or "").strip()
        if alias and target and alias not in _RESERVED_REFERENCE_OWNERS:
            bindings[alias] = target
    return bindings


def static_call_targets(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    targets: list[tuple[str, str, int]] = []
    for match in _STATIC_CALL_RE.finditer(stripped_text):
        owner = str(match.group("owner") or "").strip()
        method_name = str(match.group("name") or "").strip()
        if owner and method_name and method_name.lower() not in _RESERVED_REFERENCE_NAMES:
            targets.append((owner, method_name, _line_number(stripped_text, match.start())))
    return tuple(targets)


def new_reference_targets(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    targets: list[tuple[str, int]] = []
    for match in _NEW_REFERENCE_RE.finditer(stripped_text):
        target = str(match.group("name") or "").strip()
        if target:
            targets.append((target, _line_number(stripped_text, match.start())))
    return tuple(targets)


def instance_call_targets(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    targets: list[tuple[str, str, int]] = []
    for match in _INSTANCE_CALL_RE.finditer(stripped_text):
        owner = str(match.group("owner") or "").strip()
        method_name = str(match.group("name") or "").strip()
        if (
            owner
            and method_name
            and owner.lower() not in _RESERVED_REFERENCE_OWNERS
            and method_name.lower() not in _RESERVED_REFERENCE_NAMES
        ):
            targets.append((owner, method_name, _line_number(stripped_text, match.start())))
    return tuple(targets)
