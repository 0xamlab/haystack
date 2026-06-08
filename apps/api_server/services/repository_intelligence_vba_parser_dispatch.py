from __future__ import annotations

from apps.api_server.services import (
    repository_intelligence_native_resolution as repository_native_resolution,
)
from apps.api_server.services.repository_intelligence_adapters import vba as vba_adapter
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_symbols_from_entries = repository_native_resolution._symbols_from_entries
_dependencies_from_specs = repository_native_resolution._dependencies_from_specs
_references_from_specs = repository_native_resolution._references_from_specs
_resolve_classic_visual_basic_target = (
    repository_native_resolution._resolve_classic_visual_basic_target
)


def _parse_vba_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        vba_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_target_fn=lambda reference_target: _resolve_classic_visual_basic_target(
                reference_target,
                module_index,
            ),
        )
    )


def _parse_vba_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = vba_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_target_fn=lambda reference_target: _resolve_classic_visual_basic_target(
            reference_target,
            module_index,
        ),
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )
