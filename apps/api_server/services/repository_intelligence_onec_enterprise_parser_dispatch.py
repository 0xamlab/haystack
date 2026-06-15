from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    onec_enterprise as onec_enterprise_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_indexing import _resolve_suffix_match
from apps.api_server.services.repository_intelligence_shared import _stable_identifier


def _parse_onec_enterprise_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return onec_enterprise_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_onec_enterprise_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return onec_enterprise_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )

