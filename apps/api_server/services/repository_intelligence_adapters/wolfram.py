from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    wolfram_support as repository_wolfram_support,
)
from apps.api_server.services.repository_intelligence_adapters.wolfram_support import (
    _KNOWN_WOLFRAM_SUFFIXES,
    RESERVED_SYMBOL_NAMES,
    _canonical_symbol_name,
    _current_package_context,
    _extract_begin_package_imports,
    _extract_context_import_targets,
    _extract_declared_symbol_aliases,
    _extract_declared_symbols,
    _extract_relative_file_targets,
    _package_file_context,
    _path_aliases,
    _qualified_symbol_contexts,
    _reference_names,
    _resolve_import_target,
    _resolve_reference_target,
    is_probable_wolfram_source,
    normalize_context_name,
    strip_comments,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
NormalizeRepositoryRelativePath = Callable[[str], str]

has_wolfram_path_hints = repository_wolfram_support.has_wolfram_path_hints
paclet_kernel_entries = repository_wolfram_support.paclet_kernel_entries


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_WOLFRAM_SUFFIXES:
        return set()
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return set()
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    if not is_probable_wolfram_source(path=path, text=text, stripped_text=stripped_text):
        return set()
    current_package = _current_package_context(stripped_text)
    aliases = _path_aliases(path)
    for package_alias in _package_file_context(current_package, path.stem):
        aliases.add(package_alias)
    for qualified_symbol in _qualified_symbol_contexts(stripped_text):
        for package_alias in _package_file_context(qualified_symbol, path.stem):
            aliases.add(package_alias)
    for symbol_name, qualified_name in _extract_declared_symbol_aliases(
        stripped_text,
        current_package=current_package,
    ):
        if symbol_name:
            aliases.add(symbol_name)
            aliases.add(f"{path.stem}.{symbol_name}")
        if qualified_name:
            aliases.add(qualified_name)
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stripped_text: str | None = None,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if stripped_text is None:
        stripped_text = strip_comments(text)
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str]] = set()
    for context_name in _extract_begin_package_imports(stripped_text):
        target_file = _resolve_import_target(
            current_file=file_path,
            import_target=context_name,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, context_name, "imports")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": context_name,
                        "kind": "imports",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=context_name,
                dependency_type="imports",
            )
        )
    for head, import_target, line_no in _extract_context_import_targets(stripped_text):
        dependency_type = "imports" if head == "needs" else "loads"
        target_file = _resolve_import_target(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, dependency_type)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "kind": dependency_type,
                        "line": line_no,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=import_target,
                dependency_type=dependency_type,
            )
        )
    current_dir = PurePosixPath(file_path).parent
    for relative_target, line_no in _extract_relative_file_targets(stripped_text):
        normalized_target = normalize_repository_relative_path(str(current_dir / relative_target))
        target_file = _resolve_import_target(
            current_file=file_path,
            import_target=normalized_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, normalized_target, "loads")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": normalized_target,
                        "kind": "loads",
                        "line": line_no,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=normalized_target,
                dependency_type="loads",
            )
        )
    return tuple(dependencies)


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
    stripped_text = strip_comments(text)
    current_package = _current_package_context(stripped_text)
    imported_contexts = tuple(
        dict.fromkeys(
            (
                *(_extract_begin_package_imports(stripped_text)),
                *(
                    normalize_context_name(import_target)
                    for _head, import_target, _line_no in _extract_context_import_targets(
                        stripped_text
                    )
                    if "`" in import_target
                ),
            )
        )
    )
    symbol_entries = _extract_declared_symbols(
        stripped_text,
        current_package=current_package,
        include_message_definitions=False,
    )
    symbols = tuple(
        _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "name": str(entry["qualified_name"] or entry["symbol_name"]),
                    "kind": str(entry["symbol_kind"]),
                    "line": int(entry["start_line"]),
                },
            ),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=None,
            signature=str(entry["signature"]),
        )
        for entry in symbol_entries
    )
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stripped_text=stripped_text,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    local_symbol_names = {str(entry["symbol_name"]).lower() for entry in symbol_entries}
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    lines = stripped_text.splitlines()
    symbol_ids_by_name = {
        str(entry["qualified_name"] or entry["symbol_name"]): stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "name": str(entry["qualified_name"] or entry["symbol_name"]),
                "kind": str(entry["symbol_kind"]),
                "line": int(entry["start_line"]),
            },
        )
        for entry in symbol_entries
    }
    for entry in symbol_entries:
        source_symbol_id = symbol_ids_by_name[
            str(entry["qualified_name"] or entry["symbol_name"])
        ]
        start_line = int(entry["start_line"])
        end_line = int(entry["end_line"])
        snippet = "\n".join(lines[start_line - 1 : end_line])
        for reference_name, _offset in _reference_names(snippet):
            canonical_name = _canonical_symbol_name(reference_name)
            if (
                not canonical_name
                or canonical_name in RESERVED_SYMBOL_NAMES
                or canonical_name in local_symbol_names
                or canonical_name == str(entry["symbol_name"]).lower()
            ):
                continue
            target_file, target_names = _resolve_reference_target(
                current_file=file_path,
                symbol_name=reference_name,
                current_package=current_package,
                imported_contexts=imported_contexts,
                module_index=module_index,
            )
            if target_file is None or target_file == file_path:
                continue
            reference_edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": source_symbol_id,
                    "target_file": target_file,
                    "target_names": target_names or (reference_name,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                reference_edge_id,
                _SymbolReferenceCandidate(
                    reference_edge_id=reference_edge_id,
                    source_symbol_id=source_symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=target_names or (reference_name,),
                    reference_type="references_symbol",
                ),
            )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
