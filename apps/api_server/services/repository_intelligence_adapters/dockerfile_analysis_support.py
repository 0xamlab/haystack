from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    dockerfile_primitives as repository_dockerfile_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_dockerfile_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_dockerfile_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_dockerfile_primitives.ResolveSuffixMatch

DOCKERFILE_BASENAMES = repository_dockerfile_primitives.DOCKERFILE_BASENAMES
DOCKERFILE_SUFFIXES = repository_dockerfile_primitives.DOCKERFILE_SUFFIXES
_line_count = repository_dockerfile_primitives._line_count
_ordered_names = repository_dockerfile_primitives._ordered_names
has_dockerfile_path_hints = repository_dockerfile_primitives.has_dockerfile_path_hints
is_probable_dockerfile_source = repository_dockerfile_primitives.is_probable_dockerfile_source
iter_copy_add_entries = repository_dockerfile_primitives.iter_copy_add_entries
iter_run_local_path_entries = repository_dockerfile_primitives.iter_run_local_path_entries
iter_stage_entries = repository_dockerfile_primitives.iter_stage_entries
module_name_from_path = repository_dockerfile_primitives.module_name_from_path
source_symbol_name_for_line = repository_dockerfile_primitives.source_symbol_name_for_line
strip_comments = repository_dockerfile_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if not has_dockerfile_path_hints(path):
        return set()
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        path.name,
        module_name,
        module_name.replace("/", "."),
        path.stem if path.suffix else path.name,
    }
    if path.name.lower() in DOCKERFILE_BASENAMES and path.parent not in {
        PurePosixPath("."),
        PurePosixPath(""),
    }:
        aliases.add(str(path.parent))
        aliases.add(str(path.parent).replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_dockerfile_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    for stage_name, _image, _alias, stage_key, _line_number in iter_stage_entries(text):
        aliases.add(stage_name)
        aliases.add(stage_key)
        aliases.add(f"{module_name.replace('/', '.')}.{stage_name}")
    return {alias for alias in aliases if alias}


def _local_dependency_symbol_name(target_file: str) -> str | None:
    path = PurePosixPath(target_file)
    if path.name.lower() in DOCKERFILE_BASENAMES:
        return module_name_from_path(target_file)
    if path.suffix.lower() in DOCKERFILE_SUFFIXES:
        return module_name_from_path(target_file)
    return path.stem or path.name or None


def _resolve_local_context_path(
    *,
    current_file: str,
    raw_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> str | None:
    normalized_target = str(raw_target or "").strip().replace("\\", "/")
    if (
        not normalized_target
        or normalized_target == "."
        or normalized_target.startswith(("/", "~", "http://", "https://"))
        or "$" in normalized_target
        or "*" in normalized_target
        or "?" in normalized_target
    ):
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    if current_dir:
        candidate_keys.append(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / normalized_target))
        )
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    return None


