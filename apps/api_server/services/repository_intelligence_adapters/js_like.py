from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _JSImportBinding,
    _JsLikeLexState,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
ResolveImport = Callable[..., str | None]

IMPORT_RE = re.compile(r"""(?:from|require\()\s*['"]([^'"]+)['"]""")
IMPORT_STATEMENT_RE = re.compile(
    r"^\s*import\s+(?P<clause>.+?)\s+from\s+['\"](?P<target>[^'\"]+)['\"]\s*;?\s*$",
    re.MULTILINE | re.DOTALL,
)
EXPORT_FROM_RE = re.compile(
    r"^\s*export\s+(?:type\s+)?(?P<clause>\*|\{.+?\}(?:\s+as\s+[A-Za-z_$][A-Za-z0-9_$]*)?)\s+from\s+['\"](?P<target>[^'\"]+)['\"]\s*;?\s*$",
    re.MULTILINE | re.DOTALL,
)
REQUIRE_ASSIGN_RE = re.compile(
    r"^\s*(?:const|let|var)\s+(?P<binding>\{[^}]+\}|[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
    r"require\(\s*['\"](?P<target>[^'\"]+)['\"]\s*\)\s*;?\s*$",
    re.MULTILINE,
)
IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")
SYMBOL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:(?:async\s+)?function|class|interface|type|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:(async)\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:<[^>]+>)?\s*\(",
)
CLASS_DECL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][A-Za-z0-9_$]*)\b",
)
INTERFACE_DECL_RE = re.compile(
    r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][A-Za-z0-9_$]*)\b",
)
TYPE_DECL_RE = re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][A-Za-z0-9_$]*)\b")
ARROW_ASSIGN_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
    r"(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][A-Za-z0-9_$]*)\s*(?::\s*.+?)?\s*=>",
)
FUNCTION_ASSIGN_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:(async)\s+)?function\b",
)
CLASS_ASSIGN_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*class\b",
)
CONST_DECL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\b",
)
METHOD_DECL_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|static|readonly|abstract|declare|override)\s+)*"
    r"(?:(async)\s+)?(?:(get|set)\s+)?([A-Za-z_$][A-Za-z0-9_$]*|constructor)\s*(?:<[^>]+>)?\s*\(",
)
CLASS_FIELD_ARROW_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|static|readonly|abstract|declare|override)\s+)*"
    r"([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\s*(?::\s*.+?)?\s*=>",
)


def sanitize_line(
    line: str,
    *,
    state: _JsLikeLexState,
) -> tuple[str, int, int]:
    chars: list[str] = []
    open_count = 0
    close_count = 0
    index = 0
    while index < len(line):
        char = line[index]
        next_char = line[index + 1] if index + 1 < len(line) else ""
        if state.in_block_comment:
            if char == "*" and next_char == "/":
                state.in_block_comment = False
                chars.extend([" ", " "])
                index += 2
                continue
            chars.append(" ")
            index += 1
            continue
        if state.string_delim is not None:
            if state.escape:
                state.escape = False
            elif char == "\\":
                state.escape = True
            elif state.string_delim == "`" and char == "$" and next_char == "{":
                state.template_expression_depth = 1
                state.string_delim = None
                chars.extend([" ", "{"])
                open_count += 1
                index += 2
                continue
            elif char == state.string_delim:
                state.string_delim = None
            chars.append(" ")
            index += 1
            continue
        if char == "/" and next_char == "*":
            state.in_block_comment = True
            chars.extend([" ", " "])
            index += 2
            continue
        if char == "/" and next_char == "/":
            break
        if char in {"'", '"', "`"}:
            state.string_delim = char
            chars.append(" ")
            index += 1
            continue
        if char == "{":
            open_count += 1
            if state.template_expression_depth > 0:
                state.template_expression_depth += 1
        elif char == "}":
            close_count += 1
            if state.template_expression_depth > 0:
                state.template_expression_depth -= 1
                if state.template_expression_depth == 0:
                    state.string_delim = "`"
        chars.append(char)
        index += 1
    return "".join(chars), open_count, close_count


