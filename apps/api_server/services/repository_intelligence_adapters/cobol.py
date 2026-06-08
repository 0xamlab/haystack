from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveImport = Callable[[str, dict[str, str]], str | None]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "accept",
        "add",
        "call",
        "close",
        "compute",
        "configuration",
        "continue",
        "copy",
        "data",
        "delete",
        "display",
        "division",
        "else",
        "end",
        "end-call",
        "end-evaluate",
        "end-if",
        "end-perform",
        "entry",
        "environment",
        "evaluate",
        "exit",
        "fd",
        "goback",
        "goto",
        "identification",
        "if",
        "input-output",
        "inspect",
        "linkage",
        "local-storage",
        "move",
        "multiply",
        "open",
        "perform",
        "procedure",
        "program-id",
        "read",
        "return",
        "rewrite",
        "search",
        "section",
        "sort",
        "start",
        "stop",
        "string",
        "subtract",
        "unstring",
        "use",
        "working-storage",
        "write",
    }
)
PROGRAM_ID_RE = re.compile(
    r"^\s*PROGRAM-ID\.\s+(?:IS\s+)?(?P<name>[A-Za-z][A-Za-z0-9_-]*)\s*\.?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
SECTION_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z][A-Za-z0-9_-]*)\s+SECTION\.\s*$",
    re.IGNORECASE | re.MULTILINE,
)
PARAGRAPH_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z][A-Za-z0-9_-]*)\.\s*$",
    re.IGNORECASE | re.MULTILINE,
)
COPY_RE = re.compile(
    r"^\s*COPY\s+(?P<target>[A-Za-z0-9_.-]+)(?:\s+REPLACING\b.*)?\.\s*$",
    re.IGNORECASE | re.MULTILINE,
)
CALL_LITERAL_RE = re.compile(
    r"""\bCALL\s+(?:"(?P<double>[A-Za-z0-9_.-]+)"|'(?P<single>[A-Za-z0-9_.-]+)')""",
    re.IGNORECASE,
)
PERFORM_RE = re.compile(
    r"\bPERFORM\s+(?P<name>[A-Za-z][A-Za-z0-9_-]*)\b",
    re.IGNORECASE,
)
IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_KNOWN_COBOL_SUFFIXES = (".cbl", ".cob", ".cobol", ".cpy")


def normalize_target(raw_target: str) -> str:
    return raw_target.strip().strip(".\"'").lower()


def normalize_symbol_name(raw_name: str) -> str:
    return raw_name.strip().strip(".").lower()


