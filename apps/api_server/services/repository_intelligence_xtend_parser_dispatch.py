from __future__ import annotations

from apps.api_server.services import (
    repository_intelligence_language_resolution as repository_language_resolution,
)
from apps.api_server.services import (
    repository_intelligence_module_aliases as repository_module_aliases,
)
from apps.api_server.services.repository_intelligence_adapters import (
    xtend as xtend_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_collect_type_symbol_entries = repository_module_aliases._collect_type_symbol_entries
_resolve_xtend_import = repository_language_resolution._resolve_jvm_import


def _parse_xtend_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return xtend_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        collect_type_symbol_entries=_collect_type_symbol_entries,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_xtend_import,
    )


def _parse_xtend_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return xtend_adapter.parse_file(
        file_path,
        text,
        module_index,
        collect_type_symbol_entries=_collect_type_symbol_entries,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_xtend_import,
    )
