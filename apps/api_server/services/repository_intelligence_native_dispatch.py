from __future__ import annotations

from apps.api_server.services import (
    repository_intelligence_applescript_parser_dispatch as repository_applescript_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_native_resolution as repository_native_resolution,
)
from apps.api_server.services import (
    repository_intelligence_vba_parser_dispatch as repository_vba_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    abap as abap_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ada as ada_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    assembly as assembly_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    classic_visual_basic as classic_visual_basic_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    cobol as cobol_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    d_language as d_language_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    emacslisp as emacslisp_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    fortran as fortran_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    foxpro as foxpro_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    fsharp as fsharp_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    lisp as lisp_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    matlab as matlab_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ml as ml_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    objective_c as objective_c_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    plsql as plsql_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    prolog as prolog_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    racket as racket_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    sas as sas_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    scheme as scheme_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    sql as sql_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    tsql as tsql_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    visual_basic as visual_basic_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _module_index_aliases_for_file,
    _normalize_repository_relative_path,
    _resolve_directory_prefix_match,
    _resolve_suffix_match,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_symbols_from_entries = repository_native_resolution._symbols_from_entries
_dependencies_from_specs = repository_native_resolution._dependencies_from_specs
_references_from_specs = repository_native_resolution._references_from_specs
_resolve_assembly_import = repository_native_resolution._resolve_assembly_import
_resolve_assembly_target = repository_native_resolution._resolve_assembly_target
_resolve_prolog_import = repository_native_resolution._resolve_prolog_import
_resolve_prolog_target = repository_native_resolution._resolve_prolog_target
_resolve_abap_include = repository_native_resolution._resolve_abap_include
_resolve_abap_target = repository_native_resolution._resolve_abap_target
_resolve_sql_target = repository_native_resolution._resolve_sql_target
_resolve_plsql_import = repository_native_resolution._resolve_plsql_import
_resolve_plsql_target = repository_native_resolution._resolve_plsql_target
_resolve_sas_include = repository_native_resolution._resolve_sas_include
_resolve_sas_target = repository_native_resolution._resolve_sas_target
_resolve_matlab_import = repository_native_resolution._resolve_matlab_import
_resolve_ml_import = repository_native_resolution._resolve_ml_import
_resolve_matlab_target = repository_native_resolution._resolve_matlab_target
_resolve_d_import = repository_native_resolution._resolve_d_import
_resolve_fortran_import = repository_native_resolution._resolve_fortran_import
_resolve_ada_import = repository_native_resolution._resolve_ada_import
_resolve_cobol_import = repository_native_resolution._resolve_cobol_import
_resolve_visual_basic_import = repository_native_resolution._resolve_visual_basic_import
_resolve_classic_visual_basic_target = (
    repository_native_resolution._resolve_classic_visual_basic_target
)
_resolve_foxpro_target = repository_native_resolution._resolve_foxpro_target
_resolve_objective_c_import = repository_native_resolution._resolve_objective_c_import
_resolve_objective_c_target = repository_native_resolution._resolve_objective_c_target
_parse_applescript_dependencies_only = (
    repository_applescript_parser_dispatch._parse_applescript_dependencies_only
)
_parse_applescript_file = repository_applescript_parser_dispatch._parse_applescript_file
_parse_vba_dependencies_only = repository_vba_parser_dispatch._parse_vba_dependencies_only
_parse_vba_file = repository_vba_parser_dispatch._parse_vba_file


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
    return _dependencies_from_specs(
        classic_visual_basic_adapter.parse_dependencies_only(
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


def _parse_classic_visual_basic_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_entries, dependency_specs, reference_specs = (
        classic_visual_basic_adapter.parse_file(
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


NATIVE_ADAPTER_DEPENDENCY_PARSERS = {
    "abap": _parse_abap_dependencies_only,
    "ada": _parse_ada_dependencies_only,
    "assembly": _parse_assembly_dependencies_only,
    "applescript": _parse_applescript_dependencies_only,
    "vb6": _parse_classic_visual_basic_dependencies_only,
    "vba": _parse_vba_dependencies_only,
    "cobol": _parse_cobol_dependencies_only,
    "d": _parse_d_dependencies_only,
    "foxpro": _parse_foxpro_dependencies_only,
    "fsharp": _parse_fsharp_dependencies_only,
    "fortran": _parse_fortran_dependencies_only,
    "lisp": _parse_lisp_dependencies_only,
    "emacslisp": _parse_emacslisp_dependencies_only,
    "scheme": _parse_scheme_dependencies_only,
    "racket": _parse_racket_dependencies_only,
    "matlab": _parse_matlab_dependencies_only,
    "ml": _parse_ml_dependencies_only,
    "objectivec": _parse_objective_c_dependencies_only,
    "plsql": _parse_plsql_dependencies_only,
    "prolog": _parse_prolog_dependencies_only,
    "sas": _parse_sas_dependencies_only,
    "sql": _parse_sql_dependencies_only,
    "tsql": _parse_tsql_dependencies_only,
    "vb": _parse_visual_basic_dependencies_only,
}

NATIVE_ADAPTER_FILE_PARSERS = {
    "abap": _parse_abap_file,
    "ada": _parse_ada_file,
    "assembly": _parse_assembly_file,
    "applescript": _parse_applescript_file,
    "vb6": _parse_classic_visual_basic_file,
    "vba": _parse_vba_file,
    "cobol": _parse_cobol_file,
    "d": _parse_d_file,
    "foxpro": _parse_foxpro_file,
    "fsharp": _parse_fsharp_file,
    "fortran": _parse_fortran_file,
    "lisp": _parse_lisp_file,
    "emacslisp": _parse_emacslisp_file,
    "scheme": _parse_scheme_file,
    "racket": _parse_racket_file,
    "matlab": _parse_matlab_file,
    "ml": _parse_ml_file,
    "objectivec": _parse_objective_c_file,
    "plsql": _parse_plsql_file,
    "prolog": _parse_prolog_file,
    "sas": _parse_sas_file,
    "sql": _parse_sql_file,
    "tsql": _parse_tsql_file,
    "vb": _parse_visual_basic_file,
}
