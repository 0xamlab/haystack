from __future__ import annotations

from collections.abc import Mapping
from collections import defaultdict
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    moonbit_primitives as repository_moonbit_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_moonbit_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_moonbit_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_moonbit_primitives.ResolveSuffixMatch

MOONBIT_CONFIG_BASENAMES = repository_moonbit_primitives.MOONBIT_CONFIG_BASENAMES
MOONBIT_SOURCE_SUFFIXES = repository_moonbit_primitives.MOONBIT_SOURCE_SUFFIXES
_CollectedSymbol = repository_moonbit_primitives._CollectedSymbol
_QUALIFIED_REFERENCE_RE = repository_moonbit_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_moonbit_primitives._RESERVED_SYMBOL_NAMES
_TYPE_METHOD_REFERENCE_RE = repository_moonbit_primitives._TYPE_METHOD_REFERENCE_RE
_UNQUALIFIED_CALL_RE = repository_moonbit_primitives._UNQUALIFIED_CALL_RE
_line_count = repository_moonbit_primitives._line_count
has_moonbit_path_hints = repository_moonbit_primitives.has_moonbit_path_hints
is_probable_moonbit_config = repository_moonbit_primitives.is_probable_moonbit_config
is_probable_moonbit_source = repository_moonbit_primitives.is_probable_moonbit_source
iter_symbol_entries = repository_moonbit_primitives.iter_symbol_entries
module_name_from_path = repository_moonbit_primitives.module_name_from_path
normalize_identifier = repository_moonbit_primitives.normalize_identifier
normalize_import_target = repository_moonbit_primitives.normalize_import_target
parse_import_entries = repository_moonbit_primitives.parse_import_entries
parse_using_entries = repository_moonbit_primitives.parse_using_entries
strip_comments = repository_moonbit_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def _nearest_config_path(file_path: str, module_index: dict[str, str], basename: str) -> str | None:
    current = PurePosixPath(file_path).parent
    while True:
        candidate = str(current / basename) if str(current) not in {"", "."} else basename
        normalized_candidate = candidate.replace("\\", "/")
        if normalized_candidate in module_index:
            return module_index[normalized_candidate]
        if str(current) in {"", "."} or not current.parts:
            break
        current = current.parent
    return None


def _package_directory_from_file_path(file_path: str, module_index: dict[str, str]) -> PurePosixPath:
    package_config_path = _nearest_config_path(file_path, module_index, "moon.pkg")
    if package_config_path:
        return PurePosixPath(package_config_path).parent
    return PurePosixPath(file_path).parent


def _module_root_directory(file_path: str, module_index: dict[str, str]) -> PurePosixPath:
    module_config_path = _nearest_config_path(file_path, module_index, "moon.mod")
    if module_config_path:
        return PurePosixPath(module_config_path).parent
    return PurePosixPath(".")


def _package_alias_for_path(file_path: str, module_index: dict[str, str]) -> str:
    package_directory = _package_directory_from_file_path(file_path, module_index)
    return package_directory.name or module_name_from_path(file_path)


def _package_relative_path(file_path: str, module_index: dict[str, str]) -> str:
    package_directory = _package_directory_from_file_path(file_path, module_index)
    module_root = _module_root_directory(file_path, module_index)
    try:
        relative_path = package_directory.relative_to(module_root)
    except ValueError:
        relative_path = package_directory
    return str(relative_path).replace("\\", "/").strip("./")


def _parse_module_name_from_config_text(text: str) -> str:
    for raw_line in text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line.startswith("name"):
            continue
        if "=" not in stripped_line:
            continue
        _name, raw_value = stripped_line.split("=", 1)
        normalized_value = normalize_identifier(raw_value).strip('"').strip("'")
        if normalized_value:
            return normalized_value
    return ""


def _full_package_import_path(
    *,
    root_path: Path,
    file_path: str,
    cached_text_by_path: Mapping[str, str] | None = None,
) -> str:
    normalized_path = PurePosixPath(file_path)
    current = normalized_path.parent
    while True:
        candidate_path = str(current / "moon.mod").replace("\\", "/").strip("./")
        candidate = root_path / current / "moon.mod"
        if candidate.is_file() and not candidate.is_symlink():
            try:
                config_text = (
                    cached_text_by_path.get(candidate_path)
                    if cached_text_by_path is not None
                    else None
                )
                if config_text is None:
                    config_text = candidate.read_text(encoding="utf-8", errors="replace")
                module_name = _parse_module_name_from_config_text(config_text)
            except OSError:
                module_name = ""
            if not module_name:
                break
            try:
                relative_package = normalized_path.parent.relative_to(current)
            except ValueError:
                relative_package = PurePosixPath(".")
            normalized_relative_package = str(relative_package).replace("\\", "/").strip("./")
            return (
                f"{module_name}/{normalized_relative_package}".rstrip("/")
                if normalized_relative_package
                else module_name
            )
        if str(current) in {"", "."} or not current.parts:
            break
        current = current.parent
    return ""


