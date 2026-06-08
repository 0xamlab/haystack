from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    starlark_primitives as repository_starlark_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_starlark_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_starlark_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_starlark_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_starlark_primitives._KNOWN_SUFFIXES
_KNOWN_BASENAMES = repository_starlark_primitives._KNOWN_BASENAMES
_CALL_RE = repository_starlark_primitives._CALL_RE
_BUILTIN_REFERENCE_NAMES = repository_starlark_primitives._BUILTIN_REFERENCE_NAMES
_CollectedSymbol = repository_starlark_primitives._CollectedSymbol

_line_count = repository_starlark_primitives._line_count
_line_number = repository_starlark_primitives._line_number
_RESERVED_SYMBOL_NAMES = repository_starlark_primitives._RESERVED_SYMBOL_NAMES
has_starlark_path_hints = repository_starlark_primitives.has_starlark_path_hints
is_probable_starlark_source = repository_starlark_primitives.is_probable_starlark_source
iter_load_statements = repository_starlark_primitives.iter_load_statements
iter_symbol_entries = repository_starlark_primitives.iter_symbol_entries
module_name_from_path = repository_starlark_primitives.module_name_from_path
parse_loaded_symbols = repository_starlark_primitives.parse_loaded_symbols
strip_comments = repository_starlark_primitives.strip_comments
target_label_for_path = repository_starlark_primitives.target_label_for_path


def _without_suffix_path(path: PurePosixPath) -> str:
    if path.suffix:
        return str(path.with_suffix(""))
    return str(path)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path)
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
        signature=f"module {module_name}" if module_name else None,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
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
            )
        )
    final_line = _line_count(stripped_text)
    finalized_symbols: list[_CollectedSymbol] = []
    for index, collected_symbol in enumerate(collected_symbols):
        if index + 1 < len(collected_symbols):
            end_line = max(
                collected_symbols[index + 1].local_start_line - 1,
                collected_symbol.local_start_line,
            )
        else:
            end_line = final_line
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
    if not has_starlark_path_hints(path):
        return set()
    aliases = {file_path, target_label_for_path(path), path.name}
    if path.suffix.lower() in _KNOWN_SUFFIXES:
        aliases.add(_without_suffix_path(path))
        aliases.add(_without_suffix_path(path).replace("/", "."))
        aliases.add(path.stem)
    elif path.name in {"BUILD", "BUILD.bazel"}:
        package_alias = f"//{path.parent}" if str(path.parent) not in {"", "."} else "//"
        aliases.add(package_alias)
        if str(path.parent) not in {"", "."}:
            aliases.add(str(path.parent))
            aliases.add(str(path.parent).replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    module_name = module_name_from_path(file_path)
    if module_name:
        aliases.add(module_name)
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        symbol_name = collected_symbol.symbol.symbol_name
        if not symbol_name:
            continue
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_load_target(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if not normalized_target or normalized_target.startswith("@"):
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None and direct_match != current_file:
        return direct_match
    current_parent = PurePosixPath(current_file).parent
    candidate_keys: list[str] = []
    if normalized_target.startswith(":"):
        raw_candidates = [str(current_parent / normalized_target[1:])]
    elif normalized_target.startswith("//"):
        body = normalized_target[2:]
        if ":" in body:
            package_path, target_path = body.split(":", 1)
            raw_candidates = [str(PurePosixPath(package_path) / target_path)]
        else:
            raw_candidates = [
                str(PurePosixPath(body) / "BUILD.bazel"),
                str(PurePosixPath(body) / "BUILD"),
            ]
    elif ":" in normalized_target:
        package_path, target_path = normalized_target.split(":", 1)
        raw_candidates = [str(PurePosixPath(package_path) / target_path)]
    else:
        raw_candidates = [str(current_parent / normalized_target), normalized_target]
    for raw_candidate in raw_candidates:
        normalized_candidate = normalize_repository_relative_path(raw_candidate)
        if not normalized_candidate:
            continue
        candidate_keys.append(normalized_candidate)
        candidate_path = PurePosixPath(normalized_candidate)
        if (
            candidate_path.suffix.lower() not in _KNOWN_SUFFIXES
            and candidate_path.name not in _KNOWN_BASENAMES
        ):
            for suffix in (".bzl", ".star"):
                candidate_keys.append(
                    normalize_repository_relative_path(str(candidate_path.with_suffix(suffix)))
                )
    for candidate_key in tuple(dict.fromkeys(candidate_keys)):
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(dict.fromkeys(candidate_keys)),
    )


def extract_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    stripped_text = strip_comments(text)
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_target, import_body, line_number in iter_load_statements(stripped_text):
        target_file = resolve_load_target(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
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
                    target_symbol=PurePosixPath(import_target).name,
                    dependency_type="imports",
                )
            )
        for binding_alias, target_name in parse_loaded_symbols(import_body):
            import_bindings[binding_alias] = _ImportedSymbolBinding(
                alias=binding_alias,
                target_file=target_file,
                target_names=(target_name,),
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
    if not is_probable_starlark_source(path=Path(file_path), text=text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    dependencies, import_bindings = extract_import_bindings(
        file_path=file_path,
        text=text,
        module_index=module_index,
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
    seen_reference_keys: set[tuple[str, str, str, str | None]] = set()
    for collected_symbol in collected_symbols:
        symbol = collected_symbol.symbol
        symbol_text = "\n".join(
            stripped_lines[
                max(collected_symbol.local_start_line - 1, 0) : collected_symbol.local_end_line
            ]
        )
        for match in _CALL_RE.finditer(symbol_text):
            name = str(match.group("name") or "").strip()
            if (
                not name
                or name == symbol.symbol_name
                or name in _RESERVED_SYMBOL_NAMES
                or name in _BUILTIN_REFERENCE_NAMES
            ):
                continue
            target_symbol_id: str | None = None
            target_file: str | None = None
            target_names: tuple[str, ...]
            imported_binding = import_bindings.get(name)
            if imported_binding is not None:
                target_file = imported_binding.target_file
                target_names = imported_binding.target_names or (name,)
            else:
                local_target = local_symbols_by_name.get(name)
                if local_target is None:
                    continue
                target_symbol_id = local_target.symbol_id
                target_file = file_path
                target_names = (name,)
            reference_key = (symbol.symbol_id, name, target_file or "", target_symbol_id)
            if reference_key in seen_reference_keys:
                continue
            seen_reference_keys.add(reference_key)
            symbol_references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "symref",
                        {
                            "file_path": file_path,
                            "source_symbol_id": symbol.symbol_id,
                            "target": name,
                            "line": symbol.start_line,
                        },
                    ),
                    source_symbol_id=symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=target_symbol_id,
                    target_file=target_file,
                    target_names=target_names,
                    reference_type="calls",
                )
            )
    return (
        tuple(collected_symbol.symbol for collected_symbol in collected_symbols),
        tuple(dependencies),
        tuple(symbol_references),
    )
