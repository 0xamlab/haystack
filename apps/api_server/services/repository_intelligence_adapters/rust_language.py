from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]

USE_RE = re.compile(
    r"^\s*use\s+(?P<path>[A-Za-z_][A-Za-z0-9_:\{\},\s\*]+);",
    re.MULTILINE,
)
MOD_RE = re.compile(
    r"^\s*(?:pub\s+)?mod\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;",
    re.MULTILINE,
)
SYMBOL_LINE_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:(?:async|const|unsafe)\s+)?"
    r"(?P<kind>fn|struct|enum|trait)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
)
CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def parse_use_targets(path_expression: str) -> list[tuple[str, str]]:
    normalized = re.sub(r"\s+", "", path_expression.strip())
    if not normalized:
        return []
    if "{" not in normalized:
        leaf = normalized.rsplit("::", 1)[-1]
        return [(normalized, leaf)]
    prefix, _, remainder = normalized.partition("{")
    inner = remainder.rsplit("}", 1)[0]
    base = prefix.rstrip(":")
    targets: list[tuple[str, str]] = []
    for item in inner.split(","):
        entry = item.strip()
        if not entry or entry == "*":
            continue
        if " as " in entry:
            target_path, alias = re.split(r"\s+as\s+", entry, maxsplit=1)
        else:
            target_path = entry
            alias = entry.rsplit("::", 1)[-1]
        full_path = "::".join(part for part in (base, target_path) if part)
        targets.append((full_path, alias))
    return targets


def resolve_module_path(
    *,
    current_file: str,
    module_path: str,
    module_index: dict[str, str],
) -> str | None:
    normalized_path = module_path.strip()
    if not normalized_path or normalized_path == "crate":
        return module_index.get("crate")
    current_path = PurePosixPath(current_file)
    current_dir_parts = list(current_path.parent.parts)
    if normalized_path.startswith("crate::"):
        base_parts = ["src"]
        remainder = normalized_path.split("::")[1:]
    elif normalized_path.startswith("self::"):
        base_parts = current_dir_parts
        remainder = normalized_path.split("::")[1:]
    elif normalized_path.startswith("super::"):
        remainder = normalized_path.split("::")
        base_parts = current_dir_parts
        while remainder and remainder[0] == "super":
            remainder = remainder[1:]
            if base_parts:
                base_parts = base_parts[:-1]
    else:
        base_parts = ["src"]
        remainder = normalized_path.split("::")
    candidate_parts = [part for part in [*base_parts, *remainder] if part]
    for trim in range(0, min(2, len(candidate_parts)) + 1):
        parts = candidate_parts if trim == 0 else candidate_parts[:-trim]
        if not parts:
            continue
        candidate_path = "/".join(parts)
        for key in (candidate_path, candidate_path.replace("/", ".")):
            target = module_index.get(key)
            if target is not None:
                return target
    return None


def resolve_child_module(
    *,
    current_file: str,
    module_name: str,
    module_index: dict[str, str],
) -> str | None:
    current_path = PurePosixPath(current_file)
    base_parts = list(current_path.parent.parts)
    if current_path.stem == "mod":
        base_parts = list(current_path.parent.parts)
    candidate_parts = [*base_parts, module_name]
    candidate_path = "/".join(candidate_parts)
    for key in (candidate_path, candidate_path.replace("/", ".")):
        target = module_index.get(key)
        if target is not None:
            return target
    return None


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_module_path: Callable[..., str | None],
    resolve_child_module: Callable[..., str | None],
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    for match in USE_RE.finditer(text):
        for full_path, alias in parse_use_targets(match.group("path")):
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {"file_path": file_path, "target": full_path, "alias": alias},
                    ),
                    source_file=file_path,
                    target_file=resolve_module_path(
                        current_file=file_path,
                        module_path=full_path,
                        module_index=module_index,
                    ),
                    target_symbol=alias,
                    dependency_type="imports",
                )
            )
    for match in MOD_RE.finditer(text):
        module_name = match.group("name")
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "module": module_name, "kind": "mod"},
                ),
                source_file=file_path,
                target_file=resolve_child_module(
                    current_file=file_path,
                    module_name=module_name,
                    module_index=module_index,
                ),
                target_symbol=module_name,
                dependency_type="imports",
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_module_path: Callable[..., str | None],
    resolve_child_module: Callable[..., str | None],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    symbols: list[_Symbol] = []
    dependencies: list[_Dependency] = []
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    symbols_by_name: dict[str, list[_Symbol]] = defaultdict(list)
    symbol_ranges: list[tuple[_Symbol, str]] = []
    lines = text.splitlines()
    brace_depth = 0
    pending_symbol_index: int | None = None
    symbol_stack: list[dict[str, Any]] = []

    def _close_completed_symbols(line_no: int, current_depth: int) -> None:
        while symbol_stack and current_depth < int(symbol_stack[-1]["exit_depth"]):
            completed = symbol_stack.pop()
            symbols[int(completed["index"])] = _Symbol(
                **(symbols[int(completed["index"])].__dict__ | {"end_line": line_no})
            )

    for line_no, line in enumerate(lines, start=1):
        stripped_line = line.strip()
        starting_depth = brace_depth
        open_count = line.count("{")
        close_count = line.count("}")
        ending_depth = max(0, starting_depth + open_count - close_count)
        if pending_symbol_index is None:
            symbol_match = SYMBOL_LINE_RE.match(stripped_line)
            if symbol_match is not None:
                symbol_kind = symbol_match.group("kind")
                symbol_name = symbol_match.group("name")
                symbol = _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": symbol_name,
                            "line": line_no,
                            "kind": symbol_kind,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=line_no,
                    end_line=line_no,
                    parent_symbol_id=None,
                    signature=symbol_name,
                )
                symbols.append(symbol)
                symbols_by_name[symbol_name].append(symbol)
                symbol_index = len(symbols) - 1
                if ending_depth > starting_depth:
                    symbol_stack.append(
                        {
                            "index": symbol_index,
                            "exit_depth": ending_depth,
                        }
                    )
                else:
                    pending_symbol_index = symbol_index
        brace_depth = ending_depth
        if pending_symbol_index is not None and brace_depth > starting_depth:
            symbol_stack.append(
                {
                    "index": pending_symbol_index,
                    "exit_depth": brace_depth,
                }
            )
            pending_symbol_index = None
        _close_completed_symbols(line_no, brace_depth)

    final_line = len(lines) if lines else 1
    for stack_entry in symbol_stack:
        symbols[int(stack_entry["index"])] = _Symbol(
            **(symbols[int(stack_entry["index"])].__dict__ | {"end_line": final_line})
        )
    if pending_symbol_index is not None:
        symbols[pending_symbol_index] = _Symbol(
            **(symbols[pending_symbol_index].__dict__ | {"end_line": final_line})
        )

    for match in USE_RE.finditer(text):
        for full_path, alias in parse_use_targets(match.group("path")):
            target_file = resolve_module_path(
                current_file=file_path,
                module_path=full_path,
                module_index=module_index,
            )
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {"file_path": file_path, "target": full_path, "alias": alias},
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=alias,
                    dependency_type="imports",
                )
            )
            import_bindings[alias] = _ImportedSymbolBinding(
                alias=alias,
                target_file=target_file,
                target_names=(full_path.rsplit("::", 1)[-1], alias),
            )
    for match in MOD_RE.finditer(text):
        module_name = match.group("name")
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "module": module_name, "kind": "mod"},
                ),
                source_file=file_path,
                target_file=resolve_child_module(
                    current_file=file_path,
                    module_name=module_name,
                    module_index=module_index,
                ),
                target_symbol=module_name,
                dependency_type="imports",
            )
        )

    for symbol in symbols:
        start_index = max(symbol.start_line - 1, 0)
        end_index = min(symbol.end_line, len(lines))
        symbol_ranges.append((symbol, "\n".join(lines[start_index:end_index])))

    for symbol, snippet in symbol_ranges:
        for match in CALL_RE.finditer(snippet):
            target_name = match.group(1)
            binding = import_bindings.get(target_name)
            if binding is not None:
                edge_id = stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol.symbol_id,
                        "target_file": binding.target_file,
                        "target_names": binding.target_names,
                        "type": "references_symbol",
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_symbol_id=symbol.symbol_id,
                        source_file=file_path,
                        target_symbol_id=None,
                        target_file=binding.target_file,
                        target_names=binding.target_names,
                        reference_type="references_symbol",
                    ),
                )
                continue
            for target_symbol in symbols_by_name.get(target_name, ()):
                if target_symbol.symbol_id == symbol.symbol_id:
                    continue
                edge_id = stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol.symbol_id,
                        "target_symbol_id": target_symbol.symbol_id,
                        "type": "references_symbol",
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_symbol_id=symbol.symbol_id,
                        source_file=file_path,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=file_path,
                        target_names=(target_symbol.symbol_name,),
                        reference_type="references_symbol",
                    ),
                )

    return (
        tuple(symbols),
        tuple(dependencies),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
