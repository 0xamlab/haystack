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

_KNOWN_SUFFIXES = frozenset({".as"})
_PATH_HINT_PARTS = frozenset({"actionscript", "as3", "flash", "flex"})
_PACKAGE_RE = re.compile(
    r"^\s*package(?:\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*))?\s*\{",
    re.MULTILINE,
)
_IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_*]*)+)\s*;",
    re.MULTILINE,
)
_INCLUDE_RE = re.compile(
    r"^\s*include\s+[\"'](?P<target>[^\"']+)[\"']\s*;",
    re.MULTILINE,
)
_TYPE_DECL_RE = re.compile(
    r"^\s*(?:\[[^\]]+\]\s*)*"
    r"(?:(?:public|internal|private|protected|final|dynamic|static|override|native|mx_internal)\s+)*"
    r"(?P<kind>class|interface)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
    r"(?:\s+extends\s+(?P<extends>[A-Za-z_][A-Za-z0-9_.]*)\b)?"
    r"(?:\s+implements\s+(?P<implements>[A-Za-z_][A-Za-z0-9_.,\s]*)\b)?"
    r"(?=[^{;\n]*[\{;])",
    re.MULTILINE,
)
_FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:\[[^\]]+\]\s*)*"
    r"(?:(?:public|internal|private|protected|final|static|override|native)\s+)*"
    r"function\s+(?:(?:get|set)\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_TYPED_BINDING_RE = re.compile(
    r"\b(?:var|const)\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_.]*)",
)
_NEW_REFERENCE_RE = re.compile(
    r"\bnew\s+(?P<target>[A-Za-z_][A-Za-z0-9_.]*)\s*\(",
)
_QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<owner>[A-Za-z_][A-Za-z0-9_.]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
)
_ACTIONSCRIPT_FEATURE_RE = re.compile(
    r"\bpackage\b"
    r"|\bimport\s+[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_*]*)+\s*;"
    r"|\b(?:public|internal|private|protected)\s+(?:class|interface|function|var|const)\b"
    r"|\bfunction\s+(?:get\s+|set\s+)?[A-Za-z_][A-Za-z0-9_]*\s*\("
    r"|\b(?:var|const)\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*[A-Za-z_][A-Za-z0-9_.<>]*"
    r"|\bimplements\b"
    r"|\bextends\b",
    re.IGNORECASE,
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "addchild",
        "else",
        "for",
        "function",
        "if",
        "import",
        "include",
        "new",
        "package",
        "removechild",
        "return",
        "settimeout",
        "super",
        "switch",
        "trace",
        "while",
    }
)
_RESERVED_REFERENCE_OWNERS = frozenset({"super", "this"})


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class _ResolvedBinding:
    alias: str
    target_file: str | None
    target_name: str


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


@lru_cache(maxsize=256)
def _strip_comments_cached(text: str) -> str:
    return _strip_comments_uncached(text)


def strip_comments(text: str) -> str:
    return _strip_comments_cached(text)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        normalized = str(raw_value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _package_name(text: str) -> str:
    match = _PACKAGE_RE.search(text)
    if match is None:
        return ""
    return str(match.group("name") or "").strip()


def _qualified_name(*, package_name: str, symbol_name: str) -> str:
    normalized_symbol_name = str(symbol_name or "").strip()
    normalized_package_name = str(package_name or "").strip()
    if not normalized_package_name:
        return normalized_symbol_name
    if not normalized_symbol_name:
        return normalized_package_name
    return f"{normalized_package_name}.{normalized_symbol_name}"


def has_actionscript_path_hints(path: Path | PurePosixPath) -> bool:
    pure_path = PurePosixPath(path)
    if pure_path.suffix.lower() not in _KNOWN_SUFFIXES:
        return False
    lowered_parts = {part.lower() for part in pure_path.parts}
    # Only ActionScript-specific directory hints (flash/flex/actionscript/as3) count.
    # ``main.as`` / ``app.as`` are NOT distinctive — AngelScript projects use the same
    # entrypoint names — so treating them as a hint mis-classified AngelScript (and bare
    # ``.as`` notes) as ActionScript on path alone.
    return bool(lowered_parts & _PATH_HINT_PARTS)


def is_probable_actionscript_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).suffix.lower() not in _KNOWN_SUFFIXES:
        return False
    stripped_text = strip_comments(text)
    if _ACTIONSCRIPT_FEATURE_RE.search(stripped_text):
        return True
    return has_actionscript_path_hints(path)


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


