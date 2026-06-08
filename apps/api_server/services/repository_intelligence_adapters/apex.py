from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]
NormalizeRepositoryRelativePath = Callable[[str], str]

_KNOWN_APEX_SUFFIXES = frozenset({".cls", ".trigger", ".apex"})
_TEST_PATH_TOKENS = frozenset({"test", "tests", "testing"})
_COMMENT_LINE_RE = re.compile(r"//.*?$", re.MULTILINE)
_ANNOTATION_RE = re.compile(
    r"^\s*@(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\((?P<body>[^\n]*)\))?\s*$",
    re.MULTILINE,
)
_TYPE_DECL_RE = re.compile(
    r"^\s*(?:@[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*)*"
    r"(?:(?:public|private|protected|global|virtual|abstract|static|final|"
    r"transient|webservice|with\s+sharing|without\s+sharing|inherited\s+sharing)\s+)*"
    r"(?P<kind>class|interface|enum)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+extends\s+(?P<extends>[^{]+?))?"
    r"(?:\s+implements\s+(?P<implements>[^{]+?))?"
    r"\s*(?:\{|$)",
    re.MULTILINE | re.IGNORECASE,
)
_TRIGGER_DECL_RE = re.compile(
    r"^\s*trigger\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+on\s+"
    r"(?P<object>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE | re.IGNORECASE,
)
_METHOD_DECL_RE = re.compile(
    r"^\s*(?:@[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*)*"
    r"(?:(?:public|private|protected|global|static|virtual|abstract|override|"
    r"testmethod|webservice|final|transient)\s+)*"
    r"(?:(?:[A-Za-z_][A-Za-z0-9_<>,.\[\]?]*)\s+)?"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE | re.IGNORECASE,
)
_FIELD_TYPE_RE = re.compile(
    r"\b(?P<type>[A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)?)"
    r"(?:<[^>]+>)?\s+[A-Za-z_][A-Za-z0-9_]*\s*(?:[=;,\)])"
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<qualifier>[A-Z][A-Za-z0-9_]*)\s*\.\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_NEW_REFERENCE_RE = re.compile(r"\bnew\s+(?P<name>[A-Z][A-Za-z0-9_]*)\s*\(")
_REFERENCE_NAME_RE = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:<[^>]+>)?\b"
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abstract",
        "after",
        "and",
        "as",
        "before",
        "break",
        "case",
        "catch",
        "class",
        "continue",
        "delete",
        "do",
        "else",
        "enum",
        "extends",
        "final",
        "finally",
        "for",
        "global",
        "if",
        "implements",
        "in",
        "insert",
        "interface",
        "merge",
        "new",
        "not",
        "null",
        "on",
        "or",
        "private",
        "protected",
        "public",
        "return",
        "static",
        "super",
        "switch",
        "testmethod",
        "this",
        "throw",
        "trigger",
        "try",
        "undelete",
        "update",
        "upsert",
        "virtual",
        "webservice",
        "when",
        "while",
        "with",
        "without",
    }
)
_BUILTIN_TYPE_NAMES = frozenset(
    {
        "blob",
        "boolean",
        "date",
        "datetime",
        "decimal",
        "double",
        "exception",
        "id",
        "integer",
        "list",
        "long",
        "map",
        "object",
        "set",
        "sobject",
        "string",
        "time",
        "void",
    }
)
_BUILTIN_QUALIFIER_NAMES = frozenset(
    {
        "approval",
        "apexpages",
        "auth",
        "crypto",
        "database",
        "encodingutil",
        "eventbus",
        "limits",
        "math",
        "messaging",
        "schema",
        "search",
        "security",
        "site",
        "system",
        "test",
        "trigger",
        "userinfo",
    }
)
_METHOD_PREFIX_BLACKLIST = (
    "if ",
    "for ",
    "while ",
    "switch ",
    "catch ",
    "return ",
    "new ",
    "insert ",
    "update ",
    "delete ",
    "upsert ",
    "merge ",
    "undelete ",
    "throw ",
    "trigger ",
)


def _strip_block_comments(text: str) -> str:
    chars: list[str] = []
    index = 0
    in_string = False
    string_char = ""
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        if in_string:
            chars.append(character)
            if character == string_char:
                in_string = False
            index += 1
            continue
        if character in {"'", '"'}:
            chars.append(character)
            string_char = character
            in_string = True
            index += 1
            continue
        if character == "/" and next_character == "*":
            index += 2
            while index < len(text):
                if text[index] == "*" and index + 1 < len(text) and text[index + 1] == "/":
                    index += 2
                    break
                if text[index] == "\n":
                    chars.append("\n")
                index += 1
            continue
        chars.append(character)
        index += 1
    return "".join(chars)