def _is_package_entry_file(*, file_path: str, package_alias: str) -> bool:
    stem = PurePosixPath(file_path).with_suffix("").name
    return stem == package_alias or stem == "main" or stem.startswith("pkg.generated")


def resolve_import_target(
    import_target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_import_target(import_target)
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match and PurePosixPath(direct_match).name.lower() not in MOONBIT_CONFIG_BASENAMES:
        return direct_match
    path_segments = [segment for segment in normalized_target.split("/") if segment]
    candidate_keys: list[str] = [normalized_target]
    if len(path_segments) >= 3:
        relative_target = "/".join(path_segments[2:])
        if relative_target:
            candidate_keys.extend((relative_target, path_segments[-1]))
    elif path_segments:
        candidate_keys.append(path_segments[-1])
    leaf_name = path_segments[-1] if path_segments else normalized_target
    candidate_keys.extend(
        (
            f"{normalized_target}/{leaf_name}.mbt",
            f"{normalized_target}/{leaf_name}.mbti",
            f"{normalized_target}/pkg.generated.mbti",
        )
    )
    normalized_candidates: list[str] = []
    seen: set[str] = set()
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate or normalized_candidate in seen:
            continue
        seen.add(normalized_candidate)
        normalized_candidates.append(normalized_candidate)
        resolved = module_index.get(normalized_candidate)
        if resolved is not None:
            if (
                PurePosixPath(resolved).name.lower() in MOONBIT_CONFIG_BASENAMES
                and PurePosixPath(normalized_candidate).name.lower()
                not in MOONBIT_CONFIG_BASENAMES
            ):
                continue
            return resolved
    resolved_match = resolve_suffix_match(module_index=module_index, suffixes=normalized_candidates)
    if resolved_match is not None:
        return resolved_match
    return direct_match


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    final_line = _line_count(stripped_text)
    package_alias = _package_alias_for_path(file_path, module_index)
    default_module_name = package_alias or module_name_from_path(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": default_module_name or file_path,
                "symbol_kind": "module",
                "start_line": 1,
            },
        ),
        symbol_name=default_module_name or file_path,
        symbol_kind="module",
        start_line=1,
        end_line=final_line,
        parent_symbol_id=None,
        signature=f"module {default_module_name}" if default_module_name else None,
    )
    package_relative_path = _package_relative_path(file_path, module_index)
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=final_line,
            qualified_names=repository_moonbit_primitives._ordered_names(
                default_module_name,
                package_relative_path,
            ),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(
        text,
        stripped_text=stripped_text,
    ):
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
                qualified_names=repository_moonbit_primitives._ordered_names(
                    symbol_name,
                    f"{default_module_name}.{symbol_name}" if default_module_name else "",
                ),
            )
        )
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
    text: str | None = None,
    stripped_text: str | None = None,
    include_symbol_aliases: bool = True,
    cached_text_by_path: Mapping[str, str] | None = None,
) -> set[str]:
    path = PurePosixPath(file_path)
    aliases = {
        file_path,
        _without_suffix_path(path),
        path.name,
    }
    if path.name.lower() in MOONBIT_CONFIG_BASENAMES:
        return {alias for alias in aliases if alias}
    if path.suffix.lower() not in MOONBIT_SOURCE_SUFFIXES:
        return set()
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    if not is_probable_moonbit_source(path=Path(file_path), text=text, stripped_text=stripped_text):
        return {alias for alias in aliases if alias}
    package_alias = path.parent.name or path.stem
    aliases.add(path.stem)
    if _is_package_entry_file(file_path=file_path, package_alias=package_alias):
        aliases.add(package_alias)
        full_import_path = _full_package_import_path(
            root_path=root_path,
            file_path=file_path,
            cached_text_by_path=cached_text_by_path,
        )
        if full_import_path:
            aliases.add(full_import_path)
            if "/" in full_import_path:
                relative_import_path = "/".join(full_import_path.split("/")[2:])
                if relative_import_path:
                    aliases.add(relative_import_path)
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    module_index = {file_path: file_path}
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def _config_dependencies_for_source(
    *,
    file_path: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    seen: set[tuple[str, str]] = set()
    for basename, dependency_type in (("moon.pkg", "package_config"), ("moon.mod", "module_config")):
        config_path = _nearest_config_path(file_path, module_index, basename)
        if not config_path or (config_path, dependency_type) in seen:
            continue
        seen.add((config_path, dependency_type))
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": config_path,
                        "kind": dependency_type,
                        "line": 1,
                    },
                ),
                source_file=file_path,
                target_file=config_path,
                target_symbol=PurePosixPath(config_path).name,
                dependency_type=dependency_type,
            )
        )
    return tuple(dependencies)


