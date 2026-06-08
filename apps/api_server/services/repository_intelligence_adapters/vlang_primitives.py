from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _ImportedSymbolBinding,
    _Symbol,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]

_MODULE_RE = re.compile(r"^\s*module\s+(?P<name>[a-zA-Z_][A-Za-z0-9_.]*)\s*$", re.MULTILINE)
_IMPORT_RE = re.compile(r"^\s*import\s+(?P<body>.+)$", re.MULTILINE)
_FUNCTION_RE = re.compile(
    r"^\s*(?:pub\s+)?fn\s+(?:\([^)]+\)\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_TYPE_RE = re.compile(
    r"^\s*(?:pub\s+)?(?:struct|interface|enum|type)\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*\.\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_CALL_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_MANIFEST_NAME_RE = re.compile(r"^\s*name\s*:\s*['\"][^'\"]+['\"]\s*$", re.MULTILINE)
_V_SIGNAL_RE = re.compile(
    r"(^\s*module\s+[A-Za-z_][A-Za-z0-9_.]*\s*$)|"
    r"(^\s*import\s+[A-Za-z_][A-Za-z0-9_.]*(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?.*$)|"
    r"(^\s*(?:pub\s+)?fn\s+(?:\([^)]+\)\s*)?[A-Za-z_][A-Za-z0-9_]*\s*\()|"
    r"(^\s*(?:pub\s+)?(?:struct|interface|enum|type)\s+[A-Z][A-Za-z0-9_]*\b)",
    re.MULTILINE,
)
_VERILOG_SIGNAL_RE = re.compile(
    r"(^\s*endmodule\b)|(^\s*always(?:_ff|_comb|_latch)?\b)|(^\s*assign\b)|"
    r"(^\s*(?:input|output|inout|wire|logic|reg)\b)|(`include)|(^\s*module\s+\w+\s*\()",
    re.MULTILINE,
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "assert",
        "atomic",
        "break",
        "chan",
        "const",
        "continue",
        "defer",
        "dump",
        "else",
        "enum",
        "false",
        "fn",
        "for",
        "go",
        "goto",
        "if",
        "import",
        "in",
        "interface",
        "is",
        "lock",
        "match",
        "module",
        "mut",
        "none",
        "or",
        "pub",
        "return",
        "rlock",
        "select",
        "shared",
        "sizeof",
        "spawn",
        "static",
        "struct",
        "true",
        "type",
        "typeof",
        "union",
        "unsafe",
    }
)


def strip_comments(text: str) -> str:
    result: list[str] = []
    index = 0
    length = len(text)
    in_block_comment = False
    while index < length:
        char = text[index]
        next_char = text[index + 1] if index + 1 < length else ""
        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                result.extend((" ", " "))
                index += 2
                continue
            result.append("\n" if char == "\n" else " ")
            index += 1
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            result.extend((" ", " "))
            index += 2
            continue
        if char == "/" and next_char == "/":
            result.extend((" ", " "))
            index += 2
            while index < length and text[index] != "\n":
                result.append(" ")
                index += 1
            continue
        result.append(char)
        index += 1
    return "".join(result)


def has_v_path_hints(path: Path) -> bool:
    return path.suffix.lower() == ".v" or path.name.lower() == "v.mod"


def is_probable_v_manifest(path: Path, text: str) -> bool:
    if path.name.lower() != "v.mod":
        return False
    stripped = strip_comments(text)
    return "Module {" in stripped and _MANIFEST_NAME_RE.search(stripped) is not None


def is_probable_v_source(path: Path, text: str) -> bool:
    if path.name.lower() == "v.mod":
        return is_probable_v_manifest(path, text)
    if path.suffix.lower() != ".v":
        return False
    stripped = strip_comments(text)
    if _V_SIGNAL_RE.search(stripped) is None:
        return False
    verilog_hits = len(_VERILOG_SIGNAL_RE.findall(stripped))
    v_hits = len(_V_SIGNAL_RE.findall(stripped))
    return v_hits > 0 and v_hits >= verilog_hits


def module_name_from_text(text: str) -> str | None:
    match = _MODULE_RE.search(strip_comments(text))
    if match is None:
        return None
    name = str(match.group("name") or "").strip()
    return name or None


def split_import_targets(raw_body: str) -> tuple[tuple[str, str | None, tuple[str, ...]], ...]:
    body = raw_body.split("//", 1)[0].strip()
    if not body:
        return ()
    items: list[tuple[str, str | None, tuple[str, ...]]] = []
    for raw_item in body.split(","):
        item = raw_item.strip()
        if not item:
            continue
        explicit_names: tuple[str, ...] = ()
        if "{" in item and "}" in item:
            prefix, remainder = item.split("{", 1)
            target = prefix.strip()
            explicit_names = tuple(
                name.strip()
                for name in remainder.split("}", 1)[0].split(",")
                if name.strip()
            )
        else:
            target = item
        alias: str | None = None
        if " as " in target:
            target, alias = (part.strip() for part in target.split(" as ", 1))
        normalized = target.strip()
        if normalized:
            items.append((normalized, alias, explicit_names))
    return tuple(items)


