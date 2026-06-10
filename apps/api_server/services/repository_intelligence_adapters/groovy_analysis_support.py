from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    groovy_primitives as repository_groovy_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    jvm as repository_jvm,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

CollectTypeSymbolEntries = Callable[..., list[dict[str, Any]]]
StableIdentifier = Callable[[str, Any], str]
ResolveImport = Callable[[str, dict[str, str]], str | None]

GROOVY_SUFFIXES = repository_groovy_primitives.GROOVY_SUFFIXES
GROOVY_CONFIG_BASENAMES = repository_groovy_primitives.GROOVY_CONFIG_BASENAMES
PACKAGE_RE = repository_groovy_primitives.PACKAGE_RE
IMPORT_RE = repository_groovy_primitives.IMPORT_RE
TYPE_DECL_RE = repository_groovy_primitives.TYPE_DECL_RE
TYPE_REFERENCE_RE = repository_groovy_primitives.TYPE_REFERENCE_RE
has_groovy_path_hints = repository_groovy_primitives.has_groovy_path_hints
is_probable_groovy_source = repository_groovy_primitives.is_probable_groovy_source
module_aliases_for_path = repository_groovy_primitives.module_aliases_for_path
resolve_import = repository_groovy_primitives.resolve_import


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    language: str | None = None,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding], str]:
    del language
    return repository_jvm.extract_import_bindings(
        file_path,
        text,
        module_index,
        language="groovy",
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    collect_type_symbol_entries: CollectTypeSymbolEntries,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[_Dependency, ...]:
    if not is_probable_groovy_source(path=file_path, text=text):
        return ()
    return repository_jvm.parse_dependencies_only(
        file_path,
        text,
        module_index,
        language="groovy",
        collect_type_symbol_entries=collect_type_symbol_entries,
        stable_identifier=stable_identifier,
        extract_import_bindings=lambda candidate_file_path, candidate_text, candidate_module_index, *, language=None: extract_import_bindings(  # noqa: E501
            candidate_file_path,
            candidate_text,
            candidate_module_index,
            language=language,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
        ),
        resolve_import=resolve_import,
    )


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    collect_type_symbol_entries: CollectTypeSymbolEntries,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    if not is_probable_groovy_source(path=file_path, text=text):
        return (), (), ()
    return repository_jvm.parse_file(
        file_path,
        text,
        module_index,
        language="groovy",
        collect_type_symbol_entries=collect_type_symbol_entries,
        stable_identifier=stable_identifier,
        extract_import_bindings=lambda candidate_file_path, candidate_text, candidate_module_index, *, language=None: extract_import_bindings(  # noqa: E501
            candidate_file_path,
            candidate_text,
            candidate_module_index,
            language=language,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
        ),
        resolve_import=resolve_import,
    )