def _config_import_dependencies(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    seen: set[tuple[str | None, str, str]] = set()
    for import_target, import_alias, line_number in parse_import_entries(
        text,
        stripped_text=stripped_text,
    ):
        target_file = resolve_import_target(
            import_target,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, import_alias or "")
        if dependency_key in seen:
            continue
        seen.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "alias": import_alias,
                        "line": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=import_alias or PurePosixPath(import_target).name,
                dependency_type="imports",
            )
        )
    return tuple(dependencies)


def _using_import_bindings(
    *,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for alias, exported_names, _line_number in parse_using_entries(
        text,
        stripped_text=stripped_text,
    ):
        target_file = resolve_import_target(
            alias,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if not target_file:
            continue
        for exported_name in exported_names:
            if not exported_name or exported_name in _RESERVED_SYMBOL_NAMES:
                continue
            bindings.setdefault(
                exported_name,
                _ImportedSymbolBinding(
                    alias=exported_name,
                    target_file=target_file,
                    target_names=(exported_name,),
                ),
            )
    return bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    path = Path(file_path)
    stripped_text = strip_comments(text)
    if path.name.lower() in MOONBIT_CONFIG_BASENAMES:
        if not is_probable_moonbit_config(path=path, text=text, stripped_text=stripped_text):
            return ()
        return _config_import_dependencies(
            file_path=file_path,
            text=text,
            module_index=module_index,
            stable_identifier=stable_identifier,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
            stripped_text=stripped_text,
        )
    if not is_probable_moonbit_source(path=path, text=text, stripped_text=stripped_text):
        return ()
    return _config_dependencies_for_source(
        file_path=file_path,
        module_index=module_index,
        stable_identifier=stable_identifier,
    )


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
    path = Path(file_path)
    stripped_text = strip_comments(text)
    if path.name.lower() in MOONBIT_CONFIG_BASENAMES:
        if not is_probable_moonbit_config(path=path, text=text, stripped_text=stripped_text):
            return (), (), ()
        dependencies = _config_import_dependencies(
            file_path=file_path,
            text=text,
            module_index=module_index,
            stable_identifier=stable_identifier,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
            stripped_text=stripped_text,
        )
        return (), dependencies, ()
    if not is_probable_moonbit_source(path=path, text=text, stripped_text=stripped_text):
        return (), (), ()

    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    dependencies = _config_dependencies_for_source(
        file_path=file_path,
        module_index=module_index,
        stable_identifier=stable_identifier,
    )
    local_symbols_by_name: dict[str, list[_Symbol]] = defaultdict(list)
    for symbol in symbols:
        local_symbols_by_name[symbol.symbol_name].append(symbol)
    imported_bindings = _using_import_bindings(
        text=text,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
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

    for symbol in symbols[1:]:
        snippet = "\n".join(
            lines[max(symbol.start_line - 1, 0) : max(symbol.end_line, symbol.start_line)]
        )
        for match in _QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias = normalize_identifier(str(match.group("alias") or ""))
            target_name = normalize_identifier(str(match.group("name") or ""))
            method_suffix = normalize_identifier(str(match.group("method") or ""))
            target_file = resolve_import_target(
                alias,
                module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if not target_file or not target_name:
                continue
            resolved_target_name = (
                f"{target_name}{method_suffix}" if method_suffix else target_name
            )
            _append_reference(
                source_symbol=symbol,
                target_file=target_file,
                target_name=resolved_target_name,
                target_symbol_id=None,
            )
        for match in _TYPE_METHOD_REFERENCE_RE.finditer(snippet):
            owner = normalize_identifier(str(match.group("owner") or ""))
            target_name = normalize_identifier(str(match.group("name") or ""))
            if not owner or not target_name:
                continue
            method_symbol_name = f"{owner}::{target_name}"
            local_target = next(iter(local_symbols_by_name.get(method_symbol_name, ())), None)
            if local_target is not None:
                _append_reference(
                    source_symbol=symbol,
                    target_file=file_path,
                    target_name=method_symbol_name,
                    target_symbol_id=local_target.symbol_id,
                )
                continue
            target_file = resolve_import_target(
                owner,
                module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if target_file:
                _append_reference(
                    source_symbol=symbol,
                    target_file=target_file,
                    target_name=method_symbol_name,
                    target_symbol_id=None,
                )
        for match in _UNQUALIFIED_CALL_RE.finditer(snippet):
            target_name = normalize_identifier(str(match.group("name") or ""))
            if (
                not target_name
                or target_name in _RESERVED_SYMBOL_NAMES
                or target_name == symbol.symbol_name
            ):
                continue
            local_target = next(iter(local_symbols_by_name.get(target_name, ())), None)
            if local_target is not None:
                _append_reference(
                    source_symbol=symbol,
                    target_file=file_path,
                    target_name=target_name,
                    target_symbol_id=local_target.symbol_id,
                )
                continue
            binding = imported_bindings.get(target_name)
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


__all__ = [
    "MOONBIT_CONFIG_BASENAMES",
    "MOONBIT_SOURCE_SUFFIXES",
    "has_moonbit_path_hints",
    "is_probable_moonbit_config",
    "is_probable_moonbit_source",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import_target",
]
