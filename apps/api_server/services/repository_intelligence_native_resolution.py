from __future__ import annotations

from typing import Any

from apps.api_server.services import repository_intelligence_adapters as repository_adapters
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _resolve_directory_prefix_match,
    _resolve_suffix_match,
)


class _LazyAdapterModule:
    __slots__ = ("_adapter_name", "_attribute_cache", "_loaded_module")

    def __init__(self, adapter_name: str) -> None:
        object.__setattr__(self, "_adapter_name", adapter_name)
        object.__setattr__(self, "_attribute_cache", {})
        object.__setattr__(self, "_loaded_module", None)

    def _load(self):
        loaded_module = object.__getattribute__(self, "_loaded_module")
        if loaded_module is None:
            loaded_module = getattr(repository_adapters, self._adapter_name)
            object.__setattr__(self, "_loaded_module", loaded_module)
        return loaded_module

    def __getattr__(self, name: str) -> object:
        cache = object.__getattribute__(self, "_attribute_cache")
        try:
            return cache[name]
        except KeyError:
            value = getattr(self._load(), name)
            cache[name] = value
            return value

    def __setattr__(self, name: str, value: object) -> None:
        # Slot-backed bookkeeping fields use the normal path; any other attribute is an
        # override (notably pytest's ``monkeypatch.setattr``) routed through the attribute
        # cache so callers can patch the wrapper without mutating the shared adapter
        # module. ``__getattr__`` reads the cache first, so the override takes effect.
        if name in _LazyAdapterModule.__slots__:
            object.__setattr__(self, name, value)
            return
        object.__getattribute__(self, "_attribute_cache")[name] = value

    def __delattr__(self, name: str) -> None:
        cache = object.__getattribute__(self, "_attribute_cache")
        if name in cache:
            del cache[name]
            return
        raise AttributeError(name)


def _lazy_adapter_module(adapter_name: str) -> _LazyAdapterModule:
    return _LazyAdapterModule(adapter_name)


abap_adapter = _lazy_adapter_module("abap")
ada_adapter = _lazy_adapter_module("ada")
assembly_adapter = _lazy_adapter_module("assembly")
classic_visual_basic_adapter = _lazy_adapter_module("classic_visual_basic")
cobol_adapter = _lazy_adapter_module("cobol")
d_language_adapter = _lazy_adapter_module("d_language")
fortran_adapter = _lazy_adapter_module("fortran")
foxpro_adapter = _lazy_adapter_module("foxpro")
matlab_adapter = _lazy_adapter_module("matlab")
ml_adapter = _lazy_adapter_module("ml")
objective_c_adapter = _lazy_adapter_module("objective_c")
plsql_adapter = _lazy_adapter_module("plsql")
prolog_adapter = _lazy_adapter_module("prolog")
sas_adapter = _lazy_adapter_module("sas")
sql_adapter = _lazy_adapter_module("sql")
visual_basic_adapter = _lazy_adapter_module("visual_basic")


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
