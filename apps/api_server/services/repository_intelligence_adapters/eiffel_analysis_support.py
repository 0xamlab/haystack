from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    eiffel_primitives as repository_eiffel_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_eiffel_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_eiffel_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_eiffel_primitives.ResolveSuffixMatch

EIFFEL_CONFIG_SUFFIXES = repository_eiffel_primitives.EIFFEL_CONFIG_SUFFIXES
EIFFEL_SOURCE_SUFFIXES = repository_eiffel_primitives.EIFFEL_SOURCE_SUFFIXES
class_name_from_text = repository_eiffel_primitives.class_name_from_text
has_eiffel_path_hints = repository_eiffel_primitives.has_eiffel_path_hints
iter_feature_entries = repository_eiffel_primitives.iter_feature_entries
parse_config_location_targets = repository_eiffel_primitives.parse_config_location_targets
parse_config_variables = repository_eiffel_primitives.parse_config_variables
parse_dependency_targets = repository_eiffel_primitives.parse_dependency_targets
parse_root_class_names = repository_eiffel_primitives.parse_root_class_names
strip_comments = repository_eiffel_primitives.strip_comments
system_name_from_text = repository_eiffel_primitives.system_name_from_text

_COLLAPSE_RE = re.compile(r"[\\/]+")
_VARIABLE_REFERENCE_RE = re.compile(r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")
_MARKER_RE = repository_eiffel_primitives.EIFFEL_MARKER_RE
_CONFIG_MARKER_RE = repository_eiffel_primitives.EIFFEL_CONFIG_MARKER_RE


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _is_config_path(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in EIFFEL_CONFIG_SUFFIXES


def _is_source_path(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in EIFFEL_SOURCE_SUFFIXES


def is_probable_eiffel_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    candidate_path = PurePosixPath(path)
    if not has_eiffel_path_hints(candidate_path):
        return False
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    if not stripped_text.strip():
        return False
    if _is_config_path(candidate_path):
        return bool(_CONFIG_MARKER_RE.search(stripped_text))
    return bool(_MARKER_RE.search(stripped_text))


def _normalize_relative_target(
    raw_value: str,
    *,
    file_path: str,
    variables: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> str | None:
    candidate_value = str(raw_value or "").strip()
    if not candidate_value or "://" in candidate_value:
        return None
    for _ in range(4):
        updated_value = _VARIABLE_REFERENCE_RE.sub(
            lambda match: variables.get(str(match.group("name") or "").strip(), match.group(0)),
            candidate_value,
        )
        if updated_value == candidate_value:
            break
        candidate_value = updated_value
    collapsed_value = _COLLAPSE_RE.sub("/", candidate_value.replace("\\", "/")).strip()
    if not collapsed_value:
        return None
    if collapsed_value.startswith("/"):
        return normalize_repository_relative_path(collapsed_value)
    return normalize_repository_relative_path(
        str(PurePosixPath(file_path).parent / collapsed_value)
    )


def _resolve_class_target(
    class_name: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_name = str(class_name or "").strip()
    if not normalized_name:
        return None
    candidate_targets = (
        normalized_name,
        normalized_name.upper(),
        normalized_name.lower(),
        f"{normalized_name}.e",
        f"{normalized_name.lower()}.e",
    )
    for candidate in candidate_targets:
        target_file = module_index.get(candidate)
        if target_file is not None:
            return target_file
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_targets)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
    include_feature_symbols: bool = True,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    line_count = _line_count(stripped_text)
    if _is_config_path(PurePosixPath(file_path)):
        system_name = system_name_from_text(
            text,
            file_path=file_path,
            stripped_text=stripped_text,
        )
        config_symbol = _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {"file_path": file_path, "symbol_name": system_name, "symbol_kind": "system"},
            ),
            symbol_name=system_name,
            symbol_kind="system",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=system_name,
        )
        return (
            _CollectedSymbol(
                symbol=config_symbol,
                local_start_line=1,
                local_end_line=line_count,
                qualified_names=_ordered_names(
                    system_name,
                    file_path,
                    PurePosixPath(file_path).stem,
                ),
            ),
        )
    class_name = class_name_from_text(
        stripped_text,
        file_path=file_path,
        stripped_text=stripped_text,
    )
    class_match = repository_eiffel_primitives.EIFFEL_CLASS_RE.search(stripped_text)
    class_line = _line_number(stripped_text, class_match.start()) if class_match else 1
    class_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": class_name, "symbol_kind": "class"},
        ),
        symbol_name=class_name,
        symbol_kind="class",
        start_line=class_line,
        end_line=line_count,
        parent_symbol_id=None,
        signature=class_name,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=class_symbol,
            local_start_line=class_line,
            local_end_line=line_count,
            qualified_names=_ordered_names(
                class_name,
                file_path,
                str(PurePosixPath(file_path).with_suffix("")),
                PurePosixPath(file_path).stem,
            ),
        )
    ]
    if include_feature_symbols:
        for feature_name, start_line in iter_feature_entries(
            stripped_text,
            stripped_text=stripped_text,
        ):
            collected_symbols.append(
                _CollectedSymbol(
                    symbol=_Symbol(
                        symbol_id=stable_identifier(
                            "sym",
                            {
                                "file_path": file_path,
                                "symbol_name": feature_name,
                                "symbol_kind": "feature",
                                "start_line": start_line,
                            },
                        ),
                        symbol_name=feature_name,
                        symbol_kind="feature",
                        start_line=start_line,
                        end_line=start_line,
                        parent_symbol_id=class_symbol.symbol_id,
                        signature=feature_name,
                    ),
                    local_start_line=start_line,
                    local_end_line=start_line,
                    qualified_names=_ordered_names(feature_name, f"{class_name}.{feature_name}"),
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
            else line_count
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
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_eiffel_path_hints(path):
        return set()
    aliases = {file_path, str(path.with_suffix("")), path.stem}
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    if not is_probable_eiffel_source(path=path, text=text, stripped_text=stripped_text):
        return {alias for alias in aliases if alias}
    if not include_symbol_aliases:
        if _is_config_path(path):
            aliases.add(
                system_name_from_text(
                    text,
                    file_path=file_path,
                    stripped_text=stripped_text,
                )
            )
        else:
            aliases.add(
                class_name_from_text(
                    text,
                    file_path=file_path,
                    stripped_text=stripped_text,
                )
            )
        return {alias for alias in aliases if alias}
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
        include_feature_symbols=include_symbol_aliases,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    for root_class_name in parse_root_class_names(text, stripped_text=stripped_text):
        aliases.add(root_class_name)
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[_Dependency, ...]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    if _is_config_path(PurePosixPath(file_path)):
        variables = parse_config_variables(text, stripped_text=stripped_text)
        dependencies: list[_Dependency] = []
        for line_number, raw_target in enumerate(
            parse_config_location_targets(text, stripped_text=stripped_text),
            start=1,
        ):
            target_file = _normalize_relative_target(
                raw_target,
                file_path=file_path,
                variables=variables,
                normalize_repository_relative_path=normalize_repository_relative_path,
            )
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": raw_target,
                            "line": line_number,
                            "type": "config_import",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=None,
                    dependency_type="config_imports",
                )
            )
        for root_class_name in parse_root_class_names(text, stripped_text=stripped_text):
            target_file = _resolve_class_target(
                root_class_name,
                module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": root_class_name,
                            "type": "root_class",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=root_class_name,
                    dependency_type="config_root",
                )
            )
        return tuple(dependencies)
    dependencies: list[_Dependency] = []
    for target_name in parse_dependency_targets(
        text,
        file_path=file_path,
        stripped_text=stripped_text,
    ):
        target_file = _resolve_class_target(
            target_name,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": target_name, "type": "class_reference"},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="references",
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
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    stripped_text = strip_comments(text)
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    symbol_references: list[_SymbolReferenceCandidate] = []
    source_symbol = collected_symbols[0].symbol if collected_symbols else None
    if source_symbol is not None:
        for dependency in dependencies:
            target_name = str(dependency.target_symbol or "").strip()
            if not target_name:
                continue
            symbol_references.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "file_path": file_path,
                            "source_symbol_id": source_symbol.symbol_id,
                            "target": target_name,
                            "type": dependency.dependency_type,
                        },
                    ),
                    source_symbol_id=source_symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=dependency.target_file,
                    target_names=_ordered_names(target_name),
                    reference_type=dependency.dependency_type,
                )
            )
    return (
        tuple(collected_symbol.symbol for collected_symbol in collected_symbols),
        dependencies,
        tuple(symbol_references),
    )
