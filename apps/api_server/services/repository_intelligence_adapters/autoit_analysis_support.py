from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    autoit_primitives as repository_autoit_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_autoit_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_autoit_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_autoit_primitives.ResolveSuffixMatch

_CALL_RE = repository_autoit_primitives._CALL_RE
_QUALIFIED_CALL_RE = repository_autoit_primitives._QUALIFIED_CALL_RE
_RESERVED_SYMBOL_NAMES = repository_autoit_primitives._RESERVED_SYMBOL_NAMES

collect_symbols = repository_autoit_primitives.collect_symbols
has_autoit_path_hints = repository_autoit_primitives.has_autoit_path_hints
import_statements = repository_autoit_primitives.import_statements
imported_symbol_bindings = repository_autoit_primitives.imported_symbol_bindings
is_probable_autoit_source = repository_autoit_primitives.is_probable_autoit_source
module_aliases_for_path = repository_autoit_primitives.module_aliases_for_path
module_name_from_path = repository_autoit_primitives.module_name_from_path
normalize_identifier = repository_autoit_primitives.normalize_identifier
resolve_include = repository_autoit_primitives.resolve_include
strip_comments = repository_autoit_primitives.strip_comments


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
    stripped_text = (
        stripped_text
        if isinstance(stripped_text, str)
        else repository_autoit_primitives.strip_comments(text)
    )
    bindings = imported_symbol_bindings(
        current_file=file_path,
        text=text,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str]] = set()
    for import_target, line_number in import_statements(text, stripped_text=stripped_text):
        target_file = resolve_include(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
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
                        "kind": "imports",
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=Path(import_target).stem or None,
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
    stripped_text = repository_autoit_primitives.strip_comments(text)
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
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    stripped_text = repository_autoit_primitives.strip_comments(text)
    if not is_probable_autoit_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return (), (), ()

    symbols = collect_symbols(
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
                or target_name.casefold() in _RESERVED_SYMBOL_NAMES
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
