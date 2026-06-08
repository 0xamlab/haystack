from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    tcl_primitives as repository_tcl_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_tcl_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_tcl_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_tcl_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_tcl_primitives._KNOWN_SUFFIXES
_PACKAGE_REQUIRE_RE = repository_tcl_primitives._PACKAGE_REQUIRE_RE
_PACKAGE_IFNEEDED_RE = repository_tcl_primitives._PACKAGE_IFNEEDED_RE
_SOURCE_RE = repository_tcl_primitives._SOURCE_RE
_NAMESPACE_IMPORT_RE = repository_tcl_primitives._NAMESPACE_IMPORT_RE
_PROC_DECL_RE = repository_tcl_primitives._PROC_DECL_RE
_QUALIFIED_COMMAND_RE = repository_tcl_primitives._QUALIFIED_COMMAND_RE
_RESERVED_COMMANDS = repository_tcl_primitives._RESERVED_COMMANDS
_CollectedSymbol = repository_tcl_primitives._CollectedSymbol

_normalize_namespace = repository_tcl_primitives._normalize_namespace
_line_number = repository_tcl_primitives._line_number
_strip_comment_lines = repository_tcl_primitives._strip_comment_lines
_extract_file_targets = repository_tcl_primitives._extract_file_targets
_namespace_symbol_name = repository_tcl_primitives._namespace_symbol_name
_iter_package_provides = repository_tcl_primitives._iter_package_provides
_iter_namespace_declarations = repository_tcl_primitives._iter_namespace_declarations
is_probable_tcl_source = repository_tcl_primitives.is_probable_tcl_source


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    stripped_text = _strip_comment_lines(text)
    for package_name, _line_no in _iter_package_provides(stripped_text):
        aliases.update(
            {
                package_name,
                f"package:{package_name}",
            }
        )
    for namespace_name, _line_no in _iter_namespace_declarations(stripped_text):
        aliases.update(
            {
                namespace_name,
                _namespace_symbol_name(namespace_name),
                f"namespace:{namespace_name}",
            }
        )
    for match in _PROC_DECL_RE.finditer(stripped_text):
        raw_name = _normalize_namespace(str(match.group("name") or ""))
        if not raw_name:
            continue
        full_name = raw_name
        if "::" not in full_name:
            declared_namespaces = _iter_namespace_declarations(stripped_text)
            if len(declared_namespaces) == 1:
                full_name = f"{declared_namespaces[0][0]}::{full_name}"
        aliases.update(
            {
                full_name,
                full_name.split("::")[-1],
                f"proc:{full_name}",
            }
        )
    return {alias for alias in aliases if alias}


def _resolve_package_target(
    *,
    package_name: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized = _normalize_namespace(package_name)
    if not normalized:
        return None
    for candidate in (
        f"package:{normalized}",
        f"namespace:{normalized}",
        normalized,
    ):
        resolved = module_index.get(candidate)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{normalized}.tcl",
            f"{normalized}.tm",
            normalized.replace("::", "/") + ".tcl",
            normalized.replace("::", "/") + ".tm",
        ],
    )


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip().strip('"').strip("'").strip("{}")
    if not normalized_target:
        return None
    target_suffix = PurePosixPath(normalized_target).suffix.lower()
    if (
        target_suffix in _KNOWN_SUFFIXES
        or "/" in normalized_target
        or normalized_target.startswith(".")
    ):
        resolved_path = normalize_repository_relative_path(
            str(PurePosixPath(current_file).parent / normalized_target)
        )
        if not resolved_path:
            return None
        direct_match = module_index.get(resolved_path)
        if direct_match is not None:
            return direct_match
        return resolve_suffix_match(module_index=module_index, suffixes=[resolved_path])
    return _resolve_package_target(
        package_name=normalized_target,
        module_index=module_index,
        resolve_suffix_match=resolve_suffix_match,
    )


def _dependency_key(
    target_file: str | None,
    target_symbol: str | None,
    dependency_type: str,
) -> tuple[str | None, str | None, str]:
    return target_file, target_symbol, dependency_type


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
    if not is_probable_tcl_source(path=path, text=text):
        return ()
    stripped_text = _strip_comment_lines(text)
    dependencies: list[_Dependency] = []
    seen_keys: set[tuple[str | None, str | None, str]] = set()

    def _append_dependency(
        *,
        target_file: str | None,
        target_symbol: str | None,
        line_no: int,
        import_target: str,
    ) -> None:
        key = _dependency_key(target_file, target_symbol, "imports")
        if key in seen_keys:
            return
        seen_keys.add(key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "line": line_no,
                        "type": "imports",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="imports",
            )
        )

    for match in _PACKAGE_REQUIRE_RE.finditer(stripped_text):
        package_name = _normalize_namespace(str(match.group("name") or ""))
        if not package_name:
            continue
        _append_dependency(
            target_file=_resolve_package_target(
                package_name=package_name,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            ),
            target_symbol=_namespace_symbol_name(package_name),
            line_no=_line_number(stripped_text, match.start()),
            import_target=package_name,
        )

    for match in _SOURCE_RE.finditer(stripped_text):
        line_no = _line_number(stripped_text, match.start())
        for target_path in _extract_file_targets(str(match.group("target") or "")):
            _append_dependency(
                target_file=resolve_import(
                    current_file=file_path,
                    import_target=target_path,
                    module_index=module_index,
                    normalize_repository_relative_path=normalize_repository_relative_path,
                    resolve_suffix_match=resolve_suffix_match,
                ),
                target_symbol=PurePosixPath(target_path).stem,
                line_no=line_no,
                import_target=target_path,
            )

    for match in _PACKAGE_IFNEEDED_RE.finditer(stripped_text):
        line_no = _line_number(stripped_text, match.start())
        for target_path in _extract_file_targets(str(match.group("body") or "")):
            _append_dependency(
                target_file=resolve_import(
                    current_file=file_path,
                    import_target=target_path,
                    module_index=module_index,
                    normalize_repository_relative_path=normalize_repository_relative_path,
                    resolve_suffix_match=resolve_suffix_match,
                ),
                target_symbol=PurePosixPath(target_path).stem,
                line_no=line_no,
                import_target=target_path,
            )

    for match in _NAMESPACE_IMPORT_RE.finditer(stripped_text):
        raw_target = str(match.group("target") or "").strip()
        namespace_name = _normalize_namespace(raw_target.replace("::*", ""))
        if not namespace_name:
            continue
        _append_dependency(
            target_file=_resolve_package_target(
                package_name=namespace_name,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            ),
            target_symbol=_namespace_symbol_name(namespace_name),
            line_no=_line_number(stripped_text, match.start()),
            import_target=namespace_name,
        )

    return tuple(dependencies)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[tuple[_Symbol, ...], tuple[_CollectedSymbol, ...], tuple[_CollectedSymbol, ...]]:
    module_symbols: list[_CollectedSymbol] = []
    proc_symbols: list[_CollectedSymbol] = []
    seen_module_names: set[str] = set()
    module_symbol_ids: dict[str, str] = {}

    for raw_name, line_no in (*_iter_package_provides(text), *_iter_namespace_declarations(text)):
        normalized = _normalize_namespace(raw_name)
        if not normalized or normalized in seen_module_names:
            continue
        seen_module_names.add(normalized)
        symbol = _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "name": _namespace_symbol_name(normalized),
                    "line": line_no,
                    "kind": "module",
                },
            ),
            symbol_name=_namespace_symbol_name(normalized),
            symbol_kind="module",
            start_line=line_no,
            end_line=line_no,
            parent_symbol_id=None,
            signature=normalized,
        )
        module_symbols.append(
            _CollectedSymbol(symbol=symbol, local_start_line=line_no, local_end_line=line_no)
        )
        module_symbol_ids[normalized] = symbol.symbol_id

    proc_entries: list[dict[str, Any]] = []
    for match in _PROC_DECL_RE.finditer(text):
        raw_name = _normalize_namespace(str(match.group("name") or ""))
        if not raw_name:
            continue
        full_name = raw_name
        if "::" not in full_name and len(module_symbols) == 1:
            parent_signature = (
                module_symbols[0].symbol.signature or module_symbols[0].symbol.symbol_name
            )
            full_name = f"{parent_signature}::{full_name}"
        symbol_name = full_name.split("::")[-1]
        namespace_name = "::".join(full_name.split("::")[:-1]).strip(":")
        parent_symbol_id = module_symbol_ids.get(namespace_name) if namespace_name else None
        proc_entries.append(
            {
                "symbol": _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": symbol_name,
                            "line": _line_number(text, match.start()),
                            "kind": "function",
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind="function",
                    start_line=_line_number(text, match.start()),
                    end_line=_line_number(text, match.start()),
                    parent_symbol_id=parent_symbol_id,
                    signature=full_name,
                ),
                "offset": match.start(),
            }
        )
    final_line = max(text.count("\n") + 1, 1)
    for index, entry in enumerate(proc_entries):
        current_symbol = entry["symbol"]
        if index + 1 < len(proc_entries):
            next_start_line = int(proc_entries[index + 1]["symbol"].start_line)
            end_line = max(next_start_line - 1, current_symbol.start_line)
        else:
            end_line = final_line
        proc_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=current_symbol.symbol_id,
                    symbol_name=current_symbol.symbol_name,
                    symbol_kind=current_symbol.symbol_kind,
                    start_line=current_symbol.start_line,
                    end_line=end_line,
                    parent_symbol_id=current_symbol.parent_symbol_id,
                    signature=current_symbol.signature,
                ),
                local_start_line=current_symbol.start_line,
                local_end_line=end_line,
            )
        )

    symbols = [entry.symbol for entry in module_symbols]
    if not symbols and not proc_symbols:
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": PurePosixPath(file_path).stem,
                        "line": 1,
                        "kind": "module",
                    },
                ),
                symbol_name=PurePosixPath(file_path).stem,
                symbol_kind="module",
                start_line=1,
                end_line=final_line,
                parent_symbol_id=None,
                signature=str(PurePosixPath(file_path).with_suffix("")),
            )
        )
    symbols.extend(entry.symbol for entry in proc_symbols)
    return tuple(symbols), tuple(module_symbols), tuple(proc_symbols)


