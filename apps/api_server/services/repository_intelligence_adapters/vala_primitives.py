from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveDirectoryPrefixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".vala", ".vapi"})
_VALA_KEYWORDS = (
    "using ",
    "namespace ",
    "class ",
    "interface ",
    "struct ",
    "delegate ",
    "errordomain ",
    "enum ",
    "signal ",
)
_USING_RE = re.compile(
    r"^\s*using\s+(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)\s*;",
    re.MULTILINE,
)
_NAMESPACE_RE = re.compile(
    r"^\s*namespace\s+(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)\s*\{",
    re.MULTILINE,
)
_TYPE_DECL_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|abstract|class|compact|const|"
    r"dynamic|extern|inline|override|owned|sealed|signal|static|unowned|virtual|"
    r"weak)\s+)*(?:class|interface|struct|enum|delegate|errordomain)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b(?:\s*:\s*(?P<relations>[^{]+))?",
    re.MULTILINE,
)
_METHOD_DECL_RE = re.compile(
    r"^\s*(?!(?:if|for|foreach|while|switch|catch|return|yield|lock|assert)\b)"
    r"(?:(?:public|private|protected|internal|abstract|async|const|dynamic|extern|"
    r"inline|override|owned|sealed|signal|static|unowned|virtual|weak)\s+)*"
    r"(?:(?:[A-Za-z_][A-Za-z0-9_<>\.\[\]\?]*|void|bool|char|double|float|int|"
    r"int8|int16|int32|int64|long|size_t|string|uint|uint8|uint16|uint32|uint64)\s+)?"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*"
    r"(?:throws\s+[A-Za-z_][A-Za-z0-9_<>\.\[\]\?]*)?\s*(?:\{|=>|;)$",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_NEW_REFERENCE_RE = re.compile(
    r"\bnew\s+(?P<name>[A-Za-z_][A-Za-z0-9_\.]*)\s*\(",
)
_INSTANCE_ASSIGN_RE = re.compile(
    r"^\s*(?:(?:var|unowned|owned|weak)\s+)?"
    r"(?:(?P<declared_type>[A-Za-z_][A-Za-z0-9_\.]*)\s+)?"
    r"(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*new\s+"
    r"(?P<type_name>[A-Za-z_][A-Za-z0-9_\.]*)\s*\(",
    re.MULTILINE,
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "assert",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "construct",
        "continue",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "errordomain",
        "false",
        "finally",
        "for",
        "foreach",
        "get",
        "if",
        "in",
        "interface",
        "internal",
        "lock",
        "namespace",
        "new",
        "null",
        "out",
        "params",
        "private",
        "protected",
        "public",
        "ref",
        "return",
        "set",
        "signal",
        "static",
        "struct",
        "switch",
        "this",
        "throw",
        "throws",
        "true",
        "try",
        "using",
        "var",
        "void",
        "weak",
        "while",
        "yield",
    }
)
_BUILTIN_TYPE_NAMES = frozenset(
    {
        "bool",
        "char",
        "double",
        "float",
        "int",
        "int8",
        "int16",
        "int32",
        "int64",
        "long",
        "size_t",
        "string",
        "uint",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "void",
    }
)


def strip_comments(text: str) -> str:
    result_lines: list[str] = []
    in_block_comment = False
    for raw_line in text.splitlines():
        if not raw_line:
            result_lines.append("")
            continue
        line = raw_line
        if in_block_comment:
            end_index = line.find("*/")
            if end_index == -1:
                result_lines.append("")
                continue
            line = line[end_index + 2 :]
            in_block_comment = False
        stripped_line: list[str] = []
        index = 0
        while index < len(line):
            if line.startswith("/*", index):
                in_block_comment = True
                end_index = line.find("*/", index + 2)
                if end_index == -1:
                    break
                in_block_comment = False
                index = end_index + 2
                continue
            if line.startswith("//", index):
                break
            stripped_line.append(line[index])
            index += 1
        result_lines.append("".join(stripped_line).rstrip())
    return "\n".join(result_lines)


def has_vala_path_hints(path: Path) -> bool:
    return path.suffix.lower() in _KNOWN_SUFFIXES


def is_probable_vala_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix not in _KNOWN_SUFFIXES:
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if suffix == ".vapi":
        return True
    lowered_text = stripped_text.lower()
    if any(keyword in lowered_text for keyword in _VALA_KEYWORDS):
        return True
    return bool(_TYPE_DECL_RE.search(stripped_text) or _METHOD_DECL_RE.search(stripped_text))


def normalize_target(raw_target: str) -> str:
    return str(raw_target or "").strip().strip(".")


def normalize_symbol_name(raw_name: str) -> str:
    return str(raw_name or "").strip()


def without_suffix_aliases(path: PurePosixPath) -> tuple[str, ...]:
    without_suffix_path = str(path.with_suffix(""))
    if not without_suffix_path:
        return ()
    return (
        without_suffix_path,
        without_suffix_path.lower(),
        without_suffix_path.replace("/", "."),
        without_suffix_path.replace("/", ".").lower(),
    )


def split_relation_targets(raw_relations: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen_targets: set[str] = set()
    for raw_target in str(raw_relations or "").split(","):
        normalized_target = normalize_target(raw_target)
        if not normalized_target:
            continue
        canonical_target = normalized_target.lower()
        if canonical_target in seen_targets:
            continue
        seen_targets.add(canonical_target)
        targets.append(normalized_target)
    return tuple(targets)

