"""Imports re-exported to test_repository_intelligence_service_* sub-modules.

Extracted from tests/test_repository_intelligence_service.py during modularization.
Each split sub-file does `from tests._repository_intelligence_service_imports import *`.
"""
# ruff: noqa: F401

from __future__ import annotations
import difflib
import hashlib
import json
import subprocess
import time
import uuid
import zipfile
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import pytest
from apps.api_server.schemas.repositories import (
    RepositoryApplyMode,
    RepositoryApplyRequest,
    RepositoryDecisionPlanCreateRequest,
    RepositorySimulationRequest,
    RepositorySnapshotCreateRequest,
    RepositoryTriageRequest,
)
from apps.api_server.schemas.response import (
    DecisionEnvelope,
    MetricsSummary,
    PercentileSummary,
    RunMetadata,
)
from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_adapter_parser_dispatch as repository_adapter_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_agda_parser_dispatch as repository_agda_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_bicep_parser_dispatch as repository_bicep_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_batchfile_parser_dispatch as repository_batchfile_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_makefile_parser_dispatch as repository_makefile_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_factor_parser_dispatch as repository_factor_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_cue_parser_dispatch as repository_cue_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_odin_parser_dispatch as repository_odin_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_chapel_parser_dispatch as repository_chapel_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_dhall_parser_dispatch as repository_dhall_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_eiffel_parser_dispatch as repository_eiffel_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_cache as repository_cache,
)
from apps.api_server.services import (
    repository_intelligence_cfml_parser_dispatch as repository_cfml_parser_dispatch,
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
    repository_intelligence_execution_workflow as repository_execution_workflow,
)
from apps.api_server.services import (
    repository_intelligence_file_selection as repository_file_selection,
)
from apps.api_server.services import (
    repository_intelligence_fish_parser_dispatch as repository_fish_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_coq_parser_dispatch as repository_coq_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_lean_parser_dispatch as repository_lean_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_glsl_parser_dispatch as repository_glsl_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_hlsl_parser_dispatch as repository_hlsl_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_shaderlab_parser_dispatch as repository_shaderlab_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_robotframework_parser_dispatch as repository_robotframework_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_scss_parser_dispatch as repository_scss_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_typst_parser_dispatch as repository_typst_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_dockerfile_parser_dispatch as repository_dockerfile_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_hack_parser_dispatch as repository_hack_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_hcl_parser_dispatch as repository_hcl_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_idris_parser_dispatch as repository_idris_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_graph as repository_graph,
)
from apps.api_server.services import (
    repository_intelligence_graph_workflow as repository_graph_workflow,
)
from apps.api_server.services import (
    repository_intelligence_indexing as repository_indexing,
)
from apps.api_server.services import (
    repository_intelligence_inventory as repository_inventory,
)
from apps.api_server.services import (
    repository_intelligence_janet_parser_dispatch as repository_janet_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_logtalk_parser_dispatch as repository_logtalk_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_luau_parser_dispatch as repository_luau_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_puppet_parser_dispatch as repository_puppet_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_tlaplus_parser_dispatch as repository_tlaplus_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_rego_parser_dispatch as repository_rego_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_yara_parser_dispatch as repository_yara_parser_dispatch,
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
    repository_intelligence_package_symbol_resolution as repository_package_symbol_resolution,
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
    repository_intelligence_raku_parser_dispatch as repository_raku_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_repository_source as repository_repository_source,
)
from apps.api_server.services import (
    repository_intelligence_root_scoped_aliases as repository_root_scoped_aliases,
)
from apps.api_server.services import (
    repository_intelligence_runtime as repository_runtime,
)
from apps.api_server.services import (
    repository_intelligence_scripting_parser_dispatch as repository_scripting_parser_dispatch,
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
    repository_intelligence_typed_parser_dispatch as repository_typed_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_verilog_parser_dispatch as repository_verilog_parser_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_xpp_parser_dispatch as repository_xpp_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    abap_analysis_support as repository_abap_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    abap_primitives as repository_abap_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    actionscript_analysis_support as repository_actionscript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    actionscript_primitives as repository_actionscript_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    agda_analysis_support as repository_agda_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    agda_primitives as repository_agda_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    applescript_analysis_support as repository_applescript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    bicep_analysis_support as repository_bicep_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    applescript_primitives as repository_applescript_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    bicep_primitives as repository_bicep_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    batchfile_analysis_support as repository_batchfile_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    batchfile_primitives as repository_batchfile_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    bitbake_analysis_support as repository_bitbake_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    bitbake_primitives as repository_bitbake_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    cue_analysis_support as repository_cue_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    cmake_analysis_support as repository_cmake_analysis_support,
    cuda_analysis_support as repository_cuda_analysis_support,
    cython_analysis_support as repository_cython_analysis_support,
    dockerfile_analysis_support as repository_dockerfile_analysis_support,
    hlsl_analysis_support as repository_hlsl_analysis_support,
    just_analysis_support as repository_just_analysis_support,
    meson_analysis_support as repository_meson_analysis_support,
    qmake_analysis_support as repository_qmake_analysis_support,
    qml_analysis_support as repository_qml_analysis_support,
    robotframework_analysis_support as repository_robotframework_analysis_support,
    scss_analysis_support as repository_scss_analysis_support,
    shaderlab_analysis_support as repository_shaderlab_analysis_support,
    stan_analysis_support as repository_stan_analysis_support,
    typst_analysis_support as repository_typst_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    cue_primitives as repository_cue_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    cmake_primitives as repository_cmake_primitives,
    cuda_primitives as repository_cuda_primitives,
    cython_primitives as repository_cython_primitives,
    dockerfile_primitives as repository_dockerfile_primitives,
    hlsl_primitives as repository_hlsl_primitives,
    just_primitives as repository_just_primitives,
    meson_primitives as repository_meson_primitives,
    qmake_primitives as repository_qmake_primitives,
    qml_primitives as repository_qml_primitives,
    robotframework_primitives as repository_robotframework_primitives,
    scss_primitives as repository_scss_primitives,
    shaderlab_primitives as repository_shaderlab_primitives,
    stan_primitives as repository_stan_primitives,
    typst_primitives as repository_typst_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    factor_analysis_support as repository_factor_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    factor_primitives as repository_factor_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    makefile_analysis_support as repository_makefile_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    makefile_primitives as repository_makefile_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    odin_analysis_support as repository_odin_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    odin_primitives as repository_odin_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    autohotkey_analysis_support as repository_autohotkey_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    autohotkey_primitives as repository_autohotkey_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    autoit_analysis_support as repository_autoit_analysis_support,
    squirrel_analysis_support as repository_squirrel_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    autoit_primitives as repository_autoit_primitives,
    squirrel_primitives as repository_squirrel_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    awk_analysis_support as repository_awk_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    awk_primitives as repository_awk_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    cfml_analysis_support as repository_cfml_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    cfml_primitives as repository_cfml_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    classic_visual_basic_analysis_support as repository_classic_visual_basic_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    classic_visual_basic_primitives as repository_classic_visual_basic_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    classic_visual_basic_support as repository_classic_visual_basic_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    coffeescript_analysis_support as repository_coffeescript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    coffeescript_primitives as repository_coffeescript_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    elm_analysis_support as repository_elm_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    elm_primitives as repository_elm_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    emacslisp_analysis_support as repository_emacslisp_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    emacslisp_primitives as repository_emacslisp_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    chapel_analysis_support as repository_chapel_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    chapel_primitives as repository_chapel_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    dhall_analysis_support as repository_dhall_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    dhall_primitives as repository_dhall_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    eiffel_analysis_support as repository_eiffel_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    eiffel_primitives as repository_eiffel_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    fish_analysis_support as repository_fish_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    fish_primitives as repository_fish_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gams_analysis_support as repository_gams_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gams_primitives as repository_gams_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gleam_analysis_support as repository_gleam_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gleam_primitives as repository_gleam_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    coq_analysis_support as repository_coq_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    coq_primitives as repository_coq_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    lean_analysis_support as repository_lean_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    lean_primitives as repository_lean_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    glsl_analysis_support as repository_glsl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    glsl_primitives as repository_glsl_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gml_analysis_support as repository_gml_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gml_primitives as repository_gml_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    hack_analysis_support as repository_hack_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    hack_primitives as repository_hack_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    logtalk_analysis_support as repository_logtalk_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    logtalk_primitives as repository_logtalk_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    luau_analysis_support as repository_luau_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    luau_primitives as repository_luau_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    puppet_analysis_support as repository_puppet_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    puppet_primitives as repository_puppet_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    tlaplus_analysis_support as repository_tlaplus_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    tlaplus_primitives as repository_tlaplus_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    haxe_analysis_support as repository_haxe_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    haxe_primitives as repository_haxe_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    hcl_analysis_support as repository_hcl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    hcl_primitives as repository_hcl_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    idris_analysis_support as repository_idris_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    idris_primitives as repository_idris_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    janet_analysis_support as repository_janet_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    janet_primitives as repository_janet_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    rego_analysis_support as repository_rego_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    rego_primitives as repository_rego_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    yara_analysis_support as repository_yara_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    yara_primitives as repository_yara_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    lisp_analysis_support as repository_lisp_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    lisp_support as repository_lisp_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    mql5_analysis_support as repository_mql5_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    mql5_primitives as repository_mql5_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    nix_analysis_support as repository_nix_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    nix_primitives as repository_nix_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    nushell_analysis_support as repository_nushell_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    nushell_primitives as repository_nushell_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    objective_c_analysis_support as repository_objective_c_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    objective_c_primitives as repository_objective_c_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    openscad_analysis_support as repository_openscad_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    openscad_primitives as repository_openscad_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    php_analysis_support as repository_php_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    php_primitives as repository_php_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    prolog_analysis_support as repository_prolog_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    prolog_primitives as repository_prolog_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    prolog_support as repository_prolog_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    purescript_analysis_support as repository_purescript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    purescript_primitives as repository_purescript_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    racket_analysis_support as repository_racket_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    racket_primitives as repository_racket_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    raku_analysis_support as repository_raku_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    raku_primitives as repository_raku_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    rpg_support as repository_rpg_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    scheme_analysis_support as repository_scheme_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    scheme_primitives as repository_scheme_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    scratch_analysis_support as repository_scratch_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    scratch_primitives as repository_scratch_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    smalltalk_analysis_support as repository_smalltalk_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    smalltalk_primitives as repository_smalltalk_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    solidity_support as repository_solidity_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    starlark_analysis_support as repository_starlark_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    starlark_primitives as repository_starlark_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    systemverilog_analysis_support as repository_systemverilog_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    systemverilog_primitives as repository_systemverilog_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    systemverilog_support as repository_systemverilog_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    tcl_analysis_support as repository_tcl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    tcl_primitives as repository_tcl_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vala_analysis_support as repository_vala_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vala_primitives as repository_vala_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vbscript_analysis_support as repository_vbscript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vbscript_primitives as repository_vbscript_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    verilog_analysis_support as repository_verilog_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    verilog_primitives as repository_verilog_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    verilog_support as repository_verilog_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vhdl_analysis_support as repository_vhdl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vhdl_primitives as repository_vhdl_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vimscript_analysis_support as repository_vimscript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vimscript_primitives as repository_vimscript_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vlang_analysis_support as repository_vlang_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vlang_primitives as repository_vlang_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    wolfram_support as repository_wolfram_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    xpp_analysis_support as repository_xpp_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    xpp_primitives as repository_xpp_primitives,
)

