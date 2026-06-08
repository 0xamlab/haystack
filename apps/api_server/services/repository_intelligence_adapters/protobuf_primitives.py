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

PROTOBUF_SUFFIXES = frozenset({".proto"})
PROTOBUF_CONFIG_BASENAMES = frozenset({"buf.gen.yaml", "buf.work.yaml", "buf.yaml"})
_COMMON_MODULE_ROOTS = frozenset(
    {"api", "apis", "buf", "proto", "protos", "schema", "schemas", "src"}
)
_PACKAGE_RE = re.compile(r"(?m)^\s*package\s+(?P<name>[A-Za-z_][A-Za-z0-9_.]*)\s*;")
_IMPORT_RE = re.compile(
    r'(?m)^\s*import\s+(?:weak\s+|public\s+)?(?P<target>"[^"\r\n]+")\s*;'
)
_TYPE_DECL_RE = re.compile(
    r"(?m)^\s*(?P<kind>message|enum|service)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_RPC_RE = re.compile(
    r"(?m)^\s*rpc\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\(\s*(?:stream\s+)?(?P<request>[A-Za-z_][A-Za-z0-9_.]*)\s*\)\s*"
    r"returns\s*\(\s*(?:stream\s+)?(?P<response>[A-Za-z_][A-Za-z0-9_.]*)\s*\)"
)
_FIELD_RE = re.compile(
    r"(?m)^\s*(?:optional|required|repeated)\s+"
    r"(?P<type>[A-Za-z_][A-Za-z0-9_.]*)\s+[A-Za-z_][A-Za-z0-9_]*\s*="
)
_BARE_FIELD_RE = re.compile(
    r"(?m)^\s*(?P<type>[A-Za-z_][A-Za-z0-9_.]*)\s+[A-Za-z_][A-Za-z0-9_]*\s*="
)
_MAP_FIELD_RE = re.compile(
    r"(?m)^\s*map\s*<\s*[^,>]+\s*,\s*(?P<value>[A-Za-z_][A-Za-z0-9_.]*)\s*>\s+"
    r"[A-Za-z_][A-Za-z0-9_]*\s*="
)
_CONFIG_MARKER_RE = re.compile(
    r"(?m)^\s*(?:version|modules|deps|plugins|lint|breaking|managed)\s*:"
)
_PROTO_SOURCE_MARKER_RE = re.compile(
    r"(?m)^\s*(?:syntax\s*=|package\s+|import\s+|message\s+|enum\s+|service\s+|rpc\s+)"
)
_RESERVED_TYPE_NAMES = frozenset(
    {
        "bool",
        "bytes",
        "double",
        "fixed32",
        "fixed64",
        "float",
        "group",
        "int32",
        "int64",
        "map",
        "oneof",
        "optional",
        "repeated",
        "required",
        "sfixed32",
        "sfixed64",
        "sint32",
        "sint64",
        "stream",
        "string",
        "uint32",
        "uint64",
    }
)


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    characters: list[str] = []
    index = 0
    in_string = False
    in_block_comment = False
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        previous_character = text[index - 1] if index > 0 else ""
        if in_block_comment:
            if character == "*" and next_character == "/":
                in_block_comment = False
                index += 2
                continue
            if character == "\n":
                characters.append("\n")
            index += 1
            continue
        if in_string:
            characters.append(character)
            if character == '"' and previous_character != "\\":
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            characters.append(character)
            index += 1
            continue
        if character == "/" and next_character == "/":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        if character == "/" and next_character == "*":
            in_block_comment = True
            index += 2
            continue
        characters.append(character)
        index += 1
    return "".join(characters)


def has_protobuf_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in PROTOBUF_SUFFIXES
        or normalized_path.name.lower() in PROTOBUF_CONFIG_BASENAMES
    )


def is_probable_protobuf_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if (
        normalized_path.suffix.lower() not in PROTOBUF_SUFFIXES
        or not text
        or _looks_binaryish(text)
    ):
        return False
    return bool(_PROTO_SOURCE_MARKER_RE.search(strip_comments(text)))


def is_probable_protobuf_config(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.name.lower() not in PROTOBUF_CONFIG_BASENAMES or not text:
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_CONFIG_MARKER_RE.search(stripped_text))


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").lstrip(".")


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


def package_name_from_text(text: str) -> str | None:
    match = _PACKAGE_RE.search(strip_comments(text))
    if match is None:
        return None
    package_name = normalize_identifier(str(match.group("name") or ""))
    return package_name or None


def module_name_from_path(file_path: str, *, package_name: str | None = None) -> str:
    if package_name:
        return package_name
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def _normalize_import_target(raw_target: str) -> str:
    normalized_target = normalize_identifier(raw_target)
    if not normalized_target:
        return ""
    normalized_target = _normalize_repository_relative_path(normalized_target)
    if not normalized_target:
        return ""
    if PurePosixPath(normalized_target).suffix.lower() != ".proto":
        normalized_target = f"{normalized_target}.proto"
    return normalized_target


