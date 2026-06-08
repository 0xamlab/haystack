from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    solidity_primitives as repository_solidity_primitives,
)

StableIdentifier = repository_solidity_primitives.StableIdentifier
ResolveImport = repository_solidity_primitives.ResolveImport

_KNOWN_SOLIDITY_SUFFIXES = repository_solidity_primitives._KNOWN_SOLIDITY_SUFFIXES
IMPORT_RE = repository_solidity_primitives.IMPORT_RE
CONTRACT_DECL_RE = repository_solidity_primitives.CONTRACT_DECL_RE
USING_RE = repository_solidity_primitives.USING_RE
QUALIFIED_REFERENCE_RE = repository_solidity_primitives.QUALIFIED_REFERENCE_RE
NEW_REFERENCE_RE = repository_solidity_primitives.NEW_REFERENCE_RE
INHERITANCE_ITEM_RE = repository_solidity_primitives.INHERITANCE_ITEM_RE

normalize_identifier = repository_solidity_primitives.normalize_identifier
normalize_import_target = repository_solidity_primitives.normalize_import_target
_is_candidate_symbol_name = repository_solidity_primitives._is_candidate_symbol_name
_path_aliases = repository_solidity_primitives._path_aliases
_package_name_prefixes = repository_solidity_primitives._package_name_prefixes
_line_number = repository_solidity_primitives._line_number
collect_symbol_entries = repository_solidity_primitives.collect_symbol_entries
resolve_import = repository_solidity_primitives.resolve_import
strip_comments = repository_solidity_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SOLIDITY_SUFFIXES:
        return set()
    aliases, source_relative_aliases = _path_aliases(path)
    for prefix in _package_name_prefixes(root_path):
        for relative_alias in source_relative_aliases:
            aliases.add(f"{prefix}/{relative_alias}")
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return aliases
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(
            str(alias)
            for alias in symbol_entry.get("qualified_names", ())
            if alias
        )
    return {alias for alias in aliases if alias}


def _append_dependency(
    dependency_entries: list[dict[str, Any]],
    dependency_keys: set[tuple[str | None, str, str]],
    *,
    file_path: str,
    target_file: str | None,
    target_symbol: str,
    dependency_type: str,
    stable_identifier: StableIdentifier,
    position: int,
) -> None:
    normalized_target_symbol = normalize_identifier(target_symbol)
    if not normalized_target_symbol:
        return
    dependency_key = (target_file, normalized_target_symbol, dependency_type)
    if dependency_key in dependency_keys:
        return
    dependency_keys.add(dependency_key)
    dependency_entries.append(
        {
            "dependency_edge_id": stable_identifier(
                "dep",
                {
                    "file_path": file_path,
                    "target": normalized_target_symbol,
                    "line": position,
                    "type": dependency_type,
                },
            ),
            "source_file": file_path,
            "target_file": target_file,
            "target_symbol": normalized_target_symbol,
            "dependency_type": dependency_type,
        }
    )


def _module_index_aliases_for_file(
    module_index: dict[str, str],
    target_file: str,
) -> set[str]:
    return {
        alias
        for alias, file_path in module_index.items()
        if file_path == target_file and "/" not in alias
    }