def match_symbol(
    *,
    stripped_line: str,
    parent_kind: str | None,
    at_parent_scope: bool,
    current_depth: int,
) -> tuple[str, str, bool] | None:
    if not stripped_line:
        return None
    function_match = FUNCTION_DECL_RE.match(stripped_line)
    if function_match is not None:
        return (
            "async_function" if function_match.group(1) else "function",
            function_match.group(2),
            True,
        )
    class_match = CLASS_DECL_RE.match(stripped_line)
    if class_match is not None:
        return ("class", class_match.group(1), True)
    interface_match = INTERFACE_DECL_RE.match(stripped_line)
    if interface_match is not None:
        return ("interface", interface_match.group(1), True)
    type_match = TYPE_DECL_RE.match(stripped_line)
    if type_match is not None:
        return ("type", type_match.group(1), False)
    arrow_match = ARROW_ASSIGN_RE.match(stripped_line)
    if arrow_match is not None:
        return ("arrow_function", arrow_match.group(1), True)
    function_assign_match = FUNCTION_ASSIGN_RE.match(stripped_line)
    if function_assign_match is not None:
        function_kind = (
            "async_function_expression"
            if function_assign_match.group(2)
            else "function_expression"
        )
        return (function_kind, function_assign_match.group(1), True)
    class_assign_match = CLASS_ASSIGN_RE.match(stripped_line)
    if class_assign_match is not None:
        return ("class_expression", class_assign_match.group(1), True)
    if parent_kind in {"class", "interface"} and at_parent_scope:
        class_field_match = CLASS_FIELD_ARROW_RE.match(stripped_line)
        if class_field_match is not None:
            return ("class_field_arrow", class_field_match.group(1), True)
        method_match = METHOD_DECL_RE.match(stripped_line)
        if method_match is not None:
            accessor = method_match.group(2)
            method_name = method_match.group(3)
            if accessor is not None:
                return (f"{accessor}_method", method_name, parent_kind == "class")
            if method_name == "constructor":
                return ("constructor", method_name, True)
            return (
                "async_method" if method_match.group(1) else "method",
                method_name,
                parent_kind == "class",
            )
    const_match = CONST_DECL_RE.match(stripped_line)
    if const_match is not None and current_depth == 0:
        return ("const", const_match.group(1), False)
    return None


def normalize_binding_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    if normalized.startswith("type "):
        normalized = normalized[5:].strip()
    return normalized


def parse_named_binding(part: str) -> tuple[str, str] | None:
    normalized = normalize_binding_name(part).strip(",")
    if not normalized:
        return None
    for separator in (" as ", ":"):
        if separator in normalized:
            source_name, alias = normalized.split(separator, maxsplit=1)
            source_name = normalize_binding_name(source_name)
            alias = normalize_binding_name(alias)
            if source_name and alias:
                return source_name, alias
            return None
    return normalized, normalized


