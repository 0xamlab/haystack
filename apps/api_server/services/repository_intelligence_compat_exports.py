# ruff: noqa: I001, F401
from __future__ import annotations

from typing import Any

from apps.api_server.services.repository_intelligence_compat_exports_modules import (
    _prefixed_exports,
    repository_adapter_parser_dispatch, repository_bicep_parser_dispatch, repository_cache, repository_chapel_parser_dispatch, repository_config, repository_contracts,
    repository_coq_parser_dispatch, repository_cue_parser_dispatch, repository_decision_plan_workflow, repository_factor_parser_dispatch, repository_file_selection, repository_glsl_parser_dispatch,
    repository_graph, repository_hcl_parser_dispatch, repository_idris_parser_dispatch, repository_indexing, repository_intelligence_al_parser_dispatch, repository_intelligence_astro_parser_dispatch,
    repository_intelligence_ballerina_parser_dispatch, repository_intelligence_circom_parser_dispatch, repository_intelligence_clojurescript_parser_dispatch, repository_intelligence_dafny_parser_dispatch, repository_intelligence_dockerfile_parser_dispatch, repository_intelligence_ejs_parser_dispatch,
    repository_intelligence_fennel_parser_dispatch, repository_intelligence_groovy_parser_dispatch, repository_intelligence_handlebars_parser_dispatch, repository_intelligence_hlsl_parser_dispatch, repository_intelligence_hy_parser_dispatch, repository_intelligence_jinja_parser_dispatch,
    repository_intelligence_less_parser_dispatch, repository_intelligence_liquid_parser_dispatch, repository_intelligence_moonbit_parser_dispatch, repository_intelligence_mustache_parser_dispatch, repository_intelligence_nextflow_parser_dispatch, repository_intelligence_nunjucks_parser_dispatch,
    repository_intelligence_opencl_parser_dispatch, repository_intelligence_protobuf_parser_dispatch, repository_intelligence_pug_parser_dispatch, repository_intelligence_qsharp_parser_dispatch, repository_intelligence_sass_parser_dispatch, repository_intelligence_scss_parser_dispatch,
    repository_intelligence_shaderlab_parser_dispatch, repository_intelligence_sml_parser_dispatch, repository_intelligence_stylus_parser_dispatch, repository_intelligence_svelte_parser_dispatch, repository_intelligence_tex_parser_dispatch, repository_intelligence_typst_parser_dispatch,
    repository_intelligence_vyper_parser_dispatch, repository_intelligence_wgsl_parser_dispatch, repository_intelligence_wren_parser_dispatch, repository_inventory, repository_janet_parser_dispatch, repository_js_resolution,
    repository_language_resolution, repository_lean_parser_dispatch, repository_logtalk_parser_dispatch, repository_module_aliases, repository_native_dispatch, repository_native_resolution,
    repository_odin_parser_dispatch, repository_pascal_solidity_dispatch, repository_patch_analysis, repository_planner_generation, repository_rego_parser_dispatch, repository_repository_source,
    repository_robotframework_parser_dispatch, repository_runtime, repository_shared, repository_simple_parser_dispatch, repository_snapshot_workflow, repository_storage,
    repository_tlaplus_parser_dispatch, repository_verilog_parser_dispatch, repository_vue_parser_dispatch, repository_yara_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_compat_exports_renamed import (
    _RENAMED_EXPORTS,
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
    repository_intelligence_circom_parser_dispatch,
    repository_intelligence_dafny_parser_dispatch,
    repository_intelligence_opencl_parser_dispatch,
    repository_intelligence_ballerina_parser_dispatch,
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