def _source_symbol_id_for_line(
    *,
    line_no: int,
    module_symbols: tuple[_CollectedSymbol, ...],
    proc_symbols: tuple[_CollectedSymbol, ...],
    symbols: tuple[_Symbol, ...],
) -> str | None:
    for entry in proc_symbols:
        if entry.local_start_line <= line_no <= entry.local_end_line:
            return entry.symbol.symbol_id
    if len(module_symbols) == 1:
        return module_symbols[0].symbol.symbol_id
    if symbols:
        return symbols[0].symbol_id
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
    if not is_probable_tcl_source(path=path, text=text):
        return (), (), ()
    stripped_text = _strip_comment_lines(text)
    symbols, module_symbols, proc_symbols = _collect_symbols(
        file_path=file_path,
        text=stripped_text,
        stable_identifier=stable_identifier,
    )
    dependencies = parse_dependencies_only(
        file_path,
        stripped_text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    reference_candidates: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, tuple[str, ...], str]] = set()

    for match in _NAMESPACE_IMPORT_RE.finditer(stripped_text):
        namespace_name = _normalize_namespace(str(match.group("target") or "").replace("::*", ""))
        if not namespace_name:
            continue
        target_file = _resolve_package_target(
            package_name=namespace_name,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_names = (_namespace_symbol_name(namespace_name),)
        source_symbol_id = _source_symbol_id_for_line(
            line_no=_line_number(stripped_text, match.start()),
            module_symbols=module_symbols,
            proc_symbols=proc_symbols,
            symbols=symbols,
        )
        if source_symbol_id is None:
            continue
        key = (target_file, target_names, source_symbol_id)
        if key in seen_reference_keys:
            continue
        seen_reference_keys.add(key)
        reference_candidates.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "symbol_id": source_symbol_id,
                        "target": namespace_name,
                        "line": _line_number(stripped_text, match.start()),
                        "type": "references_symbol",
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )

    for line_index, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        lowered_line = stripped_line.lower()
        if lowered_line.startswith(("proc ", "namespace ", "package ", "source ")):
            continue
        source_symbol_id = _source_symbol_id_for_line(
            line_no=line_index,
            module_symbols=module_symbols,
            proc_symbols=proc_symbols,
            symbols=symbols,
        )
        if source_symbol_id is None:
            continue
        for match in _QUALIFIED_COMMAND_RE.finditer(raw_line):
            qualified_name = _normalize_namespace(str(match.group("name") or ""))
            if not qualified_name:
                continue
            command_name = qualified_name.split("::")[-1]
            if command_name.lower() in _RESERVED_COMMANDS:
                continue
            namespace_name = "::".join(qualified_name.split("::")[:-1]).strip(":")
            target_file = (
                module_index.get(f"proc:{qualified_name}")
                or module_index.get(qualified_name)
                or module_index.get(f"namespace:{namespace_name}")
                or module_index.get(namespace_name)
                or _resolve_package_target(
                    package_name=namespace_name,
                    module_index=module_index,
                    resolve_suffix_match=resolve_suffix_match,
                )
            )
            target_names = (command_name,)
            key = (target_file, target_names, source_symbol_id)
            if key in seen_reference_keys:
                continue
            seen_reference_keys.add(key)
            reference_candidates.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "file_path": file_path,
                            "symbol_id": source_symbol_id,
                            "target": qualified_name,
                            "line": line_index,
                            "type": "references_symbol",
                        },
                    ),
                    source_symbol_id=source_symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=target_names,
                    reference_type="references_symbol",
                )
            )

    return symbols, dependencies, tuple(reference_candidates)
