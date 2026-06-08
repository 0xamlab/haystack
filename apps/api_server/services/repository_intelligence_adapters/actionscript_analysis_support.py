from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    actionscript_primitives as repository_actionscript_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_actionscript_primitives.StableIdentifier
NormalizeRepositoryRelativePath = (
    repository_actionscript_primitives.NormalizeRepositoryRelativePath
)
ResolveSuffixMatch = repository_actionscript_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_actionscript_primitives._KNOWN_SUFFIXES
_IMPORT_RE = repository_actionscript_primitives._IMPORT_RE
_INCLUDE_RE = repository_actionscript_primitives._INCLUDE_RE
_NEW_REFERENCE_RE = repository_actionscript_primitives._NEW_REFERENCE_RE
_QUALIFIED_CALL_RE = repository_actionscript_primitives._QUALIFIED_CALL_RE
_RESERVED_REFERENCE_NAMES = (
    repository_actionscript_primitives._RESERVED_REFERENCE_NAMES
)
_RESERVED_REFERENCE_OWNERS = (
    repository_actionscript_primitives._RESERVED_REFERENCE_OWNERS
)
_line_number = repository_actionscript_primitives._line_number
_package_name = repository_actionscript_primitives._package_name
_collect_type_entries = repository_actionscript_primitives._collect_type_entries
_collect_function_entries = (
    repository_actionscript_primitives._collect_function_entries
)
_resolve_import_target = repository_actionscript_primitives._resolve_import_target
_resolve_include_target = repository_actionscript_primitives._resolve_include_target
_import_bindings_for_text = repository_actionscript_primitives._import_bindings_for_text
_resolve_named_type_target = (
    repository_actionscript_primitives._resolve_named_type_target
)
_typed_variable_bindings = repository_actionscript_primitives._typed_variable_bindings
is_probable_actionscript_source = (
    repository_actionscript_primitives.is_probable_actionscript_source
)
strip_comments = repository_actionscript_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    without_suffix = str(path.with_suffix(""))
    aliases = {
        file_path,
        without_suffix,
        without_suffix.replace("/", "."),
        path.stem,
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    if not is_probable_actionscript_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    stripped_text = strip_comments(text)
    package_name = _package_name(stripped_text)
    if package_name:
        aliases.update({package_name, f"package:{package_name}"})
    type_entries = _collect_type_entries(
        file_path=file_path,
        text=stripped_text,
        package_name=package_name,
        stable_identifier=stable_identifier,
    )
    function_entries = _collect_function_entries(
        file_path=file_path,
        text=stripped_text,
        package_name=package_name,
        type_entries=type_entries,
        stable_identifier=stable_identifier,
    )
    for entry in type_entries:
        symbol = entry["symbol"]
        qualified_name = str(entry["qualified_name"])
        aliases.update(
            {
                symbol.symbol_name,
                qualified_name,
                f"{symbol.symbol_kind}:{symbol.symbol_name}",
                f"{symbol.symbol_kind}:{qualified_name}",
            }
        )
    for entry in function_entries:
        symbol = entry["symbol"]
        aliases.add(symbol.symbol_name)
        signature = str(symbol.signature or "").strip()
        if signature:
            aliases.add(signature)
            signature_parts = signature.split(".")
            if len(signature_parts) >= 2:
                aliases.add(".".join(signature_parts[-2:]))
    return {alias for alias in aliases if alias}


def _register_dependency(
    *,
    file_path: str,
    target_file: str | None,
    target_symbol: str | None,
    dependency_type: str,
    target_hint: str,
    line_no: int,
    stable_identifier: StableIdentifier,
    dependency_keys: set[tuple[str | None, str | None, str]],
    dependencies: list[_Dependency],
) -> None:
    dependency_key = (target_file, target_symbol, dependency_type)
    if dependency_key in dependency_keys:
        return
    dependency_keys.add(dependency_key)
    dependencies.append(
        _Dependency(
            dependency_edge_id=stable_identifier(
                "dep",
                {
                    "file_path": file_path,
                    "target": target_hint,
                    "symbol": target_symbol,
                    "line": line_no,
                    "type": dependency_type,
                },
            ),
            source_file=file_path,
            target_file=target_file,
            target_symbol=target_symbol,
            dependency_type=dependency_type,
        )
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    path = PurePosixPath(file_path)
    if not is_probable_actionscript_source(path=path, text=text):
        return ()
    stripped_text = strip_comments(text)
    package_name = _package_name(stripped_text)
    imported_bindings, wildcard_packages = _import_bindings_for_text(
        file_path=file_path,
        text=stripped_text,
        module_index=module_index,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str | None, str]] = set()

    for match in _IMPORT_RE.finditer(stripped_text):
        import_target = str(match.group("target") or "").strip()
        target_file, target_name = _resolve_import_target(
            import_target=import_target,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        _register_dependency(
            file_path=file_path,
            target_file=target_file,
            target_symbol=target_name,
            dependency_type="imports",
            target_hint=import_target,
            line_no=_line_number(stripped_text, match.start()),
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )

    for match in _INCLUDE_RE.finditer(stripped_text):
        include_target = str(match.group("target") or "").strip()
        _register_dependency(
            file_path=file_path,
            target_file=_resolve_include_target(
                current_file=file_path,
                include_target=include_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            ),
            target_symbol=PurePosixPath(include_target).stem or None,
            dependency_type="imports",
            target_hint=include_target,
            line_no=_line_number(stripped_text, match.start()),
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )

    type_entries = _collect_type_entries(
        file_path=file_path,
        text=stripped_text,
        package_name=package_name,
        stable_identifier=stable_identifier,
    )
    for entry in type_entries:
        symbol = entry["symbol"]
        for target_name in entry["relation_targets"]:
            target_file, resolved_target_name = _resolve_named_type_target(
                target_name=target_name,
                current_file=file_path,
                current_package_name=package_name,
                imported_bindings=imported_bindings,
                wildcard_packages=wildcard_packages,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_dependency(
                file_path=file_path,
                target_file=target_file,
                target_symbol=resolved_target_name,
                dependency_type="imports",
                target_hint=target_name,
                line_no=int(symbol.start_line),
                stable_identifier=stable_identifier,
                dependency_keys=dependency_keys,
                dependencies=dependencies,
            )

    variable_bindings = _typed_variable_bindings(stripped_text)
    for match in _NEW_REFERENCE_RE.finditer(stripped_text):
        target_name = str(match.group("target") or "").strip()
        target_file, resolved_target_name = _resolve_named_type_target(
            target_name=target_name,
            current_file=file_path,
            current_package_name=package_name,
            imported_bindings=imported_bindings,
            wildcard_packages=wildcard_packages,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        _register_dependency(
            file_path=file_path,
            target_file=target_file,
            target_symbol=resolved_target_name,
            dependency_type="references",
            target_hint=target_name,
            line_no=_line_number(stripped_text, match.start()),
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )

    for match in _QUALIFIED_CALL_RE.finditer(stripped_text):
        owner_name = str(match.group("owner") or "").strip()
        method_name = str(match.group("name") or "").strip()
        if (
            not owner_name
            or not method_name
            or owner_name.lower() in _RESERVED_REFERENCE_OWNERS
            or method_name.lower() in _RESERVED_REFERENCE_NAMES
        ):
            continue
        target_type = variable_bindings.get(owner_name.lower(), owner_name)
        target_file, _resolved_target_name = _resolve_named_type_target(
            target_name=target_type,
            current_file=file_path,
            current_package_name=package_name,
            imported_bindings=imported_bindings,
            wildcard_packages=wildcard_packages,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        _register_dependency(
            file_path=file_path,
            target_file=target_file,
            target_symbol=method_name,
            dependency_type="references",
            target_hint=f"{owner_name}.{method_name}",
            line_no=_line_number(stripped_text, match.start()),
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )

    return tuple(dependencies)


def _source_symbol_id_for_line(
    *,
    line_no: int,
    type_entries: tuple[dict[str, Any], ...],
    function_entries: tuple[dict[str, Any], ...],
    symbols: tuple[_Symbol, ...],
) -> str | None:
    for entry in function_entries:
        symbol = entry["symbol"]
        if int(symbol.start_line) <= line_no <= int(symbol.end_line):
            return str(symbol.symbol_id)
    matched_types = [
        entry["symbol"]
        for entry in type_entries
        if int(entry["symbol"].start_line) <= line_no <= int(entry["symbol"].end_line)
    ]
    if matched_types:
        matched_types.sort(key=lambda symbol: int(symbol.end_line) - int(symbol.start_line))
        return str(matched_types[0].symbol_id)
    if symbols:
        return str(symbols[0].symbol_id)
    return None


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
    path = PurePosixPath(file_path)
    if not is_probable_actionscript_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    package_name = _package_name(stripped_text)
    type_entries = _collect_type_entries(
        file_path=file_path,
        text=stripped_text,
        package_name=package_name,
        stable_identifier=stable_identifier,
    )
    function_entries = _collect_function_entries(
        file_path=file_path,
        text=stripped_text,
        package_name=package_name,
        type_entries=type_entries,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(
        [entry["symbol"] for entry in type_entries]
        + [entry["symbol"] for entry in function_entries]
    )
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    imported_bindings, wildcard_packages = _import_bindings_for_text(
        file_path=file_path,
        text=stripped_text,
        module_index=module_index,
        resolve_suffix_match=resolve_suffix_match,
    )
    variable_bindings = _typed_variable_bindings(stripped_text)
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}

    def _register_reference(
        *,
        source_symbol_id: str | None,
        target_file: str | None,
        target_names: tuple[str, ...],
        line_no: int,
        target_hint: str,
    ) -> None:
        if source_symbol_id is None or not target_names:
            return
        if target_file == file_path:
            return
        edge_id = stable_identifier(
            "ref",
            {
                "file_path": file_path,
                "symbol_id": source_symbol_id,
                "target": target_hint,
                "target_file": target_file,
                "target_names": target_names,
                "line": line_no,
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            _SymbolReferenceCandidate(
                reference_edge_id=edge_id,
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            ),
        )

    for entry in type_entries:
        symbol = entry["symbol"]
        for target_name in entry["relation_targets"]:
            target_file, resolved_target_name = _resolve_named_type_target(
                target_name=target_name,
                current_file=file_path,
                current_package_name=package_name,
                imported_bindings=imported_bindings,
                wildcard_packages=wildcard_packages,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_reference(
                source_symbol_id=symbol.symbol_id,
                target_file=target_file,
                target_names=(resolved_target_name or target_name.rsplit(".", 1)[-1],),
                line_no=int(symbol.start_line),
                target_hint=target_name,
            )

    for match in _NEW_REFERENCE_RE.finditer(stripped_text):
        target_name = str(match.group("target") or "").strip()
        target_file, resolved_target_name = _resolve_named_type_target(
            target_name=target_name,
            current_file=file_path,
            current_package_name=package_name,
            imported_bindings=imported_bindings,
            wildcard_packages=wildcard_packages,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        _register_reference(
            source_symbol_id=_source_symbol_id_for_line(
                line_no=_line_number(stripped_text, match.start()),
                type_entries=type_entries,
                function_entries=function_entries,
                symbols=symbols,
            ),
            target_file=target_file,
            target_names=(resolved_target_name or target_name.rsplit(".", 1)[-1],),
            line_no=_line_number(stripped_text, match.start()),
            target_hint=target_name,
        )

    for match in _QUALIFIED_CALL_RE.finditer(stripped_text):
        owner_name = str(match.group("owner") or "").strip()
        method_name = str(match.group("name") or "").strip()
        if (
            not owner_name
            or not method_name
            or owner_name.lower() in _RESERVED_REFERENCE_OWNERS
            or method_name.lower() in _RESERVED_REFERENCE_NAMES
        ):
            continue
        target_type = variable_bindings.get(owner_name.lower(), owner_name)
        target_file, _resolved_target_name = _resolve_named_type_target(
            target_name=target_type,
            current_file=file_path,
            current_package_name=package_name,
            imported_bindings=imported_bindings,
            wildcard_packages=wildcard_packages,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        _register_reference(
            source_symbol_id=_source_symbol_id_for_line(
                line_no=_line_number(stripped_text, match.start()),
                type_entries=type_entries,
                function_entries=function_entries,
                symbols=symbols,
            ),
            target_file=target_file,
            target_names=(method_name,),
            line_no=_line_number(stripped_text, match.start()),
            target_hint=f"{owner_name}.{method_name}",
        )

    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
