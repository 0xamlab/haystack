from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    c_family as c_family_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    metal_primitives as repository_metal_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_metal_primitives.StableIdentifier
ResolveInclude = c_family_adapter.ResolveInclude

METAL_SUFFIXES = repository_metal_primitives.METAL_SUFFIXES
candidate_module_keys = repository_metal_primitives.candidate_module_keys
has_metal_path_hints = repository_metal_primitives.has_metal_path_hints
is_probable_metal_source = repository_metal_primitives.is_probable_metal_source
module_aliases_for_path = repository_metal_primitives.module_aliases_for_path
module_name_from_path = repository_metal_primitives.module_name_from_path
normalize_symbol_name = repository_metal_primitives.normalize_symbol_name
resolve_include = repository_metal_primitives.resolve_include
strip_comments = repository_metal_primitives.strip_comments


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_include: ResolveInclude,
) -> tuple[_Dependency, ...]:
    if not is_probable_metal_source(path=Path(file_path), text=text):
        return ()
    return c_family_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_include=resolve_include,
    )


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_include: ResolveInclude,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    if not is_probable_metal_source(path=Path(file_path), text=text):
        return (), (), ()
    return c_family_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_include=resolve_include,
    )
