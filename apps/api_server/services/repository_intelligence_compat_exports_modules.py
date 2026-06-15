# ruff: noqa: I001
from __future__ import annotations

import re
from types import ModuleType
from typing import Any

from apps.api_server.services import repository_intelligence_adapter_parser_dispatch as repository_adapter_parser_dispatch, repository_intelligence_bicep_parser_dispatch as repository_bicep_parser_dispatch, repository_intelligence_batchfile_parser_dispatch as repository_batchfile_parser_dispatch  # noqa: E501
from apps.api_server.services import (
    repository_intelligence_antlr_parser_dispatch as repository_intelligence_antlr_parser_dispatch,
    repository_intelligence_autoit_parser_dispatch as repository_autoit_parser_dispatch,
    repository_intelligence_gherkin_parser_dispatch as repository_intelligence_gherkin_parser_dispatch,
    repository_intelligence_graphviz_parser_dispatch as repository_intelligence_graphviz_parser_dispatch,
    repository_intelligence_just_parser_dispatch as repository_just_parser_dispatch,
    repository_intelligence_mermaid_parser_dispatch as repository_intelligence_mermaid_parser_dispatch,
    repository_intelligence_dm_parser_dispatch as repository_intelligence_dm_parser_dispatch,
    repository_intelligence_cairo_parser_dispatch as repository_intelligence_cairo_parser_dispatch,
    repository_intelligence_modelica_parser_dispatch as repository_intelligence_modelica_parser_dispatch,
    repository_intelligence_move_parser_dispatch as repository_intelligence_move_parser_dispatch,
    repository_intelligence_openqasm_parser_dispatch as repository_intelligence_openqasm_parser_dispatch,
    repository_intelligence_plantuml_parser_dispatch as repository_intelligence_plantuml_parser_dispatch,
    repository_intelligence_reasonml_parser_dispatch as repository_intelligence_reasonml_parser_dispatch,
    repository_intelligence_rescript_parser_dispatch as repository_intelligence_rescript_parser_dispatch,
    repository_intelligence_roc_parser_dispatch as repository_intelligence_roc_parser_dispatch,
    repository_intelligence_smarty_parser_dispatch as repository_intelligence_smarty_parser_dispatch,
    repository_intelligence_sway_parser_dispatch as repository_intelligence_sway_parser_dispatch,
    repository_intelligence_squirrel_parser_dispatch as repository_squirrel_parser_dispatch,
)
from apps.api_server.services import repository_intelligence_cuda_parser_dispatch as repository_intelligence_cuda_parser_dispatch, repository_intelligence_hlsl_parser_dispatch as repository_intelligence_hlsl_parser_dispatch, repository_intelligence_shaderlab_parser_dispatch as repository_intelligence_shaderlab_parser_dispatch, repository_intelligence_wgsl_parser_dispatch as repository_intelligence_wgsl_parser_dispatch  # noqa: E501
from apps.api_server.services import repository_intelligence_cython_parser_dispatch as repository_intelligence_cython_parser_dispatch, repository_intelligence_dockerfile_parser_dispatch as repository_intelligence_dockerfile_parser_dispatch, repository_intelligence_protobuf_parser_dispatch as repository_intelligence_protobuf_parser_dispatch, repository_intelligence_stan_parser_dispatch as repository_intelligence_stan_parser_dispatch  # noqa: E501
from apps.api_server.services import repository_intelligence_scss_parser_dispatch as repository_intelligence_scss_parser_dispatch, repository_intelligence_tex_parser_dispatch as repository_intelligence_tex_parser_dispatch, repository_intelligence_typst_parser_dispatch as repository_intelligence_typst_parser_dispatch  # noqa: E501
from apps.api_server.services import (
    repository_intelligence_less_parser_dispatch as repository_intelligence_less_parser_dispatch,
    repository_intelligence_stylus_parser_dispatch as repository_intelligence_stylus_parser_dispatch,
    repository_intelligence_astro_parser_dispatch as repository_intelligence_astro_parser_dispatch,
    repository_intelligence_svelte_parser_dispatch as repository_intelligence_svelte_parser_dispatch,
    repository_intelligence_pug_parser_dispatch as repository_intelligence_pug_parser_dispatch,
    repository_intelligence_ejs_parser_dispatch as repository_intelligence_ejs_parser_dispatch,
    repository_intelligence_blade_parser_dispatch as repository_intelligence_blade_parser_dispatch,
)
from apps.api_server.services import repository_intelligence_handlebars_parser_dispatch as repository_intelligence_handlebars_parser_dispatch, repository_intelligence_jinja_parser_dispatch as repository_intelligence_jinja_parser_dispatch, repository_intelligence_liquid_parser_dispatch as repository_intelligence_liquid_parser_dispatch  # noqa: E501
from apps.api_server.services import repository_intelligence_erb_parser_dispatch as repository_intelligence_erb_parser_dispatch, repository_intelligence_haml_parser_dispatch as repository_intelligence_haml_parser_dispatch, repository_intelligence_mustache_parser_dispatch as repository_intelligence_mustache_parser_dispatch, repository_intelligence_nunjucks_parser_dispatch as repository_intelligence_nunjucks_parser_dispatch, repository_intelligence_rst_parser_dispatch as repository_intelligence_rst_parser_dispatch, repository_intelligence_slim_parser_dispatch as repository_intelligence_slim_parser_dispatch, repository_intelligence_twig_parser_dispatch as repository_intelligence_twig_parser_dispatch  # noqa: E501
from apps.api_server.services import (
    repository_intelligence_makefile_parser_dispatch as repository_makefile_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_meson_parser_dispatch as repository_meson_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_qmake_parser_dispatch as repository_qmake_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_qml_parser_dispatch as repository_qml_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_vue_parser_dispatch as repository_vue_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_odin_parser_dispatch as repository_odin_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_cache as repository_cache,
)
from apps.api_server.services import (
    repository_intelligence_chapel_parser_dispatch as repository_chapel_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_coq_parser_dispatch as repository_coq_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_cue_parser_dispatch as repository_cue_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_lean_parser_dispatch as repository_lean_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_dhall_parser_dispatch as repository_dhall_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_eiffel_parser_dispatch as repository_eiffel_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_factor_parser_dispatch as repository_factor_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_glsl_parser_dispatch as repository_glsl_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_hack_parser_dispatch as repository_hack_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_puppet_parser_dispatch as repository_puppet_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_config as repository_config,
)
from apps.api_server.services import (
    repository_intelligence_contracts as repository_contracts,
)
from apps.api_server.services import (
    repository_intelligence_decision_plan_workflow as repository_decision_plan_workflow,
)
from apps.api_server.services import (
    repository_intelligence_file_selection as repository_file_selection,
)
from apps.api_server.services import (
    repository_intelligence_graph as repository_graph,
)
from apps.api_server.services import (
    repository_intelligence_indexing as repository_indexing,
)
from apps.api_server.services import (
    repository_intelligence_inventory as repository_inventory,
)
from apps.api_server.services import (
    repository_intelligence_hcl_parser_dispatch as repository_hcl_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_idris_parser_dispatch as repository_idris_parser_dispatch,
)
from apps.api_server.services import repository_intelligence_hy_parser_dispatch as repository_intelligence_hy_parser_dispatch, repository_intelligence_fennel_parser_dispatch as repository_intelligence_fennel_parser_dispatch, repository_intelligence_wren_parser_dispatch as repository_intelligence_wren_parser_dispatch, repository_intelligence_janet_parser_dispatch as repository_janet_parser_dispatch, repository_intelligence_nextflow_parser_dispatch as repository_intelligence_nextflow_parser_dispatch, repository_intelligence_moonbit_parser_dispatch as repository_intelligence_moonbit_parser_dispatch, repository_intelligence_vyper_parser_dispatch as repository_intelligence_vyper_parser_dispatch  # noqa: E501
from apps.api_server.services import (
    repository_intelligence_al_parser_dispatch as repository_intelligence_al_parser_dispatch,
    repository_intelligence_ballerina_parser_dispatch as repository_intelligence_ballerina_parser_dispatch,
    repository_intelligence_circom_parser_dispatch as repository_intelligence_circom_parser_dispatch,
    repository_intelligence_clojurescript_parser_dispatch as repository_intelligence_clojurescript_parser_dispatch,
    repository_intelligence_dafny_parser_dispatch as repository_intelligence_dafny_parser_dispatch,
    repository_intelligence_four_d_parser_dispatch as repository_intelligence_four_d_parser_dispatch,
    repository_intelligence_groovy_parser_dispatch as repository_intelligence_groovy_parser_dispatch,
    repository_intelligence_opencl_parser_dispatch as repository_intelligence_opencl_parser_dispatch,
    repository_intelligence_qsharp_parser_dispatch as repository_intelligence_qsharp_parser_dispatch,
    repository_intelligence_sass_parser_dispatch as repository_intelligence_sass_parser_dispatch,
    repository_intelligence_sml_parser_dispatch as repository_intelligence_sml_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_logtalk_parser_dispatch as repository_logtalk_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_luau_parser_dispatch as repository_luau_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_js_resolution as repository_js_resolution,
)
from apps.api_server.services import (
    repository_intelligence_language_resolution as repository_language_resolution,
)
from apps.api_server.services import (
    repository_intelligence_module_aliases as repository_module_aliases,
)
from apps.api_server.services import (
    repository_intelligence_native_dispatch as repository_native_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_native_resolution as repository_native_resolution,
)
from apps.api_server.services import (
    repository_intelligence_pascal_solidity_dispatch as repository_pascal_solidity_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_patch_analysis as repository_patch_analysis,
)
from apps.api_server.services import (
    repository_intelligence_planner_generation as repository_planner_generation,
)
from apps.api_server.services import (
    repository_intelligence_apl_parser_dispatch as repository_intelligence_apl_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_bqn_parser_dispatch as repository_intelligence_bqn_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_brightscript_parser_dispatch as repository_intelligence_brightscript_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_gnuplot_parser_dispatch as repository_intelligence_gnuplot_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_dataweave_parser_dispatch as repository_intelligence_dataweave_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_common_workflow_language_parser_dispatch as repository_intelligence_common_workflow_language_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_earthly_parser_dispatch as repository_intelligence_earthly_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_rebol_parser_dispatch as repository_intelligence_rebol_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_hoon_parser_dispatch as repository_intelligence_hoon_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_mercury_parser_dispatch as repository_intelligence_mercury_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_forth_parser_dispatch as repository_intelligence_forth_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_isabelle_parser_dispatch as repository_intelligence_isabelle_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_j_parser_dispatch as repository_intelligence_j_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_codeql_parser_dispatch as repository_intelligence_codeql_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_jsonnet_parser_dispatch as repository_intelligence_jsonnet_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_lex_parser_dispatch as repository_intelligence_lex_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_m4_parser_dispatch as repository_intelligence_m4_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_mako_parser_dispatch as repository_intelligence_mako_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_metal_parser_dispatch as repository_intelligence_metal_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_maven_parser_dispatch as repository_intelligence_maven_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_motoko_parser_dispatch as repository_intelligence_motoko_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_moonscript_parser_dispatch as repository_intelligence_moonscript_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_nginx_parser_dispatch as repository_intelligence_nginx_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_ocamllex_parser_dispatch as repository_intelligence_ocamllex_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_ocamlyacc_parser_dispatch as repository_intelligence_ocamlyacc_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_templ_parser_dispatch as repository_intelligence_templ_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_thrift_parser_dispatch as repository_intelligence_thrift_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_vcl_parser_dispatch as repository_intelligence_vcl_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_pawn_parser_dispatch as repository_intelligence_pawn_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_pony_parser_dispatch as repository_intelligence_pony_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_postscript_parser_dispatch as repository_intelligence_postscript_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_purebasic_parser_dispatch as repository_intelligence_purebasic_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_q_parser_dispatch as repository_intelligence_q_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_red_parser_dispatch as repository_intelligence_red_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_smali_parser_dispatch as repository_intelligence_smali_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_sed_parser_dispatch as repository_intelligence_sed_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_xquery_parser_dispatch as repository_intelligence_xquery_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_xslt_parser_dispatch as repository_intelligence_xslt_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_yacc_parser_dispatch as repository_intelligence_yacc_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_rego_parser_dispatch as repository_rego_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_robotframework_parser_dispatch as repository_robotframework_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_tlaplus_parser_dispatch as repository_tlaplus_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_yara_parser_dispatch as repository_yara_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_repository_source as repository_repository_source,
)
from apps.api_server.services import (
    repository_intelligence_runtime as repository_runtime,
)
from apps.api_server.services import (
    repository_intelligence_shared as repository_shared,
)
from apps.api_server.services import (
    repository_intelligence_simple_parser_dispatch as repository_simple_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_snapshot_workflow as repository_snapshot_workflow,
)
from apps.api_server.services import (
    repository_intelligence_storage as repository_storage,
)
from apps.api_server.services import (
    repository_intelligence_verilog_parser_dispatch as repository_verilog_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    actionscript as actionscript_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    applescript as applescript_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    autoit as autoit_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    squirrel as squirrel_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    bicep as bicep_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    bitbake as bitbake_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    batchfile as batchfile_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import just as just_adapter, dockerfile as dockerfile_adapter, cuda as cuda_adapter, robotframework as robotframework_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import scss as scss_adapter, less as less_adapter, stylus as stylus_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import antlr as antlr_adapter, astro as astro_adapter, svelte as svelte_adapter, pug as pug_adapter, cairo as cairo_adapter, dm as dm_adapter, ejs as ejs_adapter, blade as blade_adapter, fennel as fennel_adapter, gherkin as gherkin_adapter, graphviz as graphviz_adapter, hy as hy_adapter, mermaid as mermaid_adapter, modelica as modelica_adapter, moonbit as moonbit_adapter, move as move_adapter, nextflow as nextflow_adapter, openqasm as openqasm_adapter, plantuml as plantuml_adapter, reasonml as reasonml_adapter, rescript as rescript_adapter, roc as roc_adapter, smarty as smarty_adapter, sway as sway_adapter, wren as wren_adapter, vyper as vyper_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import graphql as graphql_adapter, pkl as pkl_adapter, plpgsql as plpgsql_adapter, webassembly as webassembly_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    al as al_adapter,
    ampl as ampl_adapter,
    ballerina as ballerina_adapter,
    brightscript as brightscript_adapter,
    bqn as bqn_adapter,
    clojurescript as clojurescript_adapter,
    common_workflow_language as common_workflow_language_adapter,
    dataweave as dataweave_adapter,
    earthly as earthly_adapter,
    forth as forth_adapter,
    four_d as four_d_adapter,
    gnuplot as gnuplot_adapter,
    groovy as groovy_adapter,
    isabelle as isabelle_adapter,
    j as j_adapter,
    jsonnet as jsonnet_adapter,
    codeql as codeql_adapter,
    lex as lex_adapter,
    mako as mako_adapter,
    m4 as m4_adapter,
    metal as metal_adapter,
    motoko as motoko_adapter,
    moonscript as moonscript_adapter,
    maven as maven_adapter,
    nsis as nsis_adapter,
    ocamllex as ocamllex_adapter,
    ocamlyacc as ocamlyacc_adapter,
    opencl as opencl_adapter,
    openedge as openedge_adapter,
    pawn as pawn_adapter,
    pony as pony_adapter,
    postscript as postscript_adapter,
    purebasic as purebasic_adapter,
    q as q_adapter,
    qsharp as qsharp_adapter,
    circom as circom_adapter,
    dafny as dafny_adapter,
    rebol as rebol_adapter,
    apl as apl_adapter,
    hoon as hoon_adapter,
    mercury as mercury_adapter,
    nginx as nginx_adapter,
    red as red_adapter,
    sass as sass_adapter,
    sed as sed_adapter,
    smali as smali_adapter,
    sml as sml_adapter,
    templ as templ_adapter,
    thrift as thrift_adapter,
    vcl as vcl_adapter,
    xquery as xquery_adapter,
    xtend as xtend_adapter,
    xslt as xslt_adapter,
    yacc as yacc_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import jinja as jinja_adapter, liquid as liquid_adapter, handlebars as handlebars_adapter, mustache as mustache_adapter, nunjucks as nunjucks_adapter, twig as twig_adapter, haml as haml_adapter, slim as slim_adapter, erb as erb_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import hlsl as hlsl_adapter, wgsl as wgsl_adapter, shaderlab as shaderlab_adapter, cython as cython_adapter, stan as stan_adapter, protobuf as protobuf_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import asciidoc as asciidoc_adapter, org as org_adapter, rst as rst_adapter, tex as tex_adapter, typst as typst_adapter, cmake as cmake_adapter, meson as meson_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import qmake as qmake_adapter
from apps.api_server.services.repository_intelligence_adapters import qml as qml_adapter
from apps.api_server.services.repository_intelligence_adapters import vue as vue_adapter
from apps.api_server.services.repository_intelligence_adapters import makefile as makefile_adapter
from apps.api_server.services.repository_intelligence_adapters import odin as odin_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    chapel as chapel_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import coq as coq_adapter
from apps.api_server.services.repository_intelligence_adapters import lean as lean_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    c_family as c_family_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    clojure as clojure_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    csharp as csharp_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    dhall as dhall_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    eiffel as eiffel_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    cue as cue_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    factor as factor_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    glsl as glsl_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    dart_language as dart_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    elixir as elixir_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    erlang as erlang_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    go_language as go_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    hack as hack_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    haskell as haskell_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    hcl as hcl_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    idris as idris_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    js_like as js_like_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    julia as julia_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    logtalk as logtalk_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import jvm as jvm_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    lua as lua_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    luau as luau_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    mojo_language as mojo_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    nim as nim_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ocaml as ocaml_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    perl as perl_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    php as php_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    rego as rego_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    powershell as powershell_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    puppet as puppet_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    yara as yara_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ruby as ruby_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    rust_language as rust_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    shell as shell_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    swift as swift_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    tlaplus as tlaplus_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    zig as zig_adapter,
)


def _prefixed_exports(
    prefix: str, module: ModuleType, *attribute_names: str
) -> dict[str, object]:
    return {
        f"{prefix}{attribute_name}": getattr(module, attribute_name)
        for attribute_name in attribute_names
    }
