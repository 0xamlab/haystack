from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    odin_primitives as repository_odin_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_odin_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_odin_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_odin_primitives.ResolveSuffixMatch

ODIN_CONFIG_BASENAMES = repository_odin_primitives.ODIN_CONFIG_BASENAMES
ODIN_FILE_SUFFIXES = repository_odin_primitives.ODIN_FILE_SUFFIXES
RESERVED_SYMBOL_NAMES = repository_odin_primitives.RESERVED_SYMBOL_NAMES
_CollectedSymbol = repository_odin_primitives._CollectedSymbol
_line_count = repository_odin_primitives._line_count
_ordered_names = repository_odin_primitives._ordered_names
default_import_alias = repository_odin_primitives.default_import_alias
has_odin_path_hints = repository_odin_primitives.has_odin_path_hints
is_probable_odin_source = repository_odin_primitives.is_probable_odin_source
iter_symbol_entries = repository_odin_primitives.iter_symbol_entries
package_name_from_text = repository_odin_primitives.package_name_from_text
parse_import_statements = repository_odin_primitives.parse_import_statements
parse_reference_targets = repository_odin_primitives.parse_reference_targets
strip_comments = repository_odin_primitives.strip_comments


def _collection_style_aliases(file_path: str) -> tuple[str, ...]:
    path = PurePosixPath(file_path)
    parent = path.parent
    if parent in {PurePosixPath("."), PurePosixPath("")}:
        return ()
    parent_parts = parent.parts
    if len(parent_parts) < 2:
        return ()
    return (f"{parent_parts[0]}:{'/'.join(parent_parts[1:])}",)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    package_name = package_name_from_text(stripped_text, file_path=file_path)
    package_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": package_name, "symbol_kind": "package"},
        ),
        symbol_name=package_name,
        symbol_kind="package",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=package_name,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=package_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
            qualified_names=_ordered_names(
                package_name,
                file_path,
                str(PurePosixPath(file_path).with_suffix("")),
                PurePosixPath(file_path).stem,
                *_collection_style_aliases(file_path),
            ),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
        qualified_names = _ordered_names(
            symbol_name,
            f"{package_name}.{symbol_name}" if package_name else "",
        )
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": symbol_name,
                            "symbol_kind": symbol_kind,
                            "start_line": start_line,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=start_line,
                    end_line=start_line,
                    parent_symbol_id=package_symbol.symbol_id,
                    signature=symbol_name,
                ),
                local_start_line=start_line,
                local_end_line=start_line,
                qualified_names=qualified_names,
            )
        )
    final_line = _line_count(stripped_text)
    finalized: list[_CollectedSymbol] = []
    for index, collected_symbol in enumerate(collected_symbols):
        end_line = (
            max(
                collected_symbols[index + 1].local_start_line - 1,
                collected_symbol.local_start_line,
            )
            if index + 1 < len(collected_symbols)
            else final_line
        )
        symbol = collected_symbol.symbol
        finalized.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=symbol.symbol_id,
                    symbol_name=symbol.symbol_name,
                    symbol_kind=symbol.symbol_kind,
                    start_line=symbol.start_line,
                    end_line=end_line,
                    parent_symbol_id=symbol.parent_symbol_id,
                    signature=symbol.signature,
                ),
                local_start_line=collected_symbol.local_start_line,
                local_end_line=end_line,
                qualified_names=collected_symbol.qualified_names,
            )
        )
    return tuple(finalized)


def parse_ols_checker_paths(manifest_text: str) -> tuple[str, ...]:
    try:
        payload = json.loads(manifest_text)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, dict):
        return ()
    active_profile_name = str(payload.get("profile") or "").strip()
    checker_paths: list[str] = []
    for value in payload.get("checker_path", []):
        normalized = str(value or "").strip()
        if normalized:
            checker_paths.append(normalized)
    profiles = payload.get("profiles", [])
    if isinstance(profiles, list):
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            profile_name = str(profile.get("name") or "").strip()
            if active_profile_name and profile_name and profile_name != active_profile_name:
                continue
            for value in profile.get("checker_path", []):
                normalized = str(value or "").strip()
                if normalized:
                    checker_paths.append(normalized)
            if active_profile_name and profile_name == active_profile_name:
                break
    return tuple(dict.fromkeys(checker_paths))


