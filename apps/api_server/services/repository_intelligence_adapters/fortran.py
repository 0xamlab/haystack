from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveImport = Callable[[str, dict[str, str]], str | None]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ModuleIndexAliasesForFile = Callable[[dict[str, str], str], set[str]]

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "allocate",
        "associate",
        "block",
        "call",
        "case",
        "character",
        "class",
        "complex",
        "contains",
        "cycle",
        "data",
        "deallocate",
        "default",
        "do",
        "double",
        "else",
        "elseif",
        "end",
        "endif",
        "entry",
        "enum",
        "equivalence",
        "error",
        "exit",
        "external",
        "final",
        "function",
        "if",
        "implicit",
        "import",
        "include",
        "integer",
        "interface",
        "intrinsic",
        "logical",
        "module",
        "namelist",
        "none",
        "only",
        "parameter",
        "pause",
        "pointer",
        "print",
        "private",
        "procedure",
        "program",
        "public",
        "real",
        "recursive",
        "result",
        "return",
        "save",
        "select",
        "stop",
        "submodule",
        "subroutine",
        "target",
        "then",
        "type",
        "use",
        "value",
        "where",
        "while",
        "write",
    }
)
USE_RE = re.compile(
    r"^\s*use(?:\s*,\s*(?:intrinsic|non_intrinsic))?\s*(?:::\s*)?(?P<target>[A-Za-z_][A-Za-z0-9_]*)\b(?P<rest>.*)$",
    re.IGNORECASE | re.MULTILINE,
)
MODULE_RE = re.compile(
    r"^\s*module\s+(?!procedure\b)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
SUBMODULE_RE = re.compile(
    r"^\s*submodule\s*\(\s*(?P<parent>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
PROGRAM_RE = re.compile(
    r"^\s*program\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
SUBROUTINE_RE = re.compile(
    r"^\s*(?:(?:recursive|pure|elemental|impure|module)\s+)*subroutine\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
FUNCTION_RE = re.compile(
    r"^\s*(?:(?:recursive|pure|elemental|impure|module)\s+)*(?:[A-Za-z0-9_(),:*=\s]+\s+)?function\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*type(?:\s*,[^:]*)?\s*::\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
END_MODULE_RE = re.compile(
    r"^\s*end\s+(?:module|submodule|program)\b",
    re.IGNORECASE | re.MULTILINE,
)
CALL_RE = re.compile(r"\bcall\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE)
IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*$")


def normalize_name(raw_name: str) -> str:
    return raw_name.strip().lower()


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_name(import_target)
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{normalized_target}.f90",
            f"{normalized_target}.f95",
            f"{normalized_target}.f03",
            f"{normalized_target}.f08",
            f"{normalized_target}.f",
            f"{normalized_target}.for",
        ],
    )


def is_declared_symbol_alias(value: str) -> bool:
    return IDENTIFIER_RE.fullmatch(value.strip().lower()) is not None


def statement_entries(text: str) -> tuple[tuple[int, str], ...]:
    statements: list[tuple[int, str]] = []
    buffer_parts: list[str] = []
    buffer_start_line: int | None = None
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        raw_without_comment = raw_line.split("!", 1)[0].rstrip()
        stripped_line = raw_without_comment.strip()
        if not stripped_line:
            continue
        leading_continuation = stripped_line.startswith("&")
        if leading_continuation:
            stripped_line = stripped_line[1:].lstrip()
        trailing_continuation = stripped_line.endswith("&")
        if trailing_continuation:
            stripped_line = stripped_line[:-1].rstrip()
        if not buffer_parts or not leading_continuation:
            if buffer_parts:
                statements.append((buffer_start_line or line_no, " ".join(buffer_parts)))
                buffer_parts = []
            buffer_start_line = line_no
        if stripped_line:
            buffer_parts.append(stripped_line)
        if not trailing_continuation and buffer_parts:
            statements.append((buffer_start_line or line_no, " ".join(buffer_parts)))
            buffer_parts = []
            buffer_start_line = None
    if buffer_parts:
        statements.append((buffer_start_line or 1, " ".join(buffer_parts)))
    return tuple(statements)


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    current_module: str | None = None
    final_line = len(text.splitlines()) if text else 1
    for line_no, statement in statement_entries(text):
        normalized_statement = statement.strip()
        if not normalized_statement:
            continue
        if END_MODULE_RE.match(normalized_statement):
            current_module = None
            continue
        symbol_kind: str | None = None
        symbol_name: str | None = None
        qualified_names: set[str] = set()
        module_match = MODULE_RE.match(normalized_statement)
        if module_match is not None:
            symbol_kind = "module"
            symbol_name = normalize_name(module_match.group("name"))
            current_module = symbol_name
            qualified_names.add(symbol_name)
        else:
            submodule_match = SUBMODULE_RE.match(normalized_statement)
            if submodule_match is not None:
                symbol_kind = "module"
                parent_name = normalize_name(submodule_match.group("parent"))
                child_name = normalize_name(submodule_match.group("name"))
                symbol_name = child_name
                current_module = child_name
                qualified_names.add(child_name)
                qualified_names.add(f"{parent_name}.{child_name}")
            else:
                program_match = PROGRAM_RE.match(normalized_statement)
                if program_match is not None:
                    symbol_kind = "program"
                    symbol_name = normalize_name(program_match.group("name"))
                    current_module = None
                    qualified_names.add(symbol_name)
                else:
                    type_match = TYPE_DECL_RE.match(normalized_statement)
                    if type_match is not None:
                        symbol_kind = "type"
                        symbol_name = normalize_name(type_match.group("name"))
                    else:
                        subroutine_match = SUBROUTINE_RE.match(normalized_statement)
                        if subroutine_match is not None:
                            symbol_kind = "function"
                            symbol_name = normalize_name(subroutine_match.group("name"))
                        else:
                            function_match = FUNCTION_RE.match(normalized_statement)
                            if function_match is not None:
                                symbol_kind = "function"
                                symbol_name = normalize_name(function_match.group("name"))
        if (
            symbol_kind is None
            or symbol_name is None
            or not symbol_name
            or symbol_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        qualified_names.add(symbol_name)
        if current_module and current_module != symbol_name:
            qualified_names.add(f"{current_module}.{symbol_name}")
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
                        "line": line_no,
                        "kind": symbol_kind,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": line_no,
                "end_line": line_no,
                "signature": symbol_name,
                "qualified_names": tuple(sorted(name for name in qualified_names if name)),
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
    if path.suffix.lower() not in {".f", ".f03", ".f08", ".f90", ".f95", ".for"}:
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    aliases: set[str] = set()
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(
            normalize_name(str(alias))
            for alias in symbol_entry["qualified_names"]
            if alias
        )
    return {alias for alias in aliases if alias}


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
    module_index_aliases_for_file: ModuleIndexAliasesForFile,
) -> tuple[tuple[dict[str, Any], ...], dict[str, dict[str, Any]]]:
    dependencies: list[dict[str, Any]] = []
    import_bindings: dict[str, dict[str, Any]] = {}
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for line_no, statement in statement_entries(text):
        match = USE_RE.match(statement)
        if match is None:
            continue
        import_target = normalize_name(match.group("target"))
        if not import_target:
            continue
        target_file = resolve_import(import_target, module_index)
        dependency_key = (target_file, import_target, "imports")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {"file_path": file_path, "target": import_target, "line": line_no},
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": import_target,
                    "dependency_type": "imports",
                }
            )
        import_bindings.setdefault(
            import_target,
            {
                "alias": import_target,
                "target_file": target_file,
                "target_names": (import_target,),
            },
        )
        rest = str(match.group("rest") or "")
        lower_rest = rest.lower()
        if "only:" in lower_rest:
            only_body = rest[lower_rest.index("only:") + len("only:") :]
            for raw_item in only_body.split(","):
                normalized_item = raw_item.strip()
                if not normalized_item:
                    continue
                local_name, _, target_name = normalized_item.partition("=>")
                alias_name = normalize_name(local_name or target_name)
                resolved_target_name = normalize_name(target_name or local_name)
                if (
                    not alias_name
                    or alias_name in RESERVED_SYMBOL_NAMES
                    or not resolved_target_name
                ):
                    continue
                import_bindings.setdefault(
                    alias_name,
                    {
                        "alias": alias_name,
                        "target_file": target_file,
                        "target_names": (resolved_target_name,),
                    },
                )
            continue
        if target_file is None:
            continue
        for alias in sorted(module_index_aliases_for_file(module_index, target_file)):
            normalized_alias = normalize_name(alias.rsplit(".", 1)[-1])
            if (
                not normalized_alias
                or normalized_alias in RESERVED_SYMBOL_NAMES
                or not is_declared_symbol_alias(normalized_alias)
            ):
                continue
            import_bindings.setdefault(
                normalized_alias,
                {
                    "alias": normalized_alias,
                    "target_file": target_file,
                    "target_names": (normalized_alias,),
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
    module_index_aliases_for_file: ModuleIndexAliasesForFile,
) -> tuple[dict[str, Any], ...]:
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
        module_index_aliases_for_file=module_index_aliases_for_file,
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
    for line_no, statement in statement_entries(text):
        for match in CALL_RE.finditer(statement):
            target_name = normalize_name(match.group("name"))
            if (
                not target_name
                or target_name in RESERVED_SYMBOL_NAMES
                or target_name in declared_symbol_names
            ):
                continue
            binding = import_bindings.get(target_name)
            target_file = binding["target_file"] if binding is not None else None
            target_symbol = (
                binding["target_names"][0]
                if binding is not None and binding["target_names"]
                else target_name
            )
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
    module_index_aliases_for_file: ModuleIndexAliasesForFile,
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
        module_index_aliases_for_file=module_index_aliases_for_file,
    )
    reference_candidates: dict[str, dict[str, Any]] = {}
    parsed_statements = statement_entries(text)
    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_id = str(symbol_entry["symbol_id"])
        for line_no, statement in parsed_statements:
            if line_no < start_line or line_no > end_line:
                continue
            for match in CALL_RE.finditer(statement):
                target_name = normalize_name(match.group("name"))
                if not target_name or target_name in RESERVED_SYMBOL_NAMES:
                    continue
                binding = import_bindings.get(target_name)
                target_file = binding["target_file"] if binding is not None else None
                if target_file is None:
                    continue
                target_names = (
                    tuple(binding["target_names"])
                    if binding["target_names"]
                    else (target_name,)
                )
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
            module_index_aliases_for_file=module_index_aliases_for_file,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
