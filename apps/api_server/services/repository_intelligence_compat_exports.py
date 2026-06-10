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
    repository_intelligence_modelica_parser_dispatch as repository_intelligence_modelica_parser_dispatch,
    repository_intelligence_move_parser_dispatch as repository_intelligence_move_parser_dispatch,
    repository_intelligence_openqasm_parser_dispatch as repository_intelligence_openqasm_parser_dispatch,
    repository_intelligence_plantuml_parser_dispatch as repository_intelligence_plantuml_parser_dispatch,
    repository_intelligence_rescript_parser_dispatch as repository_intelligence_rescript_parser_dispatch,
    repository_intelligence_roc_parser_dispatch as repository_intelligence_roc_parser_dispatch,
    repository_intelligence_smarty_parser_dispatch as repository_intelligence_smarty_parser_dispatch,
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
    repository_intelligence_clojurescript_parser_dispatch as repository_intelligence_clojurescript_parser_dispatch,
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
from apps.api_server.services.repository_intelligence_adapters import antlr as antlr_adapter, astro as astro_adapter, svelte as svelte_adapter, pug as pug_adapter, dm as dm_adapter, ejs as ejs_adapter, blade as blade_adapter, fennel as fennel_adapter, gherkin as gherkin_adapter, graphviz as graphviz_adapter, hy as hy_adapter, mermaid as mermaid_adapter, modelica as modelica_adapter, moonbit as moonbit_adapter, move as move_adapter, nextflow as nextflow_adapter, openqasm as openqasm_adapter, plantuml as plantuml_adapter, rescript as rescript_adapter, roc as roc_adapter, smarty as smarty_adapter, wren as wren_adapter, vyper as vyper_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import (
    al as al_adapter,
    clojurescript as clojurescript_adapter,
    groovy as groovy_adapter,
    opencl as opencl_adapter,
    qsharp as qsharp_adapter,
    sass as sass_adapter,
    sml as sml_adapter,
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


_RENAMED_EXPORTS: dict[str, object] = {
    "_TEXT_FILE_SUFFIXES": repository_file_selection.TEXT_FILE_SUFFIXES,
    "_TEXT_FILE_BASENAMES": repository_file_selection.TEXT_FILE_BASENAMES,
    "actionscript_adapter": actionscript_adapter,
    "applescript_adapter": applescript_adapter,
    "autoit_adapter": autoit_adapter,
    "squirrel_adapter": squirrel_adapter,
    "batchfile_adapter": batchfile_adapter,
    "bitbake_adapter": bitbake_adapter,
    "just_adapter": just_adapter,
    "dockerfile_adapter": dockerfile_adapter,
    "cuda_adapter": cuda_adapter,
    "robotframework_adapter": robotframework_adapter,
    "gherkin_adapter": gherkin_adapter,
    "antlr_adapter": antlr_adapter,
    "graphviz_adapter": graphviz_adapter,
    "mermaid_adapter": mermaid_adapter,
    "plantuml_adapter": plantuml_adapter,
    "openqasm_adapter": openqasm_adapter,
    "move_adapter": move_adapter, "dm_adapter": dm_adapter,
    "hy_adapter": hy_adapter, "wren_adapter": wren_adapter, "fennel_adapter": fennel_adapter, "vyper_adapter": vyper_adapter, "nextflow_adapter": nextflow_adapter, "moonbit_adapter": moonbit_adapter,
    "modelica_adapter": modelica_adapter,
    "rescript_adapter": rescript_adapter,
    "roc_adapter": roc_adapter,
    "smarty_adapter": smarty_adapter,
    "scss_adapter": scss_adapter,
    "less_adapter": less_adapter,
    "stylus_adapter": stylus_adapter,
    "astro_adapter": astro_adapter,
    "svelte_adapter": svelte_adapter,
    "jinja_adapter": jinja_adapter,
    "liquid_adapter": liquid_adapter,
    "handlebars_adapter": handlebars_adapter,
    "mustache_adapter": mustache_adapter,
    "nunjucks_adapter": nunjucks_adapter,
    "twig_adapter": twig_adapter,
    "haml_adapter": haml_adapter,
    "slim_adapter": slim_adapter,
    "erb_adapter": erb_adapter,
    "rst_adapter": rst_adapter, "asciidoc_adapter": asciidoc_adapter, "org_adapter": org_adapter,
    "pug_adapter": pug_adapter,
    "ejs_adapter": ejs_adapter,
    "blade_adapter": blade_adapter,
    "hlsl_adapter": hlsl_adapter,
    "wgsl_adapter": wgsl_adapter,
    "shaderlab_adapter": shaderlab_adapter,
    "cython_adapter": cython_adapter,
    "stan_adapter": stan_adapter,
    "protobuf_adapter": protobuf_adapter,
    "tex_adapter": tex_adapter,
    "typst_adapter": typst_adapter,
    "makefile_adapter": makefile_adapter,
    "cmake_adapter": cmake_adapter,
    "meson_adapter": meson_adapter,
    "qmake_adapter": qmake_adapter,
    "qml_adapter": qml_adapter,
    "vue_adapter": vue_adapter,
    "odin_adapter": odin_adapter,
    "factor_adapter": factor_adapter,
    "cue_adapter": cue_adapter,
    "bicep_adapter": bicep_adapter,
    "chapel_adapter": chapel_adapter,
    "coq_adapter": coq_adapter,
    "lean_adapter": lean_adapter,
    "dhall_adapter": dhall_adapter,
    "eiffel_adapter": eiffel_adapter,
    "glsl_adapter": glsl_adapter,
    "hack_adapter": hack_adapter,
    "hcl_adapter": hcl_adapter,
    "idris_adapter": idris_adapter,
    "logtalk_adapter": logtalk_adapter,
    "luau_adapter": luau_adapter,
    "puppet_adapter": puppet_adapter,
    "_parse_lua_dependencies_only": repository_luau_parser_dispatch._parse_lua_dependencies_only,
    "_parse_lua_file": repository_luau_parser_dispatch._parse_lua_file,
    "_parse_luau_dependencies_only": repository_luau_parser_dispatch._parse_luau_dependencies_only,
    "_parse_luau_file": repository_luau_parser_dispatch._parse_luau_file,
    "_parse_coq_dependencies_only": repository_coq_parser_dispatch._parse_coq_dependencies_only,
    "_parse_coq_file": repository_coq_parser_dispatch._parse_coq_file,
    "_parse_lean_dependencies_only": repository_lean_parser_dispatch._parse_lean_dependencies_only,
    "_parse_lean_file": repository_lean_parser_dispatch._parse_lean_file,
    "_parse_dhall_dependencies_only": (
        repository_dhall_parser_dispatch._parse_dhall_dependencies_only
    ),
    "_parse_dhall_file": repository_dhall_parser_dispatch._parse_dhall_file,
    "_parse_batchfile_dependencies_only": (
        repository_batchfile_parser_dispatch._parse_batchfile_dependencies_only
    ),
    "_parse_batchfile_file": repository_batchfile_parser_dispatch._parse_batchfile_file,
    "_parse_autoit_dependencies_only": (
        repository_autoit_parser_dispatch._parse_autoit_dependencies_only
    ),
    "_parse_autoit_file": repository_autoit_parser_dispatch._parse_autoit_file,
    "_parse_squirrel_dependencies_only": (
        repository_squirrel_parser_dispatch._parse_squirrel_dependencies_only
    ),
    "_parse_squirrel_file": repository_squirrel_parser_dispatch._parse_squirrel_file,
    "_parse_makefile_dependencies_only": (
        repository_makefile_parser_dispatch._parse_makefile_dependencies_only
    ),
    "_parse_makefile_file": repository_makefile_parser_dispatch._parse_makefile_file,
    "_parse_just_dependencies_only": repository_just_parser_dispatch._parse_just_dependencies_only,
    "_parse_just_file": repository_just_parser_dispatch._parse_just_file,
    "_parse_dockerfile_dependencies_only": repository_intelligence_dockerfile_parser_dispatch._parse_dockerfile_dependencies_only,
    "_parse_dockerfile_file": repository_intelligence_dockerfile_parser_dispatch._parse_dockerfile_file,
    "_parse_cuda_dependencies_only": repository_intelligence_cuda_parser_dispatch._parse_cuda_dependencies_only,
    "_parse_cuda_file": repository_intelligence_cuda_parser_dispatch._parse_cuda_file,
    "_parse_hlsl_dependencies_only": repository_intelligence_hlsl_parser_dispatch._parse_hlsl_dependencies_only,
    "_parse_hlsl_file": repository_intelligence_hlsl_parser_dispatch._parse_hlsl_file,
    "_parse_wgsl_dependencies_only": repository_intelligence_wgsl_parser_dispatch._parse_wgsl_dependencies_only,
    "_parse_wgsl_file": repository_intelligence_wgsl_parser_dispatch._parse_wgsl_file,
    "_parse_shaderlab_dependencies_only": repository_intelligence_shaderlab_parser_dispatch._parse_shaderlab_dependencies_only,
    "_parse_shaderlab_file": repository_intelligence_shaderlab_parser_dispatch._parse_shaderlab_file,
    "_parse_robotframework_dependencies_only": repository_robotframework_parser_dispatch._parse_robotframework_dependencies_only,
    "_parse_robotframework_file": repository_robotframework_parser_dispatch._parse_robotframework_file,
    "_parse_gherkin_dependencies_only": repository_intelligence_gherkin_parser_dispatch._parse_gherkin_dependencies_only,
    "_parse_gherkin_file": repository_intelligence_gherkin_parser_dispatch._parse_gherkin_file,
    "_parse_antlr_dependencies_only": repository_intelligence_antlr_parser_dispatch._parse_antlr_dependencies_only,
    "_parse_antlr_file": repository_intelligence_antlr_parser_dispatch._parse_antlr_file,
    "_parse_graphviz_dependencies_only": repository_intelligence_graphviz_parser_dispatch._parse_graphviz_dependencies_only,
    "_parse_graphviz_file": repository_intelligence_graphviz_parser_dispatch._parse_graphviz_file,
    "_parse_mermaid_dependencies_only": repository_intelligence_mermaid_parser_dispatch._parse_mermaid_dependencies_only,
    "_parse_mermaid_file": repository_intelligence_mermaid_parser_dispatch._parse_mermaid_file,
    "_parse_plantuml_dependencies_only": repository_intelligence_plantuml_parser_dispatch._parse_plantuml_dependencies_only,
    "_parse_plantuml_file": repository_intelligence_plantuml_parser_dispatch._parse_plantuml_file,
    "_parse_openqasm_dependencies_only": repository_intelligence_openqasm_parser_dispatch._parse_openqasm_dependencies_only,
    "_parse_openqasm_file": repository_intelligence_openqasm_parser_dispatch._parse_openqasm_file,
    "_parse_move_dependencies_only": repository_intelligence_move_parser_dispatch._parse_move_dependencies_only, "_parse_dm_dependencies_only": repository_intelligence_dm_parser_dispatch._parse_dm_dependencies_only,
    "_parse_move_file": repository_intelligence_move_parser_dispatch._parse_move_file, "_parse_dm_file": repository_intelligence_dm_parser_dispatch._parse_dm_file,
    "_parse_hy_dependencies_only": repository_intelligence_hy_parser_dispatch._parse_hy_dependencies_only, "_parse_wren_dependencies_only": repository_intelligence_wren_parser_dispatch._parse_wren_dependencies_only, "_parse_fennel_dependencies_only": repository_intelligence_fennel_parser_dispatch._parse_fennel_dependencies_only, "_parse_vyper_dependencies_only": repository_intelligence_vyper_parser_dispatch._parse_vyper_dependencies_only, "_parse_nextflow_dependencies_only": repository_intelligence_nextflow_parser_dispatch._parse_nextflow_dependencies_only, "_parse_moonbit_dependencies_only": repository_intelligence_moonbit_parser_dispatch._parse_moonbit_dependencies_only,
    "_parse_hy_file": repository_intelligence_hy_parser_dispatch._parse_hy_file, "_parse_wren_file": repository_intelligence_wren_parser_dispatch._parse_wren_file, "_parse_fennel_file": repository_intelligence_fennel_parser_dispatch._parse_fennel_file, "_parse_vyper_file": repository_intelligence_vyper_parser_dispatch._parse_vyper_file, "_parse_nextflow_file": repository_intelligence_nextflow_parser_dispatch._parse_nextflow_file, "_parse_moonbit_file": repository_intelligence_moonbit_parser_dispatch._parse_moonbit_file,
    "_parse_modelica_dependencies_only": repository_intelligence_modelica_parser_dispatch._parse_modelica_dependencies_only,
    "_parse_modelica_file": repository_intelligence_modelica_parser_dispatch._parse_modelica_file,
    "_parse_rescript_dependencies_only": repository_intelligence_rescript_parser_dispatch._parse_rescript_dependencies_only,
    "_parse_rescript_file": repository_intelligence_rescript_parser_dispatch._parse_rescript_file,
    "_parse_roc_dependencies_only": repository_intelligence_roc_parser_dispatch._parse_roc_dependencies_only,
    "_parse_roc_file": repository_intelligence_roc_parser_dispatch._parse_roc_file,
    "_parse_scss_dependencies_only": repository_intelligence_scss_parser_dispatch._parse_scss_dependencies_only,
    "_parse_scss_file": repository_intelligence_scss_parser_dispatch._parse_scss_file,
    "_parse_less_dependencies_only": repository_intelligence_less_parser_dispatch._parse_less_dependencies_only,
    "_parse_less_file": repository_intelligence_less_parser_dispatch._parse_less_file,
    "_parse_stylus_dependencies_only": repository_intelligence_stylus_parser_dispatch._parse_stylus_dependencies_only,
    "_parse_stylus_file": repository_intelligence_stylus_parser_dispatch._parse_stylus_file,
    "_parse_astro_dependencies_only": repository_intelligence_astro_parser_dispatch._parse_astro_dependencies_only,
    "_parse_astro_file": repository_intelligence_astro_parser_dispatch._parse_astro_file,
    "_parse_svelte_dependencies_only": repository_intelligence_svelte_parser_dispatch._parse_svelte_dependencies_only,
    "_parse_svelte_file": repository_intelligence_svelte_parser_dispatch._parse_svelte_file,
    "_parse_jinja_dependencies_only": repository_intelligence_jinja_parser_dispatch._parse_jinja_dependencies_only,
    "_parse_jinja_file": repository_intelligence_jinja_parser_dispatch._parse_jinja_file,
    "_parse_liquid_dependencies_only": repository_intelligence_liquid_parser_dispatch._parse_liquid_dependencies_only,
    "_parse_liquid_file": repository_intelligence_liquid_parser_dispatch._parse_liquid_file,
    "_parse_handlebars_dependencies_only": repository_intelligence_handlebars_parser_dispatch._parse_handlebars_dependencies_only,
    "_parse_handlebars_file": repository_intelligence_handlebars_parser_dispatch._parse_handlebars_file,
    "_parse_mustache_dependencies_only": repository_intelligence_mustache_parser_dispatch._parse_mustache_dependencies_only,
    "_parse_mustache_file": repository_intelligence_mustache_parser_dispatch._parse_mustache_file,
    "_parse_nunjucks_dependencies_only": repository_intelligence_nunjucks_parser_dispatch._parse_nunjucks_dependencies_only,
    "_parse_nunjucks_file": repository_intelligence_nunjucks_parser_dispatch._parse_nunjucks_file,
    "_parse_twig_dependencies_only": repository_intelligence_twig_parser_dispatch._parse_twig_dependencies_only,
    "_parse_twig_file": repository_intelligence_twig_parser_dispatch._parse_twig_file,
    "_parse_haml_dependencies_only": repository_intelligence_haml_parser_dispatch._parse_haml_dependencies_only,
    "_parse_haml_file": repository_intelligence_haml_parser_dispatch._parse_haml_file,
    "_parse_slim_dependencies_only": repository_intelligence_slim_parser_dispatch._parse_slim_dependencies_only,
    "_parse_slim_file": repository_intelligence_slim_parser_dispatch._parse_slim_file,
    "_parse_erb_dependencies_only": repository_intelligence_erb_parser_dispatch._parse_erb_dependencies_only,
    "_parse_erb_file": repository_intelligence_erb_parser_dispatch._parse_erb_file,
    "_parse_rst_dependencies_only": repository_intelligence_rst_parser_dispatch._parse_rst_dependencies_only,
    "_parse_rst_file": repository_intelligence_rst_parser_dispatch._parse_rst_file,
    "_parse_pug_dependencies_only": repository_intelligence_pug_parser_dispatch._parse_pug_dependencies_only,
    "_parse_pug_file": repository_intelligence_pug_parser_dispatch._parse_pug_file,
    "_parse_ejs_dependencies_only": repository_intelligence_ejs_parser_dispatch._parse_ejs_dependencies_only,
    "_parse_ejs_file": repository_intelligence_ejs_parser_dispatch._parse_ejs_file,
    "_parse_blade_dependencies_only": repository_intelligence_blade_parser_dispatch._parse_blade_dependencies_only,
    "_parse_blade_file": repository_intelligence_blade_parser_dispatch._parse_blade_file,
    "_parse_cython_dependencies_only": repository_intelligence_cython_parser_dispatch._parse_cython_dependencies_only,
    "_parse_cython_file": repository_intelligence_cython_parser_dispatch._parse_cython_file,
    "_parse_stan_dependencies_only": repository_intelligence_stan_parser_dispatch._parse_stan_dependencies_only,
    "_parse_stan_file": repository_intelligence_stan_parser_dispatch._parse_stan_file,
    "_parse_protobuf_dependencies_only": repository_intelligence_protobuf_parser_dispatch._parse_protobuf_dependencies_only,
    "_parse_protobuf_file": repository_intelligence_protobuf_parser_dispatch._parse_protobuf_file,
    "_parse_tex_dependencies_only": repository_intelligence_tex_parser_dispatch._parse_tex_dependencies_only,
    "_parse_tex_file": repository_intelligence_tex_parser_dispatch._parse_tex_file,
    "_parse_typst_dependencies_only": repository_intelligence_typst_parser_dispatch._parse_typst_dependencies_only,
    "_parse_typst_file": repository_intelligence_typst_parser_dispatch._parse_typst_file,
    "_parse_meson_dependencies_only": repository_meson_parser_dispatch._parse_meson_dependencies_only,
    "_parse_meson_file": repository_meson_parser_dispatch._parse_meson_file,
    "_parse_qmake_dependencies_only": repository_qmake_parser_dispatch._parse_qmake_dependencies_only,
    "_parse_qmake_file": repository_qmake_parser_dispatch._parse_qmake_file,
    "_parse_qml_dependencies_only": repository_qml_parser_dispatch._parse_qml_dependencies_only,
    "_parse_qml_file": repository_qml_parser_dispatch._parse_qml_file,
    "_parse_vue_dependencies_only": repository_vue_parser_dispatch._parse_vue_dependencies_only,
    "_parse_vue_file": repository_vue_parser_dispatch._parse_vue_file,
    "_parse_odin_dependencies_only": repository_odin_parser_dispatch._parse_odin_dependencies_only,
    "_parse_odin_file": repository_odin_parser_dispatch._parse_odin_file,
    "_parse_factor_dependencies_only": (
        repository_factor_parser_dispatch._parse_factor_dependencies_only
    ),
    "_parse_factor_file": repository_factor_parser_dispatch._parse_factor_file,
    "_parse_cue_dependencies_only": repository_cue_parser_dispatch._parse_cue_dependencies_only,
    "_parse_cue_file": repository_cue_parser_dispatch._parse_cue_file,
    "_parse_eiffel_dependencies_only": (
        repository_eiffel_parser_dispatch._parse_eiffel_dependencies_only
    ),
    "_parse_eiffel_file": repository_eiffel_parser_dispatch._parse_eiffel_file,
    "_parse_glsl_dependencies_only": repository_glsl_parser_dispatch._parse_glsl_dependencies_only,
    "_parse_glsl_file": repository_glsl_parser_dispatch._parse_glsl_file,
    "_parse_hack_dependencies_only": repository_hack_parser_dispatch._parse_hack_dependencies_only,
    "_parse_hack_file": repository_hack_parser_dispatch._parse_hack_file,
    "_parse_puppet_dependencies_only": (
        repository_puppet_parser_dispatch._parse_puppet_dependencies_only
    ),
    "_parse_puppet_file": repository_puppet_parser_dispatch._parse_puppet_file,
    "tlaplus_adapter": tlaplus_adapter,
    "rego_adapter": rego_adapter,
    "yara_adapter": yara_adapter,
    "_REGISTERED_ADAPTER_DEPENDENCY_PARSERS": (
        repository_adapter_parser_dispatch.REGISTERED_ADAPTER_DEPENDENCY_PARSERS
    ),
    "_REGISTERED_ADAPTER_FILE_PARSERS": (
        repository_adapter_parser_dispatch.REGISTERED_ADAPTER_FILE_PARSERS
    ),
    "_ZIG_BUILD_MODULE_RE": re.compile(
        r'addModule\(\s*"(?P<name>[^"]+)"[\s\S]{0,600}?root_source_file\s*=\s*b\.path\(\s*"(?P<path>[^"]+\.zig)"\s*\)',
        re.MULTILINE,
    ),
}
_RENAMED_EXPORTS.update(
    {
        "sass_adapter": sass_adapter,
        "qsharp_adapter": qsharp_adapter,
        "opencl_adapter": opencl_adapter,
        "clojurescript_adapter": clojurescript_adapter,
        "al_adapter": al_adapter,
        "sml_adapter": sml_adapter,
        "groovy_adapter": groovy_adapter,
        "_parse_sass_dependencies_only": repository_intelligence_sass_parser_dispatch._parse_sass_dependencies_only,
        "_parse_sass_file": repository_intelligence_sass_parser_dispatch._parse_sass_file,
        "_parse_qsharp_dependencies_only": repository_intelligence_qsharp_parser_dispatch._parse_qsharp_dependencies_only,
        "_parse_qsharp_file": repository_intelligence_qsharp_parser_dispatch._parse_qsharp_file,
        "_parse_opencl_dependencies_only": repository_intelligence_opencl_parser_dispatch._parse_opencl_dependencies_only,
        "_parse_opencl_file": repository_intelligence_opencl_parser_dispatch._parse_opencl_file,
        "_parse_clojurescript_dependencies_only": repository_intelligence_clojurescript_parser_dispatch._parse_clojurescript_dependencies_only,
        "_parse_clojurescript_file": repository_intelligence_clojurescript_parser_dispatch._parse_clojurescript_file,
        "_parse_al_dependencies_only": repository_intelligence_al_parser_dispatch._parse_al_dependencies_only,
        "_parse_al_file": repository_intelligence_al_parser_dispatch._parse_al_file,
        "_parse_sml_dependencies_only": repository_intelligence_sml_parser_dispatch._parse_sml_dependencies_only,
        "_parse_sml_file": repository_intelligence_sml_parser_dispatch._parse_sml_file,
        "_parse_groovy_dependencies_only": repository_intelligence_groovy_parser_dispatch._parse_groovy_dependencies_only,
        "_parse_groovy_file": repository_intelligence_groovy_parser_dispatch._parse_groovy_file,
    }
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_JS_",
        js_like_adapter,
        "IMPORT_RE",
        "IMPORT_STATEMENT_RE",
        "EXPORT_FROM_RE",
        "REQUIRE_ASSIGN_RE",
        "IDENTIFIER_RE",
        "SYMBOL_RE",
        "FUNCTION_DECL_RE",
        "CLASS_DECL_RE",
        "INTERFACE_DECL_RE",
        "TYPE_DECL_RE",
        "ARROW_ASSIGN_RE",
        "FUNCTION_ASSIGN_RE",
        "CLASS_ASSIGN_RE",
        "CONST_DECL_RE",
        "METHOD_DECL_RE",
        "CLASS_FIELD_ARROW_RE",
    )
)
_RENAMED_EXPORTS.update(
    {
        "_sanitize_js_like_line": js_like_adapter.sanitize_line,
        "_match_js_like_symbol": js_like_adapter.match_symbol,
        "_normalize_js_like_binding_name": js_like_adapter.normalize_binding_name,
        "_parse_js_like_named_binding": js_like_adapter.parse_named_binding,
        "_bindings_from_js_like_import_clause": js_like_adapter.bindings_from_import_clause,
        "_iter_js_like_dependency_specs": js_like_adapter.iter_dependency_specs,
        "_compile_js_like_reference_pattern": js_like_adapter.compile_reference_pattern,
        "_js_like_symbol_reference_present": js_like_adapter.symbol_reference_present,
        "_build_js_like_symbol_reference_candidates": (
            js_like_adapter.build_symbol_reference_candidates
        ),
    }
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_MOJO_",
        mojo_adapter,
        "IMPORT_RE",
        "FROM_IMPORT_RE",
        "SYMBOL_RE",
        "SELECTOR_CALL_RE",
        "CALL_RE",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_ZIG_",
        zig_adapter,
        "IMPORT_RE",
        "IMPORT_BINDING_RE",
        "TOP_LEVEL_CONST_RE",
        "TOP_LEVEL_FUNCTION_RE",
        "SELECTOR_REFERENCE_RE",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_C_FAMILY_",
        c_family_adapter,
        "INCLUDE_RE",
        "ATTRIBUTE_RE",
        "TYPE_DECL_RE",
        "FUNCTION_DECL_RE",
        "SCOPED_REFERENCE_RE",
        "CALL_RE",
        "NON_OPERATIONAL_REFERENCE_NAMES",
        "DECLARATION_PREFIX_KEYWORDS",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_RUST_",
        rust_adapter,
        "USE_RE",
        "MOD_RE",
        "SYMBOL_LINE_RE",
        "CALL_RE",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_GO_",
        go_adapter,
        "FUNC_DECL_RE",
        "TYPE_DECL_RE",
        "IMPORT_SPEC_RE",
        "PACKAGE_RE",
        "SELECTOR_CALL_RE",
        "CALL_RE",
        "BUILTIN_CALL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_DART_",
        dart_adapter,
        "IMPORT_DIRECTIVE_RE",
        "IMPORT_ALIAS_RE",
        "IMPORT_SHOW_RE",
        "TYPE_DECL_RE",
        "EXTENSION_DECL_RE",
        "TYPEDEF_DECL_RE",
        "TOP_LEVEL_FUNCTION_RE",
        "METHOD_DECL_RE",
        "SELECTOR_REFERENCE_RE",
        "RESERVED_SYMBOL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    {
        "_match_dart_symbol": dart_adapter.match_symbol,
        "_iter_dart_import_directives": dart_adapter.iter_import_directives,
    }
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_CLOJURE_",
        clojure_adapter,
        "NS_RE",
        "REQUIRE_VECTOR_RE",
        "ALIAS_RE",
        "REFER_RE",
        "DEF_DECL_RE",
        "QUALIFIED_REFERENCE_RE",
        "UNQUALIFIED_REFERENCE_RE",
        "RESERVED_SYMBOL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_HASKELL_",
        haskell_adapter,
        "MODULE_RE",
        "IMPORT_RE",
        "TYPE_DECL_RE",
        "FUNCTION_DECL_RE",
        "QUALIFIED_REFERENCE_RE",
        "TYPE_REFERENCE_RE",
        "CALL_RE",
        "RESERVED_SYMBOL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_RUBY_",
        ruby_adapter,
        "REQUIRE_RE",
        "MODULE_DECL_RE",
        "FUNCTION_DECL_RE",
        "QUALIFIED_REFERENCE_RE",
        "INCLUDE_EXTEND_RE",
        "INHERITANCE_RE",
        "CALL_RE",
        "RESERVED_SYMBOL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_LUA_",
        lua_adapter,
        "REQUIRE_RE",
        "REQUIRE_BINDING_RE",
        "FUNCTION_DECL_RE",
        "FUNCTION_ASSIGN_RE",
        "QUALIFIED_REFERENCE_RE",
        "IMPORTED_CALL_RE",
        "RESERVED_SYMBOL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_SHELL_",
        shell_adapter,
        "SOURCE_RE",
        "FUNCTION_DECL_RE",
        "COMMAND_SUBSTITUTION_RE",
        "ASSIGNMENT_PREFIX_RE",
        "COMMAND_NAME_RE",
        "SOURCE_SUFFIXES",
        "CONTROL_PREFIXES",
        "RESERVED_SYMBOL_NAMES",
        "BUILTIN_COMMAND_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_POWERSHELL_",
        powershell_adapter,
        "DOT_SOURCE_RE",
        "IMPORT_MODULE_RE",
        "USING_MODULE_RE",
        "FUNCTION_DECL_RE",
        "TYPE_DECL_RE",
        "COMMAND_NAME_RE",
        "TYPE_REFERENCE_RE",
        "SOURCE_SUFFIXES",
        "RESERVED_SYMBOL_NAMES",
        "BUILTIN_COMMAND_NAMES",
        "BUILTIN_TYPE_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_NIM_",
        nim_adapter,
        "IMPORT_LINE_RE",
        "FROM_IMPORT_RE",
        "INCLUDE_LINE_RE",
        "GROUPED_IMPORT_RE",
        "FUNCTION_DECL_RE",
        "TYPE_DECL_RE",
        "QUALIFIED_REFERENCE_RE",
        "CALL_RE",
        "RESERVED_SYMBOL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_OCAML_",
        ocaml_adapter,
        "OPEN_RE",
        "INCLUDE_RE",
        "MODULE_ALIAS_RE",
        "LET_DECL_RE",
        "TYPE_DECL_RE",
        "MODULE_DECL_RE",
        "QUALIFIED_REFERENCE_RE",
        "RESERVED_SYMBOL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_PERL_",
        perl_adapter,
        "PACKAGE_RE",
        "USE_STATEMENT_RE",
        "USE_RE",
        "REQUIRE_RE",
        "SUB_DECL_RE",
        "QUALIFIED_REFERENCE_RE",
        "CALL_RE",
        "QUOTED_ARG_RE",
        "SIMPLE_ARG_RE",
        "IGNORED_IMPORT_TARGETS",
        "RESERVED_SYMBOL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_JULIA_",
        julia_adapter,
        "PROJECT_NAME_RE",
        "MODULE_DECL_RE",
        "INCLUDE_RE",
        "IMPORT_RE",
        "FUNCTION_DECL_RE",
        "SHORT_FUNCTION_DECL_RE",
        "TYPE_DECL_RE",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_ERLANG_",
        erlang_adapter,
        "MODULE_RE",
        "INCLUDE_RE",
        "INCLUDE_LIB_RE",
        "IMPORT_RE",
        "FUNCTION_DECL_RE",
        "QUALIFIED_REFERENCE_RE",
        "RESERVED_SYMBOL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_PHP_",
        php_adapter,
        "INCLUDE_RE",
        "NAMESPACE_RE",
        "USE_RE",
        "TYPE_DECL_RE",
        "FUNCTION_DECL_RE",
        "QUALIFIED_REFERENCE_RE",
        "TYPE_REFERENCE_RE",
        "TRAIT_USE_RE",
        "DOC_TAG_RE",
        "DOC_TYPE_TOKEN_RE",
        "VARIABLE_TYPE_TOKEN_RE",
        "RESERVED_SYMBOL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_ELIXIR_",
        elixir_adapter,
        "IMPORT_RE",
        "GROUP_IMPORT_RE",
        "AS_ALIAS_RE",
        "MODULE_DECL_RE",
        "FUNCTION_DECL_RE",
        "QUALIFIED_REFERENCE_RE",
        "CALL_RE",
        "RESERVED_SYMBOL_NAMES",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_SWIFT_",
        swift_adapter,
        "IMPORT_RE",
        "TYPE_DECL_RE",
        "TYPE_REFERENCE_RE",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_CSHARP_",
        csharp_adapter,
        "USING_RE",
        "NAMESPACE_RE",
        "TYPE_DECL_RE",
        "TYPE_REFERENCE_RE",
    )
)
_RENAMED_EXPORTS.update(
    _prefixed_exports(
        "_JVM_",
        jvm_adapter,
        "PACKAGE_RE",
        "IMPORT_RE",
        "TYPE_DECL_RE",
        "TYPE_REFERENCE_RE",
    )
)
_RENAMED_EXPORTS.update(
    {
        "_SCALA_PACKAGE_OBJECT_RE": jvm_adapter.SCALA_PACKAGE_OBJECT_RE,
        "_SCALA_PACKAGE_RE": jvm_adapter.SCALA_PACKAGE_RE,
        "_SCALA_IMPORT_RE": jvm_adapter.SCALA_IMPORT_RE,
        "_SCALA_GROUPED_IMPORT_RE": jvm_adapter.SCALA_GROUPED_IMPORT_RE,
        "_SCALA_TYPE_DECL_RE": jvm_adapter.SCALA_TYPE_DECL_RE,
        "_scala_current_package": jvm_adapter.scala_current_package,
        "_iter_scala_import_targets": jvm_adapter.iter_scala_import_targets,
        "_scala_package_aliases_for_path": jvm_adapter.scala_package_aliases_for_path,
        "_jvm_declared_type_aliases_for_path": jvm_adapter.declared_type_aliases_for_path,
    }
)

