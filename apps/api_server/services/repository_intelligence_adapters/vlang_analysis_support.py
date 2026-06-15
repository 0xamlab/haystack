from __future__ import annotations

from pathlib import PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    vlang_primitives as repository_vlang_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_vlang_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_vlang_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_vlang_primitives.ResolveSuffixMatch


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    return repository_vlang_primitives.resolve_import(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )


def module_aliases_for_path(
    *,
    root_path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
) -> set[str]:
    return repository_vlang_primitives.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=stable_identifier,
        text=text,
        stripped_text=stripped_text,
    )


def _extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    bindings = repository_vlang_primitives.imported_symbol_bindings(
        text=text,
        file_path=file_path,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str]] = set()
    for import_target in repository_vlang_primitives.import_targets_for_text(
        text,
        stripped_text=stripped_text,
    ):
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        target_symbol = PurePosixPath(import_target.replace(".", "/")).name or import_target
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": import_target, "line": import_target},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="imports",
            )
        )
    return tuple(dependencies), bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[_Dependency, ...]:
    stripped_text = (
        repository_vlang_primitives.strip_comments(text)
        if stripped_text is None
        else stripped_text
    )
    dependencies, _bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    return dependencies


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    stripped_text = (
        repository_vlang_primitives.strip_comments(text)
        if stripped_text is None
        else stripped_text
    )
    symbols = repository_vlang_primitives.collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    dependencies, import_bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )

    local_symbol_names = {symbol.symbol_name for symbol in symbols}
    local_symbol_lookup = {symbol.symbol_name: symbol.symbol_id for symbol in symbols}
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str | None, str | None]] = set()
    lines = stripped_text.splitlines()

    for symbol in symbols:
        snippet = "\n".join(
            lines[max(symbol.start_line - 1, 0) : max(symbol.end_line, symbol.start_line)]
        )
        for match in repository_vlang_primitives._QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias_name = str(match.group("alias") or "").strip()
            target_name = str(match.group("name") or "").strip()
            imported_binding = import_bindings.get(alias_name)
            if imported_binding is None or not target_name:
                continue
            candidate_key = (
                imported_binding.target_file,
                target_name,
                symbol.symbol_id,
                symbol.symbol_name,
            )
            if candidate_key in seen_reference_keys:
                continue
            seen_reference_keys.add(candidate_key)
            symbol_references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "file_path": file_path,
                            "source_symbol_id": symbol.symbol_id,
                            "target_file": imported_binding.target_file,
                            "target_name": target_name,
                        },
                    ),
                    source_symbol_id=symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=imported_binding.target_file,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                )
            )

        for match in repository_vlang_primitives._CALL_RE.finditer(snippet):
            target_name = str(match.group("name") or "").strip()
            if (
                not target_name
                or target_name in repository_vlang_primitives._RESERVED_SYMBOL_NAMES
                or target_name not in local_symbol_names
                or target_name == symbol.symbol_name
            ):
                continue
            candidate_key = (file_path, target_name, symbol.symbol_id, symbol.symbol_name)
            if candidate_key in seen_reference_keys:
                continue
            seen_reference_keys.add(candidate_key)
            symbol_references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "file_path": file_path,
                            "source_symbol_id": symbol.symbol_id,
                            "target_file": file_path,
                            "target_name": target_name,
                        },
                    ),
                    source_symbol_id=symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=local_symbol_lookup.get(target_name),
                    target_file=file_path,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                )
            )

    return symbols, dependencies, tuple(symbol_references)