def parse_ols_collections(manifest_text: str) -> tuple[str, ...]:
    try:
        payload = json.loads(manifest_text)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, dict):
        return ()
    collections = payload.get("collections", [])
    if not isinstance(collections, list):
        return ()
    paths: list[str] = []
    for collection in collections:
        if not isinstance(collection, dict):
            continue
        collection_path = str(collection.get("path") or "").strip()
        if collection_path:
            paths.append(collection_path)
    return tuple(dict.fromkeys(paths))


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    aliases = {file_path, str(path.with_suffix("")), path.stem}
    aliases.update(_collection_style_aliases(file_path))
    if path.name.lower() in ODIN_CONFIG_BASENAMES:
        return {alias for alias in aliases if alias}
    if path.suffix.lower() not in ODIN_FILE_SUFFIXES:
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_odin_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    package_name = package_name_from_text(text, file_path=file_path)
    aliases.add(package_name)
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip().rstrip("/")
    if not normalized_target:
        return None
    import_alias = default_import_alias(normalized_target)
    slash_target = normalized_target.replace(":", "/")
    candidate_targets = (
        normalized_target,
        slash_target,
        import_alias,
    )
    for candidate in candidate_targets:
        target_file = module_index.get(candidate)
        if target_file is not None:
            return target_file
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_targets)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    seen_dependency_keys: set[tuple[str, str | None]] = set()
    for import_target, explicit_alias, line_number in parse_import_statements(text):
        target_file = resolve_import(
            import_target,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        binding_alias = explicit_alias or default_import_alias(import_target)
        dependency_key = (import_target, target_file)
        if dependency_key not in seen_dependency_keys:
            seen_dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "line": line_number,
                            "type": "imports",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=binding_alias or import_target,
                    dependency_type="imports",
                )
            )
        if binding_alias:
            import_bindings[binding_alias] = _ImportedSymbolBinding(
                alias=binding_alias,
                target_file=target_file,
                target_names=_ordered_names(import_target, binding_alias),
            )
    return tuple(dependencies), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    _ = normalize_repository_relative_path
    dependencies, _bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
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
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    _ = normalize_repository_relative_path
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    package_name = package_name_from_text(text, file_path=file_path)
    symbol_name_to_id = {
        collected_symbol.symbol.symbol_name: collected_symbol.symbol.symbol_id
        for collected_symbol in collected_symbols
    }
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str | None, str, str]] = set()
    for qualifier, symbol_name, line_number in parse_reference_targets(text):
        if symbol_name in RESERVED_SYMBOL_NAMES:
            continue
        source_symbol = next(
            (
                collected_symbol.symbol
                for collected_symbol in reversed(collected_symbols)
                if collected_symbol.local_start_line <= line_number
                <= collected_symbol.local_end_line
            ),
            collected_symbols[0].symbol,
        )
        candidate_targets: list[tuple[str | None, str | None, tuple[str, ...]]] = []
        if qualifier:
            import_binding = import_bindings.get(qualifier)
            if import_binding is not None:
                candidate_targets.append(
                    (
                        import_binding.target_file,
                        None,
                        _ordered_names(symbol_name, f"{qualifier}.{symbol_name}"),
                    )
                )
            package_target = module_index.get(f"{qualifier}.{symbol_name}")
            if package_target is not None:
                candidate_targets.append(
                    (
                        package_target,
                        None,
                        _ordered_names(symbol_name, f"{qualifier}.{symbol_name}"),
                    )
                )
        else:
            if symbol_name in symbol_name_to_id:
                candidate_targets.append(
                    (file_path, symbol_name_to_id.get(symbol_name), (symbol_name,))
                )
            package_target = module_index.get(f"{package_name}.{symbol_name}")
            if package_target is not None:
                candidate_targets.append(
                    (
                        package_target,
                        None,
                        _ordered_names(symbol_name, f"{package_name}.{symbol_name}"),
                    )
                )
        for target_file, target_symbol_id, target_names in candidate_targets:
            reference_key = (
                source_symbol.symbol_id,
                target_symbol_id,
                target_file or "",
                "|".join(target_names),
            )
            if reference_key in seen_reference_keys:
                continue
            seen_reference_keys.add(reference_key)
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": source_symbol.symbol_id,
                    "target_file": target_file,
                    "target_names": target_names,
                    "type": "references_symbol",
                },
            )
            references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=edge_id,
                    source_symbol_id=source_symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=target_symbol_id,
                    target_file=target_file,
                    target_names=target_names,
                    reference_type="references_symbol",
                )
            )
    return (
        tuple(collected_symbol.symbol for collected_symbol in collected_symbols),
        dependencies,
        tuple(references),
    )