def _matching_brace_end(text: str, brace_offset: int) -> int:
    depth = 0
    string_delim: str | None = None
    escape = False
    for index in range(brace_offset, len(text)):
        character = text[index]
        if string_delim is not None:
            if escape:
                escape = False
                continue
            if character == "\\":
                escape = True
                continue
            if character == string_delim:
                string_delim = None
            continue
        if character in {"'", '"'}:
            string_delim = character
            continue
        if character == "{":
            depth += 1
            continue
        if character != "}":
            continue
        depth -= 1
        if depth == 0:
            return index
    return len(text)


def _split_relation_targets(raw_targets: str) -> tuple[str, ...]:
    values: list[str] = []
    for raw_value in str(raw_targets or "").split(","):
        normalized = str(raw_value or "").strip()
        if not normalized:
            continue
        values.append(normalized)
    return _ordered_names(*values)


def _collect_type_entries(
    *,
    file_path: str,
    text: str,
    package_name: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, Any], ...]:
    entries: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int]] = set()
    for match in _TYPE_DECL_RE.finditer(text):
        kind = str(match.group("kind") or "").strip().lower()
        symbol_name = str(match.group("name") or "").strip()
        if not kind or not symbol_name:
            continue
        start_line = _line_number(text, match.start())
        key = (symbol_name.lower(), start_line)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        qualified_name = _qualified_name(package_name=package_name, symbol_name=symbol_name)
        body_start = text.find("{", match.end())
        if body_start == -1:
            end_offset = match.end()
        else:
            end_offset = _matching_brace_end(text, body_start)
        end_line = _line_number(text, end_offset)
        relation_targets = _ordered_names(
            str(match.group("extends") or "").strip(),
            *_split_relation_targets(str(match.group("implements") or "")),
        )
        entries.append(
            {
                "symbol": _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": symbol_name,
                            "line": start_line,
                            "kind": kind,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=kind,
                    start_line=start_line,
                    end_line=end_line,
                    parent_symbol_id=None,
                    signature=qualified_name,
                ),
                "qualified_name": qualified_name,
                "start_offset": match.start(),
                "end_offset": end_offset,
                "relation_targets": relation_targets,
            }
        )
    return tuple(entries)


def _innermost_type_entry(
    *,
    offset: int,
    type_entries: tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
    matched_entries = [
        entry
        for entry in type_entries
        if int(entry["start_offset"]) <= offset <= int(entry["end_offset"])
    ]
    if not matched_entries:
        return None
    return min(
        matched_entries,
        key=lambda entry: int(entry["end_offset"]) - int(entry["start_offset"]),
    )


def _collect_function_entries(
    *,
    file_path: str,
    text: str,
    package_name: str,
    type_entries: tuple[dict[str, Any], ...],
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, Any], ...]:
    entries: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int]] = set()
    for match in _FUNCTION_DECL_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name:
            continue
        start_line = _line_number(text, match.start())
        key = (symbol_name.lower(), start_line)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        containing_type = _innermost_type_entry(offset=match.start(), type_entries=type_entries)
        parent_symbol_id = (
            containing_type["symbol"].symbol_id if containing_type is not None else None
        )
        parent_signature = (
            str(containing_type["qualified_name"])
            if containing_type is not None
            else str(package_name or "").strip()
        )
        qualified_name = _qualified_name(
            package_name=parent_signature,
            symbol_name=symbol_name,
        )
        brace_offset = -1
        terminator_offset = -1
        for candidate_index in range(match.end(), len(text)):
            character = text[candidate_index]
            if character == "{":
                brace_offset = candidate_index
                break
            if character == ";":
                terminator_offset = candidate_index
                break
        if brace_offset != -1:
            end_offset = _matching_brace_end(text, brace_offset)
        elif terminator_offset != -1:
            end_offset = terminator_offset
        else:
            next_line_break = text.find("\n", match.end())
            end_offset = len(text) if next_line_break == -1 else next_line_break
        end_line = _line_number(text, end_offset)
        entries.append(
            {
                "symbol": _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": symbol_name,
                            "line": start_line,
                            "kind": "function",
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind="function",
                    start_line=start_line,
                    end_line=end_line,
                    parent_symbol_id=parent_symbol_id,
                    signature=qualified_name,
                ),
                "parent_qualified_name": parent_signature,
                "start_offset": match.start(),
                "end_offset": end_offset,
            }
        )
    return tuple(entries)


