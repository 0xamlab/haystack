from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    webassembly as webassembly_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier


def _parse_webassembly_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return webassembly_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
    )


def _parse_webassembly_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return webassembly_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
    )