def _parse_import_context(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import_fn: ResolveImport,
) -> tuple[
    tuple[dict[str, Any], ...],
    dict[str, dict[str, Any]],
    dict[str, str],
    set[str],
]:
    stripped_text = strip_comments(text)
    dependencies: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, dict[str, Any]] = {}
    namespace_imports: dict[str, str] = {}
    imported_files: set[str] = set()
    for match in IMPORT_RE.finditer(stripped_text):
        import_target = normalize_import_target(str(match.group("target") or ""))
        if not import_target:
            continue
        target_file = resolve_import_fn(import_target)
        if target_file is not None:
            imported_files.add(target_file)
        _append_dependency(
            dependencies,
            dependency_keys,
            file_path=file_path,
            target_file=target_file,
            target_symbol=PurePosixPath(import_target).stem or import_target,
            dependency_type="imports",
            stable_identifier=stable_identifier,
            position=_line_number(stripped_text, match.start()),
        )
        namespace_alias = normalize_identifier(str(match.group("namespace") or ""))
        if namespace_alias and target_file is not None:
            namespace_imports[namespace_alias] = target_file
            continue
        braced_body = str(match.group("braced") or "").strip()
        if not braced_body or target_file is None:
            continue
        for raw_entry in braced_body.split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            source_name, alias_name = entry, entry
            alias_match = re.match(
                r"^(?P<source>[A-Za-z_][A-Za-z0-9_]*)\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)$",
                entry,
                re.IGNORECASE,
            )
            if alias_match is not None:
                source_name = str(alias_match.group("source") or "")
                alias_name = str(alias_match.group("alias") or "")
            normalized_source_name = normalize_identifier(source_name)
            normalized_alias_name = normalize_identifier(alias_name)
            if not _is_candidate_symbol_name(normalized_alias_name):
                continue
            import_bindings[normalized_alias_name] = {
                "target_file": target_file,
                "target_names": (normalized_source_name,),
            }
    return (
        tuple(dependencies),
        import_bindings,
        namespace_imports,
        imported_files,
    )


def _resolve_reference_binding(
    reference_name: str,
    *,
    current_file: str,
    import_bindings: dict[str, dict[str, Any]],
    imported_files: set[str],
    module_index: dict[str, str],
) -> tuple[str | None, tuple[str, ...]]:
    binding = import_bindings.get(reference_name)
    if binding is not None:
        target_file = str(binding["target_file"])
        if target_file and target_file != current_file:
            return target_file, tuple(str(name) for name in binding["target_names"])
    for target_file in sorted(imported_files):
        if target_file == current_file:
            continue
        if reference_name in _module_index_aliases_for_file(module_index, target_file):
            return target_file, (reference_name,)
    direct_match = module_index.get(reference_name)
    if direct_match is not None and direct_match != current_file:
        return direct_match, (reference_name,)
    direct_file_match = module_index.get(f"{reference_name}.sol")
    if direct_file_match is not None and direct_file_match != current_file:
        return direct_file_match, (reference_name,)
    return None, (reference_name,)