__all__ = [
    "annotations",
    "difflib",
    "hashlib",
    "json",
    "subprocess",
    "time",
    "uuid",
    "zipfile",
    "Sequence",
    "Path",
    "SimpleNamespace",
    "Any",
    "pytest",
    "RepositoryApplyMode",
    "RepositoryApplyRequest",
    "RepositoryDecisionPlanCreateRequest",
    "RepositorySimulationRequest",
    "RepositorySnapshotCreateRequest",
    "RepositoryTriageRequest",
    "DecisionEnvelope",
    "MetricsSummary",
    "PercentileSummary",
    "RunMetadata",
    "repository_service",
    "repository_adapter_parser_dispatch",
    "repository_agda_parser_dispatch",
    "repository_bicep_parser_dispatch",
    "repository_batchfile_parser_dispatch",
    "repository_makefile_parser_dispatch",
    "repository_factor_parser_dispatch",
    "repository_cue_parser_dispatch",
    "repository_odin_parser_dispatch",
    "repository_chapel_parser_dispatch",
    "repository_dhall_parser_dispatch",
    "repository_eiffel_parser_dispatch",
    "repository_cache",
    "repository_cfml_parser_dispatch",
    "repository_config",
    "repository_contracts",
    "repository_decision_plan_workflow",
    "repository_execution_workflow",
    "repository_file_selection",
    "repository_fish_parser_dispatch",
    "repository_coq_parser_dispatch",
    "repository_lean_parser_dispatch",
    "repository_glsl_parser_dispatch",
    "repository_hlsl_parser_dispatch",
    "repository_shaderlab_parser_dispatch",
    "repository_robotframework_parser_dispatch",
    "repository_scss_parser_dispatch",
    "repository_typst_parser_dispatch",
    "repository_dockerfile_parser_dispatch",
    "repository_hack_parser_dispatch",
    "repository_hcl_parser_dispatch",
    "repository_idris_parser_dispatch",
    "repository_graph",
    "repository_graph_workflow",
    "repository_indexing",
    "repository_inventory",
    "repository_janet_parser_dispatch",
    "repository_logtalk_parser_dispatch",
    "repository_luau_parser_dispatch",
    "repository_puppet_parser_dispatch",
    "repository_tlaplus_parser_dispatch",
    "repository_rego_parser_dispatch",
    "repository_yara_parser_dispatch",
    "repository_js_resolution",
    "repository_language_resolution",
    "repository_module_aliases",
    "repository_native_dispatch",
    "repository_native_resolution",
    "repository_package_symbol_resolution",
    "repository_pascal_solidity_dispatch",
    "repository_patch_analysis",
    "repository_planner_generation",
    "repository_raku_parser_dispatch",
    "repository_repository_source",
    "repository_root_scoped_aliases",
    "repository_runtime",
    "repository_scripting_parser_dispatch",
    "repository_shared",
    "repository_simple_parser_dispatch",
    "repository_snapshot_workflow",
    "repository_storage",
    "repository_typed_parser_dispatch",
    "repository_verilog_parser_dispatch",
    "repository_xpp_parser_dispatch",
    "initialize_pyarrow_parquet_runtime",
    "repository_abap_analysis_support",
    "repository_abap_primitives",
    "repository_actionscript_analysis_support",
    "repository_actionscript_primitives",
    "repository_agda_analysis_support",
    "repository_agda_primitives",
    "repository_applescript_analysis_support",
    "repository_bicep_analysis_support",
    "repository_applescript_primitives",
    "repository_bicep_primitives",
    "repository_batchfile_analysis_support",
    "repository_batchfile_primitives",
    "repository_bitbake_analysis_support",
    "repository_bitbake_primitives",
    "repository_cue_analysis_support",
    "repository_cmake_analysis_support",
    "repository_cuda_analysis_support",
    "repository_cython_analysis_support",
    "repository_dockerfile_analysis_support",
    "repository_hlsl_analysis_support",
    "repository_just_analysis_support",
    "repository_meson_analysis_support",
    "repository_qmake_analysis_support",
    "repository_qml_analysis_support",
    "repository_robotframework_analysis_support",
    "repository_scss_analysis_support",
    "repository_shaderlab_analysis_support",
    "repository_stan_analysis_support",
    "repository_typst_analysis_support",
    "repository_cue_primitives",
    "repository_cmake_primitives",
    "repository_cuda_primitives",
    "repository_cython_primitives",
    "repository_dockerfile_primitives",
    "repository_hlsl_primitives",
    "repository_just_primitives",
    "repository_meson_primitives",
    "repository_qmake_primitives",
    "repository_qml_primitives",
    "repository_robotframework_primitives",
    "repository_scss_primitives",
    "repository_shaderlab_primitives",
    "repository_stan_primitives",
    "repository_typst_primitives",
    "repository_factor_analysis_support",
    "repository_factor_primitives",
    "repository_makefile_analysis_support",
    "repository_makefile_primitives",
    "repository_odin_analysis_support",
    "repository_odin_primitives",
    "repository_autohotkey_analysis_support",
    "repository_autohotkey_primitives",
    "repository_autoit_analysis_support",
    "repository_squirrel_analysis_support",
    "repository_autoit_primitives",
    "repository_squirrel_primitives",
    "repository_awk_analysis_support",
    "repository_awk_primitives",
    "repository_cfml_analysis_support",
    "repository_cfml_primitives",
    "repository_classic_visual_basic_analysis_support",
    "repository_classic_visual_basic_primitives",
    "repository_classic_visual_basic_support",
    "repository_coffeescript_analysis_support",
    "repository_coffeescript_primitives",
    "repository_elm_analysis_support",
    "repository_elm_primitives",
    "repository_emacslisp_analysis_support",
    "repository_emacslisp_primitives",
    "repository_chapel_analysis_support",
    "repository_chapel_primitives",
    "repository_dhall_analysis_support",
    "repository_dhall_primitives",
    "repository_eiffel_analysis_support",
    "repository_eiffel_primitives",
    "repository_fish_analysis_support",
    "repository_fish_primitives",
    "repository_gams_analysis_support",
    "repository_gams_primitives",
    "repository_gleam_analysis_support",
    "repository_gleam_primitives",
    "repository_coq_analysis_support",
    "repository_coq_primitives",
    "repository_lean_analysis_support",
    "repository_lean_primitives",
    "repository_glsl_analysis_support",
    "repository_glsl_primitives",
    "repository_gml_analysis_support",
    "repository_gml_primitives",
    "repository_hack_analysis_support",
    "repository_hack_primitives",
    "repository_logtalk_analysis_support",
    "repository_logtalk_primitives",
    "repository_luau_analysis_support",
    "repository_luau_primitives",
    "repository_puppet_analysis_support",
    "repository_puppet_primitives",
    "repository_tlaplus_analysis_support",
    "repository_tlaplus_primitives",
    "repository_haxe_analysis_support",
    "repository_haxe_primitives",
    "repository_hcl_analysis_support",
    "repository_hcl_primitives",
    "repository_idris_analysis_support",
    "repository_idris_primitives",
    "repository_janet_analysis_support",
    "repository_janet_primitives",
    "repository_rego_analysis_support",
    "repository_rego_primitives",
    "repository_yara_analysis_support",
    "repository_yara_primitives",
    "repository_lisp_analysis_support",
    "repository_lisp_support",
    "repository_mql5_analysis_support",
    "repository_mql5_primitives",
    "repository_nix_analysis_support",
    "repository_nix_primitives",
    "repository_nushell_analysis_support",
    "repository_nushell_primitives",
    "repository_objective_c_analysis_support",
    "repository_objective_c_primitives",
    "repository_openscad_analysis_support",
    "repository_openscad_primitives",
    "repository_php_analysis_support",
    "repository_php_primitives",
    "repository_prolog_analysis_support",
    "repository_prolog_primitives",
    "repository_prolog_support",
    "repository_purescript_analysis_support",
    "repository_purescript_primitives",
    "repository_racket_analysis_support",
    "repository_racket_primitives",
    "repository_raku_analysis_support",
    "repository_raku_primitives",
    "repository_rpg_support",
    "repository_scheme_analysis_support",
    "repository_scheme_primitives",
    "repository_scratch_analysis_support",
    "repository_scratch_primitives",
    "repository_smalltalk_analysis_support",
    "repository_smalltalk_primitives",
    "repository_solidity_support",
    "repository_starlark_analysis_support",
    "repository_starlark_primitives",
    "repository_systemverilog_analysis_support",
    "repository_systemverilog_primitives",
    "repository_systemverilog_support",
    "repository_tcl_analysis_support",
    "repository_tcl_primitives",
    "repository_vala_analysis_support",
    "repository_vala_primitives",
    "repository_vbscript_analysis_support",
    "repository_vbscript_primitives",
    "repository_verilog_analysis_support",
    "repository_verilog_primitives",
    "repository_verilog_support",
    "repository_vhdl_analysis_support",
    "repository_vhdl_primitives",
    "repository_vimscript_analysis_support",
    "repository_vimscript_primitives",
    "repository_vlang_analysis_support",
    "repository_vlang_primitives",
    "repository_wolfram_support",
    "repository_xpp_analysis_support",
    "repository_xpp_primitives",
]
