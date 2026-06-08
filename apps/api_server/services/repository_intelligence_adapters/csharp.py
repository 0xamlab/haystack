from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

CollectTypeSymbolEntries = Callable[..., list[dict[str, Any]]]
ResolveDirectoryPrefixMatch = Callable[..., str | None]
ResolveSuffixMatch = Callable[..., str | None]
StableIdentifier = Callable[[str, Any], str]
ImportBindingsResult = tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding], str]

USING_RE = re.compile(
    r"^\s*using\s+(?P<target>[A-Za-z_][A-Za-z0-9_\.]+)\s*;",
    re.MULTILINE,
)
NAMESPACE_RE = re.compile(
    r"^\s*namespace\s+(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)\s*;?",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"(?:^|;)\s*(?:(?:public|protected|private|internal|abstract|sealed|partial|static|readonly|ref|unsafe)\s+)*"
    r"(?:class|interface|record|struct|enum|delegate)\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_]*)\b")


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
    resolve_directory_prefix_match: ResolveDirectoryPrefixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    namespace_path = normalized_target.replace(".", "/")
    direct = module_index.get(namespace_path)
    if direct is not None:
        return direct
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[namespace_path, f"{namespace_path}.cs", f"{normalized_target.split('.')[-1]}.cs"],
    )
    if resolved is not None:
        return resolved
    return resolve_directory_prefix_match(
        module_index=module_index,
        prefixes=[namespace_path, f"src/{namespace_path}"],
    )


def resolve_import_for_file(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    resolve_import: Callable[[str, dict[str, str]], str | None],
    normalize_repository_relative_path: Callable[[str], str],
) -> str | None:
    resolved = resolve_import(import_target, module_index)
    if resolved is None or resolved != current_file:
        return resolved
    namespace_path = import_target.strip().replace(".", "/")
    candidate_files = sorted(
        {
            normalized_candidate
            for normalized_candidate in (
                normalize_repository_relative_path(candidate)
                for candidate in module_index.values()
            )
            if normalized_candidate
        }
    )
    for prefix in (namespace_path, f"src/{namespace_path}"):
        normalized_prefix = normalize_repository_relative_path(prefix)
        if not normalized_prefix:
            continue
        prefix_with_separator = f"{normalized_prefix}/"
        for candidate_file in candidate_files:
            if candidate_file == current_file:
                continue
            if (
                candidate_file == normalized_prefix
                or candidate_file.startswith(prefix_with_separator)
            ):
                return candidate_file
    return None


def resolve_same_namespace_reference(
    *,
    current_file: str,
    current_namespace: str,
    type_name: str,
    module_index: dict[str, str],
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> str | None:
    normalized_type = type_name.strip()
    if not normalized_type or not current_namespace:
        return None
    resolved = resolve_import(f"{current_namespace}.{normalized_type}", module_index)
    if resolved is None or resolved == current_file:
        return None
    return resolved


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import_for_file: Callable[..., str | None],
) -> tuple[
    tuple[_Dependency, ...],
    dict[str, _ImportedSymbolBinding],
    str,
]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for match in USING_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        target_symbol = import_target.rsplit(".", 1)[-1]
        target_file = resolve_import_for_file(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
        )
        dependency_key = (target_file, target_symbol, "imports")
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
                target_symbol=target_symbol,
                dependency_type="imports",
            )
        )
        import_bindings.setdefault(
            target_symbol,
            _ImportedSymbolBinding(
                alias=target_symbol,
                target_file=target_file,
                target_names=(target_symbol,),
            ),
        )
    namespace_match = NAMESPACE_RE.search(text)
    current_namespace = (
        str(namespace_match.group("target") or "").strip() if namespace_match else ""
    )
    return tuple(dependencies), import_bindings, current_namespace


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    collect_type_symbol_entries: CollectTypeSymbolEntries,
    stable_identifier: StableIdentifier,
    extract_import_bindings: Callable[..., ImportBindingsResult],
    resolve_same_namespace_reference: Callable[..., str | None],
) -> tuple[_Dependency, ...]:
    dependencies, import_bindings, current_namespace = extract_import_bindings(
        file_path,
        text,
        module_index,
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_entries
    }
    if not current_namespace:
        return tuple(dependency_entries)
    declared_type_names = {
        str(entry["symbol_name"])
        for entry in collect_type_symbol_entries(
            text,
            file_path=file_path,
            regex=TYPE_DECL_RE,
        )
    }
    imported_short_names = {
        alias for alias in import_bindings if "." not in alias and alias not in declared_type_names
    }
    for match in TYPE_REFERENCE_RE.finditer(text):
        type_name = str(match.group("name") or "").strip()
        if type_name in declared_type_names or type_name in imported_short_names:
            continue
        target_file = resolve_same_namespace_reference(
            current_file=file_path,
            current_namespace=current_namespace,
            type_name=type_name,
            module_index=module_index,
        )
        dependency_key = (target_file, type_name, "references")
        if target_file is None or target_file == file_path or dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
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
    return tuple(dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    collect_type_symbol_entries: CollectTypeSymbolEntries,
    stable_identifier: StableIdentifier,
    extract_import_bindings: Callable[..., ImportBindingsResult],
    resolve_same_namespace_reference: Callable[..., str | None],
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
    _, import_bindings, current_namespace = extract_import_bindings(
        file_path,
        text,
        module_index,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    lines = text.splitlines()
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in TYPE_REFERENCE_RE.finditer(snippet):
            type_name = str(match.group("name") or "").strip()
            if type_name in declared_symbol_names or type_name == symbol.symbol_name:
                continue
            binding = import_bindings.get(type_name)
            target_file = binding.target_file if binding is not None else None
            if target_file is None and current_namespace:
                target_file = resolve_same_namespace_reference(
                    current_file=file_path,
                    current_namespace=current_namespace,
                    type_name=type_name,
                    module_index=module_index,
                )
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
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            collect_type_symbol_entries=collect_type_symbol_entries,
            stable_identifier=stable_identifier,
            extract_import_bindings=extract_import_bindings,
            resolve_same_namespace_reference=resolve_same_namespace_reference,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
