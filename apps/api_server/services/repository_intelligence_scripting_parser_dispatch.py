from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    crystal as crystal_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    elixir as elixir_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    php as php_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ruby as ruby_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _module_index_aliases_for_file,
    _module_index_values,
    _normalize_repository_relative_path,
    _resolve_suffix_match,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier


def _parse_ruby_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return ruby_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
        module_index_aliases_for_file=_module_index_aliases_for_file,
        root_path=Path("."),
    )


def _extract_ruby_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    return ruby_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
        module_index_aliases_for_file=_module_index_aliases_for_file,
        root_path=Path("."),
    )


def _resolve_ruby_reference_target(
    *,
    reference_name: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
    module_index: dict[str, str],
) -> tuple[str | None, tuple[str, ...]]:
    return ruby_adapter.resolve_reference_target(
        reference_name=reference_name,
        import_bindings=import_bindings,
        module_index=module_index,
    )


def _iter_ruby_reference_targets(
    *,
    file_path: str,
    symbol_name: str,
    snippet: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
    module_index: dict[str, str],
) -> tuple[tuple[str | None, tuple[str, ...]], ...]:
    return ruby_adapter.iter_reference_targets(
        file_path=file_path,
        symbol_name=symbol_name,
        snippet=snippet,
        import_bindings=import_bindings,
        module_index=module_index,
    )


def _parse_ruby_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return ruby_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
        module_index_aliases_for_file=_module_index_aliases_for_file,
        root_path=Path("."),
    )


def _extract_crystal_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    return crystal_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
        module_index_values=_module_index_values,
        module_index_aliases_for_file=_module_index_aliases_for_file,
    )


def _resolve_crystal_reference_target(
    *,
    reference_name: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
    module_index: dict[str, str],
) -> tuple[str | None, tuple[str, ...]]:
    return crystal_adapter.resolve_reference_target(
        reference_name=reference_name,
        import_bindings=import_bindings,
        module_index=module_index,
    )


def _iter_crystal_reference_targets(
    *,
    file_path: str,
    symbol_name: str,
    snippet: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
    module_index: dict[str, str],
) -> tuple[tuple[str | None, tuple[str, ...]], ...]:
    return crystal_adapter.iter_reference_targets(
        file_path=file_path,
        symbol_name=symbol_name,
        snippet=snippet,
        import_bindings=import_bindings,
        module_index=module_index,
    )


def _parse_crystal_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return crystal_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
        module_index_values=_module_index_values,
        module_index_aliases_for_file=_module_index_aliases_for_file,
    )


def _parse_crystal_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return crystal_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
        module_index_values=_module_index_values,
        module_index_aliases_for_file=_module_index_aliases_for_file,
    )


def _extract_php_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding], str]:
    return php_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_php_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return php_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_php_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return php_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _extract_elixir_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    return elixir_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_elixir_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return elixir_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_elixir_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return elixir_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )
