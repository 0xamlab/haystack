from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    gams_primitives as repository_gams_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_gams_primitives.StableIdentifier

_BUILTIN_NAMES = repository_gams_primitives._BUILTIN_NAMES
_IDENTIFIER_RE = repository_gams_primitives._IDENTIFIER_RE
_SOURCE_SUFFIXES = repository_gams_primitives._SOURCE_SUFFIXES
collect_symbol_entries = repository_gams_primitives.collect_symbol_entries
has_gams_path_hints = repository_gams_primitives.has_gams_path_hints
import_targets_for_text = repository_gams_primitives.import_targets_for_text
is_probable_gams_source = repository_gams_primitives.is_probable_gams_source
module_symbol_name = repository_gams_primitives.module_symbol_name
normalize_identifier = repository_gams_primitives.normalize_identifier
normalize_import_target = repository_gams_primitives.normalize_import_target
strip_comments = repository_gams_primitives.strip_comments


def _symbol_from_entry(entry: dict[str, Any]) -> _Symbol:
    return _Symbol(
        symbol_id=str(entry["symbol_id"]),
        symbol_name=str(entry["symbol_name"]),
        symbol_kind=str(entry["symbol_kind"]),
        start_line=int(entry["start_line"]),
        end_line=int(entry["end_line"]),
        parent_symbol_id=(
            str(entry["parent_symbol_id"])
            if entry["parent_symbol_id"] is not None
            else None
        ),
        signature=str(entry["signature"]) if entry["signature"] is not None else None,
    )


def _lookup_target_file(module_index: dict[str, str], target_name: str) -> str | None:
    normalized_target = normalize_identifier(target_name)
    if not normalized_target:
        return None
    candidate_names = [normalized_target, normalized_target.lower()]
    for separator in (".", "/"):
        if separator not in normalized_target:
            continue
        leaf_name = normalized_target.rsplit(separator, 1)[-1]
        candidate_names.extend((leaf_name, leaf_name.lower()))
    for candidate_name in candidate_names:
        resolved_path = module_index.get(candidate_name)
        if resolved_path is not None:
            return resolved_path
    return None


def _source_symbol_id_for_line(
    *,
    line_number: int,
    source_symbol_ids_by_line: dict[int, str],
) -> str | None:
    return source_symbol_ids_by_line.get(line_number)


def _build_source_symbol_ids_by_line(
    symbol_entries: tuple[dict[str, Any], ...],
) -> dict[int, str]:
    source_symbol_ids_by_line: dict[int, str] = {}
    ranked_entries = sorted(
        symbol_entries,
        key=lambda entry: (
            int(entry["end_line"]) - int(entry["start_line"]),
            int(entry["start_line"]),
            str(entry["symbol_id"]),
        ),
    )
    for symbol_entry in ranked_entries:
        symbol_id = str(symbol_entry["symbol_id"])
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        for line_number in range(start_line, end_line + 1):
            source_symbol_ids_by_line.setdefault(line_number, symbol_id)
    return source_symbol_ids_by_line


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _SOURCE_SUFFIXES:
        return set()
    without_suffix_path = str(path.with_suffix(""))
    aliases = {
        file_path,
        file_path.lower(),
        path.stem,
        path.stem.lower(),
        without_suffix_path,
        without_suffix_path.lower(),
        without_suffix_path.replace("/", "."),
        without_suffix_path.replace("/", ".").lower(),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    if not is_probable_gams_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    module_name = module_symbol_name(file_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.lower())
    for symbol_entry in collect_symbol_entries(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        symbol_name = str(symbol_entry["symbol_name"])
        aliases.add(symbol_name)
        aliases.add(symbol_name.lower())
        aliases.update(
            str(alias)
            for alias in symbol_entry["qualified_names"]
            if str(alias).strip()
        )
        aliases.update(
            str(alias).lower()
            for alias in symbol_entry["qualified_names"]
            if str(alias).strip()
        )
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    *,
    file_path: str,
    module_index: dict[str, str],
    resolve_suffix_match,
) -> str | None:
    normalized_target = normalize_import_target(import_target)
    if not normalized_target:
        return None
    direct_match = _lookup_target_file(module_index, normalized_target)
    if direct_match is not None:
        return direct_match
    suffix_candidates = [normalized_target]
    if PurePosixPath(normalized_target).suffix.lower() not in {".gms", ".inc"}:
        suffix_candidates = [
            f"{normalized_target}.inc",
            f"{normalized_target}.gms",
            normalized_target,
        ]
    source_dir = PurePosixPath(file_path).parent
    path_candidates: list[str] = []
    for candidate_suffix in suffix_candidates:
        relative_candidate = normalize_import_target(str(source_dir / candidate_suffix))
        if relative_candidate:
            path_candidates.append(relative_candidate)
        path_candidates.append(candidate_suffix)
    return resolve_suffix_match(module_index=module_index, suffixes=path_candidates)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match,
) -> tuple[_Dependency, ...]:
    path = Path(file_path)
    if not is_probable_gams_source(path=path, text=text):
        return ()
    stripped_text = strip_comments(text)
    dependencies: list[_Dependency] = []
    seen_keys: set[tuple[str | None, str]] = set()
    for line_number, import_target in enumerate(
        import_targets_for_text(stripped_text),
        start=1,
    ):
        target_file = resolve_import(
            import_target,
            file_path=file_path,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, "imports")
        if dependency_key in seen_keys:
            continue
        seen_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "line": line_number,
                        "target_file": target_file,
                        "type": "imports",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=None,
                dependency_type="imports",
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    if not is_probable_gams_source(path=Path(file_path), text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    symbol_entries = tuple(
        collect_symbol_entries(
            file_path=file_path,
            text=text,
            stable_identifier=stable_identifier,
        )
    )
    source_symbol_ids_by_line = _build_source_symbol_ids_by_line(symbol_entries)
    dependencies = parse_dependencies_only(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    symbols = tuple(_symbol_from_entry(entry) for entry in symbol_entries)
    reference_candidates: dict[
        tuple[str, str | None, tuple[str, ...]],
        _SymbolReferenceCandidate,
    ] = {}
    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_name = str(symbol_entry["symbol_name"]).lower()
        snippet = "\n".join(stripped_text.splitlines()[start_line - 1 : end_line])
        for match in _IDENTIFIER_RE.finditer(snippet):
            target_name = normalize_identifier(str(match.group("name") or ""))
            if (
                not target_name
                or target_name.lower() in _BUILTIN_NAMES
                or target_name.lower() == symbol_name
            ):
                continue
            target_file = _lookup_target_file(module_index, target_name)
            if target_file is None or target_file == file_path:
                continue
            line_number = start_line + snippet.count("\n", 0, match.start())
            source_symbol_id = _source_symbol_id_for_line(
                line_number=line_number,
                source_symbol_ids_by_line=source_symbol_ids_by_line,
            )
            if source_symbol_id is None:
                continue
            reference_key = (source_symbol_id, target_file, (target_name,))
            reference_candidates.setdefault(
                reference_key,
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "source_symbol_id": source_symbol_id,
                            "target_file": target_file,
                            "target_names": (target_name,),
                            "line": line_number,
                        },
                    ),
                    source_symbol_id=source_symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
    return (
        symbols,
        dependencies,
        tuple(sorted(reference_candidates.values(), key=lambda item: item.reference_edge_id)),
    )