def strip_comments(text: str) -> str:
    return _COMMENT_LINE_RE.sub("", _strip_block_comments(text))


def _type_names(fragment: str) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    for raw_name in _REFERENCE_NAME_RE.findall(fragment):
        normalized_name = raw_name.split("<", 1)[0].split(".")[-1].strip()
        lowered_name = normalized_name.lower()
        if (
            not normalized_name
            or lowered_name in _RESERVED_SYMBOL_NAMES
            or lowered_name in _BUILTIN_TYPE_NAMES
        ):
            continue
        if lowered_name in seen:
            continue
        seen.add(lowered_name)
        names.append(normalized_name)
    return tuple(names)


def _declared_types_and_headers(text: str) -> tuple[tuple[str, str, int, str], ...]:
    headers: list[tuple[int, str, str, str]] = []
    for match in _TYPE_DECL_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name:
            continue
        header_targets = " ".join(
            fragment
            for fragment in (
                str(match.group("extends") or ""),
                str(match.group("implements") or ""),
            )
            if fragment.strip()
        )
        headers.append(
            (
                match.start(),
                str(match.group("kind") or "class").strip().lower(),
                symbol_name,
                header_targets,
            )
        )
    for match in _TRIGGER_DECL_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        target_object = str(match.group("object") or "").strip()
        if not symbol_name:
            continue
        headers.append((match.start(), "trigger", symbol_name, target_object))
    return tuple(
        (kind, name, offset, header_targets)
        for offset, kind, name, header_targets in sorted(headers)
    )


def _declared_symbol_names(text: str) -> set[str]:
    declared_names = {
        name.lower()
        for kind, name, _offset, _header_targets in _declared_types_and_headers(text)
        if kind in {"class", "interface", "enum", "trigger"}
    }
    for match in _METHOD_DECL_RE.finditer(text):
        line = str(match.group(0) or "").strip().lower()
        symbol_name = str(match.group("name") or "").strip()
        if (
            not symbol_name
            or symbol_name.lower() in _RESERVED_SYMBOL_NAMES
            or line.startswith(_METHOD_PREFIX_BLACKLIST)
        ):
            continue
        declared_names.add(symbol_name.lower())
    return declared_names


def is_probable_apex_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix not in _KNOWN_APEX_SUFFIXES:
        return False
    stripped_text = strip_comments(text)
    if suffix == ".trigger":
        return bool(_TRIGGER_DECL_RE.search(stripped_text))
    if _TYPE_DECL_RE.search(stripped_text):
        return True
    return bool(_ANNOTATION_RE.search(stripped_text) and "{" in stripped_text)


def is_probable_test_source(*, path: Path, text: str) -> bool:
    parts = {part.lower() for part in path.parts}
    if parts & _TEST_PATH_TOKENS:
        return True
    lowered_name = path.name.lower()
    if lowered_name.endswith("test.cls") or lowered_name.endswith("tests.cls"):
        return True
    return "@istest" in strip_comments(text).lower()


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_APEX_SUFFIXES:
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    if not is_probable_apex_source(path=Path(file_path), text=text):
        return set()
    stripped_text = strip_comments(text)
    aliases: set[str] = {
        file_path,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        path.stem,
    }
    for _kind, symbol_name, _offset, _targets in _declared_types_and_headers(stripped_text):
        aliases.add(symbol_name)
        aliases.add(f"{path.stem}.{symbol_name}")
    for match in _METHOD_DECL_RE.finditer(stripped_text):
        line = str(match.group(0) or "").strip().lower()
        symbol_name = str(match.group("name") or "").strip()
        if (
            not symbol_name
            or symbol_name.lower() in _RESERVED_SYMBOL_NAMES
            or line.startswith(_METHOD_PREFIX_BLACKLIST)
        ):
            continue
        aliases.add(symbol_name)
        aliases.add(f"{path.stem}.{symbol_name}")
    return aliases


def _resolve_symbol_target(
    *,
    symbol_name: str,
    current_file: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_name = str(symbol_name or "").strip()
    if not normalized_name:
        return None
    candidate_keys = (
        normalized_name,
        f"{normalized_name}.cls",
        f"{normalized_name}.trigger",
        f"classes/{normalized_name}.cls",
        f"triggers/{normalized_name}.trigger",
    )
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"/{normalized_name}.cls",
            f"/{normalized_name}.trigger",
        ],
    )


