from __future__ import annotations

from typing import Any

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
    fortran as fortran_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    foxpro as foxpro_adapter,
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
    sas as sas_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    sql as sql_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    visual_basic as visual_basic_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _resolve_directory_prefix_match,
    _resolve_suffix_match,
)


def _symbols_from_entries(symbol_entries: list[dict[str, Any]]) -> tuple[_Symbol, ...]:
    return tuple(
        _Symbol(
            symbol_id=str(entry["symbol_id"]),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=None,
            signature=str(entry["signature"]),
        )
        for entry in symbol_entries
    )


def _dependencies_from_specs(
    dependency_specs: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> tuple[_Dependency, ...]:
    return tuple(_Dependency(**spec) for spec in dependency_specs)


def _references_from_specs(
    reference_specs: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> tuple[_SymbolReferenceCandidate, ...]:
    return tuple(_SymbolReferenceCandidate(**spec) for spec in reference_specs)


def _resolve_assembly_import(
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return assembly_adapter.resolve_import(
        current_file,
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_assembly_target(
    current_file: str,
    reference_target: str,
    module_index: dict[str, str],
) -> str | None:
    return assembly_adapter.resolve_target(
        current_file,
        reference_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_prolog_import(
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return prolog_adapter.resolve_import(
        current_file,
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_prolog_target(
    current_file: str,
    reference_target: str,
    module_index: dict[str, str],
) -> str | None:
    return prolog_adapter.resolve_target(
        current_file,
        reference_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_abap_include(
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return abap_adapter.resolve_include(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_abap_target(reference_target: str, module_index: dict[str, str]) -> str | None:
    return abap_adapter.resolve_target(
        reference_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_sql_target(reference_target: str, module_index: dict[str, str]) -> str | None:
    return sql_adapter.resolve_target(
        reference_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_plsql_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return plsql_adapter.resolve_import(
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_plsql_target(reference_target: str, module_index: dict[str, str]) -> str | None:
    return plsql_adapter.resolve_target(
        reference_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_sas_include(
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return sas_adapter.resolve_include(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_sas_target(reference_target: str, module_index: dict[str, str]) -> str | None:
    return sas_adapter.resolve_target(
        reference_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_matlab_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return matlab_adapter.resolve_import(
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_ml_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return ml_adapter.resolve_import(
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_matlab_target(
    current_file: str,
    reference_target: str,
    module_index: dict[str, str],
) -> str | None:
    return matlab_adapter.resolve_target(
        current_file,
        reference_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_d_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return d_language_adapter.resolve_import(
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_fortran_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return fortran_adapter.resolve_import(
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_ada_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return ada_adapter.resolve_import(
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
        resolve_directory_prefix_match=_resolve_directory_prefix_match,
    )


def _resolve_cobol_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return cobol_adapter.resolve_import(
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_visual_basic_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return visual_basic_adapter.resolve_import(
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
        resolve_directory_prefix_match=_resolve_directory_prefix_match,
    )


def _resolve_classic_visual_basic_target(
    reference_target: str,
    module_index: dict[str, str],
) -> str | None:
    return classic_visual_basic_adapter.resolve_target(
        reference_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
        resolve_directory_prefix_match=_resolve_directory_prefix_match,
    )


def _resolve_foxpro_target(reference_target: str, module_index: dict[str, str]) -> str | None:
    return foxpro_adapter.resolve_target(
        reference_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
        resolve_directory_prefix_match=_resolve_directory_prefix_match,
    )


def _resolve_objective_c_import(
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return objective_c_adapter.resolve_import(
        current_file,
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_objective_c_target(
    current_file: str,
    reference_target: str,
    module_index: dict[str, str],
) -> str | None:
    return objective_c_adapter.resolve_target(
        current_file,
        reference_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )
