from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    c_family as c_family_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    cuda_primitives as repository_cuda_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_cuda_primitives.StableIdentifier
ResolveInclude = c_family_adapter.ResolveInclude

CUDA_SUFFIXES = repository_cuda_primitives.CUDA_SUFFIXES
candidate_module_keys = repository_cuda_primitives.candidate_module_keys
has_cuda_path_hints = repository_cuda_primitives.has_cuda_path_hints
is_probable_cuda_source = repository_cuda_primitives.is_probable_cuda_source
module_aliases_for_path = repository_cuda_primitives.module_aliases_for_path
module_name_from_path = repository_cuda_primitives.module_name_from_path
normalize_symbol_name = repository_cuda_primitives.normalize_symbol_name
resolve_include = repository_cuda_primitives.resolve_include
strip_comments = repository_cuda_primitives.strip_comments


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_include: ResolveInclude,
) -> tuple[_Dependency, ...]:
    if not is_probable_cuda_source(path=Path(file_path), text=text):
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
    if not is_probable_cuda_source(path=Path(file_path), text=text):
        return (), (), ()
    return c_family_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_include=resolve_include,
    )