def _reference_targets(text: str) -> Iterable[tuple[str, int]]:
    stripped_text = strip_comments(text)
    declared_symbol_names = _declared_symbol_names(stripped_text)
    for _kind, _name, start_offset, header_targets in _declared_types_and_headers(stripped_text):
        for target_name in _type_names(header_targets):
            yield target_name, start_offset
    for match in _FIELD_TYPE_RE.finditer(stripped_text):
        for target_name in _type_names(str(match.group("type") or "")):
            yield target_name, match.start()
    for match in _NEW_REFERENCE_RE.finditer(stripped_text):
        target_name = str(match.group("name") or "").strip()
        if target_name and target_name.lower() not in _RESERVED_SYMBOL_NAMES:
            yield target_name, match.start()
    for match in _QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        qualifier = str(match.group("qualifier") or "").strip()
        if (
            not qualifier
            or qualifier.lower() in _RESERVED_SYMBOL_NAMES
            or qualifier.lower() in _BUILTIN_QUALIFIER_NAMES
        ):
            continue
        yield qualifier, match.start()
    seen_offsets: set[tuple[str, int]] = set()
    for match in _METHOD_DECL_RE.finditer(stripped_text):
        line = str(match.group(0) or "").strip().lower()
        method_name = str(match.group("name") or "").strip()
        if (
            not method_name
            or method_name.lower() in declared_symbol_names
            or method_name.lower() in _RESERVED_SYMBOL_NAMES
            or line.startswith(_METHOD_PREFIX_BLACKLIST)
        ):
            continue
        key = (method_name.lower(), match.start())
        if key in seen_offsets:
            continue
        seen_offsets.add(key)
        yield method_name, match.start()


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    del normalize_repository_relative_path
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for target_name, line_offset in _reference_targets(text):
        target_file = _resolve_symbol_target(
            symbol_name=target_name,
            current_file=file_path,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, target_name, "references")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target_name,
                        "symbol": target_name,
                        "kind": "references",
                        "line": line_offset,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="references",
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    del normalize_repository_relative_path
    stripped_text = strip_comments(text)
    lines = stripped_text.splitlines()
    symbol_entries: list[dict[str, Any]] = []
    for kind, symbol_name, start_offset, _targets in _declared_types_and_headers(stripped_text):
        line_no = stripped_text.count("\n", 0, start_offset) + 1
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "line": line_no,
                        "kind": kind,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": kind,
                "start_line": line_no,
                "end_line": line_no,
                "signature": symbol_name,
            }
        )
    declared_type_names = {
        str(entry["symbol_name"]).lower()
        for entry in symbol_entries
        if str(entry["symbol_kind"]) in {"class", "interface", "enum", "trigger"}
    }
    for match in _METHOD_DECL_RE.finditer(stripped_text):
        line_text = str(match.group(0) or "").strip().lower()
        symbol_name = str(match.group("name") or "").strip()
        if (
            not symbol_name
            or symbol_name.lower() in _RESERVED_SYMBOL_NAMES
            or line_text.startswith(_METHOD_PREFIX_BLACKLIST)
        ):
            continue
        line_no = stripped_text.count("\n", 0, match.start()) + 1
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "line": line_no,
                        "kind": "function",
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": "function",
                "start_line": line_no,
                "end_line": line_no,
                "signature": symbol_name,
            }
        )
    symbol_entries.sort(key=lambda entry: (int(entry["start_line"]), str(entry["symbol_name"])))
    final_line = len(lines) if lines else 1
    for index, entry in enumerate(symbol_entries):
        next_start = (
            int(symbol_entries[index + 1]["start_line"])
            if index + 1 < len(symbol_entries)
            else final_line + 1
        )
        entry["end_line"] = max(next_start - 1, int(entry["start_line"]))
    symbols = tuple(
        _Symbol(
            symbol_id=str(entry["symbol_id"]),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=None,
            signature=str(entry["signature"]),
        )
        for entry in symbol_entries
    )
    dependencies = parse_dependencies_only(
        file_path,
        stripped_text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=lambda value: value,
        resolve_suffix_match=resolve_suffix_match,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for target_name, _line_offset in _reference_targets(snippet):
            if target_name.lower() in declared_type_names and symbol.symbol_name == target_name:
                continue
            target_file = _resolve_symbol_target(
                symbol_name=target_name,
                current_file=file_path,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                _SymbolReferenceCandidate(
                    reference_edge_id=edge_id,
                    source_symbol_id=symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