def _resolve_import_target(
    *,
    import_target: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, str | None]:
    normalized_target = str(import_target or "").strip().strip(";")
    if not normalized_target:
        return None, None
    wildcard_package = ""
    if normalized_target.endswith(".*"):
        wildcard_package = normalized_target[: -len(".*")]
    lookup_target = wildcard_package or normalized_target
    for candidate in (
        lookup_target,
        f"class:{lookup_target}",
        f"interface:{lookup_target}",
        f"package:{lookup_target}",
    ):
        resolved = module_index.get(candidate)
        if resolved is not None:
            return resolved, lookup_target.rsplit(".", 1)[-1]
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            lookup_target.replace(".", "/") + ".as",
            "/" + lookup_target.rsplit(".", 1)[-1] + ".as",
        ],
    )
    if resolved is None:
        return None, lookup_target.rsplit(".", 1)[-1]
    return resolved, lookup_target.rsplit(".", 1)[-1]


def _resolve_include_target(
    *,
    current_file: str,
    include_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(include_target or "").strip().strip('"').strip("'")
    if not normalized_target:
        return None
    resolved_path = normalize_repository_relative_path(
        str(PurePosixPath(current_file).parent / normalized_target)
    )
    if not resolved_path:
        return None
    direct_match = module_index.get(resolved_path)
    if direct_match is not None:
        return direct_match
    return resolve_suffix_match(module_index=module_index, suffixes=[resolved_path])


def _import_bindings_for_text(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[dict[str, _ResolvedBinding], tuple[str, ...]]:
    bindings: dict[str, _ResolvedBinding] = {}
    wildcard_packages: list[str] = []
    for match in _IMPORT_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        if import_target.endswith(".*"):
            wildcard_packages.append(import_target[: -len(".*")])
            continue
        target_file, target_name = _resolve_import_target(
            import_target=import_target,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        alias = import_target.rsplit(".", 1)[-1]
        if not alias:
            continue
        bindings.setdefault(
            alias,
            _ResolvedBinding(
                alias=alias,
                target_file=target_file if target_file != file_path else None,
                target_name=target_name or alias,
            ),
        )
    return bindings, _ordered_names(*wildcard_packages)


def _resolve_named_type_target(
    *,
    target_name: str,
    current_file: str,
    current_package_name: str,
    imported_bindings: dict[str, _ResolvedBinding],
    wildcard_packages: tuple[str, ...],
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, str | None]:
    normalized_target = str(target_name or "").strip()
    if not normalized_target:
        return None, None
    if "." in normalized_target:
        target_file, resolved_name = _resolve_import_target(
            import_target=normalized_target,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file == current_file:
            return None, None
        return target_file, resolved_name or normalized_target.rsplit(".", 1)[-1]
    binding = imported_bindings.get(normalized_target)
    if binding is not None:
        if binding.target_file == current_file:
            return None, None
        return binding.target_file, binding.target_name
    qualified_targets = []
    if current_package_name:
        qualified_targets.append(
            _qualified_name(package_name=current_package_name, symbol_name=normalized_target)
        )
    qualified_targets.extend(
        _qualified_name(package_name=package_name, symbol_name=normalized_target)
        for package_name in wildcard_packages
    )
    qualified_targets.extend(
        (normalized_target, f"class:{normalized_target}", f"interface:{normalized_target}")
    )
    for candidate in qualified_targets:
        for lookup_key in (
            candidate,
            f"class:{candidate}",
            f"interface:{candidate}",
        ):
            resolved = module_index.get(lookup_key)
            if resolved is not None:
                if resolved == current_file:
                    return None, None
                return resolved, normalized_target
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"/{normalized_target}.as",
            normalized_target.replace(".", "/") + ".as",
        ],
    )
    if resolved == current_file:
        return None, None
    return resolved, normalized_target


def _typed_variable_bindings(text: str) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for match in _TYPED_BINDING_RE.finditer(text):
        alias = str(match.group("alias") or "").strip().lower()
        target = str(match.group("target") or "").strip()
        if not alias or not target:
            continue
        bindings[alias] = target
    return bindings