def bindings_from_import_clause(
    *,
    clause: str,
    target_file: str | None,
) -> tuple[_JSImportBinding, ...]:
    normalized_clause = re.sub(r"\s+", " ", clause).strip()
    if not normalized_clause:
        return ()
    bindings: list[_JSImportBinding] = []
    named_clause = ""
    default_clause = normalized_clause
    if "{" in normalized_clause and "}" in normalized_clause:
        start_index = normalized_clause.index("{")
        end_index = normalized_clause.rindex("}")
        named_clause = normalized_clause[start_index + 1 : end_index]
        default_clause = normalized_clause[:start_index].rstrip(", ").strip()
    if default_clause:
        normalized_default = normalize_binding_name(default_clause.rstrip(","))
        if normalized_default.startswith("* as "):
            alias = normalize_binding_name(normalized_default[5:])
            if alias:
                bindings.append(
                    _JSImportBinding(
                        alias=alias,
                        target_file=target_file,
                        target_names=(),
                    )
                )
        elif normalized_default:
            bindings.append(
                _JSImportBinding(
                    alias=normalized_default,
                    target_file=target_file,
                    target_names=tuple(
                        value
                        for value in ("default", normalized_default)
                        if value and value != "default" or value == "default"
                    ),
                )
            )
    if named_clause:
        for part in named_clause.split(","):
            parsed_binding = parse_named_binding(part)
            if parsed_binding is None:
                continue
            source_name, alias = parsed_binding
            bindings.append(
                _JSImportBinding(
                    alias=alias,
                    target_file=target_file,
                    target_names=tuple(
                        dict.fromkeys(
                            value for value in (source_name, alias) if value and value != "*"
                        )
                    ),
                )
            )
    return tuple(bindings)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    *,
    resolve_import: ResolveImport,
) -> tuple[_JSImportBinding, ...]:
    bindings: list[_JSImportBinding] = []
    for match in IMPORT_STATEMENT_RE.finditer(text):
        target = match.group("target")
        target_file = resolve_import(
            current_file=file_path,
            import_target=target,
            module_index=module_index,
            workspace_package_index=workspace_package_index,
        )
        bindings.extend(
            bindings_from_import_clause(
                clause=match.group("clause"),
                target_file=target_file,
            )
        )
    for match in REQUIRE_ASSIGN_RE.finditer(text):
        target = match.group("target")
        target_file = resolve_import(
            current_file=file_path,
            import_target=target,
            module_index=module_index,
            workspace_package_index=workspace_package_index,
        )
        bindings.extend(
            bindings_from_import_clause(
                clause=match.group("binding"),
                target_file=target_file,
            )
        )
    return tuple(bindings)


def iter_dependency_specs(text: str) -> tuple[tuple[str, str], ...]:
    specs: dict[tuple[str, str], None] = {}
    for match in IMPORT_STATEMENT_RE.finditer(text):
        specs[(match.group("target"), "imports")] = None
    for match in REQUIRE_ASSIGN_RE.finditer(text):
        specs[(match.group("target"), "imports")] = None
    for match in EXPORT_FROM_RE.finditer(text):
        specs[(match.group("target"), "reexports")] = None
    return tuple(specs)


def compile_reference_pattern(identifier: str, *, member_only: bool) -> re.Pattern[str]:
    escaped_identifier = re.escape(identifier)
    if member_only:
        return re.compile(rf"\b(?:this|super)\s*\.\s*{escaped_identifier}\b")
    return re.compile(rf"\b{escaped_identifier}\b")


def symbol_reference_present(
    *,
    body_lines: Sequence[tuple[int, str]],
    identifier: str,
    exclude_line: int | None = None,
    member_only: bool = False,
) -> bool:
    if not identifier:
        return False
    pattern = compile_reference_pattern(identifier, member_only=member_only)
    for line_no, line_text in body_lines:
        if exclude_line is not None and line_no == exclude_line:
            continue
        if pattern.search(line_text):
            return True
    return False


