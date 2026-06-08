from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveImport = Callable[[str, dict[str, str]], str | None]
ResolveTarget = Callable[[str, str, dict[str, str]], str | None]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "break",
        "case",
        "catch",
        "classdef",
        "continue",
        "else",
        "elseif",
        "end",
        "enumeration",
        "events",
        "for",
        "function",
        "global",
        "if",
        "import",
        "methods",
        "otherwise",
        "parfor",
        "persistent",
        "properties",
        "return",
        "spmd",
        "switch",
        "try",
        "while",
    }
)
FUNCTION_RE = re.compile(
    r"^\s*function(?:\s+\[[^\]]+\]\s*=\s*|\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*|\s+)?"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
CLASSDEF_RE = re.compile(
    r"^\s*classdef(?:\s*\([^)]+\))?\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\.\*)*)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
BLOCK_RE = re.compile(
    r"^\s*(?:properties|methods|events|enumeration)\b",
    re.IGNORECASE | re.MULTILINE,
)
QUALIFIED_CALL_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*\(",
    re.IGNORECASE,
)
UNQUALIFIED_CALL_RE = re.compile(r"(?<![.@])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
OBJECTIVE_C_MARKER_RE = re.compile(
    r"^\s*#import\b|^\s*@(?:interface|implementation|protocol|property|autoreleasepool|end)\b",
    re.IGNORECASE | re.MULTILINE,
)


def normalize_identifier(raw_name: str) -> str:
    return raw_name.strip().strip("%").strip().lower()


def normalize_import_target(raw_target: str) -> str:
    return normalize_identifier(raw_target.removesuffix(".*"))


def has_matlab_path_hints(path: PurePosixPath | Path | str) -> bool:
    normalized_path = PurePosixPath(str(path).replace("\\", "/"))
    if normalized_path.suffix.lower() != ".m":
        return False
    if normalized_path.name.lower() == "contents.m":
        return True
    return any(part.startswith(("+", "@")) for part in normalized_path.parts[:-1])


def has_objective_c_markers(text: str) -> bool:
    return bool(OBJECTIVE_C_MARKER_RE.search(text))


def _replace_with_spaces(value: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in value)


def strip_comments(text: str) -> str:
    processed_lines: list[str] = []
    in_block_comment = False
    for raw_line in text.splitlines(keepends=True):
        if in_block_comment:
            processed_lines.append(_replace_with_spaces(raw_line))
            if re.match(r"^\s*%}", raw_line):
                in_block_comment = False
            continue
        if re.match(r"^\s*%{", raw_line):
            in_block_comment = True
            processed_lines.append(_replace_with_spaces(raw_line))
            continue
        line_parts: list[str] = []
        in_string = False
        index = 0
        while index < len(raw_line):
            character = raw_line[index]
            if character == "\n":
                line_parts.append("\n")
                index += 1
                continue
            if character == "'":
                if in_string and index + 1 < len(raw_line) and raw_line[index + 1] == "'":
                    line_parts.append("''")
                    index += 2
                    continue
                in_string = not in_string
                line_parts.append(character)
                index += 1
                continue
            if character == "%" and not in_string:
                line_parts.extend(
                    " " if value != "\n" else "\n" for value in raw_line[index:]
                )
                break
            line_parts.append(character)
            index += 1
        processed_lines.append("".join(line_parts))
    return "".join(processed_lines)


def is_probable_matlab_source(*, path: PurePosixPath | Path | str, text: str) -> bool:
    normalized_path = PurePosixPath(str(path).replace("\\", "/"))
    if normalized_path.suffix.lower() != ".m":
        return False
    if has_objective_c_markers(text):
        return False
    if has_matlab_path_hints(normalized_path):
        return True
    stripped_text = strip_comments(text)
    if FUNCTION_RE.search(stripped_text) or CLASSDEF_RE.search(stripped_text):
        return True
    if IMPORT_RE.search(stripped_text) or BLOCK_RE.search(stripped_text):
        return True
    return any(raw_line.lstrip().startswith("%") for raw_line in text.splitlines())


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


def _path_context(file_path: str) -> tuple[tuple[str, ...], str | None, str]:
    path = PurePosixPath(file_path)
    package_parts: list[str] = []
    class_name: str | None = None
    for part in path.parts[:-1]:
        if part.startswith("+") and len(part) > 1:
            package_parts.append(normalize_identifier(part[1:]))
        elif part.startswith("@") and len(part) > 1:
            class_name = normalize_identifier(part[1:])
    return tuple(package_parts), class_name, normalize_identifier(path.stem)


def _path_namespace_prefixes(file_path: str) -> tuple[str, ...]:
    package_parts, class_name, _ = _path_context(file_path)
    prefixes: list[str] = []
    if package_parts:
        prefixes.append(".".join(package_parts))
    if class_name:
        class_prefix_parts = list(package_parts) + [class_name]
        prefixes.append(".".join(class_prefix_parts))
    return tuple(prefix for prefix in prefixes if prefix)


def _derived_path_aliases(file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    package_parts, class_name, stem = _path_context(file_path)
    aliases = {
        file_path.lower(),
        str(path.with_suffix("")).lower(),
        str(path.with_suffix("")).replace("/", ".").lower(),
        stem,
    }
    if path.name.lower() == "contents.m":
        if package_parts:
            aliases.add(".".join(package_parts))
        if class_name:
            aliases.add(".".join([*package_parts, class_name]))
        return {alias for alias in aliases if alias and alias != "."}
    if package_parts:
        aliases.add(".".join([*package_parts, stem]))
    if class_name:
        aliases.add(".".join([*package_parts, class_name]))
        if stem != class_name:
            aliases.add(".".join([*package_parts, class_name, stem]))
    return {alias for alias in aliases if alias and alias != "."}


def _qualified_names_for_symbol(
    *,
    file_path: str,
    symbol_name: str,
    current_class_name: str | None,
) -> set[str]:
    qualified_names = {symbol_name}
    for namespace_prefix in _path_namespace_prefixes(file_path):
        qualified_names.add(f"{namespace_prefix}.{symbol_name}")
    if current_class_name:
        package_parts, _, _ = _path_context(file_path)
        qualified_names.add(current_class_name)
        qualified_names.add(f"{current_class_name}.{symbol_name}")
        if package_parts:
            qualified_names.add(".".join([*package_parts, current_class_name, symbol_name]))
    return {alias for alias in qualified_names if alias}


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    stripped_text = strip_comments(text)
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    current_class_name: str | None = None
    final_line = len(stripped_text.splitlines()) if stripped_text else 1
    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        normalized_line = raw_line.strip()
        if not normalized_line:
            continue
        symbol_kind: str | None = None
        symbol_name: str | None = None
        classdef_match = CLASSDEF_RE.match(normalized_line)
        if classdef_match is not None:
            symbol_kind = "type"
            symbol_name = normalize_identifier(classdef_match.group("name"))
            current_class_name = symbol_name
        else:
            function_match = FUNCTION_RE.match(normalized_line)
            if function_match is not None:
                symbol_kind = "function"
                symbol_name = normalize_identifier(function_match.group("name"))
        if (
            symbol_kind is None
            or symbol_name is None
            or not symbol_name
            or symbol_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        symbol_key = (symbol_kind, symbol_name, line_no)
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
                "qualified_names": tuple(
                    sorted(
                        _qualified_names_for_symbol(
                            file_path=file_path,
                            symbol_name=symbol_name,
                            current_class_name=current_class_name
                            if symbol_kind == "function"
                            else None,
                        )
                        | ({symbol_name} if symbol_kind == "type" else set())
                    )
                ),
            }
        )
    for index, symbol_entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            symbol_entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(symbol_entry["start_line"]),
            )
        else:
            symbol_entry["end_line"] = final_line
    return symbol_entries


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() != ".m":
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    if not is_probable_matlab_source(path=path, text=text):
        return set()
    aliases = _derived_path_aliases(file_path)
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        for alias in symbol_entry["qualified_names"]:
            if isinstance(alias, str) and alias:
                aliases.add(alias)
    return {alias for alias in aliases if alias and alias != "."}


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_import_target(import_target)
    if not normalized_target:
        return None
    for candidate in (normalized_target, normalized_target.rsplit(".", 1)[-1]):
        if not candidate:
            continue
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{normalized_target}.m",
            f"{normalized_target.replace('.', '/')}.m",
        ],
    )


