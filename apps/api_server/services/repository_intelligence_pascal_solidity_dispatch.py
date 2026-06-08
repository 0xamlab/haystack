from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    delphi as delphi_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    pascal as pascal_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    solidity as solidity_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _module_index_aliases_for_file,
    _resolve_directory_prefix_match,
    _resolve_suffix_match,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_PASCAL_RESERVED_SYMBOL_NAMES = pascal_adapter.RESERVED_SYMBOL_NAMES
_PASCAL_IDENTIFIER_RE = pascal_adapter.IDENTIFIER_RE
_PASCAL_QUALIFIED_REFERENCE_RE = pascal_adapter.QUALIFIED_REFERENCE_RE
_PASCAL_UNQUALIFIED_CALL_RE = pascal_adapter.UNQUALIFIED_CALL_RE

_normalize_pascal_target = pascal_adapter.normalize_target
_normalize_pascal_symbol_name = pascal_adapter.normalize_symbol_name
_strip_pascal_comments = pascal_adapter.strip_comments
_pascal_unit_name = pascal_adapter.unit_name
_pascal_uses_targets = pascal_adapter.uses_targets


def _collect_pascal_symbol_entries(
    text: str,
    *,
    file_path: str,
) -> list[dict[str, Any]]:
    return pascal_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _resolve_pascal_target(reference_target: str, module_index: dict[str, str]) -> str | None:
    normalized_target = _normalize_pascal_target(reference_target).lower()
    if not normalized_target:
        return None
    leaf_name = normalized_target.rsplit(".", 1)[-1]
    for candidate in (normalized_target, leaf_name):
        if not candidate:
            continue
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match
    namespace_path = normalized_target.replace(".", "/")
    resolved = _resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            normalized_target,
            namespace_path,
            f"{normalized_target}.pas",
            f"{normalized_target}.pp",
            f"{normalized_target}.lpr",
            f"{normalized_target}.dpr",
            f"{normalized_target}.dpk",
            f"{namespace_path}.pas",
            f"{namespace_path}.pp",
            f"{namespace_path}.lpr",
            f"{namespace_path}.dpr",
            f"{namespace_path}.dpk",
            f"{leaf_name}.pas" if leaf_name else "",
            f"{leaf_name}.pp" if leaf_name else "",
            f"{leaf_name}.lpr" if leaf_name else "",
            f"{leaf_name}.dpr" if leaf_name else "",
            f"{leaf_name}.dpk" if leaf_name else "",
        ],
    )
    if resolved is not None:
        return resolved
    return _resolve_directory_prefix_match(
        module_index=module_index,
        prefixes=[
            namespace_path,
            f"src/{namespace_path}",
            f"source/{namespace_path}",
            f"units/{namespace_path}",
            f"lib/{namespace_path}",
        ],
    )


def _extract_pascal_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_target in _pascal_uses_targets(text):
        canonical_target = import_target.lower()
        target_symbol = import_target.rsplit(".", 1)[-1]
        target_symbol_key = target_symbol.lower()
        target_file = _resolve_pascal_target(import_target, module_index)
        dependency_key = (target_file, target_symbol, "imports")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=_stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": canonical_target,
                            "line": text.lower().find(import_target.lower()),
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=target_symbol,
                    dependency_type="imports",
                )
            )
        for binding_alias in {canonical_target, target_symbol_key}:
            if not binding_alias:
                continue
            import_bindings.setdefault(
                binding_alias,
                _ImportedSymbolBinding(
                    alias=binding_alias,
                    target_file=target_file,
                    target_names=(target_symbol,),
                ),
            )
        if target_file is None:
            continue
        for alias in sorted(_module_index_aliases_for_file(module_index, target_file)):
            lower_alias = alias.strip().lower()
            if not lower_alias or "/" in lower_alias:
                continue
            leaf_alias = lower_alias.rsplit(".", 1)[-1]
            if (
                not leaf_alias
                or leaf_alias in _PASCAL_RESERVED_SYMBOL_NAMES
                or not _PASCAL_IDENTIFIER_RE.fullmatch(leaf_alias)
            ):
                continue
            import_bindings.setdefault(
                leaf_alias,
                _ImportedSymbolBinding(
                    alias=leaf_alias,
                    target_file=target_file,
                    target_names=(leaf_alias,),
                ),
            )
    return tuple(dependencies), import_bindings


def _parse_pascal_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    dependencies, import_bindings = _extract_pascal_import_bindings(
        file_path,
        text,
        module_index,
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_entries
    }
    declared_symbol_names = {
        str(entry["symbol_name"]).lower()
        for entry in _collect_pascal_symbol_entries(text, file_path=file_path)
    }
    stripped_text = _strip_pascal_comments(text)
    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        normalized_line = raw_line.strip()
        if not normalized_line:
            continue
        for match in _PASCAL_QUALIFIED_REFERENCE_RE.finditer(normalized_line):
            alias = str(match.group("alias") or "").strip().lower()
            target_name = _normalize_pascal_symbol_name(str(match.group("name") or ""))
            target_name_key = target_name.lower()
            if (
                not alias
                or not target_name
                or alias in _PASCAL_RESERVED_SYMBOL_NAMES
                or target_name_key in _PASCAL_RESERVED_SYMBOL_NAMES
            ):
                continue
            binding = import_bindings.get(alias)
            target_file = binding.target_file if binding is not None else None
            if target_file is None:
                target_file = _resolve_pascal_target(alias, module_index)
            dependency_key = (target_file, target_name, "references")
            if (
                target_file is None
                or target_file == file_path
                or dependency_key in dependency_keys
            ):
                continue
            dependency_keys.add(dependency_key)
            dependency_entries.append(
                _Dependency(
                    dependency_edge_id=_stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": f"{alias}.{target_name_key}",
                            "line": line_no,
                            "kind": "qualified_call",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=target_name,
                    dependency_type="references",
                )
            )
        for match in _PASCAL_UNQUALIFIED_CALL_RE.finditer(normalized_line):
            target_name = _normalize_pascal_symbol_name(str(match.group("name") or ""))
            target_name_key = target_name.lower()
            if (
                not target_name
                or target_name_key in _PASCAL_RESERVED_SYMBOL_NAMES
                or target_name_key in declared_symbol_names
            ):
                continue
            binding = import_bindings.get(target_name_key)
            target_file = binding.target_file if binding is not None else None
            target_symbol = (
                binding.target_names[0]
                if binding is not None and binding.target_names
                else target_name
            )
            dependency_key = (target_file, target_symbol, "references")
            if (
                target_file is None
                or target_file == file_path
                or dependency_key in dependency_keys
            ):
                continue
            dependency_keys.add(dependency_key)
            dependency_entries.append(
                _Dependency(
                    dependency_edge_id=_stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": target_symbol.lower(),
                            "line": line_no,
                            "kind": "call",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=target_symbol,
                    dependency_type="references",
                )
            )
    return tuple(dependency_entries)


def _parse_pascal_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    symbol_entries = _collect_pascal_symbol_entries(text, file_path=file_path)
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
    _, import_bindings = _extract_pascal_import_bindings(
        file_path,
        text,
        module_index,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    lines = _strip_pascal_comments(text).splitlines()
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in _PASCAL_QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias = str(match.group("alias") or "").strip().lower()
            target_name = _normalize_pascal_symbol_name(str(match.group("name") or ""))
            if (
                not alias
                or not target_name
                or alias in _PASCAL_RESERVED_SYMBOL_NAMES
                or target_name.lower() in _PASCAL_RESERVED_SYMBOL_NAMES
            ):
                continue
            binding = import_bindings.get(alias)
            target_file = binding.target_file if binding is not None else None
            if target_file is None:
                target_file = _resolve_pascal_target(alias, module_index)
            if target_file is None or target_file == file_path:
                continue
            edge_id = _stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": target_file,
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
                    target_file=target_file,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
        for match in _PASCAL_UNQUALIFIED_CALL_RE.finditer(snippet):
            target_name = _normalize_pascal_symbol_name(str(match.group("name") or ""))
            target_name_key = target_name.lower()
            if (
                not target_name
                or target_name_key in _PASCAL_RESERVED_SYMBOL_NAMES
                or target_name_key == symbol.symbol_name.lower()
            ):
                continue
            binding = import_bindings.get(target_name_key)
            target_file = binding.target_file if binding is not None else None
            if target_file is None or target_file == file_path:
                continue
            target_names = (
                binding.target_names
                if binding is not None and binding.target_names
                else (target_name,)
            )
            edge_id = _stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": target_file,
                    "target_names": target_names,
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
                    target_names=target_names,
                    reference_type="references_symbol",
                ),
            )
    return (
        symbols,
        _parse_pascal_dependencies_only(file_path, text, module_index),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )


def _parse_delphi_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    if PurePosixPath(file_path).suffix.lower() in {".dfm", ".fmx", ".dproj"}:
        return ()
    return _parse_pascal_dependencies_only(file_path, text, module_index)


def _parse_delphi_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    suffix = PurePosixPath(file_path).suffix.lower()
    if suffix in {".dfm", ".fmx", ".dproj"}:
        return (), (), ()
    symbol_entries = delphi_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )
    if not symbol_entries:
        return (), _parse_delphi_dependencies_only(file_path, text, module_index), ()
    return _parse_pascal_file(file_path, text, module_index)


def _resolve_solidity_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return solidity_adapter.resolve_import(
        import_target,
        current_file=current_file,
        module_index=module_index,
    )


def _dependencies_from_specs(
    dependency_specs: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> tuple[_Dependency, ...]:
    return tuple(_Dependency(**spec) for spec in dependency_specs)


def _references_from_specs(
    reference_specs: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> tuple[_SymbolReferenceCandidate, ...]:
    return tuple(_SymbolReferenceCandidate(**spec) for spec in reference_specs)


def _symbols_from_entries(symbol_entries: list[dict[str, Any]]) -> tuple[_Symbol, ...]:
    return tuple(
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


def _parse_solidity_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    dependency_specs = solidity_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import_fn=lambda import_target: _resolve_solidity_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
        ),
    )
    return _dependencies_from_specs(dependency_specs)


def _parse_solidity_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    symbol_entries, dependency_specs, reference_specs = solidity_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import_fn=lambda import_target: _resolve_solidity_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
        ),
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


PASCAL_SOLIDITY_ADAPTER_DEPENDENCY_PARSERS = {
    "delphi": _parse_delphi_dependencies_only,
    "pascal": _parse_pascal_dependencies_only,
    "solidity": _parse_solidity_dependencies_only,
}

PASCAL_SOLIDITY_ADAPTER_FILE_PARSERS = {
    "delphi": _parse_delphi_file,
    "pascal": _parse_pascal_file,
    "solidity": _parse_solidity_file,
}