def import_targets_for_text(text: str) -> tuple[str, ...]:
    targets: list[str] = []
    stripped = strip_comments(text)
    for match in _IMPORT_RE.finditer(stripped):
        for target, _alias, _names in split_import_targets(str(match.group("body") or "")):
            targets.append(target)
    return tuple(dict.fromkeys(targets))


def declared_symbol_names(text: str) -> tuple[str, ...]:
    stripped = strip_comments(text)
    names: list[str] = []
    for regex in (_FUNCTION_RE, _TYPE_RE):
        for match in regex.finditer(stripped):
            name = str(match.group("name") or "").strip()
            if name and name not in _RESERVED_SYMBOL_NAMES:
                names.append(name)
    return tuple(dict.fromkeys(names))


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    stripped = strip_comments(text)
    entries: list[tuple[int, str, str]] = []
    for regex, kind in ((_FUNCTION_RE, "function"), (_TYPE_RE, "type")):
        for match in regex.finditer(stripped):
            name = str(match.group("name") or "").strip()
            if not name:
                continue
            entries.append((_line_number(stripped, match.start()), name, kind))
    entries.sort(key=lambda item: item[0])
    final_line = stripped.count("\n") + (1 if stripped else 0)
    symbols: list[_Symbol] = []
    for index, (line_no, name, kind) in enumerate(entries):
        next_line = entries[index + 1][0] if index + 1 < len(entries) else final_line + 1
        end_line = max(line_no, next_line - 1)
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": name,
                        "kind": kind,
                        "line": line_no,
                    },
                ),
                symbol_name=name,
                symbol_kind=kind,
                start_line=line_no,
                end_line=end_line,
                parent_symbol_id=None,
                signature=name,
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
    aliases: set[str] = {file_path}
    if path.suffix.lower() == ".v":
        aliases.add(str(path.with_suffix("")))
        aliases.add(str(path.with_suffix("")).replace("/", "."))
        aliases.add(path.stem)
    elif path.name.lower() == "v.mod":
        aliases.add("v.mod")
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    module_name = module_name_from_text(text)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.split(".")[-1])
    for symbol_name in declared_symbol_names(text):
        aliases.add(symbol_name)
        if path.suffix.lower() == ".v":
            aliases.add(f"{path.stem}.{symbol_name}")
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None and direct_match != current_file:
        return direct_match
    current_parent = PurePosixPath(current_file).parent
    path_target = normalized_target.replace(".", "/")
    leaf = PurePosixPath(path_target).name
    candidate_keys: list[str] = []
    for raw_candidate in (
        str(current_parent / f"{path_target}.v"),
        str(current_parent / path_target / f"{leaf}.v"),
        f"{path_target}.v",
        f"{path_target}/{leaf}.v",
        f"{path_target}/main.v",
        f"src/{path_target}.v",
        f"src/{path_target}/{leaf}.v",
        f"src/{path_target}/main.v",
        f"cmd/{path_target}.v",
        f"cmd/{path_target}/{leaf}.v",
    ):
        normalized_candidate = normalize_repository_relative_path(raw_candidate)
        if normalized_candidate:
            candidate_keys.append(normalized_candidate)
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(dict.fromkeys(candidate_keys)),
    )


def imported_symbol_bindings(
    *,
    text: str,
    file_path: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    stripped = strip_comments(text)
    for match in _IMPORT_RE.finditer(stripped):
        for target, alias, explicit_names in split_import_targets(str(match.group("body") or "")):
            binding_alias = alias or PurePosixPath(target.replace(".", "/")).name
            if not binding_alias:
                continue
            bindings[binding_alias] = _ImportedSymbolBinding(
                alias=binding_alias,
                target_file=resolve_import(
                    current_file=file_path,
                    import_target=target,
                    module_index=module_index,
                    normalize_repository_relative_path=normalize_repository_relative_path,
                    resolve_suffix_match=resolve_suffix_match,
                ),
                target_names=explicit_names,
            )
    return bindings


def candidate_local_reference_names(
    text: str,
    *,
    imported_bindings: dict[str, _ImportedSymbolBinding],
    local_symbol_names: Iterable[str],
) -> tuple[str, ...]:
    stripped = strip_comments(text)
    local_names = set(local_symbol_names)
    candidates: list[str] = []
    for match in _CALL_RE.finditer(stripped):
        name = str(match.group("name") or "").strip()
        if (
            not name
            or name in _RESERVED_SYMBOL_NAMES
            or name in imported_bindings
            or name not in local_names
        ):
            continue
        candidates.append(name)
    return tuple(dict.fromkeys(candidates))
