from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Dependency

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

_KNOWN_RPG_SUFFIXES = frozenset(
    {
        ".rpg",
        ".rpgle",
        ".sqlrpg",
        ".sqlrpgle",
        ".rpginc",
        ".rpgleinc",
    }
)
_RPG_INCLUDE_SUFFIXES = frozenset({".rpginc", ".rpgleinc"})
_RPG_OBJECT_SUFFIXES = (".pgm", ".srvpgm", ".module", ".servicepgm")
_RPG_SOURCE_ROOTS = (
    "qrpglesrc",
    "qrpgsrc",
    "qsqlsrc",
    "qprotosrc",
    "rpglesrc",
    "rpgsrc",
    "rpgleinc",
    "rpginc",
    "includes",
    "include",
    "programs",
    "src",
    "source",
    "sources",
)
_DCL_PROC_RE = re.compile(
    r"^\s*dcl-proc\s+(?P<name>[A-Za-z_][A-Za-z0-9_@$#-]*)\b",
    re.IGNORECASE,
)
_FREE_PI_RE = re.compile(
    r"^\s*dcl-pi\s+(?P<name>\*n|[A-Za-z_][A-Za-z0-9_@$#-]*)\b"
    r"(?:.*?\bextpgm\s*\(\s*['\"](?P<target>[^'\"]+)['\"]\s*\))?",
    re.IGNORECASE,
)
_FIXED_PI_RE = re.compile(
    r"^\s*d\s+(?P<name>\*n|[A-Za-z_][A-Za-z0-9_@$#-]*)\s+pi\b"
    r"(?:.*?\bextpgm\s*\(\s*['\"](?P<target>[^'\"]+)['\"]\s*\))?",
    re.IGNORECASE,
)
_FIXED_PROC_BEGIN_RE = re.compile(
    r"^\s*[Pp]\s*(?P<name>[A-Za-z_][A-Za-z0-9_@$#-]*)\s+[Bb]\b"
)
_FREE_BEGSR_RE = re.compile(
    r"^\s*begsr\s+(?P<name>\*?[A-Za-z_][A-Za-z0-9_@$#-]*)\b",
    re.IGNORECASE,
)
_INCLUDE_RE = re.compile(
    r"^\s*/(?:copy|include)\s+(?P<target>[^;\r\n]+)",
    re.IGNORECASE,
)
_EXTERNAL_INTERFACE_RE = re.compile(
    r"^\s*(?:"
    r"dcl-(?P<free_kind>pr|pi)\s+"
    r"(?P<free_name>\*n|[A-Za-z_][A-Za-z0-9_@$#-]*)\b"
    r"|d\s+"
    r"(?P<fixed_name>\*n|[A-Za-z_][A-Za-z0-9_@$#-]*)\s+"
    r"(?P<fixed_kind>pr|pi)\b"
    r").*?\bext(?P<external_kind>pgm|proc)\s*"
    r"\(\s*['\"](?P<target>[^'\"]+)['\"]\s*\)",
    re.IGNORECASE,
)
_UNQUALIFIED_CALL_RE = re.compile(
    r"(?<![\w.%])(?P<name>[A-Za-z_][A-Za-z0-9_@$#-]*)\s*(?=\()",
    re.IGNORECASE,
)
_CALLP_RE = re.compile(
    r"\bcallp\s+(?P<name>[A-Za-z_][A-Za-z0-9_@$#-]*)\b",
    re.IGNORECASE,
)
_EXSR_RE = re.compile(
    r"\bexsr\s+(?P<name>\*?[A-Za-z_][A-Za-z0-9_@$#-]*)\b",
    re.IGNORECASE,
)
_RPG_HINT_PATTERNS = (
    re.compile(r"\bdcl-proc\b", re.IGNORECASE),
    re.compile(r"\bdcl-pr\b", re.IGNORECASE),
    re.compile(r"\bctl-opt\b", re.IGNORECASE),
    re.compile(r"^\s*/(?:copy|include)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"\bext(?:pgm|proc)\s*\(", re.IGNORECASE),
    re.compile(r"\bbegsr\b", re.IGNORECASE),
    re.compile(r"\bexsr\b", re.IGNORECASE),
    re.compile(r"^\s*[Pp]\s*[A-Za-z_][A-Za-z0-9_@$#-]*\s+[Bb]\b", re.MULTILINE),
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "begsr",
        "callp",
        "chain",
        "clear",
        "close",
        "ctl-opt",
        "data-gen",
        "data-into",
        "dcl-c",
        "dcl-ds",
        "dcl-f",
        "dcl-pi",
        "dcl-pr",
        "dcl-proc",
        "dcl-s",
        "dow",
        "dou",
        "else",
        "elseif",
        "enddo",
        "endif",
        "endmon",
        "end-pi",
        "end-pr",
        "end-proc",
        "endsl",
        "endsr",
        "eof",
        "eval",
        "exfmt",
        "exec",
        "exsr",
        "extpgm",
        "extproc",
        "for",
        "if",
        "leave",
        "monitor",
        "not",
        "on-error",
        "open",
        "or",
        "other",
        "read",
        "reade",
        "return",
        "select",
        "setll",
        "update",
        "when",
        "write",
    }
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


def _strip_inline_comment(raw_line: str) -> str:
    if len(raw_line) > 6 and raw_line[6] == "*":
        return ""
    stripped_line = raw_line.lstrip()
    if stripped_line.startswith("//"):
        return ""
    chars: list[str] = []
    index = 0
    in_quote = False
    while index < len(raw_line):
        character = raw_line[index]
        next_character = raw_line[index + 1] if index + 1 < len(raw_line) else ""
        if character == "'":
            chars.append(character)
            if in_quote and next_character == "'":
                chars.append(next_character)
                index += 2
                continue
            in_quote = not in_quote
            index += 1
            continue
        if character == "/" and next_character == "/" and not in_quote:
            break
        chars.append(character)
        index += 1
    return "".join(chars)


def strip_comments(text: str) -> str:
    return "\n".join(_strip_inline_comment(line) for line in text.splitlines())


def normalize_target(raw_target: str) -> str:
    return _normalize_repository_relative_path(
        str(raw_target or "").strip().strip(";:,").strip().strip("'\"")
    )


def normalize_symbol_name(raw_name: str) -> str:
    return str(raw_name or "").strip().strip(";:,").strip().strip("'\"")


def _canonical_symbol_name(raw_name: str) -> str:
    return normalize_symbol_name(raw_name).lower()


def _strip_rpg_suffix(raw_name: str) -> str:
    value = str(raw_name or "")
    lower_value = value.lower()
    for suffix in sorted(_KNOWN_RPG_SUFFIXES, key=len, reverse=True):
        if lower_value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def _strip_object_suffix(raw_name: str) -> str:
    value = str(raw_name or "")
    lower_value = value.lower()
    for suffix in _RPG_OBJECT_SUFFIXES:
        if lower_value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def _object_name_from_path(path: PurePosixPath) -> str:
    return normalize_symbol_name(_strip_object_suffix(_strip_rpg_suffix(path.name)))


def _target_leaf_name(raw_target: str) -> str:
    normalized_target = normalize_target(raw_target)
    if not normalized_target:
        return ""
    leaf_name = PurePosixPath(normalized_target).name
    return normalize_symbol_name(_strip_object_suffix(_strip_rpg_suffix(leaf_name)))


def _ordered_names(*names: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for name in names:
        normalized_name = normalize_symbol_name(name)
        if not normalized_name:
            continue
        for candidate in (normalized_name, normalized_name.lower()):
            if candidate and candidate not in seen:
                seen.add(candidate)
                ordered.append(candidate)
    return tuple(ordered)


def _module_index_get(module_index: dict[str, str], candidate: str) -> str | None:
    normalized_candidate = str(candidate or "").strip()
    if not normalized_candidate:
        return None
    return module_index.get(normalized_candidate) or module_index.get(
        normalized_candidate.lower()
    )


def _relative_target_candidates(*, current_file: str, import_target: str) -> tuple[str, ...]:
    raw_target = str(import_target or "").strip().strip(";:,").strip().strip("'\"")
    normalized_target = normalize_target(raw_target)
    if not normalized_target:
        return ()
    current_parent = PurePosixPath(current_file).parent
    candidates: list[str] = []
    if "/" in raw_target or "\\" in raw_target or raw_target.startswith("."):
        resolved_relative = _normalize_repository_relative_path(str(current_parent / raw_target))
        if resolved_relative:
            candidates.append(resolved_relative)
            candidates.append(_strip_rpg_suffix(resolved_relative))
            candidates.append(_strip_object_suffix(_strip_rpg_suffix(resolved_relative)))
    candidates.append(normalized_target)
    candidates.append(_strip_rpg_suffix(normalized_target))
    candidates.append(_strip_object_suffix(_strip_rpg_suffix(normalized_target)))
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate))


def resolve_import(
    import_target: str,
    *,
    current_file: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    relative_candidates = list(
        _relative_target_candidates(current_file=current_file, import_target=import_target)
    )
    relative_candidates.extend(
        value
        for value in (
            _target_leaf_name(import_target),
            _strip_object_suffix(_strip_rpg_suffix(normalize_target(import_target))),
        )
        if value
    )
    normalized_candidates = [
        candidate for candidate in dict.fromkeys(relative_candidates) if candidate
    ]
    for candidate in normalized_candidates:
        direct_match = _module_index_get(module_index, candidate)
        if direct_match is not None:
            return direct_match
    suffixes: list[str] = []
    for candidate in normalized_candidates:
        lower_candidate = candidate.lower()
        suffixes.extend(
            [
                f"{lower_candidate}.rpg",
                f"{lower_candidate}.rpgle",
                f"{lower_candidate}.sqlrpg",
                f"{lower_candidate}.sqlrpgle",
                f"{lower_candidate}.rpginc",
                f"{lower_candidate}.rpgleinc",
            ]
        )
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(dict.fromkeys(suffixes)),
    )


def _fixed_operation_target(raw_line: str, *, operation: str) -> str:
    tokens = raw_line.strip().split()
    if not tokens:
        return ""
    lowered_tokens = [token.lower() for token in tokens]
    if operation not in lowered_tokens:
        return ""
    operation_index = lowered_tokens.index(operation)
    if operation == "begsr":
        if operation_index <= 0:
            return ""
        candidate = tokens[operation_index - 1]
    else:
        if operation_index + 1 >= len(tokens):
            return ""
        candidate = tokens[operation_index + 1]
    if candidate.lower() == "c":
        return ""
    return normalize_symbol_name(candidate)


def _pi_symbol_name(raw_name: str, raw_target: str) -> str:
    normalized_name = normalize_symbol_name(raw_name)
    if normalized_name and normalized_name.lower() != "*n":
        return normalized_name
    return _target_leaf_name(raw_target)


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() in _RPG_INCLUDE_SUFFIXES:
        return []
    stripped_lines = strip_comments(text).splitlines()
    final_line = len(stripped_lines) if stripped_lines else 1
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()

    for line_no, raw_line in enumerate(stripped_lines, start=1):
        normalized_line = raw_line.strip()
        if not normalized_line:
            continue
        symbol_kind: str | None = None
        symbol_name = ""

        procedure_match = _DCL_PROC_RE.match(normalized_line)
        if procedure_match is not None:
            symbol_kind = "function"
            symbol_name = normalize_symbol_name(str(procedure_match.group("name") or ""))
        else:
            fixed_proc_match = _FIXED_PROC_BEGIN_RE.match(raw_line)
            if fixed_proc_match is not None:
                symbol_kind = "function"
                symbol_name = normalize_symbol_name(str(fixed_proc_match.group("name") or ""))
            else:
                free_begsr_match = _FREE_BEGSR_RE.match(normalized_line)
                if free_begsr_match is not None:
                    symbol_kind = "function"
                    symbol_name = normalize_symbol_name(str(free_begsr_match.group("name") or ""))
                else:
                    fixed_begsr_name = _fixed_operation_target(raw_line, operation="begsr")
                    if fixed_begsr_name:
                        symbol_kind = "function"
                        symbol_name = fixed_begsr_name
                    else:
                        free_pi_match = _FREE_PI_RE.match(normalized_line)
                        fixed_pi_match = None
                        if free_pi_match is None:
                            fixed_pi_match = _FIXED_PI_RE.match(normalized_line)
                        if free_pi_match is not None or fixed_pi_match is not None:
                            pi_match = free_pi_match or fixed_pi_match
                            symbol_kind = "program"
                            symbol_name = _pi_symbol_name(
                                str(pi_match.group("name") or ""),
                                str(pi_match.group("target") or ""),
                            )

        canonical_name = _canonical_symbol_name(symbol_name)
        if (
            symbol_kind is None
            or not symbol_name
            or symbol_name.startswith("*")
            or canonical_name in _RESERVED_SYMBOL_NAMES
        ):
            continue

        qualified_names = set(_ordered_names(symbol_name))
        symbol_key = (symbol_kind, canonical_name, line_no)
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
                "end_line": final_line,
                "signature": normalized_line,
                "qualified_names": tuple(sorted(qualified_names)),
            }
        )

    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def _path_aliases(path: PurePosixPath) -> set[str]:
    normalized_path = str(path).lower()
    without_suffix = _strip_rpg_suffix(normalized_path).lower()
    aliases = {
        normalized_path,
        without_suffix,
        without_suffix.replace("/", "."),
        path.stem.lower(),
    }
    object_name = _object_name_from_path(path)
    if object_name:
        aliases.add(object_name.lower())
        if without_suffix.endswith(f".{object_name.lower()}"):
            aliases.add(without_suffix[: -(len(object_name) + 1)])
    source_parts = [part.lower() for part in path.parts]
    for source_root in _RPG_SOURCE_ROOTS:
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        derived_parts = list(path.parts[root_index + 1 :])
        if not derived_parts:
            continue
        derived_parts[-1] = _strip_object_suffix(_strip_rpg_suffix(derived_parts[-1]))
        module_path = _normalize_repository_relative_path("/".join(derived_parts)).lower()
        if module_path:
            aliases.add(module_path)
            aliases.add(module_path.replace("/", "."))
            aliases.add(PurePosixPath(module_path).name)
        break
    return {alias for alias in aliases if alias and alias not in {"."}}


