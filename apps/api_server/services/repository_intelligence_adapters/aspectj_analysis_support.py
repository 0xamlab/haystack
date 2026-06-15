from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    aspectj_primitives as repository_aspectj_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_aspectj_primitives.StableIdentifier
ResolveSuffixMatch = repository_aspectj_primitives.ResolveSuffixMatch

ASPECTJ_SUFFIXES = repository_aspectj_primitives.ASPECTJ_SUFFIXES
ASPECT_DECL_RE = repository_aspectj_primitives.ASPECT_DECL_RE
IMPORT_RE = repository_aspectj_primitives.IMPORT_RE
PACKAGE_RE = repository_aspectj_primitives.PACKAGE_RE
POINTCUT_DECL_RE = repository_aspectj_primitives.POINTCUT_DECL_RE
TYPE_DECL_RE = repository_aspectj_primitives.TYPE_DECL_RE
TYPE_REFERENCE_RE = repository_aspectj_primitives.TYPE_REFERENCE_RE
has_aspectj_path_hints = repository_aspectj_primitives.has_aspectj_path_hints
is_probable_aspectj_source = repository_aspectj_primitives.is_probable_aspectj_source
iter_declared_type_entries = repository_aspectj_primitives.iter_declared_type_entries
iter_pointcut_entries = repository_aspectj_primitives.iter_pointcut_entries
iter_pointcut_reference_names = repository_aspectj_primitives.iter_pointcut_reference_names
path_aliases_for_file = repository_aspectj_primitives.path_aliases_for_file
resolve_import = repository_aspectj_primitives.resolve_import
_line_count = repository_aspectj_primitives._line_count


def _current_package(text: str) -> str:
    package_match = PACKAGE_RE.search(text)
    return str(package_match.group("target") or "").strip() if package_match else ""


def _import_specs(text: str) -> tuple[tuple[str, str | None], ...]:
    return tuple(
        (
            str(match.group("target") or "").strip(),
            str(match.group("alias") or "").strip() or None,
        )
        for match in IMPORT_RE.finditer(text)
        if str(match.group("target") or "").strip()
    )


def _build_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, tuple[str | None, tuple[str, ...]]], str]:
    current_package = _current_package(text)
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, tuple[str | None, tuple[str, ...]]] = {}
    for import_index, (import_target, import_alias) in enumerate(_import_specs(text)):
        target_symbol = import_target.rsplit(".", 1)[-1]
        target_file = resolve_import(
            import_target,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, target_symbol, "imports")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "index": import_index,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=target_symbol,
                    dependency_type="imports",
                )
            )
        import_bindings.setdefault(target_symbol, (target_file, (target_symbol,)))
        if import_alias is not None:
            import_bindings.setdefault(import_alias, (target_file, (target_symbol,)))
    return tuple(dependencies), import_bindings, current_package


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    aliases = path_aliases_for_file(file_path)
    absolute_path = root_path / file_path
    try:
        text = absolute_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return aliases
    if not is_probable_aspectj_source(path=Path(file_path), text=text):
        return aliases
    current_package = _current_package(text)
    for entry in iter_declared_type_entries(
        text=text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        symbol_name = str(entry["symbol_name"])
        aliases.add(symbol_name)
        if current_package:
            aliases.add(f"{current_package}.{symbol_name}")
    for pointcut_name, _line_number in iter_pointcut_entries(text):
        aliases.add(pointcut_name)
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_aspectj_source(path=Path(file_path), text=text):
        return ()
    dependencies, import_bindings, current_package = _build_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_entries
    }
    if not current_package:
        return tuple(dependency_entries)
    declared_type_names = {
        str(entry["symbol_name"])
        for entry in iter_declared_type_entries(
            text=text,
            file_path=file_path,
            stable_identifier=stable_identifier,
        )
    }
    imported_short_names = {
        alias for alias in import_bindings if "." not in alias and alias not in declared_type_names
    }
    for match in TYPE_REFERENCE_RE.finditer(text):
        type_name = str(match.group("name") or "").strip()
        if (
            not type_name
            or type_name in declared_type_names
            or type_name in imported_short_names
        ):
            continue
        import_target = f"{current_package}.{type_name}"
        target_file = resolve_import(
            import_target,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None or target_file == file_path:
            continue
        dependency_key = (target_file, type_name, "references")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "index": match.start(),
                    },
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
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    if not is_probable_aspectj_source(path=Path(file_path), text=text):
        return (), (), ()
    module_symbol = _Symbol(
        symbol_id=stable_identifier("symbol", {"file_path": file_path, "kind": "module"}),
        symbol_name=Path(file_path).stem,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(text),
        parent_symbol_id=None,
        signature=file_path,
    )
    symbols: list[_Symbol] = [module_symbol]
    symbol_ids_by_name = {module_symbol.symbol_name: module_symbol.symbol_id}
    type_entries = iter_declared_type_entries(
        text=text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    for entry in type_entries:
        symbol = _Symbol(
            symbol_id=str(entry["symbol_id"]),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=module_symbol.symbol_id,
            signature=str(entry["signature"]),
        )
        symbols.append(symbol)
        symbol_ids_by_name[symbol.symbol_name] = symbol.symbol_id
    parent_symbol_id = next(
        (symbol.symbol_id for symbol in symbols if symbol.symbol_kind == "aspect"),
        module_symbol.symbol_id,
    )
    for pointcut_name, line_number in iter_pointcut_entries(text):
        symbol_id = stable_identifier(
            "symbol",
            {
                "file_path": file_path,
                "kind": "pointcut",
                "name": pointcut_name,
                "line": line_number,
            },
        )
        symbols.append(
            _Symbol(
                symbol_id=symbol_id,
                symbol_name=pointcut_name,
                symbol_kind="pointcut",
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=parent_symbol_id,
                signature=None,
            )
        )
        symbol_ids_by_name[pointcut_name] = symbol_id
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, tuple[str, ...], str]] = set()
    for dependency in dependencies:
        if not dependency.target_file:
            continue
        target_names = (dependency.target_symbol,)
        reference_key = (dependency.target_file, target_names, module_symbol.symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": module_symbol.symbol_id,
                        "target_file": dependency.target_file,
                        "target_names": target_names,
                    },
                ),
                source_symbol_id=module_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=dependency.target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )
    for pointcut_name, line_number in iter_pointcut_reference_names(text):
        target_symbol_id = symbol_ids_by_name.get(pointcut_name)
        if target_symbol_id is None:
            continue
        reference_key = (file_path, (pointcut_name,), module_symbol.symbol_id)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": module_symbol.symbol_id,
                        "target_name": pointcut_name,
                        "line": line_number,
                    },
                ),
                source_symbol_id=module_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=file_path,
                target_names=(pointcut_name,),
                reference_type="references_symbol",
            )
        )
    return tuple(symbols), dependencies, tuple(references)


__all__ = [
    "ASPECTJ_SUFFIXES",
    "ASPECT_DECL_RE",
    "IMPORT_RE",
    "PACKAGE_RE",
    "POINTCUT_DECL_RE",
    "TYPE_DECL_RE",
    "TYPE_REFERENCE_RE",
    "has_aspectj_path_hints",
    "is_probable_aspectj_source",
    "iter_declared_type_entries",
    "iter_pointcut_entries",
    "iter_pointcut_reference_names",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
    "path_aliases_for_file",
    "resolve_import",
]