def _target_symbol_name(raw_target: str) -> str:
    normalized_target = normalize_target(raw_target)
    if not normalized_target:
        return ""
    leaf_name = PurePosixPath(normalized_target).name
    for suffix in _KNOWN_COBOL_SUFFIXES:
        if leaf_name.endswith(suffix):
            return leaf_name[: -len(suffix)]
    return leaf_name


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_target(import_target)
    if not normalized_target:
        return None
    leaf_name = _target_symbol_name(normalized_target)
    for candidate in (normalized_target, leaf_name):
        if not candidate:
            continue
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match
    nested_target = normalized_target.replace(".", "/")
    suffixes = [
        normalized_target,
        leaf_name,
        f"{normalized_target}.cbl",
        f"{normalized_target}.cob",
        f"{normalized_target}.cobol",
        f"{normalized_target}.cpy",
        f"{nested_target}.cbl",
        f"{nested_target}.cob",
        f"{nested_target}.cobol",
        f"{nested_target}.cpy",
    ]
    if leaf_name:
        suffixes.extend(
            [
                f"{leaf_name}.cbl",
                f"{leaf_name}.cob",
                f"{leaf_name}.cobol",
                f"{leaf_name}.cpy",
            ]
        )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        if len(raw_line) > 6 and raw_line[6] in {"*", "/"}:
            continue
        stripped_line = raw_line.lstrip()
        if stripped_line.startswith("*>"):
            continue
        line = raw_line.split("*>", 1)[0].rstrip()
        lines.append(line)
    return "\n".join(lines)


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    stripped_text = strip_comments(text)
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    current_program = ""
    final_line = len(stripped_text.splitlines()) if stripped_text else 1

    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        normalized_line = raw_line.strip()
        if not normalized_line:
            continue
        symbol_kind: str | None = None
        symbol_name = ""
        qualified_names: set[str] = set()

        program_match = PROGRAM_ID_RE.match(normalized_line)
        if program_match is not None:
            symbol_kind = "program"
            symbol_name = normalize_symbol_name(str(program_match.group("name") or ""))
            current_program = symbol_name
        else:
            section_match = SECTION_RE.match(normalized_line)
            if section_match is not None:
                symbol_kind = "function"
                symbol_name = normalize_symbol_name(str(section_match.group("name") or ""))
            else:
                paragraph_match = PARAGRAPH_RE.match(normalized_line)
                if paragraph_match is not None:
                    symbol_kind = "function"
                    symbol_name = normalize_symbol_name(str(paragraph_match.group("name") or ""))

        if (
            symbol_kind is None
            or not symbol_name
            or symbol_name in RESERVED_SYMBOL_NAMES
            or not IDENTIFIER_RE.fullmatch(symbol_name)
        ):
            continue

        qualified_names.add(symbol_name)
        if current_program and current_program != symbol_name:
            qualified_names.add(f"{current_program}.{symbol_name}")

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
    if path.suffix.lower() not in _KNOWN_COBOL_SUFFIXES:
        return set()
    aliases = {
        file_path.lower(),
        str(path.with_suffix("")).lower(),
        str(path.with_suffix("")).replace("/", ".").lower(),
        path.stem.lower(),
    }
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
            str(alias).lower()
            for alias in symbol_entry["qualified_names"]
            if isinstance(alias, str) and alias
        )
    return {alias for alias in aliases if alias}


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[tuple[dict[str, Any], ...], dict[str, dict[str, Any]]]:
    stripped_text = strip_comments(text)
    dependencies: list[dict[str, Any]] = []
    import_bindings: dict[str, dict[str, Any]] = {}
    dependency_keys: set[tuple[str | None, str, str]] = set()

    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        normalized_line = raw_line.strip()
        if not normalized_line:
            continue

        copy_match = COPY_RE.match(normalized_line)
        if copy_match is not None:
            raw_target = str(copy_match.group("target") or "")
            normalized_target = normalize_target(raw_target)
            target_symbol = _target_symbol_name(normalized_target)
            if not normalized_target or not target_symbol:
                continue
            target_file = resolve_import(normalized_target, module_index)
            dependency_key = (target_file, target_symbol, "imports")
            if dependency_key not in dependency_keys:
                dependency_keys.add(dependency_key)
                dependencies.append(
                    {
                        "dependency_edge_id": stable_identifier(
                            "dep",
                            {
                                "file_path": file_path,
                                "target": normalized_target,
                                "line": line_no,
                                "type": "imports",
                            },
                        ),
                        "source_file": file_path,
                        "target_file": target_file,
                        "target_symbol": target_symbol,
                        "dependency_type": "imports",
                    }
                )
            for alias in {normalized_target, target_symbol}:
                import_bindings.setdefault(
                    alias,
                    {
                        "alias": alias,
                        "target_file": target_file,
                        "target_names": (target_symbol,),
                    },
                )
            continue

        for match in CALL_LITERAL_RE.finditer(normalized_line):
            raw_target = str(match.group("double") or match.group("single") or "")
            normalized_target = normalize_target(raw_target)
            target_symbol = _target_symbol_name(normalized_target)
            if not normalized_target or not target_symbol:
                continue
            target_file = resolve_import(normalized_target, module_index)
            dependency_key = (target_file, target_symbol, "references")
            if dependency_key not in dependency_keys:
                dependency_keys.add(dependency_key)
                dependencies.append(
                    {
                        "dependency_edge_id": stable_identifier(
                            "dep",
                            {
                                "file_path": file_path,
                                "target": normalized_target,
                                "line": line_no,
                                "type": "references",
                            },
                        ),
                        "source_file": file_path,
                        "target_file": target_file,
                        "target_symbol": target_symbol,
                        "dependency_type": "references",
                    }
                )
            for alias in {normalized_target, target_symbol}:
                import_bindings.setdefault(
                    alias,
                    {
                        "alias": alias,
                        "target_file": target_file,
                        "target_names": (target_symbol,),
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
    dependencies, _import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    return dependencies


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
    dependency_specs, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    stripped_lines = strip_comments(text).splitlines()
    symbol_lookup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for symbol_entry in symbol_entries:
        symbol_lookup[str(symbol_entry["symbol_name"])].append(symbol_entry)
    reference_candidates: dict[str, dict[str, Any]] = {}

    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_id = str(symbol_entry["symbol_id"])
        snippet = "\n".join(
            stripped_lines[max(start_line - 1, 0) : min(end_line, len(stripped_lines))]
        )

        for match in CALL_LITERAL_RE.finditer(snippet):
            raw_target = str(match.group("double") or match.group("single") or "")
            normalized_target = normalize_target(raw_target)
            target_symbol = _target_symbol_name(normalized_target)
            if not normalized_target or not target_symbol:
                continue
            binding = import_bindings.get(normalized_target) or import_bindings.get(target_symbol)
            target_file = (
                str(binding["target_file"])
                if binding is not None and binding.get("target_file") is not None
                else resolve_import(normalized_target, module_index)
            )
            if target_file is None or target_file == file_path:
                continue
            target_names = (
                tuple(str(name) for name in binding.get("target_names", ()) if str(name))
                if binding is not None
                else (target_symbol,)
            ) or (target_symbol,)
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

        for match in PERFORM_RE.finditer(snippet):
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            if (
                not target_name
                or target_name in RESERVED_SYMBOL_NAMES
                or target_name == str(symbol_entry["symbol_name"])
            ):
                continue
            target_entries = symbol_lookup.get(target_name, [])
            if not target_entries:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": file_path,
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
                    "target_file": file_path,
                    "target_names": (target_name,),
                    "reference_type": "references_symbol",
                },
            )

    return (
        symbol_entries,
        dependency_specs,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
