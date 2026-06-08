from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveDirectoryPrefixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveImport = Callable[[str, dict[str, str]], str | None]

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abort",
        "abs",
        "abstract",
        "accept",
        "access",
        "aliased",
        "all",
        "and",
        "array",
        "at",
        "begin",
        "body",
        "case",
        "constant",
        "declare",
        "delay",
        "delta",
        "digits",
        "do",
        "else",
        "elsif",
        "end",
        "entry",
        "exception",
        "exit",
        "for",
        "function",
        "generic",
        "goto",
        "if",
        "in",
        "interface",
        "is",
        "limited",
        "loop",
        "mod",
        "new",
        "not",
        "null",
        "of",
        "or",
        "others",
        "out",
        "overriding",
        "package",
        "pragma",
        "private",
        "procedure",
        "protected",
        "raise",
        "range",
        "record",
        "rem",
        "renames",
        "requeue",
        "return",
        "reverse",
        "select",
        "separate",
        "subtype",
        "synchronized",
        "tagged",
        "task",
        "terminate",
        "then",
        "type",
        "until",
        "use",
        "when",
        "while",
        "with",
        "xor",
    }
)
BUILTIN_TYPE_NAMES = frozenset(
    {
        "boolean",
        "character",
        "duration",
        "float",
        "integer",
        "long_float",
        "long_integer",
        "natural",
        "positive",
        "string",
        "wide_character",
        "wide_string",
    }
)
IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$")
WITH_RE = re.compile(
    r"^\s*(?:limited\s+|private\s+)*with\s+(?P<body>[^;]+);",
    re.MULTILINE | re.IGNORECASE,
)
USE_RE = re.compile(
    r"^\s*use(?:\s+type)?\s+(?P<body>[^;]+);",
    re.MULTILINE | re.IGNORECASE,
)
PACKAGE_DECL_RE = re.compile(
    r"^\s*(?:generic\s+)?package(?:\s+body)?\s+"
    r"(?P<name>[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*)\s+is\b",
    re.MULTILINE | re.IGNORECASE,
)
SUBPROGRAM_DECL_RE = re.compile(
    r"^\s*(?:overriding\s+|not\s+overriding\s+)?(?:procedure|function)\s+"
    r"(?P<name>[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*)\b",
    re.MULTILINE | re.IGNORECASE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:type|subtype|task\s+type|protected\s+type)\s+"
    r"(?P<name>[A-Za-z][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*)\."
    r"(?P<name>[A-Za-z][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
CALL_REFERENCE_RE = re.compile(
    r"(?<!\.)\b(?P<name>[A-Za-z][A-Za-z0-9_]*)\b(?=\s*(?:\(|;))",
    re.IGNORECASE,
)


def normalize_target(raw_target: str) -> str:
    normalized_target = raw_target.strip()
    normalized_target = re.sub(
        r"^(?:limited|private|all|type)\s+",
        "",
        normalized_target,
        flags=re.IGNORECASE,
    )
    return normalized_target.strip(" .")


def normalize_symbol_name(raw_name: str) -> str:
    normalized_name = raw_name.strip()
    if "." in normalized_name:
        normalized_name = normalized_name.rsplit(".", 1)[-1].strip()
    return normalized_name


def normalize_unit_name(raw_name: str) -> str:
    return normalize_target(raw_name).lower()


def strip_comments(text: str) -> str:
    return re.sub(r"--.*$", "", text, flags=re.MULTILINE)