_SAME_NAME_EXPORT_MODULES = (
    repository_contracts,
    repository_cache,
    repository_graph,
    repository_storage,
    repository_snapshot_workflow,
    repository_runtime,
    repository_repository_source,
    repository_file_selection,
    repository_inventory,
    repository_indexing,
    repository_bicep_parser_dispatch,
    repository_chapel_parser_dispatch,
    repository_coq_parser_dispatch,
    repository_lean_parser_dispatch,
    repository_hcl_parser_dispatch,
    repository_factor_parser_dispatch,
    repository_cue_parser_dispatch,
    repository_idris_parser_dispatch,
    repository_intelligence_hy_parser_dispatch, repository_intelligence_wren_parser_dispatch,
    repository_intelligence_fennel_parser_dispatch,
    repository_intelligence_vyper_parser_dispatch,
    repository_intelligence_sass_parser_dispatch,
    repository_intelligence_qsharp_parser_dispatch,
    repository_intelligence_opencl_parser_dispatch,
    repository_intelligence_clojurescript_parser_dispatch,
    repository_intelligence_al_parser_dispatch,
    repository_intelligence_sml_parser_dispatch,
    repository_intelligence_groovy_parser_dispatch,
    repository_intelligence_nextflow_parser_dispatch,
    repository_intelligence_moonbit_parser_dispatch,
    repository_janet_parser_dispatch,
    repository_glsl_parser_dispatch,
    repository_intelligence_hlsl_parser_dispatch,
    repository_intelligence_wgsl_parser_dispatch,
    repository_robotframework_parser_dispatch,
    repository_intelligence_scss_parser_dispatch,
    repository_intelligence_less_parser_dispatch,
    repository_intelligence_stylus_parser_dispatch,
    repository_intelligence_astro_parser_dispatch,
    repository_intelligence_svelte_parser_dispatch,
    repository_intelligence_pug_parser_dispatch,
    repository_intelligence_ejs_parser_dispatch,
    repository_intelligence_jinja_parser_dispatch,
    repository_intelligence_liquid_parser_dispatch,
    repository_intelligence_handlebars_parser_dispatch,
    repository_intelligence_mustache_parser_dispatch,
    repository_intelligence_nunjucks_parser_dispatch,
    repository_intelligence_dockerfile_parser_dispatch,
    repository_intelligence_protobuf_parser_dispatch,
    repository_intelligence_tex_parser_dispatch,
    repository_intelligence_shaderlab_parser_dispatch,
    repository_intelligence_typst_parser_dispatch,
    repository_vue_parser_dispatch,
    repository_odin_parser_dispatch,
    repository_logtalk_parser_dispatch,
    repository_rego_parser_dispatch,
    repository_tlaplus_parser_dispatch,
    repository_yara_parser_dispatch,
    repository_shared,
    repository_config,
    repository_module_aliases,
    repository_js_resolution,
    repository_language_resolution,
    repository_native_dispatch,
    repository_native_resolution,
    repository_pascal_solidity_dispatch,
    repository_patch_analysis,
    repository_planner_generation,
    repository_decision_plan_workflow,
    repository_simple_parser_dispatch,
    repository_adapter_parser_dispatch,
    repository_verilog_parser_dispatch,
)


def get_export(name: str) -> Any:
    if name in _RENAMED_EXPORTS:
        return _RENAMED_EXPORTS[name]
    if not (name.startswith("_") or name.endswith("_adapter")):
        raise AttributeError(name)
    for module in _SAME_NAME_EXPORT_MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(name)
