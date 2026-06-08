from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
ResolveImport = Callable[[str, dict[str, str]], str | None]

IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z0-9_\.]+)", re.MULTILINE)
FROM_IMPORT_RE = re.compile(
    r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+([A-Za-z0-9_,\s\.]+)",
    re.MULTILINE,
)
SYMBOL_RE = re.compile(
    r"^\s*(?P<kind>fn|def|class|struct|trait|alias)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)
SELECTOR_CALL_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def resolve_import(import_target: str, module_index: dict[str, str]) -> str | None:
    direct_match = module_index.get(import_target)
    if direct_match is not None:
        return direct_match
    normalized_target = import_target.replace(".", "/")
    for key in (normalized_target, import_target):
        resolved = module_index.get(key)
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
    import_bindings: dict[str, _ImportedSymbolBinding] = {}

    for match in IMPORT_RE.finditer(text):
        target = str(match.group(1) or "")
        alias_name = target.rsplit(".", 1)[-1]
        target_file = resolve_import(target, module_index)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"target": target, "alias": alias_name},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=alias_name,
                dependency_type="imports",
            )
        )
        import_bindings[alias_name] = _ImportedSymbolBinding(
            alias=alias_name,
            target_file=target_file,
            target_names=(alias_name,),
        )

    for match in FROM_IMPORT_RE.finditer(text):
        module_name = str(match.group(1) or "")
        raw_names = str(match.group(2) or "")
        for entry in raw_names.split(","):
            name = entry.strip()
            if not name:
                continue
            if " as " in name:
                source_name, alias_name = re.split(r"\s+as\s+", name, maxsplit=1)
            else:
                source_name, alias_name = name, name
            full_target = f"{module_name}.{source_name}"
            target_file = resolve_import(full_target, module_index)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {"target": full_target, "alias": alias_name},
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=alias_name,
                    dependency_type="imports",
                )
            )
            import_bindings[alias_name] = _ImportedSymbolBinding(
                alias=alias_name,
                target_file=target_file,
                target_names=(source_name,),
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
    symbols: list[_Symbol] = []
    symbols_by_name: dict[str, list[_Symbol]] = defaultdict(list)
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for match in SYMBOL_RE.finditer(text):
        line = text[: match.start()].count("\n") + 1
        name = str(match.group("name") or "")
        kind = str(match.group("kind") or "")
        symbol = _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {"file_path": file_path, "name": name, "line": line, "kind": kind}
            ),
            symbol_name=name,
            symbol_kind=kind,
            start_line=line,
            end_line=line,
            parent_symbol_id=None,
            signature=name,
        )
        symbols.append(symbol)
        symbols_by_name[name].append(symbol)
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    lines = text.splitlines()
    symbol_ranges: list[tuple[_Symbol, str]] = []
    for index, symbol in enumerate(symbols):
        end_line = len(lines)
        if index + 1 < len(symbols):
            end_line = max(symbols[index + 1].start_line - 1, symbol.start_line)
        symbol_ranges.append((symbol, "\n".join(lines[symbol.start_line - 1 : end_line])))

    for symbol, snippet in symbol_ranges:
        for match in SELECTOR_CALL_RE.finditer(snippet):
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
        for match in CALL_RE.finditer(snippet):
            target_name = str(match.group(1) or "")
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
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
