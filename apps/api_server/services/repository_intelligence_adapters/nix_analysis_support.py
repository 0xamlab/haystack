from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    nix_primitives as repository_nix_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_nix_primitives.StableIdentifier

_KNOWN_SUFFIXES = repository_nix_primitives._KNOWN_SUFFIXES
_IDENTIFIER_RE = repository_nix_primitives._IDENTIFIER_RE
_QUALIFIED_REFERENCE_RE = repository_nix_primitives._QUALIFIED_REFERENCE_RE
_NIX_KEYWORDS = repository_nix_primitives._NIX_KEYWORDS

collect_symbol_entries = repository_nix_primitives.collect_symbol_entries
has_nix_path_hints = repository_nix_primitives.has_nix_path_hints
import_bindings_for_text = repository_nix_primitives.import_bindings_for_text
import_targets_for_text = repository_nix_primitives.import_targets_for_text
is_probable_nix_source = repository_nix_primitives.is_probable_nix_source
module_symbol_name = repository_nix_primitives.module_symbol_name
normalize_identifier = repository_nix_primitives.normalize_identifier
normalize_import_target = repository_nix_primitives.normalize_import_target
strip_comments = repository_nix_primitives.strip_comments


def _symbol_from_entry(entry: dict[str, Any]) -> _Symbol:
    return _Symbol(
        symbol_id=str(entry["symbol_id"]),
        symbol_name=str(entry["symbol_name"]),
        symbol_kind=str(entry["symbol_kind"]),
        start_line=int(entry["start_line"]),
        end_line=int(entry["end_line"]),
        parent_symbol_id=None,
        signature=str(entry["signature"]),
    )


def _source_symbol_id_for_line(
    *,
    line_number: int,
    symbol_entries: tuple[dict[str, Any], ...],
) -> str | None:
    matching_symbols = [
        entry
        for entry in symbol_entries
        if int(entry["start_line"]) <= line_number <= int(entry["end_line"])
    ]
    if not matching_symbols:
        return None
    ranked = sorted(
        matching_symbols,
        key=lambda entry: (
            int(entry["end_line"]) - int(entry["start_line"]),
            int(entry["start_line"]),
            str(entry["symbol_id"]),
        ),
    )
    return str(ranked[0]["symbol_id"])


def _lookup_target_file(module_index: dict[str, str], target_name: str) -> str | None:
    normalized_target = normalize_identifier(target_name)
    if not normalized_target:
        return None
    candidate_names = [
        normalized_target,
        normalized_target.lower(),
        normalized_target.rsplit(".", 1)[-1],
        normalized_target.rsplit(".", 1)[-1].lower(),
    ]
    for candidate_name in candidate_names:
        resolved = module_index.get(candidate_name)
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
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
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
    if not is_probable_nix_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    module_name = module_symbol_name(file_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.lower())
    for entry in collect_symbol_entries(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        symbol_name = str(entry["symbol_name"])
        aliases.add(symbol_name)
        aliases.add(symbol_name.lower())
        aliases.update(str(alias) for alias in entry["qualified_names"] if str(alias).strip())
        aliases.update(
            str(alias).lower() for alias in entry["qualified_names"] if str(alias).strip()
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
    if direct_match is not None and direct_match != file_path:
        return direct_match
    current_dir = PurePosixPath(file_path).parent
    suffix_candidates = [normalized_target]
    if PurePosixPath(normalized_target).suffix.lower() != ".nix":
        suffix_candidates = [
            normalized_target,
            f"{normalized_target}.nix",
            f"{normalized_target}/default.nix",
        ]
    path_candidates: list[str] = []
    for candidate in suffix_candidates:
        relative_candidate = normalize_import_target(str(current_dir / candidate))
        if relative_candidate:
            path_candidates.append(relative_candidate)
        path_candidates.append(candidate)
    for candidate in path_candidates:
        resolved = module_index.get(candidate)
        if resolved is not None and resolved != file_path:
            return resolved
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
    if not is_probable_nix_source(path=path, text=text):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str]] = set()
    for line_number, import_target in enumerate(import_targets_for_text(text), start=1):
        target_file = resolve_import(
            import_target,
            file_path=file_path,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, "imports")
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
    if not is_probable_nix_source(path=Path(file_path), text=text):
        return (), (), ()
    symbol_entries = tuple(
        collect_symbol_entries(
            file_path=file_path,
            text=text,
            stable_identifier=stable_identifier,
        )
    )
    dependencies = parse_dependencies_only(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    stripped_text = strip_comments(text)
    import_bindings: dict[str, tuple[str | None, tuple[str, ...]]] = {}
    for alias_name, import_target, target_names in import_bindings_for_text(text):
        target_file = resolve_import(
            import_target,
            file_path=file_path,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        if alias_name:
            import_bindings[alias_name] = (target_file, target_names)
    reference_candidates: dict[
        tuple[str, str | None, tuple[str, ...]],
        _SymbolReferenceCandidate,
    ] = {}
    for entry in symbol_entries:
        start_line = int(entry["start_line"])
        end_line = int(entry["end_line"])
        snippet = "\n".join(stripped_text.splitlines()[start_line - 1 : end_line])
        symbol_name = str(entry["symbol_name"]).lower()
        for match in _QUALIFIED_REFERENCE_RE.finditer(snippet):
            owner_name = normalize_identifier(str(match.group("owner") or ""))
            target_name = normalize_identifier(str(match.group("name") or ""))
            if not owner_name or not target_name:
                continue
            binding_target = import_bindings.get(owner_name)
            target_file = binding_target[0] if binding_target is not None else None
            if target_file is None:
                target_file = _lookup_target_file(module_index, owner_name)
            if target_file is None or target_file == file_path:
                continue
            line_number = start_line + snippet.count("\n", 0, match.start())
            source_symbol_id = _source_symbol_id_for_line(
                line_number=line_number,
                symbol_entries=symbol_entries,
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
                    target_file=target_file,
                    target_symbol_id=None,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
        for match in _IDENTIFIER_RE.finditer(snippet):
            target_name = normalize_identifier(str(match.group("name") or ""))
            if (
                not target_name
                or target_name.lower() in _NIX_KEYWORDS
                or target_name.lower() == symbol_name
            ):
                continue
            binding_target = import_bindings.get(target_name)
            if binding_target is None:
                continue
            target_file, target_names = binding_target
            if target_file is None or target_file == file_path:
                continue
            line_number = start_line + snippet.count("\n", 0, match.start())
            source_symbol_id = _source_symbol_id_for_line(
                line_number=line_number,
                symbol_entries=symbol_entries,
            )
            if source_symbol_id is None:
                continue
            resolved_target_names = target_names or (target_name,)
            reference_key = (source_symbol_id, target_file, resolved_target_names)
            reference_candidates.setdefault(
                reference_key,
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "source_symbol_id": source_symbol_id,
                            "target_file": target_file,
                            "target_names": resolved_target_names,
                            "line": line_number,
                        },
                    ),
                    source_symbol_id=source_symbol_id,
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol_id=None,
                    target_names=resolved_target_names,
                    reference_type="references_symbol",
                ),
            )
    return (
        tuple(_symbol_from_entry(entry) for entry in symbol_entries),
        dependencies,
        tuple(reference_candidates.values()),
    )
