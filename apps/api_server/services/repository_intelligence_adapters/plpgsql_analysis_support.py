from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    plpgsql_primitives as repository_plpgsql_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    plsql as repository_plsql,
)

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

PLPGSQL_SUFFIXES = repository_plpgsql_primitives.PLPGSQL_SUFFIXES
has_plpgsql_path_hints = repository_plpgsql_primitives.has_plpgsql_path_hints
is_probable_plpgsql_source = repository_plpgsql_primitives.is_probable_plpgsql_source
module_aliases_for_path = repository_plpgsql_primitives.module_aliases_for_path
normalize_identifier = repository_plpgsql_primitives.normalize_identifier
resolve_import = repository_plpgsql_primitives.resolve_import
resolve_target = repository_plpgsql_primitives.resolve_target
strip_comments = repository_plpgsql_primitives.strip_comments
symbol_name_parts = repository_plpgsql_primitives.symbol_name_parts


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[dict[str, Any], ...]:
    if not is_probable_plpgsql_source(path=file_path, text=text):
        return ()
    return repository_plsql.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=lambda import_target, candidate_module_index: resolve_import(
            import_target,
            module_index=candidate_module_index,
            resolve_suffix_match=resolve_suffix_match,
        ),
        resolve_target=lambda target_name, candidate_module_index: resolve_target(
            target_name,
            module_index=candidate_module_index,
            resolve_suffix_match=resolve_suffix_match,
        ),
    )


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    list[dict[str, Any]],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    if not is_probable_plpgsql_source(path=file_path, text=text):
        return [], (), ()
    return repository_plsql.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=lambda import_target, candidate_module_index: resolve_import(
            import_target,
            module_index=candidate_module_index,
            resolve_suffix_match=resolve_suffix_match,
        ),
        resolve_target=lambda target_name, candidate_module_index: resolve_target(
            target_name,
            module_index=candidate_module_index,
            resolve_suffix_match=resolve_suffix_match,
        ),
    )