def iter_import_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        target = _normalize_import_target(str(match.group("target") or ""))
        if not target:
            continue
        item = (target, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _TYPE_DECL_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        symbol_kind = normalize_identifier(str(match.group("kind") or ""))
        if not symbol_name or not symbol_kind:
            continue
        item = (symbol_name, symbol_kind, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    for match in _RPC_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name:
            continue
        item = (symbol_name, "rpc", _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def _normalize_type_name(raw_type: str) -> str:
    return normalize_identifier(raw_type).removeprefix(".")


def _split_qualified_type_name(type_name: str) -> tuple[str | None, str, str | None]:
    normalized_type = _normalize_type_name(type_name)
    if "." not in normalized_type:
        return None, normalized_type, None
    owner, leaf = normalized_type.rsplit(".", 1)
    return owner or None, leaf, normalized_type


def iter_reference_entries(text: str) -> tuple[tuple[str | None, str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str | None, str, str | None, int]] = []
    seen: set[tuple[str | None, str, str | None, int]] = set()

    def _append_reference(raw_type: str, line_number: int) -> None:
        owner, target_name, qualified_name = _split_qualified_type_name(raw_type)
        if not target_name or target_name in _RESERVED_TYPE_NAMES:
            return
        item = (owner, target_name, qualified_name, line_number)
        if item in seen:
            return
        seen.add(item)
        entries.append(item)

    for match in _RPC_RE.finditer(stripped_text):
        line_number = _line_number(stripped_text, match.start())
        _append_reference(str(match.group("request") or ""), line_number)
        _append_reference(str(match.group("response") or ""), line_number)
    for pattern, key in ((_FIELD_RE, "type"), (_BARE_FIELD_RE, "type"), (_MAP_FIELD_RE, "value")):
        for match in pattern.finditer(stripped_text):
            _append_reference(
                str(match.group(key) or ""),
                _line_number(stripped_text, match.start()),
            )
    return tuple(entries)


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    source_symbol_name: str | None = None
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line > line_number:
            break
        source_symbol_name = symbol_name
    return source_symbol_name


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    repository_file = root_path / file_path
    try:
        text = repository_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    package_name = package_name_from_text(text)
    module_name = module_name_from_path(file_path, package_name=package_name)
    normalized_path = _normalize_repository_relative_path(file_path)
    normalized_path_without_suffix = str(PurePosixPath(normalized_path).with_suffix(""))
    dotted_path = normalized_path_without_suffix.replace("/", ".")
    aliases = set(
        _ordered_names(
            normalized_path,
            normalized_path_without_suffix,
            dotted_path,
            module_name,
            module_name.split(".")[-1] if module_name else "",
            PurePosixPath(normalized_path).stem,
        )
    )
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
        aliases.update(
            _ordered_names(
                symbol_name,
                f"{module_name}.{symbol_name}" if module_name else "",
                f"{dotted_path}.{symbol_name}" if dotted_path else "",
            )
        )
    return aliases


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_import_target(import_target)
    if not normalized_target:
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    if current_dir:
        candidate_keys.append(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / normalized_target))
        )
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(f"/{PurePosixPath(candidate).name}" for candidate in candidate_keys),
    )


def _module_alias_bindings_for_target_file(
    *,
    module_index: dict[str, str],
    target_file: str,
) -> tuple[str, ...]:
    aliases = sorted(alias for alias, mapped_file in module_index.items() if mapped_file == target_file)
    if aliases:
        return tuple(aliases)
    module_name = module_name_from_path(target_file)
    return _ordered_names(
        PurePosixPath(target_file).stem,
        module_name,
        module_name.split(".")[-1] if module_name else "",
    )


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_target, _line_number in iter_import_entries(text):
        target_file = resolve_import(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None:
            continue
        for alias_name in _module_alias_bindings_for_target_file(
            module_index=module_index,
            target_file=target_file,
        ):
            bindings.setdefault(
                alias_name,
                _ImportedSymbolBinding(
                    alias=alias_name,
                    target_file=target_file,
                    target_names=(),
                ),
            )
    return bindings


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    stripped_text = strip_comments(text)
    package_name = package_name_from_text(text)
    module_name = module_name_from_path(file_path, package_name=package_name)
    file_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name,
                "symbol_kind": "protobuf",
            },
        ),
        symbol_name=module_name,
        symbol_kind="protobuf",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"protobuf {module_name}",
    )
    symbols: list[_Symbol] = [file_symbol]
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                        "line": line_number,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=None,
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)