def resolve_target(
    current_file: str,
    reference_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(reference_target)
    if not normalized_target:
        return None
    candidate_names: list[str] = []
    if "." in normalized_target:
        candidate_names.append(normalized_target)
    else:
        for namespace_prefix in _path_namespace_prefixes(current_file):
            candidate_names.append(f"{namespace_prefix}.{normalized_target}")
        candidate_names.append(normalized_target)
    for candidate_name in candidate_names:
        direct_match = module_index.get(candidate_name)
        if direct_match is not None and direct_match != current_file:
            return direct_match
    current_parent = PurePosixPath(current_file).parent
    suffixes: list[str] = []
    for candidate_name in candidate_names:
        suffixes.append(f"{candidate_name}.m")
        suffixes.append(f"{candidate_name.replace('.', '/')}.m")
        if str(current_parent) not in {"", "."} and "." not in normalized_target:
            suffixes.append(f"{current_parent}/{normalized_target}.m")
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=suffixes,
    )
    if resolved is None or resolved == current_file:
        return None
    return resolved


def _extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[tuple[dict[str, Any], ...], dict[str, dict[str, Any]], tuple[str, ...]]:
    stripped_text = strip_comments(text)
    dependencies: list[dict[str, Any]] = []
    import_bindings: dict[str, dict[str, Any]] = {}
    wildcard_prefixes: list[str] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for match in IMPORT_RE.finditer(stripped_text):
        raw_target = str(match.group("target") or "").strip()
        if not raw_target:
            continue
        line_no = stripped_text.count("\n", 0, match.start()) + 1
        is_wildcard = raw_target.endswith(".*")
        normalized_target = normalize_import_target(raw_target)
        if not normalized_target:
            continue
        target_file = resolve_import(normalized_target, module_index)
        dependency_key = (target_file, normalized_target, "imports")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": raw_target,
                            "line": line_no,
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": normalized_target.rsplit(".", 1)[-1],
                    "dependency_type": "imports",
                }
            )
        if is_wildcard:
            wildcard_prefixes.append(normalized_target)
            continue
        alias_name = normalized_target.rsplit(".", 1)[-1]
        if alias_name and alias_name not in RESERVED_SYMBOL_NAMES:
            import_bindings.setdefault(
                alias_name,
                {
                    "alias": alias_name,
                    "target_file": target_file,
                    "target_names": (alias_name,),
                    "target_namespace": normalized_target,
                },
            )
    return tuple(dependencies), import_bindings, tuple(dict.fromkeys(wildcard_prefixes))


