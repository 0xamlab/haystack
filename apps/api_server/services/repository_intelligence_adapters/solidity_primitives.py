from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveImport = Callable[[str], str | None]

_KNOWN_SOLIDITY_SUFFIXES = (".sol",)
_SOLIDITY_SOURCE_ROOTS = ("contracts", "src", "script", "scripts")
_PACKAGE_PREFIX_CACHE: dict[str, tuple[str, ...]] = {}

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abstract",
        "address",
        "anonymous",
        "as",
        "bool",
        "break",
        "bytes",
        "calldata",
        "case",
        "catch",
        "constant",
        "constructor",
        "continue",
        "contract",
        "default",
        "delete",
        "do",
        "else",
        "emit",
        "enum",
        "error",
        "event",
        "external",
        "fallback",
        "false",
        "for",
        "from",
        "function",
        "if",
        "immutable",
        "import",
        "indexed",
        "interface",
        "internal",
        "is",
        "library",
        "mapping",
        "memory",
        "modifier",
        "new",
        "override",
        "payable",
        "pragma",
        "private",
        "public",
        "pure",
        "receive",
        "return",
        "returns",
        "revert",
        "storage",
        "string",
        "struct",
        "switch",
        "true",
        "try",
        "type",
        "uint",
        "using",
        "var",
        "view",
        "virtual",
        "while",
    }
)
BUILTIN_TYPE_NAMES = frozenset(
    {
        "address",
        "bool",
        "byte",
        "bytes",
        "bytes1",
        "bytes2",
        "bytes3",
        "bytes4",
        "bytes5",
        "bytes6",
        "bytes7",
        "bytes8",
        "bytes9",
        "bytes10",
        "bytes11",
        "bytes12",
        "bytes13",
        "bytes14",
        "bytes15",
        "bytes16",
        "bytes17",
        "bytes18",
        "bytes19",
        "bytes20",
        "bytes21",
        "bytes22",
        "bytes23",
        "bytes24",
        "bytes25",
        "bytes26",
        "bytes27",
        "bytes28",
        "bytes29",
        "bytes30",
        "bytes31",
        "bytes32",
        "fixed",
        "int",
        "int8",
        "int16",
        "int24",
        "int32",
        "int40",
        "int48",
        "int56",
        "int64",
        "int72",
        "int80",
        "int88",
        "int96",
        "int104",
        "int112",
        "int120",
        "int128",
        "int136",
        "int144",
        "int152",
        "int160",
        "int168",
        "int176",
        "int184",
        "int192",
        "int200",
        "int208",
        "int216",
        "int224",
        "int232",
        "int240",
        "int248",
        "int256",
        "string",
        "ufixed",
        "uint",
        "uint8",
        "uint16",
        "uint24",
        "uint32",
        "uint40",
        "uint48",
        "uint56",
        "uint64",
        "uint72",
        "uint80",
        "uint88",
        "uint96",
        "uint104",
        "uint112",
        "uint120",
        "uint128",
        "uint136",
        "uint144",
        "uint152",
        "uint160",
        "uint168",
        "uint176",
        "uint184",
        "uint192",
        "uint200",
        "uint208",
        "uint216",
        "uint224",
        "uint232",
        "uint240",
        "uint248",
        "uint256",
    }
)
IMPORT_RE = re.compile(
    r"\bimport\s+"
    r"(?:(?:\{(?P<braced>[^}]+)\}\s+from\s+)|(?:\*\s+as\s+(?P<namespace>[A-Za-z_][A-Za-z0-9_]*)\s+from\s+))?"
    r"(?P<target>\"[^\"]+\"|'[^']+')\s*;",
    re.IGNORECASE,
)
CONTRACT_DECL_RE = re.compile(
    r"\b(?:(?P<abstract>abstract)\s+)?(?P<kind>contract|interface|library)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+is\s+(?P<inherits>[^{]+))?\s*\{",
    re.IGNORECASE,
)
FUNCTION_DECL_RE = re.compile(
    r"\bfunction\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.IGNORECASE,
)
TYPE_DECL_RE = re.compile(
    r"\b(?P<kind>struct|enum|error)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
USING_RE = re.compile(
    r"\busing\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+for\b",
    re.IGNORECASE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<qualifier>[A-Z][A-Za-z0-9_]*)\s*\.\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
NEW_REFERENCE_RE = re.compile(
    r"\bnew\s+(?P<name>[A-Z][A-Za-z0-9_]*)\s*\(",
)
INHERITANCE_ITEM_RE = re.compile(
    r"(?P<name>[A-Z][A-Za-z0-9_]*)(?:\s*\([^)]*\))?"
)


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
    chars: list[str] = []
    index = 0
    in_single = False
    in_double = False
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        if not in_double and character == "'":
            in_single = not in_single
            chars.append(character)
            index += 1
            continue
        if not in_single and character == '"':
            escaped = index > 0 and text[index - 1] == "\\"
            if not escaped:
                in_double = not in_double
            chars.append(character)
            index += 1
            continue
        if not in_single and not in_double and character == "/" and next_character == "/":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        if not in_single and not in_double and character == "/" and next_character == "*":
            index += 2
            while index < len(text):
                block_character = text[index]
                block_next = text[index + 1] if index + 1 < len(text) else ""
                if block_character == "\n":
                    chars.append("\n")
                if block_character == "*" and block_next == "/":
                    index += 2
                    break
                index += 1
            continue
        chars.append(character)
        index += 1
    return "".join(chars)


def normalize_identifier(raw_name: str) -> str:
    return str(raw_name or "").strip()


def normalize_import_target(raw_target: str) -> str:
    return normalize_identifier(raw_target).strip("'\"").replace("\\", "/")


def _is_candidate_symbol_name(name: str) -> bool:
    normalized_name = normalize_identifier(name)
    if not normalized_name:
        return False
    lower_name = normalized_name.lower()
    return lower_name not in RESERVED_SYMBOL_NAMES and lower_name not in BUILTIN_TYPE_NAMES


def _path_aliases(path: PurePosixPath) -> tuple[set[str], set[str]]:
    aliases = {
        str(path),
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    source_relative_aliases: set[str] = set()
    source_parts = list(path.parts)
    for source_root in _SOLIDITY_SOURCE_ROOTS:
        if source_root not in source_parts:
            continue
        source_index = source_parts.index(source_root)
        derived_parts = list(source_parts[source_index + 1 :])
        if not derived_parts:
            break
        relative_with_suffix = "/".join(derived_parts)
        relative_without_suffix = str(PurePosixPath(relative_with_suffix).with_suffix(""))
        source_relative_aliases.update(
            {
                relative_with_suffix,
                relative_without_suffix,
                relative_without_suffix.replace("/", "."),
            }
        )
        break
    aliases.update(source_relative_aliases)
    return {alias for alias in aliases if alias}, source_relative_aliases


def _package_name_prefixes(root_path: Path) -> tuple[str, ...]:
    cache_key = str(root_path.resolve())
    cached = _PACKAGE_PREFIX_CACHE.get(cache_key)
    if cached is not None:
        return cached
    prefixes: set[str] = set()
    repo_name = re.sub(r"[^a-z0-9_/@.-]+", "", root_path.name.lower()).strip()
    if repo_name:
        prefixes.add(repo_name)
    package_json_candidates = [
        root_path / "package.json",
        *sorted(root_path.glob("*/package.json")),
    ]
    for package_json_path in package_json_candidates:
        if not package_json_path.is_file():
            continue
        try:
            payload = json.loads(
                package_json_path.read_text(encoding="utf-8", errors="replace")
            )
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        package_name = str(payload.get("name") or "").strip()
        if package_name:
            prefixes.add(package_name)
    ordered_prefixes = tuple(sorted(prefix for prefix in prefixes if prefix))
    _PACKAGE_PREFIX_CACHE[cache_key] = ordered_prefixes
    return ordered_prefixes


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _declaration_entries(stripped_text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for match in CONTRACT_DECL_RE.finditer(stripped_text):
        kind = str(match.group("kind") or "").lower()
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not _is_candidate_symbol_name(symbol_name):
            continue
        symbol_kind = "interface" if kind == "interface" else "type"
        entries.append(
            {
                "offset": match.start(),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "signature": str(match.group(0) or "").strip(),
                "qualified_names": (symbol_name,),
            }
        )
    for match in TYPE_DECL_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not _is_candidate_symbol_name(symbol_name):
            continue
        entries.append(
            {
                "offset": match.start(),
                "symbol_name": symbol_name,
                "symbol_kind": "type",
                "signature": str(match.group(0) or "").strip(),
                "qualified_names": (symbol_name,),
            }
        )
    for match in FUNCTION_DECL_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not _is_candidate_symbol_name(symbol_name):
            continue
        entries.append(
            {
                "offset": match.start(),
                "symbol_name": symbol_name,
                "symbol_kind": "function",
                "signature": str(match.group(0) or "").strip(),
                "qualified_names": (symbol_name,),
            }
        )
    entries.sort(key=lambda entry: (int(entry["offset"]), str(entry["symbol_name"])))
    return entries


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    stripped_text = strip_comments(text)
    declarations = _declaration_entries(stripped_text)
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    final_line = len(stripped_text.splitlines()) if stripped_text else 1
    for index, declaration in enumerate(declarations):
        line_no = _line_number(stripped_text, int(declaration["offset"]))
        symbol_name = str(declaration["symbol_name"])
        symbol_kind = str(declaration["symbol_kind"])
        symbol_key = (symbol_kind, symbol_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        end_line = final_line
        if index + 1 < len(declarations):
            next_line = _line_number(stripped_text, int(declarations[index + 1]["offset"]))
            end_line = max(line_no, next_line - 1)
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
                "end_line": end_line,
                "signature": str(declaration["signature"]),
                "qualified_names": tuple(
                    alias for alias in declaration["qualified_names"] if alias
                ),
            }
        )
    return symbol_entries


def resolve_import(
    import_target: str,
    *,
    current_file: str,
    module_index: dict[str, str],
) -> str | None:
    normalized_target = normalize_import_target(import_target)
    if not normalized_target:
        return None
    target_path = PurePosixPath(normalized_target)
    candidate_keys: list[str] = []
    if normalized_target.startswith("."):
        current_dir = PurePosixPath(current_file).parent
        resolved_relative = _normalize_repository_relative_path(
            str(current_dir / normalized_target)
        )
        if resolved_relative:
            candidate_keys.append(resolved_relative)
            if PurePosixPath(resolved_relative).suffix.lower() not in _KNOWN_SOLIDITY_SUFFIXES:
                candidate_keys.append(f"{resolved_relative}.sol")
    candidate_keys.append(normalized_target)
    if target_path.suffix.lower() not in _KNOWN_SOLIDITY_SUFFIXES:
        candidate_keys.append(f"{normalized_target}.sol")
    candidate_keys.append(str(target_path.with_suffix("")))
    seen_keys: set[str] = set()
    for candidate_key in candidate_keys:
        normalized_key = _normalize_repository_relative_path(candidate_key)
        if not normalized_key or normalized_key in seen_keys:
            continue
        seen_keys.add(normalized_key)
        direct_match = module_index.get(normalized_key)
        if direct_match is not None and direct_match != current_file:
            return direct_match
    suffix_candidates: list[str] = []
    for candidate_key in candidate_keys:
        normalized_key = _normalize_repository_relative_path(candidate_key)
        if not normalized_key:
            continue
        suffix_candidates.append(normalized_key)
        suffix_candidates.append(PurePosixPath(normalized_key).name)
    for candidate_suffix in suffix_candidates:
        for alias, file_path_value in module_index.items():
            lowered_alias = alias.lower()
            lowered_suffix = candidate_suffix.lower()
            if lowered_alias == lowered_suffix or lowered_alias.endswith(
                f"/{lowered_suffix}"
            ):
                if file_path_value != current_file:
                    return file_path_value
    return None