def _split_identifier_targets(body: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen_targets: set[str] = set()
    for raw_segment in body.split(","):
        candidate = normalize_target(raw_segment)
        normalized_candidate = candidate.lower()
        if (
            not candidate
            or not IDENTIFIER_RE.fullmatch(candidate)
            or normalized_candidate in RESERVED_SYMBOL_NAMES
        ):
            continue
        if normalized_candidate in seen_targets:
            continue
        seen_targets.add(normalized_candidate)
        targets.append(candidate)
    return tuple(targets)


def unit_names(text: str) -> tuple[str, ...]:
    names: list[str] = []
    seen_names: set[str] = set()
    stripped_text = strip_comments(text)
    for pattern in (PACKAGE_DECL_RE, SUBPROGRAM_DECL_RE):
        for match in pattern.finditer(stripped_text):
            unit_name = normalize_unit_name(str(match.group("name") or ""))
            if not unit_name or unit_name in seen_names:
                continue
            seen_names.add(unit_name)
            names.append(unit_name)
    return tuple(names)


def with_targets(text: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen_targets: set[str] = set()
    stripped_text = strip_comments(text)
    for pattern in (WITH_RE, USE_RE):
        for match in pattern.finditer(stripped_text):
            for candidate in _split_identifier_targets(str(match.group("body") or "")):
                normalized_candidate = candidate.lower()
                if normalized_candidate in seen_targets:
                    continue
                seen_targets.add(normalized_candidate)
                targets.append(candidate)
    return tuple(targets)


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    stripped_text = strip_comments(text)
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    current_unit = next(iter(unit_names(text)), "")
    final_line = len(stripped_text.splitlines()) if stripped_text else 1
    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        symbol_kind: str | None = None
        symbol_name: str | None = None
        package_match = PACKAGE_DECL_RE.match(stripped_line)
        if package_match is not None:
            symbol_kind = "module"
            symbol_name = normalize_symbol_name(str(package_match.group("name") or ""))
            current_unit = normalize_unit_name(str(package_match.group("name") or ""))
        else:
            type_match = TYPE_DECL_RE.match(stripped_line)
            if type_match is not None:
                symbol_kind = "type"
                symbol_name = normalize_symbol_name(str(type_match.group("name") or ""))
            else:
                subprogram_match = SUBPROGRAM_DECL_RE.match(stripped_line)
                if subprogram_match is not None:
                    symbol_kind = "function"
                    symbol_name = normalize_symbol_name(str(subprogram_match.group("name") or ""))
        canonical_symbol_name = symbol_name.lower() if symbol_name else ""
        if (
            symbol_kind is None
            or not symbol_name
            or not canonical_symbol_name
            or canonical_symbol_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        symbol_key = (symbol_kind, canonical_symbol_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        qualified_names = {canonical_symbol_name}
        if current_unit and symbol_kind != "module":
            qualified_names.add(f"{current_unit}.{canonical_symbol_name}")
        if symbol_kind == "module" and current_unit:
            qualified_names.add(current_unit)
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


def _path_unit_alias(path: PurePosixPath) -> str:
    stem = path.stem.lower().replace("-", ".")
    return stem.strip(".")


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in {".adb", ".ads", ".ada"}:
        return set()
    aliases = {
        file_path.lower(),
        str(path.with_suffix("")).lower(),
        str(path.with_suffix("")).replace("/", ".").lower(),
        path.stem.lower(),
    }
    path_unit_alias = _path_unit_alias(path)
    if path_unit_alias:
        aliases.add(path_unit_alias)
        aliases.add(path_unit_alias.rsplit(".", 1)[-1])
    source_parts = list(path.parts)
    for source_root in ("src", "source", "ada"):
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        module_parts = list(source_parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = _path_unit_alias(PurePosixPath(module_parts[-1]))
        derived_alias = ".".join(part for part in module_parts if part).strip(".").lower()
        if derived_alias:
            aliases.add(derived_alias)
            aliases.add(derived_alias.rsplit(".", 1)[-1])
        break
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for unit_name in unit_names(text):
        aliases.add(unit_name)
        aliases.add(unit_name.rsplit(".", 1)[-1])
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        for alias in symbol_entry["qualified_names"]:
            if isinstance(alias, str) and alias:
                aliases.add(alias.lower())
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
    resolve_directory_prefix_match: ResolveDirectoryPrefixMatch,
) -> str | None:
    normalized_target = normalize_unit_name(import_target)
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    leaf_name = normalized_target.rsplit(".", 1)[-1]
    leaf_match = module_index.get(leaf_name)
    if leaf_match is not None:
        return leaf_match
    unit_path = normalized_target.replace(".", "/")
    unit_file = normalized_target.replace(".", "-")
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            normalized_target,
            leaf_name,
            unit_path,
            unit_file,
            f"{unit_path}.ads",
            f"{unit_path}.adb",
            f"{unit_path}.ada",
            f"{unit_file}.ads",
            f"{unit_file}.adb",
            f"{unit_file}.ada",
            f"{leaf_name}.ads",
            f"{leaf_name}.adb",
            f"{leaf_name}.ada",
        ],
    )
    if resolved is not None:
        return resolved
    return resolve_directory_prefix_match(
        module_index=module_index,
        prefixes=[
            unit_path,
            f"src/{unit_path}",
            f"source/{unit_path}",
            f"ada/{unit_path}",
        ],
    )


def _binding_target_file(binding: dict[str, Any] | None) -> str | None:
    if binding is None:
        return None
    target_file = binding.get("target_file")
    if not isinstance(target_file, str) or not target_file:
        return None
    return target_file


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[tuple[dict[str, Any], ...], dict[str, dict[str, Any]]]:
    dependencies: list[dict[str, Any]] = []
    import_bindings: dict[str, dict[str, Any]] = {}
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for import_target in with_targets(text):
        canonical_target = normalize_unit_name(import_target)
        if not canonical_target:
            continue
        target_symbol = canonical_target.rsplit(".", 1)[-1]
        target_file = resolve_import(canonical_target, module_index)
        dependency_key = (target_file, target_symbol, "imports")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": canonical_target,
                            "line": text.lower().find(import_target.lower()),
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_symbol,
                    "dependency_type": "imports",
                }
            )
        for alias_name in {canonical_target, target_symbol}:
            import_bindings.setdefault(
                alias_name,
                {
                    "alias": alias_name,
                    "target_file": target_file,
                    "target_names": (),
                },
            )
    return tuple(dependencies), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[dict[str, Any], ...]:
    dependencies, import_bindings = extract_import_bindings(
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
        str(entry["symbol_name"]).lower()
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
        for match in QUALIFIED_REFERENCE_RE.finditer(normalized_line):
            prefix = normalize_unit_name(str(match.group("alias") or ""))
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            if not prefix or not target_name:
                continue
            binding = import_bindings.get(prefix)
            target_file = _binding_target_file(binding)
            if target_file is None:
                target_file = resolve_import(prefix, module_index)
            dependency_key = (target_file, target_name.lower(), "references")
            if (
                target_file is None
                or target_file == file_path
                or dependency_key in dependency_keys
                or target_name.lower() in RESERVED_SYMBOL_NAMES
            ):
                continue
            dependency_keys.add(dependency_key)
            dependency_entries.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": f"{prefix}.{target_name}",
                            "line": line_no,
                            "kind": "qualified_reference",
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_name,
                    "dependency_type": "references",
                }
            )
        for match in CALL_REFERENCE_RE.finditer(normalized_line):
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            target_name_key = target_name.lower()
            if (
                not target_name
                or target_name_key in RESERVED_SYMBOL_NAMES
                or target_name_key in BUILTIN_TYPE_NAMES
                or target_name_key in declared_symbol_names
            ):
                continue
            target_file = resolve_import(target_name_key, module_index)
            dependency_key = (target_file, target_name_key, "references")
            if target_file is None or target_file == file_path or dependency_key in dependency_keys:
                continue
            dependency_keys.add(dependency_key)
            dependency_entries.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": target_name_key,
                            "line": line_no,
                            "kind": "call",
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_name,
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
    _, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    stripped_text = strip_comments(text)
    lines = stripped_text.splitlines()
    reference_candidates: dict[str, dict[str, Any]] = {}
    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_name = str(symbol_entry["symbol_name"])
        symbol_id = str(symbol_entry["symbol_id"])
        snippet = "\n".join(lines[start_line - 1 : end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            prefix = normalize_unit_name(str(match.group("alias") or ""))
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            if not prefix or not target_name:
                continue
            binding = import_bindings.get(prefix)
            target_file = _binding_target_file(binding)
            if target_file is None:
                target_file = resolve_import(prefix, module_index)
            if (
                target_file is None
                or target_file == file_path
                or target_name.lower() in RESERVED_SYMBOL_NAMES
            ):
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
        for match in CALL_REFERENCE_RE.finditer(snippet):
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            target_name_key = target_name.lower()
            if (
                not target_name
                or target_name_key in RESERVED_SYMBOL_NAMES
                or target_name_key in BUILTIN_TYPE_NAMES
                or target_name_key == symbol_name.lower()
            ):
                continue
            target_file = resolve_import(target_name_key, module_index)
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
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
