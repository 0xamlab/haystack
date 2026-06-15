from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import metal as metal_adapter
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _normalize_repository_relative_path,
    _resolve_suffix_match,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier


def _parse_metal_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return metal_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_include=lambda **kwargs: metal_adapter.resolve_include(
            normalize_repository_relative_path=_normalize_repository_relative_path,
            resolve_suffix_match=_resolve_suffix_match,
            **kwargs,
        ),
    )


def _parse_metal_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return metal_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_include=lambda **kwargs: metal_adapter.resolve_include(
            normalize_repository_relative_path=_normalize_repository_relative_path,
            resolve_suffix_match=_resolve_suffix_match,
            **kwargs,
        ),
    )
