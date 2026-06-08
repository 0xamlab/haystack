from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    js_like as js_like_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _JSImportBinding,
    _JsLikeLexState,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
ResolveImport = Callable[..., str | None]

IMPORT_DIRECTIVE_RE = re.compile(
    r"^\s*(?P<kind>import|export|part)\s+['\"](?P<target>[^'\"]+)['\"](?P<rest>[^;]*)\s*;",
    re.MULTILINE,
)
IMPORT_ALIAS_RE = re.compile(r"\bas\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\b")
IMPORT_SHOW_RE = re.compile(r"\bshow\s+(?P<names>[A-Za-z0-9_,\s]+)")
TYPE_DECL_RE = re.compile(
    r"^\s*(?:(?:abstract|base|sealed|interface|final)\s+)*"
    r"(?P<kind>class|mixin|enum)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
EXTENSION_DECL_RE = re.compile(
    r"^\s*extension(?:\s+type)?\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
TYPEDEF_DECL_RE = re.compile(r"^\s*typedef\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
TOP_LEVEL_FUNCTION_RE = re.compile(
    r"^\s*(?:(?:external|const|final|late|covariant|required|static)\s+)*"
    r"(?:(?:[A-Za-z_][A-Za-z0-9_<>,\?\[\]\s]*)\s+)?"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*(?:async\s*)?(?:=>|\{)"
)
METHOD_DECL_RE = re.compile(
    r"^\s*(?:(?:external|static|factory|const|final|late|covariant|required|override|operator)\s+)*"
    r"(?:(?:[A-Za-z_][A-Za-z0-9_<>,\?\[\]\s]*)\s+)?"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*(?:async\s*)?(?:=>|\{)"
)
SELECTOR_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "assert",
        "async",
        "await",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "default",
        "do",
        "else",
        "enum",
        "export",
        "extension",
        "factory",
        "false",
        "final",
        "finally",
        "for",
        "get",
        "hide",
        "if",
        "import",
        "in",
        "interface",
        "is",
        "late",
        "mixin",
        "new",
        "null",
        "operator",
        "part",
        "required",
        "rethrow",
        "return",
        "set",
        "show",
        "static",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typedef",
        "var",
        "void",
        "while",
        "with",
        "yield",
    }
)


def match_symbol(
    *,
    stripped_line: str,
    parent_kind: str | None,
    at_parent_scope: bool,
    current_depth: int,
) -> tuple[str, str, bool] | None:
    if not stripped_line:
        return None
    type_match = TYPE_DECL_RE.match(stripped_line)
    if type_match is not None:
        return (type_match.group("kind"), type_match.group("name"), True)
    extension_match = EXTENSION_DECL_RE.match(stripped_line)
    if extension_match is not None:
        return ("extension", extension_match.group("name"), True)
    typedef_match = TYPEDEF_DECL_RE.match(stripped_line)
    if typedef_match is not None:
        return ("typedef", typedef_match.group("name"), False)
    if parent_kind in {"class", "mixin", "enum", "extension"} and at_parent_scope:
        method_match = METHOD_DECL_RE.match(stripped_line)
        if method_match is not None:
            method_name = method_match.group("name")
            if method_name not in RESERVED_SYMBOL_NAMES:
                return ("method", method_name, True)
    if current_depth == 0:
        function_match = TOP_LEVEL_FUNCTION_RE.match(stripped_line)
        if function_match is not None:
            function_name = function_match.group("name")
            if function_name not in RESERVED_SYMBOL_NAMES:
                return ("function", function_name, True)
    return None


def iter_import_directives(
    text: str,
) -> tuple[tuple[str, str, str | None, tuple[str, ...]], ...]:
    directives: list[tuple[str, str, str | None, tuple[str, ...]]] = []
    for match in IMPORT_DIRECTIVE_RE.finditer(text):
        import_kind = str(match.group("kind") or "").strip()
        import_target = str(match.group("target") or "").strip()
        if not import_kind or not import_target:
            continue
        rest = str(match.group("rest") or "")
        alias_match = IMPORT_ALIAS_RE.search(rest)
        alias = str(alias_match.group("alias")).strip() if alias_match is not None else None
        show_names: list[str] = []
        show_match = IMPORT_SHOW_RE.search(rest)
        if show_match is not None:
            for raw_name in str(show_match.group("names") or "").split(","):
                candidate_name = raw_name.strip()
                if (
                    candidate_name
                    and candidate_name not in RESERVED_SYMBOL_NAMES
                    and candidate_name not in show_names
                ):
                    show_names.append(candidate_name)
        directives.append((import_kind, import_target, alias, tuple(show_names)))
    return tuple(directives)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str, str | None, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_index, (import_kind, import_target, alias, show_names) in enumerate(
        iter_import_directives(text)
    ):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
        )
        dependency_type = "exports" if import_kind == "export" else "imports"
        dependency_key = (import_kind, target_file, import_target)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "kind": import_kind,
                            "index": import_index,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=PurePosixPath(import_target).name or import_target,
                    dependency_type=dependency_type,
                )
            )
        if import_kind != "import":
            continue
        if alias is not None:
            import_bindings.setdefault(
                alias,
                _ImportedSymbolBinding(
                    alias=alias,
                    target_file=target_file,
                    target_names=(),
                ),
            )
        for show_name in show_names:
            import_bindings.setdefault(
                show_name,
                _ImportedSymbolBinding(
                    alias=show_name,
                    target_file=target_file,
                    target_names=(show_name,),
                ),
            )
    return tuple(dependencies), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[_Dependency, ...]:
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
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    symbol_entries: list[dict[str, Any]] = []
    symbol_stack: list[dict[str, Any]] = []
    pending_symbol_index: int | None = None
    sanitized_lines: list[str] = []
    lex_state = _JsLikeLexState()
    lines = text.splitlines()
    brace_depth = 0

    def _current_parent_symbol_id() -> str | None:
        return str(symbol_stack[-1]["symbol_id"]) if symbol_stack else None

    def _close_completed_symbols(line_no: int, current_depth: int) -> None:
        while symbol_stack and current_depth < int(symbol_stack[-1]["exit_depth"]):
            completed = symbol_stack.pop()
            symbol_entries[int(completed["index"])]["end_line"] = line_no

    for line_no, line in enumerate(lines, start=1):
        sanitized_line, open_count, close_count = js_like_adapter.sanitize_line(
            line,
            state=lex_state,
        )
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
    if pending_symbol_index is not None:
        symbol_entries[pending_symbol_index]["end_line"] = final_line

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
            signature=str(entry["signature"]),
        )
        for entry in symbol_entries
    )
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    symbol_references = {
        candidate.reference_edge_id: candidate
        for candidate in js_like_adapter.build_symbol_reference_candidates(
            file_path=file_path,
            sanitized_lines=sanitized_lines,
            symbols=symbols,
            import_bindings=tuple(
                _JSImportBinding(
                    alias=binding.alias,
                    target_file=binding.target_file,
                    target_names=binding.target_names,
                )
                for binding in import_bindings.values()
                if binding.target_file is not None and binding.target_names
            ),
            stable_identifier=stable_identifier,
        )
    }

    def _body_lines(symbol: _Symbol) -> list[tuple[int, str]]:
        end_line = min(symbol.end_line, len(sanitized_lines))
        return [
            (line_no, sanitized_lines[line_no - 1])
            for line_no in range(symbol.start_line, end_line + 1)
        ]

    for source_symbol in symbols:
        body_lines = _body_lines(source_symbol)
        if not body_lines:
            continue
        snippet = "\n".join(line for _line_no, line in body_lines)
        for match in SELECTOR_REFERENCE_RE.finditer(snippet):
            alias = str(match.group("alias") or "").strip()
            target_name = str(match.group("name") or "").strip()
            binding = import_bindings.get(alias)
            if (
                binding is None
                or binding.target_file is None
                or not target_name
                or target_name in RESERVED_SYMBOL_NAMES
            ):
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": source_symbol.symbol_id,
                    "target_file": binding.target_file,
                    "target_names": (target_name,),
                    "type": "references_symbol",
                },
            )
            symbol_references.setdefault(
                edge_id,
                _SymbolReferenceCandidate(
                    reference_edge_id=edge_id,
                    source_symbol_id=source_symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=binding.target_file,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
    return symbols, dependencies, tuple(symbol_references[key] for key in sorted(symbol_references))
