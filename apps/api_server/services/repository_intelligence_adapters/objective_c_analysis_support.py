from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    objective_c_primitives as repository_objective_c_primitives,
)

StableIdentifier = repository_objective_c_primitives.StableIdentifier
ResolveSuffixMatch = repository_objective_c_primitives.ResolveSuffixMatch

_KNOWN_OBJECTIVE_C_SUFFIXES = repository_objective_c_primitives._KNOWN_OBJECTIVE_C_SUFFIXES
_RESERVED_REFERENCE_NAMES = repository_objective_c_primitives._RESERVED_REFERENCE_NAMES

collect_symbol_entries = repository_objective_c_primitives.collect_symbol_entries
iter_import_targets = repository_objective_c_primitives.iter_import_targets
iter_message_sends = repository_objective_c_primitives.iter_message_sends
iter_type_reference_tokens = repository_objective_c_primitives.iter_type_reference_tokens
normalize_identifier = repository_objective_c_primitives.normalize_identifier
_candidate_import_suffixes = repository_objective_c_primitives._candidate_import_suffixes
_is_macro_like_name = repository_objective_c_primitives._is_macro_like_name
_normalize_import_target = repository_objective_c_primitives._normalize_import_target
_normalize_repository_relative_path = (
    repository_objective_c_primitives._normalize_repository_relative_path
)
sanitize_text = repository_objective_c_primitives.sanitize_text


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_OBJECTIVE_C_SUFFIXES:
        return set()
    aliases = {
        file_path.lower(),
        path.stem.lower(),
    }
    without_suffix_path = str(path.with_suffix("")).lower()
    aliases.add(without_suffix_path)
    aliases.add(without_suffix_path.replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(str(alias).lower() for alias in symbol_entry["qualified_names"] if alias)
    return {alias for alias in aliases if alias}


def resolve_import(
    current_file: str,
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_import_target(import_target)
    if not normalized_target or normalized_target.startswith("/"):
        return None
    candidate_suffixes: list[str] = []
    current_dir = _normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    if current_dir:
        relative_target = _normalize_repository_relative_path(
            str(PurePosixPath(current_dir) / normalized_target)
        )
        candidate_suffixes.extend(_candidate_import_suffixes(relative_target))
    candidate_suffixes.extend(_candidate_import_suffixes(normalized_target))
    target_name = PurePosixPath(normalized_target).name
    if target_name:
        candidate_suffixes.extend(_candidate_import_suffixes(target_name))
    seen_suffixes: set[str] = set()
    ordered_suffixes: list[str] = []
    for candidate_suffix in candidate_suffixes:
        normalized_candidate = _normalize_repository_relative_path(candidate_suffix)
        if not normalized_candidate or normalized_candidate in seen_suffixes:
            continue
        seen_suffixes.add(normalized_candidate)
        ordered_suffixes.append(normalized_candidate.lower())
    for candidate_suffix in ordered_suffixes:
        resolved = module_index.get(candidate_suffix)
        if resolved is not None and resolved != current_file:
            return resolved
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=ordered_suffixes,
    )
    if resolved is not None and resolved != current_file:
        return resolved
    return None


def resolve_target(
    current_file: str,
    reference_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(reference_target)
    if (
        not normalized_target
        or normalized_target in _RESERVED_REFERENCE_NAMES
        or _is_macro_like_name(reference_target)
    ):
        return None
    namespace_path = normalized_target.replace(".", "/")
    leaf_name = normalized_target.rsplit(".", 1)[-1]
    preferred_suffixes = [
        suffix
        for candidate in (normalized_target, namespace_path, leaf_name)
        if candidate
        for suffix in (
            f"{candidate}.h",
            f"{candidate}.pch",
            f"{candidate}.mm",
            f"{candidate}.m",
        )
    ]
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=preferred_suffixes,
    )
    if resolved is not None and resolved != current_file:
        return resolved
    for candidate in (normalized_target, namespace_path, leaf_name):
        if not candidate:
            continue
        direct_match = module_index.get(candidate)
        if direct_match is not None and direct_match != current_file:
            return direct_match
    return None


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Any,
    resolve_target: Any,
) -> tuple[dict[str, Any], ...]:
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()

    for line_no, import_target in iter_import_targets(text):
        target_file = resolve_import(file_path, import_target, module_index)
        target_symbol = normalize_identifier(PurePosixPath(import_target).stem)
        dependency_key = (target_file, target_symbol, "imports")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "line": line_no,
                        "kind": "import",
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": target_symbol or PurePosixPath(import_target).name.lower(),
                "dependency_type": "imports",
            }
        )

    for line_no, receiver, selector_name in iter_message_sends(text):
        target_file = resolve_target(file_path, receiver, module_index)
        dependency_key = (target_file, selector_name, "references")
        if (
            target_file is None
            or target_file == file_path
            or dependency_key in dependency_keys
        ):
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": receiver,
                        "selector": selector_name,
                        "line": line_no,
                        "kind": "message_send",
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": selector_name,
                "dependency_type": "references",
            }
        )

    for line_no, raw_token in iter_type_reference_tokens(text):
        target_file = resolve_target(file_path, raw_token, module_index)
        dependency_key = (target_file, raw_token, "references")
        if (
            target_file is None
            or target_file == file_path
            or dependency_key in dependency_keys
        ):
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": raw_token,
                        "line": line_no,
                        "kind": "type_reference",
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": raw_token,
                "dependency_type": "references",
            }
        )

    return tuple(dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Any,
    resolve_target: Any,
) -> tuple[
    list[dict[str, Any]],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    reference_candidates: dict[str, dict[str, Any]] = {}
    sanitized_lines = sanitize_text(text).splitlines()

    def _record_reference(
        *,
        source_symbol_id: str,
        target_file: str | None,
        target_names: tuple[str, ...],
    ) -> None:
        normalized_names = tuple(
            normalize_identifier(target_name)
            for target_name in target_names
            if normalize_identifier(target_name)
        )
        if target_file is None or target_file == file_path or not normalized_names:
            return
        edge_id = stable_identifier(
            "ref",
            {
                "source_symbol_id": source_symbol_id,
                "target_file": target_file,
                "target_names": normalized_names,
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            {
                "reference_edge_id": edge_id,
                "source_symbol_id": source_symbol_id,
                "source_file": file_path,
                "target_symbol_id": None,
                "target_file": target_file,
                "target_names": normalized_names,
                "reference_type": "references_symbol",
            },
        )

    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_name = normalize_identifier(str(symbol_entry["symbol_name"]))
        symbol_id = str(symbol_entry["symbol_id"])
        snippet = "\n".join(sanitized_lines[start_line - 1 : end_line])

        for _line_no, receiver, selector_name in iter_message_sends(snippet):
            target_file = resolve_target(file_path, receiver, module_index)
            if selector_name == symbol_name:
                continue
            _record_reference(
                source_symbol_id=symbol_id,
                target_file=target_file,
                target_names=(selector_name,),
            )

        for _line_no, raw_token in iter_type_reference_tokens(snippet):
            normalized_token = normalize_identifier(raw_token)
            if normalized_token == symbol_name:
                continue
            target_file = resolve_target(file_path, raw_token, module_index)
            _record_reference(
                source_symbol_id=symbol_id,
                target_file=target_file,
                target_names=(normalized_token,),
            )

    return (
        symbol_entries,
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
            resolve_target=resolve_target,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
