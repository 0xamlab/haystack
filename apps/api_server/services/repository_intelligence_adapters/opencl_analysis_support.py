from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    c_family as c_family_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    opencl_primitives as repository_opencl_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_opencl_primitives.StableIdentifier
ResolveInclude = c_family_adapter.ResolveInclude

OPENCL_SUFFIXES = repository_opencl_primitives.OPENCL_SUFFIXES
candidate_module_keys = repository_opencl_primitives.candidate_module_keys
has_opencl_path_hints = repository_opencl_primitives.has_opencl_path_hints
is_probable_opencl_source = repository_opencl_primitives.is_probable_opencl_source
module_aliases_for_path = repository_opencl_primitives.module_aliases_for_path
module_name_from_path = repository_opencl_primitives.module_name_from_path
normalize_symbol_name = repository_opencl_primitives.normalize_symbol_name
resolve_include = repository_opencl_primitives.resolve_include
strip_comments = repository_opencl_primitives.strip_comments


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_include: ResolveInclude,
    stripped_text: str | None = None,
) -> tuple[_Dependency, ...]:
    if not is_probable_opencl_source(
        path=Path(file_path),
        text=text,
        stripped_text=stripped_text,
    ):
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
    stripped_text: str | None = None,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    if not is_probable_opencl_source(
        path=Path(file_path),
        text=text,
        stripped_text=stripped_text,
    ):
        return (), (), ()
    return c_family_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_include=resolve_include,
    )