def build_symbol_reference_candidates(
    *,
    file_path: str,
    sanitized_lines: Sequence[str],
    symbols: tuple[_Symbol, ...],
    import_bindings: tuple[_JSImportBinding, ...],
    stable_identifier: StableIdentifier,
) -> tuple[_SymbolReferenceCandidate, ...]:
    if not symbols:
        return ()

    symbols_by_id = {symbol.symbol_id: symbol for symbol in symbols}
    children_by_parent: dict[str, list[_Symbol]] = defaultdict(list)
    descendants_by_ancestor: dict[str, list[_Symbol]] = defaultdict(list)
    for symbol in symbols:
        current_parent = symbol.parent_symbol_id
        if symbol.parent_symbol_id is not None:
            children_by_parent[symbol.parent_symbol_id].append(symbol)
        while current_parent is not None:
            descendants_by_ancestor[current_parent].append(symbol)
            current_parent_symbol = symbols_by_id.get(current_parent)
            current_parent = (
                current_parent_symbol.parent_symbol_id
                if current_parent_symbol is not None
                else None
            )

    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}

    def _body_lines(symbol: _Symbol) -> list[tuple[int, str]]:
        end_line = min(symbol.end_line, len(sanitized_lines))
        return [
            (line_no, sanitized_lines[line_no - 1])
            for line_no in range(symbol.start_line, end_line + 1)
        ]

    def _record_candidate(candidate: _SymbolReferenceCandidate) -> None:
        reference_candidates[candidate.reference_edge_id] = candidate

    for source_symbol in symbols:
        body_lines = _body_lines(source_symbol)
        if not body_lines:
            continue

        for target_symbol in sorted(
            descendants_by_ancestor.get(source_symbol.symbol_id, ()),
            key=lambda item: (item.start_line, item.end_line, item.symbol_id),
        ):
            if not symbol_reference_present(
                body_lines=body_lines,
                identifier=target_symbol.symbol_name,
                exclude_line=target_symbol.start_line,
            ):
                continue
            _record_candidate(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "symref",
                        {
                            "source_symbol_id": source_symbol.symbol_id,
                            "target_symbol_id": target_symbol.symbol_id,
                            "type": "references_symbol",
                        },
                    ),
                    source_symbol_id=source_symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=target_symbol.symbol_id,
                    target_file=file_path,
                    target_names=(target_symbol.symbol_name,),
                    reference_type="references_symbol",
                )
            )

        parent_symbol = (
            symbols_by_id.get(source_symbol.parent_symbol_id)
            if source_symbol.parent_symbol_id is not None
            else None
        )
        if parent_symbol is not None and parent_symbol.symbol_kind in {"class", "class_expression"}:
            for sibling_symbol in sorted(
                children_by_parent.get(parent_symbol.symbol_id, ()),
                key=lambda item: (item.start_line, item.end_line, item.symbol_id),
            ):
                if sibling_symbol.symbol_id == source_symbol.symbol_id:
                    continue
                if not symbol_reference_present(
                    body_lines=body_lines,
                    identifier=sibling_symbol.symbol_name,
                    member_only=True,
                ):
                    continue
                _record_candidate(
                    _SymbolReferenceCandidate(
                        reference_edge_id=stable_identifier(
                            "symref",
                            {
                                "source_symbol_id": source_symbol.symbol_id,
                                "target_symbol_id": sibling_symbol.symbol_id,
                                "type": "references_symbol",
                            },
                        ),
                        source_symbol_id=source_symbol.symbol_id,
                        source_file=file_path,
                        target_symbol_id=sibling_symbol.symbol_id,
                        target_file=file_path,
                        target_names=(sibling_symbol.symbol_name,),
                        reference_type="references_symbol",
                    )
                )

        for binding in import_bindings:
            if not binding.target_names or binding.target_file is None:
                continue
            if not symbol_reference_present(
                body_lines=body_lines,
                identifier=binding.alias,
            ):
                continue
            _record_candidate(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "symref",
                        {
                            "source_symbol_id": source_symbol.symbol_id,
                            "target_file": binding.target_file,
                            "target_names": list(binding.target_names),
                            "type": "references_symbol",
                        },
                    ),
                    source_symbol_id=source_symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=binding.target_file,
                    target_names=binding.target_names,
                    reference_type="references_symbol",
                )
            )

    return tuple(reference_candidates[key] for key in sorted(reference_candidates))


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    for target, dependency_type in iter_dependency_specs(text):
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target,
                        "dependency_type": dependency_type,
                    },
                ),
                source_file=file_path,
                target_file=resolve_import(
                    current_file=file_path,
                    import_target=target,
                    module_index=module_index,
                    workspace_package_index=workspace_package_index,
                ),
                target_symbol=target,
                dependency_type=dependency_type,
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    symbol_entries: list[dict[str, Any]] = []
    dependencies: list[_Dependency] = []
    lex_state = _JsLikeLexState()
    symbol_stack: list[dict[str, Any]] = []
    pending_symbol_index: int | None = None
    sanitized_lines: list[str] = []

    def _current_parent_symbol_id() -> str | None:
        return str(symbol_stack[-1]["symbol_id"]) if symbol_stack else None

    def _close_completed_symbols(line_no: int, brace_depth: int) -> None:
        while symbol_stack and brace_depth < int(symbol_stack[-1]["exit_depth"]):
            completed = symbol_stack.pop()
            symbol_entries[int(completed["index"])]["end_line"] = line_no

    lines = text.splitlines()
    brace_depth = 0
    for line_no, line in enumerate(lines, start=1):
        sanitized_line, open_count, close_count = sanitize_line(line, state=lex_state)
        sanitized_lines.append(sanitized_line)
        stripped_line = sanitized_line.strip()
        starting_depth = brace_depth
        ending_depth = max(0, starting_depth + open_count - close_count)

        if pending_symbol_index is None:
            parent_kind = str(symbol_stack[-1]["symbol_kind"]) if symbol_stack else None
            at_parent_scope = bool(symbol_stack) and (
                starting_depth == int(symbol_stack[-1]["exit_depth"])
            )
            matched_symbol = match_symbol(
                stripped_line=stripped_line,
                parent_kind=parent_kind,
                at_parent_scope=at_parent_scope,
                current_depth=starting_depth,
            )
            if matched_symbol is not None:
                symbol_kind, symbol_name, expects_body = matched_symbol
                symbol_id = stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "line": line_no,
                        "kind": symbol_kind,
                    },
                )
                symbol_entries.append(
                    {
                        "symbol_id": symbol_id,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                        "start_line": line_no,
                        "end_line": line_no,
                        "parent_symbol_id": _current_parent_symbol_id(),
                        "signature": symbol_name,
                    }
                )
                symbol_index = len(symbol_entries) - 1
                if expects_body:
                    if ending_depth > starting_depth:
                        symbol_stack.append(
                            {
                                "index": symbol_index,
                                "symbol_id": symbol_id,
                                "symbol_kind": symbol_kind,
                                "exit_depth": ending_depth,
                            }
                        )
                    else:
                        pending_symbol_index = symbol_index

        brace_depth = ending_depth
        if pending_symbol_index is not None and brace_depth > starting_depth:
            pending_entry = symbol_entries[pending_symbol_index]
            symbol_stack.append(
                {
                    "index": pending_symbol_index,
                    "symbol_id": pending_entry["symbol_id"],
                    "symbol_kind": pending_entry["symbol_kind"],
                    "exit_depth": brace_depth,
                }
            )
            pending_symbol_index = None
        _close_completed_symbols(line_no, brace_depth)

    final_line = len(lines) if lines else 1
    for stack_entry in symbol_stack:
        symbol_entries[int(stack_entry["index"])]["end_line"] = final_line
    for target, dependency_type in iter_dependency_specs(text):
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target,
                        "dependency_type": dependency_type,
                    },
                ),
                source_file=file_path,
                target_file=resolve_import(
                    current_file=file_path,
                    import_target=target,
                    module_index=module_index,
                    workspace_package_index=workspace_package_index,
                ),
                target_symbol=target,
                dependency_type=dependency_type,
            )
        )
    import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        workspace_package_index,
        resolve_import=resolve_import,
    )
    symbols = tuple(
        _Symbol(
            symbol_id=str(entry["symbol_id"]),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=(
                None if entry["parent_symbol_id"] is None else str(entry["parent_symbol_id"])
            ),
            signature=None if entry["signature"] is None else str(entry["signature"]),
        )
        for entry in symbol_entries
    )
    symbol_references = build_symbol_reference_candidates(
        file_path=file_path,
        sanitized_lines=sanitized_lines,
        symbols=symbols,
        import_bindings=import_bindings,
        stable_identifier=stable_identifier,
    )
    return symbols, tuple(dependencies), symbol_references
