from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    rego_primitives as repository_rego_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_rego_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_rego_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_rego_primitives.ResolveSuffixMatch

_CollectedSymbol = repository_rego_primitives._CollectedSymbol
_DATA_REFERENCE_RE = repository_rego_primitives._DATA_REFERENCE_RE
_IDENTIFIER_RE = repository_rego_primitives._IDENTIFIER_RE
_QUALIFIED_REFERENCE_RE = repository_rego_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_rego_primitives._RESERVED_SYMBOL_NAMES
_line_count = repository_rego_primitives._line_count
_line_number = repository_rego_primitives._line_number
_ordered_names = repository_rego_primitives._ordered_names
has_rego_path_hints = repository_rego_primitives.has_rego_path_hints
is_probable_rego_source = repository_rego_primitives.is_probable_rego_source
iter_symbol_entries = repository_rego_primitives.iter_symbol_entries
module_name_from_path = repository_rego_primitives.module_name_from_path
package_name_from_text = repository_rego_primitives.package_name_from_text
parse_import_statements = repository_rego_primitives.parse_import_statements
strip_comments = repository_rego_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    module_name = package_name_from_text(stripped_text) or module_name_from_path(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name,
                "symbol_kind": "module",
                "start_line": 1,
            },
        ),
        symbol_name=module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"package {module_name}" if module_name else None,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
            qualified_names=_ordered_names(
                module_name,
                f"data.{module_name}" if module_name else "",
            ),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
        qualified_names = _ordered_names(
            symbol_name,
            f"{module_name}.{symbol_name}" if module_name else "",
            f"data.{module_name}.{symbol_name}" if module_name else "",
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
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=symbol_name,
                ),
                local_start_line=start_line,
                local_end_line=start_line,
                qualified_names=qualified_names,
            )
        )
    final_line = _line_count(stripped_text)
    finalized_symbols: list[_CollectedSymbol] = []
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
        finalized_symbols.append(
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
    return tuple(finalized_symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_rego_path_hints(path):
        return set()
    aliases = {
        file_path,
        _without_suffix_path(path),
        _without_suffix_path(path).replace("/", "."),
        path.stem,
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_rego_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    module_name = package_name_from_text(text) or module_name_from_path(file_path)
    aliases.update(
        _ordered_names(
            module_name,
            module_name.replace(".", "/"),
            f"data.{module_name}",
        )
    )
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
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if not normalized_target.startswith("data."):
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    package_target = normalized_target[5:]
    candidate_keys = [
        normalized_target,
        package_target,
        package_target.replace(".", "/"),
        f"{package_target.replace('.', '/')}.rego",
        f"policy/{package_target.replace('.', '/')}.rego",
        f"policies/{package_target.replace('.', '/')}.rego",
        f"lib/{package_target.replace('.', '/')}.rego",
    ]
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None:
            return resolved
    suffixes = [
        f"{package_target.replace('.', '/')}.rego",
        f"/{package_target.replace('.', '/')}.rego",
        f"policy/{package_target.replace('.', '/')}.rego",
        f"policies/{package_target.replace('.', '/')}.rego",
        f"lib/{package_target.replace('.', '/')}.rego",
    ]
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_target, alias, line_number in parse_import_statements(text):
        if not import_target.startswith("data."):
            continue
        target_file = resolve_import(
            import_target,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "line": line_number,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=import_target.split(".")[-1],
                    dependency_type="imports",
                )
            )
        binding_alias = alias or import_target.split(".")[-1]
        if binding_alias:
            import_bindings[binding_alias] = _ImportedSymbolBinding(
                alias=binding_alias,
                target_file=target_file,
                target_names=(import_target.split(".")[-1],),
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
    dependencies, _bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    return dependencies


def _resolve_data_reference_target(
    full_target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(full_target or "").strip()
    if not normalized_target.startswith("data."):
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    parts = normalized_target.split(".")
    for end_index in range(len(parts) - 1, 1, -1):
        candidate_target = ".".join(parts[:end_index])
        resolved = resolve_import(
            candidate_target,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if resolved is not None:
            return resolved
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
    if not is_probable_rego_source(path=Path(file_path), text=text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    local_symbols_by_name = {
        collected_symbol.symbol.symbol_name: collected_symbol.symbol
        for collected_symbol in collected_symbols
    }
    stripped_lines = strip_comments(text).splitlines()
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str, str | None, str | None]] = set()

    def _record_reference(
        *,
        source_symbol: _Symbol,
        target_name: str,
        target_file: str | None,
        target_symbol_id: str | None,
    ) -> None:
        reference_key = (source_symbol.symbol_id, target_name, target_file, target_symbol_id)
        if reference_key in seen_reference_keys:
            return
        seen_reference_keys.add(reference_key)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "symref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": source_symbol.symbol_id,
                        "target": target_name,
                        "line": source_symbol.start_line,
                    },
                ),
                source_symbol_id=source_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=(target_name,),
                reference_type="calls",
            )
        )

    for collected_symbol in collected_symbols:
        symbol = collected_symbol.symbol
        symbol_text = "\n".join(
            stripped_lines[
                max(collected_symbol.local_start_line - 1, 0) : collected_symbol.local_end_line
            ]
        )
        masked_text = list(symbol_text)
        for match in _DATA_REFERENCE_RE.finditer(symbol_text):
            full_target = str(match.group("full") or "").strip()
            if not full_target:
                continue
            target_name = full_target.split(".")[-1]
            target_file = _resolve_data_reference_target(
                full_target,
                module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            _record_reference(
                source_symbol=symbol,
                target_name=target_name,
                target_file=target_file,
                target_symbol_id=None,
            )
            for index in range(match.start(), match.end()):
                masked_text[index] = " "
        masked_symbol_text = "".join(masked_text)
        masked_text = list(masked_symbol_text)
        for match in _QUALIFIED_REFERENCE_RE.finditer(masked_symbol_text):
            alias = str(match.group("alias") or "").strip()
            name = str(match.group("name") or "").strip()
            if alias == "data" or not alias or not name:
                continue
            imported_binding = import_bindings.get(alias)
            if imported_binding is None or imported_binding.target_file is None:
                continue
            _record_reference(
                source_symbol=symbol,
                target_name=name,
                target_file=imported_binding.target_file,
                target_symbol_id=None,
            )
            for index in range(match.start(), match.end()):
                masked_text[index] = " "
        bare_symbol_text = "".join(masked_text)
        for match in _IDENTIFIER_RE.finditer(bare_symbol_text):
            name = str(match.group("name") or "").strip()
            if (
                not name
                or name == symbol.symbol_name
                or name in _RESERVED_SYMBOL_NAMES
            ):
                continue
            imported_binding = import_bindings.get(name)
            if imported_binding is not None and imported_binding.target_file is not None:
                _record_reference(
                    source_symbol=symbol,
                    target_name=name,
                    target_file=imported_binding.target_file,
                    target_symbol_id=None,
                )
                continue
            local_target = local_symbols_by_name.get(name)
            if local_target is None:
                continue
            _record_reference(
                source_symbol=symbol,
                target_name=name,
                target_file=file_path,
                target_symbol_id=local_target.symbol_id,
            )
    return (
        tuple(collected_symbol.symbol for collected_symbol in collected_symbols),
        tuple(dependencies),
        tuple(symbol_references),
    )
