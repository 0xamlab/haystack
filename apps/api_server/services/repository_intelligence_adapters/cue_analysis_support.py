from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    cue_primitives as repository_cue_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_cue_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_cue_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_cue_primitives.ResolveSuffixMatch

_CollectedSymbol = repository_cue_primitives._CollectedSymbol
_KNOWN_SUFFIXES = repository_cue_primitives._KNOWN_SUFFIXES
_QUALIFIED_REFERENCE_RE = repository_cue_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_cue_primitives._RESERVED_SYMBOL_NAMES
_UNQUALIFIED_REFERENCE_RE = repository_cue_primitives._UNQUALIFIED_REFERENCE_RE
_line_count = repository_cue_primitives._line_count
_line_number = repository_cue_primitives._line_number
_ordered_names = repository_cue_primitives._ordered_names
cue_module_name_from_text = repository_cue_primitives.cue_module_name_from_text
has_cue_path_hints = repository_cue_primitives.has_cue_path_hints
is_probable_cue_source = repository_cue_primitives.is_probable_cue_source
iter_symbol_entries = repository_cue_primitives.iter_symbol_entries
package_name_from_text = repository_cue_primitives.package_name_from_text
parse_import_statements = repository_cue_primitives.parse_import_statements
parse_reference_targets = repository_cue_primitives.parse_reference_targets
parse_unqualified_reference_targets = (
    repository_cue_primitives.parse_unqualified_reference_targets
)
strip_comments = repository_cue_primitives.strip_comments

_IMPORT_VERSION_SUFFIX_RE = re.compile(r"@[^/]+$")


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _project_root_and_module_prefix(
    *, root_path: Path, file_path: str
) -> tuple[str | None, str | None]:
    pure_path = PurePosixPath(file_path)
    search_parts = list(pure_path.parent.parts)
    while True:
        candidate_root = PurePosixPath(*search_parts) if search_parts else PurePosixPath(".")
        module_manifest = (
            candidate_root / "cue.mod" / "module.cue"
            if str(candidate_root) not in {"", "."}
            else PurePosixPath("cue.mod/module.cue")
        )
        module_path = root_path / module_manifest
        if module_path.is_file() and not module_path.is_symlink():
            try:
                module_text = module_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                module_text = ""
            return (
                "" if str(candidate_root) in {"", "."} else str(candidate_root),
                cue_module_name_from_text(module_text) or None,
            )
        if not search_parts:
            return None, None
        search_parts.pop()


def _module_relative_parent(file_path: str, project_root: str | None) -> str:
    file_parent = PurePosixPath(file_path).parent
    if project_root in {None, "", "."}:
        return "" if str(file_parent) == "." else str(file_parent)
    root_parts = PurePosixPath(project_root).parts
    parent_parts = file_parent.parts
    if tuple(parent_parts[: len(root_parts)]) != tuple(root_parts):
        return ""
    relative_parts = parent_parts[len(root_parts) :]
    return "/".join(relative_parts)


def _package_import_aliases(file_path: str, *, root_path: Path, text: str) -> set[str]:
    aliases: set[str] = set()
    project_root, module_prefix = _project_root_and_module_prefix(
        root_path=root_path,
        file_path=file_path,
    )
    relative_parent = _module_relative_parent(file_path, project_root)
    if relative_parent:
        aliases.add(relative_parent)
    elif module_prefix:
        aliases.add(module_prefix)
    if module_prefix and relative_parent:
        aliases.add(f"{module_prefix}/{relative_parent}")
    path_parts = PurePosixPath(file_path).parts
    for marker in ("gen", "pkg", "usr"):
        marker_parts = ("cue.mod", marker)
        for index in range(len(path_parts) - len(marker_parts)):
            if tuple(path_parts[index : index + len(marker_parts)]) != marker_parts:
                continue
            trailing_parts = path_parts[index + len(marker_parts) : -1]
            if trailing_parts:
                aliases.add("/".join(trailing_parts))
            break
    package_name = package_name_from_text(text)
    if package_name:
        aliases.add(package_name)
        parent_dir = PurePosixPath(file_path).parent
        if str(parent_dir) not in {"", "."}:
            aliases.add(f"{parent_dir}/{package_name}")
    return {alias for alias in aliases if alias}


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    package_name = package_name_from_text(stripped_text)
    module_name = package_name or _without_suffix_path(PurePosixPath(file_path))
    final_line = _line_count(stripped_text)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name,
                "symbol_kind": "package",
                "start_line": 1,
            },
        ),
        symbol_name=module_name,
        symbol_kind="package",
        start_line=1,
        end_line=final_line,
        parent_symbol_id=None,
        signature=f"package {module_name}",
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=final_line,
            qualified_names=_ordered_names(
                module_name,
                _without_suffix_path(PurePosixPath(file_path)),
                file_path,
            ),
        )
    ]
    for symbol_kind, symbol_name, start_line in iter_symbol_entries(stripped_text):
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
                qualified_names=_ordered_names(
                    symbol_name,
                    f"{module_name}.{symbol_name}" if module_name else "",
                    f"{module_name}/{symbol_name}" if module_name else "",
                ),
            )
        )
    finalized_symbols: list[_CollectedSymbol] = []
    for index, collected_symbol in enumerate(collected_symbols):
        next_start_line = (
            collected_symbols[index + 1].local_start_line
            if index + 1 < len(collected_symbols)
            else None
        )
        end_line = (
            max(next_start_line - 1, collected_symbol.local_start_line)
            if next_start_line is not None
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


def _source_symbol_id_for_line(
    collected_symbols: tuple[_CollectedSymbol, ...], line_number: int
) -> str | None:
    for collected_symbol in reversed(collected_symbols):
        if collected_symbol.local_start_line <= line_number <= collected_symbol.local_end_line:
            return collected_symbol.symbol.symbol_id
    return collected_symbols[0].symbol.symbol_id if collected_symbols else None


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        _without_suffix_path(path),
        path.stem,
        str(path.parent) if str(path.parent) != "." else "",
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_cue_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    aliases.update(_package_import_aliases(file_path, root_path=root_path, text=text))
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def _candidate_import_keys(
    *,
    file_path: str,
    import_target: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    root_path: Path | None = None,
) -> tuple[str, ...]:
    normalized_target = str(import_target or "").strip().strip('"').strip("'")
    if not normalized_target:
        return ()
    normalized_target = _IMPORT_VERSION_SUFFIX_RE.sub("", normalized_target)
    current_directory = normalize_repository_relative_path(str(PurePosixPath(file_path).parent))
    path_part = normalized_target
    if normalized_target.startswith(("./", "../")) and current_directory:
        path_part = normalize_repository_relative_path(
            str(PurePosixPath(current_directory) / normalized_target)
        )
    candidate_keys = [
        path_part,
        f"{path_part}.cue",
        f"{path_part}/main.cue",
        f"{path_part}/schema.cue",
        f"cue.mod/gen/{path_part}",
        f"cue.mod/pkg/{path_part}",
        f"cue.mod/usr/{path_part}",
    ]
    if root_path is not None:
        project_root, module_prefix = _project_root_and_module_prefix(
            root_path=root_path,
            file_path=file_path,
        )
        if module_prefix and path_part.startswith(f"{module_prefix}/"):
            relative_target = path_part[len(module_prefix) + 1 :]
            if project_root:
                candidate_keys.extend(
                    (
                        f"{project_root}/{relative_target}",
                        f"{project_root}/{relative_target}.cue",
                    )
                )
            else:
                candidate_keys.extend((relative_target, f"{relative_target}.cue"))
    normalized_candidates: list[str] = []
    seen: set[str] = set()
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if normalized_candidate and normalized_candidate not in seen:
            seen.add(normalized_candidate)
            normalized_candidates.append(normalized_candidate)
    return tuple(normalized_candidates)


def resolve_import(
    *,
    file_path: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    root_path: Path | None = None,
) -> str | None:
    candidate_keys = _candidate_import_keys(
        file_path=file_path,
        import_target=import_target,
        normalize_repository_relative_path=normalize_repository_relative_path,
        root_path=root_path,
    )
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_keys)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    root_path: Path | None = None,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    for statement in parse_import_statements(text):
        target_file = resolve_import(
            file_path=file_path,
            import_target=statement.target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
            root_path=root_path,
        )
        dependency_key = (target_file, statement.target, "imports")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "source_file": file_path,
                            "target_file": target_file,
                            "target_symbol": statement.target,
                            "dependency_type": "imports",
                            "line_number": statement.line_number,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=statement.target,
                    dependency_type="imports",
                )
            )
        alias = statement.alias or statement.selector or PurePosixPath(statement.target).name
        alias = alias.strip()
        if alias:
            target_names = _ordered_names(statement.selector or "", alias)
            import_bindings[alias] = _ImportedSymbolBinding(
                alias=alias,
                target_file=target_file,
                target_names=target_names,
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
    root_path: Path | None = None,
) -> tuple[_Dependency, ...]:
    dependencies, _bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        root_path=root_path,
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
    root_path: Path | None = None,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    if not is_probable_cue_source(path=Path(file_path), text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
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
        root_path=root_path,
    )
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, tuple[str, ...], int]] = set()
    local_names = {
        name
        for collected_symbol in collected_symbols
        for name in collected_symbol.qualified_names
        if name and "." not in name and "/" not in name
    }
    for alias, target_name, line_number in parse_reference_targets(stripped_text):
        binding = import_bindings.get(alias)
        if binding is None:
            continue
        source_symbol_id = _source_symbol_id_for_line(collected_symbols, line_number)
        if source_symbol_id is None:
            continue
        target_names = _ordered_names(target_name, *binding.target_names)
        key = (binding.target_file, target_names, line_number)
        if key in seen_reference_keys:
            continue
        seen_reference_keys.add(key)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "source_file": file_path,
                        "source_symbol_id": source_symbol_id,
                        "target_file": binding.target_file,
                        "target_names": target_names,
                        "reference_type": "references",
                        "line_number": line_number,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=binding.target_file,
                target_names=target_names,
                reference_type="references",
            )
        )
    for name, line_number in parse_unqualified_reference_targets(stripped_text):
        if (
            name in _RESERVED_SYMBOL_NAMES
            or name in local_names
            or name in import_bindings
            or name in {"package", "module"}
        ):
            continue
        matching_binding = next(
            (
                binding
                for binding in import_bindings.values()
                if name in binding.target_names
            ),
            None,
        )
        if matching_binding is None:
            continue
        source_symbol_id = _source_symbol_id_for_line(collected_symbols, line_number)
        if source_symbol_id is None:
            continue
        target_names = _ordered_names(name, *matching_binding.target_names)
        key = (matching_binding.target_file, target_names, line_number)
        if key in seen_reference_keys:
            continue
        seen_reference_keys.add(key)
        symbol_references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "source_file": file_path,
                        "source_symbol_id": source_symbol_id,
                        "target_file": matching_binding.target_file,
                        "target_names": target_names,
                        "reference_type": "references",
                        "line_number": line_number,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=matching_binding.target_file,
                target_names=target_names,
                reference_type="references",
            )
        )
    return (
        tuple(collected_symbol.symbol for collected_symbol in collected_symbols),
        dependencies,
        tuple(symbol_references),
    )
