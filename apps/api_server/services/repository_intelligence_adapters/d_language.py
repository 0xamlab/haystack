from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveImport = Callable[[str, dict[str, str]], str | None]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
RawSymbolEntry = tuple[str, str, int, str, tuple[str, ...]]

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
# NOTE: bounded the inner identifier-style return-type segment with an explicit
# upper repetition limit to defang the polynomial backtracking flagged by
# py/redos. Both groups can otherwise match overlapping qualifier-like tokens
# (e.g. 'extern extern ...' could be split across the two quantified groups).
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:(?:public|private|package|protected|export|abstract|final|static|extern|override|synchronized|pure|nothrow|scope|ref|auto|const|immutable|shared|__gshared|lazy|@[_A-Za-z][_A-Za-z0-9.]*)\s+)*"
    r"(?:(?:[_A-Za-z][_A-Za-z0-9.!<>\[\]]{0,256}|~?this)\s+){1,8}(?P<name>~?this|[A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)",
    re.MULTILINE,
)
QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<prefix>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
UNQUALIFIED_CALL_RE = re.compile(r"(?<!\.)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LEADING_TOKEN_RE = re.compile(r"^\s*(?P<token>[A-Za-z_][A-Za-z0-9_]*)")
# Statement-leading keywords. A line beginning with one of these is a control-flow /
# expression statement (e.g. `return helper();`), not a type/function declaration —
# without this guard FUNCTION_DECL_RE treats the keyword as a return-type token and the
# call target as a declared function, spawning a phantom symbol inside a function body.
_STATEMENT_LEADING_KEYWORDS = frozenset(
    {
        "return",
        "if",
        "else",
        "while",
        "for",
        "foreach",
        "foreach_reverse",
        "switch",
        "case",
        "default",
        "do",
        "break",
        "continue",
        "goto",
        "throw",
        "try",
        "catch",
        "finally",
        "with",
        "assert",
        "mixin",
        "scope",
        "synchronized",
        "delete",
        "new",
        "cast",
    }
)


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


@lru_cache(maxsize=1024)
def _strip_comments_cached(text: str) -> str:
    without_block_comments = re.sub(r"/\+.*?\+/|/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*$", "", without_block_comments, flags=re.MULTILINE)


def strip_comments(text: str) -> str:
    return _strip_comments_cached(text)


@lru_cache(maxsize=1024)
def _statement_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[int, str], ...]:
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


def statement_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[int, str], ...]:
    return _statement_entries_from_stripped_text(
        stripped_text if stripped_text is not None else strip_comments(text)
    )


@lru_cache(maxsize=1024)
def _iter_symbol_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[RawSymbolEntry, ...]:
    symbol_entries: list[RawSymbolEntry] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    current_module: str | None = None
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
            leading_token_match = _LEADING_TOKEN_RE.match(normalized_line)
            leading_token = (
                leading_token_match.group("token") if leading_token_match is not None else ""
            )
            if leading_token in _STATEMENT_LEADING_KEYWORDS:
                # Statement (e.g. `return helper();`), not a declaration — skip so the
                # call target is not mistaken for a function declared inside the body.
                continue
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
            (
                symbol_kind,
                symbol_name,
                line_no,
                normalized_line,
                tuple(sorted(qualified_names)),
            )
        )
    return tuple(symbol_entries)


def _declared_symbol_names_from_stripped_text(stripped_text: str) -> frozenset[str]:
    return frozenset(
        symbol_name
        for _, symbol_name, _, _, _ in _iter_symbol_entries_from_stripped_text(stripped_text)
    )


def _symbol_entry_end_lines(
    raw_symbol_entries: tuple[RawSymbolEntry, ...],
    *,
    final_line: int,
) -> tuple[int, ...]:
    end_lines: list[int] = []
    for index, (symbol_kind, _symbol_name, start_line, _signature, _qualified_names) in enumerate(
        raw_symbol_entries
    ):
        if symbol_kind == "module":
            end_lines.append(final_line)
            continue
        next_start_line = (
            raw_symbol_entries[index + 1][2] if index + 1 < len(raw_symbol_entries) else None
        )
        end_lines.append(
            final_line if next_start_line is None else max(start_line, next_start_line - 1)
        )
    return tuple(end_lines)


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> list[dict[str, Any]]:
    effective_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    raw_symbol_entries = _iter_symbol_entries_from_stripped_text(effective_stripped_text)
    symbol_entries: list[dict[str, Any]] = []
    final_line = len(effective_stripped_text.splitlines()) if effective_stripped_text else 1
    for end_line, (
        symbol_kind,
        symbol_name,
        line_no,
        signature,
        qualified_names,
    ) in zip(
        _symbol_entry_end_lines(raw_symbol_entries, final_line=final_line),
        raw_symbol_entries,
        strict=True,
    ):
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    (file_path, symbol_name, symbol_kind, line_no),
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": line_no,
                "end_line": end_line,
                "signature": signature,
                "qualified_names": qualified_names,
            }
        )
    return symbol_entries


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in {".d", ".di"}:
        return set()
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    effective_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    aliases: set[str] = set()
    for match in MODULE_RE.finditer(effective_stripped_text):
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
    for _, _, _, _, qualified_names in _iter_symbol_entries_from_stripped_text(
        effective_stripped_text
    ):
        for alias in qualified_names:
            if alias:
                aliases.add(alias)
    return {alias for alias in aliases if alias}


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
    stripped_text: str | None = None,
    statements: tuple[tuple[int, str], ...] | None = None,
) -> tuple[tuple[dict[str, Any], ...], dict[str, dict[str, Any]]]:
    effective_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    effective_statements = (
        statements
        if statements is not None
        else statement_entries(text, stripped_text=effective_stripped_text)
    )
    dependencies: list[dict[str, Any]] = []
    import_bindings: dict[str, dict[str, Any]] = {}
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for line_no, statement in effective_statements:
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
                            (file_path, normalized_target, line_no, "imports"),
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