def is_probable_rpg_source(*, path: PurePosixPath | Path | str, text: str) -> bool:
    suffix = PurePosixPath(str(path).replace("\\", "/")).suffix.lower()
    if suffix not in _KNOWN_RPG_SUFFIXES:
        return False
    stripped_text = strip_comments(text)
    score = 0
    for pattern in _RPG_HINT_PATTERNS:
        if pattern.search(stripped_text):
            score += 1
    if suffix in _RPG_INCLUDE_SUFFIXES:
        return score >= 1
    return score >= 2


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_RPG_SUFFIXES:
        return set()
    aliases = _path_aliases(path)
    if path.suffix.lower() in _RPG_INCLUDE_SUFFIXES:
        return aliases
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(
            alias
            for alias in symbol_entry["qualified_names"]
            if isinstance(alias, str) and alias
        )
    return {alias for alias in aliases if alias}


def _include_targets_for_line(raw_line: str) -> tuple[str, ...]:
    match = _INCLUDE_RE.match(raw_line.strip())
    if match is None:
        return ()
    target = normalize_target(str(match.group("target") or ""))
    return (target,) if target else ()


def _prototype_bindings_for_line(raw_line: str) -> tuple[dict[str, str], ...]:
    match = _EXTERNAL_INTERFACE_RE.match(raw_line.strip())
    if match is None:
        return ()
    prototype_name = normalize_symbol_name(
        str(match.group("free_name") or match.group("fixed_name") or "")
    )
    external_target = normalize_target(str(match.group("target") or ""))
    if not external_target:
        return ()
    target_leaf = _target_leaf_name(external_target)
    if not target_leaf:
        return ()
    target_names = _ordered_names(prototype_name, target_leaf)
    if not target_names:
        return ()
    return (
        {
            "prototype_name": prototype_name,
            "external_target": external_target,
            "target_leaf": target_leaf,
            "target_names": target_names,
        },
    )


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, dict[str, Any]]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, dict[str, Any]] = {}
    dependency_keys: set[tuple[str | None, tuple[str, ...], str]] = set()

    for line_no, raw_line in enumerate(strip_comments(text).splitlines(), start=1):
        normalized_line = raw_line.strip()
        if not normalized_line:
            continue

        for import_target in _include_targets_for_line(normalized_line):
            target_file = resolve_import(
                import_target,
                current_file=file_path,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            target_leaf = _target_leaf_name(import_target)
            target_names = _ordered_names(target_leaf)
            dependency_key = (target_file, target_names, "imports")
            if dependency_key not in dependency_keys:
                dependency_keys.add(dependency_key)
                dependencies.append(
                    _Dependency(
                        dependency_edge_id=stable_identifier(
                            "dep",
                            {
                                "file_path": file_path,
                                "target": import_target,
                                "line": line_no,
                                "type": "imports",
                            },
                        ),
                        source_file=file_path,
                        target_file=target_file,
                        target_symbol=target_leaf or None,
                        dependency_type="imports",
                    )
                )
            for alias_name in _ordered_names(import_target, target_leaf):
                import_bindings[alias_name.lower()] = {
                    "alias": alias_name,
                    "target_file": target_file,
                    "target_names": target_names,
                }

        for prototype_binding in _prototype_bindings_for_line(normalized_line):
            external_target = str(prototype_binding["external_target"])
            target_file = resolve_import(
                external_target,
                current_file=file_path,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            target_names = tuple(str(name) for name in prototype_binding["target_names"])
            dependency_key = (target_file, target_names, "references")
            if dependency_key not in dependency_keys:
                dependency_keys.add(dependency_key)
                dependencies.append(
                    _Dependency(
                        dependency_edge_id=stable_identifier(
                            "dep",
                            {
                                "file_path": file_path,
                                "target": external_target,
                                "line": line_no,
                                "type": "references",
                            },
                        ),
                        source_file=file_path,
                        target_file=target_file,
                        target_symbol=target_names[0] if target_names else None,
                        dependency_type="references",
                    )
                )
            for alias_name in _ordered_names(
                str(prototype_binding["prototype_name"]),
                str(prototype_binding["target_leaf"]),
                external_target,
            ):
                import_bindings[alias_name.lower()] = {
                    "alias": alias_name,
                    "target_file": target_file,
                    "target_names": target_names,
                }

    return tuple(dependencies), import_bindings


def _reference_target_from_module_index(
    target_name: str,
    *,
    file_path: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    return resolve_import(
        target_name,
        current_file=file_path,
        module_index=module_index,
        resolve_suffix_match=resolve_suffix_match,
    )


def _call_targets(snippet: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen: set[str] = set()
    for match in _UNQUALIFIED_CALL_RE.finditer(snippet):
        target_name = normalize_symbol_name(str(match.group("name") or ""))
        canonical_name = _canonical_symbol_name(target_name)
        if (
            not target_name
            or target_name.startswith("*")
            or canonical_name in _RESERVED_SYMBOL_NAMES
            or canonical_name in seen
        ):
            continue
        seen.add(canonical_name)
        targets.append(target_name)
    for match in _CALLP_RE.finditer(snippet):
        target_name = normalize_symbol_name(str(match.group("name") or ""))
        canonical_name = _canonical_symbol_name(target_name)
        if (
            not target_name
            or target_name.startswith("*")
            or canonical_name in _RESERVED_SYMBOL_NAMES
            or canonical_name in seen
        ):
            continue
        seen.add(canonical_name)
        targets.append(target_name)
    return tuple(targets)


def _exsr_targets(snippet: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen: set[str] = set()
    for match in _EXSR_RE.finditer(snippet):
        target_name = normalize_symbol_name(str(match.group("name") or ""))
        canonical_name = _canonical_symbol_name(target_name)
        if (
            not target_name
            or target_name.startswith("*")
            or canonical_name in _RESERVED_SYMBOL_NAMES
            or canonical_name in seen
        ):
            continue
        seen.add(canonical_name)
        targets.append(target_name)
    for raw_line in snippet.splitlines():
        target_name = _fixed_operation_target(raw_line, operation="exsr")
        canonical_name = _canonical_symbol_name(target_name)
        if (
            not target_name
            or target_name.startswith("*")
            or canonical_name in _RESERVED_SYMBOL_NAMES
            or canonical_name in seen
        ):
            continue
        seen.add(canonical_name)
        targets.append(target_name)
    return tuple(targets)
