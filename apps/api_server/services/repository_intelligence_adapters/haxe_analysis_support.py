from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    haxe_primitives as repository_haxe_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_haxe_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_haxe_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_haxe_primitives.ResolveSuffixMatch

_CALL_RE = repository_haxe_primitives._CALL_RE
_NEW_RE = repository_haxe_primitives._NEW_RE
_QUALIFIED_REFERENCE_RE = repository_haxe_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_haxe_primitives._RESERVED_SYMBOL_NAMES
_TYPE_REFERENCE_RE = repository_haxe_primitives._TYPE_REFERENCE_RE

collect_symbols = repository_haxe_primitives.collect_symbols
has_haxe_path_hints = repository_haxe_primitives.has_haxe_path_hints
import_statements = repository_haxe_primitives.import_statements
imported_symbol_bindings = repository_haxe_primitives.imported_symbol_bindings
is_probable_haxe_source = repository_haxe_primitives.is_probable_haxe_source
module_aliases_for_path = repository_haxe_primitives.module_aliases_for_path
module_name_for_file = repository_haxe_primitives.module_name_for_file
resolve_import = repository_haxe_primitives.resolve_import
strip_comments = repository_haxe_primitives.strip_comments


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
        text=text,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for dependency_kind, import_target, _alias, line_number in import_statements(text):
        target_file = resolve_import(
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, dependency_kind)
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "kind": dependency_kind,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=import_target.rsplit(".", 1)[-1] or import_target,
                dependency_type="imports" if dependency_kind == "import" else "uses",
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
    if not is_probable_haxe_source(path=Path(file_path), text=text):
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

    local_symbol_names = {symbol.symbol_name for symbol in symbols}
    local_symbol_lookup = {symbol.symbol_name: symbol.symbol_id for symbol in symbols}
    stripped_text = strip_comments(text)
    lines = stripped_text.splitlines()
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, str, str | None, str | None]] = set()

    def _append_reference(
        *,
        source_symbol: _Symbol,
        target_file: str | None,
        target_name: str,
        target_symbol_id: str | None,
    ) -> None:
        if not target_name:
            return
        candidate_key = (
            target_file,
            target_name,
            source_symbol.symbol_id,
            source_symbol.symbol_name,
        )
        if candidate_key in seen_reference_keys:
            return
        seen_reference_keys.add(candidate_key)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": source_symbol.symbol_id,
                        "target_file": target_file,
                        "target_name": target_name,
                    },
                ),
                source_symbol_id=source_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )

    for symbol in symbols:
        snippet = "\n".join(
            lines[max(symbol.start_line - 1, 0) : max(symbol.end_line, symbol.start_line)]
        )
        for match in _QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias_name = str(match.group("alias") or "").strip()
            target_name = str(match.group("name") or "").strip()
            binding = import_bindings.get(alias_name)
            if binding is None or not target_name:
                continue
            _append_reference(
                source_symbol=symbol,
                target_file=binding.target_file,
                target_name=target_name,
                target_symbol_id=None,
            )
        for regex in (_NEW_RE, _TYPE_REFERENCE_RE):
            for match in regex.finditer(snippet):
                target_name = str(match.group("name") or "").strip()
                if (
                    not target_name
                    or target_name in _RESERVED_SYMBOL_NAMES
                    or target_name == symbol.symbol_name
                ):
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
        for match in _CALL_RE.finditer(snippet):
            target_name = str(match.group("name") or "").strip()
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