def _build_dependency_entries(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
    stripped_text: str | None = None,
    import_bindings: dict[str, dict[str, Any]] | None = None,
    dependencies: tuple[dict[str, Any], ...] | None = None,
    declared_symbol_names: frozenset[str] | set[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    effective_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    if dependencies is None or import_bindings is None:
        dependencies, import_bindings = extract_import_bindings(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
            stripped_text=effective_stripped_text,
        )
    effective_declared_symbol_names = (
        declared_symbol_names
        if declared_symbol_names is not None
        else _declared_symbol_names_from_stripped_text(effective_stripped_text)
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (entry["target_file"], entry["target_symbol"], entry["dependency_type"])
        for entry in dependency_entries
    }
    for line_no, raw_line in enumerate(effective_stripped_text.splitlines(), start=1):
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
                        (file_path, f"{prefix}.{target_name}", line_no, "qualified_call"),
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
                or target_name in effective_declared_symbol_names
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
                        (file_path, target_symbol, line_no, "call"),
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_symbol,
                    "dependency_type": "references",
                }
            )
    return tuple(dependency_entries)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[dict[str, Any], ...]:
    stripped_text = strip_comments(text)
    return _build_dependency_entries(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
        stripped_text=stripped_text,
    )


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
    stripped_text = strip_comments(text)
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    statements = statement_entries(text, stripped_text=stripped_text)
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
        stripped_text=stripped_text,
        statements=statements,
    )
    stripped_lines = stripped_text.splitlines()
    ordered_symbols = sorted(
        symbol_entries,
        key=lambda entry: (
            int(entry["start_line"]),
            int(entry["end_line"]),
            str(entry["symbol_id"]),
        ),
    )
    reference_candidates: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
    active_symbols: list[dict[str, Any]] = []
    next_symbol_index = 0
    for line_no, raw_line in enumerate(stripped_lines, start=1):
        while next_symbol_index < len(ordered_symbols):
            candidate_symbol = ordered_symbols[next_symbol_index]
            if int(candidate_symbol["start_line"]) > line_no:
                break
            active_symbols.append(candidate_symbol)
            next_symbol_index += 1
        if active_symbols:
            active_symbols = [
                symbol_entry
                for symbol_entry in active_symbols
                if int(symbol_entry["end_line"]) >= line_no
            ]
        if not active_symbols:
            continue
        normalized_line = raw_line.strip()
        if not normalized_line:
            continue
        line_targets: list[tuple[str, tuple[str, ...]]] = []
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
            line_targets.append((target_file, (target_name,)))
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
            line_targets.append((target_file, target_names))
        if not line_targets:
            continue
        unique_line_targets = tuple(dict.fromkeys(line_targets))
        reference_source_symbols = [
            symbol_entry
            for symbol_entry in active_symbols
            if str(symbol_entry["symbol_kind"]) == "function"
        ]
        if not reference_source_symbols:
            reference_source_symbols = active_symbols
        for symbol_entry in reference_source_symbols:
            symbol_id = str(symbol_entry["symbol_id"])
            for target_file, target_names in unique_line_targets:
                candidate_key = (symbol_id, target_file, target_names)
                if candidate_key in reference_candidates:
                    continue
                edge_id = stable_identifier(
                    "ref",
                    (symbol_id, target_file, target_names, "references_symbol"),
                )
                reference_candidates[candidate_key] = {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": symbol_id,
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": target_names,
                    "reference_type": "references_symbol",
                }
    return (
        symbol_entries,
        _build_dependency_entries(
            file_path=file_path,
            text=text,
            module_index=module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
            stripped_text=stripped_text,
            import_bindings=import_bindings,
            dependencies=dependencies,
            declared_symbol_names={
                str(entry["symbol_name"])
                for entry in symbol_entries
            },
        ),
        tuple(
            candidate
            for candidate in sorted(
                reference_candidates.values(),
                key=lambda entry: str(entry["reference_edge_id"]),
            )
        ),
    )
