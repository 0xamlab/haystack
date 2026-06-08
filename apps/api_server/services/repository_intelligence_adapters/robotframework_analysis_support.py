from __future__ import annotations

from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    robotframework_primitives as repository_robotframework_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = repository_robotframework_primitives._KNOWN_SUFFIXES
_line_count = repository_robotframework_primitives._line_count
_ordered_names = repository_robotframework_primitives._ordered_names
has_robotframework_path_hints = repository_robotframework_primitives.has_robotframework_path_hints
is_probable_robotframework_source = repository_robotframework_primitives.is_probable_robotframework_source
iter_keyword_call_entries = repository_robotframework_primitives.iter_keyword_call_entries
iter_resource_imports = repository_robotframework_primitives.iter_resource_imports
iter_symbol_entries = repository_robotframework_primitives.iter_symbol_entries
module_name_from_path = repository_robotframework_primitives.module_name_from_path
source_symbol_name_for_line = repository_robotframework_primitives.source_symbol_name_for_line
strip_comments = repository_robotframework_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if not has_robotframework_path_hints(path):
        return set()
    aliases = {
        file_path,
        path.name,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_robotframework_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(file_path)
    aliases.add(module_name)
    aliases.add(module_name.replace("/", "."))
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
        aliases.add(symbol_name)
        aliases.add(symbol_name.replace(" ", ""))
        if module_name:
            aliases.add(f"{module_name.replace('/', '.')}.{symbol_name}")
    return {alias for alias in aliases if alias}


def _resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = (
        str(import_target or "").strip().strip('"').strip("'").replace("\\", "/")
    )
    if (
        not normalized_target
        or normalized_target.startswith("/")
        or normalized_target.startswith("~")
        or "${" in normalized_target
    ):
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    suffix = PurePosixPath(normalized_target).suffix.lower()
    if suffix not in _KNOWN_SUFFIXES and suffix != ".py":
        candidate_keys.extend((f"{normalized_target}.robot", f"{normalized_target}.resource"))
    if current_dir:
        candidate_keys.extend(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / candidate_key))
            for candidate_key in tuple(candidate_keys)
        )
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    target_name = PurePosixPath(normalized_target).stem or PurePosixPath(normalized_target).name
    suffixes = [f"/{target_name}.robot", f"/{target_name}.resource", f"/{target_name}.py"]
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


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
    if not is_probable_robotframework_source(path=path, text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen: set[tuple[str | None, str | None, str]] = set()
    for dependency_kind, import_target, line_number in iter_resource_imports(text):
        target_file = _resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_symbol = PurePosixPath(import_target).stem or None
        dependency_type = "imports" if dependency_kind == "resource" else "uses"
        key = (target_file, target_symbol, dependency_type)
        if key in seen:
            continue
        seen.add(key)
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
                target_symbol=target_symbol,
                dependency_type=dependency_type,
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    path = PurePosixPath(file_path)
    if not is_probable_robotframework_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path) or path.stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "robotframework"},
        ),
        symbol_name=module_name,
        symbol_kind="robotframework",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"robotframework {module_name}",
    )
    symbol_entries = iter_symbol_entries(stripped_text)
    symbols: list[_Symbol] = [module_symbol]
    symbol_ids_by_name: dict[str, str] = {module_symbol.symbol_name: module_symbol.symbol_id}
    for symbol_name, symbol_kind, line_number in symbol_entries:
        symbol = _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "symbol_name": symbol_name,
                    "symbol_kind": symbol_kind,
                    "line": line_number,
                },
            ),
            symbol_name=symbol_name,
            symbol_kind=symbol_kind,
            start_line=line_number,
            end_line=line_number,
            parent_symbol_id=module_symbol.symbol_id,
            signature=f"{symbol_kind} {symbol_name}",
        )
        symbols.append(symbol)
        symbol_ids_by_name.setdefault(symbol_name, symbol.symbol_id)
    dependencies = parse_dependencies_only(
        file_path,
        stripped_text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    references: list[_SymbolReferenceCandidate] = []
    seen_references: set[tuple[str, str | None, tuple[str, ...]]] = set()
    for target_name, line_number in iter_keyword_call_entries(stripped_text):
        source_symbol_name = source_symbol_name_for_line(symbol_entries, line_number=line_number)
        source_symbol_id = symbol_ids_by_name.get(source_symbol_name or "", module_symbol.symbol_id)
        target_file = module_index.get(target_name) or module_index.get(target_name.replace(" ", ""))
        target_names = _ordered_names(target_name, target_name.replace(" ", ""))
        key = (source_symbol_id, target_file, target_names)
        if key in seen_references:
            continue
        seen_references.add(key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": source_symbol_id,
                        "target_names": target_names,
                        "line": line_number,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=target_names,
                reference_type="calls",
            )
        )
    return tuple(symbols), dependencies, tuple(references)