def _resolved_unqualified_call_target(
    *,
    current_file: str,
    name: str,
    import_bindings: dict[str, dict[str, Any]],
    wildcard_prefixes: Sequence[str],
    module_index: dict[str, str],
    resolve_target: ResolveTarget,
) -> tuple[str | None, tuple[str, ...]]:
    binding = import_bindings.get(name)
    candidate_targets: list[str] = []
    target_names = (name,)
    if binding is not None:
        candidate_targets.append(str(binding["target_namespace"]))
        if binding["target_names"]:
            target_names = tuple(str(value) for value in binding["target_names"])
    candidate_targets.extend(f"{prefix}.{name}" for prefix in wildcard_prefixes if prefix)
    candidate_targets.append(name)
    for candidate_target in candidate_targets:
        target_file = resolve_target(current_file, candidate_target, module_index)
        if target_file is not None:
            if "." in candidate_target:
                target_names = (candidate_target.rsplit(".", 1)[-1],)
            return target_file, target_names
    return None, target_names


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
    resolve_target: ResolveTarget,
) -> tuple[dict[str, Any], ...]:
    dependencies, import_bindings, wildcard_prefixes = _extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (entry["target_file"], entry["target_symbol"], entry["dependency_type"])
        for entry in dependency_entries
    }
    declared_symbol_names = {
        str(entry["symbol_name"])
        for entry in collect_symbol_entries(
            text,
            file_path=file_path,
            stable_identifier=stable_identifier,
        )
    }
    stripped_text = strip_comments(text)
    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        normalized_line = raw_line.strip()
        if not normalized_line:
            continue
        for match in QUALIFIED_CALL_RE.finditer(normalized_line):
            qualified_target = normalize_identifier(match.group("target"))
            target_file = resolve_target(file_path, qualified_target, module_index)
            target_symbol = qualified_target.rsplit(".", 1)[-1]
            dependency_key = (target_file, target_symbol, "references")
            if (
                target_file is None
                or target_file == file_path
                or target_symbol in RESERVED_SYMBOL_NAMES
                or dependency_key in dependency_keys
            ):
                continue
            dependency_keys.add(dependency_key)
            dependency_entries.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": qualified_target,
                            "line": line_no,
                            "kind": "qualified_call",
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_symbol,
                    "dependency_type": "references",
                }
            )
        for match in UNQUALIFIED_CALL_RE.finditer(normalized_line):
            name = normalize_identifier(match.group("name"))
            if (
                not name
                or name in RESERVED_SYMBOL_NAMES
                or name in declared_symbol_names
            ):
                continue
            target_file, target_names = _resolved_unqualified_call_target(
                current_file=file_path,
                name=name,
                import_bindings=import_bindings,
                wildcard_prefixes=wildcard_prefixes,
                module_index=module_index,
                resolve_target=resolve_target,
            )
            target_symbol = target_names[0] if target_names else name
            dependency_key = (target_file, target_symbol, "references")
            if target_file is None or target_file == file_path or dependency_key in dependency_keys:
                continue
            dependency_keys.add(dependency_key)
            dependency_entries.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": target_symbol,
                            "line": line_no,
                            "kind": "call",
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_symbol,
                    "dependency_type": "references",
                }
            )
    return tuple(dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
    resolve_target: ResolveTarget,
) -> tuple[
    list[dict[str, Any]],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    _, import_bindings, wildcard_prefixes = _extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    stripped_text = strip_comments(text)
    reference_candidates: dict[str, dict[str, Any]] = {}
    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_id = str(symbol_entry["symbol_id"])
        for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
            if line_no < start_line or line_no > end_line:
                continue
            normalized_line = raw_line.strip()
            if not normalized_line:
                continue
            for match in QUALIFIED_CALL_RE.finditer(normalized_line):
                qualified_target = normalize_identifier(match.group("target"))
                target_file = resolve_target(file_path, qualified_target, module_index)
                target_symbol = qualified_target.rsplit(".", 1)[-1]
                if (
                    target_file is None
                    or target_file == file_path
                    or target_symbol in RESERVED_SYMBOL_NAMES
                ):
                    continue
                edge_id = stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol_id,
                        "target_file": target_file,
                        "target_names": (target_symbol,),
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
                        "target_names": (target_symbol,),
                        "reference_type": "references_symbol",
                    },
                )
            for match in UNQUALIFIED_CALL_RE.finditer(normalized_line):
                name = normalize_identifier(match.group("name"))
                if not name or name in RESERVED_SYMBOL_NAMES:
                    continue
                target_file, target_names = _resolved_unqualified_call_target(
                    current_file=file_path,
                    name=name,
                    import_bindings=import_bindings,
                    wildcard_prefixes=wildcard_prefixes,
                    module_index=module_index,
                    resolve_target=resolve_target,
                )
                if target_file is None or target_file == file_path:
                    continue
                edge_id = stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol_id,
                        "target_file": target_file,
                        "target_names": target_names,
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
                        "target_names": target_names,
                        "reference_type": "references_symbol",
                    },
                )
    return (
        symbol_entries,
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
            resolve_target=resolve_target,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
