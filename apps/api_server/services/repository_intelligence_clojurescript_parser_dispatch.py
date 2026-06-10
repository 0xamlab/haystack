from __future__ import annotations

from apps.api_server.services import repository_intelligence_language_resolution as rlr
from apps.api_server.services.repository_intelligence_adapters import (
    clojurescript as clojurescript_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_resolve_clojure_import = rlr._resolve_clojure_import


def _parse_clojurescript_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return clojurescript_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_clojure_import,
    )


def _parse_clojurescript_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return clojurescript_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_clojure_import,
    )
