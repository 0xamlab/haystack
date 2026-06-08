from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import cuda as cuda_adapter
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_language_resolution import (
    _resolve_c_family_include,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier


def _parse_cuda_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return cuda_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_include=_resolve_c_family_include,
    )


def _parse_cuda_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return cuda_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_include=_resolve_c_family_include,
    )
