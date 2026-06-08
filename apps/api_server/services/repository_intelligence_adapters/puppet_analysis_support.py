from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    puppet_primitives as repository_puppet_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_puppet_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_puppet_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_puppet_primitives.ResolveSuffixMatch

_KNOWN_PUPPET_SUFFIXES = repository_puppet_primitives._KNOWN_PUPPET_SUFFIXES
_PUPPET_MANIFEST_BASENAMES = repository_puppet_primitives._PUPPET_MANIFEST_BASENAMES
_PUPPET_SOURCE_ROOTS = repository_puppet_primitives._PUPPET_SOURCE_ROOTS
_line_count = repository_puppet_primitives._line_count
_line_number = repository_puppet_primitives._line_number
_ordered_names = repository_puppet_primitives._ordered_names
has_puppet_path_hints = repository_puppet_primitives.has_puppet_path_hints
is_probable_puppet_source = repository_puppet_primitives.is_probable_puppet_source
iter_dependency_targets = repository_puppet_primitives.iter_dependency_targets
iter_symbol_entries = repository_puppet_primitives.iter_symbol_entries
module_name_from_metadata_name = repository_puppet_primitives.module_name_from_metadata_name
path_aliases = repository_puppet_primitives.path_aliases
puppet_metadata_name = repository_puppet_primitives.puppet_metadata_name
strip_comments = repository_puppet_primitives.strip_comments


@dataclass(frozen=True)
class _ModuleContext:
    module_name: str | None
    module_root: PurePosixPath | None
    relative_path: PurePosixPath


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


def _normalize_target_name(raw_name: str) -> str:
    normalized = str(raw_name or "").strip().strip("'").strip('"').replace("/", "::")
    while normalized.startswith("::"):
        normalized = normalized[2:]
    if normalized.endswith(".pp"):
        normalized = normalized[:-3]
    return normalized.strip().lower()


def _read_module_name_from_root(root_path: Path, module_root: PurePosixPath) -> str | None:
    metadata_path = root_path / module_root / "metadata.json"
    try:
        metadata_text = metadata_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        metadata_text = ""
    metadata_name = puppet_metadata_name(metadata_text)
    if metadata_name:
        return module_name_from_metadata_name(metadata_name)
    modulefile_path = root_path / module_root / "Modulefile"
    try:
        modulefile_text = modulefile_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        modulefile_text = ""
    if modulefile_text:
        lowered = modulefile_text.lower()
        if "name" in lowered:
            for quote in ("'", '"'):
                marker = f"{quote}"
                if marker in modulefile_text:
                    break
            for line in modulefile_text.splitlines():
                stripped_line = line.strip()
                if not stripped_line.lower().startswith("name "):
                    continue
                parts = stripped_line.split(None, 1)
                if len(parts) != 2:
                    continue
                value = parts[1].strip().strip("'").strip('"')
                if value:
                    return module_name_from_metadata_name(value)
    if module_root.parent.name.lower() == "modules":
        return module_root.name.lower()
    return None


def _module_context_for_file(root_path: Path | None, file_path: str) -> _ModuleContext:
    path = PurePosixPath(file_path)
    parts = path.parts
    if root_path is not None:
        root_module_name = _read_module_name_from_root(root_path, PurePosixPath("."))
        if root_module_name and parts and parts[0].lower() in _PUPPET_SOURCE_ROOTS:
            return _ModuleContext(
                module_name=root_module_name,
                module_root=PurePosixPath("."),
                relative_path=path,
            )
        for index in range(len(parts) - 1, -1, -1):
            candidate_root = PurePosixPath(*parts[: index + 1])
            module_name = _read_module_name_from_root(root_path, candidate_root)
            if module_name:
                relative_path = (
                    PurePosixPath(*parts[index + 1 :])
                    if index + 1 < len(parts)
                    else PurePosixPath(path.name)
                )
                return _ModuleContext(
                    module_name=module_name,
                    module_root=candidate_root,
                    relative_path=relative_path,
                )
    if "modules" in parts:
        modules_index = parts.index("modules")
        if modules_index + 1 < len(parts):
            module_root = PurePosixPath(*parts[: modules_index + 2])
            relative_path = PurePosixPath(*parts[modules_index + 2 :])
            return _ModuleContext(
                module_name=parts[modules_index + 1].lower(),
                module_root=module_root,
                relative_path=relative_path,
            )
    return _ModuleContext(module_name=None, module_root=None, relative_path=path)


def _qualified_module_name(context: _ModuleContext) -> str | None:
    module_name = context.module_name
    if not module_name:
        return None
    relative_path = context.relative_path
    if not relative_path.parts:
        return module_name
    parts = [part.lower() for part in relative_path.parts]
    if parts[0] in {"manifests", "plans", "types", "functions", "tasks"} and len(parts) >= 2:
        name_parts = [module_name]
        trailing_parts = list(parts[1:])
        if trailing_parts[-1] == "init.pp":
            trailing_parts = trailing_parts[:-1]
        elif trailing_parts[-1].endswith(".pp"):
            trailing_parts[-1] = trailing_parts[-1][:-3]
        name_parts.extend(part for part in trailing_parts if part)
        return "::".join(part for part in name_parts if part)
    return module_name


