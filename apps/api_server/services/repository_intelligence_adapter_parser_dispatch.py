# ruff: noqa: I001
from __future__ import annotations
from apps.api_server.services import repository_intelligence_agda_parser_dispatch as apd
from apps.api_server.services import repository_intelligence_bicep_parser_dispatch as bpd
from apps.api_server.services import repository_intelligence_batchfile_parser_dispatch as bfpd
from apps.api_server.services import repository_intelligence_bitbake_parser_dispatch as bbpd
from apps.api_server.services import repository_intelligence_chapel_parser_dispatch as chpd
from apps.api_server.services import repository_intelligence_cmake_parser_dispatch as cmpd
from apps.api_server.services import repository_intelligence_cfml_parser_dispatch as cpd
from apps.api_server.services import repository_intelligence_cue_parser_dispatch as cupd
from apps.api_server.services import repository_intelligence_coq_parser_dispatch as cqd
from apps.api_server.services import repository_intelligence_dhall_parser_dispatch as dpd
from apps.api_server.services import repository_intelligence_eiffel_parser_dispatch as epd
from apps.api_server.services import repository_intelligence_factor_parser_dispatch as fad
from apps.api_server.services import repository_intelligence_fish_parser_dispatch as fpd
from apps.api_server.services import repository_intelligence_glsl_parser_dispatch as gpd
from apps.api_server.services import repository_intelligence_hack_parser_dispatch as hkd
from apps.api_server.services import repository_intelligence_hcl_parser_dispatch as hpd
from apps.api_server.services import repository_intelligence_hlsl_parser_dispatch as hlpd
from apps.api_server.services import repository_intelligence_wgsl_parser_dispatch as wpd
from apps.api_server.services import repository_intelligence_idris_parser_dispatch as ipd
from apps.api_server.services import repository_intelligence_antlr_parser_dispatch as anpd, repository_intelligence_asciidoc_parser_dispatch as adpd, repository_intelligence_blade_parser_dispatch as blpd, repository_intelligence_cuda_parser_dispatch as ctd, repository_intelligence_cython_parser_dispatch as cypd, repository_intelligence_dockerfile_parser_dispatch as dfd, repository_intelligence_ejs_parser_dispatch as ejpd, repository_intelligence_erb_parser_dispatch as erpd, repository_intelligence_fennel_parser_dispatch as fnpd, repository_intelligence_gherkin_parser_dispatch as ghpd, repository_intelligence_graphviz_parser_dispatch as gvpd, repository_intelligence_haml_parser_dispatch as hmpd, repository_intelligence_handlebars_parser_dispatch as hbpd, repository_intelligence_hy_parser_dispatch as hypd, repository_intelligence_janet_parser_dispatch as jpd, repository_intelligence_jinja_parser_dispatch as jnd, repository_intelligence_just_parser_dispatch as jstd, repository_intelligence_lean_parser_dispatch as lpd, repository_intelligence_liquid_parser_dispatch as lqd, repository_intelligence_logtalk_parser_dispatch as lgd, repository_intelligence_mermaid_parser_dispatch as mmpd, repository_intelligence_modelica_parser_dispatch as mdpd, repository_intelligence_moonbit_parser_dispatch as mbpd, repository_intelligence_move_parser_dispatch as mvpd, repository_intelligence_mustache_parser_dispatch as mpstpd, repository_intelligence_nextflow_parser_dispatch as nfpd, repository_intelligence_nunjucks_parser_dispatch as njpd, repository_intelligence_openqasm_parser_dispatch as oqpd, repository_intelligence_org_parser_dispatch as orgpd, repository_intelligence_plantuml_parser_dispatch as pupd, repository_intelligence_protobuf_parser_dispatch as ppbd, repository_intelligence_pug_parser_dispatch as pugpd, repository_intelligence_rescript_parser_dispatch as rscpd, repository_intelligence_robotframework_parser_dispatch as rfpd, repository_intelligence_roc_parser_dispatch as rocpd, repository_intelligence_rst_parser_dispatch as rspd, repository_intelligence_scss_parser_dispatch as scpd, repository_intelligence_shaderlab_parser_dispatch as shpd, repository_intelligence_slim_parser_dispatch as slpd, repository_intelligence_smarty_parser_dispatch as smpd, repository_intelligence_stan_parser_dispatch as spd, repository_intelligence_tex_parser_dispatch as txpd, repository_intelligence_twig_parser_dispatch as twpd, repository_intelligence_typst_parser_dispatch as tpd2, repository_intelligence_wren_parser_dispatch as wrpd  # noqa: E501
from apps.api_server.services import repository_intelligence_astro_parser_dispatch as astpd, repository_intelligence_less_parser_dispatch as lepd, repository_intelligence_luau_parser_dispatch as lud, repository_intelligence_makefile_parser_dispatch as mpd, repository_intelligence_meson_parser_dispatch as msd, repository_intelligence_odin_parser_dispatch as opd, repository_intelligence_qmake_parser_dispatch as qpd, repository_intelligence_qml_parser_dispatch as qmd, repository_intelligence_stylus_parser_dispatch as sypd, repository_intelligence_svelte_parser_dispatch as svpd, repository_intelligence_vue_parser_dispatch as vpd  # noqa: E501
from apps.api_server.services import repository_intelligence_puppet_parser_dispatch as ppd, repository_intelligence_rego_parser_dispatch as rpd, repository_intelligence_tlaplus_parser_dispatch as tpd  # noqa: E501
from apps.api_server.services import repository_intelligence_language_resolution as rlr
from apps.api_server.services import repository_intelligence_native_dispatch as rnd
from apps.api_server.services import (
    repository_intelligence_pascal_solidity_dispatch as repository_pascal_solidity_dispatch,
    repository_intelligence_raku_parser_dispatch as repository_raku_parser_dispatch,
)
from apps.api_server.services import repository_intelligence_scripting_parser_dispatch as repository_scripting_parser_dispatch, repository_intelligence_simple_parser_dispatch as repository_simple_parser_dispatch, repository_intelligence_typed_parser_dispatch as repository_typed_parser_dispatch  # noqa: E501
from apps.api_server.services import (
    repository_intelligence_verilog_parser_dispatch as repository_verilog_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_xpp_parser_dispatch as repository_xpp_parser_dispatch,
)
from apps.api_server.services import repository_intelligence_yara_parser_dispatch as ypd
from apps.api_server.services.repository_intelligence_adapters import actionscript as as3_adapter
from apps.api_server.services.repository_intelligence_adapters import apex as apex_adapter
from apps.api_server.services.repository_intelligence_adapters import awk as awk_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    clojure as clojure_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import elm as elm_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    erlang as erlang_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gdscript as gdscript_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gml as gml_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    labview as labview_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ladder as ladder_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    perl as perl_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    powershell as powershell_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    r_language as r_language_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import rpg as rpg_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    scratch as scratch_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    shell as shell_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    systemverilog as systemverilog_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    tcl as tcl_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vbscript as vbscript_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import vhdl as vhdl_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    wolfram as wolfram_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _normalize_repository_relative_path,
    _resolve_suffix_match,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier
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
REGISTERED_ADAPTER_DEPENDENCY_PARSERS = {
    **rnd.NATIVE_ADAPTER_DEPENDENCY_PARSERS,
    **repository_pascal_solidity_dispatch.PASCAL_SOLIDITY_ADAPTER_DEPENDENCY_PARSERS,
    "awk": _parse_awk_dependencies_only, "robotframework": rfpd._parse_robotframework_dependencies_only, "gherkin": ghpd._parse_gherkin_dependencies_only, "antlr": anpd._parse_antlr_dependencies_only, "graphviz": gvpd._parse_graphviz_dependencies_only, "mermaid": mmpd._parse_mermaid_dependencies_only, "plantuml": pupd._parse_plantuml_dependencies_only, "openqasm": oqpd._parse_openqasm_dependencies_only, "move": mvpd._parse_move_dependencies_only, "modelica": mdpd._parse_modelica_dependencies_only, "moonbit": mbpd._parse_moonbit_dependencies_only, "rescript": rscpd._parse_rescript_dependencies_only, "roc": rocpd._parse_roc_dependencies_only, "scss": scpd._parse_scss_dependencies_only, "less": lepd._parse_less_dependencies_only, "stylus": sypd._parse_stylus_dependencies_only, "jinja": jnd._parse_jinja_dependencies_only, "liquid": lqd._parse_liquid_dependencies_only, "handlebars": hbpd._parse_handlebars_dependencies_only, "mustache": mpstpd._parse_mustache_dependencies_only, "nunjucks": njpd._parse_nunjucks_dependencies_only, "twig": twpd._parse_twig_dependencies_only, "haml": hmpd._parse_haml_dependencies_only, "slim": slpd._parse_slim_dependencies_only, "smarty": smpd._parse_smarty_dependencies_only, "erb": erpd._parse_erb_dependencies_only, "pug": pugpd._parse_pug_dependencies_only, "ejs": ejpd._parse_ejs_dependencies_only, "blade": blpd._parse_blade_dependencies_only, "dockerfile": dfd._parse_dockerfile_dependencies_only, "protobuf": ppbd._parse_protobuf_dependencies_only, "tex": txpd._parse_tex_dependencies_only, "rst": rspd._parse_rst_dependencies_only, "asciidoc": adpd._parse_asciidoc_dependencies_only, "org": orgpd._parse_org_dependencies_only,
    "batchfile": bfpd._parse_batchfile_dependencies_only,
    "makefile": mpd._parse_makefile_dependencies_only, "just": jstd._parse_just_dependencies_only,
    "cuda": ctd._parse_cuda_dependencies_only,
    "cython": cypd._parse_cython_dependencies_only,
    "hlsl": hlpd._parse_hlsl_dependencies_only,
    "wgsl": wpd._parse_wgsl_dependencies_only,
    "shaderlab": shpd._parse_shaderlab_dependencies_only,
    "stan": spd._parse_stan_dependencies_only,
    "typst": tpd2._parse_typst_dependencies_only,
    "cmake": cmpd._parse_cmake_dependencies_only, "meson": msd._parse_meson_dependencies_only, "qmake": qpd._parse_qmake_dependencies_only, "qml": qmd._parse_qml_dependencies_only, "vue": vpd._parse_vue_dependencies_only, "svelte": svpd._parse_svelte_dependencies_only, "astro": astpd._parse_astro_dependencies_only,
    "bitbake": bbpd._parse_bitbake_dependencies_only,
    "odin": opd._parse_odin_dependencies_only,
    "factor": fad._parse_factor_dependencies_only,
    "cue": cupd._parse_cue_dependencies_only,
    "cfml": _parse_cfml_dependencies_only,
    "chapel": chpd._parse_chapel_dependencies_only,
    "coq": cqd._parse_coq_dependencies_only,
    "lean": lpd._parse_lean_dependencies_only,
    "eiffel": epd._parse_eiffel_dependencies_only,
    "glsl": gpd._parse_glsl_dependencies_only,
    "elm": _parse_elm_dependencies_only,
    "xpp": _parse_xpp_dependencies_only,
    "actionscript": _parse_actionscript_dependencies_only,
    "scratch": _parse_scratch_dependencies_only,
    "crystal": _parse_crystal_dependencies_only,
    "ex": _parse_elixir_dependencies_only,
    "erlang": _parse_erlang_dependencies_only,
    "gdscript": _parse_gdscript_dependencies_only,
    "gml": _parse_gml_dependencies_only,
    "fish": _parse_fish_dependencies_only,
    "hack": hkd._parse_hack_dependencies_only,
    "hcl": hpd._parse_hcl_dependencies_only,
    "haskell": repository_simple_parser_dispatch._parse_haskell_dependencies_only,
    "agda": apd._parse_agda_dependencies_only,
    "idris": ipd._parse_idris_dependencies_only,
    "rego": rpd._parse_rego_dependencies_only, "yara": ypd._parse_yara_dependencies_only,
    "hy": hypd._parse_hy_dependencies_only, "wren": wrpd._parse_wren_dependencies_only, "janet": jpd._parse_janet_dependencies_only, "fennel": fnpd._parse_fennel_dependencies_only, "nextflow": nfpd._parse_nextflow_dependencies_only, "bicep": bpd._parse_bicep_dependencies_only,
    "dhall": dpd._parse_dhall_dependencies_only,
    "puppet": ppd._parse_puppet_dependencies_only,
    "tlaplus": tpd._parse_tlaplus_dependencies_only,
    "logtalk": lgd._parse_logtalk_dependencies_only,
    "raku": repository_raku_parser_dispatch._parse_raku_dependencies_only,
    "julia": repository_simple_parser_dispatch._parse_julia_dependencies_only,
    "lua": lud._parse_lua_dependencies_only,
    "luau": lud._parse_luau_dependencies_only,
    "nim": repository_simple_parser_dispatch._parse_nim_dependencies_only,
    "clojure": _parse_clojure_dependencies_only,
    "ocaml": repository_simple_parser_dispatch._parse_ocaml_dependencies_only,
    "perl": _parse_perl_dependencies_only,
    "php": _parse_php_dependencies_only, "powershell": _parse_powershell_dependencies_only,
    "ruby": _parse_ruby_dependencies_only,
    "shell": _parse_shell_dependencies_only,
    "swift": _parse_swift_dependencies_only, "ladder": _parse_ladder_dependencies_only,
    "labview": _parse_labview_dependencies_only,
    "tcl": _parse_tcl_dependencies_only,
    **repository_verilog_parser_dispatch.VERILOG_ADAPTER_DEPENDENCY_PARSERS,
    "systemverilog": _parse_systemverilog_dependencies_only,
    "vhdl": _parse_vhdl_dependencies_only,
    "vbscript": _parse_vbscript_dependencies_only,
    "rpg": _parse_rpg_dependencies_only,
    "apex": _parse_apex_dependencies_only,
    "wolfram": _parse_wolfram_dependencies_only,
    "cs": _parse_csharp_dependencies_only,
}
REGISTERED_ADAPTER_FILE_PARSERS = {
    **rnd.NATIVE_ADAPTER_FILE_PARSERS,
    **repository_pascal_solidity_dispatch.PASCAL_SOLIDITY_ADAPTER_FILE_PARSERS,
    "awk": _parse_awk_file, "robotframework": rfpd._parse_robotframework_file, "gherkin": ghpd._parse_gherkin_file, "antlr": anpd._parse_antlr_file, "graphviz": gvpd._parse_graphviz_file, "mermaid": mmpd._parse_mermaid_file, "plantuml": pupd._parse_plantuml_file, "openqasm": oqpd._parse_openqasm_file, "move": mvpd._parse_move_file, "modelica": mdpd._parse_modelica_file, "moonbit": mbpd._parse_moonbit_file, "rescript": rscpd._parse_rescript_file, "roc": rocpd._parse_roc_file, "scss": scpd._parse_scss_file, "less": lepd._parse_less_file, "stylus": sypd._parse_stylus_file, "jinja": jnd._parse_jinja_file, "liquid": lqd._parse_liquid_file, "handlebars": hbpd._parse_handlebars_file, "mustache": mpstpd._parse_mustache_file, "nunjucks": njpd._parse_nunjucks_file, "twig": twpd._parse_twig_file, "haml": hmpd._parse_haml_file, "slim": slpd._parse_slim_file, "smarty": smpd._parse_smarty_file, "erb": erpd._parse_erb_file, "pug": pugpd._parse_pug_file, "ejs": ejpd._parse_ejs_file, "blade": blpd._parse_blade_file, "dockerfile": dfd._parse_dockerfile_file, "protobuf": ppbd._parse_protobuf_file, "tex": txpd._parse_tex_file, "rst": rspd._parse_rst_file, "asciidoc": adpd._parse_asciidoc_file, "org": orgpd._parse_org_file,
    "batchfile": bfpd._parse_batchfile_file,
    "makefile": mpd._parse_makefile_file, "bitbake": bbpd._parse_bitbake_file, "just": jstd._parse_just_file,
    "cuda": ctd._parse_cuda_file,
    "cython": cypd._parse_cython_file,
    "hlsl": hlpd._parse_hlsl_file,
    "wgsl": wpd._parse_wgsl_file,
    "shaderlab": shpd._parse_shaderlab_file,
    "stan": spd._parse_stan_file,
    "typst": tpd2._parse_typst_file,
    "cmake": cmpd._parse_cmake_file, "meson": msd._parse_meson_file, "qmake": qpd._parse_qmake_file, "qml": qmd._parse_qml_file, "vue": vpd._parse_vue_file, "svelte": svpd._parse_svelte_file, "astro": astpd._parse_astro_file,
    "odin": opd._parse_odin_file,
    "factor": fad._parse_factor_file,
    "cue": cupd._parse_cue_file,
    "cfml": _parse_cfml_file,
    "chapel": chpd._parse_chapel_file,
    "coq": cqd._parse_coq_file,
    "lean": lpd._parse_lean_file,
    "eiffel": epd._parse_eiffel_file,
    "glsl": gpd._parse_glsl_file,
    "elm": _parse_elm_file,
    "xpp": _parse_xpp_file,
    "actionscript": _parse_actionscript_file,
    "scratch": _parse_scratch_file,
    "crystal": _parse_crystal_file,
    "ex": _parse_elixir_file,
    "erlang": _parse_erlang_file,
    "gdscript": _parse_gdscript_file,
    "gml": _parse_gml_file,
    "fish": _parse_fish_file, "hack": hkd._parse_hack_file, "hcl": hpd._parse_hcl_file,
    "haskell": repository_simple_parser_dispatch._parse_haskell_file,
    "agda": apd._parse_agda_file,
    "idris": ipd._parse_idris_file, "rego": rpd._parse_rego_file, "yara": ypd._parse_yara_file,
    "hy": hypd._parse_hy_file, "wren": wrpd._parse_wren_file, "janet": jpd._parse_janet_file, "fennel": fnpd._parse_fennel_file, "nextflow": nfpd._parse_nextflow_file, "bicep": bpd._parse_bicep_file, "dhall": dpd._parse_dhall_file,
    "puppet": ppd._parse_puppet_file,
    "tlaplus": tpd._parse_tlaplus_file,
    "logtalk": lgd._parse_logtalk_file,
    "raku": repository_raku_parser_dispatch._parse_raku_file,
    "julia": repository_simple_parser_dispatch._parse_julia_file,
    "lua": lud._parse_lua_file,
    "luau": lud._parse_luau_file,
    "nim": repository_simple_parser_dispatch._parse_nim_file,
    "clojure": _parse_clojure_file,
    "ocaml": repository_simple_parser_dispatch._parse_ocaml_file,
    "perl": _parse_perl_file,
    "php": _parse_php_file, "powershell": _parse_powershell_file,
    "ruby": _parse_ruby_file,
    "shell": _parse_shell_file,
    "swift": _parse_swift_file, "ladder": _parse_ladder_file,
    "labview": _parse_labview_file,
    "tcl": _parse_tcl_file,
    **repository_verilog_parser_dispatch.VERILOG_ADAPTER_FILE_PARSERS,
    "systemverilog": _parse_systemverilog_file,
    "vhdl": _parse_vhdl_file,
    "vbscript": _parse_vbscript_file,
    "rpg": _parse_rpg_file,
    "apex": _parse_apex_file,
    "wolfram": _parse_wolfram_file,
    "cs": _parse_csharp_file,
}
