from __future__ import annotations

from apps.api_server.services import (
    repository_intelligence_language_resolution as repository_language_resolution,
)
from apps.api_server.services import (
    repository_intelligence_module_aliases as repository_module_aliases,
)
from apps.api_server.services.repository_intelligence_adapters import (
    csharp as csharp_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import jvm as jvm_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    swift as swift_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_collect_type_symbol_entries = repository_module_aliases._collect_type_symbol_entries
_resolve_csharp_import_for_file = repository_language_resolution._resolve_csharp_import_for_file
_resolve_csharp_same_namespace_reference = (
    repository_language_resolution._resolve_csharp_same_namespace_reference
)
_resolve_jvm_import = repository_language_resolution._resolve_jvm_import
_resolve_swift_import = repository_language_resolution._resolve_swift_import
_resolve_swift_same_target_reference = (
    repository_language_resolution._resolve_swift_same_target_reference
)


def _parse_swift_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return swift_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_swift_import,
        resolve_same_target_reference=_resolve_swift_same_target_reference,
    )


def _parse_swift_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return swift_adapter.parse_file(
        file_path,
        text,
        module_index,
        collect_type_symbol_entries=_collect_type_symbol_entries,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_swift_import,
        resolve_same_target_reference=_resolve_swift_same_target_reference,
    )


def _extract_csharp_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Dependency, ...],
    dict[str, _ImportedSymbolBinding],
    str,
]:
    return csharp_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import_for_file=_resolve_csharp_import_for_file,
    )


def _parse_csharp_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return csharp_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        collect_type_symbol_entries=_collect_type_symbol_entries,
        stable_identifier=_stable_identifier,
        extract_import_bindings=_extract_csharp_import_bindings,
        resolve_same_namespace_reference=_resolve_csharp_same_namespace_reference,
    )


def _parse_csharp_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return csharp_adapter.parse_file(
        file_path,
        text,
        module_index,
        collect_type_symbol_entries=_collect_type_symbol_entries,
        stable_identifier=_stable_identifier,
        extract_import_bindings=_extract_csharp_import_bindings,
        resolve_same_namespace_reference=_resolve_csharp_same_namespace_reference,
    )


def _extract_jvm_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    language: str,
) -> tuple[
    tuple[_Dependency, ...],
    dict[str, _ImportedSymbolBinding],
    str,
]:
    return jvm_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        language=language,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_jvm_import,
    )


def _parse_jvm_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    language: str,
) -> tuple[_Dependency, ...]:
    return jvm_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        language=language,
        collect_type_symbol_entries=_collect_type_symbol_entries,
        stable_identifier=_stable_identifier,
        extract_import_bindings=_extract_jvm_import_bindings,
        resolve_import=_resolve_jvm_import,
    )


def _parse_jvm_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    language: str,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return jvm_adapter.parse_file(
        file_path,
        text,
        module_index,
        language=language,
        collect_type_symbol_entries=_collect_type_symbol_entries,
        stable_identifier=_stable_identifier,
        extract_import_bindings=_extract_jvm_import_bindings,
        resolve_import=_resolve_jvm_import,
    )
