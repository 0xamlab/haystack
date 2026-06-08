from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    openscad_primitives as repository_openscad_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_openscad_primitives.StableIdentifier
ResolveSuffixMatch = repository_openscad_primitives.ResolveSuffixMatch

_CALL_RE = repository_openscad_primitives._CALL_RE
_IMPORT_RE = repository_openscad_primitives._IMPORT_RE
_RESERVED_NAMES = repository_openscad_primitives._RESERVED_NAMES
_CollectedSymbol = repository_openscad_primitives._CollectedSymbol

_normalize_identifier = repository_openscad_primitives._normalize_identifier
_normalize_import_target = repository_openscad_primitives._normalize_import_target
_line_number = repository_openscad_primitives._line_number
collect_symbol_entries = repository_openscad_primitives.collect_symbol_entries
has_openscad_path_hints = repository_openscad_primitives.has_openscad_path_hints
import_targets_for_text = repository_openscad_primitives.import_targets_for_text
is_probable_openscad_source = repository_openscad_primitives.is_probable_openscad_source
module_symbol_name = repository_openscad_primitives.module_symbol_name
strip_comments = repository_openscad_primitives.strip_comments


def _lookup_target_file(module_index: dict[str, str], target_name: str) -> str | None:
    normalized_name = _normalize_identifier(target_name)
    if not normalized_name:
        return None
    for candidate in (normalized_name, normalized_name.lower()):
        resolved = module_index.get(candidate)
        if resolved is not None:
            return resolved
    return None


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in repository_openscad_primitives._KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        file_path.lower(),
        path.stem,
        path.stem.lower(),
        str(path.with_suffix("")),
        str(path.with_suffix("")).lower(),
        str(path.with_suffix("")).replace("/", "."),
        str(path.with_suffix("")).replace("/", ".").lower(),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    if not is_probable_openscad_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    for entry in collect_symbol_entries(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(entry.symbol.symbol_name)
        aliases.add(entry.symbol.symbol_name.lower())
        aliases.update(entry.qualified_names)
        aliases.update(alias.lower() for alias in entry.qualified_names)
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    *,
    file_path: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_import_target(import_target)
    if not normalized_target:
        return None
    current_dir = PurePosixPath(file_path).parent
    candidate_paths: list[str] = []
    for raw_candidate in (normalized_target, str(current_dir / normalized_target)):
        normalized_candidate = _normalize_import_target(raw_candidate)
        if normalized_candidate and normalized_candidate not in candidate_paths:
            candidate_paths.append(normalized_candidate)
    for candidate_path in candidate_paths:
        resolved = module_index.get(candidate_path)
        if resolved is not None and resolved != file_path:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_paths)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    if not is_probable_openscad_source(path=Path(file_path), text=text):
        return ()
    stripped_text = strip_comments(text)
    dependencies: list[_Dependency] = []
    seen_targets: set[tuple[str | None, str]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        raw_target = (
            match.group("angled") or match.group("quoted") or match.group("single") or ""
        )
        import_target = _normalize_import_target(raw_target)
        if not import_target:
            continue
        target_file = resolve_import(
            import_target,
            file_path=file_path,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        key = (target_file, "imports")
        if key in seen_targets:
            continue
        seen_targets.add(key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "line": _line_number(stripped_text, match.start()),
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
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    if not is_probable_openscad_source(path=Path(file_path), text=text):
        return (), (), ()
    collected_symbols = collect_symbol_entries(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    dependencies = parse_dependencies_only(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    stripped_text = strip_comments(text)
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    reference_candidates: dict[
        tuple[str, str | None, tuple[str, ...]],
        _SymbolReferenceCandidate,
    ] = {}
    for collected_symbol in collected_symbols:
        symbol_name = collected_symbol.symbol.symbol_name.lower()
        snippet = "\n".join(
            stripped_text.splitlines()[
                collected_symbol.local_start_line - 1 : collected_symbol.local_end_line
            ]
        )
        for match in _CALL_RE.finditer(snippet):
            target_name = _normalize_identifier(match.group("name") or "")
            if (
                not target_name
                or target_name.lower() in _RESERVED_NAMES
                or target_name.lower() == symbol_name
            ):
                continue
            target_file = _lookup_target_file(module_index, target_name)
            key = (
                collected_symbol.symbol.symbol_id,
                target_file,
                (target_name,),
            )
            reference_candidates[key] = _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": collected_symbol.symbol.symbol_id,
                        "source_file": file_path,
                        "target_file": target_file,
                        "target_names": (target_name,),
                        "reference_type": "references_symbol",
                    },
                ),
                source_symbol_id=collected_symbol.symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=(target_name,),
                reference_type="references_symbol",
            )
    return symbols, dependencies, tuple(reference_candidates.values())
