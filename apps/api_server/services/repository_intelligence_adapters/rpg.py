from __future__ import annotations

from collections import defaultdict

from apps.api_server.services.repository_intelligence_adapters import (
    rpg_support as repository_rpg_support,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_rpg_support.StableIdentifier
ResolveSuffixMatch = repository_rpg_support.ResolveSuffixMatch

_KNOWN_RPG_SUFFIXES = repository_rpg_support._KNOWN_RPG_SUFFIXES
_RPG_INCLUDE_SUFFIXES = repository_rpg_support._RPG_INCLUDE_SUFFIXES
_RPG_SOURCE_ROOTS = repository_rpg_support._RPG_SOURCE_ROOTS
_RESERVED_SYMBOL_NAMES = repository_rpg_support._RESERVED_SYMBOL_NAMES
strip_comments = repository_rpg_support.strip_comments
normalize_target = repository_rpg_support.normalize_target
normalize_symbol_name = repository_rpg_support.normalize_symbol_name
collect_symbol_entries = repository_rpg_support.collect_symbol_entries
resolve_import = repository_rpg_support.resolve_import
module_aliases_for_path = repository_rpg_support.module_aliases_for_path
extract_import_bindings = repository_rpg_support.extract_import_bindings
is_probable_rpg_source = repository_rpg_support.is_probable_rpg_source


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies, _import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    return dependencies


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
    raw_symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    symbol_entries = tuple(
        _Symbol(
            symbol_id=str(entry["symbol_id"]),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=None,
            signature=(
                str(entry["signature"]) if entry.get("signature") is not None else None
            ),
        )
        for entry in raw_symbol_entries
    )
    dependency_specs, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    stripped_lines = strip_comments(text).splitlines()
    symbol_lookup: dict[str, list[_Symbol]] = defaultdict(list)
    for symbol_entry in symbol_entries:
        symbol_lookup[symbol_entry.symbol_name.lower()].append(symbol_entry)

    symbol_candidates = list(symbol_entries)
    if any(symbol.symbol_kind != "program" for symbol in symbol_candidates):
        symbol_candidates = [
            symbol for symbol in symbol_candidates if symbol.symbol_kind != "program"
        ]

    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol_entry in symbol_candidates:
        start_line = int(symbol_entry.start_line)
        end_line = int(symbol_entry.end_line)
        snippet = "\n".join(
            stripped_lines[max(start_line - 1, 0) : min(end_line, len(stripped_lines))]
        )

        for target_name in repository_rpg_support._exsr_targets(snippet):
            if (
                repository_rpg_support._canonical_symbol_name(target_name)
                == symbol_entry.symbol_name.lower()
            ):
                continue
            local_matches = symbol_lookup.get(target_name.lower(), ())
            if not local_matches:
                continue
            resolved_target_names = repository_rpg_support._ordered_names(
                *(match.symbol_name for match in local_matches)
            )
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_entry.symbol_id,
                    "target_file": file_path,
                    "target_names": resolved_target_names,
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                _SymbolReferenceCandidate(
                    reference_edge_id=edge_id,
                    source_symbol_id=symbol_entry.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=file_path,
                    target_names=resolved_target_names,
                    reference_type="references_symbol",
                ),
            )

        for target_name in repository_rpg_support._call_targets(snippet):
            if (
                repository_rpg_support._canonical_symbol_name(target_name)
                == symbol_entry.symbol_name.lower()
            ):
                continue
            binding = import_bindings.get(target_name.lower())
            target_file: str | None = None
            resolved_target_names: tuple[str, ...] = ()
            if binding is not None:
                target_file = (
                    str(binding["target_file"])
                    if binding.get("target_file") is not None
                    else None
                )
                resolved_target_names = tuple(
                    str(name) for name in binding.get("target_names", ()) if str(name)
                )
            if not target_file:
                local_matches = symbol_lookup.get(target_name.lower(), ())
                if local_matches:
                    target_file = file_path
                    resolved_target_names = repository_rpg_support._ordered_names(
                        *(match.symbol_name for match in local_matches)
                    )
            if not target_file:
                target_file = repository_rpg_support._reference_target_from_module_index(
                    target_name,
                    file_path=file_path,
                    module_index=module_index,
                    resolve_suffix_match=resolve_suffix_match,
                )
                resolved_target_names = repository_rpg_support._ordered_names(target_name)
            if target_file is None or not resolved_target_names:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_entry.symbol_id,
                    "target_file": target_file,
                    "target_names": resolved_target_names,
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                _SymbolReferenceCandidate(
                    reference_edge_id=edge_id,
                    source_symbol_id=symbol_entry.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=resolved_target_names,
                    reference_type="references_symbol",
                ),
            )

    return (
        symbol_entries,
        dependency_specs,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