def _resolve_target_file(
    *,
    file_path: str,
    raw_target_name: str,
    module_index: dict[str, str],
    root_path: Path | None,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, tuple[str, ...]]:
    context = _module_context_for_file(root_path, file_path)
    target_name = _normalize_target_name(raw_target_name)
    if not target_name:
        return None, ()
    candidate_names = [target_name]
    if context.module_name and "::" not in target_name:
        candidate_names.append(f"{context.module_name}::{target_name}")
    path_candidates: list[str] = []
    for candidate_name in candidate_names:
        path_candidates.extend(
            [
                candidate_name,
                candidate_name.replace("::", "/"),
                f"{candidate_name.replace('::', '/')}.pp",
            ]
        )
    normalized_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in path_candidates:
        normalized = normalize_repository_relative_path(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            normalized_candidates.append(normalized)
    for candidate in normalized_candidates:
        resolved = module_index.get(candidate)
        if resolved is not None:
            return resolved, tuple(candidate_names)
    return (
        resolve_suffix_match(module_index=module_index, suffixes=normalized_candidates),
        tuple(candidate_names),
    )


def _collect_symbols(
    *,
    root_path: Path | None,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    final_line = _line_count(stripped_text)
    context = _module_context_for_file(root_path, file_path)
    collected: list[_CollectedSymbol] = []
    qualified_module_name = _qualified_module_name(context)
    if qualified_module_name:
        module_symbol = _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "symbol_name": qualified_module_name,
                    "symbol_kind": "module",
                    "start_line": 1,
                },
            ),
            symbol_name=qualified_module_name,
            symbol_kind="module",
            start_line=1,
            end_line=final_line,
            parent_symbol_id=None,
            signature=f"module {qualified_module_name}",
        )
        collected.append(
            _CollectedSymbol(
                symbol=module_symbol,
                local_start_line=1,
                local_end_line=final_line,
                qualified_names=_ordered_names(
                    qualified_module_name,
                    qualified_module_name.replace("::", "/"),
                    file_path,
                    str(PurePosixPath(file_path).with_suffix("")),
                ),
            )
        )
    for symbol_name, symbol_kind, line_number, _inherits in iter_symbol_entries(stripped_text):
        qualified_names = _ordered_names(
            symbol_name,
            symbol_name.replace("::", "/"),
        )
        parent_symbol_id = collected[0].symbol.symbol_id if collected else None
        collected.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": symbol_name,
                            "symbol_kind": symbol_kind,
                            "start_line": line_number,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=line_number,
                    end_line=line_number,
                    parent_symbol_id=parent_symbol_id,
                    signature=symbol_name,
                ),
                local_start_line=line_number,
                local_end_line=line_number,
                qualified_names=qualified_names,
            )
        )
    finalized: list[_CollectedSymbol] = []
    for index, collected_symbol in enumerate(collected):
        next_start_line = (
            collected[index + 1].local_start_line if index + 1 < len(collected) else None
        )
        end_line = (
            max(next_start_line - 1, collected_symbol.local_start_line)
            if next_start_line is not None
            else final_line
        )
        symbol = collected_symbol.symbol
        finalized.append(
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
    return tuple(finalized)


def _source_symbol_id_for_line(
    collected_symbols: tuple[_CollectedSymbol, ...],
    line_number: int,
) -> str | None:
    for collected_symbol in reversed(collected_symbols):
        if collected_symbol.local_start_line <= line_number <= collected_symbol.local_end_line:
            return collected_symbol.symbol.symbol_id
    return collected_symbols[0].symbol.symbol_id if collected_symbols else None


def module_aliases_for_path(
    *,
    root_path: Path | None,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    aliases = set(path_aliases(path))
    context = _module_context_for_file(root_path, file_path)
    qualified_module_name = _qualified_module_name(context)
    if qualified_module_name:
        aliases.add(qualified_module_name)
        aliases.add(qualified_module_name.replace("::", "/"))
        aliases.add(qualified_module_name.replace("::", "."))
        aliases.add(qualified_module_name.rsplit("::", 1)[-1])
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_puppet_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    for collected_symbol in _collect_symbols(
        root_path=root_path,
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    root_path: Path | None = None,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_puppet_source(path=Path(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen: set[tuple[str | None, str, str]] = set()
    for raw_target_name, line_number in iter_dependency_targets(text):
        target_file, target_names = _resolve_target_file(
            file_path=file_path,
            raw_target_name=raw_target_name,
            module_index=module_index,
            root_path=root_path,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_symbol = target_names[0] if target_names else _normalize_target_name(raw_target_name)
        dependency_key = (target_file, target_symbol, "imports")
        if dependency_key in seen:
            continue
        seen.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "source_file": file_path,
                        "target_file": target_file,
                        "target_symbol": target_symbol,
                        "dependency_type": "imports",
                        "line_number": line_number,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="imports",
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    root_path: Path | None = None,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    if not is_probable_puppet_source(path=Path(file_path), text=text):
        return (), (), ()
    collected_symbols = _collect_symbols(
        root_path=root_path,
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        root_path=root_path,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    symbol_references: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str, str | None, tuple[str, ...], int]] = set()
    for raw_target_name, line_number in iter_dependency_targets(text):
        target_file, target_names = _resolve_target_file(
            file_path=file_path,
            raw_target_name=raw_target_name,
            module_index=module_index,
            root_path=root_path,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        source_symbol_id = _source_symbol_id_for_line(collected_symbols, line_number)
        if source_symbol_id is None or not target_names:
            continue
        key = (source_symbol_id, target_file, target_names, line_number)
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
                        "target_file": target_file,
                        "target_names": target_names,
                        "reference_type": "references_symbol",
                        "line_number": line_number,
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
    return (
        tuple(collected_symbol.symbol for collected_symbol in collected_symbols),
        dependencies,
        tuple(symbol_references),
    )