def _stage_symbol_index(
    text: str,
) -> tuple[
    tuple[tuple[str, str, str | None, str, int], ...],
    dict[str, str],
]:
    stage_entries = iter_stage_entries(text)
    stage_aliases: dict[str, str] = {}
    for stage_name, _image, alias, stage_key, _line_number in stage_entries:
        for alias_name in _ordered_names(stage_name, alias or "", stage_key):
            stage_aliases.setdefault(alias_name, stage_name)
    return stage_entries, stage_aliases


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    del resolve_suffix_match
    if not is_probable_dockerfile_source(path=PurePosixPath(file_path), text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str, str | None, str | None]] = set()
    stage_entries, stage_aliases = _stage_symbol_index(text)
    for stage_name, image, _alias, _stage_key, line_number in stage_entries:
        target_stage = stage_aliases.get(image)
        if target_stage is None or target_stage == stage_name:
            continue
        dependency_key = ("builds_from", file_path, target_stage)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "line": line_number,
                        "kind": "builds_from",
                        "target_stage": target_stage,
                    },
                ),
                source_file=file_path,
                target_file=file_path,
                target_symbol=target_stage,
                dependency_type="builds_from",
            )
        )
    for instruction_name, source_path, copy_from, line_number in iter_copy_add_entries(text):
        target_stage = stage_aliases.get(str(copy_from or "").strip())
        if target_stage is not None:
            dependency_key = ("copies_from", file_path, target_stage)
            if dependency_key not in seen_dependencies:
                seen_dependencies.add(dependency_key)
                dependencies.append(
                    _Dependency(
                        dependency_edge_id=stable_identifier(
                            "dep",
                            {
                                "file_path": file_path,
                                "line": line_number,
                                "kind": "copies_from",
                                "target_stage": target_stage,
                            },
                        ),
                        source_file=file_path,
                        target_file=file_path,
                        target_symbol=target_stage,
                        dependency_type="copies_from",
                    )
                )
            continue
        target_file = _resolve_local_context_path(
            current_file=file_path,
            raw_target=source_path,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
        )
        if target_file is None:
            continue
        target_symbol = _local_dependency_symbol_name(target_file)
        dependency_type = "adds" if instruction_name == "add" else "copies"
        dependency_key = (dependency_type, target_file, target_symbol)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "line": line_number,
                        "kind": dependency_type,
                        "target_file": target_file,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type=dependency_type,
            )
        )
    for source_path, line_number in iter_run_local_path_entries(text):
        target_file = _resolve_local_context_path(
            current_file=file_path,
            raw_target=source_path,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
        )
        if target_file is None:
            continue
        target_symbol = _local_dependency_symbol_name(target_file)
        dependency_key = ("executes", target_file, target_symbol)
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "line": line_number,
                        "kind": "executes",
                        "target_file": target_file,
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="executes",
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
    if not is_probable_dockerfile_source(path=PurePosixPath(file_path), text=text):
        return (), (), ()

    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "dockerfile"},
        ),
        symbol_name=module_name,
        symbol_kind="dockerfile",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=module_name,
    )
    stage_entries, stage_aliases = _stage_symbol_index(stripped_text)
    collected_symbols: list[tuple[_Symbol, int]] = [(module_symbol, 1)]
    for stage_name, image, _alias, stage_key, line_number in stage_entries:
        collected_symbols.append(
            (
                _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": stage_name,
                            "symbol_kind": "stage",
                            "line": line_number,
                            "stage_key": stage_key,
                        },
                    ),
                    symbol_name=stage_name,
                    symbol_kind="stage",
                    start_line=line_number,
                    end_line=line_number,
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=f"FROM {image}",
                ),
                line_number,
            )
        )
    finalized_symbols: list[_Symbol] = []
    final_line = _line_count(stripped_text)
    for index, (symbol, start_line) in enumerate(collected_symbols):
        next_start = collected_symbols[index + 1][1] if index + 1 < len(collected_symbols) else None
        end_line = final_line if next_start is None else max(start_line, next_start - 1)
        finalized_symbols.append(
            _Symbol(
                symbol_id=symbol.symbol_id,
                symbol_name=symbol.symbol_name,
                symbol_kind=symbol.symbol_kind,
                start_line=symbol.start_line,
                end_line=end_line,
                parent_symbol_id=symbol.parent_symbol_id,
                signature=symbol.signature,
            )
        )

    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    local_symbol_ids = {
        symbol.symbol_name: symbol.symbol_id
        for symbol in finalized_symbols
        if symbol.symbol_kind == "stage"
    }
    references: list[_SymbolReferenceCandidate] = []
    seen_references: set[tuple[str, str | None, str]] = set()

    def _append_reference(
        *,
        source_symbol_id: str,
        target_name: str,
    ) -> None:
        reference_key = (source_symbol_id, file_path, target_name)
        if reference_key in seen_references:
            return
        seen_references.add(reference_key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "source_symbol_id": source_symbol_id,
                        "target_name": target_name,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=local_symbol_ids.get(target_name),
                target_file=file_path,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
        )

    for stage_name, image, _alias, _stage_key, _line_number in stage_entries:
        source_symbol_id = local_symbol_ids.get(stage_name)
        target_stage = stage_aliases.get(image)
        if source_symbol_id is not None and target_stage is not None and target_stage != stage_name:
            _append_reference(source_symbol_id=source_symbol_id, target_name=target_stage)
    for _instruction_name, _source_path, copy_from, line_number in iter_copy_add_entries(text):
        target_stage = stage_aliases.get(str(copy_from or "").strip())
        if target_stage is None:
            continue
        source_stage_name = source_symbol_name_for_line(stage_entries, line_number=line_number)
        source_symbol_id = local_symbol_ids.get(source_stage_name or "", module_symbol.symbol_id)
        _append_reference(source_symbol_id=source_symbol_id, target_name=target_stage)

    return tuple(finalized_symbols), dependencies, tuple(references)
