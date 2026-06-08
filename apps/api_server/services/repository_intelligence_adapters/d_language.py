from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveImport = Callable[[str, dict[str, str]], str | None]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abstract",
        "alias",
        "asm",
        "assert",
        "auto",
        "body",
        "break",
        "case",
        "cast",
        "catch",
        "class",
        "const",
        "continue",
        "debug",
        "default",
        "delegate",
        "delete",
        "deprecated",
        "do",
        "else",
        "enum",
        "export",
        "extern",
        "false",
        "final",
        "finally",
        "for",
        "foreach",
        "foreach_reverse",
        "function",
        "goto",
        "if",
        "immutable",
        "import",
        "in",
        "inout",
        "interface",
        "is",
        "lazy",
        "mixin",
        "module",
        "new",
        "nothrow",
        "null",
        "out",
        "override",
        "package",
        "pragma",
        "private",
        "protected",
        "public",
        "pure",
        "ref",
        "return",
        "scope",
        "shared",
        "static",
        "struct",
        "super",
        "switch",
        "synchronized",
        "template",
        "this",
        "throw",
        "true",
        "try",
        "typeid",
        "typeof",
        "union",
        "unittest",
        "version",
        "while",
        "with",
    }
)
MODULE_RE = re.compile(
    r"^\s*module\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*;",
    re.MULTILINE,
)
IMPORT_RE = re.compile(
    r"^\s*(?:(?:public|private|package|protected|export|static)\s+)*import\s+(?P<body>[^;]+);",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:(?:public|private|package|protected|export|abstract|final|static|extern|immutable|shared|__gshared)\s+)*"
    r"(?:class|struct|interface|enum|union|template)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:(?:public|private|package|protected|export|abstract|final|static|extern|override|synchronized|pure|nothrow|scope|ref|auto|const|immutable|shared|__gshared|lazy|@[_A-Za-z][_A-Za-z0-9.]*)\s+)*"
    r"(?:(?:[_A-Za-z][_A-Za-z0-9.!<>\[\]]*|~?this)\s+)+(?P<name>~?this|[A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)",
    re.MULTILINE,
)
QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<prefix>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
UNQUALIFIED_CALL_RE = re.compile(r"(?<!\.)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_module_name(raw_name: str) -> str:
    return raw_name.strip().lower()


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_module_name(import_target)
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{normalized_target}.d",
            f"{normalized_target}.di",
            f"{normalized_target.replace('.', '/')}.d",
            f"{normalized_target.replace('.', '/')}.di",
        ],
    )


def strip_comments(text: str) -> str:
    without_block_comments = re.sub(r"/\+.*?\+/|/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*$", "", without_block_comments, flags=re.MULTILINE)


