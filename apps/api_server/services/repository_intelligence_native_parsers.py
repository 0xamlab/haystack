"""Per-language native parser bodies for repository intelligence.

Extracted from repository_intelligence_native_dispatch so both modules stay within the
per-module line budget. The shared dispatch infrastructure (lazy adapters, native-
resolution helpers, clarity/virtualized helpers) is defined in that module and imported
back here; the parser registries in native_dispatch import these bodies in turn.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from apps.api_server.services import (
    repository_intelligence_native_dispatch as repository_native_dispatch,
)
from apps.api_server.services.repository_intelligence_native_dispatch import (  # noqa: E501
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
    _cached_classic_visual_basic_target_resolver,
    _clarity_dependencies,
    _clarity_references,
    _clarity_symbols,
    _module_index_aliases_for_file,
    _normalize_repository_relative_path,
    _resolve_directory_prefix_match,
    _resolve_suffix_match,
    _stable_identifier,
    _virtualized_language_file_path,
    _virtualized_suffix_module_index,
    abap_adapter,
    ada_adapter,
    assembly_adapter,
    classic_visual_basic_adapter,
    cobol_adapter,
    d_language_adapter,
    emacslisp_adapter,
    fortran_adapter,
    foxpro_adapter,
    fsharp_adapter,
    lisp_adapter,
    matlab_adapter,
    ml_adapter,
    objective_c_adapter,
    plsql_adapter,
    prolog_adapter,
    racket_adapter,
    sas_adapter,
    scheme_adapter,
    sql_adapter,
    tsql_adapter,
    visual_basic_adapter,
)

# The native-resolution helpers (_resolve_*, _dependencies_from_specs, etc.) must be
# referenced by the parser bodies below WITHOUT pulling in
# repository_intelligence_native_resolution at import time — importing native_dispatch
# (which imports this module) has to leave native_resolution unloaded until a parse
# function actually runs (the lazy-load test guards that). A module-level ``__getattr__``
# does not help here, because bare-name global lookups inside functions never trigger it;
# so bind each helper to a thin lazy call wrapper that resolves the real function off
# native_dispatch on first invocation. These are only ever *called* (or passed straight to
# a callee that calls them), never identity-compared, so wrapping is transparent.
def _lazy_native_resolution_attr(name: str):
    def _call(*args: Any, **kwargs: Any) -> Any:
        return getattr(repository_native_dispatch, name)(*args, **kwargs)

    _call.__name__ = name
    _call.__qualname__ = name
    return _call


for _native_resolution_name in repository_native_dispatch._NATIVE_RESOLUTION_EXPORT_NAMES:
    globals()[_native_resolution_name] = _lazy_native_resolution_attr(_native_resolution_name)
del _native_resolution_name


def _parse_assembly_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        assembly_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_assembly_import,
            resolve_target=_resolve_assembly_target,
        )
    )


def _parse_assembly_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = assembly_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_assembly_import,
        resolve_target=_resolve_assembly_target,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_sql_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        sql_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_target=_resolve_sql_target,
        )
    )


def _parse_sql_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = sql_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_target=_resolve_sql_target,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_tsql_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        tsql_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_target=_resolve_sql_target,
        )
    )


def _parse_tsql_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = tsql_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_target=_resolve_sql_target,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_prolog_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        prolog_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_prolog_import,
            resolve_target=_resolve_prolog_target,
        )
    )


def _parse_prolog_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = prolog_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_prolog_import,
        resolve_target=_resolve_prolog_target,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_abap_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        abap_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_include=_resolve_abap_include,
            resolve_target=_resolve_abap_target,
        )
    )


def _parse_abap_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = abap_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_include=_resolve_abap_include,
        resolve_target=_resolve_abap_target,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_plsql_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        plsql_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_plsql_import,
            resolve_target=_resolve_plsql_target,
        )
    )


def _parse_plsql_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = plsql_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_plsql_import,
        resolve_target=_resolve_plsql_target,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_sas_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        sas_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_include=_resolve_sas_include,
            resolve_target=_resolve_sas_target,
        )
    )


def _parse_sas_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = sas_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_include=_resolve_sas_include,
        resolve_target=_resolve_sas_target,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_matlab_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        matlab_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_matlab_import,
            resolve_target=_resolve_matlab_target,
        )
    )


def _parse_matlab_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = matlab_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_matlab_import,
        resolve_target=_resolve_matlab_target,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_ml_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        ml_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_ml_import,
        )
    )


def _parse_ml_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = ml_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_ml_import,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_lisp_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        lisp_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            normalize_repository_relative_path=_normalize_repository_relative_path,
            resolve_suffix_match=_resolve_suffix_match,
        )
    )


def _parse_lisp_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = lisp_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_clarity_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _clarity_dependencies(file_path, text, module_index)


def _parse_clarity_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbols = _clarity_symbols(file_path, text)
    dependencies = _clarity_dependencies(file_path, text, module_index)
    source_symbol_id = symbols[0].symbol_id if symbols else ""
    references = _clarity_references(
        file_path,
        text,
        module_index,
        source_symbol_id=source_symbol_id,
    )
    return (symbols, dependencies, references)


def _parse_emacslisp_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        emacslisp_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            normalize_repository_relative_path=_normalize_repository_relative_path,
            resolve_suffix_match=_resolve_suffix_match,
        )
    )


def _parse_emacslisp_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = emacslisp_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_racket_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        racket_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            normalize_repository_relative_path=_normalize_repository_relative_path,
            resolve_suffix_match=_resolve_suffix_match,
        )
    )


def _parse_racket_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = racket_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_scheme_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        scheme_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            normalize_repository_relative_path=_normalize_repository_relative_path,
            resolve_suffix_match=_resolve_suffix_match,
        )
    )


def _parse_scheme_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = scheme_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _extract_fsharp_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding], tuple[str, ...]]:
    return fsharp_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
        resolve_directory_prefix_match=_resolve_directory_prefix_match,
    )


def _parse_fsharp_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return fsharp_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
        resolve_directory_prefix_match=_resolve_directory_prefix_match,
    )


def _parse_fsharp_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    return fsharp_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
        resolve_directory_prefix_match=_resolve_directory_prefix_match,
    )


def _parse_d_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        d_language_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_d_import,
        )
    )


def _parse_d_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = d_language_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_d_import,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_fortran_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        fortran_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_fortran_import,
            module_index_aliases_for_file=_module_index_aliases_for_file,
        )
    )


def _parse_fortran_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = fortran_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_fortran_import,
        module_index_aliases_for_file=_module_index_aliases_for_file,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_ada_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        ada_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_ada_import,
        )
    )


def _parse_ada_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = ada_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_ada_import,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_cobol_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        cobol_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_cobol_import,
        )
    )


def _parse_cobol_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = cobol_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_cobol_import,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_visual_basic_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        visual_basic_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_visual_basic_import,
        )
    )


def _parse_visual_basic_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = visual_basic_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_visual_basic_import,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_classic_visual_basic_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    resolve_target_fn = _cached_classic_visual_basic_target_resolver(module_index)
    return _dependencies_from_specs(
        classic_visual_basic_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_target_fn=resolve_target_fn,
        )
    )


def _parse_classic_visual_basic_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    resolve_target_fn = _cached_classic_visual_basic_target_resolver(module_index)
    symbol_entries, dependency_specs, reference_specs = (
        classic_visual_basic_adapter.parse_file(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_target_fn=resolve_target_fn,
        )
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_freebasic_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    aliased_index = _virtualized_suffix_module_index(
        module_index,
        source_suffixes=(".bi", ".bas"),
        target_suffix=".bas",
    )
    resolve_target_fn = _cached_classic_visual_basic_target_resolver(aliased_index)
    return _dependencies_from_specs(
        classic_visual_basic_adapter.parse_dependencies_only(
            _virtualized_language_file_path(file_path, suffix=".bas"),
            text,
            aliased_index,
            stable_identifier=_stable_identifier,
            resolve_target_fn=resolve_target_fn,
        )
    )


def _parse_freebasic_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    aliased_index = _virtualized_suffix_module_index(
        module_index,
        source_suffixes=(".bi", ".bas"),
        target_suffix=".bas",
    )
    resolve_target_fn = _cached_classic_visual_basic_target_resolver(aliased_index)
    symbol_entries, dependency_specs, reference_specs = (
        classic_visual_basic_adapter.parse_file(
            _virtualized_language_file_path(file_path, suffix=".bas"),
            text,
            aliased_index,
            stable_identifier=_stable_identifier,
            resolve_target_fn=resolve_target_fn,
        )
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_foxpro_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        foxpro_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_target_fn=lambda reference_target: _resolve_foxpro_target(
                reference_target,
                module_index,
            ),
        )
    )


def _parse_foxpro_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = foxpro_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_target_fn=lambda reference_target: _resolve_foxpro_target(
            reference_target,
            module_index,
        ),
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


def _parse_objective_c_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return _dependencies_from_specs(
        objective_c_adapter.parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_objective_c_import,
            resolve_target=_resolve_objective_c_target,
        )
    )


def _parse_objective_c_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = objective_c_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_objective_c_import,
        resolve_target=_resolve_objective_c_target,
    )
    return (
        _symbols_from_entries(symbol_entries),
        _dependencies_from_specs(dependency_specs),
        _references_from_specs(reference_specs),
    )


