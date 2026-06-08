from __future__ import annotations

import re
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
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveImport = Callable[..., str | None]

IMPORT_RE = re.compile(r'@import\(\s*"(?P<target>[^"]+)"\s*\)')
IMPORT_BINDING_RE = re.compile(
    r"\bconst\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*@import\(\s*\"(?P<target>[^\"]+)\"\s*\)"
)
TOP_LEVEL_CONST_RE = re.compile(r"^\s*pub\s+const\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
TOP_LEVEL_FUNCTION_RE = re.compile(r"^\s*pub\s+fn\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
SELECTOR_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*\.\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)


def candidate_module_keys(
    current_file: str,
    import_target: str,
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_target = import_target.strip()
    if not normalized_target:
        return ()
    current_parent = PurePosixPath(current_file).parent
    candidate_keys: list[str] = [normalized_target]
    if normalized_target.endswith(".zig"):
        relative_target = normalize_repository_relative_path(
            str((current_parent / normalized_target).as_posix())
        )
        candidate_keys.extend(
            [
                relative_target,
                normalized_target,
                normalized_target.removesuffix(".zig"),
            ]
        )
    else:
        normalized_path_target = normalized_target.replace(".", "/")
        candidate_keys.extend(
            [
                f"{normalized_target}.zig",
                f"src/{normalized_target}.zig",
                f"{normalized_target}/main.zig",
                f"{normalized_target}/root.zig",
                normalized_path_target,
                normalized_path_target + ".zig",
                normalized_path_target + "/main.zig",
                normalized_path_target + "/root.zig",
            ]
        )
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if normalized_candidate and normalized_candidate not in seen:
            seen.add(normalized_candidate)
            ordered.append(normalized_candidate)
    return tuple(ordered)


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target or normalized_target in {"std", "builtin", "root", "build"}:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    for candidate_key in candidate_module_keys(
        current_file,
        normalized_target,
        normalize_repository_relative_path=normalize_repository_relative_path,
    ):
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return None


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for match in IMPORT_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
        )
        dependency_key = (target_file, import_target)
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        target_symbol = PurePosixPath(import_target).name.removesuffix(".zig") or import_target
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": import_target, "line": match.start()},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="imports",
            )
        )
    for match in IMPORT_BINDING_RE.finditer(text):
        alias_name = str(match.group("alias") or "")
        import_target = str(match.group("target") or "").strip()
        import_bindings[alias_name] = _ImportedSymbolBinding(
            alias=alias_name,
            target_file=resolve_import(
                current_file=file_path,
                import_target=import_target,
                module_index=module_index,
            ),
            target_names=(),
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
    symbol_stack: list[dict[str, int]] = []
    pending_symbol_index: int | None = None
    lines = text.splitlines()
    brace_depth = 0
    for line_no, line in enumerate(lines, start=1):
        stripped_line = line.strip()
        starting_depth = brace_depth
        open_count = line.count("{")
        close_count = line.count("}")
        ending_depth = max(0, starting_depth + open_count - close_count)
        if starting_depth == 0:
            symbol_name: str | None = None
            symbol_kind: str | None = None
            if "@import(" not in stripped_line:
                const_match = TOP_LEVEL_CONST_RE.match(stripped_line)
                if const_match is not None:
                    symbol_name = str(const_match.group("name") or "")
                    symbol_kind = "const"
                else:
                    function_match = TOP_LEVEL_FUNCTION_RE.match(stripped_line)
                    if function_match is not None:
                        symbol_name = str(function_match.group("name") or "")
                        symbol_kind = "function"
            if symbol_name is not None and symbol_kind is not None:
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
                    }
                )
                symbol_index = len(symbol_entries) - 1
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
        while symbol_stack and brace_depth < int(symbol_stack[-1]["exit_depth"]):
            completed = symbol_stack.pop()
            symbol_entries[int(completed["index"])]["end_line"] = line_no
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
            parent_symbol_id=None,
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
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for index, symbol in enumerate(symbols):
        end_line = len(lines)
        if index + 1 < len(symbols):
            end_line = max(symbols[index + 1].start_line - 1, symbol.start_line)
        snippet = "\n".join(lines[symbol.start_line - 1 : end_line])
        for match in SELECTOR_REFERENCE_RE.finditer(snippet):
            binding = import_bindings.get(str(match.group("alias") or ""))
            if binding is None:
                continue
            target_name = str(match.group("name") or "")
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": binding.target_file,
                    "target_names": (target_name,),
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
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