def _reference_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import_fn: ResolveImport,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    import_dependencies, import_bindings, namespace_imports, imported_files = (
        _parse_import_context(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import_fn=resolve_import_fn,
        )
    )
    stripped_text = strip_comments(text)
    bindings: list[dict[str, Any]] = []
    seen_bindings: set[tuple[int, str, tuple[str, ...]]] = set()

    def _append_binding(
        *,
        line_no: int,
        target_file: str | None,
        target_names: tuple[str, ...],
    ) -> None:
        if target_file is None or target_file == file_path or not target_names:
            return
        binding_key = (line_no, target_file, target_names)
        if binding_key in seen_bindings:
            return
        seen_bindings.add(binding_key)
        bindings.append(
            {
                "line_no": line_no,
                "target_file": target_file,
                "target_names": target_names,
                "target_symbol": target_names[0],
            }
        )

    for match in CONTRACT_DECL_RE.finditer(stripped_text):
        inherits_body = str(match.group("inherits") or "").strip()
        if not inherits_body:
            continue
        line_no = _line_number(stripped_text, match.start())
        for inherit_match in INHERITANCE_ITEM_RE.finditer(inherits_body):
            reference_name = normalize_identifier(str(inherit_match.group("name") or ""))
            if not _is_candidate_symbol_name(reference_name):
                continue
            target_file, target_names = _resolve_reference_binding(
                reference_name,
                current_file=file_path,
                import_bindings=import_bindings,
                imported_files=imported_files,
                module_index=module_index,
            )
            _append_binding(
                line_no=line_no,
                target_file=target_file,
                target_names=target_names,
            )

    for match in USING_RE.finditer(stripped_text):
        reference_name = normalize_identifier(str(match.group("name") or ""))
        if not _is_candidate_symbol_name(reference_name):
            continue
        target_file, target_names = _resolve_reference_binding(
            reference_name,
            current_file=file_path,
            import_bindings=import_bindings,
            imported_files=imported_files,
            module_index=module_index,
        )
        _append_binding(
            line_no=_line_number(stripped_text, match.start()),
            target_file=target_file,
            target_names=target_names,
        )

    for match in QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        qualifier = normalize_identifier(str(match.group("qualifier") or ""))
        member_name = normalize_identifier(str(match.group("name") or ""))
        if not _is_candidate_symbol_name(qualifier):
            continue
        if qualifier in namespace_imports:
            _append_binding(
                line_no=_line_number(stripped_text, match.start()),
                target_file=namespace_imports[qualifier],
                target_names=tuple(name for name in (member_name, qualifier) if name),
            )
            continue
        target_file, target_names = _resolve_reference_binding(
            qualifier,
            current_file=file_path,
            import_bindings=import_bindings,
            imported_files=imported_files,
            module_index=module_index,
        )
        _append_binding(
            line_no=_line_number(stripped_text, match.start()),
            target_file=target_file,
            target_names=target_names,
        )

    for match in NEW_REFERENCE_RE.finditer(stripped_text):
        reference_name = normalize_identifier(str(match.group("name") or ""))
        if not _is_candidate_symbol_name(reference_name):
            continue
        target_file, target_names = _resolve_reference_binding(
            reference_name,
            current_file=file_path,
            import_bindings=import_bindings,
            imported_files=imported_files,
            module_index=module_index,
        )
        _append_binding(
            line_no=_line_number(stripped_text, match.start()),
            target_file=target_file,
            target_names=target_names,
        )

    return import_dependencies, tuple(bindings)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import_fn: ResolveImport,
) -> tuple[dict[str, Any], ...]:
    import_dependencies, reference_bindings = _reference_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import_fn=resolve_import_fn,
    )
    dependencies = list(import_dependencies)
    dependency_keys = {
        (entry["target_file"], entry["target_symbol"], entry["dependency_type"])
        for entry in dependencies
    }
    for binding in reference_bindings:
        dependency_key = (binding["target_file"], binding["target_symbol"], "references")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": binding["target_names"],
                        "line": binding["line_no"],
                        "type": "references",
                    },
                ),
                "source_file": file_path,
                "target_file": binding["target_file"],
                "target_symbol": binding["target_symbol"],
                "dependency_type": "references",
            }
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import_fn: ResolveImport,
) -> tuple[
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    symbol_entries = tuple(
        collect_symbol_entries(
            text,
            file_path=file_path,
            stable_identifier=stable_identifier,
        )
    )
    reference_bindings = _reference_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import_fn=resolve_import_fn,
    )[1]

    def _symbol_for_line(line_no: int) -> dict[str, Any] | None:
        for symbol_entry in reversed(symbol_entries):
            if int(symbol_entry["start_line"]) <= line_no <= int(symbol_entry["end_line"]):
                return symbol_entry
        return None

    reference_candidates: dict[str, dict[str, Any]] = {}
    for binding in reference_bindings:
        source_symbol = _symbol_for_line(int(binding["line_no"]))
        if source_symbol is None:
            continue
        edge_id = stable_identifier(
            "ref",
            {
                "source_symbol_id": source_symbol["symbol_id"],
                "target_file": binding["target_file"],
                "target_names": binding["target_names"],
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            {
                "reference_edge_id": edge_id,
                "source_symbol_id": str(source_symbol["symbol_id"]),
                "source_file": file_path,
                "target_symbol_id": None,
                "target_file": str(binding["target_file"]),
                "target_names": tuple(str(name) for name in binding["target_names"]),
                "reference_type": "references_symbol",
            },
        )
    return (
        symbol_entries,
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import_fn=resolve_import_fn,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
