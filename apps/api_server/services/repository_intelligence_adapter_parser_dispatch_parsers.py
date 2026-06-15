# ruff: noqa: I001
from __future__ import annotations
from apps.api_server.services.repository_intelligence_adapter_parser_dispatch import (
    _Dependency, _ImportedSymbolBinding, _Symbol, _SymbolReferenceCandidate, _normalize_repository_relative_path, _resolve_suffix_match,
    _stable_identifier, apex_adapter, as3_adapter, awk_adapter, clojure_adapter, cpd,
    elm_adapter, erlang_adapter, fpd, gdscript_adapter, gml_adapter, labview_adapter,
    ladder_adapter, perl_adapter, powershell_adapter, r_language_adapter, repository_scripting_parser_dispatch, repository_typed_parser_dispatch,
    repository_xpp_parser_dispatch, rlr, rpg_adapter, scratch_adapter, shell_adapter, systemverilog_adapter,
    tcl_adapter, vbscript_adapter, vhdl_adapter, wolfram_adapter,
)
_resolve_clojure_import = rlr._resolve_clojure_import
_resolve_erlang_include, _resolve_erlang_module = (
    rlr._resolve_erlang_include,
    rlr._resolve_erlang_module,
)
def _parse_awk_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return awk_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )
def _parse_awk_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return awk_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )
def _parse_elm_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return elm_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )
def _parse_elm_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return elm_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )
def _parse_actionscript_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return as3_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )
def _parse_actionscript_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return as3_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )
def _parse_scratch_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return scratch_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
    )
def _parse_scratch_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return scratch_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
    )
def _parse_erlang_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return erlang_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_module=_resolve_erlang_module,
        resolve_include=_resolve_erlang_include,
    )
def _parse_erlang_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return erlang_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_module=_resolve_erlang_module,
        resolve_include=_resolve_erlang_include,
    )


def _parse_clojure_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return clojure_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_clojure_import,
    )


def _parse_clojure_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return clojure_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_clojure_import,
    )


def _parse_shell_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return shell_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_shell_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return shell_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_powershell_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return powershell_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_powershell_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return powershell_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _extract_perl_dependency_candidates(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    return perl_adapter.extract_dependency_candidates(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_perl_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return perl_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_perl_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return perl_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_vbscript_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return vbscript_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_rpg_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return rpg_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_apex_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return apex_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_wolfram_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return wolfram_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_ladder_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return ladder_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
    )


def _parse_labview_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return labview_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_tcl_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return tcl_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_systemverilog_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return systemverilog_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_vhdl_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return vhdl_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_gdscript_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return gdscript_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_gml_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return gml_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
    )


def _parse_vbscript_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return vbscript_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_tcl_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return tcl_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_systemverilog_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return systemverilog_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_gdscript_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return gdscript_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_gml_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return gml_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
    )


def _parse_vhdl_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return vhdl_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_rpg_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return rpg_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_apex_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return apex_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_wolfram_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return wolfram_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_ladder_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return ladder_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
    )


def _parse_labview_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return labview_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _extract_r_dependency_candidates(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return r_language_adapter.extract_dependency_candidates(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_r_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return r_language_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_r_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return r_language_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


_parse_ruby_dependencies_only = (
    repository_scripting_parser_dispatch._parse_ruby_dependencies_only
)
_extract_ruby_import_bindings = (
    repository_scripting_parser_dispatch._extract_ruby_import_bindings
)
_resolve_ruby_reference_target = (
    repository_scripting_parser_dispatch._resolve_ruby_reference_target
)
_iter_ruby_reference_targets = (
    repository_scripting_parser_dispatch._iter_ruby_reference_targets
)
_parse_ruby_file = repository_scripting_parser_dispatch._parse_ruby_file
_extract_crystal_import_bindings = (
    repository_scripting_parser_dispatch._extract_crystal_import_bindings
)
_resolve_crystal_reference_target = (
    repository_scripting_parser_dispatch._resolve_crystal_reference_target
)
_iter_crystal_reference_targets = (
    repository_scripting_parser_dispatch._iter_crystal_reference_targets
)
_parse_crystal_dependencies_only = (
    repository_scripting_parser_dispatch._parse_crystal_dependencies_only
)
_parse_crystal_file = repository_scripting_parser_dispatch._parse_crystal_file
_extract_php_import_bindings = repository_scripting_parser_dispatch._extract_php_import_bindings
_parse_php_dependencies_only = repository_scripting_parser_dispatch._parse_php_dependencies_only
_parse_php_file = repository_scripting_parser_dispatch._parse_php_file
_extract_elixir_import_bindings = (
    repository_scripting_parser_dispatch._extract_elixir_import_bindings
)
_parse_elixir_dependencies_only = (
    repository_scripting_parser_dispatch._parse_elixir_dependencies_only
)
_parse_elixir_file = repository_scripting_parser_dispatch._parse_elixir_file
_parse_swift_dependencies_only = repository_typed_parser_dispatch._parse_swift_dependencies_only
_parse_swift_file = repository_typed_parser_dispatch._parse_swift_file
_extract_csharp_import_bindings = repository_typed_parser_dispatch._extract_csharp_import_bindings
_parse_csharp_dependencies_only = repository_typed_parser_dispatch._parse_csharp_dependencies_only
_parse_csharp_file = repository_typed_parser_dispatch._parse_csharp_file
_parse_xpp_dependencies_only = repository_xpp_parser_dispatch._parse_xpp_dependencies_only
_parse_xpp_file = repository_xpp_parser_dispatch._parse_xpp_file
_parse_cfml_dependencies_only = cpd._parse_cfml_dependencies_only
_parse_cfml_file = cpd._parse_cfml_file
_parse_fish_dependencies_only = fpd._parse_fish_dependencies_only
_parse_fish_file = fpd._parse_fish_file
_extract_jvm_import_bindings = repository_typed_parser_dispatch._extract_jvm_import_bindings
_parse_jvm_dependencies_only = repository_typed_parser_dispatch._parse_jvm_dependencies_only
_parse_jvm_file = repository_typed_parser_dispatch._parse_jvm_file
