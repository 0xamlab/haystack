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

_KNOWN_HAXE_SOURCE_SUFFIXES = frozenset({".hx"})
_KNOWN_HAXE_MANIFEST_SUFFIXES = frozenset({".hxml"})
_PACKAGE_RE = re.compile(
    r"^\s*package(?:\s+(?P<name>[a-z][A-Za-z0-9_]*(?:\.[a-z][A-Za-z0-9_]*)*))?\s*;",
    re.MULTILINE,
)
_IMPORT_RE = re.compile(
    r"^\s*(?P<kind>import|using)\s+"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
    r"(?:\s+(?:as|in)\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?"
    r"\s*;",
    re.MULTILINE,
)
_TYPE_RE = re.compile(
    r"^\s*(?:@\:[^\n]+\s*)*"
    r"(?:(?:public|private|extern)\s+)*"
    r"(?P<keyword>class|interface|enum|typedef|abstract)\s+"
    r"(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_FUNCTION_RE = re.compile(
    r"^\s*(?:@\:[^\n]+\s*)*"
    r"(?:(?:public|private|static|inline|macro|override|extern|final|dynamic)\s+)*"
    r"function\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_]*)\b")
_NEW_RE = re.compile(r"\bnew\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b")
_CALL_RE = re.compile(r"(?<![.])\b(?P<name>[a-z_][A-Za-z0-9_]*)\s*\(")
_HAXE_SOURCE_SIGNAL_RE = re.compile(
    r"(^\s*package(?:\s+[a-z][A-Za-z0-9_.]*)?\s*;)|"
    r"(^\s*(?:import|using)\s+[A-Za-z_][A-Za-z0-9_.]*\s*;)|"
    r"(^\s*(?:@\:[^\n]+\s*)*(?:(?:public|private|extern)\s+)*(?:class|interface|enum|typedef|abstract)\s+[A-Z][A-Za-z0-9_]*\b)|"
    r"(^\s*(?:@\:[^\n]+\s*)*(?:(?:public|private|static|inline|macro|override|extern|final|dynamic)\s+)*function\s+[A-Za-z_][A-Za-z0-9_]*\s*\()",
    re.MULTILINE,
)
_PROJECT_XML_SIGNAL_RE = re.compile(
    r"<(?:project|app|source|haxelib|haxedef|set)\b",
    re.IGNORECASE,
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abstract",
        "break",
        "case",
        "cast",
        "catch",
        "class",
        "continue",
        "default",
        "do",
        "dynamic",
        "else",
        "enum",
        "extern",
        "false",
        "final",
        "for",
        "function",
        "if",
        "implements",
        "import",
        "in",
        "inline",
        "interface",
        "macro",
        "new",
        "null",
        "override",
        "package",
        "private",
        "public",
        "return",
        "static",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typedef",
        "untyped",
        "using",
        "var",
        "while",
    }
)


def strip_comments(text: str) -> str:
    result: list[str] = []
    index = 0
    length = len(text)
    in_block_comment = False
    in_string = False
    string_delimiter = ""
    while index < length:
        character = text[index]
        next_character = text[index + 1] if index + 1 < length else ""
        if in_block_comment:
            if character == "*" and next_character == "/":
                in_block_comment = False
                result.extend((" ", " "))
                index += 2
                continue
            result.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string:
            result.append(character)
            if character == string_delimiter and (index == 0 or text[index - 1] != "\\"):
                in_string = False
                string_delimiter = ""
            index += 1
            continue
        if character == "/" and next_character == "*":
            in_block_comment = True
            result.extend((" ", " "))
            index += 2
            continue
        if character == "/" and next_character == "/":
            result.extend((" ", " "))
            index += 2
            while index < length and text[index] != "\n":
                result.append(" ")
                index += 1
            continue
        result.append(character)
        if character in {'"', "'"}:
            in_string = True
            string_delimiter = character
        index += 1
    return "".join(result)


def has_haxe_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    suffix = normalized_path.suffix.lower()
    return suffix in _KNOWN_HAXE_SOURCE_SUFFIXES | _KNOWN_HAXE_MANIFEST_SUFFIXES


def is_probable_haxe_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    suffix = normalized_path.suffix.lower()
    stripped_text = strip_comments(text)
    if suffix == ".hx":
        return _HAXE_SOURCE_SIGNAL_RE.search(stripped_text) is not None
    if suffix == ".hxml":
        return any(
            token in stripped_text
            for token in ("-main", "--main", "-cp", "--class-path", "--cwd")
        )
    if normalized_path.name.lower() == "project.xml":
        return _PROJECT_XML_SIGNAL_RE.search(stripped_text) is not None and any(
            marker in stripped_text.lower()
            for marker in ("<source", "<app", "<haxelib", "<haxedef", "openfl", "lime")
        )
    return False


def package_name_from_text(text: str) -> str | None:
    match = _PACKAGE_RE.search(strip_comments(text))
    if match is None:
        return None
    package_name = str(match.group("name") or "").strip()
    return package_name or None


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    for source_root in ("src", "source", "sources", "haxe", "test", "tests"):
        lowered_parts = tuple(part.lower() for part in path.parts)
        if source_root not in lowered_parts:
            continue
        root_index = lowered_parts.index(source_root)
        module_parts = list(path.parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem
        return ".".join(part for part in module_parts if part)
    return path.stem


def module_name_for_file(file_path: str, text: str) -> str:
    package_name = package_name_from_text(text)
    module_stem = PurePosixPath(file_path).stem
    if package_name:
        return f"{package_name}.{module_stem}"
    path_module_name = module_name_from_path(file_path)
    return path_module_name or module_stem


def import_statements(text: str) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, str, str | None, int]] = []
    for match in _IMPORT_RE.finditer(stripped_text):
        kind = str(match.group("kind") or "").strip()
        target = str(match.group("target") or "").strip()
        alias = str(match.group("alias") or "").strip() or None
        if not kind or not target:
            continue
        statements.append((kind, target, alias, _line_number(stripped_text, match.start())))
    return tuple(statements)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, symbol_kind in ((_TYPE_RE, "type"), (_FUNCTION_RE, "function")):
        for match in regex.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if (
                not symbol_name
                or symbol_name in seen_names
                or symbol_name in _RESERVED_SYMBOL_NAMES
            ):
                continue
            seen_names.add(symbol_name)
            entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    stripped_text = strip_comments(text)
    entries = iter_symbol_entries(stripped_text)
    final_line = _line_count(stripped_text)
    symbols: list[_Symbol] = []
    for index, (symbol_name, symbol_kind, start_line) in enumerate(entries):
        next_line = entries[index + 1][2] if index + 1 < len(entries) else final_line + 1
        end_line = max(start_line, next_line - 1)
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                        "start_line": start_line,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=start_line,
                end_line=end_line,
                parent_symbol_id=None,
                signature=symbol_name,
            )
        )
    return tuple(symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    aliases = {
        file_path,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        path.stem,
    }
    if path.suffix.lower() != ".hx":
        return {alias for alias in aliases if alias}
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_haxe_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_for_file(file_path, text)
    if module_name:
        aliases.add(module_name)
    for symbol_name, _kind, _line_no in iter_symbol_entries(text):
        aliases.add(symbol_name)
        if module_name and symbol_name != path.stem:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    module_path = normalized_target.replace(".", "/")
    candidate_keys = [
        normalized_target,
        module_path,
        f"{module_path}.hx",
        f"src/{module_path}.hx",
        f"source/{module_path}.hx",
        f"sources/{module_path}.hx",
        f"haxe/{module_path}.hx",
        f"test/{module_path}.hx",
        f"tests/{module_path}.hx",
    ]
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[f"{module_path}.hx", f"/{module_path}.hx"],
    )


def imported_symbol_bindings(
    *,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for _kind, target, alias, _line_no in import_statements(text):
        target_file = resolve_import(
            import_target=target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_name = target.rsplit(".", 1)[-1]
        binding_alias = alias or target_name
        if not binding_alias:
            continue
        bindings.setdefault(
            binding_alias,
            _ImportedSymbolBinding(
                alias=binding_alias,
                target_file=target_file,
                target_names=(target_name,) if target_name else (),
            ),
        )
    return bindings