def statement_entries(text: str) -> tuple[tuple[int, str], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[int, str]] = []
    buffer_parts: list[str] = []
    buffer_start_line: int | None = None
    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        if buffer_start_line is None:
            buffer_start_line = line_no
        buffer_parts.append(stripped_line)
        joined = " ".join(buffer_parts)
        while ";" in joined:
            statement, joined = joined.split(";", 1)
            normalized_statement = statement.strip()
            if normalized_statement:
                statements.append((buffer_start_line, normalized_statement))
            joined = joined.strip()
            buffer_parts = [joined] if joined else []
            buffer_start_line = line_no if joined else None
        if buffer_parts and joined:
            buffer_parts = [joined]
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
    stripped_text = strip_comments(text)
    final_line = len(stripped_text.splitlines()) if stripped_text else 1
    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        normalized_line = raw_line.strip()
        if not normalized_line:
            continue
        symbol_kind: str | None = None
        symbol_name: str | None = None
        qualified_names: set[str] = set()
        module_match = MODULE_RE.match(normalized_line)
        if module_match is not None:
            symbol_kind = "module"
            symbol_name = module_match.group("name").strip()
            current_module = symbol_name
            qualified_names.add(symbol_name)
        else:
            type_match = TYPE_DECL_RE.match(normalized_line)
            if type_match is not None:
                symbol_kind = "type"
                symbol_name = type_match.group("name").strip()
            else:
                function_match = FUNCTION_DECL_RE.match(normalized_line)
                if function_match is not None:
                    symbol_kind = "function"
                    symbol_name = function_match.group("name").strip()
        if (
            symbol_kind is None
            or symbol_name is None
            or not symbol_name
            or symbol_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        qualified_names.add(symbol_name)
        if current_module and symbol_kind != "module":
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
    return symbol_entries


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in {".d", ".di"}:
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    aliases: set[str] = set()
    for match in MODULE_RE.finditer(strip_comments(text)):
        module_name = normalize_module_name(match.group("name"))
        if module_name:
            aliases.add(module_name)
            aliases.add(module_name.rsplit(".", 1)[-1])
    path_parts = list(path.parts)
    for source_root in ("src", "source"):
        if source_root not in path_parts:
            continue
        root_index = path_parts.index(source_root)
        module_parts = list(path_parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem
        derived_alias = normalize_module_name(".".join(part for part in module_parts if part))
        if derived_alias:
            aliases.add(derived_alias)
            aliases.add(derived_alias.rsplit(".", 1)[-1])
        break
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        for alias in symbol_entry["qualified_names"]:
            if isinstance(alias, str) and alias:
                aliases.add(alias)
    return {alias for alias in aliases if alias}


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
    for line_no, statement in statement_entries(text):
        match = IMPORT_RE.match(f"{statement};")
        if match is None:
            continue
        body = match.group("body").strip()
        if not body:
            continue
        if ":" in body:
            module_part, symbol_part = body.split(":", 1)
        else:
            module_part, symbol_part = body, ""
        module_targets = [part.strip() for part in module_part.split(",") if part.strip()]
        for raw_target in module_targets:
            local_alias: str | None = None
            import_target = raw_target
            if "=" in raw_target:
                local_alias, import_target = (
                    part.strip() for part in raw_target.split("=", 1)
                )
            normalized_target = normalize_module_name(import_target)
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
                                "target": normalized_target,
                                "line": line_no,
                            },
                        ),
                        "source_file": file_path,
                        "target_file": target_file,
                        "target_symbol": normalized_target,
                        "dependency_type": "imports",
                    }
                )
            for alias_name in {
                local_alias.strip() if isinstance(local_alias, str) else None,
                import_target.rsplit(".", 1)[-1].strip(),
                normalized_target,
            }:
                if (
                    not alias_name
                    or alias_name in RESERVED_SYMBOL_NAMES
                    or not IDENTIFIER_RE.fullmatch(alias_name)
                ):
                    continue
                import_bindings.setdefault(
                    alias_name,
                    {
                        "alias": alias_name,
                        "target_file": target_file,
                        "target_names": (),
                    },
                )
            if not symbol_part or len(module_targets) != 1:
                continue
            for raw_item in symbol_part.split(","):
                normalized_item = raw_item.strip()
                if not normalized_item:
                    continue
                local_name, _, target_name = normalized_item.partition("=")
                alias_name = (local_name or target_name).strip()
                resolved_target_name = (target_name or local_name).strip()
                if (
                    not alias_name
                    or not resolved_target_name
                    or alias_name in RESERVED_SYMBOL_NAMES
                    or not IDENTIFIER_RE.fullmatch(alias_name)
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
            prefix = match.group("prefix").strip()
            target_name = match.group("name").strip()
            target_file = None
            binding = import_bindings.get(prefix)
            if binding is not None:
                target_file = binding["target_file"]
            if target_file is None:
                target_file = resolve_import(prefix, module_index)
            dependency_key = (target_file, target_name, "references")
            if (
                target_file is None
                or target_file == file_path
                or dependency_key in dependency_keys
                or target_name in RESERVED_SYMBOL_NAMES
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
                            "kind": "qualified_call",
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_name,
                    "dependency_type": "references",
                }
            )
        for match in UNQUALIFIED_CALL_RE.finditer(normalized_line):
            target_name = match.group("name").strip()
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
                prefix = match.group("prefix").strip()
                target_name = match.group("name").strip()
                target_file = None
                binding = import_bindings.get(prefix)
                if binding is not None:
                    target_file = binding["target_file"]
                if target_file is None:
                    target_file = resolve_import(prefix, module_index)
                if (
                    target_file is None
                    or target_file == file_path
                    or target_name in RESERVED_SYMBOL_NAMES
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
            for match in UNQUALIFIED_CALL_RE.finditer(normalized_line):
                target_name = match.group("name").strip()
                if not target_name or target_name in RESERVED_SYMBOL_NAMES:
                    continue
                binding = import_bindings.get(target_name)
                target_file = binding["target_file"] if binding is not None else None
                if target_file is None or target_file == file_path:
                    continue
                target_names = (
                    tuple(binding["target_names"])
                    if binding is not None and binding["target_names"]
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
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
