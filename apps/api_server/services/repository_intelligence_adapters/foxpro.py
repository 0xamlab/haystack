from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveDirectoryPrefixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

_KNOWN_FOXPRO_SUFFIXES = (".prg",)
_FOXPRO_SOURCE_ROOTS = ("src", "source", "sources", "programs", "prg", "lib", "classes")
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "additive",
        "alias",
        "and",
        "as",
        "case",
        "class",
        "createobject",
        "default",
        "dimension",
        "do",
        "else",
        "elseif",
        "endcase",
        "enddefine",
        "endfunc",
        "endif",
        "endproc",
        "endscan",
        "endtext",
        "endwith",
        "events",
        "false",
        "for",
        "form",
        "function",
        "hidden",
        "if",
        "in",
        "local",
        "lparameters",
        "newobject",
        "not",
        "null",
        "of",
        "or",
        "otherwise",
        "parameters",
        "private",
        "procedure",
        "protected",
        "public",
        "return",
        "scan",
        "set",
        "step",
        "this",
        "thisform",
        "to",
        "true",
        "while",
        "with",
    }
)
_PARAM_MARKER_RE = re.compile(r"\b(?:lparameters|parameters)\b", re.IGNORECASE)
_LOCAL_DECL_RE = re.compile(
    r"^\s*(?:local|private|public|protected|hidden)\s+[A-Za-z_][A-Za-z0-9_]*",
    re.MULTILINE | re.IGNORECASE,
)
DEFINE_CLASS_RE = re.compile(
    r"^\s*define\s+class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+as\s+"
    r"(?P<base>[A-Za-z_][A-Za-z0-9_\.]*)",
    re.MULTILINE | re.IGNORECASE,
)
ENDDEFINE_RE = re.compile(r"^\s*enddefine\b", re.MULTILINE | re.IGNORECASE)
ROUTINE_DECL_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|hidden)\s+)?"
    r"(?P<kind>procedure|function)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
