from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

CollectTypeSymbolEntries = Callable[..., list[dict[str, Any]]]
ResolveSuffixMatch = Callable[..., str | None]
ResolveSameTargetReference = Callable[..., str | None]
StableIdentifier = Callable[[str, Any], str]

IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<target>[A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:(?:public|internal|fileprivate|private|open|final|indirect)\s+)*"
    r"(?:class|struct|enum|protocol|actor|typealias)\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_]*)\b")


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[f"Sources/{normalized_target}", f"Sources/{normalized_target}/main.swift"],
    )


def resolve_same_target_reference(
    *,
    current_file: str,
    type_name: str,
    module_index: dict[str, str],
    module_index_values: Callable[[dict[str, str]], Sequence[str]],
) -> str | None:
    normalized_type = type_name.strip()
    if not normalized_type:
        return None
    current_path = PurePosixPath(current_file)
    target_root: str | None = None
    parts = list(current_path.parts)
    for marker in ("Sources", "Tests", "Plugins", "Tools"):
        if marker in parts:
            marker_index = parts.index(marker)
            if marker_index + 1 < len(parts):
                target_root = "/".join(parts[: marker_index + 2])
                break
    direct = module_index.get(normalized_type)
    if direct is not None and direct != current_file and direct.endswith(".swift"):
        if target_root is None or direct.startswith(f"{target_root}/"):
            return direct
    matches = [
        file_path
        for file_path in module_index_values(module_index)
        if file_path != current_file
        and file_path.endswith(".swift")
        and PurePosixPath(file_path).stem == normalized_type
        and (target_root is None or file_path.startswith(f"{target_root}/"))
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _cached_same_target_reference_resolver(
    *,
    current_file: str,
    module_index: dict[str, str],
    resolve_same_target_reference: ResolveSameTargetReference,
) -> Callable[[str], str | None]:
    cache: dict[str, str | None] = {}

    def _resolve(type_name: str) -> str | None:
        normalized_type = str(type_name or "").strip()
        if not normalized_type:
            return None
        if normalized_type not in cache:
            cache[normalized_type] = resolve_same_target_reference(
                current_file=current_file,
                type_name=normalized_type,
                module_index=module_index,
            )
        return cache[normalized_type]

    return _resolve


def _parse_dependencies_only_with_cached_resolver(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
    resolve_same_target_reference_cached: Callable[[str], str | None],
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for match in IMPORT_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        target_file = resolve_import(import_target, module_index)
        dependency_key = (target_file, import_target, "imports")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": import_target, "line": match.start()},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=import_target,
                dependency_type="imports",
            )
        )
    declared_type_names = {match.group("name") for match in TYPE_DECL_RE.finditer(text)}
    for match in TYPE_REFERENCE_RE.finditer(text):
        type_name = str(match.group("name") or "").strip()
        if type_name in declared_type_names:
            continue
        target_file = resolve_same_target_reference_cached(type_name)
        dependency_key = (target_file, type_name, "references")
        if target_file is None or dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": type_name, "line": match.start()},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=type_name,
                dependency_type="references",
            )
        )
    return tuple(dependencies)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
    resolve_same_target_reference: ResolveSameTargetReference,
) -> tuple[_Dependency, ...]:
    return _parse_dependencies_only_with_cached_resolver(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
        resolve_same_target_reference_cached=_cached_same_target_reference_resolver(
            current_file=file_path,
            module_index=module_index,
            resolve_same_target_reference=resolve_same_target_reference,
        ),
    )


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    collect_type_symbol_entries: CollectTypeSymbolEntries,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
    resolve_same_target_reference: ResolveSameTargetReference,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    symbol_entries = collect_type_symbol_entries(
        text,
        file_path=file_path,
        regex=TYPE_DECL_RE,
    )
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
    declared_symbol_names = {symbol.symbol_name for symbol in symbols}
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    lines = text.splitlines()
    resolve_same_target_reference_cached = _cached_same_target_reference_resolver(
        current_file=file_path,
        module_index=module_index,
        resolve_same_target_reference=resolve_same_target_reference,
    )
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in TYPE_REFERENCE_RE.finditer(snippet):
            type_name = str(match.group("name") or "").strip()
            if type_name in declared_symbol_names or type_name == symbol.symbol_name:
                continue
            target_file = resolve_same_target_reference_cached(type_name)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": target_file,
                    "target_names": (type_name,),
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
                    target_file=target_file,
                    target_names=(type_name,),
                    reference_type="references_symbol",
                ),
            )
    return (
        symbols,
        _parse_dependencies_only_with_cached_resolver(
            file_path=file_path,
            text=text,
            module_index=module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
            resolve_same_target_reference_cached=resolve_same_target_reference_cached,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
