from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    cython_primitives as repository_cython_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_cython_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_cython_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_cython_primitives.ResolveSuffixMatch

_CALL_RE = repository_cython_primitives._CALL_RE
_QUALIFIED_CALL_RE = repository_cython_primitives._QUALIFIED_CALL_RE
_RESERVED_SYMBOL_NAMES = repository_cython_primitives._RESERVED_SYMBOL_NAMES

collect_symbols = repository_cython_primitives.collect_symbols
has_cython_path_hints = repository_cython_primitives.has_cython_path_hints
import_statements = repository_cython_primitives.import_statements
include_statements = repository_cython_primitives.include_statements
imported_symbol_bindings = repository_cython_primitives.imported_symbol_bindings
is_probable_cython_source = repository_cython_primitives.is_probable_cython_source
module_aliases_for_path = repository_cython_primitives.module_aliases_for_path
module_name_from_path = repository_cython_primitives.module_name_from_path
normalize_identifier = repository_cython_primitives.normalize_identifier
resolve_import = repository_cython_primitives.resolve_import
resolve_include = repository_cython_primitives.resolve_include
strip_comments = repository_cython_primitives.strip_comments


def _extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    bindings = imported_symbol_bindings(
        current_file=file_path,
        text=text,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str | None, str]] = set()
    for include_target, line_number in include_statements(text):
        target_file = resolve_include(
            current_file=file_path,
            include_target=include_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, Path(include_target).stem or None, "includes")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": include_target,
                        "kind": "includes",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=Path(include_target).stem or None,
                dependency_type="includes",
            )
        )
    for import_kind, module_name, target_name, _alias_name, line_number in import_statements(text):
        target_file = resolve_import(
            current_file=file_path,
            import_target=module_name or target_name,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        resolved_target_name = normalize_identifier(
            target_name if import_kind in {"from_cimport", "from_import"} else module_name or target_name
        )
        dependency_key = (target_file, resolved_target_name or None, "imports")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "module": module_name,
                        "target": target_name,
                        "kind": import_kind,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=resolved_target_name or None,
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
) -> tuple[_Dependency, ...]:
    dependencies, _bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
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
    if not is_probable_cython_source(path=Path(file_path), text=text):
        return (), (), ()

    symbols = collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    dependencies, import_bindings = _extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    local_symbol_lookup = {
        symbol.symbol_name: symbol.symbol_id
        for symbol in symbols
        if symbol.symbol_kind != "module"
    }
    local_symbol_names = set(local_symbol_lookup)
    stripped_text = strip_comments(text)
    lines = stripped_text.splitlines()
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str]] = set()

    def _append_reference(
        *,
        source_symbol: _Symbol,
        target_file: str | None,
        target_name: str,
        target_symbol_id: str | None,
    ) -> None:
        normalized_target_name = normalize_identifier(target_name)
        if not normalized_target_name:
            return
        reference_key = (target_file, normalized_target_name, source_symbol.symbol_id)
        if reference_key in seen_reference_keys:
            return
        seen_reference_keys.add(reference_key)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": source_symbol.symbol_id,
                        "target_file": target_file,
                        "target_name": normalized_target_name,
                    },
                ),
                source_symbol_id=source_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=(normalized_target_name,),
                reference_type="references_symbol",
            )
        )

    for symbol in symbols:
        if symbol.symbol_kind == "module":
            continue
        snippet = "\n".join(
            lines[max(symbol.start_line - 1, 0) : max(symbol.end_line, symbol.start_line)]
        )
        for match in _QUALIFIED_CALL_RE.finditer(snippet):
            owner = normalize_identifier(str(match.group("owner") or ""))
            target_name = normalize_identifier(str(match.group("name") or ""))
            binding = import_bindings.get(owner)
            if binding is None or not target_name:
                continue
            _append_reference(
                source_symbol=symbol,
                target_file=binding.target_file,
                target_name=target_name,
                target_symbol_id=None,
            )
        for match in _CALL_RE.finditer(snippet):
            target_name = normalize_identifier(str(match.group("name") or ""))
            if (
                not target_name
                or target_name in _RESERVED_SYMBOL_NAMES
                or target_name == symbol.symbol_name
            ):
                continue
            if target_name in local_symbol_names:
                _append_reference(
                    source_symbol=symbol,
                    target_file=file_path,
                    target_name=target_name,
                    target_symbol_id=local_symbol_lookup.get(target_name),
                )
                continue
            binding = import_bindings.get(target_name)
            if binding is None:
                continue
            resolved_name = binding.target_names[0] if binding.target_names else target_name
            _append_reference(
                source_symbol=symbol,
                target_file=binding.target_file,
                target_name=resolved_name,
                target_symbol_id=None,
            )
    return symbols, dependencies, tuple(symbol_references)