END_ROUTINE_RE = re.compile(r"^\s*end(?:proc|func)\b", re.MULTILINE | re.IGNORECASE)
INCLUDE_RE = re.compile(
    r"^\s*#include\s+[\"<](?P<target>[^\">]+)[\">]",
    re.MULTILINE | re.IGNORECASE,
)
SET_LIBRARY_RE = re.compile(
    r"^\s*set\s+(?P<kind>procedure|classlib)\s+to\s+(?P<body>.+)$",
    re.MULTILINE | re.IGNORECASE,
)
OBJECT_CREATION_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(?:createobject|newobject)\s*\(\s*['\"](?P<type>[^'\"]+)['\"]"
    r"(?:\s*,\s*['\"](?P<library>[^'\"]+)['\"])?",
    re.IGNORECASE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
UNQUALIFIED_CALL_RE = re.compile(
    r"(?<!\.)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b\s*(?=\()",
    re.IGNORECASE,
)
DO_COMMAND_RE = re.compile(
    r"\bdo\s+(?:form\s+)?(?P<target>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
THIS_MARKER_RE = re.compile(r"\b(?:this|thisform)\b", re.IGNORECASE)


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
    stripped_line = raw_line.lstrip()
    if stripped_line.startswith("*"):
        return ""
    if "&&" not in raw_line:
        return raw_line
    if "'" not in raw_line and '"' not in raw_line:
        return raw_line.split("&&", 1)[0]
    chars: list[str] = []
    index = 0
    in_single = False
    in_double = False
    while index < len(raw_line):
        character = raw_line[index]
        next_character = raw_line[index + 1] if index + 1 < len(raw_line) else ""
        if character == "'" and not in_double:
            in_single = not in_single
            chars.append(character)
            index += 1
            continue
        if character == '"' and not in_single:
            in_double = not in_double
            chars.append(character)
            index += 1
            continue
        if character == "&" and next_character == "&" and not in_single and not in_double:
            break
        chars.append(character)
        index += 1
    return "".join(chars)


def strip_comments(text: str) -> str:
    return "\n".join(_strip_inline_comment(line) for line in text.splitlines())


def normalize_target(raw_target: str) -> str:
    normalized = str(raw_target or "").strip().strip(",;").strip()
    normalized = normalized.strip("'\"")
    normalized = re.sub(
        r"\b(?:additive|alias|nosave|protected|public|private)\b",
        "",
        normalized,
        flags=re.IGNORECASE,
    ).strip()
    return _normalize_repository_relative_path(normalized) or normalized


def normalize_symbol_name(raw_name: str) -> str:
    return str(raw_name or "").strip().strip("'\"")


def _canonical_symbol_name(raw_name: str) -> str:
    return normalize_symbol_name(raw_name).lower()


def _path_aliases(path: PurePosixPath) -> set[str]:
    without_suffix = str(path.with_suffix("")).lower()
    aliases = {
        str(path).lower(),
        without_suffix,
        without_suffix.replace("/", "."),
        path.stem.lower(),
    }
    source_parts = list(path.parts)
    for source_root in _FOXPRO_SOURCE_ROOTS:
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        derived_parts = list(source_parts[root_index + 1 :])
        if not derived_parts:
            continue
        derived_parts[-1] = PurePosixPath(derived_parts[-1]).stem
        module_path = "/".join(part for part in derived_parts if part).lower()
        if module_path:
            aliases.add(module_path)
            aliases.add(module_path.replace("/", "."))
        break
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def is_probable_foxpro_source(
    *,
    path: PurePosixPath | Path | str,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    suffix = PurePosixPath(str(path).replace("\\", "/")).suffix.lower()
    if suffix not in _KNOWN_FOXPRO_SUFFIXES:
        return False
    if not isinstance(stripped_text, str):
        stripped_text = strip_comments(text)
    score = 0
    if DEFINE_CLASS_RE.search(stripped_text):
        score += 3
    if ROUTINE_DECL_RE.search(stripped_text):
        score += 2
    if _PARAM_MARKER_RE.search(stripped_text):
        score += 1
    if _LOCAL_DECL_RE.search(stripped_text):
        score += 1
    if INCLUDE_RE.search(stripped_text):
        score += 1
    if SET_LIBRARY_RE.search(stripped_text):
        score += 2
    if OBJECT_CREATION_RE.search(stripped_text):
        score += 1
    if END_ROUTINE_RE.search(stripped_text) or ENDDEFINE_RE.search(stripped_text):
        score += 1
    if THIS_MARKER_RE.search(stripped_text):
        score += 1
    return score >= 3


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    if not isinstance(stripped_text, str):
        stripped_text = strip_comments(text)
    stripped_lines = stripped_text.splitlines()
    final_line = len(stripped_lines) if stripped_lines else 1
    current_class: str = ""
    file_module = PurePosixPath(file_path).stem.lower()
    for line_no, raw_line in enumerate(stripped_lines, start=1):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        if ENDDEFINE_RE.match(stripped_line):
            current_class = ""
            continue
        symbol_kind: str | None = None
        symbol_name: str = ""
        qualified_names: set[str] = set()
        class_match = DEFINE_CLASS_RE.match(stripped_line)
        if class_match is not None:
            symbol_kind = "type"
            symbol_name = normalize_symbol_name(str(class_match.group("name") or ""))
            canonical_name = symbol_name.lower()
            current_class = canonical_name
            qualified_names = {canonical_name}
        else:
            routine_match = ROUTINE_DECL_RE.match(stripped_line)
            if routine_match is not None:
                symbol_kind = "function"
                symbol_name = normalize_symbol_name(str(routine_match.group("name") or ""))
                canonical_name = symbol_name.lower()
                qualified_names = {canonical_name}
                if file_module:
                    qualified_names.add(f"{file_module}.{canonical_name}")
                if current_class:
                    qualified_names.add(f"{current_class}.{canonical_name}")
            else:
                continue
        canonical_name = symbol_name.lower()
        if not symbol_name or canonical_name in RESERVED_SYMBOL_NAMES:
            continue
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
                "end_line": line_no,
                "signature": stripped_line,
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


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_FOXPRO_SUFFIXES:
        return set()
    aliases = _path_aliases(path)
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return aliases
    stripped_text = strip_comments(text)
    if not is_probable_foxpro_source(path=path, text=text, stripped_text=stripped_text):
        return aliases
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    ):
        aliases.update(
            str(alias).lower()
            for alias in symbol_entry.get("qualified_names", ())
            if alias
        )
    return aliases


def resolve_target(
    reference_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
    resolve_directory_prefix_match: ResolveDirectoryPrefixMatch,
) -> str | None:
    normalized_target = normalize_target(reference_target).lower()
    if not normalized_target or normalized_target in RESERVED_SYMBOL_NAMES:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    normalized_path = PurePosixPath(normalized_target)
    stem = normalized_path.stem.lower() if normalized_path.stem else normalized_target
    normalized_without_suffix = str(normalized_path.with_suffix("")).lower()
    direct_stem_match = module_index.get(stem)
    if direct_stem_match is not None:
        return direct_stem_match
    suffix_candidates = [
        normalized_target,
        normalized_without_suffix,
        normalized_without_suffix.replace("/", "."),
        stem,
        f"{normalized_without_suffix}.prg",
        f"{normalized_without_suffix}.h",
        f"{stem}.prg",
        f"{stem}.h",
    ]
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=suffix_candidates,
    )
    if resolved is not None:
        return resolved
    return resolve_directory_prefix_match(
        module_index=module_index,
        prefixes=[
            normalized_without_suffix,
            f"src/{normalized_without_suffix}",
            f"source/{normalized_without_suffix}",
            f"sources/{normalized_without_suffix}",
            f"programs/{normalized_without_suffix}",
            f"prg/{normalized_without_suffix}",
            stem,
            f"src/{stem}",
            f"source/{stem}",
            f"sources/{stem}",
            f"programs/{stem}",
            f"prg/{stem}",
        ],
    )


def _iter_library_targets(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[int, str], ...]:
    targets: list[tuple[int, str]] = []
    if not isinstance(stripped_text, str):
        stripped_text = strip_comments(text)
    for match in SET_LIBRARY_RE.finditer(stripped_text):
        body = str(match.group("body") or "")
        for raw_segment in body.split(","):
            target = normalize_target(raw_segment)
            if not target:
                continue
            target = target.split(None, 1)[0].strip()
            if target:
                targets.append((match.start(), target))
    return tuple(targets)


def _object_bindings(
    text: str,
    *,
    resolve_target_fn: Callable[[str], str | None],
    stripped_text: str | None = None,
) -> dict[str, dict[str, str]]:
    bindings: dict[str, dict[str, str]] = {}
    if not isinstance(stripped_text, str):
        stripped_text = strip_comments(text)
    for match in OBJECT_CREATION_RE.finditer(stripped_text):
        alias = _canonical_symbol_name(str(match.group("alias") or ""))
        target_name = normalize_symbol_name(str(match.group("type") or ""))
        library_target = normalize_target(str(match.group("library") or ""))
        if not alias or not target_name or alias in RESERVED_SYMBOL_NAMES:
            continue
        target_file = None
        if library_target:
            target_file = resolve_target_fn(library_target)
        if target_file is None:
            target_file = resolve_target_fn(target_name)
        if target_file is None:
            continue
        bindings[alias] = {
            "target_file": target_file,
            "target_name": target_name.rsplit(".", 1)[-1],
        }
    return bindings


def _append_dependency(
    dependency_entries: list[dict[str, Any]],
    dependency_keys: set[tuple[str | None, str, str]],
    *,
    file_path: str,
    target_file: str | None,
    target_symbol: str,
    dependency_type: str,
    stable_identifier: StableIdentifier,
    position: int,
) -> None:
    normalized_target_symbol = normalize_symbol_name(target_symbol)
    canonical_target_symbol = normalized_target_symbol.lower()
    if not canonical_target_symbol:
        return
    dependency_key = (target_file, canonical_target_symbol, dependency_type)
    if dependency_key in dependency_keys:
        return
    dependency_keys.add(dependency_key)
    dependency_entries.append(
        {
            "dependency_edge_id": stable_identifier(
                "dep",
                {
                    "file_path": file_path,
                    "target": canonical_target_symbol,
                    "line": position,
                    "type": dependency_type,
                },
            ),
            "source_file": file_path,
            "target_file": target_file,
            "target_symbol": normalized_target_symbol,
            "dependency_type": dependency_type,
        }
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_target_fn: Callable[[str], str | None],
    stripped_text: str | None = None,
    symbol_entries: list[dict[str, Any]] | None = None,
    object_bindings: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[str, Any], ...]:
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    if not isinstance(stripped_text, str):
        stripped_text = strip_comments(text)
    if symbol_entries is None:
        symbol_entries = collect_symbol_entries(
            text,
            file_path=file_path,
            stable_identifier=stable_identifier,
            stripped_text=stripped_text,
        )
    local_symbol_names = {str(entry["symbol_name"]).lower() for entry in symbol_entries}
    if object_bindings is None:
        object_bindings = _object_bindings(
            text,
            resolve_target_fn=resolve_target_fn,
            stripped_text=stripped_text,
        )

    for match in INCLUDE_RE.finditer(stripped_text):
        import_target = normalize_target(str(match.group("target") or ""))
        if not import_target:
            continue
        _append_dependency(
            dependency_entries,
            dependency_keys,
            file_path=file_path,
            target_file=resolve_target_fn(import_target),
            target_symbol=PurePosixPath(import_target).name or import_target,
            dependency_type="imports",
            stable_identifier=stable_identifier,
            position=match.start(),
        )
    for position, import_target in _iter_library_targets(text, stripped_text=stripped_text):
        leaf_name = PurePosixPath(import_target).stem or PurePosixPath(import_target).name
        _append_dependency(
            dependency_entries,
            dependency_keys,
            file_path=file_path,
            target_file=resolve_target_fn(import_target),
            target_symbol=leaf_name or import_target,
            dependency_type="imports",
            stable_identifier=stable_identifier,
            position=position,
        )
    for match in OBJECT_CREATION_RE.finditer(stripped_text):
        target_name = normalize_symbol_name(str(match.group("type") or ""))
        if not target_name or target_name.lower() in local_symbol_names:
            continue
        library_target = normalize_target(str(match.group("library") or ""))
        target_file = resolve_target_fn(library_target or target_name)
        if target_file is None or target_file == file_path:
            continue
        _append_dependency(
            dependency_entries,
            dependency_keys,
            file_path=file_path,
            target_file=target_file,
            target_symbol=target_name,
            dependency_type="references",
            stable_identifier=stable_identifier,
            position=match.start(),
        )
    for match in DO_COMMAND_RE.finditer(stripped_text):
        target_name = normalize_symbol_name(str(match.group("target") or ""))
        canonical_target_name = target_name.lower()
        if not target_name or canonical_target_name in RESERVED_SYMBOL_NAMES:
            continue
        target_file = resolve_target_fn(target_name)
        if target_file is None or target_file == file_path:
            continue
        _append_dependency(
            dependency_entries,
            dependency_keys,
            file_path=file_path,
            target_file=target_file,
            target_symbol=target_name,
            dependency_type="references",
            stable_identifier=stable_identifier,
            position=match.start(),
        )
    for match in QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        alias = _canonical_symbol_name(str(match.group("alias") or ""))
        target_name = normalize_symbol_name(str(match.group("name") or ""))
        if not alias or not target_name or alias in RESERVED_SYMBOL_NAMES:
            continue
        if alias in object_bindings:
            target_file = str(object_bindings[alias]["target_file"])
        else:
            target_file = resolve_target_fn(alias)
        if target_file is None or target_file == file_path:
            continue
        _append_dependency(
            dependency_entries,
            dependency_keys,
            file_path=file_path,
            target_file=target_file,
            target_symbol=target_name,
            dependency_type="references",
            stable_identifier=stable_identifier,
            position=match.start(),
        )
    for match in UNQUALIFIED_CALL_RE.finditer(stripped_text):
        target_name = normalize_symbol_name(str(match.group("name") or ""))
        canonical_target_name = target_name.lower()
        if (
            not target_name
            or canonical_target_name in RESERVED_SYMBOL_NAMES
            or canonical_target_name in local_symbol_names
        ):
            continue
        target_file = resolve_target_fn(target_name)
        if target_file is None or target_file == file_path:
            continue
        _append_dependency(
            dependency_entries,
            dependency_keys,
            file_path=file_path,
            target_file=target_file,
            target_symbol=target_name,
            dependency_type="references",
            stable_identifier=stable_identifier,
            position=match.start(),
        )
    return tuple(dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_target_fn: Callable[[str], str | None],
) -> tuple[
    list[dict[str, Any]],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    stripped_text = strip_comments(text)
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    object_bindings = _object_bindings(
        text,
        resolve_target_fn=resolve_target_fn,
        stripped_text=stripped_text,
    )
    dependency_entries = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_target_fn=resolve_target_fn,
        stripped_text=stripped_text,
        symbol_entries=symbol_entries,
        object_bindings=object_bindings,
    )
    local_symbol_names = {str(entry["symbol_name"]).lower() for entry in symbol_entries}
    stripped_lines = stripped_text.splitlines()
    reference_candidates: dict[str, dict[str, Any]] = {}
    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_id = str(symbol_entry["symbol_id"])
        symbol_name = str(symbol_entry["symbol_name"]).lower()
        snippet = "\n".join(stripped_lines[start_line - 1 : end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias = _canonical_symbol_name(str(match.group("alias") or ""))
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            if not alias or not target_name or alias in RESERVED_SYMBOL_NAMES:
                continue
            if alias in object_bindings:
                target_file = str(object_bindings[alias]["target_file"])
            else:
                target_file = resolve_target_fn(alias)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": symbol_id,
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "reference_type": "references_symbol",
                },
            )
        for match in DO_COMMAND_RE.finditer(snippet):
            target_name = normalize_symbol_name(str(match.group("target") or ""))
            canonical_target_name = target_name.lower()
            if (
                not target_name
                or canonical_target_name in RESERVED_SYMBOL_NAMES
                or canonical_target_name == symbol_name
            ):
                continue
            target_file = resolve_target_fn(target_name)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": symbol_id,
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "reference_type": "references_symbol",
                },
            )
        for match in UNQUALIFIED_CALL_RE.finditer(snippet):
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            canonical_target_name = target_name.lower()
            if (
                not target_name
                or canonical_target_name in RESERVED_SYMBOL_NAMES
                or canonical_target_name in local_symbol_names
                or canonical_target_name == symbol_name
            ):
                continue
            target_file = resolve_target_fn(target_name)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": symbol_id,
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "reference_type": "references_symbol",
                },
            )
    return (
        symbol_entries,
        dependency_entries,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
