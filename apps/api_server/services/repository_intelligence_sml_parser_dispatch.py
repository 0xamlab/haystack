from __future__ import annotations

from apps.api_server.services import (
    repository_intelligence_native_resolution as repository_native_resolution,
)
from apps.api_server.services.repository_intelligence_adapters import sml as sml_adapter
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_indexing import _resolve_suffix_match
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_dependencies_from_specs = repository_native_resolution._dependencies_from_specs
_references_from_specs = repository_native_resolution._references_from_specs
_symbols_from_entries = repository_native_resolution._symbols_from_entries


def _parse_sml_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        sml_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=lambda import_target, index: sml_adapter.resolve_import(
                import_target,
                module_index=index,
                resolve_suffix_match=_resolve_suffix_match,
            ),
        )
    )


def _parse_sml_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = sml_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=lambda import_target, index: sml_adapter.resolve_import(
            import_target,
            module_index=index,
            resolve_suffix_match=_resolve_suffix_match,
        ),
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )
