# ruff: noqa: I001
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


def _connector_for_repo(repo_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )


def _connector_for_archive(archive_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="repo_archive"),
        config_json=json.dumps({"path": str(archive_path)}),
    )


def _init_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Repo Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-m", "Initial commit"], check=True)


def _write_scratch_project(
    path: Path,
    payload: dict[str, Any],
    *,
    extra_assets: dict[str, bytes] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(payload, indent=2, sort_keys=True))
        for asset_path, asset_bytes in sorted((extra_assets or {}).items()):
            archive.writestr(asset_path, asset_bytes)


def _scratch_project_payload() -> dict[str, Any]:
    return {
        "extensions": [],
        "meta": {"agent": "pytest", "semver": "3.0.0", "vm": "0.2.0"},
        "monitors": [],
        "targets": [
            {
                "blocks": {
                    "stage_event": {
                        "fields": {},
                        "inputs": {},
                        "next": "stage_broadcast",
                        "opcode": "event_whenflagclicked",
                        "parent": None,
                        "topLevel": True,
                    },
                    "stage_broadcast": {
                        "fields": {},
                        "inputs": {"BROADCAST_INPUT": [1, [11, "start", "broadcast-id"]]},
                        "next": None,
                        "opcode": "event_broadcast",
                        "parent": "stage_event",
                        "topLevel": False,
                    },
                },
                "broadcasts": {"broadcast-id": "start"},
                "comments": {},
                "costumes": [],
                "currentCostume": 0,
                "isStage": True,
                "lists": {},
                "name": "Stage",
                "sounds": [],
                "tempo": 60,
                "variables": {},
                "videoState": "on",
                "videoTransparency": 50,
                "volume": 100,
            },
            {
                "blocks": {
                    "receive": {
                        "fields": {"BROADCAST_OPTION": ["start", "broadcast-id"]},
                        "inputs": {},
                        "next": "call",
                        "opcode": "event_whenbroadcastreceived",
                        "parent": None,
                        "topLevel": True,
                    },
                    "call": {
                        "fields": {},
                        "inputs": {},
                        "mutation": {
                            "argumentids": "[]",
                            "proccode": "init",
                            "warp": "false",
                        },
                        "next": None,
                        "opcode": "procedures_call",
                        "parent": "receive",
                        "topLevel": False,
                    },
                    "define": {
                        "fields": {},
                        "inputs": {"custom_block": [1, "prototype"]},
                        "next": "say",
                        "opcode": "procedures_definition",
                        "parent": None,
                        "topLevel": True,
                    },
                    "prototype": {
                        "fields": {},
                        "inputs": {},
                        "mutation": {
                            "argumentids": "[]",
                            "proccode": "init",
                            "warp": "false",
                        },
                        "next": None,
                        "opcode": "procedures_prototype",
                        "parent": "define",
                        "topLevel": False,
                    },
                    "say": {
                        "fields": {},
                        "inputs": {"MESSAGE": [1, [10, "ready"]]},
                        "next": None,
                        "opcode": "looks_say",
                        "parent": "define",
                        "topLevel": False,
                    },
                },
                "broadcasts": {},
                "comments": {},
                "costumes": [],
                "currentCostume": 0,
                "isStage": False,
                "lists": {},
                "name": "Cat",
                "size": 100,
                "sounds": [],
                "variables": {},
                "visible": True,
                "volume": 100,
                "x": 0,
                "y": 0,
            },
        ],
    }


def _sample_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "customer-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def handle_request(user):\n    return user.name\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "test_service.py").write_text(
        "from src.service import handle_request\n\n\ndef test_handle_request_user():\n    assert handle_request(type('User', (), {'name': 'Ada'})()) == 'Ada'\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    return repo_path


def _sample_archive(tmp_path: Path) -> Path:
    source_path = tmp_path / "archive-source"
    (source_path / "src").mkdir(parents=True)
    (source_path / "src" / "service.py").write_text(
        "def handle_request(user):\n    return user.name\n",
        encoding="utf-8",
    )
    archive_path = tmp_path / "customer-repo.zip"
    with zipfile.ZipFile(archive_path, "w") as handle:
        handle.write(
            source_path / "src" / "service.py",
            arcname="src/service.py",
        )
    return archive_path


def _graph_neighbor_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "graph-neighbor-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "worker.py").write_text(
        "def fragile_helper(value: str) -> str:\n"
        "    return value.strip()\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.py").write_text(
        "from src.worker import fragile_helper\n\n"
        "def orchestrate(value: str) -> str:\n"
        "    return fragile_helper(value)\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    return repo_path


def _literal_mismatch_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "literal-mismatch-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def normalize_status(status: str) -> str:\n"
        "    lowered = status.strip().lower()\n"
        '    if lowered == "open":\n'
        '        return "closed"\n'
        "    return lowered\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "test_service.py").write_text(
        "from src.service import normalize_status\n\n\n"
        "def test_normalize_status_open() -> None:\n"
        '    assert normalize_status("OPEN") == "open"\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    return repo_path


def _typescript_rootdir_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "ts-rootdir-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        '{"name":"@acme/common"}\n',
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "index.ts").write_text(
        "import { shared } from '@acme/common/shared';\n"
        "export const run = (): string => shared();\n",
        encoding="utf-8",
    )
    (repo_path / "packages" / "common" / "src" / "shared.ts").write_text(
        "export function shared(): string {\n"
        "  return 'shared';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "tsconfig.json").write_text(
        '{\n'
        '  "compilerOptions": { "outDir": "dist", "rootDir": "../.." },\n'
        '  "include": ["src"]\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "tsconfig.test.json").write_text(
        '{\n'
        '  "extends": "./tsconfig.json",\n'
        '  "compilerOptions": {\n'
        '    "noEmit": true,\n'
        '    "rootDir": ".",\n'
        '    "baseUrl": ".",\n'
        '    "paths": {\n'
        '      "@acme/common": ["../../packages/common/src/index.ts"],\n'
        '      "@acme/common/*": ["../../packages/common/src/*"]\n'
        "    }\n"
        "  },\n"
        '  "include": ["src"]\n'
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    return repo_path


def _typescript_barrel_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "ts-barrel-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    (repo_path / "src" / "app").mkdir(parents=True)
    (repo_path / "src" / "common" / "shared.ts").write_text(
        "export function usefulHelper(): string {\n"
        "  return 'ok';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "common" / "index.ts").write_text(
        "export { usefulHelper } from './shared';\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "app" / "main.ts").write_text(
        "import { usefulHelper } from '../common';\n"
        "export const run = (): string => usefulHelper();\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    return repo_path


def _decision_envelope() -> DecisionEnvelope:
    return DecisionEnvelope(
        run_id=uuid.uuid4(),
        engine_version="2026.05.0",
        recommended_action="apply_patch",
        confidence=0.91,
        rationale="Patch simulation satisfies the current execution policy.",
        metrics=MetricsSummary(
            expected_value=84.0,
            median=82.0,
            std_deviation=9.0,
            variance=81.0,
            probability_of_loss=0.08,
            var_95=12.0,
            cvar_95=15.0,
        ),
        percentiles=PercentileSummary(
            p5=-12.0,
            p25=60.0,
            p50=82.0,
            p75=95.0,
            p95=110.0,
        ),
        scenarios_run=5_000,
        execution_ms=11,
        metadata=RunMetadata(
            mode="expert",
            seed=42,
            billing_units=1,
            engine_version="2026.05.0",
        ),
    )


def test_repository_snapshot_and_triage_are_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    snapshot_repeat = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "handle_request crashes when user is null",
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 2,
                        "severity": "error",
                        "message": "AttributeError: 'NoneType' object has no attribute 'name'",
                    }
                ],
                "failing_tests": ["tests/test_service.py"],
                "changed_files": ["src/service.py"],
            },
        ),
    )

    assert snapshot.snapshot_id == snapshot_repeat.snapshot_id
    assert snapshot_repeat.status == "existing"
    assert triage.suspect_files[0] == "src/service.py"
    assert triage.workspace_evidence_bundle_ref
    assert triage.evidence_bundle_token_count > 0
    assert triage.reduction_ratio >= 1.0
    assert triage.suspect_symbols[0] == "handle_request"
    assert "handle_request" in triage.suspect_symbols
    assert triage.evidence_items[0].symbol_name == "handle_request"


def test_repository_snapshot_existing_lookup_skips_reanalysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    manifest_path = repository_service._snapshot_paths(
        str(connector.org_id),
        str(connector.id),
        snapshot.snapshot_id,
    )["manifest"]

    def _unexpected_iter_repository_files(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("snapshot fast path should reuse the persisted lookup index")

    monkeypatch.setattr(repository_service, "_iter_repository_files", _unexpected_iter_repository_files)
    original_read_json = repository_service._read_json

    def _read_json_without_snapshot_manifest(path: Path) -> dict[str, Any]:
        if Path(path) == manifest_path:
            raise AssertionError("snapshot fast path should not reopen the snapshot manifest")
        return original_read_json(path)

    monkeypatch.setattr(repository_service, "_read_json", _read_json_without_snapshot_manifest)

    snapshot_repeat = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert snapshot_repeat.snapshot_id == snapshot.snapshot_id
    assert snapshot_repeat.status == "existing"


def test_repository_snapshot_engine_revision_invalidation_rebuilds_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    baseline = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    monkeypatch.setattr(
        repository_service,
        "_REPOSITORY_INTELLIGENCE_ENGINE_REVISION",
        "repository-intelligence-test-revision-r2",
    )

    rebuilt = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert rebuilt.status == "created"
    assert rebuilt.snapshot_id != baseline.snapshot_id


def test_repository_snapshot_tracks_dirty_git_worktree_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    baseline = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    target_file = repo_path / "src" / "service.py"
    target_file.write_text(
        "def handle_request(user):\n    return user.email\n",
        encoding="utf-8",
    )

    dirty_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert dirty_snapshot.status == "created"
    assert dirty_snapshot.snapshot_id != baseline.snapshot_id
    assert dirty_snapshot.resolved_revision != baseline.resolved_revision


def test_repository_snapshot_reuses_shared_file_analysis_across_connectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    first_connector = _connector_for_repo(repo_path)
    second_connector = _connector_for_repo(repo_path)

    first_snapshot = repository_service.create_repository_snapshot(
        connector=first_connector,
        request=RepositorySnapshotCreateRequest(),
    )

    def _unexpected_analyze_file(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("shared file-analysis cache should avoid reparsing unchanged files")

    monkeypatch.setattr(repository_service, "_analyze_file", _unexpected_analyze_file)

    second_snapshot = repository_service.create_repository_snapshot(
        connector=second_connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert first_snapshot.status == "created"
    assert second_snapshot.status == "created"
    assert second_snapshot.snapshot_id != first_snapshot.snapshot_id
    assert second_snapshot.file_count == first_snapshot.file_count


def test_repository_snapshot_reuses_shared_file_selection_across_archive_connectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    archive_path = _sample_archive(tmp_path)
    first_connector = _connector_for_archive(archive_path)
    second_connector = _connector_for_archive(archive_path)

    first_snapshot = repository_service.create_repository_snapshot(
        connector=first_connector,
        request=RepositorySnapshotCreateRequest(),
    )

    def _unexpected_iter_repository_files(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("archive file-selection cache should avoid rescanning extracted files")

    monkeypatch.setattr(repository_service, "_iter_repository_files", _unexpected_iter_repository_files)

    second_snapshot = repository_service.create_repository_snapshot(
        connector=second_connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert first_snapshot.status == "created"
    assert second_snapshot.status == "created"
    assert second_snapshot.snapshot_id != first_snapshot.snapshot_id
    assert second_snapshot.file_count == first_snapshot.file_count


def test_repository_snapshot_uses_git_blob_hashes_for_clean_tracked_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    original_hash_file = repository_service._hash_file

    def _unexpected_hash_file(path: Path) -> str:
        try:
            path.relative_to(repo_path)
        except ValueError:
            return original_hash_file(path)
        raise AssertionError(f"clean tracked git file should use git blob hash: {path}")

    monkeypatch.setattr(repository_service, "_hash_file", _unexpected_hash_file)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert snapshot.status == "created"
    assert snapshot.file_count == 2


def test_repository_snapshot_only_reanalyzes_changed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    target_file = repo_path / "src" / "service.py"
    target_file.write_text(
        "def handle_request(user):\n    return user.email\n",
        encoding="utf-8",
    )

    original_analyze_file = repository_service._analyze_file
    analyzed_paths: list[str] = []

    def _tracking_analyze_file(*args, **kwargs):  # type: ignore[no-untyped-def]
        analyzed_paths.append(str(kwargs["path"].relative_to(kwargs["root_path"])))
        return original_analyze_file(*args, **kwargs)

    monkeypatch.setattr(repository_service, "_analyze_file", _tracking_analyze_file)

    updated_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert updated_snapshot.status == "created"
    assert analyzed_paths == ["src/service.py"]


def test_analyze_snapshot_files_preserves_input_order_when_parallel(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ordered-repo"
    (repo_path / "src").mkdir(parents=True)
    first = repo_path / "src" / "a.py"
    second = repo_path / "src" / "b.py"
    first.write_text("def a() -> int:\n    return 1\n", encoding="utf-8")
    second.write_text("def b() -> int:\n    return 2\n", encoding="utf-8")

    original_analyze_file_cached = repository_service._analyze_file_cached

    def _delayed_analyze_file_cached(*args, **kwargs):  # type: ignore[no-untyped-def]
        path = kwargs["path"]
        if Path(path).name == "a.py":
            time.sleep(0.05)
        return original_analyze_file_cached(*args, **kwargs)

    repository_service._analyze_file_cached = _delayed_analyze_file_cached
    try:
        analyses = repository_service._analyze_snapshot_files(
            root_path=repo_path,
            files=[first, second],
            module_index={"src/a": "src/a.py", "src/b": "src/b.py"},
            workspace_package_index={},
            workspace_go_module_index={},
            max_file_size_bytes=100_000,
            analysis_context_hash="order-test",
            git_content_hashes=None,
            max_workers=2,
        )
    finally:
        repository_service._analyze_file_cached = original_analyze_file_cached

    assert [analysis.file_path for analysis in analyses] == ["src/a.py", "src/b.py"]


def test_resolve_suffix_match_preserves_sorted_first_match_for_nested_suffixes() -> None:
    module_index = {
        "alpha": "packages/alpha/src/FSharpPlus/Control/Functor.fs",
        "beta": "packages/beta/src/FSharpPlus/Control/Functor.fs",
    }

    resolved = repository_service._resolve_suffix_match(
        module_index=module_index,
        suffixes=("src/FSharpPlus/Control/Functor.fs", "Functor.fs"),
    )

    assert resolved == "packages/alpha/src/FSharpPlus/Control/Functor.fs"


def test_resolve_directory_prefix_match_finds_nested_directory_suffixes() -> None:
    module_index = {
        "alpha": "packages/alpha/src/FSharpPlus/Control/Functor.fs",
        "beta": "packages/beta/src/Other/Control/Functor.fs",
    }

    resolved = repository_service._resolve_directory_prefix_match(
        module_index=module_index,
        prefixes=("src/FSharpPlus/Control",),
    )

    assert resolved == "packages/alpha/src/FSharpPlus/Control/Functor.fs"


def test_repository_snapshot_hashes_only_dirty_git_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    target_file = repo_path / "src" / "service.py"
    target_file.write_text(
        "def handle_request(user):\n    return user.email\n",
        encoding="utf-8",
    )

    original_hash_file = repository_service._hash_file
    hashed_paths: list[str] = []

    def _tracking_hash_file(path: Path) -> str:
        try:
            hashed_paths.append(str(path.relative_to(repo_path)))
        except ValueError:
            return original_hash_file(path)
        return original_hash_file(path)

    monkeypatch.setattr(repository_service, "_hash_file", _tracking_hash_file)

    updated_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert updated_snapshot.status == "created"
    assert hashed_paths == ["src/service.py", "src/service.py"]


def test_repository_triage_existing_lookup_skips_retriage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    request = RepositoryTriageRequest(
        snapshot_id=snapshot.snapshot_id,
        signals={
            "issue_text": "handle_request crashes when user is null",
            "diagnostics": [
                {
                    "path": "src/service.py",
                    "line": 2,
                    "severity": "error",
                    "message": "AttributeError: 'NoneType' object has no attribute 'name'",
                }
            ],
        },
    )

    first = repository_service.triage_repository(connector=connector, request=request)
    triage_path = repository_service._triage_dir(
        str(connector.org_id),
        str(connector.id),
    ) / f"{first.workspace_evidence_bundle_ref}.json"

    def _unexpected_materialized_snapshot(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("triage fast path should reuse the persisted evidence bundle")

    monkeypatch.setattr(
        repository_service,
        "materialized_snapshot",
        _unexpected_materialized_snapshot,
    )
    original_read_json = repository_service._read_json

    def _read_json_without_triage_manifest(path: Path) -> dict[str, Any]:
        if Path(path) == triage_path:
            raise AssertionError("triage fast path should not reopen the triage manifest")
        return original_read_json(path)

    monkeypatch.setattr(repository_service, "_read_json", _read_json_without_triage_manifest)
    second = repository_service.triage_repository(connector=connector, request=request)

    assert second.workspace_evidence_bundle_ref == first.workspace_evidence_bundle_ref
    assert second.evidence_items == first.evidence_items


def test_repository_triage_propagates_graph_neighbor_risk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _graph_neighbor_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "fragile_helper fails on malformed whitespace input",
                "diagnostics": [
                    {
                        "path": "src/worker.py",
                        "line": 2,
                        "severity": "error",
                        "message": "ValueError raised inside fragile_helper",
                    }
                ],
            },
            max_evidence_items=4,
        ),
    )

    assert triage.suspect_files[0] == "src/worker.py"
    assert "src/main.py" in triage.suspect_files


def test_repository_triage_lifts_related_diagnostic_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_rootdir_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    related_path = repo_path / "packages" / "common" / "src" / "shared.ts"
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "TypeScript rootDir drift",
                "diagnostics": [
                    {
                        "path": "services/app/src/index.ts",
                        "line": 1,
                        "severity": "error",
                        "code": "TS6059",
                        "message": (
                            f"File '{related_path}' is not under 'rootDir' "
                            f"'{repo_path / 'services' / 'app'}'. 'rootDir' is expected "
                            "to contain all source files."
                        ),
                    }
                ],
            },
            max_evidence_items=4,
        ),
    )

    assert triage.suspect_files[0] == "packages/common/src/shared.ts"
    assert triage.evidence_items[0].file_path == "packages/common/src/shared.ts"
    assert triage.evidence_items[0].symbol_name == "shared"


def test_repository_triage_penalizes_typescript_barrel_wrappers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_barrel_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    related_path = repo_path / "src" / "common" / "shared.ts"
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "Helper import crosses a wrapper barrel",
                "diagnostics": [
                    {
                        "path": "src/common/index.ts",
                        "line": 1,
                        "severity": "error",
                        "code": "TS6059",
                        "message": (
                            f"File '{related_path}' is not under 'rootDir' "
                            f"'{repo_path / 'src' / 'app'}'. 'rootDir' is expected "
                            "to contain all source files."
                        ),
                    }
                ],
            },
            max_evidence_items=4,
        ),
    )

    assert triage.suspect_files[0] == "src/common/shared.ts"
    assert "src/common/index.ts" in triage.suspect_files
    assert triage.evidence_items[0].symbol_name == "usefulHelper"


def test_repository_graph_query_returns_dependency_and_dependent_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _graph_neighbor_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    response = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            file_path="src/worker.py",
            direction="both",
            max_depth=2,
        ),
    )

    assert response.seed_file_paths == ["src/worker.py"]
    assert response.direct_dependents == ["src/main.py"]
    assert response.impacted_files[:2] == ["src/worker.py", "src/main.py"]
    assert response.top_change_risk_files[0].file_path == "src/worker.py"


def test_repository_graph_query_resolves_symbol_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_barrel_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    response = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            symbol_name="usefulHelper",
            direction="inbound",
            max_depth=2,
        ),
    )

    assert "src/common/shared.ts" in response.seed_file_paths
    assert "src/app/main.ts" in response.direct_dependents
    assert any(item.top_symbol == "usefulHelper" for item in response.top_change_risk_files)


def test_repository_graph_query_promotes_wrapper_seed_to_actionable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_barrel_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    response = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            file_path="src/common/index.ts",
            direction="both",
            max_depth=2,
        ),
    )

    assert response.seed_file_paths == ["src/common/shared.ts"]
    assert "src/app/main.ts" in response.direct_dependents
    assert response.top_change_risk_files[0].file_path == "src/common/shared.ts"


def test_repository_graph_query_promotes_config_seed_to_nearby_actionable_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_rootdir_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=[
                "services/app",
                "packages/common",
                "services/app/tsconfig.test.json",
                "services/app/tsconfig.json",
            ],
            include_patterns=[
                "services/**/*.ts",
                "services/**/*.json",
                "packages/**/*.ts",
                "packages/**/*.json",
            ],
        ),
    )

    response = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            file_path="services/app/tsconfig.test.json",
            direction="both",
            max_depth=2,
        ),
    )

    assert response.seed_file_paths == ["services/app/src/index.ts"]
    assert response.direct_dependencies == ["packages/common/src/shared.ts"]
    assert response.top_change_risk_files[0].file_path == "services/app/src/index.ts"


def test_repository_graph_query_existing_lookup_skips_recomputation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _graph_neighbor_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    first = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            file_path="src/worker.py",
            direction="both",
            max_depth=2,
        ),
    )

    def _fail_load_snapshot_manifest(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("cached graph query should not reload the snapshot manifest")

    monkeypatch.setattr(
        repository_service,
        "_load_snapshot_manifest",
        _fail_load_snapshot_manifest,
    )

    second = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            file_path="src/worker.py",
            direction="both",
            max_depth=2,
        ),
    )

    assert second.model_dump(mode="json") == first.model_dump(mode="json")


def test_repository_graph_query_uses_workspace_evidence_bundle_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "handle_request crashes when user is null",
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 2,
                        "severity": "error",
                        "message": "AttributeError: 'NoneType' object has no attribute 'name'",
                    }
                ],
            },
        ),
    )

    response = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            direction="both",
            max_depth=2,
        ),
    )

    assert response.seed_file_paths == ["src/service.py"]
    assert response.direct_dependents == ["tests/test_service.py"]
    assert response.top_change_risk_files[0].file_path == "src/service.py"


def test_repository_graph_query_workspace_evidence_bundle_snapshot_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    first_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=first_snapshot.snapshot_id,
            signals={
                "issue_text": "handle_request crashes when user is null",
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 2,
                        "severity": "error",
                        "message": "AttributeError: 'NoneType' object has no attribute 'name'",
                    }
                ],
            },
        ),
    )
    second_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(ref="HEAD"),
    )

    with pytest.raises(repository_service.RepositoryIntelligenceError) as excinfo:
        repository_service.query_repository_graph(
            connector=connector,
            request=repository_service.RepositoryGraphQueryRequest(
                snapshot_id=second_snapshot.snapshot_id,
                workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
                direction="both",
                max_depth=2,
            ),
        )

    assert excinfo.value.code == "repository_graph_query_snapshot_mismatch"


def test_repository_snapshot_falls_back_from_unwritable_default_runtime_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ALGENTA_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(repository_runtime, "_RUNTIME_FALLBACK_CACHE", None)
    fallback_runtime_dir = tmp_path / "workspace-runtime"
    default_home = tmp_path / "home"
    default_runtime_dir = (default_home / ".algenta" / "runtime").resolve()
    monkeypatch.setattr(repository_runtime.Path, "home", staticmethod(lambda: default_home))
    monkeypatch.setattr(
        repository_runtime,
        "_runtime_fallback_candidates",
        lambda: [fallback_runtime_dir],
    )
    monkeypatch.setattr(
        repository_runtime,
        "_runtime_dir_writable",
        lambda path: path.resolve() != default_runtime_dir,
    )

    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    storage_path = Path(manifest["repository_snapshot_artifact"]["storage_path"])
    assert str(storage_path).startswith(str(fallback_runtime_dir.resolve()))
    assert fallback_runtime_dir.exists()


def test_repository_snapshot_focus_paths_bound_analysis_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "focused-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def important_handler() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "worker.py").write_text(
        "def background_worker() -> str:\n    return 'worker'\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "runbook.md").write_text(
        "# Runbook\n\nThis file should not be indexed in the focused snapshot.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    focused_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/service.py"],
            max_total_bytes=4_096,
        ),
    )

    assert focused_snapshot.file_count == 1
    assert focused_snapshot.language_counts == {"python": 1}
    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=focused_snapshot.snapshot_id,
    )
    assert manifest["focus_paths"] == ["src/service.py"]
    assert manifest["requested_focus_paths"] == ["src/service.py"]
    assert manifest["effective_focus_paths"] == ["src/service.py"]
    assert [entry["file_path"] for entry in manifest["files"]] == ["src/service.py"]


def test_repository_snapshot_compacts_redundant_broad_focus_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "compact-focus-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def important_handler() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "worker.py").write_text(
        "def background_worker() -> str:\n    return 'worker'\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "src/service.py", "src/worker.py"],
        ),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    assert snapshot.file_count == 2
    assert manifest["requested_focus_paths"] == ["src", "src/service.py", "src/worker.py"]
    assert manifest["effective_focus_paths"] == ["src/service.py", "src/worker.py"]
    assert manifest["focus_paths"] == ["src/service.py", "src/worker.py"]


def test_repository_snapshot_preserves_broad_focus_when_it_covers_unique_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "preserve-focus-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def important_handler() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "worker.py").write_text(
        "def background_worker() -> str:\n    return 'worker'\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "src/service.py"],
        ),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    assert snapshot.file_count == 2
    assert manifest["requested_focus_paths"] == ["src", "src/service.py"]
    assert manifest["effective_focus_paths"] == ["src", "src/service.py"]
    assert manifest["focus_paths"] == ["src", "src/service.py"]


def test_repository_snapshot_prefer_concrete_focus_paths_drops_broad_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "prefer-concrete-focus-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def important_handler() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "worker.py").write_text(
        "def background_worker() -> str:\n    return 'worker'\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "src/service.py"],
            prefer_concrete_focus_paths=True,
        ),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    assert snapshot.file_count == 1
    assert manifest["requested_focus_paths"] == ["src", "src/service.py"]
    assert manifest["effective_focus_paths"] == ["src/service.py"]
    assert manifest["prefer_concrete_focus_paths"] is True


def test_repository_snapshot_excludes_nested_generated_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "generated-output-repo"
    (repo_path / "services" / "api" / "src").mkdir(parents=True)
    (repo_path / "services" / "api" / "dist_fresh").mkdir(parents=True)
    (repo_path / "services" / "api" / "src" / "main.ts").write_text(
        "export const value = 1;\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "api" / "dist_fresh" / "main.js").write_text(
        "exports.value = 1;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["services/api"],
            include_patterns=["services/**/*.ts", "services/**/*.js"],
        ),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    assert snapshot.file_count == 1
    assert [entry["file_path"] for entry in manifest["files"]] == ["services/api/src/main.ts"]


def test_repository_snapshot_includes_control_files_and_skips_binary_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "mixed-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def run() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "Dockerfile").write_text(
        "FROM python:3.12-slim\nCOPY . /app\n",
        encoding="utf-8",
    )
    (repo_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    assert sorted(entry["file_path"] for entry in manifest["files"]) == [
        "Dockerfile",
        "src/service.py",
    ]


def test_repository_snapshot_persists_uncompressed_source_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    source_archive_path = Path(manifest["source_archive_path"])

    assert source_archive_path.name == "source.tar"
    with repository_service.materialized_snapshot(manifest) as extracted_root:
        assert (extracted_root / "src" / "service.py").read_text(encoding="utf-8") == (
            repo_path / "src" / "service.py"
        ).read_text(encoding="utf-8")


def test_repository_snapshot_does_not_rehash_parquet_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    original_hash_file = repository_service._hash_file
    hashed_paths: list[str] = []

    def _tracking_hash_file(path: Path) -> str:
        hashed_paths.append(Path(path).name)
        return original_hash_file(path)

    monkeypatch.setattr(repository_service, "_hash_file", _tracking_hash_file)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert snapshot.status == "created"
    assert "source.tar" in hashed_paths
    assert not any(path.endswith(".parquet") for path in hashed_paths)


def test_iter_repository_files_uses_git_listing_without_tree_walk(tmp_path: Path) -> None:
    repo_path = tmp_path / "git-listing-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def run() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    original_os_walk = repository_service.os.walk

    def _unexpected_os_walk(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("git-backed repository discovery should avoid os.walk")

    repository_service.os.walk = _unexpected_os_walk
    try:
        files = repository_service._iter_repository_files(
            repo_path,
            focus_paths=[],
            include_patterns=["src/*.py", "src/**/*.py"],
            exclude_patterns=[],
            max_files=128,
            max_total_bytes=None,
        )
    finally:
        repository_service.os.walk = original_os_walk

    assert [str(path.relative_to(repo_path)) for path in files] == ["src/service.py"]


def test_matches_repository_pattern_treats_recursive_glob_as_optional_for_direct_children() -> None:
    assert repository_service._matches_repository_pattern("src/main.cpp", "src/**/*.cpp")
    assert repository_service._matches_repository_pattern("src/acme/main.cpp", "src/**/*.cpp")
    assert repository_service._matches_repository_pattern(
        "include/acme/core.hpp",
        "include/**/*.hpp",
    )


def test_repository_analysis_resolves_typescript_relative_and_workspace_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        json.dumps({"name": "@acme/common"}),
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "util.ts").write_text(
        "export const helper = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "packages" / "common" / "src" / "shared.ts").write_text(
        "export const shared = (): string => 'shared';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { helper } from './util';\n"
        "import { shared } from '@acme/common/shared';\n"
        "export const run = (): string => `${helper()}-${shared()}`;\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "services/app/src/main.ts",
            "services/app/src/util.ts",
            "packages/common/src/shared.ts",
        ]
    )
    workspace_package_index = repository_service._build_workspace_package_index(repo_path)
    analysis = repository_service._analyze_file(
        root_path=repo_path,
        path=repo_path / "services" / "app" / "src" / "main.ts",
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        max_file_size_bytes=100_000,
    )

    resolved_targets = {dependency.target_file for dependency in analysis.dependencies}
    assert "services/app/src/util.ts" in resolved_targets
    assert "packages/common/src/shared.ts" in resolved_targets


def test_repository_analysis_resolves_typescript_tsconfig_path_aliases(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tsconfig-alias-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "tsconfig.json").write_text(
        '{\n'
        '  "compilerOptions": {\n'
        '    "baseUrl": ".",\n'
        '    "paths": {\n'
        '      "@/*": ["./src/*"]\n'
        "    }\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "lib" / "utils.ts").write_text(
        "export const helper = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.ts").write_text(
        "import { helper } from '@/lib/utils';\n"
        "export const run = (): string => helper();\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "src/main.ts",
            "src/lib/utils.ts",
        ],
        root_path=repo_path,
    )
    analysis = repository_service._analyze_file(
        root_path=repo_path,
        path=repo_path / "src" / "main.ts",
        module_index=module_index,
        workspace_package_index={},
        max_file_size_bytes=100_000,
    )

    resolved_targets = {dependency.target_file for dependency in analysis.dependencies}
    assert "src/lib/utils.ts" in resolved_targets


def test_repository_analysis_extracts_nested_typescript_symbol_hierarchy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "nested-symbol-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    target_path = repo_path / "services" / "app" / "src" / "main.ts"
    target_path.write_text(
        "export class Planner {\n"
        "  private readonly onEvent = async (): Promise<string> => {\n"
        "    function normalize(value: string): string {\n"
        "      return value.trim();\n"
        "    }\n"
        "    return normalize('ok');\n"
        "  };\n"
        "\n"
        "  build(): string {\n"
        "    function finalize(value: string): string {\n"
        "      return value.toUpperCase();\n"
        "    }\n"
        "    return finalize('ok');\n"
        "  }\n"
        "}\n"
        "\n"
        "export const run = (): string => {\n"
        "  class Inner {\n"
        "    execute(): string {\n"
        "      return 'done';\n"
        "    }\n"
        "  }\n"
        "  return new Inner().execute();\n"
        "};\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(["services/app/src/main.ts"])
    analysis = repository_service._analyze_file(
        root_path=repo_path,
        path=target_path,
        module_index=module_index,
        workspace_package_index={},
        max_file_size_bytes=100_000,
    )

    symbols_by_name = {symbol.symbol_name: symbol for symbol in analysis.symbols}
    assert symbols_by_name["Planner"].parent_symbol_id is None
    assert symbols_by_name["onEvent"].parent_symbol_id == symbols_by_name["Planner"].symbol_id
    assert symbols_by_name["normalize"].parent_symbol_id == symbols_by_name["onEvent"].symbol_id
    assert symbols_by_name["build"].parent_symbol_id == symbols_by_name["Planner"].symbol_id
    assert symbols_by_name["finalize"].parent_symbol_id == symbols_by_name["build"].symbol_id
    assert symbols_by_name["run"].parent_symbol_id is None
    assert symbols_by_name["Inner"].parent_symbol_id == symbols_by_name["run"].symbol_id
    assert symbols_by_name["execute"].parent_symbol_id == symbols_by_name["Inner"].symbol_id


def test_repository_snapshot_graph_contains_symbol_parent_child_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "graph-symbol-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    target_path = repo_path / "services" / "app" / "src" / "main.ts"
    target_path.write_text(
        "export class Planner {\n"
        "  build(): string {\n"
        "    function finalize(value: string): string {\n"
        "      return value.toUpperCase();\n"
        "    }\n"
        "    return finalize('ok');\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["services/app/src/main.ts"],
            include_patterns=["services/**/*.ts"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {str(row["symbol_name"]): str(row["symbol_id"]) for row in symbol_rows}

    assert any(
        str(row["edge_type"]) == "contains_symbol"
        and str(row["source_node"]) == f"symbol:{symbol_ids['Planner']}"
        and str(row["target_node"]) == f"symbol:{symbol_ids['build']}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "contains_symbol"
        and str(row["source_node"]) == f"symbol:{symbol_ids['build']}"
        and str(row["target_node"]) == f"symbol:{symbol_ids['finalize']}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "graph-reference-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "services" / "app" / "src" / "util.ts").write_text(
        "export function helper(): string {\n"
        "  return 'ok';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { helper } from './util';\n"
        "\n"
        "export const run = (): string => {\n"
        "  function finalize(value: string): string {\n"
        "    return `${helper()}-${value}`;\n"
        "  }\n"
        "  return finalize('ok');\n"
        "};\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["services/app/src"],
            include_patterns=["services/**/*.ts"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("services/app/src/main.ts", "run")]
    finalize_symbol_id = symbol_ids[("services/app/src/main.ts", "finalize")]
    helper_symbol_id = symbol_ids[("services/app/src/util.ts", "helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{finalize_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{finalize_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_python_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "python-graph-reference-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "app" / "util.py").write_text(
        "def helper() -> str:\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "main.py").write_text(
        "from app.util import helper\n\n"
        "class Planner:\n"
        "    def finish(self, value: str) -> str:\n"
        "        return value.upper()\n\n"
        "    def build(self) -> str:\n"
        "        return self.finish(helper())\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["app"],
            include_patterns=["app/*.py", "app/**/*.py"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    build_symbol_id = symbol_ids[("app/main.py", "build")]
    finish_symbol_id = symbol_ids[("app/main.py", "finish")]
    helper_symbol_id = symbol_ids[("app/util.py", "helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{finish_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_rust_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "rust-graph-reference-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.rs").write_text(
        "pub fn value() -> String {\n"
        '    "ok".to_string()\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.rs").write_text(
        "use crate::helper::value;\n"
        "mod helper;\n\n"
        "pub fn run() -> String {\n"
        "    value()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/*.rs", "src/**/*.rs"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("src/main.rs", "run")]
    value_symbol_id = symbol_ids[("src/helper.rs", "value")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{value_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_go_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "go-graph-reference-repo"
    (repo_path / "helper").mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper" / "helper.go").write_text(
        "package helper\n\n"
        "func Value() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package main\n\n"
        'import "example.com/repo/helper"\n\n'
        "func run() string {\n"
        "    return helper.Value()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.go", "helper"],
            include_patterns=["*.go", "**/*.go"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("main.go", "run")]
    value_symbol_id = symbol_ids[("helper/helper.go", "Value")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{value_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_go_same_package_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "go-same-package-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run() string {\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.go", "helper.go"],
            include_patterns=["*.go", "**/*.go"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("main.go", "run")]
    helper_symbol_id = symbol_ids[("helper.go", "helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_ignores_go_builtin_collisions_for_same_package_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "go-builtin-collision-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "builtin.go").write_text(
        "package cobra\n\n"
        "func len(items []string) int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run(items []string) int {\n"
        "    _ = len(items)\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.go", "helper.go", "builtin.go"],
            include_patterns=["*.go", "**/*.go"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("main.go", "run")]
    helper_symbol_id = symbol_ids[("helper.go", "helper")]
    builtin_symbol_id = symbol_ids[("builtin.go", "len")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert not any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{builtin_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_ignores_go_stdlib_import_file_name_collisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "go-stdlib-import-collision-repo"
    (repo_path / "middleware").mkdir(parents=True)
    (repo_path / "_examples" / "versions" / "data").mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "middleware" / "recoverer.go").write_text(
        "package middleware\n\n"
        'import "errors"\n\n'
        "func Recoverer() error {\n"
        '    return errors.New("boom")\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "_examples" / "versions" / "data" / "errors.go").write_text(
        "package data\n\n"
        "func PresentError() string {\n"
        '    return "boom"\n'
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["middleware", "_examples/versions/data"],
            include_patterns=["*.go", "**/*.go"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    dependency_rows = pq.read_table(snapshot.dependency_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["source_file"]) == "middleware/recoverer.go"
        and str(row["target_symbol"]) == "errors"
        and row["target_file"] is None
        for row in dependency_rows
    )
    assert not any(
        str(row["source_file"]) == "middleware/recoverer.go"
        and str(row["target_file"]) == "_examples/versions/data/errors.go"
        for row in dependency_rows
    )


def test_repository_snapshot_graph_prefers_non_test_go_same_package_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "go-test-leak-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "helper_test.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "test"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run() string {\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.go", "helper.go", "helper_test.go"],
            include_patterns=["*.go", "**/*.go"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("main.go", "run")]
    helper_symbol_id = symbol_ids[("helper.go", "helper")]
    helper_test_symbol_id = symbol_ids[("helper_test.go", "helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert not any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_test_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_mojo_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "mojo-graph-reference-repo"
    (repo_path / "helper").mkdir(parents=True)
    (repo_path / "helper" / "util.mojo").write_text(
        "fn value():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (repo_path / "main.mojo").write_text(
        "import helper.util\n\n"
        "fn run():\n"
        "    return util.value()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.mojo", "helper"],
            include_patterns=["*.mojo", "**/*.mojo"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("main.mojo", "run")]
    value_symbol_id = symbol_ids[("helper/util.mojo", "value")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{value_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_cpp_include_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cpp-dependency-repo"
    (repo_path / "include" / "acme").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include" / "acme" / "format.hpp").write_text(
        "#pragma once\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "format.hpp").write_text(
        '#include "acme/format.hpp"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cpp").write_text(
        '#include "format.hpp"\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "include"],
            include_patterns=["src/**/*.cpp", "src/**/*.hpp", "include/**/*.hpp"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.cpp"
        and str(row["target_node"]) in {"file:src/format.hpp", "file:include/acme/format.hpp"}
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/format.hpp"
        and str(row["target_node"]) == "file:include/acme/format.hpp"
        for row in graph_rows
    )


def test_c_family_operational_reference_name_filters_macro_like_noise() -> None:
    assert repository_service._is_c_family_operational_reference_name("format_value")
    assert not repository_service._is_c_family_operational_reference_name("FMT_ENABLE_IF")
    assert not repository_service._is_c_family_operational_reference_name("__attribute__")
    assert not repository_service._is_c_family_operational_reference_name("va_end")


def test_parse_c_family_file_skips_attribute_noise_symbols() -> None:
    symbols, dependencies, symbol_references = repository_service._parse_c_family_file(
        "src/net.c",
        "__attribute__((unused)) static int helper(void);\n"
        "int run(void) {\n"
        "    va_end(args);\n"
        "    return helper();\n"
        "}\n",
        {},
    )

    symbol_names = {symbol.symbol_name for symbol in symbols}
    assert "__attribute__" not in symbol_names
    assert "helper" in symbol_names
    assert "run" in symbol_names
    assert dependencies == ()
    assert all("va_end" not in candidate.target_names for candidate in symbol_references)


def test_repository_snapshot_graph_contains_cpp_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cpp-symbol-graph-repo"
    (repo_path / "include" / "acme").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include" / "acme" / "format.hpp").write_text(
        "#pragma once\n"
        "namespace acme {\n"
        "int format_value();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cpp").write_text(
        '#include "acme/format.hpp"\n'
        "int run() {\n"
        "    return acme::format_value();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "include"],
            include_patterns=["src/**/*.cpp", "include/**/*.hpp"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("src/main.cpp", "run")]
    format_value_symbol_id = symbol_ids[("include/acme/format.hpp", "format_value")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{format_value_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_ruby_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ruby-dependency-repo"
    (repo_path / "lib" / "jekyll").mkdir(parents=True)
    (repo_path / "lib" / "jekyll" / "cache.rb").write_text(
        "module Jekyll\n"
        "  class Cache\n"
        "    def self.helper\n"
        "      1\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "jekyll.rb").write_text(
        'require "jekyll/cache"\n'
        "module Jekyll\n"
        "  def self.run\n"
        "    Jekyll::Cache.helper\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=["lib/*.rb", "lib/**/*.rb"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:lib/jekyll.rb"
        and str(row["target_node"]) == "file:lib/jekyll/cache.rb"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("lib/jekyll.rb", "run")]
    helper_symbol_id = symbol_ids[("lib/jekyll/cache.rb", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_ruby_new_inheritance_and_mixin_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ruby-structure-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "lib" / "acme" / "base_runner.rb").write_text(
        "module Acme\n"
        "  class BaseRunner\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "serializable.rb").write_text(
        "module Acme\n"
        "  module Serializable\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "runner.rb").write_text(
        'require "acme/base_runner"\n'
        'require "acme/serializable"\n'
        "module Acme\n"
        "  class Runner < BaseRunner\n"
        "    include Serializable\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme.rb").write_text(
        'require "acme/runner"\n'
        "module Acme\n"
        "  def self.build\n"
        "    Runner.new\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=["lib/*.rb", "lib/**/*.rb", "Gemfile"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    build_symbol_id = symbol_ids[("lib/acme.rb", "build")]
    runner_symbol_id = symbol_ids[("lib/acme/runner.rb", "Runner")]
    base_runner_symbol_id = symbol_ids[("lib/acme/base_runner.rb", "BaseRunner")]
    serializable_symbol_id = symbol_ids[("lib/acme/serializable.rb", "Serializable")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{runner_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{runner_symbol_id}"
        and str(row["target_node"]) == f"symbol:{base_runner_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{runner_symbol_id}"
        and str(row["target_node"]) == f"symbol:{serializable_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_dart_package_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "dart-dependency-repo"
    (repo_path / "lib" / "src").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "pubspec.yaml").write_text(
        "name: acme_client\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "src" / "helper.dart").write_text(
        "class Helper {\n"
        "  static String value() => 'ok';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme_client.dart").write_text(
        "export 'src/helper.dart' show Helper;\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "acme_client.dart").write_text(
        "import 'package:acme_client/src/helper.dart' show Helper;\n\n"
        "String run() => Helper.value();\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib", "bin"],
            include_patterns=["lib/*.dart", "lib/**/*.dart", "bin/*.dart", "bin/**/*.dart"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:bin/acme_client.dart"
        and str(row["target_node"]) == "file:lib/src/helper.dart"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "exports"
        and str(row["source_node"]) == "file:lib/acme_client.dart"
        and str(row["target_node"]) == "file:lib/src/helper.dart"
        for row in graph_rows
    )

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    run_symbol_id = symbol_ids[("bin/acme_client.dart", "run")]
    helper_symbol_id = symbol_ids[("lib/src/helper.dart", "Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_clojure_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "clojure-dependency-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "deps.edn").write_text(
        '{:paths ["src"] :main acme.core}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "util.clj").write_text(
        "(ns acme.util)\n"
        "(defn helper [] \"ok\")\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.clj").write_text(
        "(ns acme.core\n"
        "  (:require [acme.util :as util]))\n"
        "(defn run []\n"
        "  (util/helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.clj", "src/**/*.cljc", "src/**/*.cljs"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/acme/core.clj"
        and str(row["target_node"]) == "file:src/acme/util.clj"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/acme/core.clj", "run")]
    helper_symbol_id = symbol_ids[("src/acme/util.clj", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_clojure_refer_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "clojure-refer-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "deps.edn").write_text(
        '{:paths ["src"] :main acme.core}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "util.clj").write_text(
        "(ns acme.util)\n"
        "(defn helper [] :ok)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.clj").write_text(
        "(ns acme.core\n"
        "  (:require [acme.util :refer [helper]]))\n"
        "(defn run []\n"
        "  (helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.clj", "src/**/*.cljc", "src/**/*.cljs"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("src/acme/core.clj", "run")]
    helper_symbol_id = symbol_ids[("src/acme/util.clj", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_parse_clojure_dependencies_only_follows_refer_edges() -> None:
    dependencies = repository_service._parse_clojure_dependencies_only(
        "src/acme/core.clj",
        "(ns acme.core\n"
        "  (:require [acme.util :refer [helper]]))\n"
        "(defn run []\n"
        "  (helper))\n",
        {"acme.util": "src/acme/util.clj"},
    )

    assert any(
        dependency.dependency_type == "references"
        and dependency.target_file == "src/acme/util.clj"
        and dependency.target_symbol == "helper"
        for dependency in dependencies
    )


def test_repository_snapshot_graph_contains_lua_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "lua-dependency-repo"
    (repo_path / "lua" / "acme").mkdir(parents=True)
    (repo_path / "acme-scm-1.rockspec").write_text(
        'package = "acme"\n'
        'build = { modules = { ["acme.core"] = "lua/acme/core.lua", ["acme.util"] = "lua/acme/util.lua" } }\n',
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "util.lua").write_text(
        "local M = {}\n"
        "function M.helper()\n"
        "  return 'ok'\n"
        "end\n"
        "return M\n",
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "core.lua").write_text(
        "local util = require('acme.util')\n"
        "local function run()\n"
        "  return util.helper()\n"
        "end\n"
        "return { run = run }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lua"],
            include_patterns=["lua/**/*.lua", "*.rockspec"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:lua/acme/core.lua"
        and str(row["target_node"]) == "file:lua/acme/util.lua"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("lua/acme/core.lua", "run")]
    helper_symbol_id = symbol_ids[("lua/acme/util.lua", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_lua_require_member_and_method_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "lua-member-binding-repo"
    (repo_path / "lua" / "acme").mkdir(parents=True)
    (repo_path / "acme-scm-1.rockspec").write_text(
        'package = "acme"\n'
        'build = { modules = { ["acme.util"] = "lua/acme/util.lua", ["acme.core"] = "lua/acme/core.lua" } }\n',
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "util.lua").write_text(
        "local M = {}\n"
        "function M.helper()\n"
        "  return 'ok'\n"
        "end\n"
        "function M:push()\n"
        "  return self:helper()\n"
        "end\n"
        "return M\n",
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "core.lua").write_text(
        "local util = require('acme.util')\n"
        "local helper = require('acme.util').helper\n"
        "local function run()\n"
        "  util:push()\n"
        "  return helper()\n"
        "end\n"
        "return { run = run }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lua"],
            include_patterns=["lua/**/*.lua", "*.rockspec"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("lua/acme/core.lua", "run")]
    helper_symbol_id = symbol_ids[("lua/acme/util.lua", "helper")]
    push_symbol_id = symbol_ids[("lua/acme/util.lua", "push")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{push_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_luau_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "luau-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "default.project.json").write_text(
        '{\n  "name": "demo",\n  "tree": {\n    "$path": "src/Main.luau"\n  }\n}\n',
        encoding="utf-8",
    )
    (repo_path / "wally.toml").write_text(
        "[package]\nname = 'demo/demo'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Utils.luau").write_text(
        "--!strict\nlocal M = {}\nfunction M.helper()\n  return 'ok'\nend\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.luau").write_text(
        "--!strict\nlocal Utils = require(script.Parent.Utils)\n"
        "local function run()\n  return Utils.helper()\nend\nreturn run\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.luau", "default.project.json", "wally.toml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/Main.luau"
        and str(row["target_node"]) == "file:src/Utils.luau"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/Main.luau", "run")]
    helper_symbol_id = symbol_ids[("src/Utils.luau", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_dhall_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "dhall-dependency-repo"
    (repo_path / "schemas").mkdir(parents=True)
    (repo_path / "package.dhall").write_text(
        "{ Type = ./schemas/Step.dhall }\n",
        encoding="utf-8",
    )
    (repo_path / "schemas" / "Step.dhall").write_text(
        "{ Type = \"step\", default = \"run\" }\n",
        encoding="utf-8",
    )
    (repo_path / "workflow.dhall").write_text(
        "let Package = ./package.dhall\nin Package.Type\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.dhall", "*.dhall"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:workflow.dhall"
        and str(row["target_node"]) == "file:package.dhall"
        for row in graph_rows
    )

    package_symbol_id = symbol_ids[("workflow.dhall", "Package")]
    type_symbol_id = symbol_ids[("package.dhall", "Type")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{package_symbol_id}"
        and str(row["target_node"]) == f"symbol:{type_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_coq_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "coq-dependency-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "_CoqProject").write_text(
        "-Q theories Demo\n"
        "theories/Main.v\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper : nat := 0.\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Main.v").write_text(
        "Require Import Helper.\n"
        "Lemma run : nat.\n"
        "Proof.\n"
        "  exact helper.\n"
        "Qed.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["theories", "_CoqProject"],
            include_patterns=["theories/**/*.v", "_CoqProject"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:theories/Main.v"
        and str(row["target_node"]) == "file:theories/Helper.v"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("theories/Main.v", "run")]
    helper_symbol_id = symbol_ids[("theories/Helper.v", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_lean_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "lean-dependency-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    (repo_path / "lean-toolchain").write_text(
        "leanprover/lean4:stable\n",
        encoding="utf-8",
    )
    (repo_path / "lakefile.lean").write_text(
        "package batteries where\n\n"
        "lean_lib Batteries\n",
        encoding="utf-8",
    )
    (repo_path / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 0\n",
        encoding="utf-8",
    )
    (repo_path / "Batteries" / "Main.lean").write_text(
        "import Batteries.Helper\n\n"
        "def run : Nat := Batteries.Helper.helper\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Batteries", "lean-toolchain", "lakefile.lean"],
            include_patterns=["Batteries/**/*.lean", "lean-toolchain", "lakefile.lean"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:Batteries/Main.lean"
        and str(row["target_node"]) == "file:Batteries/Helper.lean"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("Batteries/Main.lean", "run")]
    helper_symbol_id = symbol_ids[("Batteries/Helper.lean", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_glsl_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "glsl-dependency-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "lib" / "noise.glsl").write_text(
        "float noise() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.frag").write_text(
        '#version 300 es\n'
        '#include "./lib/noise.glsl"\n'
        "float render() {\n"
        "  return noise();\n"
        "}\n"
        "void main() {}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.glsl", "src/**/*.frag"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "includes"
        and str(row["source_node"]) == "file:src/main.frag"
        and str(row["target_node"]) == "file:src/lib/noise.glsl"
        for row in graph_rows
    )

    render_symbol_id = symbol_ids[("src/main.frag", "render")]
    noise_symbol_id = symbol_ids[("src/lib/noise.glsl", "noise")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{render_symbol_id}"
        and str(row["target_node"]) == f"symbol:{noise_symbol_id}"
        for row in graph_rows
    )

def test_parse_shell_dependencies_only_follows_source_and_filters_builtins() -> None:
    dependencies = repository_service._parse_shell_dependencies_only(
        "scripts/main.sh",
        '. ../lib/util.zsh\n'
        "run() {\n"
        "  helper\n"
        "  printf '%s\\n' ok\n"
        "}\n",
        {
            "lib/util.zsh": "lib/util.zsh",
            "lib/util": "lib/util.zsh",
        },
    )

    assert any(
        dependency.dependency_type == "imports"
        and dependency.target_file == "lib/util.zsh"
        for dependency in dependencies
    )
    assert any(
        dependency.dependency_type == "references"
        and dependency.target_file == "lib/util.zsh"
        and dependency.target_symbol == "helper"
        for dependency in dependencies
    )
    assert not any(
        dependency.dependency_type == "references"
        and dependency.target_symbol == "printf"
        for dependency in dependencies
    )


def test_repository_snapshot_graph_contains_shell_source_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "shell-dependency-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "lib" / "util.zsh").write_text(
        "helper() {\n"
        "  echo ok\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.sh").write_text(
        "#!/usr/bin/env bash\n"
        ". ../lib/util.zsh\n"
        "run() {\n"
        "  helper\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts", "lib"],
            include_patterns=["scripts/*.sh", "lib/*.zsh"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:scripts/main.sh"
        and str(row["target_node"]) == "file:lib/util.zsh"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("scripts/main.sh", "run")]
    helper_symbol_id = symbol_ids[("lib/util.zsh", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_parse_powershell_dependencies_only_follows_imports_and_filters_builtins() -> None:
    dependencies = repository_service._parse_powershell_dependencies_only(
        "Public/Main.ps1",
        'Import-Module "$PSScriptRoot/../Private/Helpers.ps1"\n'
        "function Invoke-Main {\n"
        "  Get-Helper\n"
        "  Write-Verbose 'ok'\n"
        "}\n",
        {
            "Private/Helpers.ps1": "Private/Helpers.ps1",
            "Private/Helpers": "Private/Helpers.ps1",
        },
    )

    assert any(
        dependency.dependency_type == "imports"
        and dependency.target_file == "Private/Helpers.ps1"
        for dependency in dependencies
    )
    assert any(
        dependency.dependency_type == "references"
        and dependency.target_file == "Private/Helpers.ps1"
        and dependency.target_symbol == "Get-Helper"
        for dependency in dependencies
    )
    assert not any(
        dependency.dependency_type == "references"
        and dependency.target_symbol == "Write-Verbose"
        for dependency in dependencies
    )


def test_repository_snapshot_graph_contains_powershell_import_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "powershell-dependency-repo"
    (repo_path / "Private").mkdir(parents=True)
    (repo_path / "Private" / "Helpers.ps1").write_text(
        "function Get-Helper {\n"
        "  return 'ok'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Module.psm1").write_text(
        '. "$PSScriptRoot/Private/Helpers.ps1"\n'
        "function Invoke-Main {\n"
        "  Get-Helper\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Module.psm1", "Private"],
            include_patterns=["*.psm1", "Private/*.ps1"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:Module.psm1"
        and str(row["target_node"]) == "file:Private/Helpers.ps1"
        for row in graph_rows
    )

    invoke_symbol_id = symbol_ids[("Module.psm1", "Invoke-Main")]
    helper_symbol_id = symbol_ids[("Private/Helpers.ps1", "Get-Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{invoke_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_erlang_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "erlang-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "rebar.config").write_text("{erl_opts, [debug_info]}.\n", encoding="utf-8")
    (repo_path / "src" / "acme_util.erl").write_text(
        "-module(acme_util).\n"
        "-export([helper/0]).\n"
        "helper() -> ok.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.erl").write_text(
        "-module(acme).\n"
        "-export([run/0]).\n"
        "run() -> acme_util:helper().\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.erl", "src/**/*.hrl", "rebar.config"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:src/acme.erl"
        and str(row["target_node"]) == "file:src/acme_util.erl"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/acme.erl", "run")]
    helper_symbol_id = symbol_ids[("src/acme_util.erl", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_nim_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "nim-dependency-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "acme.nimble").write_text("version = \"0.1.0\"\n", encoding="utf-8")
    (repo_path / "src" / "acme" / "util.nim").write_text(
        "proc helper*(): string =\n"
        "  \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.nim").write_text(
        "import acme/util\n"
        "proc run*(): string =\n"
        "  util.helper()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.nim", "*.nimble", "config.nims"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:src/acme.nim"
        and str(row["target_node"]) == "file:src/acme/util.nim"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/acme.nim", "run")]
    helper_symbol_id = symbol_ids[("src/acme/util.nim", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_nim_plain_import_and_same_file_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "nim-symbol-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "acme.nimble").write_text("version = \"0.1.0\"\n", encoding="utf-8")
    (repo_path / "src" / "acme" / "util.nim").write_text(
        "proc helper*(): string =\n"
        "  \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.nim").write_text(
        "import acme/util\n"
        "proc localHelper*(): string =\n"
        "  \"local\"\n"
        "proc wrap*(): string =\n"
        "  helper()\n"
        "proc run*(): string =\n"
        "  localHelper()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.nim", "*.nimble", "config.nims"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    wrap_symbol_id = symbol_ids[("src/acme.nim", "wrap")]
    run_symbol_id = symbol_ids[("src/acme.nim", "run")]
    helper_symbol_id = symbol_ids[("src/acme/util.nim", "helper")]
    local_helper_symbol_id = symbol_ids[("src/acme.nim", "localHelper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{wrap_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{local_helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_ocaml_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ocaml-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "dune-project").write_text("(lang dune 3.0)\n", encoding="utf-8")
    (repo_path / "src" / "util.ml").write_text(
        "let helper () = 1\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.ml").write_text(
        "let run () = Util.helper ()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.ml", "src/*.ml", "dune-project", "**/dune", "*.opam"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:src/main.ml"
        and str(row["target_node"]) == "file:src/util.ml"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/main.ml", "run")]
    helper_symbol_id = symbol_ids[("src/util.ml", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_perl_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "perl-dependency-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "cpanfile").write_text("requires 'strict';\n", encoding="utf-8")
    (repo_path / "lib" / "My" / "Util.pm").write_text(
        "package My::Util;\n"
        "sub helper { 1 }\n"
        "1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\n"
        "use My::Util;\n"
        "sub run { My::Util->helper() }\n"
        "1;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=[
                "lib/**/*.pm",
                "lib/*.pm",
                "cpanfile",
                "Makefile.PL",
                "Build.PL",
                "dist.ini",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:lib/My/Main.pm"
        and str(row["target_node"]) == "file:lib/My/Util.pm"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("lib/My/Main.pm", "run")]
    helper_symbol_id = symbol_ids[("lib/My/Util.pm", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_perl_imported_call_and_parent_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "perl-imported-call-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "cpanfile").write_text("requires 'strict';\n", encoding="utf-8")
    (repo_path / "lib" / "My" / "Base.pm").write_text(
        "package My::Base;\n"
        "sub parent_method { 1 }\n"
        "1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Util.pm").write_text(
        "package My::Util;\n"
        "sub helper { 1 }\n"
        "1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\n"
        "use parent 'My::Base';\n"
        "use My::Util qw(helper);\n"
        "sub run { helper() }\n"
        "1;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=[
                "lib/**/*.pm",
                "lib/*.pm",
                "cpanfile",
                "Makefile.PL",
                "Build.PL",
                "dist.ini",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:lib/My/Main.pm"
        and str(row["target_node"]) == "file:lib/My/Base.pm"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:lib/My/Main.pm"
        and str(row["target_node"]) == "file:lib/My/Util.pm"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("lib/My/Main.pm", "run")]
    helper_symbol_id = symbol_ids[("lib/My/Util.pm", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_r_package_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "r-package-graph-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    (repo_path / "R" / "helper.R").write_text(
        "helper <- function() {\n"
        "  1\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "main.R").write_text(
        "run <- function() {\n"
        "  helper()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["R", "DESCRIPTION", "NAMESPACE"],
            include_patterns=["R/**/*.R", "R/*.R", "DESCRIPTION", "NAMESPACE"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("R/main.R", "run")]
    helper_symbol_id = symbol_ids[("R/helper.R", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_ignores_r_builtin_collisions_for_unqualified_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "r-package-builtins-graph-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    (repo_path / "R" / "builtin-shadow.R").write_text(
        "names <- function(x) {\n"
        "  x\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "helper.R").write_text(
        "helper <- function(x) {\n"
        "  x\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "main.R").write_text(
        "run <- function(x) {\n"
        "  names(x)\n"
        "  helper(x)\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["R", "DESCRIPTION", "NAMESPACE"],
            include_patterns=["R/**/*.R", "R/*.R", "DESCRIPTION", "NAMESPACE"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("R/main.R", "run")]
    helper_symbol_id = symbol_ids[("R/helper.R", "helper")]
    builtin_shadow_symbol_id = symbol_ids[("R/builtin-shadow.R", "names")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert not any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{builtin_shadow_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_julia_include_and_import_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "julia-package-graph-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project.toml").write_text(
        'name = "Acme"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.jl").write_text(
        "module Helper\n"
        "helper() = 1\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme.jl").write_text(
        'module Acme\ninclude("Helper.jl")\nusing .Helper: helper\n\nfunction run()\n'
        "  helper()\n"
        "end\nend\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "Project.toml"],
            include_patterns=["src/**/*.jl", "src/*.jl", "Project.toml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/Acme.jl"
        and str(row["target_node"]) == "file:src/Helper.jl"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/Acme.jl", "run")]
    helper_symbol_id = symbol_ids[("src/Helper.jl", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_julia_package_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "julia-package-symbol-graph-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project.toml").write_text(
        'name = "Acme"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.jl").write_text(
        "helper() = 1\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Runner.jl").write_text(
        "run() = helper()\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme.jl").write_text(
        'module Acme\ninclude("Helper.jl")\ninclude("Runner.jl")\nend\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "Project.toml"],
            include_patterns=["src/**/*.jl", "src/*.jl", "Project.toml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("src/Runner.jl", "run")]
    helper_symbol_id = symbol_ids[("src/Helper.jl", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_ignores_julia_constructor_calls_for_operational_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "julia-package-constructor-graph-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project.toml").write_text(
        'name = "Acme"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Types.jl").write_text(
        "struct HelperType\n  value::Int\nend\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Runner.jl").write_text(
        "make_type() = HelperType(1)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme.jl").write_text(
        'module Acme\ninclude("Types.jl")\ninclude("Runner.jl")\nend\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "Project.toml"],
            include_patterns=["src/**/*.jl", "src/*.jl", "Project.toml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    make_type_symbol_id = symbol_ids[("src/Runner.jl", "make_type")]
    helper_type_symbol_id = symbol_ids[("src/Types.jl", "HelperType")]
    assert not any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{make_type_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_type_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_crystal_wildcard_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "crystal-dependency-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shard.yml").write_text(
        "name: acme\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "helper.cr").write_text(
        "module Acme::Helper\n"
        "  def self.helper : Int32\n"
        "    1\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.cr").write_text(
        'require "./acme/*"\n\n'
        "module Acme\n"
        "  def self.run : Int32\n"
        "    Acme::Helper.helper\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "shard.yml"],
            include_patterns=["src/**/*.cr", "src/*.cr", "shard.yml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/acme.cr"
        and str(row["target_node"]) == "file:src/acme/helper.cr"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/acme.cr", "run")]
    helper_symbol_id = symbol_ids[("src/acme/helper.cr", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_crystal_constructor_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "crystal-constructor-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shard.yml").write_text(
        "name: acme\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "options.cr").write_text(
        "module Acme\n"
        "  class Options\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "runner.cr").write_text(
        "module Acme\n"
        "  class Runner\n"
        "    def initialize(options : Options)\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.cr").write_text(
        'require "./acme/*"\n\n'
        "module Acme\n"
        "  def self.build : Runner\n"
        "    Runner.new(Options.new)\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "shard.yml"],
            include_patterns=["src/**/*.cr", "src/*.cr", "shard.yml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    build_symbol_id = symbol_ids[("src/acme.cr", "build")]
    options_symbol_id = symbol_ids[("src/acme/options.cr", "Options")]
    runner_symbol_id = symbol_ids[("src/acme/runner.cr", "Runner")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{options_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{runner_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_crystal_type_annotation_and_mixin_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "crystal-type-annotation-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shard.yml").write_text(
        "name: acme\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "base_runner.cr").write_text(
        "module Acme\n"
        "  class BaseRunner\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "serializable.cr").write_text(
        "module Acme\n"
        "  module Serializable\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "options.cr").write_text(
        "module Acme\n"
        "  class Options\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "runner.cr").write_text(
        "module Acme\n"
        "  class Runner < BaseRunner\n"
        "    include Serializable\n"
        "    def initialize(options : Options)\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "shard.yml"],
            include_patterns=["src/**/*.cr", "src/*.cr", "shard.yml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    runner_symbol_id = symbol_ids[("src/acme/runner.cr", "Runner")]
    initialize_symbol_id = symbol_ids[("src/acme/runner.cr", "initialize")]
    base_runner_symbol_id = symbol_ids[("src/acme/base_runner.cr", "BaseRunner")]
    serializable_symbol_id = symbol_ids[("src/acme/serializable.cr", "Serializable")]
    options_symbol_id = symbol_ids[("src/acme/options.cr", "Options")]

    for target_symbol_id in (base_runner_symbol_id, serializable_symbol_id):
        assert any(
            str(row["edge_type"]) == "references_symbol"
            and str(row["source_node"]) == f"symbol:{runner_symbol_id}"
            and str(row["target_node"]) == f"symbol:{target_symbol_id}"
            for row in graph_rows
        )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{initialize_symbol_id}"
        and str(row["target_node"]) == f"symbol:{options_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_php_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "php-dependency-repo"
    (repo_path / "app" / "Models").mkdir(parents=True)
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "app" / "Models" / "User.php").write_text("<?php\n", encoding="utf-8")
    (repo_path / "public" / "index.php").write_text(
        "<?php\nuse App\\\\Models\\\\User;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["app", "public"],
            include_patterns=["app/**/*.php", "public/*.php", "public/**/*.php"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:public/index.php"
        and str(row["target_node"]) == "file:app/Models/User.php"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_php_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "php-symbol-repo"
    (repo_path / "app" / "Models").mkdir(parents=True)
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "app" / "Models" / "User.php").write_text(
        "<?php\n"
        "namespace App\\Models;\n"
        "class User {\n"
        "    public static function make(): User {\n"
        "        return new User();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "public" / "index.php").write_text(
        "<?php\n"
        "namespace App;\n"
        "use App\\Models\\User;\n"
        "class Entry {\n"
        "    public function run(): User {\n"
        "        return User::make();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["app", "public"],
            include_patterns=["app/**/*.php", "public/*.php", "public/**/*.php"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("public/index.php", "run")]
    make_symbol_id = symbol_ids[("app/Models/User.php", "make")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{make_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_deduplicates_resolved_php_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "php-dedup-symbol-repo"
    (repo_path / "app" / "Models").mkdir(parents=True)
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "app" / "Models" / "User.php").write_text(
        "<?php\n"
        "namespace App\\Models;\n"
        "class User {}\n",
        encoding="utf-8",
    )
    (repo_path / "public" / "index.php").write_text(
        "<?php\n"
        "namespace App;\n"
        "use App\\Models\\User;\n"
        "class Entry {\n"
        "    public function run(): array {\n"
        "        return [User::ADMIN, User::MEMBER];\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["app", "public"],
            include_patterns=["app/**/*.php", "public/*.php", "public/**/*.php"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("public/index.php", "run")]
    user_symbol_id = symbol_ids[("app/Models/User.php", "User")]
    matching_edges = [
        row
        for row in graph_rows
        if str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{user_symbol_id}"
    ]
    assert len(matching_edges) == 1


def test_repository_snapshot_graph_contains_php_trait_docblock_and_type_hint_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "php-rich-symbol-repo"
    (repo_path / "app" / "Models").mkdir(parents=True)
    (repo_path / "app" / "Traits").mkdir(parents=True)
    (repo_path / "database" / "Factories").mkdir(parents=True)
    (repo_path / "app" / "Models" / "User.php").write_text(
        "<?php\n"
        "namespace App\\Models;\n"
        "class User {}\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "Traits" / "HasAudit.php").write_text(
        "<?php\n"
        "namespace App\\Traits;\n"
        "trait HasAudit {}\n",
        encoding="utf-8",
    )
    (repo_path / "database" / "Factories" / "UserFactory.php").write_text(
        "<?php\n"
        "namespace Database\\Factories;\n"
        "class UserFactory {}\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "Models" / "AuditedUser.php").write_text(
        "<?php\n"
        "namespace App\\Models;\n"
        "use App\\Traits\\HasAudit;\n"
        "use Database\\Factories\\UserFactory;\n"
        "/** @use HasAudit<UserFactory> */\n"
        "class AuditedUser extends User {\n"
        "    use HasAudit;\n"
        "    public function __construct(private UserFactory $factory) {}\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["app", "database"],
            include_patterns=["app/**/*.php", "database/**/*.php"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    audited_user_symbol_id = symbol_ids[("app/Models/AuditedUser.php", "AuditedUser")]
    user_symbol_id = symbol_ids[("app/Models/User.php", "User")]
    has_audit_symbol_id = symbol_ids[("app/Traits/HasAudit.php", "HasAudit")]
    user_factory_symbol_id = symbol_ids[
        ("database/Factories/UserFactory.php", "UserFactory")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{audited_user_symbol_id}"
        and str(row["target_node"]) == f"symbol:{user_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{audited_user_symbol_id}"
        and str(row["target_node"]) == f"symbol:{has_audit_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{audited_user_symbol_id}"
        and str(row["target_node"]) == f"symbol:{user_factory_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_elixir_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "elixir-dependency-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "lib" / "acme" / "repo.ex").write_text("defmodule Acme.Repo do\nend\n", encoding="utf-8")
    (repo_path / "lib" / "acme.ex").write_text(
        "defmodule Acme do\n  alias Acme.Repo\nend\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=["lib/*.ex", "lib/**/*.ex"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:lib/acme.ex"
        and str(row["target_node"]) == "file:lib/acme/repo.ex"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_elixir_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "elixir-symbol-graph-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "lib" / "acme" / "repo.ex").write_text(
        "defmodule Acme.Repo do\n"
        "  def format_value do\n"
        "    :ok\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme.ex").write_text(
        "defmodule Acme do\n"
        "  alias Acme.Repo\n"
        "\n"
        "  def run do\n"
        "    Repo.format_value()\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=["lib/*.ex", "lib/**/*.ex"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("lib/acme.ex", "run")]
    format_value_symbol_id = symbol_ids[("lib/acme/repo.ex", "format_value")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{format_value_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_grouped_elixir_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "elixir-grouped-dependency-repo"
    (repo_path / "lib" / "phx_new").mkdir(parents=True)
    (repo_path / "lib" / "mix" / "tasks").mkdir(parents=True)
    (repo_path / "lib" / "phx_new" / "generator.ex").write_text(
        "defmodule Phx.New.Generator do\nend\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "mix" / "tasks" / "phx.new.ex").write_text(
        "defmodule Mix.Tasks.Phx.New do\n"
        "  alias Phx.New.{Generator}\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=["lib/**/*.ex"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:lib/mix/tasks/phx.new.ex"
        and str(row["target_node"]) == "file:lib/phx_new/generator.ex"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_csharp_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "csharp-dependency-repo"
    (repo_path / "src" / "MediatR").mkdir(parents=True)
    (repo_path / "src" / "MediatR" / "Mediator.cs").write_text(
        "namespace MediatR; public sealed class Mediator {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "MediatR" / "Handler.cs").write_text(
        "using MediatR;\nnamespace MediatR; public sealed class Handler { private readonly Mediator _m = new(); }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.cs"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/MediatR/Handler.cs"
        and str(row["target_node"]).startswith("file:src/MediatR/")
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_csharp_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "csharp-symbol-repo"
    (repo_path / "src" / "MediatR").mkdir(parents=True)
    (repo_path / "src" / "MediatR" / "Mediator.cs").write_text(
        "namespace MediatR; public sealed class Mediator {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "MediatR" / "Handler.cs").write_text(
        "using MediatR;\n"
        "namespace MediatR; public sealed class Handler { private readonly Mediator _m = new(); }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.cs"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    handler_symbol_id = symbol_ids[("src/MediatR/Handler.cs", "Handler")]
    mediator_symbol_id = symbol_ids[("src/MediatR/Mediator.cs", "Mediator")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{handler_symbol_id}"
        and str(row["target_node"]) == f"symbol:{mediator_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_visual_basic_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "visual-basic-repo"
    (repo_path / "src" / "Acme").mkdir(parents=True)
    (repo_path / "src" / "Acme" / "Mediator.vb").write_text(
        "Namespace Acme\n"
        "Public Class Mediator\n"
        "End Class\n"
        "End Namespace\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme" / "Handler.vb").write_text(
        "Imports Acme.Mediator\n"
        "Namespace Acme\n"
        "Public Class Handler\n"
        "    Private ReadOnly _mediator As Mediator = New Mediator()\n"
        "End Class\n"
        "End Namespace\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.vb"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/Acme/Handler.vb"
        and str(row["target_node"]) == "file:src/Acme/Mediator.vb"
        for row in graph_rows
    )
    handler_symbol_id = symbol_ids[("src/Acme/Handler.vb", "Handler")]
    mediator_symbol_id = symbol_ids[("src/Acme/Mediator.vb", "Mediator")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{handler_symbol_id}"
        and str(row["target_node"]) == f"symbol:{mediator_symbol_id}"
        for row in graph_rows
    )


def test_visual_basic_adapter_module_aliases_include_namespace_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "visual-basic-alias-repo"
    (repo_path / "src" / "Acme").mkdir(parents=True)
    (repo_path / "src" / "Acme" / "Services.vb").write_text(
        "Namespace Acme.Core\n"
        "Public Class Mediator\n"
        "End Class\n"
        "End Namespace\n",
        encoding="utf-8",
    )

    aliases = repository_service.visual_basic_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Acme/Services.vb",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acme/services.vb" in aliases
    assert "src/acme/services" in aliases
    assert "src.acme.services" in aliases
    assert "acme.core" in aliases
    assert "acme.core.services" in aliases
    assert "acme.core.mediator" in aliases


def test_fortran_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "fortran-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "math_utils.f90").write_text(
        "module math_utils\n"
        "implicit none\n"
        "contains\n"
        "subroutine helper()\n"
        "end subroutine helper\n"
        "end module math_utils\n",
        encoding="utf-8",
    )

    aliases = repository_service.fortran_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/math_utils.f90",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "math_utils" in aliases
    assert "math_utils.helper" in aliases
    assert "helper" in aliases


def test_d_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "d-alias-repo"
    (repo_path / "source" / "acme").mkdir(parents=True)
    (repo_path / "source" / "acme" / "util.d").write_text(
        "module acme.util;\n"
        "struct Worker {}\n"
        "void helper() {}\n",
        encoding="utf-8",
    )

    aliases = repository_service.d_language_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="source/acme/util.d",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "acme.util" in aliases
    assert "util" in aliases
    assert "Worker" in aliases
    assert "acme.util.Worker" in aliases
    assert "acme.util.helper" in aliases


def test_ada_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "ada-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "acme-util.adb").write_text(
        "package body Acme.Util is\n"
        "   procedure Helper is\n"
        "   begin\n"
        "      null;\n"
        "   end Helper;\n"
        "end Acme.Util;\n",
        encoding="utf-8",
    )

    aliases = repository_service.ada_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/acme-util.adb",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acme-util.adb" in aliases
    assert "src/acme-util" in aliases
    assert "acme.util" in aliases
    assert "util" in aliases
    assert "acme.util.helper" in aliases


def test_ada_adapter_preserves_unresolved_binding_targets_as_none() -> None:
    file_path = "src/main.adb"
    text = (
        "with Missing.Util;\n"
        "procedure Main is\n"
        "begin\n"
        "   Missing.Util.Helper;\n"
        "end Main;\n"
    )

    dependencies = repository_service.ada_adapter.parse_dependencies_only(
        file_path,
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        resolve_import=lambda import_target, module_index: None,
    )
    _, _, references = repository_service.ada_adapter.parse_file(
        file_path,
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        resolve_import=lambda import_target, module_index: None,
    )

    assert len(dependencies) == 1
    assert dependencies[0]["dependency_type"] == "imports"
    assert dependencies[0]["target_file"] is None
    assert references == ()


def test_assembly_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "assembly-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "boot.asm").write_text(
        "global start\n"
        "start:\n"
        "    call print_string\n"
        "    ret\n"
        "print_string:\n"
        "    ret\n",
        encoding="utf-8",
    )

    aliases = repository_service.assembly_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/boot.asm",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/boot.asm" in aliases
    assert "src/boot" in aliases
    assert "src.boot" in aliases
    assert "boot" in aliases
    assert "start" in aliases
    assert "boot.start" in aliases
    assert "print_string" in aliases


def test_prolog_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "prolog-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "family.pl").write_text(
        ":- module(family, [ancestor/2, parent/2]).\n"
        "parent(alice, bob).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )

    aliases = repository_service.prolog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/family.pl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/family.pl" in aliases
    assert "src/family" in aliases
    assert "src.family" in aliases
    assert "family" in aliases
    assert "ancestor" in aliases
    assert "family.ancestor" in aliases
    assert "family:ancestor" in aliases


def test_prolog_marker_detection_ignores_empty_directives() -> None:
    assert repository_prolog_primitives.has_prolog_markers("\t\t:-\n") is False


def test_foxpro_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "foxpro-alias-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "programs" / "report.prg").write_text(
        "DEFINE CLASS JsonRunner AS Custom\n"
        "ENDDEFINE\n"
        "FUNCTION Helper()\n"
        "    RETURN 1\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )

    aliases = repository_service.foxpro_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="programs/report.prg",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "programs/report.prg" in aliases
    assert "programs/report" in aliases
    assert "programs.report" in aliases
    assert "report" in aliases
    assert "helper" in aliases
    assert "report.helper" in aliases
    assert "jsonrunner" in aliases


def test_solidity_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "solidity-alias-repo"
    (repo_path / "src" / "access").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        '{"name":"solidity-alias-repo"}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "access" / "Ownable.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "abstract contract Ownable {\n"
        "    function owner() public view returns (address) {}\n"
        "}\n"
        "interface IOwnable {\n"
        "    function owner() external view returns (address);\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.solidity_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/access/Ownable.sol",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/access/Ownable.sol" in aliases
    assert "src/access/Ownable" in aliases
    assert "src.access.Ownable" in aliases
    assert "access/Ownable.sol" in aliases
    assert "access/Ownable" in aliases
    assert "solidity-alias-repo/access/Ownable.sol" in aliases
    assert "Ownable" in aliases
    assert "IOwnable" in aliases
    assert "owner" in aliases


def test_systemverilog_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "systemverilog-alias-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "top.sv").write_text(
        "package util_pkg;\n"
        "endpackage\n"
        "module top;\n"
        "endmodule\n",
        encoding="utf-8",
    )

    aliases = repository_service.systemverilog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rtl/top.sv",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rtl/top.sv" in aliases
    assert "rtl/top" in aliases
    assert "rtl.top" in aliases
    assert "top" in aliases
    assert "module:top" in aliases
    assert "util_pkg" in aliases
    assert "package:util_pkg" in aliases


def test_verilog_adapter_module_aliases_include_module_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "verilog-alias-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "top.v").write_text(
        "module top;\n"
        "  function helper;\n"
        "  endfunction\n"
        "endmodule\n",
        encoding="utf-8",
    )

    aliases = repository_service.verilog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rtl/top.v",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rtl/top.v" in aliases
    assert "rtl/top" in aliases
    assert "rtl.top" in aliases
    assert "top" in aliases
    assert "module:top" in aliases


def test_actionscript_adapter_module_aliases_include_package_type_and_method_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "actionscript-alias-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "app" / "Main.as").write_text(
        "package demo.app {\n"
        "    public class Main {\n"
        "        public function boot():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.actionscript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/app/Main.as",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/app/Main.as" in aliases
    assert "src/demo/app/Main" in aliases
    assert "src.demo.app.Main" in aliases
    assert "Main" in aliases
    assert "demo.app" in aliases
    assert "package:demo.app" in aliases
    assert "demo.app.Main" in aliases
    assert "class:Main" in aliases
    assert "class:demo.app.Main" in aliases
    assert "boot" in aliases
    assert "Main.boot" in aliases
    assert "demo.app.Main.boot" in aliases


def test_awk_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "awk-alias-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "math.awk").write_text(
        "function add(a, b) {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.awk_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="lib/math.awk",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "lib/math.awk" in aliases
    assert "lib/math" in aliases
    assert "lib.math" in aliases
    assert "math" in aliases
    assert "add" in aliases
    assert "math.add" in aliases


def test_coffeescript_adapter_module_aliases_include_class_and_function_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coffeescript-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.coffee").write_text(
        "class App\n"
        "  boot: ->\n"
        "    true\n"
        "\n"
        "renderJson = ->\n"
        "  '{}'\n"
        "\n"
        "exports.compile = ->\n"
        "  true\n",
        encoding="utf-8",
    )

    aliases = repository_service.coffeescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.coffee",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/main.coffee" in aliases
    assert "src/main" in aliases
    assert "src.main" in aliases
    assert "main" in aliases
    assert "App" in aliases
    assert "boot" in aliases
    assert "renderJson" in aliases
    assert "compile" in aliases
    assert "main.boot" in aliases
    assert "main.renderJson" in aliases
    assert "main.compile" in aliases


def test_vala_adapter_module_aliases_include_namespace_type_and_method_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vala-alias-repo"
    (repo_path / "src" / "App").mkdir(parents=True)
    (repo_path / "src" / "App" / "MainWindow.vala").write_text(
        "namespace Demo.App {\n"
        "    public class MainWindow : Object {\n"
        "        public void present_window () {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.vala_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/App/MainWindow.vala",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/App/MainWindow.vala" in aliases
    assert "src/App/MainWindow" in aliases
    assert "src.app.mainwindow" in aliases
    assert "MainWindow" in aliases
    assert "demo.app" in aliases
    assert "Demo.App.MainWindow" in aliases
    assert "present_window" in aliases
    assert "Demo.App.MainWindow.present_window" in aliases


def test_mql5_adapter_module_aliases_include_type_and_function_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mql5-alias-repo"
    (repo_path / "Experts").mkdir(parents=True)
    (repo_path / "Experts" / "Main.mq5").write_text(
        "class Helper\n"
        "{\n"
        "public:\n"
        "   string RenderJson()\n"
        "     {\n"
        '      return "{}";\n'
        "     }\n"
        "};\n"
        "\n"
        "void OnStart()\n"
        "{\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.mql5_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Experts/Main.mq5",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Experts/Main.mq5" in aliases
    assert "Experts/Main" in aliases
    assert "Experts.Main" in aliases
    assert "Main" in aliases
    assert "Helper" in aliases
    assert "RenderJson" in aliases
    assert "OnStart" in aliases
    assert "Helper.RenderJson" in aliases
    assert "Main.OnStart" in aliases


def test_gams_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "gams-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "main.gms").write_text(
        "$include ../include/common.inc\n"
        "set i /a,b/;\n"
        "parameter cost(i);\n"
        "equation balance;\n"
        "balance.. cost('a') =e= 1;\n",
        encoding="utf-8",
    )

    aliases = repository_service.gams_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/main.gms",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "models/main.gms" in aliases
    assert "models/main" in aliases
    assert "models.main" in aliases
    assert "main" in aliases
    assert "i" in aliases
    assert "cost" in aliases
    assert "balance" in aliases
    assert "main.balance" in aliases


def test_nix_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "nix-alias-repo"
    (repo_path / "nix").mkdir(parents=True)
    (repo_path / "nix" / "formatter.nix").write_text(
        "{ pkgs }:\n"
        "let\n"
        "  mkFormatter = package: package;\n"
        "in {\n"
        "  mkFormatter = mkFormatter;\n"
        "  formatter = mkFormatter pkgs.alejandra;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.nix_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="nix/formatter.nix",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "nix/formatter.nix" in aliases
    assert "nix/formatter" in aliases
    assert "nix.formatter" in aliases
    assert "formatter" in aliases
    assert "mkFormatter" in aliases
    assert "formatter.mkFormatter" in aliases


def test_openscad_adapter_module_aliases_include_module_and_function_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "openscad-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "helpers.scad").write_text(
        "module shelf(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n"
        "function render_profile(value) = value + 1;\n",
        encoding="utf-8",
    )

    aliases = repository_service.openscad_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/helpers.scad",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "models/helpers.scad" in aliases
    assert "models/helpers" in aliases
    assert "models.helpers" in aliases
    assert "shelf" in aliases
    assert "render_profile" in aliases
    assert "helpers.shelf" in aliases
    assert "helpers.render_profile" in aliases


def test_purescript_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "purescript-alias-repo"
    (repo_path / "src" / "Control").mkdir(parents=True)
    (repo_path / "src" / "Control" / "Helper.purs").write_text(
        "module Control.Helper where\n"
        "\n"
        "data Helper = Helper\n"
        "\n"
        "renderJson :: String\n"
        "renderJson = \"{}\"\n",
        encoding="utf-8",
    )

    aliases = repository_service.purescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Control/Helper.purs",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Control/Helper.purs" in aliases
    assert "src/Control/Helper" in aliases
    assert "src.Control.Helper" in aliases
    assert "Control.Helper" in aliases
    assert "renderJson" in aliases
    assert "Helper" in aliases
    assert "Control.Helper.renderJson" in aliases


def test_gleam_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gleam-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "helper.gleam").write_text(
        "pub type Helper {\n  Helper\n}\n\npub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )

    aliases = repository_service.gleam_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/helper.gleam",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/helper.gleam" in aliases
    assert "src/demo/helper" in aliases
    assert "src.demo.helper" in aliases
    assert "demo/helper" in aliases
    assert "demo.helper" in aliases
    assert "render_json" in aliases
    assert "Helper" in aliases
    assert "demo.helper.render_json" in aliases


def test_janet_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "janet-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "init.janet").write_text(
        "(defn render-json [] @{})\n(def helper-state @{})\n",
        encoding="utf-8",
    )

    aliases = repository_service.janet_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/init.janet",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/init.janet" in aliases
    assert "src/demo/init" in aliases
    assert "src.demo.init" in aliases
    assert "init" in aliases
    assert "demo" in aliases
    assert "render-json" in aliases
    assert "helper-state" in aliases
    assert "demo/render-json" in aliases
    assert "demo.render-json" in aliases


def test_dhall_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dhall-alias-repo"
    (repo_path / "schemas" / "Step").mkdir(parents=True)
    (repo_path / "schemas" / "Step" / "package.dhall").write_text(
        "{ Type = \"step\", default = \"run\" }\n",
        encoding="utf-8",
    )

    aliases = repository_service.dhall_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="schemas/Step/package.dhall",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "schemas/Step/package.dhall" in aliases
    assert "schemas/Step/package" in aliases
    assert "schemas.Step.package" in aliases
    assert "schemas/Step" in aliases
    assert "schemas.Step" in aliases
    assert "Step" in aliases
    assert "Type" in aliases
    assert "default" in aliases
    assert "schemas/Step.Type" in aliases
    assert "schemas.Step.Type" in aliases


def test_puppet_adapter_module_aliases_include_manifest_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "puppet-alias-repo"
    (repo_path / "manifests").mkdir(parents=True)
    (repo_path / "metadata.json").write_text(
        '{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        encoding="utf-8",
    )
    (repo_path / "manifests" / "params.pp").write_text(
        "class apache::params { }\n",
        encoding="utf-8",
    )

    aliases = repository_service.puppet_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="manifests/params.pp",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "manifests/params.pp" in aliases
    assert "manifests/params" in aliases
    assert "manifests::params" in aliases
    assert "params" in aliases
    assert "apache::params" in aliases
    assert "apache/params" in aliases
    assert "apache.params" in aliases


def test_coq_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coq-alias-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper : nat := 0.\n",
        encoding="utf-8",
    )

    aliases = repository_service.coq_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="theories/Helper.v",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "theories/Helper.v" in aliases
    assert "theories.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases


def test_lean_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lean-alias-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    (repo_path / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 0\n",
        encoding="utf-8",
    )

    aliases = repository_service.lean_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Batteries/Helper.lean",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Batteries/Helper.lean" in aliases
    assert "Batteries.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases


def test_repository_intelligence_dhall_helpers_are_modularized() -> None:
    assert repository_service.dhall_adapter.strip_comments is (
        repository_dhall_primitives.strip_comments
    )
    assert repository_service.dhall_adapter.has_dhall_path_hints is (
        repository_dhall_primitives.has_dhall_path_hints
    )
    assert repository_service.dhall_adapter.is_probable_dhall_source is (
        repository_dhall_analysis_support.is_probable_dhall_source
    )
    assert repository_service.dhall_adapter.parse_import_statements is (
        repository_dhall_primitives.parse_import_statements
    )
    assert repository_service.dhall_adapter.parse_bound_import_statements is (
        repository_dhall_primitives.parse_bound_import_statements
    )
    assert repository_service.dhall_adapter.resolve_import is (
        repository_dhall_analysis_support.resolve_import
    )
    assert repository_service.dhall_adapter.module_aliases_for_path is (
        repository_dhall_analysis_support.module_aliases_for_path
    )
    assert repository_service.dhall_adapter.parse_dependencies_only is (
        repository_dhall_analysis_support.parse_dependencies_only
    )
    assert repository_service.dhall_adapter.parse_file is (
        repository_dhall_analysis_support.parse_file
    )
    assert repository_service._parse_dhall_dependencies_only is (
        repository_dhall_parser_dispatch._parse_dhall_dependencies_only
    )
    assert repository_service._parse_dhall_file is (
        repository_dhall_parser_dispatch._parse_dhall_file
    )


def test_repository_intelligence_coq_helpers_are_modularized() -> None:
    assert repository_service.coq_adapter.strip_comments is (
        repository_coq_primitives.strip_comments
    )
    assert repository_service.coq_adapter.has_coq_path_hints is (
        repository_coq_primitives.has_coq_path_hints
    )
    assert repository_service.coq_adapter.parse_require_modules is (
        repository_coq_primitives.parse_require_modules
    )
    assert repository_service.coq_adapter.parse_project_roots is (
        repository_coq_primitives.parse_project_roots
    )
    assert repository_service.coq_adapter.parse_project_sources is (
        repository_coq_primitives.parse_project_sources
    )
    assert repository_service.coq_adapter.is_probable_coq_source is (
        repository_coq_analysis_support.is_probable_coq_source
    )
    assert repository_service.coq_adapter.resolve_require_target is (
        repository_coq_analysis_support.resolve_require_target
    )
    assert repository_service.coq_adapter.module_aliases_for_path is (
        repository_coq_analysis_support.module_aliases_for_path
    )
    assert repository_service.coq_adapter.parse_dependencies_only is (
        repository_coq_analysis_support.parse_dependencies_only
    )
    assert repository_service.coq_adapter.parse_file is (
        repository_coq_analysis_support.parse_file
    )
    assert repository_service._parse_coq_dependencies_only is (
        repository_coq_parser_dispatch._parse_coq_dependencies_only
    )
    assert repository_service._parse_coq_file is (
        repository_coq_parser_dispatch._parse_coq_file
    )


def test_repository_intelligence_lean_helpers_are_modularized() -> None:
    assert repository_service.lean_adapter.strip_comments is (
        repository_lean_primitives.strip_comments
    )
    assert repository_service.lean_adapter.has_lean_path_hints is (
        repository_lean_primitives.has_lean_path_hints
    )
    assert repository_service.lean_adapter.parse_import_modules is (
        repository_lean_primitives.parse_import_modules
    )
    assert repository_service.lean_adapter.parse_package_names is (
        repository_lean_primitives.parse_package_names
    )
    assert repository_service.lean_adapter.is_probable_lean_source is (
        repository_lean_analysis_support.is_probable_lean_source
    )
    assert repository_service.lean_adapter.resolve_import_target is (
        repository_lean_analysis_support.resolve_import_target
    )
    assert repository_service.lean_adapter.module_aliases_for_path is (
        repository_lean_analysis_support.module_aliases_for_path
    )
    assert repository_service.lean_adapter.parse_dependencies_only is (
        repository_lean_analysis_support.parse_dependencies_only
    )
    assert repository_service.lean_adapter.parse_file is (
        repository_lean_analysis_support.parse_file
    )
    assert repository_service._parse_lean_dependencies_only is (
        repository_lean_parser_dispatch._parse_lean_dependencies_only
    )
    assert repository_service._parse_lean_file is (
        repository_lean_parser_dispatch._parse_lean_file
    )


def test_repository_intelligence_glsl_helpers_are_modularized() -> None:
    assert repository_service.glsl_adapter.strip_comments is (
        repository_glsl_primitives.strip_comments
    )
    assert repository_service.glsl_adapter.has_glsl_path_hints is (
        repository_glsl_primitives.has_glsl_path_hints
    )
    assert repository_service.glsl_adapter.parse_include_statements is (
        repository_glsl_primitives.parse_include_statements
    )
    assert repository_service.glsl_adapter.parse_glslify_require_statements is (
        repository_glsl_primitives.parse_glslify_require_statements
    )
    assert repository_service.glsl_adapter.iter_symbol_entries is (
        repository_glsl_primitives.iter_symbol_entries
    )
    assert repository_service.glsl_adapter.iter_function_call_names is (
        repository_glsl_primitives.iter_function_call_names
    )
    assert repository_service.glsl_adapter.is_probable_glsl_source is (
        repository_glsl_analysis_support.is_probable_glsl_source
    )
    assert repository_service.glsl_adapter.module_aliases_for_path is (
        repository_glsl_analysis_support.module_aliases_for_path
    )
    assert repository_service.glsl_adapter.parse_dependencies_only is (
        repository_glsl_analysis_support.parse_dependencies_only
    )
    assert repository_service.glsl_adapter.parse_file is (
        repository_glsl_analysis_support.parse_file
    )
    assert repository_service._parse_glsl_dependencies_only is (
        repository_glsl_parser_dispatch._parse_glsl_dependencies_only
    )
    assert repository_service._parse_glsl_file is (
        repository_glsl_parser_dispatch._parse_glsl_file
    )


def test_repository_intelligence_hlsl_helpers_are_modularized() -> None:
    assert repository_service.hlsl_adapter.strip_comments is (
        repository_hlsl_primitives.strip_comments
    )
    assert repository_service.hlsl_adapter.has_hlsl_path_hints is (
        repository_hlsl_primitives.has_hlsl_path_hints
    )
    assert repository_service.hlsl_adapter.parse_include_statements is (
        repository_hlsl_primitives.parse_include_statements
    )
    assert repository_service.hlsl_adapter.iter_symbol_entries is (
        repository_hlsl_primitives.iter_symbol_entries
    )
    assert repository_service.hlsl_adapter.iter_function_call_names is (
        repository_hlsl_primitives.iter_function_call_names
    )
    assert repository_service.hlsl_adapter.is_probable_hlsl_source is (
        repository_hlsl_analysis_support.is_probable_hlsl_source
    )
    assert repository_service.hlsl_adapter.module_aliases_for_path is (
        repository_hlsl_analysis_support.module_aliases_for_path
    )
    assert repository_service.hlsl_adapter.parse_dependencies_only is (
        repository_hlsl_analysis_support.parse_dependencies_only
    )
    assert repository_service.hlsl_adapter.parse_file is (
        repository_hlsl_analysis_support.parse_file
    )
    assert repository_service._parse_hlsl_dependencies_only is (
        repository_hlsl_parser_dispatch._parse_hlsl_dependencies_only
    )
    assert repository_service._parse_hlsl_file is (
        repository_hlsl_parser_dispatch._parse_hlsl_file
    )


def test_repository_intelligence_robotframework_helpers_are_modularized() -> None:
    assert repository_service.robotframework_adapter.strip_comments is (
        repository_robotframework_primitives.strip_comments
    )
    assert repository_service.robotframework_adapter.has_robotframework_path_hints is (
        repository_robotframework_primitives.has_robotframework_path_hints
    )
    assert repository_service.robotframework_adapter.iter_section_entries is (
        repository_robotframework_primitives.iter_section_entries
    )
    assert repository_service.robotframework_adapter.iter_resource_imports is (
        repository_robotframework_primitives.iter_resource_imports
    )
    assert repository_service.robotframework_adapter.iter_symbol_entries is (
        repository_robotframework_primitives.iter_symbol_entries
    )
    assert repository_service.robotframework_adapter.iter_keyword_call_entries is (
        repository_robotframework_primitives.iter_keyword_call_entries
    )
    assert repository_service.robotframework_adapter.source_symbol_name_for_line is (
        repository_robotframework_primitives.source_symbol_name_for_line
    )
    assert repository_service.robotframework_adapter.is_probable_robotframework_source is (
        repository_robotframework_analysis_support.is_probable_robotframework_source
    )
    assert repository_service.robotframework_adapter.module_aliases_for_path is (
        repository_robotframework_analysis_support.module_aliases_for_path
    )
    assert repository_service.robotframework_adapter.parse_dependencies_only is (
        repository_robotframework_analysis_support.parse_dependencies_only
    )
    assert repository_service.robotframework_adapter.parse_file is (
        repository_robotframework_analysis_support.parse_file
    )
    assert repository_service._parse_robotframework_dependencies_only is (
        repository_robotframework_parser_dispatch._parse_robotframework_dependencies_only
    )
    assert repository_service._parse_robotframework_file is (
        repository_robotframework_parser_dispatch._parse_robotframework_file
    )


def test_repository_intelligence_dockerfile_helpers_are_modularized() -> None:
    assert repository_service.dockerfile_adapter.strip_comments is (
        repository_dockerfile_primitives.strip_comments
    )
    assert repository_service.dockerfile_adapter.has_dockerfile_path_hints is (
        repository_dockerfile_primitives.has_dockerfile_path_hints
    )
    assert repository_service.dockerfile_adapter.iter_instruction_entries is (
        repository_dockerfile_primitives.iter_instruction_entries
    )
    assert repository_service.dockerfile_adapter.iter_stage_entries is (
        repository_dockerfile_primitives.iter_stage_entries
    )
    assert repository_service.dockerfile_adapter.iter_copy_add_entries is (
        repository_dockerfile_primitives.iter_copy_add_entries
    )
    assert repository_service.dockerfile_adapter.iter_run_local_path_entries is (
        repository_dockerfile_primitives.iter_run_local_path_entries
    )
    assert repository_service.dockerfile_adapter.source_symbol_name_for_line is (
        repository_dockerfile_primitives.source_symbol_name_for_line
    )
    assert repository_service.dockerfile_adapter.is_probable_dockerfile_source is (
        repository_dockerfile_analysis_support.is_probable_dockerfile_source
    )
    assert repository_service.dockerfile_adapter.module_aliases_for_path is (
        repository_dockerfile_analysis_support.module_aliases_for_path
    )
    assert repository_service.dockerfile_adapter.parse_dependencies_only is (
        repository_dockerfile_analysis_support.parse_dependencies_only
    )
    assert repository_service.dockerfile_adapter.parse_file is (
        repository_dockerfile_analysis_support.parse_file
    )
    assert repository_service._parse_dockerfile_dependencies_only is (
        repository_dockerfile_parser_dispatch._parse_dockerfile_dependencies_only
    )
    assert repository_service._parse_dockerfile_file is (
        repository_dockerfile_parser_dispatch._parse_dockerfile_file
    )


def test_repository_intelligence_scss_helpers_are_modularized() -> None:
    assert repository_service.scss_adapter.strip_comments is (
        repository_scss_primitives.strip_comments
    )
    assert repository_service.scss_adapter.has_scss_path_hints is (
        repository_scss_primitives.has_scss_path_hints
    )
    assert repository_service.scss_adapter.iter_import_entries is (
        repository_scss_primitives.iter_import_entries
    )
    assert repository_service.scss_adapter.iter_symbol_entries is (
        repository_scss_primitives.iter_symbol_entries
    )
    assert repository_service.scss_adapter.iter_reference_entries is (
        repository_scss_primitives.iter_reference_entries
    )
    assert repository_service.scss_adapter.source_symbol_name_for_line is (
        repository_scss_primitives.source_symbol_name_for_line
    )
    assert repository_service.scss_adapter.is_probable_scss_source is (
        repository_scss_analysis_support.is_probable_scss_source
    )
    assert repository_service.scss_adapter.module_aliases_for_path is (
        repository_scss_analysis_support.module_aliases_for_path
    )
    assert repository_service.scss_adapter.parse_dependencies_only is (
        repository_scss_analysis_support.parse_dependencies_only
    )
    assert repository_service.scss_adapter.parse_file is (
        repository_scss_analysis_support.parse_file
    )
    assert repository_service._parse_scss_dependencies_only is (
        repository_scss_parser_dispatch._parse_scss_dependencies_only
    )
    assert repository_service._parse_scss_file is (
        repository_scss_parser_dispatch._parse_scss_file
    )


def test_repository_intelligence_shaderlab_helpers_are_modularized() -> None:
    assert repository_service.shaderlab_adapter.strip_comments is (
        repository_shaderlab_primitives.strip_comments
    )
    assert repository_service.shaderlab_adapter.has_shaderlab_path_hints is (
        repository_shaderlab_primitives.has_shaderlab_path_hints
    )
    assert repository_service.shaderlab_adapter.iter_shader_declarations is (
        repository_shaderlab_primitives.iter_shader_declarations
    )
    assert repository_service.shaderlab_adapter.iter_usepass_targets is (
        repository_shaderlab_primitives.iter_usepass_targets
    )
    assert repository_service.shaderlab_adapter.iter_fallback_targets is (
        repository_shaderlab_primitives.iter_fallback_targets
    )
    assert repository_service.shaderlab_adapter.parse_include_statements is (
        repository_shaderlab_primitives.parse_include_statements
    )
    assert repository_service.shaderlab_adapter.iter_symbol_entries is (
        repository_shaderlab_primitives.iter_symbol_entries
    )
    assert repository_service.shaderlab_adapter.iter_function_call_names is (
        repository_shaderlab_primitives.iter_function_call_names
    )
    assert repository_service.shaderlab_adapter.is_probable_shaderlab_source is (
        repository_shaderlab_analysis_support.is_probable_shaderlab_source
    )
    assert repository_service.shaderlab_adapter.module_aliases_for_path is (
        repository_shaderlab_analysis_support.module_aliases_for_path
    )
    assert repository_service.shaderlab_adapter.parse_dependencies_only is (
        repository_shaderlab_analysis_support.parse_dependencies_only
    )
    assert repository_service.shaderlab_adapter.parse_file is (
        repository_shaderlab_analysis_support.parse_file
    )
    assert repository_service._parse_shaderlab_dependencies_only is (
        repository_shaderlab_parser_dispatch._parse_shaderlab_dependencies_only
    )
    assert repository_service._parse_shaderlab_file is (
        repository_shaderlab_parser_dispatch._parse_shaderlab_file
    )


def test_repository_intelligence_eiffel_helpers_are_modularized() -> None:
    assert repository_service.eiffel_adapter.strip_comments is (
        repository_eiffel_primitives.strip_comments
    )
    assert repository_service.eiffel_adapter.has_eiffel_path_hints is (
        repository_eiffel_primitives.has_eiffel_path_hints
    )
    assert repository_service.eiffel_adapter.class_name_from_text is (
        repository_eiffel_primitives.class_name_from_text
    )
    assert repository_service.eiffel_adapter.parse_root_class_names is (
        repository_eiffel_primitives.parse_root_class_names
    )
    assert repository_service.eiffel_adapter.is_probable_eiffel_source is (
        repository_eiffel_analysis_support.is_probable_eiffel_source
    )
    assert repository_service.eiffel_adapter.module_aliases_for_path is (
        repository_eiffel_analysis_support.module_aliases_for_path
    )
    assert repository_service.eiffel_adapter.parse_dependencies_only is (
        repository_eiffel_analysis_support.parse_dependencies_only
    )
    assert repository_service.eiffel_adapter.parse_file is (
        repository_eiffel_analysis_support.parse_file
    )
    assert repository_service._parse_eiffel_dependencies_only is (
        repository_eiffel_parser_dispatch._parse_eiffel_dependencies_only
    )
    assert repository_service._parse_eiffel_file is (
        repository_eiffel_parser_dispatch._parse_eiffel_file
    )


def test_repository_intelligence_puppet_helpers_are_modularized() -> None:
    assert repository_service.puppet_adapter.strip_comments is (
        repository_puppet_primitives.strip_comments
    )
    assert repository_service.puppet_adapter.has_puppet_path_hints is (
        repository_puppet_primitives.has_puppet_path_hints
    )
    assert repository_service.puppet_adapter.is_probable_puppet_source is (
        repository_puppet_analysis_support.is_probable_puppet_source
    )
    assert repository_service.puppet_adapter.puppet_metadata_name is (
        repository_puppet_primitives.puppet_metadata_name
    )
    assert repository_service.puppet_adapter.module_name_from_metadata_name is (
        repository_puppet_primitives.module_name_from_metadata_name
    )
    assert repository_service.puppet_adapter.iter_definition_entries is (
        repository_puppet_primitives.iter_definition_entries
    )
    assert repository_service.puppet_adapter.iter_dependency_targets is (
        repository_puppet_primitives.iter_dependency_targets
    )
    assert repository_service.puppet_adapter.module_aliases_for_path is (
        repository_puppet_analysis_support.module_aliases_for_path
    )
    assert repository_service.puppet_adapter.parse_dependencies_only is (
        repository_puppet_analysis_support.parse_dependencies_only
    )
    assert repository_service.puppet_adapter.parse_file is (
        repository_puppet_analysis_support.parse_file
    )
    assert repository_service._parse_puppet_dependencies_only is (
        repository_puppet_parser_dispatch._parse_puppet_dependencies_only
    )
    assert repository_service._parse_puppet_file is (
        repository_puppet_parser_dispatch._parse_puppet_file
    )


def test_rego_adapter_module_aliases_include_package_and_rule_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rego-alias-repo"
    (repo_path / "policy" / "lib").mkdir(parents=True)
    (repo_path / "policy" / "lib" / "helpers.rego").write_text(
        "package policy.lib.helpers\n\n"
        "render_json if {\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.rego_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="policy/lib/helpers.rego",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "policy/lib/helpers.rego" in aliases
    assert "policy/lib/helpers" in aliases
    assert "policy.lib.helpers" in aliases
    assert "policy/lib/helpers" in aliases
    assert "data.policy.lib.helpers" in aliases
    assert "render_json" in aliases
    assert "policy.lib.helpers.render_json" in aliases
    assert "data.policy.lib.helpers.render_json" in aliases


def test_yara_adapter_module_aliases_include_rule_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "yara-alias-repo"
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "rules" / "helper.yar").write_text(
        "private rule helper_rule {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.yara_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rules/helper.yar",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rules/helper.yar" in aliases
    assert "rules/helper" in aliases
    assert "helper_rule" in aliases


def test_bicep_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bicep-alias-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "modules" / "main.bicep").write_text(
        "param name string\n\n"
        "var prefix = name\n\n"
        "output fullName string = prefix\n",
        encoding="utf-8",
    )

    aliases = repository_service.bicep_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/main.bicep",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "modules/main.bicep" in aliases
    assert "modules/main" in aliases
    assert "modules" in aliases
    assert "modules.main" in aliases
    assert "name" in aliases
    assert "prefix" in aliases
    assert "fullName" in aliases
    assert "modules.fullName" in aliases


def test_tlaplus_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tlaplus-alias-repo"
    (repo_path / "specs").mkdir(parents=True)
    (repo_path / "specs" / "Spec.tla").write_text(
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals\n\n"
        "Foo == 1\n"
        "VARIABLES x\n"
        "CONSTANTS Y\n",
        encoding="utf-8",
    )

    aliases = repository_service.tlaplus_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="specs/Spec.tla",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "specs/Spec.tla" in aliases
    assert "specs/Spec" in aliases
    assert "Spec" in aliases
    assert "Foo" in aliases
    assert "Spec.Foo" in aliases
    assert "Spec!Foo" in aliases
    assert "x" in aliases
    assert "Y" in aliases


def test_logtalk_adapter_module_aliases_include_entity_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "logtalk-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.lgt").write_text(
        ":- object(main).\n"
        "    :- public(run/0).\n"
        "    run :- helper::answer(_).\n"
        ":- end_object.\n",
        encoding="utf-8",
    )

    aliases = repository_service.logtalk_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.lgt",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/main.lgt" in aliases
    assert "src/main" in aliases
    assert "main" in aliases
    assert "run" in aliases
    assert "main.run" in aliases


def test_chapel_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "chapel-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Main.chpl").write_text(
        "module Main {\n"
        "proc run() { return helper(); }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.chapel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Main.chpl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Main.chpl" in aliases
    assert "src/Main" in aliases
    assert "Main" in aliases
    assert "run" in aliases
    assert "Main.run" in aliases


def test_eiffel_adapter_module_aliases_include_class_and_feature_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "eiffel-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )

    aliases = repository_service.eiffel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/application.e",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/application.e" in aliases
    assert "src/application" in aliases
    assert "application" in aliases
    assert "APPLICATION" in aliases
    assert "make" in aliases
    assert "APPLICATION.make" in aliases


def test_raku_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "raku-alias-repo"
    (repo_path / "lib" / "Demo").mkdir(parents=True)
    (repo_path / "lib" / "Demo" / "Helper.rakumod").write_text(
        "unit module Demo::Helper;\n\nsub render-json() { }\nclass Builder { }\n",
        encoding="utf-8",
    )

    aliases = repository_service.raku_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="lib/Demo/Helper.rakumod",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "lib/Demo/Helper.rakumod" in aliases
    assert "lib/Demo/Helper" in aliases
    assert "Demo::Helper" in aliases
    assert "Demo/Helper" in aliases
    assert "Helper" in aliases
    assert "render-json" in aliases
    assert "Builder" in aliases
    assert "Demo::Helper::render-json" in aliases


def test_agda_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "agda-alias-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "src" / "Data" / "Helper.agda").write_text(
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n",
        encoding="utf-8",
    )

    aliases = repository_service.agda_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Data/Helper.agda",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Data/Helper.agda" in aliases
    assert "src/Data/Helper" in aliases
    assert "src.Data.Helper" in aliases
    assert "Data.Helper" in aliases
    assert "Data/Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases
    assert "Data.Helper.helper" in aliases


def test_idris_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "idris-alias-repo"
    (repo_path / "src" / "Demo").mkdir(parents=True)
    (repo_path / "src" / "Demo" / "Helper.idr").write_text(
        "module Demo.Helper\n\n"
        "record Builder where\n"
        "  constructor MkBuilder\n\n"
        "renderJson : IO ()\n"
        "renderJson = pure ()\n",
        encoding="utf-8",
    )

    aliases = repository_service.idris_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Demo/Helper.idr",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Demo/Helper.idr" in aliases
    assert "src/Demo/Helper" in aliases
    assert "src.Demo.Helper" in aliases
    assert "Demo.Helper" in aliases
    assert "Demo/Helper" in aliases
    assert "Helper" in aliases
    assert "Builder" in aliases
    assert "renderJson" in aliases
    assert "Demo.Helper.renderJson" in aliases


def test_nushell_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nushell-alias-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "modules" / "helper.nu").write_text(
        "export def render-json [] {\n"
        "  '{}'\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.nushell_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/helper.nu",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "modules/helper.nu" in aliases
    assert "modules/helper" in aliases
    assert "helper" in aliases
    assert "render-json" in aliases
    assert "helper render-json" in aliases


def test_fish_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fish-alias-repo"
    (repo_path / "functions").mkdir(parents=True)
    (repo_path / "functions" / "helper.fish").write_text(
        "function helper --description 'render data'\n"
        "    render_json\n"
        "end\n",
        encoding="utf-8",
    )

    aliases = repository_service.fish_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="functions/helper.fish",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "functions/helper.fish" in aliases
    assert "functions/helper" in aliases
    assert "functions.helper" in aliases
    assert "helper" in aliases
    assert "helper.helper" in aliases


def test_batchfile_adapter_module_aliases_include_script_and_label_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "batchfile-alias-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "build.bat").write_text(
        "@echo off\n"
        ":setup\n"
        "call :done\n"
        ":done\n"
        "exit /b 0\n",
        encoding="utf-8",
    )

    aliases = repository_service.batchfile_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/build.bat",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/build.bat" in aliases
    assert "scripts/build" in aliases
    assert "scripts.build" in aliases
    assert "build" in aliases
    assert "setup" in aliases
    assert "done" in aliases


def test_makefile_adapter_module_aliases_include_makefile_and_target_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "makefile-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "Makefile").write_text(
        "build: clean\n"
        "\t$(MAKE) helper\n"
        "clean:\n"
        "\t@echo clean\n",
        encoding="utf-8",
    )

    aliases = repository_service.makefile_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Makefile",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Makefile" in aliases
    assert "build" in aliases
    assert "clean" in aliases


def test_cmake_adapter_module_aliases_include_project_and_target_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cmake-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text(
        "project(acme)\n"
        "add_library(acme_core INTERFACE)\n"
        "function(configure_runtime target)\n"
        "endfunction()\n",
        encoding="utf-8",
    )

    aliases = repository_service.cmake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="CMakeLists.txt",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "CMakeLists.txt" in aliases
    assert "acme" in aliases
    assert "acme_core" in aliases
    assert "configure_runtime" in aliases


def test_meson_adapter_module_aliases_include_project_and_target_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "meson-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('acme', 'c')\n"
        "library('acme_core', 'src/core.c')\n"
        "custom_target('codegen')\n",
        encoding="utf-8",
    )

    aliases = repository_service.meson_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="meson.build",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "meson.build" in aliases
    assert "acme" in aliases
    assert "acme_core" in aliases
    assert "codegen" in aliases


def test_just_adapter_module_aliases_include_recipe_and_alias_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "just-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "Justfile").write_text(
        "alias ci := check\n"
        "check:\n"
        "  just build\n"
        "build:\n"
        "  echo build\n",
        encoding="utf-8",
    )

    aliases = repository_service.just_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Justfile",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Justfile" in aliases
    assert "ci" in aliases
    assert "check" in aliases
    assert "build" in aliases


def test_qmake_adapter_module_aliases_include_target_and_subdir_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qmake-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "project.pro").write_text(
        "TEMPLATE = subdirs\n"
        "TARGET = acme\n"
        "SUBDIRS += core app\n"
        "app.depends = core\n",
        encoding="utf-8",
    )

    aliases = repository_service.qmake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="project.pro",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "project.pro" in aliases
    assert "acme" in aliases
    assert "core" in aliases
    assert "app" in aliases


def test_qml_adapter_module_aliases_include_qmldir_module_component_and_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qml-alias-repo"
    (repo_path / "controls").mkdir(parents=True)
    (repo_path / "qmldir").write_text(
        "module Demo.Controls\n"
        "Button 1.0 controls/Button.qml\n",
        encoding="utf-8",
    )
    (repo_path / "controls" / "Button.qml").write_text(
        "Rectangle {\n"
        "    id: buttonRoot\n"
        "    function press() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.qml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="controls/Button.qml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "controls/Button.qml" in aliases
    assert "Button" in aliases
    assert "Demo.Controls.Button" in aliases
    assert "buttonRoot" in aliases
    assert "press" in aliases


def test_bitbake_adapter_module_aliases_include_recipe_class_and_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bitbake-alias-repo"
    (repo_path / "recipes-core" / "images").mkdir(parents=True)
    (repo_path / "classes").mkdir(parents=True)
    (repo_path / "recipes-core" / "images" / "core-image-minimal.bb").write_text(
        'require ../base/base.inc\n'
        "inherit image\n"
        'IMAGE_FEATURES += "ssh-server-dropbear"\n'
        "python do_install() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "classes" / "image.bbclass").write_text(
        "python image_do_rootfs() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.bitbake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="recipes-core/images/core-image-minimal.bb",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "recipes-core/images/core-image-minimal.bb" in aliases
    assert "recipes-core/images/core-image-minimal" in aliases
    assert "recipes-core.images.core-image-minimal" in aliases
    assert "core-image-minimal" in aliases
    assert "recipe:core-image-minimal" in aliases
    assert "do_install" in aliases


def test_bitbake_adapter_module_aliases_use_supplied_text_without_rereading(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bitbake-inline-text-repo"
    recipe_text = (
        'DESCRIPTION = "demo"\n'
        "python do_install() {\n"
        "    pass\n"
        "}\n"
    )

    aliases = repository_service.bitbake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="recipes-core/images/core-image-minimal.bb",
        stable_identifier=repository_service._stable_identifier,
        text=recipe_text,
    )

    assert "recipes-core/images/core-image-minimal.bb" in aliases
    assert "core-image-minimal" in aliases
    assert "recipe:core-image-minimal" in aliases
    assert "do_install" in aliases


def test_cue_adapter_module_aliases_include_module_prefix_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cue-alias-repo"
    (repo_path / "cue.mod").mkdir(parents=True)
    (repo_path / "pkg" / "schema").mkdir(parents=True)
    (repo_path / "cue.mod" / "module.cue").write_text(
        'module: "example.com/demo"\n',
        encoding="utf-8",
    )
    (repo_path / "pkg" / "schema" / "schema.cue").write_text(
        "package schema\n\n#Answer: 42\nconfig: #Answer\n",
        encoding="utf-8",
    )

    aliases = repository_service.cue_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="pkg/schema/schema.cue",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "pkg/schema/schema.cue" in aliases
    assert "pkg/schema" in aliases
    assert "example.com/demo/pkg/schema" in aliases
    assert "schema" in aliases
    assert "#Answer" in aliases
    assert "schema.#Answer" in aliases


def test_factor_adapter_module_aliases_include_vocabulary_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "factor-alias-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "math" / "math.factor").write_text(
        "IN: math\n\n: square ( n -- n ) dup * ;\n",
        encoding="utf-8",
    )

    aliases = repository_service.factor_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="math/math.factor",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "math/math.factor" in aliases
    assert "math/math" in aliases
    assert "math" in aliases
    assert "square" in aliases
    assert "math.square" in aliases


def test_haxe_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haxe-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "Helper.hx").write_text(
        "package demo;\n"
        "\n"
        "class Helper {\n"
        "    public static function renderJson():String {\n"
        '        return "{}";\n'
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.haxe_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/Helper.hx",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/Helper.hx" in aliases
    assert "src/demo/Helper" in aliases
    assert "src.demo.Helper" in aliases
    assert "demo.Helper" in aliases
    assert "Helper" in aliases
    assert "renderJson" in aliases
    assert "demo.renderJson" not in aliases
    assert "demo.Helper.renderJson" in aliases


def test_glsl_adapter_module_aliases_include_shader_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "glsl-alias-repo"
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "shaders" / "noise.glsl").write_text(
        "struct Params {\n"
        "  float gain;\n"
        "};\n"
        "\n"
        "float noise() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.glsl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="shaders/noise.glsl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "shaders/noise.glsl" in aliases
    assert "shaders/noise" in aliases
    assert "noise" in aliases
    assert "Params" in aliases


def test_hlsl_adapter_module_aliases_include_shader_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hlsl-alias-repo"
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "shaders" / "lighting.hlsli").write_text(
        "struct LightingParams {\n"
        "  float intensity;\n"
        "};\n"
        "\n"
        "float4 ShadeMain(float3 normal) : SV_Target {\n"
        "  return float4(normal, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.hlsl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="shaders/lighting.hlsli",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "shaders/lighting.hlsli" in aliases
    assert "shaders/lighting" in aliases
    assert "lighting" in aliases
    assert "LightingParams" in aliases
    assert "ShadeMain" in aliases


def test_hack_adapter_module_aliases_include_namespace_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hack-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Ref.php").write_text(
        "<?hh\n"
        "namespace Demo;\n"
        "\n"
        "final class Ref<T> {}\n",
        encoding="utf-8",
    )

    aliases = repository_service.hack_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Ref.php",
    )

    assert "src/Ref.php" in aliases
    assert "src/Ref" in aliases
    assert "src.Ref" in aliases
    assert "Ref" in aliases
    assert "Demo\\Ref" in aliases


def test_odin_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-alias-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    (repo_path / "src" / "common" / "helper.odin").write_text(
        "package common\n"
        "\n"
        "Config :: struct {\n"
        "    value: int,\n"
        "}\n"
        "\n"
        "helper :: proc() -> int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.odin_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/common/helper.odin",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/common/helper.odin" in aliases
    assert "src/common/helper" in aliases
    assert "helper" in aliases
    assert "src:common" in aliases
    assert "common" in aliases
    assert "common.Config" in aliases
    assert "common.helper" in aliases


def test_autohotkey_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autohotkey-alias-repo"
    (repo_path / "Lib").mkdir(parents=True)
    (repo_path / "Lib" / "Helper.ahk").write_text(
        "class Helper {\n"
        "    RenderJson(value) {\n"
        "        return value\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.autohotkey_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Lib/Helper.ahk",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Lib/Helper.ahk" in aliases
    assert "Lib/Helper" in aliases
    assert "Lib.Helper" in aliases
    assert "Helper" in aliases
    assert "RenderJson" in aliases
    assert "Helper.RenderJson" in aliases


def test_autoit_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autoit-alias-repo"
    (repo_path / "Includes").mkdir(parents=True)
    (repo_path / "Includes" / "Helper.au3").write_text(
        "Func RenderJson($value)\n"
        "    Return $value\n"
        "EndFunc\n",
        encoding="utf-8",
    )

    aliases = repository_service.autoit_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Includes/Helper.au3",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Includes/Helper.au3" in aliases
    assert "Includes/Helper" in aliases
    assert "Includes.Helper" in aliases
    assert "Helper" in aliases
    assert "RenderJson" in aliases
    assert "Helper.RenderJson" in aliases


def test_squirrel_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "squirrel-alias-repo"
    (repo_path / "scripts" / "vscripts").mkdir(parents=True)
    (repo_path / "scripts" / "vscripts" / "ppmod.nut").write_text(
        "::ppmod <- {\n"
        "  run = function () {\n"
        '    return "ok";\n'
        "  }\n"
        "};\n",
        encoding="utf-8",
    )

    aliases = repository_service.squirrel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/vscripts/ppmod.nut",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/vscripts/ppmod.nut" in aliases
    assert "scripts/vscripts/ppmod" in aliases
    assert "scripts.vscripts.ppmod" in aliases
    assert "ppmod" in aliases


def test_cython_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cython-alias-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "helpers.pyx").write_text(
        "cpdef int render_json():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    aliases = repository_service.cython_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/acme/helpers.pyx",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acme/helpers.pyx" in aliases
    assert "src/acme/helpers" in aliases
    assert "acme.helpers" in aliases
    assert "helpers" in aliases
    assert "render_json" in aliases
    assert "acme.helpers.render_json" in aliases


def test_cuda_adapter_module_aliases_include_file_and_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "cuda-alias-repo"
    (repo_path / "src" / "kernels").mkdir(parents=True)
    (repo_path / "src" / "kernels" / "vector_add.cuh").write_text(
        "__device__ inline int add_one(int x) {\n"
        "  return x + 1;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.cuda_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/kernels/vector_add.cuh",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/kernels/vector_add.cuh" in aliases
    assert "src/kernels/vector_add" in aliases
    assert "vector_add" in aliases


def test_stan_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "stan-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "helpers.stan").write_text(
        "functions {\n"
        "  real render_json(real x) {\n"
        "    return x;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.stan_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/helpers.stan",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "models/helpers.stan" in aliases
    assert "models/helpers" in aliases
    assert "helpers" in aliases
    assert "render_json" in aliases
    assert "helpers.render_json" in aliases


def test_robotframework_adapter_module_aliases_include_suite_test_and_keyword_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "robotframework-alias-repo"
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "login.robot").write_text(
        "*** Test Cases ***\n"
        "Valid Login\n"
        "    Open Login Page\n"
        "\n"
        "*** Keywords ***\n"
        "Open Login Page\n"
        "    Log    opened\n",
        encoding="utf-8",
    )

    aliases = repository_service.robotframework_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="tests/login.robot",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "tests/login.robot" in aliases
    assert "tests/login" in aliases
    assert "tests.login" in aliases
    assert "login" in aliases
    assert "Valid Login" in aliases
    assert "Open Login Page" in aliases
    assert "tests.login.Open Login Page" in aliases


def test_dockerfile_adapter_module_aliases_include_stage_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "dockerfile-alias-repo"
    (repo_path / "docker").mkdir(parents=True)
    (repo_path / "docker" / "Dockerfile").write_text(
        "FROM python:3.12-slim AS base\n"
        "RUN echo preparing\n"
        "FROM base AS runtime\n"
        'CMD ["python", "--version"]\n',
        encoding="utf-8",
    )

    aliases = repository_service.dockerfile_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="docker/Dockerfile",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "docker/Dockerfile" in aliases
    assert "Dockerfile" in aliases
    assert "docker" in aliases
    assert "docker.Dockerfile" in aliases
    assert "base" in aliases
    assert "runtime" in aliases
    assert "docker.Dockerfile.base" in aliases


def test_scss_adapter_module_aliases_include_module_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "scss-alias-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "_mixins.scss").write_text(
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n"
        "@function helper-fn() {\n"
        "  @return 1;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.scss_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="styles/_mixins.scss",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "styles/_mixins.scss" in aliases
    assert "styles/mixins" in aliases
    assert "styles.mixins" in aliases
    assert "_mixins" in aliases
    assert "mixins" in aliases
    assert "button-base" in aliases
    assert "helper-fn" in aliases
    assert "styles.mixins.button-base" in aliases


def test_typst_adapter_module_aliases_include_module_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "typst-alias-repo"
    (repo_path / "docs" / "lib").mkdir(parents=True)
    (repo_path / "docs" / "lib" / "utils.typ").write_text(
        "#let add(x, y) = x + y\n"
        "#let scale(x) = x * 2\n",
        encoding="utf-8",
    )

    aliases = repository_service.typst_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="docs/lib/utils.typ",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "docs/lib/utils.typ" in aliases
    assert "docs/lib/utils" in aliases
    assert "docs.lib.utils" in aliases
    assert "lib.utils" in aliases
    assert "utils" in aliases
    assert "add" in aliases
    assert "scale" in aliases
    assert "lib.utils.add" in aliases


def test_starlark_adapter_module_aliases_include_load_labels_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "starlark-alias-repo"
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "rules" / "demo.bzl").write_text(
        "def render_json(name):\n"
        "    return name\n"
        "\n"
        "helper_value = 1\n",
        encoding="utf-8",
    )

    aliases = repository_service.starlark_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rules/demo.bzl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rules/demo.bzl" in aliases
    assert "rules/demo" in aliases
    assert "rules.demo" in aliases
    assert "//rules:demo.bzl" in aliases
    assert "render_json" in aliases
    assert "helper_value" in aliases
    assert "rules.demo.render_json" in aliases


def test_starlark_adapter_resolves_shorthand_load_labels() -> None:
    module_index = {
        "BUILD.bazel": "BUILD.bazel",
        "rules/demo.bzl": "rules/demo.bzl",
        "lib/common.bzl": "lib/common.bzl",
    }

    assert repository_service.starlark_adapter.resolve_load_target(
        current_file="BUILD.bazel",
        import_target="rules:demo.bzl",
        module_index=module_index,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    ) == "rules/demo.bzl"
    assert repository_service.starlark_adapter.resolve_load_target(
        current_file="rules/demo.bzl",
        import_target=":common.bzl",
        module_index={
            **module_index,
            "rules/common.bzl": "rules/common.bzl",
        },
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    ) == "rules/common.bzl"


def test_v_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "v-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.v").write_text(
        "module demo.app\n"
        "\n"
        "pub struct Helper {}\n"
        "\n"
        "pub fn render_json() string {\n"
        "    return '{}'\n"
        "}\n"
        "\n"
        "fn (helper Helper) boot() {\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.v_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.v",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/main.v" in aliases
    assert "src/main" in aliases
    assert "src.main" in aliases
    assert "main" in aliases
    assert "demo.app" in aliases
    assert "Helper" in aliases
    assert "render_json" in aliases
    assert "boot" in aliases
    assert "demo.app.render_json" in aliases
    assert "main.boot" in aliases


def test_smalltalk_adapter_module_aliases_include_package_class_and_selector_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "smalltalk-alias-repo"
    (repo_path / "src" / "Demo-Core").mkdir(parents=True)
    (repo_path / "src" / "Demo-Core" / "Helper.class.st").write_text(
        "Class {\n"
        "\t#name : 'Helper',\n"
        "\t#superclass : 'Object',\n"
        "\t#category : 'Demo-Core',\n"
        "\t#package : 'Demo-Core'\n"
        "}\n"
        "\n"
        "{ #category : 'rendering' }\n"
        "Helper class >> renderJson [\n"
        "\t^ '{}'\n"
        "]\n",
        encoding="utf-8",
    )

    aliases = repository_service.smalltalk_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Demo-Core/Helper.class.st",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Demo-Core/Helper.class.st" in aliases
    assert "src/Demo-Core/Helper.class" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases
    assert "Demo-Core" in aliases
    assert "Demo-Core.Helper" in aliases
    assert "renderJson" in aliases
    assert "Helper.renderJson" in aliases


def test_elm_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "elm-alias-repo"
    (repo_path / "src" / "Page").mkdir(parents=True)
    (repo_path / "src" / "Page" / "Home.elm").write_text(
        "module Page.Home exposing (Model, Msg, init, update)\n\n"
        "type alias Model =\n"
        "    { count : Int }\n\n"
        "type Msg\n"
        "    = Increment\n\n"
        "init : Model\n"
        "init =\n"
        "    { count = 0 }\n\n"
        "update : Msg -> Model -> Model\n"
        "update msg model =\n"
        "    model\n",
        encoding="utf-8",
    )

    aliases = repository_service.elm_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Page/Home.elm",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Page/Home.elm" in aliases
    assert "src/Page/Home" in aliases
    assert "src.Page.Home" in aliases
    assert "Home" in aliases
    assert "Page.Home" in aliases
    assert "Model" in aliases
    assert "Msg" in aliases
    assert "init" in aliases
    assert "update" in aliases
    assert "Page.Home.init" in aliases
    assert "Page.Home.update" in aliases


def test_emacslisp_adapter_module_aliases_include_feature_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "emacslisp-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.el").write_text(
        "(provide 'main)\n"
        "(defun run () 1)\n",
        encoding="utf-8",
    )

    aliases = repository_service.emacslisp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="main.el",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "main.el" in aliases
    assert "main" in aliases
    assert "run" in aliases
    assert "main.run" in aliases


def test_vimscript_adapter_module_aliases_include_autoload_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vimscript-alias-repo"
    (repo_path / "autoload").mkdir(parents=True)
    (repo_path / "autoload" / "fugitive.vim").write_text(
        "function! fugitive#run()\n"
        "  return '{}'\n"
        "endfunction\n"
        "let g:fugitive_loaded = 1\n",
        encoding="utf-8",
    )

    aliases = repository_service.vimscript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="autoload/fugitive.vim",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "autoload/fugitive.vim" in aliases
    assert "autoload/fugitive" in aliases
    assert "autoload.fugitive" in aliases
    assert "fugitive" in aliases
    assert "fugitive#run" in aliases
    assert "g:fugitive_loaded" in aliases
    assert "fugitive.fugitive#run" in aliases


def test_racket_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "racket-alias-repo"
    (repo_path / "private").mkdir(parents=True)
    (repo_path / "main.rkt").write_text(
        "#lang racket\n"
        '(require "private/helper.rkt")\n'
        "(define (run) (helper))\n",
        encoding="utf-8",
    )

    aliases = repository_service.racket_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="main.rkt",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "main.rkt" in aliases
    assert "main" in aliases
    assert "run" in aliases
    assert "main.run" in aliases


def test_xpp_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "xpp-alias-repo"
    (repo_path / "PackagesLocalDirectory" / "Acme" / "Acme" / "AxClass").mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
        / "AcmeMain.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>AcmeMain</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class AcmeMain\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "    <Methods>\n"
        "      <Method>\n"
        "        <Name>boot</Name>\n"
        "        <Source><![CDATA[\n"
        "public static void boot()\n"
        "{\n"
        "}\n"
        "]]></Source>\n"
        "      </Method>\n"
        "    </Methods>\n"
        "  </SourceCode>\n"
        "</AxClass>\n",
        encoding="utf-8",
    )

    aliases = repository_service.xpp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml" in aliases
    assert "PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain" in aliases
    assert "AcmeMain" in aliases
    assert "boot" in aliases
    assert "AcmeMain.boot" in aliases
    assert "AcmeMain::boot" in aliases


def test_scratch_adapter_module_aliases_include_project_target_and_procedure_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scratch-alias-repo"
    _write_scratch_project(
        repo_path / "games" / "Maze.sb3",
        _scratch_project_payload(),
    )

    aliases = repository_service.scratch_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="games/Maze.sb3",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "games/Maze.sb3" in aliases
    assert "Maze" in aliases
    assert "games/Maze" in aliases
    assert "games.Maze" in aliases
    assert "project:Maze" in aliases
    assert "Stage" in aliases
    assert "Cat" in aliases
    assert "init" in aliases
    assert "procedure:init" in aliases
    assert "start" in aliases
    assert "broadcast:start" in aliases


def test_vhdl_adapter_module_aliases_include_entity_package_and_routine_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vhdl-alias-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "top.vhd").write_text(
        "package util_pkg is\n"
        "  function helper return integer;\n"
        "end package;\n"
        "entity top is\n"
        "end entity;\n"
        "architecture rtl of top is\n"
        "begin\n"
        "end architecture;\n",
        encoding="utf-8",
    )

    aliases = repository_service.vhdl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rtl/top.vhd",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rtl/top.vhd" in aliases
    assert "rtl/top" in aliases
    assert "rtl.top" in aliases
    assert "top" in aliases
    assert "entity:top" in aliases
    assert "util_pkg" in aliases
    assert "package:util_pkg" in aliases
    assert "helper" in aliases
    assert "util_pkg.helper" in aliases


def test_repository_intelligence_vhdl_helpers_are_modularized() -> None:
    assert repository_service.vhdl_adapter.strip_comments is (
        repository_vhdl_primitives.strip_comments
    )
    assert repository_service.vhdl_adapter.has_vhdl_path_hints is (
        repository_vhdl_primitives.has_vhdl_path_hints
    )
    assert repository_service.vhdl_adapter.is_probable_vhdl_source is (
        repository_vhdl_primitives.is_probable_vhdl_source
    )
    assert repository_service.vhdl_adapter.is_probable_operational_entrypoint is (
        repository_vhdl_primitives.is_probable_operational_entrypoint
    )
    assert repository_service.vhdl_adapter._collect_symbols is (
        repository_vhdl_primitives._collect_symbols
    )
    assert repository_service.vhdl_adapter._source_symbol_id_for_line is (
        repository_vhdl_primitives._source_symbol_id_for_line
    )
    assert repository_service.vhdl_adapter._resolve_target_file is (
        repository_vhdl_analysis_support._resolve_target_file
    )
    assert repository_service.vhdl_adapter._resolve_use_target is (
        repository_vhdl_analysis_support._resolve_use_target
    )
    assert repository_service.vhdl_adapter.module_aliases_for_path is (
        repository_vhdl_analysis_support.module_aliases_for_path
    )
    assert repository_service.vhdl_adapter.parse_dependencies_only is (
        repository_vhdl_analysis_support.parse_dependencies_only
    )
    assert repository_service.vhdl_adapter.parse_file is (
        repository_vhdl_analysis_support.parse_file
    )


def test_gdscript_adapter_module_aliases_include_class_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gdscript-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "player.gd").write_text(
        "class_name Player\n"
        "extends Node\n"
        "signal jumped\n"
        "func ready_up() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )

    aliases = repository_service.gdscript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/player.gd",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/player.gd" in aliases
    assert "src/player" in aliases
    assert "src.player" in aliases
    assert "res://src/player.gd" in aliases
    assert "Player" in aliases
    assert "class:Player" in aliases
    assert "ready_up" in aliases
    assert "Player.ready_up" in aliases


def test_gml_adapter_module_aliases_include_script_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gml-alias-repo"
    (repo_path / "scripts" / "Input").mkdir(parents=True)
    (repo_path / "scripts" / "Input" / "Input.gml").write_text(
        "#macro INPUT_OK 1\n"
        "enum InputState { Idle, Active }\n"
        "function InputService() constructor {\n"
        "}\n"
        "helper = function() {\n"
        "    return INPUT_OK;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.gml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/Input/Input.gml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/Input/Input.gml" in aliases
    assert "scripts/Input/Input" in aliases
    assert "scripts.Input.Input" in aliases
    assert "Input" in aliases
    assert "script:Input" in aliases
    assert "INPUT_OK" in aliases
    assert "macro:INPUT_OK" in aliases
    assert "InputState" in aliases
    assert "enum:InputState" in aliases
    assert "InputService" in aliases
    assert "helper" in aliases
    assert "Input.helper" in aliases


def test_ladder_adapter_module_aliases_include_program_and_routine_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ladder-alias-repo"
    (repo_path / "logic").mkdir(parents=True)
    (repo_path / "logic" / "Main.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="MainProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="MainRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[JSR(ChildRoutine,0);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        '          <Routine Name="ChildRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="1"><Text><![CDATA[XIC(StartPB)OTE(RunMotor);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )

    aliases = repository_service.ladder_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="logic/Main.L5X",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "logic/Main.L5X" in aliases
    assert "logic/Main" in aliases
    assert "logic.Main" in aliases
    assert "Main" in aliases
    assert "PlantController" in aliases
    assert "MainProgram" in aliases
    assert "MainRoutine" in aliases
    assert "ChildRoutine" in aliases
    assert "MainProgram.MainRoutine" in aliases


def test_ladder_adapter_distinguishes_operational_entrypoints_from_datatype_exports() -> None:
    program_text = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        '<RSLogix5000Content TargetType="Program">\n'
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="MainProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="MainRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[XIC(StartPB)OTE(RunMotor);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n"
    )
    datatype_text = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        '<RSLogix5000Content TargetType="DataType">\n'
        '  <Controller Name="PlantController">\n'
        "    <DataTypes>\n"
        '      <DataType Name="MotorStatus">\n'
        "        <Members>\n"
        '          <Member Name="Running" DataType="BOOL"/>\n'
        "        </Members>\n"
        "      </DataType>\n"
        "    </DataTypes>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n"
    )

    assert repository_service.ladder_adapter.is_probable_ladder_source(
        path=Path("logic/Main.L5X"),
        text=program_text,
    )
    assert repository_service.ladder_adapter.is_probable_operational_entrypoint(
        path=Path("logic/Main.L5X"),
        text=program_text,
    )
    assert repository_service._language_for_path(
        Path("logic/Types.L5X"),
        text=datatype_text,
    ) == "ladder"
    assert not repository_service.ladder_adapter.is_probable_operational_entrypoint(
        path=Path("logic/Types.L5X"),
        text=datatype_text,
    )


def test_labview_adapter_module_aliases_include_project_artifact_paths(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "labview-alias-repo"
    (repo_path / "Source" / "Libraries").mkdir(parents=True)
    (repo_path / "Source" / "Libraries" / "Helpers.lvlib").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        '<Library Name="Helpers">\n'
        '  <Item Name="Helper" Type="VI" URL="Helper.vi" />\n'
        "</Library>\n",
        encoding="utf-8",
    )

    aliases = repository_service.labview_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Source/Libraries/Helpers.lvlib",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Source/Libraries/Helpers.lvlib" in aliases
    assert "Source/Libraries/Helpers" in aliases
    assert "Source.Libraries.Helpers" in aliases
    assert "Helpers" in aliases


def test_tcl_adapter_module_aliases_include_package_namespace_and_proc_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tcl-alias-repo"
    (repo_path / "modules" / "sha1").mkdir(parents=True)
    (repo_path / "modules" / "sha1" / "sha1.tcl").write_text(
        "package provide sha1 2.0.5\n"
        "namespace eval ::sha1 {\n"
        "    namespace export SHA1Init\n"
        "}\n"
        "proc ::sha1::SHA1Init {} {\n"
        "    return ok\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.tcl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/sha1/sha1.tcl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "modules/sha1/sha1.tcl" in aliases
    assert "modules/sha1/sha1" in aliases
    assert "modules.sha1.sha1" in aliases
    assert "sha1" in aliases
    assert "package:sha1" in aliases
    assert "namespace:sha1" in aliases
    assert "proc:sha1::SHA1Init" in aliases
    assert "SHA1Init" in aliases


def test_vbscript_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "vbscript-alias-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "helper.vbs").write_text(
        "Class Helper\n"
        "End Class\n"
        "Function Encrypt(value)\n"
        "    Encrypt = value\n"
        "End Function\n",
        encoding="utf-8",
    )

    aliases = repository_service.vbscript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/helper.vbs",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/helper.vbs" in aliases
    assert "scripts/helper" in aliases
    assert "scripts.helper" in aliases
    assert "helper" in aliases
    assert "Helper" in aliases
    assert "Encrypt" in aliases


def test_applescript_adapter_module_aliases_include_script_and_handler_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "applescript-alias-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "Helper.applescript").write_text(
        "script HelperScript\n"
        "    on RenderJson(value)\n"
        "        return value\n"
        "    end RenderJson\n"
        "end script\n",
        encoding="utf-8",
    )

    aliases = repository_service.applescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/Helper.applescript",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/Helper.applescript" in aliases
    assert "scripts/helper.applescript" in aliases
    assert "scripts/Helper" in aliases
    assert "scripts.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases
    assert "HelperScript" in aliases
    assert "helperscript" in aliases
    assert "RenderJson" in aliases
    assert "renderjson" in aliases
    assert "Helper.RenderJson" in aliases
    assert "helper.renderjson" in aliases


def test_apex_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "apex-alias-repo"
    (repo_path / "force-app" / "main" / "default" / "classes").mkdir(parents=True)
    (repo_path / "force-app" / "main" / "default" / "classes" / "AccountTriggerHandler.cls").write_text(
        "public with sharing class AccountTriggerHandler\n"
        "{\n"
        "    public static void run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.apex_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="force-app/main/default/classes/AccountTriggerHandler.cls",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "force-app/main/default/classes/AccountTriggerHandler.cls" in aliases
    assert "force-app/main/default/classes/AccountTriggerHandler" in aliases
    assert "force-app.main.default.classes.AccountTriggerHandler" in aliases
    assert "AccountTriggerHandler" in aliases
    assert "run" in aliases
    assert "AccountTriggerHandler.run" in aliases


def test_wolfram_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "wolfram-alias-repo"
    (repo_path / "Kernel").mkdir(parents=True)
    (repo_path / "Kernel" / "Helpers.wl").write_text(
        'BeginPackage["Acme`"];\n'
        'helper::usage = "helper";\n'
        'Begin["`Private`"];\n'
        "helper[] := 1;\n"
        "End[];\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )

    aliases = repository_service.wolfram_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Kernel/Helpers.wl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Kernel/Helpers.wl" in aliases
    assert "Kernel/Helpers" in aliases
    assert "Kernel.Helpers" in aliases
    assert "Helpers" in aliases
    assert "Acme`Helpers`" in aliases
    assert "helper" in aliases
    assert "Acme`helper" in aliases


def test_rpg_adapter_module_aliases_include_object_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rpg-alias-repo"
    (repo_path / "QRPGLESRC").mkdir(parents=True)
    (repo_path / "QRPGLESRC" / "ORD101.PGM.RPGLE").write_text(
        "**free\n"
        "dcl-proc Updord export;\n"
        "   dcl-pi *n ind;\n"
        "      id packed(5);\n"
        "   end-pi;\n"
        "   return *on;\n"
        "end-proc;\n",
        encoding="utf-8",
    )

    aliases = repository_service.rpg_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="QRPGLESRC/ORD101.PGM.RPGLE",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "qrpglesrc/ord101.pgm.rpgle" in aliases
    assert "qrpglesrc/ord101.pgm" in aliases
    assert "qrpglesrc.ord101.pgm" in aliases
    assert "ord101.pgm" in aliases
    assert "ord101" in aliases
    assert "Updord" in aliases
    assert "updord" in aliases


def test_ml_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "ml-alias-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "util.sml").write_text(
        "structure Util = struct\n"
        "fun helper () = 1\n"
        "end\n",
        encoding="utf-8",
    )

    aliases = repository_service.ml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/acme/util.sml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acme/util.sml" in aliases
    assert "src/acme/util" in aliases
    assert "src.acme.util" in aliases
    assert "acme.util" in aliases
    assert "util" in aliases
    assert "helper" in aliases
    assert "util.helper" in aliases


def test_classic_visual_basic_adapter_module_aliases_include_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vb6-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "cHelper.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "cHelper"\n'
        "Option Explicit\n"
        "\n"
        "Public Function Helper() As String\n"
        '    Helper = "ok"\n'
        "End Function\n",
        encoding="utf-8",
    )

    aliases = repository_service.classic_visual_basic_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/cHelper.cls",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/chelper.cls" in aliases
    assert "src/chelper" in aliases
    assert "src.chelper" in aliases
    assert "chelper" in aliases
    assert "helper" in aliases
    assert "chelper.helper" in aliases


def test_vba_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "vba-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "JsonData.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "JsonData"\n'
        "Option Explicit\n"
        "\n"
        "Public Function ToJson() As String\n"
        '    ToJson = "{}"\n'
        "End Function\n",
        encoding="utf-8",
    )

    aliases = repository_service.vba_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/JsonData.cls",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/jsondata.cls" in aliases
    assert "src/jsondata" in aliases
    assert "src.jsondata" in aliases
    assert "jsondata" in aliases
    assert "tojson" in aliases
    assert "jsondata.tojson" in aliases


def test_lisp_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lisp-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.lisp").write_text(
        "(defpackage #:acme.helper (:use #:cl) (:export #:helper))\n"
        "(in-package #:acme.helper)\n"
        "(defun helper () 1)\n",
        encoding="utf-8",
    )

    aliases = repository_service.lisp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/helper.lisp",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/helper.lisp" in aliases
    assert "src/helper" in aliases
    assert "src.helper" in aliases
    assert "helper" in aliases
    assert "acme.helper" in aliases
    assert "acme.helper.helper" in aliases
    assert "acme.helper:helper" in aliases


def test_scheme_adapter_module_aliases_include_library_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scheme-alias-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "lib" / "acme" / "helper.sld").write_text(
        "(define-library (acme helper)\n"
        "  (export helper)\n"
        "  (begin\n"
        "    (define (helper) 1)))\n",
        encoding="utf-8",
    )

    aliases = repository_service.scheme_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="lib/acme/helper.sld",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "lib/acme/helper.sld" in aliases
    assert "lib/acme/helper" in aliases
    assert "lib.acme.helper" in aliases
    assert "helper" in aliases
    assert "acme.helper" in aliases
    assert "acme.helper.helper" in aliases


def test_cobol_adapter_module_aliases_include_program_and_paragraph_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cobol-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "MAINAPP.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. MAINAPP.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           DISPLAY 'ok'.\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )

    aliases = repository_service.cobol_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/MAINAPP.cbl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/mainapp.cbl" in aliases
    assert "src/mainapp" in aliases
    assert "src.mainapp" in aliases
    assert "mainapp" in aliases
    assert "mainapp.main-para" in aliases


def test_plsql_adapter_module_aliases_include_package_and_declared_routines(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "plsql-alias-repo"
    (repo_path / "db").mkdir(parents=True)
    (repo_path / "db" / "app_util.pks").write_text(
        "create or replace package app_util as\n"
        "  procedure record_order(p_order_id in number);\n"
        "end app_util;\n"
        "/\n",
        encoding="utf-8",
    )

    aliases = repository_service.plsql_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="db/app_util.pks",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "db/app_util.pks" in aliases
    assert "db/app_util" in aliases
    assert "db.app_util" in aliases
    assert "app_util" in aliases
    assert "app_util.record_order" in aliases


def test_sas_adapter_module_aliases_include_declared_macros(tmp_path: Path) -> None:
    repo_path = tmp_path / "sas-alias-repo"
    (repo_path / "macros").mkdir(parents=True)
    (repo_path / "macros" / "quality_checks.sas").write_text(
        "%macro assert_nonempty();\n"
        "  %put validating;\n"
        "%mend assert_nonempty;\n"
        "%macro assert_positive();\n"
        "  %put validating;\n"
        "%mend assert_positive;\n",
        encoding="utf-8",
    )

    aliases = repository_service.sas_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="macros/quality_checks.sas",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "macros/quality_checks.sas" in aliases
    assert "macros/quality_checks" in aliases
    assert "macros.quality_checks" in aliases
    assert "quality_checks" in aliases
    assert "assert_nonempty" in aliases
    assert "assert_positive" in aliases


def test_abap_adapter_module_aliases_include_object_and_method_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "abap-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "zcl_math.clas.abap").write_text(
        "CLASS zcl_math DEFINITION PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    CLASS-METHODS add_one IMPORTING iv_value TYPE i RETURNING VALUE(rv_value) TYPE i.\n"
        "ENDCLASS.\n"
        "\n"
        "CLASS zcl_math IMPLEMENTATION.\n"
        "  METHOD add_one.\n"
        "    rv_value = iv_value + 1.\n"
        "  ENDMETHOD.\n"
        "ENDCLASS.\n",
        encoding="utf-8",
    )

    aliases = repository_service.abap_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/zcl_math.clas.abap",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/zcl_math.clas.abap" in aliases
    assert "src/zcl_math.clas" in aliases
    assert "src.zcl_math.clas" in aliases
    assert "zcl_math" in aliases
    assert "zcl_math.add_one" in aliases


def test_matlab_adapter_module_aliases_include_package_and_class_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "matlab-alias-repo"
    (repo_path / "+acme" / "@pipeline").mkdir(parents=True)
    (repo_path / "+acme" / "@pipeline" / "run.m").write_text(
        "function value = run(obj)\n"
        "value = helper();\n"
        "end\n",
        encoding="utf-8",
    )

    aliases = repository_service.matlab_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="+acme/@pipeline/run.m",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "run" in aliases
    assert "acme.pipeline" in aliases
    assert "acme.pipeline.run" in aliases


def test_objective_c_adapter_module_aliases_include_declared_types_and_selectors(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "objective-c-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "ACMHelper.h").write_text(
        "#import <Foundation/Foundation.h>\n"
        "@interface ACMHelper : NSObject\n"
        "+ (void)work;\n"
        "@end\n",
        encoding="utf-8",
    )

    aliases = repository_service.objective_c_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/ACMHelper.h",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acmhelper.h" in aliases
    assert "src/acmhelper" in aliases
    assert "src.acmhelper" in aliases
    assert "acmhelper" in aliases
    assert "work" in aliases
    assert "acmhelper.work" in aliases


def test_repository_intelligence_objective_c_helpers_are_modularized() -> None:
    assert repository_service.objective_c_adapter.normalize_identifier is (
        repository_objective_c_primitives.normalize_identifier
    )
    assert repository_service.objective_c_adapter.strip_comments is (
        repository_objective_c_primitives.strip_comments
    )
    assert repository_service.objective_c_adapter.strip_string_literals is (
        repository_objective_c_primitives.strip_string_literals
    )
    assert repository_service.objective_c_adapter.sanitize_text is (
        repository_objective_c_primitives.sanitize_text
    )
    assert repository_service.objective_c_adapter.has_objective_c_markers is (
        repository_objective_c_primitives.has_objective_c_markers
    )
    assert repository_service.objective_c_adapter.is_probable_objective_c_source is (
        repository_objective_c_primitives.is_probable_objective_c_source
    )
    assert repository_service.objective_c_adapter.collect_symbol_entries is (
        repository_objective_c_primitives.collect_symbol_entries
    )
    assert repository_service.objective_c_adapter.iter_import_targets is (
        repository_objective_c_primitives.iter_import_targets
    )
    assert repository_service.objective_c_adapter.iter_message_sends is (
        repository_objective_c_primitives.iter_message_sends
    )
    assert repository_service.objective_c_adapter.iter_type_reference_tokens is (
        repository_objective_c_primitives.iter_type_reference_tokens
    )
    assert repository_service.objective_c_adapter.module_aliases_for_path is (
        repository_objective_c_analysis_support.module_aliases_for_path
    )
    assert repository_service.objective_c_adapter.resolve_import is (
        repository_objective_c_analysis_support.resolve_import
    )
    assert repository_service.objective_c_adapter.resolve_target is (
        repository_objective_c_analysis_support.resolve_target
    )
    assert repository_service.objective_c_adapter.parse_dependencies_only is (
        repository_objective_c_analysis_support.parse_dependencies_only
    )
    assert repository_service.objective_c_adapter.parse_file is (
        repository_objective_c_analysis_support.parse_file
    )


def test_sql_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "sql-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "customers.sql").write_text(
        "create table sales.customers as\n"
        "select 1 as id;\n",
        encoding="utf-8",
    )

    aliases = repository_service.sql_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/customers.sql",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "models/customers.sql" in aliases
    assert "models/customers" in aliases
    assert "models.customers" in aliases
    assert "customers" in aliases
    assert "sales.customers" in aliases


def test_tsql_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "tsql-alias-repo"
    (repo_path / "dbo" / "Stored Procedures").mkdir(parents=True)
    (repo_path / "dbo" / "Stored Procedures" / "LoadCustomers.sql").write_text(
        "create or alter procedure dbo.LoadCustomers\n"
        "as\n"
        "begin\n"
        "    set nocount on;\n"
        "    select 1 as id;\n"
        "end\n"
        "go\n",
        encoding="utf-8",
    )

    aliases = repository_service.tsql_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="dbo/Stored Procedures/LoadCustomers.sql",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "dbo/stored procedures/loadcustomers.sql" in aliases
    assert "loadcustomers" in aliases
    assert "dbo.loadcustomers" in aliases


def test_build_module_index_uses_registered_root_scoped_sql_alias_builders(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sql-module-index-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "customers.sql").write_text(
        "create table sales.customers as\n"
        "select 1 as id;\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["models/customers.sql"],
        root_path=repo_path,
    )

    assert module_index["sales.customers"] == "models/customers.sql"


def test_analyze_file_dependencies_uses_registered_sql_dependency_parser(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sql-dependency-registry-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "customers.sql").write_text(
        "create table customers as\n"
        "select 1 as id;\n",
        encoding="utf-8",
    )
    orders_path = repo_path / "models" / "orders.sql"
    orders_path.write_text(
        "select * from {{ ref('customers') }}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["models/customers.sql", "models/orders.sql"],
        root_path=repo_path,
    )
    dependencies = repository_service._analyze_file_dependencies(
        root_path=repo_path,
        path=orders_path,
        module_index=module_index,
        workspace_package_index={},
        workspace_go_module_index=None,
        max_file_size_bytes=100_000,
    )

    assert any(dependency.target_file == "models/customers.sql" for dependency in dependencies)


def test_repository_intelligence_contracts_and_shared_helpers_are_modularized() -> None:
    assert repository_service.RepositoryIntelligenceError is (
        repository_contracts.RepositoryIntelligenceError
    )
    assert repository_service.RepositoryIntelligenceError.__module__ == (
        repository_contracts.__name__
    )
    assert repository_service._stable_identifier is repository_shared._stable_identifier
    assert repository_service._stable_identifier.__module__ == repository_shared.__name__


def test_repository_intelligence_runtime_and_cache_helpers_are_modularized() -> None:
    assert repository_service._write_json_atomic is repository_runtime._write_json_atomic
    assert repository_service._write_json_atomic.__module__ == repository_runtime.__name__
    assert repository_service._file_analysis_context_hash is (
        repository_cache._file_analysis_context_hash
    )
    assert repository_service._file_analysis_context_hash.__module__ == (
        repository_cache.__name__
    )


def test_repository_intelligence_modules_stay_within_line_budget() -> None:
    services_dir = Path(repository_service.__file__).parent
    file_paths = sorted(services_dir.glob("repository_intelligence*.py")) + sorted(
        (services_dir / "repository_intelligence_adapters").glob("*.py")
    )
    over_budget: list[tuple[str, int]] = []
    for path in file_paths:
        line_count = sum(1 for _ in path.open())
        if line_count <= 1000:
            continue
        over_budget.append(
            (str(path.relative_to(services_dir.parent.parent.parent)), line_count)
        )

    assert over_budget == []


def test_repository_intelligence_indexing_helpers_are_modularized() -> None:
    assert repository_service._language_for_path is repository_indexing._language_for_path
    assert repository_service._language_for_path.__module__ == repository_indexing.__name__
    assert repository_service._matches_repository_pattern is (
        repository_indexing._matches_repository_pattern
    )
    assert repository_service._resolve_suffix_match is repository_indexing._resolve_suffix_match
    assert repository_service._resolve_directory_prefix_match is (
        repository_indexing._resolve_directory_prefix_match
    )


def test_module_index_lookup_cache_does_not_collide_when_object_ids_repeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_indexing._MODULE_INDEX_LOOKUP_CACHE.clear()
    monkeypatch.setattr(repository_indexing, "id", lambda _value: 1, raising=False)
    first_module_index = {"MediatR": "src/MediatR/Mediator.cs"}
    second_module_index = {"MediatR": "src/MediatR/Handler.cs"}

    assert repository_indexing._resolve_suffix_match(
        module_index=first_module_index,
        suffixes=["src/MediatR/Mediator.cs"],
    ) == "src/MediatR/Mediator.cs"
    assert repository_indexing._resolve_suffix_match(
        module_index=second_module_index,
        suffixes=["src/MediatR/Handler.cs"],
    ) == "src/MediatR/Handler.cs"

    repository_indexing._MODULE_INDEX_LOOKUP_CACHE.clear()


def test_repository_intelligence_js_resolution_helpers_are_modularized() -> None:
    assert repository_service._candidate_js_like_module_keys is (
        repository_js_resolution._candidate_js_like_module_keys
    )
    assert repository_service._candidate_js_like_module_keys.__module__ == (
        repository_js_resolution.__name__
    )
    assert repository_service._resolve_js_like_import is (
        repository_js_resolution._resolve_js_like_import
    )


def test_repository_intelligence_inventory_helpers_are_modularized() -> None:
    assert repository_service._DEFAULT_EXCLUDED_PATH_PARTS is (
        repository_inventory._DEFAULT_EXCLUDED_PATH_PARTS
    )
    assert repository_service._read_dart_pubspec_name is (
        repository_inventory._read_dart_pubspec_name
    )
    assert repository_service._build_workspace_package_index is (
        repository_inventory._build_workspace_package_index
    )
    assert repository_service._build_workspace_dart_package_index is (
        repository_inventory._build_workspace_dart_package_index
    )
    assert repository_service._build_workspace_go_module_index is (
        repository_inventory._build_workspace_go_module_index
    )


def test_repository_intelligence_repository_source_helpers_are_modularized() -> None:
    assert repository_service.REPOSITORY_CONNECTOR_TYPES is (
        repository_repository_source.REPOSITORY_CONNECTOR_TYPES
    )
    assert repository_service._parse_connector_config is (
        repository_repository_source._parse_connector_config
    )
    assert repository_service._git_command is repository_repository_source._git_command
    assert repository_service._git_tracked_content_hashes is (
        repository_repository_source._git_tracked_content_hashes
    )
    assert repository_service.resolved_repository_source is (
        repository_repository_source.resolved_repository_source
    )


def test_repository_intelligence_file_selection_helpers_are_modularized() -> None:
    assert repository_service._TEXT_FILE_SUFFIXES is repository_file_selection.TEXT_FILE_SUFFIXES
    assert repository_service._TEXT_FILE_BASENAMES is (
        repository_file_selection.TEXT_FILE_BASENAMES
    )
    assert repository_service._iter_repository_files is (
        repository_file_selection._iter_repository_files
    )
    assert repository_service._compact_repository_focus_paths is (
        repository_file_selection._compact_repository_focus_paths
    )
    assert repository_service._append_repository_file is (
        repository_file_selection._append_repository_file
    )
    assert repository_service._path_is_indexable_repository_file is (
        repository_file_selection._path_is_indexable_repository_file
    )


def test_repository_intelligence_config_helpers_are_modularized() -> None:
    assert repository_service._strip_jsonc_comments is repository_config._strip_jsonc_comments
    assert repository_service._safe_load_jsonc_dict is repository_config._safe_load_jsonc_dict
    assert repository_service._load_jsonc_object is repository_config._load_jsonc_object
    assert repository_service._tsconfig_root_dir_from_payload is (
        repository_config._tsconfig_root_dir_from_payload
    )
    assert repository_service._resolve_tsconfig_extends_path is (
        repository_config._resolve_tsconfig_extends_path
    )
    assert repository_service._update_tsconfig_root_dir_text is (
        repository_config._update_tsconfig_root_dir_text
    )
    assert repository_service._relative_root_dir is repository_config._relative_root_dir
    assert repository_service._resolved_tsconfig_compiler_options is (
        repository_config._resolved_tsconfig_compiler_options
    )
    assert repository_service._tsconfig_module_candidates is (
        repository_config._tsconfig_module_candidates
    )
    assert repository_service._extend_module_index_with_tsconfig_aliases is (
        repository_config._extend_module_index_with_tsconfig_aliases
    )
    assert repository_service._extend_module_index_with_dart_package_aliases is (
        repository_config._extend_module_index_with_dart_package_aliases
    )
    assert repository_service._extend_module_index_with_zig_build_aliases is (
        repository_config._extend_module_index_with_zig_build_aliases
    )


def test_repository_intelligence_graph_helpers_are_modularized() -> None:
    assert repository_service._snapshot_file_graph_edges is (
        repository_graph._snapshot_file_graph_edges
    )
    assert repository_service._snapshot_file_graph_edges.__module__ == (
        repository_graph.__name__
    )
    assert repository_service._score_snapshot_files is repository_graph._score_snapshot_files
    assert repository_service._resolve_graph_query_seeds is (
        repository_graph._resolve_graph_query_seeds
    )
    assert repository_service._collapse_wrapper_neighbors is (
        repository_graph._collapse_wrapper_neighbors
    )
    assert repository_service._snippet_for_file is repository_graph._snippet_for_file


def test_repository_intelligence_native_dispatch_helpers_are_modularized() -> None:
    assert repository_service._resolve_sql_target is repository_native_dispatch._resolve_sql_target
    assert repository_native_dispatch._resolve_sql_target is (
        repository_native_resolution._resolve_sql_target
    )
    assert repository_service._resolve_matlab_import is (
        repository_native_dispatch._resolve_matlab_import
    )
    assert repository_native_dispatch._resolve_matlab_import is (
        repository_native_resolution._resolve_matlab_import
    )
    assert repository_native_dispatch._dependencies_from_specs is (
        repository_native_resolution._dependencies_from_specs
    )
    assert repository_native_dispatch._symbols_from_entries is (
        repository_native_resolution._symbols_from_entries
    )
    assert repository_service._parse_d_file is repository_native_dispatch._parse_d_file
    assert repository_service._parse_foxpro_dependencies_only is (
        repository_native_dispatch._parse_foxpro_dependencies_only
    )
    assert repository_service._parse_objective_c_file is (
        repository_native_dispatch._parse_objective_c_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["sql"] is (
        repository_native_dispatch._parse_sql_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["racket"] is (
        repository_native_dispatch._parse_racket_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["scheme"] is (
        repository_native_dispatch._parse_scheme_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["emacslisp"] is (
        repository_native_dispatch._parse_emacslisp_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["applescript"] is (
        repository_native_dispatch._parse_applescript_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["tsql"] is (
        repository_native_dispatch._parse_tsql_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["vb6"] is (
        repository_native_dispatch._parse_classic_visual_basic_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["vba"] is (
        repository_native_dispatch._parse_vba_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["objectivec"] is (
        repository_native_dispatch._parse_objective_c_file
    )
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["racket"] is (
        repository_native_dispatch._parse_racket_file
    )
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["scheme"] is (
        repository_native_dispatch._parse_scheme_file
    )
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["emacslisp"] is (
        repository_native_dispatch._parse_emacslisp_file
    )
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["applescript"] is (
        repository_native_dispatch._parse_applescript_file
    )
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["tsql"] is (
        repository_native_dispatch._parse_tsql_file
    )
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["vba"] is (
        repository_native_dispatch._parse_vba_file
    )


def test_repository_intelligence_module_alias_helpers_are_modularized() -> None:
    assert repository_service._build_module_index is repository_module_aliases._build_module_index
    assert repository_service._go_package_symbol_alias is (
        repository_module_aliases._go_package_symbol_alias
    )
    assert repository_service._extend_module_index_with_go_package_symbol_aliases is (
        repository_module_aliases._extend_module_index_with_go_package_symbol_aliases
    )
    assert repository_service._r_module_aliases_for_path is (
        repository_module_aliases._r_module_aliases_for_path
    )
    assert repository_service._collect_type_symbol_entries is (
        repository_module_aliases._collect_type_symbol_entries
    )
    assert repository_service._ROOT_SCOPED_MODULE_ALIAS_BUILDERS is (
        repository_module_aliases._ROOT_SCOPED_MODULE_ALIAS_BUILDERS
    )


def test_repository_intelligence_root_scoped_alias_helpers_are_modularized() -> None:
    assert repository_module_aliases._r_module_aliases_for_path is (
        repository_root_scoped_aliases._r_module_aliases_for_path
    )
    assert repository_module_aliases._julia_module_aliases_for_path is (
        repository_root_scoped_aliases._julia_module_aliases_for_path
    )
    assert repository_module_aliases._nim_declared_symbol_aliases_for_path is (
        repository_root_scoped_aliases._nim_declared_symbol_aliases_for_path
    )
    assert repository_module_aliases._ROOT_SCOPED_MODULE_ALIAS_BUILDERS is (
        repository_root_scoped_aliases._ROOT_SCOPED_MODULE_ALIAS_BUILDERS
    )


def test_repository_intelligence_language_resolution_helpers_are_modularized() -> None:
    assert repository_service._resolve_python_import is (
        repository_language_resolution._resolve_python_import
    )
    assert repository_service._resolve_go_import is (
        repository_language_resolution._resolve_go_import
    )
    assert repository_service._resolve_ruby_import is (
        repository_language_resolution._resolve_ruby_import
    )
    assert repository_service._augment_go_package_symbol_references is (
        repository_language_resolution._augment_go_package_symbol_references
    )
    assert repository_service._best_package_symbol_target is (
        repository_language_resolution._best_package_symbol_target
    )
    assert repository_service._resolve_symbol_reference_target is (
        repository_language_resolution._resolve_symbol_reference_target
    )
    assert repository_service._extract_js_like_import_bindings is (
        repository_language_resolution._extract_js_like_import_bindings
    )
    assert repository_service._is_julia_operational_reference_name is (
        repository_language_resolution._is_julia_operational_reference_name
    )


def test_repository_intelligence_package_symbol_resolution_helpers_are_modularized() -> None:
    assert repository_language_resolution._best_package_symbol_target is (
        repository_package_symbol_resolution._best_package_symbol_target
    )
    assert repository_language_resolution._resolve_symbol_reference_target is (
        repository_package_symbol_resolution._resolve_symbol_reference_target
    )
    assert repository_language_resolution._augment_go_package_symbol_references is (
        repository_package_symbol_resolution._augment_go_package_symbol_references
    )
    assert repository_language_resolution._augment_r_package_symbol_references is (
        repository_package_symbol_resolution._augment_r_package_symbol_references
    )
    assert repository_language_resolution._augment_julia_package_symbol_references is (
        repository_package_symbol_resolution._augment_julia_package_symbol_references
    )


def test_repository_intelligence_simple_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._parse_python_file is (
        repository_simple_parser_dispatch._parse_python_file
    )
    assert repository_service._parse_coffeescript_file is (
        repository_simple_parser_dispatch._parse_coffeescript_file
    )
    assert repository_service._parse_vala_file is (
        repository_simple_parser_dispatch._parse_vala_file
    )
    assert repository_service._parse_mql5_file is (
        repository_simple_parser_dispatch._parse_mql5_file
    )
    assert repository_service._parse_gams_file is (
        repository_simple_parser_dispatch._parse_gams_file
    )
    assert repository_service._parse_nix_file is (
        repository_simple_parser_dispatch._parse_nix_file
    )
    assert repository_service._parse_nushell_file is (
        repository_simple_parser_dispatch._parse_nushell_file
    )
    assert repository_service._parse_openscad_file is (
        repository_simple_parser_dispatch._parse_openscad_file
    )
    assert repository_service._parse_purescript_file is (
        repository_simple_parser_dispatch._parse_purescript_file
    )
    assert repository_service._parse_gleam_file is (
        repository_simple_parser_dispatch._parse_gleam_file
    )
    assert repository_service._parse_starlark_file is (
        repository_simple_parser_dispatch._parse_starlark_file
    )
    assert repository_service._parse_vimscript_file is (
        repository_simple_parser_dispatch._parse_vimscript_file
    )
    assert repository_service._parse_smalltalk_file is (
        repository_simple_parser_dispatch._parse_smalltalk_file
    )
    assert repository_service._parse_go_file is repository_simple_parser_dispatch._parse_go_file
    assert repository_service._parse_dart_file is (
        repository_simple_parser_dispatch._parse_dart_file
    )
    assert repository_service._parse_nim_file is (
        repository_simple_parser_dispatch._parse_nim_file
    )
    assert repository_service._extract_dart_import_bindings is (
        repository_simple_parser_dispatch._extract_dart_import_bindings
    )
    assert repository_service._parse_c_family_dependencies_only is (
        repository_simple_parser_dispatch._parse_c_family_dependencies_only
    )
    assert repository_service._parse_coffeescript_dependencies_only is (
        repository_simple_parser_dispatch._parse_coffeescript_dependencies_only
    )
    assert repository_service._parse_vala_dependencies_only is (
        repository_simple_parser_dispatch._parse_vala_dependencies_only
    )
    assert repository_service._parse_mql5_dependencies_only is (
        repository_simple_parser_dispatch._parse_mql5_dependencies_only
    )
    assert repository_service._parse_gams_dependencies_only is (
        repository_simple_parser_dispatch._parse_gams_dependencies_only
    )
    assert repository_service._parse_nix_dependencies_only is (
        repository_simple_parser_dispatch._parse_nix_dependencies_only
    )
    assert repository_service._parse_nushell_dependencies_only is (
        repository_simple_parser_dispatch._parse_nushell_dependencies_only
    )
    assert repository_service._parse_openscad_dependencies_only is (
        repository_simple_parser_dispatch._parse_openscad_dependencies_only
    )
    assert repository_service._parse_purescript_dependencies_only is (
        repository_simple_parser_dispatch._parse_purescript_dependencies_only
    )
    assert repository_service._parse_gleam_dependencies_only is (
        repository_simple_parser_dispatch._parse_gleam_dependencies_only
    )
    assert repository_service._parse_starlark_dependencies_only is (
        repository_simple_parser_dispatch._parse_starlark_dependencies_only
    )
    assert repository_service._parse_vimscript_dependencies_only is (
        repository_simple_parser_dispatch._parse_vimscript_dependencies_only
    )
    assert repository_service._parse_smalltalk_dependencies_only is (
        repository_simple_parser_dispatch._parse_smalltalk_dependencies_only
    )


def test_repository_intelligence_fish_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._parse_fish_file is (
        repository_fish_parser_dispatch._parse_fish_file
    )
    assert repository_service._parse_fish_dependencies_only is (
        repository_fish_parser_dispatch._parse_fish_dependencies_only
    )


def test_repository_intelligence_batchfile_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["batchfile"] is (
        repository_batchfile_parser_dispatch._parse_batchfile_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["batchfile"] is (
        repository_batchfile_parser_dispatch._parse_batchfile_dependencies_only
    )


def test_repository_intelligence_makefile_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["makefile"] is (
        repository_makefile_parser_dispatch._parse_makefile_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["makefile"] is (
        repository_makefile_parser_dispatch._parse_makefile_dependencies_only
    )


def test_repository_intelligence_odin_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["odin"] is (
        repository_odin_parser_dispatch._parse_odin_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["odin"] is (
        repository_odin_parser_dispatch._parse_odin_dependencies_only
    )


def test_repository_intelligence_factor_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["factor"] is (
        repository_factor_parser_dispatch._parse_factor_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["factor"] is (
        repository_factor_parser_dispatch._parse_factor_dependencies_only
    )


def test_repository_intelligence_cue_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["cue"] is (
        repository_cue_parser_dispatch._parse_cue_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["cue"] is (
        repository_cue_parser_dispatch._parse_cue_dependencies_only
    )


def test_repository_intelligence_janet_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._parse_janet_file is (
        repository_janet_parser_dispatch._parse_janet_file
    )
    assert repository_service._parse_janet_dependencies_only is (
        repository_janet_parser_dispatch._parse_janet_dependencies_only
    )


def test_repository_intelligence_rego_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._parse_rego_file is (
        repository_rego_parser_dispatch._parse_rego_file
    )
    assert repository_service._parse_rego_dependencies_only is (
        repository_rego_parser_dispatch._parse_rego_dependencies_only
    )


def test_repository_intelligence_yara_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._parse_yara_file is (
        repository_yara_parser_dispatch._parse_yara_file
    )
    assert repository_service._parse_yara_dependencies_only is (
        repository_yara_parser_dispatch._parse_yara_dependencies_only
    )


def test_repository_intelligence_hcl_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["hcl"] is (
        repository_hcl_parser_dispatch._parse_hcl_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["hcl"] is (
        repository_hcl_parser_dispatch._parse_hcl_dependencies_only
    )


def test_repository_intelligence_bicep_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["bicep"] is (
        repository_bicep_parser_dispatch._parse_bicep_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["bicep"] is (
        repository_bicep_parser_dispatch._parse_bicep_dependencies_only
    )


def test_repository_intelligence_raku_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["raku"] is (
        repository_raku_parser_dispatch._parse_raku_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["raku"] is (
        repository_raku_parser_dispatch._parse_raku_dependencies_only
    )


def test_repository_intelligence_agda_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["agda"] is (
        repository_agda_parser_dispatch._parse_agda_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["agda"] is (
        repository_agda_parser_dispatch._parse_agda_dependencies_only
    )


def test_repository_intelligence_idris_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["idris"] is (
        repository_idris_parser_dispatch._parse_idris_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["idris"] is (
        repository_idris_parser_dispatch._parse_idris_dependencies_only
    )


def test_repository_intelligence_tlaplus_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["tlaplus"] is (
        repository_tlaplus_parser_dispatch._parse_tlaplus_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["tlaplus"] is (
        repository_tlaplus_parser_dispatch._parse_tlaplus_dependencies_only
    )


def test_repository_intelligence_logtalk_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["logtalk"] is (
        repository_logtalk_parser_dispatch._parse_logtalk_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["logtalk"] is (
        repository_logtalk_parser_dispatch._parse_logtalk_dependencies_only
    )


def test_repository_intelligence_glsl_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["glsl"] is (
        repository_glsl_parser_dispatch._parse_glsl_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["glsl"] is (
        repository_glsl_parser_dispatch._parse_glsl_dependencies_only
    )


def test_repository_intelligence_hlsl_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["hlsl"] is (
        repository_hlsl_parser_dispatch._parse_hlsl_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["hlsl"] is (
        repository_hlsl_parser_dispatch._parse_hlsl_dependencies_only
    )


def test_repository_intelligence_robotframework_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["robotframework"] is (
        repository_robotframework_parser_dispatch._parse_robotframework_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["robotframework"] is (
        repository_robotframework_parser_dispatch._parse_robotframework_dependencies_only
    )


def test_repository_intelligence_dockerfile_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["dockerfile"] is (
        repository_dockerfile_parser_dispatch._parse_dockerfile_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["dockerfile"] is (
        repository_dockerfile_parser_dispatch._parse_dockerfile_dependencies_only
    )


def test_repository_intelligence_scss_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["scss"] is (
        repository_scss_parser_dispatch._parse_scss_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["scss"] is (
        repository_scss_parser_dispatch._parse_scss_dependencies_only
    )


def test_repository_intelligence_typst_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["typst"] is (
        repository_typst_parser_dispatch._parse_typst_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["typst"] is (
        repository_typst_parser_dispatch._parse_typst_dependencies_only
    )


def test_repository_intelligence_coq_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["coq"] is (
        repository_coq_parser_dispatch._parse_coq_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["coq"] is (
        repository_coq_parser_dispatch._parse_coq_dependencies_only
    )


def test_repository_intelligence_lean_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["lean"] is (
        repository_lean_parser_dispatch._parse_lean_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["lean"] is (
        repository_lean_parser_dispatch._parse_lean_dependencies_only
    )


def test_repository_intelligence_chapel_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["chapel"] is (
        repository_chapel_parser_dispatch._parse_chapel_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["chapel"] is (
        repository_chapel_parser_dispatch._parse_chapel_dependencies_only
    )


def test_repository_intelligence_eiffel_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["eiffel"] is (
        repository_eiffel_parser_dispatch._parse_eiffel_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["eiffel"] is (
        repository_eiffel_parser_dispatch._parse_eiffel_dependencies_only
    )


def test_repository_intelligence_puppet_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["puppet"] is (
        repository_puppet_parser_dispatch._parse_puppet_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["puppet"] is (
        repository_puppet_parser_dispatch._parse_puppet_dependencies_only
    )


def test_repository_intelligence_hack_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["hack"] is (
        repository_hack_parser_dispatch._parse_hack_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["hack"] is (
        repository_hack_parser_dispatch._parse_hack_dependencies_only
    )


def test_repository_intelligence_adapter_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._parse_actionscript_file is (
        repository_adapter_parser_dispatch._parse_actionscript_file
    )
    assert repository_service._parse_erlang_file is (
        repository_adapter_parser_dispatch._parse_erlang_file
    )
    assert repository_service._parse_shell_dependencies_only is (
        repository_adapter_parser_dispatch._parse_shell_dependencies_only
    )
    assert repository_service._extract_ruby_import_bindings is (
        repository_adapter_parser_dispatch._extract_ruby_import_bindings
    )
    assert repository_service._parse_csharp_file is (
        repository_adapter_parser_dispatch._parse_csharp_file
    )
    assert repository_service._parse_jvm_dependencies_only is (
        repository_adapter_parser_dispatch._parse_jvm_dependencies_only
    )
    assert repository_service._parse_ladder_file is (
        repository_adapter_parser_dispatch._parse_ladder_file
    )
    assert repository_service._parse_labview_file is (
        repository_adapter_parser_dispatch._parse_labview_file
    )
    assert repository_service._parse_verilog_file is (
        repository_verilog_parser_dispatch._parse_verilog_file
    )
    assert repository_service._parse_systemverilog_file is (
        repository_adapter_parser_dispatch._parse_systemverilog_file
    )
    assert repository_service._parse_gdscript_file is (
        repository_adapter_parser_dispatch._parse_gdscript_file
    )
    assert repository_service._parse_vhdl_file is repository_adapter_parser_dispatch._parse_vhdl_file
    assert repository_service._parse_tcl_file is repository_adapter_parser_dispatch._parse_tcl_file
    assert repository_service._parse_rpg_file is repository_adapter_parser_dispatch._parse_rpg_file
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS is (
        repository_adapter_parser_dispatch.REGISTERED_ADAPTER_FILE_PARSERS
    )


def test_repository_intelligence_wolfram_helpers_are_modularized() -> None:
    assert repository_service.wolfram_adapter.strip_comments is (
        repository_wolfram_support.strip_comments
    )
    assert repository_service.wolfram_adapter.normalize_context_name is (
        repository_wolfram_support.normalize_context_name
    )
    assert repository_service.wolfram_adapter.paclet_kernel_entries is (
        repository_wolfram_support.paclet_kernel_entries
    )
    assert repository_service.wolfram_adapter.has_wolfram_path_hints is (
        repository_wolfram_support.has_wolfram_path_hints
    )
    assert repository_service.wolfram_adapter.is_probable_wolfram_source is (
        repository_wolfram_support.is_probable_wolfram_source
    )


def test_repository_intelligence_solidity_helpers_are_modularized() -> None:
    assert repository_service.solidity_adapter.strip_comments is (
        repository_solidity_support.strip_comments
    )
    assert repository_service.solidity_adapter.normalize_identifier is (
        repository_solidity_support.normalize_identifier
    )
    assert repository_service.solidity_adapter.normalize_import_target is (
        repository_solidity_support.normalize_import_target
    )
    assert repository_service.solidity_adapter.collect_symbol_entries is (
        repository_solidity_support.collect_symbol_entries
    )
    assert repository_service.solidity_adapter.resolve_import is (
        repository_solidity_support.resolve_import
    )


def test_repository_intelligence_actionscript_helpers_are_modularized() -> None:
    assert repository_service.actionscript_adapter.strip_comments is (
        repository_actionscript_primitives.strip_comments
    )
    assert repository_service.actionscript_adapter.has_actionscript_path_hints is (
        repository_actionscript_primitives.has_actionscript_path_hints
    )
    assert repository_service.actionscript_adapter.module_aliases_for_path is (
        repository_actionscript_analysis_support.module_aliases_for_path
    )
    assert repository_service.actionscript_adapter.parse_dependencies_only is (
        repository_actionscript_analysis_support.parse_dependencies_only
    )
    assert repository_service.actionscript_adapter.parse_file is (
        repository_actionscript_analysis_support.parse_file
    )


def test_repository_intelligence_applescript_helpers_are_modularized() -> None:
    assert repository_service.applescript_adapter.strip_comments is (
        repository_applescript_primitives.strip_comments
    )
    assert repository_service.applescript_adapter.has_applescript_path_hints is (
        repository_applescript_primitives.has_applescript_path_hints
    )
    assert repository_service.applescript_adapter.is_probable_applescript_source is (
        repository_applescript_primitives.is_probable_applescript_source
    )
    assert repository_service.applescript_adapter.import_targets_for_text is (
        repository_applescript_primitives.import_targets_for_text
    )
    assert repository_service.applescript_adapter.module_aliases_for_path is (
        repository_applescript_analysis_support.module_aliases_for_path
    )
    assert repository_service.applescript_adapter.resolve_import is (
        repository_applescript_analysis_support.resolve_import
    )
    assert repository_service.applescript_adapter.parse_dependencies_only is (
        repository_applescript_analysis_support.parse_dependencies_only
    )
    assert repository_service.applescript_adapter.parse_file is (
        repository_applescript_analysis_support.parse_file
    )


def test_repository_intelligence_awk_helpers_are_modularized() -> None:
    assert repository_service.awk_adapter.strip_comments is (
        repository_awk_primitives.strip_comments
    )
    assert repository_service.awk_adapter.has_awk_shebang is (
        repository_awk_primitives.has_awk_shebang
    )
    assert repository_service.awk_adapter.is_probable_awk_source is (
        repository_awk_primitives.is_probable_awk_source
    )
    assert repository_service.awk_adapter.module_aliases_for_path is (
        repository_awk_analysis_support.module_aliases_for_path
    )
    assert repository_service.awk_adapter.parse_dependencies_only is (
        repository_awk_analysis_support.parse_dependencies_only
    )
    assert repository_service.awk_adapter.parse_file is (
        repository_awk_analysis_support.parse_file
    )


def test_repository_intelligence_coffeescript_helpers_are_modularized() -> None:
    assert repository_service.coffeescript_adapter.strip_comments is (
        repository_coffeescript_primitives.strip_comments
    )
    assert repository_service.coffeescript_adapter.has_coffeescript_path_hints is (
        repository_coffeescript_primitives.has_coffeescript_path_hints
    )
    assert repository_service.coffeescript_adapter.is_probable_coffeescript_source is (
        repository_coffeescript_primitives.is_probable_coffeescript_source
    )
    assert repository_service.coffeescript_adapter.module_aliases_for_path is (
        repository_coffeescript_analysis_support.module_aliases_for_path
    )
    assert repository_service.coffeescript_adapter.resolve_import is (
        repository_coffeescript_analysis_support.resolve_import
    )
    assert repository_service.coffeescript_adapter.parse_dependencies_only is (
        repository_coffeescript_analysis_support.parse_dependencies_only
    )
    assert repository_service.coffeescript_adapter.parse_file is (
        repository_coffeescript_analysis_support.parse_file
    )


def test_repository_intelligence_vala_helpers_are_modularized() -> None:
    assert repository_service.vala_adapter.strip_comments is (
        repository_vala_primitives.strip_comments
    )
    assert repository_service.vala_adapter.has_vala_path_hints is (
        repository_vala_primitives.has_vala_path_hints
    )
    assert repository_service.vala_adapter.is_probable_vala_source is (
        repository_vala_primitives.is_probable_vala_source
    )
    assert repository_service.vala_adapter.module_aliases_for_path is (
        repository_vala_analysis_support.module_aliases_for_path
    )
    assert repository_service.vala_adapter.resolve_import is (
        repository_vala_analysis_support.resolve_import
    )
    assert repository_service.vala_adapter.parse_dependencies_only is (
        repository_vala_analysis_support.parse_dependencies_only
    )
    assert repository_service.vala_adapter.parse_file is (
        repository_vala_analysis_support.parse_file
    )


def test_repository_intelligence_mql5_helpers_are_modularized() -> None:
    assert repository_service.mql5_adapter.strip_comments is (
        repository_mql5_primitives.strip_comments
    )
    assert repository_service.mql5_adapter.has_mql5_path_hints is (
        repository_mql5_primitives.has_mql5_path_hints
    )
    assert repository_service.mql5_adapter.is_probable_mql5_source is (
        repository_mql5_primitives.is_probable_mql5_source
    )
    assert repository_service.mql5_adapter.import_targets_for_text is (
        repository_mql5_primitives.import_targets_for_text
    )
    assert repository_service.mql5_adapter.project_file_entries is (
        repository_mql5_primitives.project_file_entries
    )
    assert repository_service.mql5_adapter.module_aliases_for_path is (
        repository_mql5_analysis_support.module_aliases_for_path
    )
    assert repository_service.mql5_adapter.resolve_import is (
        repository_mql5_analysis_support.resolve_import
    )
    assert repository_service.mql5_adapter.parse_dependencies_only is (
        repository_mql5_analysis_support.parse_dependencies_only
    )
    assert repository_service.mql5_adapter.parse_file is (
        repository_mql5_analysis_support.parse_file
    )


def test_repository_intelligence_gams_helpers_are_modularized() -> None:
    assert repository_service.gams_adapter.strip_comments is (
        repository_gams_primitives.strip_comments
    )
    assert repository_service.gams_adapter.has_gams_path_hints is (
        repository_gams_primitives.has_gams_path_hints
    )
    assert repository_service.gams_adapter.is_probable_gams_source is (
        repository_gams_primitives.is_probable_gams_source
    )
    assert repository_service.gams_adapter.import_targets_for_text is (
        repository_gams_primitives.import_targets_for_text
    )
    assert repository_service.gams_adapter.module_aliases_for_path is (
        repository_gams_analysis_support.module_aliases_for_path
    )
    assert repository_service.gams_adapter.resolve_import is (
        repository_gams_analysis_support.resolve_import
    )
    assert repository_service.gams_adapter.parse_dependencies_only is (
        repository_gams_analysis_support.parse_dependencies_only
    )
    assert repository_service.gams_adapter.parse_file is (
        repository_gams_analysis_support.parse_file
    )


def test_repository_intelligence_openscad_helpers_are_modularized() -> None:
    assert repository_service.openscad_adapter.strip_comments is (
        repository_openscad_primitives.strip_comments
    )
    assert repository_service.openscad_adapter.has_openscad_path_hints is (
        repository_openscad_primitives.has_openscad_path_hints
    )
    assert repository_service.openscad_adapter.is_probable_openscad_source is (
        repository_openscad_primitives.is_probable_openscad_source
    )
    assert repository_service.openscad_adapter.import_targets_for_text is (
        repository_openscad_primitives.import_targets_for_text
    )
    assert repository_service.openscad_adapter.module_aliases_for_path is (
        repository_openscad_analysis_support.module_aliases_for_path
    )
    assert repository_service.openscad_adapter.resolve_import is (
        repository_openscad_analysis_support.resolve_import
    )
    assert repository_service.openscad_adapter.parse_dependencies_only is (
        repository_openscad_analysis_support.parse_dependencies_only
    )
    assert repository_service.openscad_adapter.parse_file is (
        repository_openscad_analysis_support.parse_file
    )


def test_repository_intelligence_purescript_helpers_are_modularized() -> None:
    assert repository_service.purescript_adapter.strip_comments is (
        repository_purescript_primitives.strip_comments
    )
    assert repository_service.purescript_adapter.has_purescript_path_hints is (
        repository_purescript_primitives.has_purescript_path_hints
    )
    assert repository_service.purescript_adapter.is_probable_purescript_source is (
        repository_purescript_primitives.is_probable_purescript_source
    )
    assert repository_service.purescript_adapter.parse_import_names is (
        repository_purescript_primitives.parse_import_names
    )
    assert repository_service.purescript_adapter.module_aliases_for_path is (
        repository_purescript_analysis_support.module_aliases_for_path
    )
    assert repository_service.purescript_adapter.resolve_import is (
        repository_purescript_analysis_support.resolve_import
    )
    assert repository_service.purescript_adapter.parse_dependencies_only is (
        repository_purescript_analysis_support.parse_dependencies_only
    )
    assert repository_service.purescript_adapter.parse_file is (
        repository_purescript_analysis_support.parse_file
    )


def test_repository_intelligence_gleam_helpers_are_modularized() -> None:
    assert repository_service.gleam_adapter.strip_comments is (
        repository_gleam_primitives.strip_comments
    )
    assert repository_service.gleam_adapter.has_gleam_path_hints is (
        repository_gleam_primitives.has_gleam_path_hints
    )
    assert repository_service.gleam_adapter.is_probable_gleam_source is (
        repository_gleam_primitives.is_probable_gleam_source
    )
    assert repository_service.gleam_adapter.parse_import_names is (
        repository_gleam_primitives.parse_import_names
    )
    assert repository_service.gleam_adapter.module_aliases_for_path is (
        repository_gleam_analysis_support.module_aliases_for_path
    )
    assert repository_service.gleam_adapter.resolve_import is (
        repository_gleam_analysis_support.resolve_import
    )
    assert repository_service.gleam_adapter.parse_dependencies_only is (
        repository_gleam_analysis_support.parse_dependencies_only
    )
    assert repository_service.gleam_adapter.parse_file is (
        repository_gleam_analysis_support.parse_file
    )


def test_repository_intelligence_janet_helpers_are_modularized() -> None:
    assert repository_service.janet_adapter.strip_comments is (
        repository_janet_primitives.strip_comments
    )
    assert repository_service.janet_adapter.has_janet_path_hints is (
        repository_janet_primitives.has_janet_path_hints
    )
    assert repository_service.janet_adapter.is_probable_janet_source is (
        repository_janet_primitives.is_probable_janet_source
    )
    assert repository_service.janet_adapter.parse_import_statements is (
        repository_janet_primitives.parse_import_statements
    )
    assert repository_service.janet_adapter.module_aliases_for_path is (
        repository_janet_analysis_support.module_aliases_for_path
    )
    assert repository_service.janet_adapter.resolve_import is (
        repository_janet_analysis_support.resolve_import
    )
    assert repository_service.janet_adapter.parse_dependencies_only is (
        repository_janet_analysis_support.parse_dependencies_only
    )
    assert repository_service.janet_adapter.parse_file is (
        repository_janet_analysis_support.parse_file
    )


def test_repository_intelligence_rego_helpers_are_modularized() -> None:
    assert repository_service.rego_adapter.strip_comments is (
        repository_rego_primitives.strip_comments
    )
    assert repository_service.rego_adapter.has_rego_path_hints is (
        repository_rego_primitives.has_rego_path_hints
    )
    assert repository_service.rego_adapter.is_probable_rego_source is (
        repository_rego_primitives.is_probable_rego_source
    )
    assert repository_service.rego_adapter.parse_import_statements is (
        repository_rego_primitives.parse_import_statements
    )
    assert repository_service.rego_adapter.module_aliases_for_path is (
        repository_rego_analysis_support.module_aliases_for_path
    )
    assert repository_service.rego_adapter.resolve_import is (
        repository_rego_analysis_support.resolve_import
    )
    assert repository_service.rego_adapter.parse_dependencies_only is (
        repository_rego_analysis_support.parse_dependencies_only
    )
    assert repository_service.rego_adapter.parse_file is (
        repository_rego_analysis_support.parse_file
    )


def test_repository_intelligence_yara_helpers_are_modularized() -> None:
    assert repository_service.yara_adapter.strip_comments is (
        repository_yara_primitives.strip_comments
    )
    assert repository_service.yara_adapter.has_yara_path_hints is (
        repository_yara_primitives.has_yara_path_hints
    )
    assert repository_service.yara_adapter.is_probable_yara_source is (
        repository_yara_primitives.is_probable_yara_source
    )
    assert repository_service.yara_adapter.parse_include_statements is (
        repository_yara_primitives.parse_include_statements
    )
    assert repository_service.yara_adapter.module_aliases_for_path is (
        repository_yara_analysis_support.module_aliases_for_path
    )
    assert repository_service.yara_adapter.resolve_include is (
        repository_yara_analysis_support.resolve_include
    )
    assert repository_service.yara_adapter.parse_dependencies_only is (
        repository_yara_analysis_support.parse_dependencies_only
    )
    assert repository_service.yara_adapter.parse_file is (
        repository_yara_analysis_support.parse_file
    )


def test_repository_intelligence_hcl_helpers_are_modularized() -> None:
    assert repository_service.hcl_adapter.strip_comments is (
        repository_hcl_primitives.strip_comments
    )
    assert repository_service.hcl_adapter.has_hcl_path_hints is (
        repository_hcl_primitives.has_hcl_path_hints
    )
    assert repository_service.hcl_adapter.is_probable_hcl_source is (
        repository_hcl_primitives.is_probable_hcl_source
    )
    assert repository_service.hcl_adapter.iter_block_entries is (
        repository_hcl_primitives.iter_block_entries
    )
    assert repository_service.hcl_adapter.module_aliases_for_path is (
        repository_hcl_analysis_support.module_aliases_for_path
    )
    assert repository_service.hcl_adapter.resolve_module_source is (
        repository_hcl_analysis_support.resolve_module_source
    )
    assert repository_service.hcl_adapter.parse_dependencies_only is (
        repository_hcl_analysis_support.parse_dependencies_only
    )
    assert repository_service.hcl_adapter.parse_file is (
        repository_hcl_analysis_support.parse_file
    )


def test_repository_intelligence_bicep_helpers_are_modularized() -> None:
    assert repository_service.bicep_adapter.strip_comments is (
        repository_bicep_primitives.strip_comments
    )
    assert repository_service.bicep_adapter.has_bicep_path_hints is (
        repository_bicep_primitives.has_bicep_path_hints
    )
    assert repository_service.bicep_adapter.is_probable_bicep_source is (
        repository_bicep_primitives.is_probable_bicep_source
    )
    assert repository_service.bicep_adapter.parse_module_statements is (
        repository_bicep_primitives.parse_module_statements
    )
    assert repository_service.bicep_adapter.module_aliases_for_path is (
        repository_bicep_analysis_support.module_aliases_for_path
    )
    assert repository_service.bicep_adapter.resolve_module_source is (
        repository_bicep_analysis_support.resolve_module_source
    )
    assert repository_service.bicep_adapter.parse_dependencies_only is (
        repository_bicep_analysis_support.parse_dependencies_only
    )
    assert repository_service.bicep_adapter.parse_file is (
        repository_bicep_analysis_support.parse_file
    )


def test_repository_intelligence_raku_helpers_are_modularized() -> None:
    assert repository_service.raku_adapter.strip_comments is (
        repository_raku_primitives.strip_comments
    )
    assert repository_service.raku_adapter.has_raku_path_hints is (
        repository_raku_primitives.has_raku_path_hints
    )
    assert repository_service.raku_adapter.is_probable_raku_source is (
        repository_raku_primitives.is_probable_raku_source
    )
    assert repository_service.raku_adapter.parse_import_statements is (
        repository_raku_primitives.parse_import_statements
    )
    assert repository_service.raku_adapter.module_aliases_for_path is (
        repository_raku_analysis_support.module_aliases_for_path
    )
    assert repository_service.raku_adapter.resolve_import is (
        repository_raku_analysis_support.resolve_import
    )
    assert repository_service.raku_adapter.parse_dependencies_only is (
        repository_raku_analysis_support.parse_dependencies_only
    )
    assert repository_service.raku_adapter.parse_file is (
        repository_raku_analysis_support.parse_file
    )


def test_repository_intelligence_agda_helpers_are_modularized() -> None:
    assert repository_service.agda_adapter.strip_comments is (
        repository_agda_primitives.strip_comments
    )
    assert repository_service.agda_adapter.has_agda_path_hints is (
        repository_agda_primitives.has_agda_path_hints
    )
    assert repository_service.agda_adapter.is_probable_agda_source is (
        repository_agda_primitives.is_probable_agda_source
    )
    assert repository_service.agda_adapter.parse_import_names is (
        repository_agda_primitives.parse_import_names
    )
    assert repository_service.agda_adapter.module_aliases_for_path is (
        repository_agda_analysis_support.module_aliases_for_path
    )
    assert repository_service.agda_adapter.resolve_import is (
        repository_agda_analysis_support.resolve_import
    )
    assert repository_service.agda_adapter.parse_dependencies_only is (
        repository_agda_analysis_support.parse_dependencies_only
    )
    assert repository_service.agda_adapter.parse_file is (
        repository_agda_analysis_support.parse_file
    )


def test_repository_intelligence_idris_helpers_are_modularized() -> None:
    assert repository_service.idris_adapter.strip_comments is (
        repository_idris_primitives.strip_comments
    )
    assert repository_service.idris_adapter.has_idris_path_hints is (
        repository_idris_primitives.has_idris_path_hints
    )
    assert repository_service.idris_adapter.is_probable_idris_source is (
        repository_idris_primitives.is_probable_idris_source
    )
    assert repository_service.idris_adapter.parse_import_statements is (
        repository_idris_primitives.parse_import_statements
    )
    assert repository_service.idris_adapter.module_aliases_for_path is (
        repository_idris_analysis_support.module_aliases_for_path
    )
    assert repository_service.idris_adapter.resolve_import is (
        repository_idris_analysis_support.resolve_import
    )
    assert repository_service.idris_adapter.parse_dependencies_only is (
        repository_idris_analysis_support.parse_dependencies_only
    )
    assert repository_service.idris_adapter.parse_file is (
        repository_idris_analysis_support.parse_file
    )


def test_repository_intelligence_tlaplus_helpers_are_modularized() -> None:
    assert repository_service.tlaplus_adapter.strip_comments is (
        repository_tlaplus_primitives.strip_comments
    )
    assert repository_service.tlaplus_adapter.has_tlaplus_path_hints is (
        repository_tlaplus_primitives.has_tlaplus_path_hints
    )
    assert repository_service.tlaplus_adapter.is_probable_tlaplus_source is (
        repository_tlaplus_primitives.is_probable_tlaplus_source
    )
    assert repository_service.tlaplus_adapter.parse_extended_modules is (
        repository_tlaplus_primitives.parse_extended_modules
    )
    assert repository_service.tlaplus_adapter.parse_instance_statements is (
        repository_tlaplus_primitives.parse_instance_statements
    )
    assert repository_service.tlaplus_adapter.module_aliases_for_path is (
        repository_tlaplus_analysis_support.module_aliases_for_path
    )
    assert repository_service.tlaplus_adapter.resolve_module_source is (
        repository_tlaplus_analysis_support.resolve_module_source
    )
    assert repository_service.tlaplus_adapter.parse_dependencies_only is (
        repository_tlaplus_analysis_support.parse_dependencies_only
    )
    assert repository_service.tlaplus_adapter.parse_file is (
        repository_tlaplus_analysis_support.parse_file
    )


def test_repository_intelligence_logtalk_helpers_are_modularized() -> None:
    assert repository_service.logtalk_adapter.strip_comments is (
        repository_logtalk_primitives.strip_comments
    )
    assert repository_service.logtalk_adapter.has_logtalk_path_hints is (
        repository_logtalk_primitives.has_logtalk_path_hints
    )
    assert repository_service.logtalk_adapter.is_probable_logtalk_source is (
        repository_logtalk_primitives.is_probable_logtalk_source
    )
    assert repository_service.logtalk_adapter.parse_load_statements is (
        repository_logtalk_primitives.parse_load_statements
    )
    assert repository_service.logtalk_adapter.parse_uses_statements is (
        repository_logtalk_primitives.parse_uses_statements
    )
    assert repository_service.logtalk_adapter.module_aliases_for_path is (
        repository_logtalk_analysis_support.module_aliases_for_path
    )
    assert repository_service.logtalk_adapter.resolve_import is (
        repository_logtalk_analysis_support.resolve_import
    )
    assert repository_service.logtalk_adapter.parse_dependencies_only is (
        repository_logtalk_analysis_support.parse_dependencies_only
    )
    assert repository_service.logtalk_adapter.parse_file is (
        repository_logtalk_analysis_support.parse_file
    )


def test_repository_intelligence_chapel_helpers_are_modularized() -> None:
    assert repository_service.chapel_adapter.strip_comments is (
        repository_chapel_primitives.strip_comments
    )
    assert repository_service.chapel_adapter.has_chapel_path_hints is (
        repository_chapel_primitives.has_chapel_path_hints
    )
    assert repository_service.chapel_adapter.is_probable_chapel_source is (
        repository_chapel_primitives.is_probable_chapel_source
    )
    assert repository_service.chapel_adapter.parse_use_import_statements is (
        repository_chapel_primitives.parse_use_import_statements
    )
    assert repository_service.chapel_adapter.module_aliases_for_path is (
        repository_chapel_analysis_support.module_aliases_for_path
    )
    assert repository_service.chapel_adapter.resolve_import is (
        repository_chapel_analysis_support.resolve_import
    )
    assert repository_service.chapel_adapter.parse_dependencies_only is (
        repository_chapel_analysis_support.parse_dependencies_only
    )
    assert repository_service.chapel_adapter.parse_file is (
        repository_chapel_analysis_support.parse_file
    )


def test_puppet_adapter_parse_file_resolves_manifest_dependencies(tmp_path: Path) -> None:
    repo_path = tmp_path / "puppet-parse-repo"
    (repo_path / "manifests").mkdir(parents=True)
    (repo_path / "metadata.json").write_text(
        '{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        encoding="utf-8",
    )
    init_path = repo_path / "manifests" / "init.pp"
    init_path.write_text(
        "class apache {\n"
        "  include apache::params\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "manifests" / "params.pp").write_text(
        "class apache::params { }\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["manifests/init.pp", "manifests/params.pp"],
        root_path=repo_path,
    )
    text = init_path.read_text(encoding="utf-8")
    dependencies = repository_service.puppet_adapter.parse_dependencies_only(
        "manifests/init.pp",
        text,
        module_index,
        root_path=repo_path,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.puppet_adapter.parse_file(
        "manifests/init.pp",
        text,
        module_index,
        root_path=repo_path,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "manifests/params.pp"
        and dependency.target_symbol == "apache::params"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "apache" for symbol in symbols)
    assert any(
        reference.target_file == "manifests/params.pp"
        and "apache::params" in reference.target_names
        for reference in references
    )


def test_hack_adapter_parse_file_resolves_imported_type_dependencies(tmp_path: Path) -> None:
    repo_path = tmp_path / "hack-parse-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Ref.php").write_text(
        "<?hh\n"
        "namespace Demo;\n"
        "\n"
        "final class Ref<T> {}\n",
        encoding="utf-8",
    )
    user_path = repo_path / "src" / "User.hack"
    user_path.write_text(
        "<?hh\n"
        "namespace Demo;\n"
        "\n"
        "use type Demo\\Ref;\n"
        "\n"
        "final class User {\n"
        "  public function make(): Ref<int> {\n"
        "    return new Ref();\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/Ref.php", "src/User.hack"],
        root_path=repo_path,
    )
    text = user_path.read_text(encoding="utf-8")
    dependencies = repository_service.hack_adapter.parse_dependencies_only(
        "src/User.hack",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.hack_adapter.parse_file(
        "src/User.hack",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/Ref.php" and dependency.target_symbol == "Ref"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "User" for symbol in symbols)
    assert any(
        reference.target_file == "src/Ref.php" and "Ref" in reference.target_names
        for reference in references
    )


def test_odin_adapter_parse_file_resolves_import_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-parse-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    (repo_path / "src" / "common" / "helper.odin").write_text(
        "package common\n"
        "\n"
        "helper :: proc() -> int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )
    main_path = repo_path / "src" / "main.odin"
    main_path.write_text(
        "package main\n"
        "\n"
        'import "src:common"\n'
        "\n"
        "run :: proc() -> int {\n"
        "    return common.helper()\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/common/helper.odin", "src/main.odin"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.odin_adapter.parse_dependencies_only(
        "src/main.odin",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.odin_adapter.parse_file(
        "src/main.odin",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/common/helper.odin"
        and dependency.target_symbol == "common"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "src/common/helper.odin"
        and "helper" in reference.target_names
        for reference in references
    )


def test_factor_adapter_parse_file_resolves_using_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "factor-parse-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "math" / "math.factor").write_text(
        "IN: math\n\n: square ( n -- n ) dup * ;\n",
        encoding="utf-8",
    )
    main_path = repo_path / "app" / "main.factor"
    main_path.write_text(
        "USING: math ;\n"
        "IN: app.main\n\n"
        ": run ( n -- n ) square ;\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["app/main.factor", "math/math.factor"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.factor_adapter.parse_dependencies_only(
        "app/main.factor",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.factor_adapter.parse_file(
        "app/main.factor",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "math/math.factor"
        and dependency.target_symbol == "math"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "math/math.factor"
        and "square" in reference.target_names
        for reference in references
    )


def test_cue_adapter_parse_file_resolves_module_dependencies_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cue-parse-repo"
    (repo_path / "cue.mod").mkdir(parents=True)
    (repo_path / "pkg" / "schema").mkdir(parents=True)
    (repo_path / "cue.mod" / "module.cue").write_text(
        'module: "example.com/demo"\n',
        encoding="utf-8",
    )
    (repo_path / "pkg" / "schema" / "schema.cue").write_text(
        "package schema\n\n#Answer: 42\n",
        encoding="utf-8",
    )
    main_path = repo_path / "main.cue"
    main_path.write_text(
        'package main\n\nimport schema "example.com/demo/pkg/schema"\n\nvalue: schema.#Answer\n',
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["main.cue", "pkg/schema/schema.cue"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.cue_adapter.parse_dependencies_only(
        "main.cue",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
        root_path=repo_path,
    )
    symbols, _, references = repository_service.cue_adapter.parse_file(
        "main.cue",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
        root_path=repo_path,
    )

    assert any(
        dependency.target_file == "pkg/schema/schema.cue"
        and dependency.target_symbol == "example.com/demo/pkg/schema"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "value" for symbol in symbols)
    assert any(
        reference.target_file == "pkg/schema/schema.cue"
        and "#Answer" in reference.target_names
        for reference in references
    )


def test_eiffel_adapter_parse_file_resolves_inherited_class_dependencies(tmp_path: Path) -> None:
    repo_path = tmp_path / "eiffel-parse-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.e").write_text(
        "class HELPER\n"
        "feature\n"
        "    assist\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )
    application_path = repo_path / "src" / "application.e"
    application_path.write_text(
        "class APPLICATION\n"
        "inherit\n"
        "    HELPER\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        local\n"
        "            helper: HELPER\n"
        "        do\n"
        "            create {HELPER} helper\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/helper.e", "src/application.e"],
        root_path=repo_path,
    )
    text = application_path.read_text(encoding="utf-8")
    dependencies = repository_service.eiffel_adapter.parse_dependencies_only(
        "src/application.e",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.eiffel_adapter.parse_file(
        "src/application.e",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/helper.e" and dependency.target_symbol == "HELPER"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "APPLICATION" for symbol in symbols)
    assert any(
        reference.target_file == "src/helper.e" and "HELPER" in reference.target_names
        for reference in references
    )


def test_coq_adapter_parse_file_resolves_require_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coq-parse-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper : nat := 0.\n",
        encoding="utf-8",
    )
    main_path = repo_path / "theories" / "Main.v"
    main_path.write_text(
        "Require Import Helper.\n"
        "Lemma run : nat.\n"
        "Proof.\n"
        "  exact helper.\n"
        "Qed.\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["theories/Helper.v", "theories/Main.v"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.coq_adapter.parse_dependencies_only(
        "theories/Main.v",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.coq_adapter.parse_file(
        "theories/Main.v",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "theories/Helper.v" and dependency.target_symbol == "Helper"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "theories/Helper.v" and "helper" in reference.target_names
        for reference in references
    )


def test_lean_adapter_parse_file_resolves_import_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lean-parse-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    (repo_path / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 0\n",
        encoding="utf-8",
    )
    main_path = repo_path / "Batteries" / "Main.lean"
    main_path.write_text(
        "import Batteries.Helper\n\n"
        "def run : Nat := Batteries.Helper.helper\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["Batteries/Helper.lean", "Batteries/Main.lean"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.lean_adapter.parse_dependencies_only(
        "Batteries/Main.lean",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.lean_adapter.parse_file(
        "Batteries/Main.lean",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "Batteries/Helper.lean"
        and dependency.target_symbol == "Helper"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "Batteries/Helper.lean" and "helper" in reference.target_names
        for reference in references
    )


def test_glsl_adapter_parse_file_resolves_include_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "glsl-parse-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "lib" / "noise.glsl").write_text(
        "float noise() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    main_path = repo_path / "src" / "main.frag"
    main_path.write_text(
        '#version 300 es\n'
        '#include "./lib/noise.glsl"\n'
        "float render() {\n"
        "  return noise();\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/lib/noise.glsl", "src/main.frag"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.glsl_adapter.parse_dependencies_only(
        "src/main.frag",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.glsl_adapter.parse_file(
        "src/main.frag",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/lib/noise.glsl" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "render" for symbol in symbols)
    assert any(reference.target_names == ("noise",) for reference in references)


def test_hlsl_adapter_parse_file_resolves_include_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hlsl-parse-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "lib" / "noise.hlsli").write_text(
        "float NoiseValue() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    main_path = repo_path / "src" / "main.hlsl"
    main_path.write_text(
        '#include "./lib/noise.hlsli"\n'
        "float4 RenderMain() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/lib/noise.hlsli", "src/main.hlsl"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.hlsl_adapter.parse_dependencies_only(
        "src/main.hlsl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.hlsl_adapter.parse_file(
        "src/main.hlsl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/lib/noise.hlsli" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "RenderMain" for symbol in symbols)
    assert any(reference.target_names == ("NoiseValue",) for reference in references)


def test_parse_batchfile_dependencies_only_follows_calls_and_filters_local_labels(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "batchfile-parse-deps-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "scripts" / "build.bat").write_text(
        "@echo off\n"
        "call ..\\tools\\helper.cmd\n"
        "call :done\n"
        ":done\n"
        "exit /b 0\n",
        encoding="utf-8",
    )
    (repo_path / "tools" / "helper.cmd").write_text(
        "@echo off\n"
        "echo helper\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["scripts/build.bat", "tools/helper.cmd"],
        root_path=repo_path,
    )
    text = (repo_path / "scripts" / "build.bat").read_text(encoding="utf-8")

    dependencies = repository_batchfile_parser_dispatch._parse_batchfile_dependencies_only(
        "scripts/build.bat",
        text,
        module_index,
    )

    assert len(dependencies) == 1
    assert dependencies[0].target_file == "tools/helper.cmd"
    assert dependencies[0].target_symbol == "helper"


def test_parse_makefile_dependencies_only_follows_include_directives(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "makefile-parse-deps-repo"
    (repo_path / "mk").mkdir(parents=True)
    (repo_path / "Makefile").write_text(
        "include mk/common.mk\n"
        "build:\n"
        "\t@echo build\n",
        encoding="utf-8",
    )
    (repo_path / "mk" / "common.mk").write_text(
        "helper:\n"
        "\t@echo helper\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["Makefile", "mk/common.mk"],
        root_path=repo_path,
    )
    text = (repo_path / "Makefile").read_text(encoding="utf-8")

    dependencies = repository_makefile_parser_dispatch._parse_makefile_dependencies_only(
        "Makefile",
        text,
        module_index,
    )

    assert len(dependencies) == 1
    assert dependencies[0].target_file == "mk/common.mk"
    assert dependencies[0].target_symbol == "common"


def test_batchfile_adapter_parse_file_resolves_call_dependencies_and_label_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "batchfile-parse-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "scripts" / "build.bat").write_text(
        "@echo off\n"
        "call ..\\tools\\helper.cmd\n"
        "goto :done\n"
        ":done\n"
        "exit /b 0\n",
        encoding="utf-8",
    )
    (repo_path / "tools" / "helper.cmd").write_text(
        "@echo off\n"
        ":helper\n"
        "echo helper\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["scripts/build.bat", "tools/helper.cmd"],
        root_path=repo_path,
    )
    text = (repo_path / "scripts" / "build.bat").read_text(encoding="utf-8")
    dependencies = repository_service.batchfile_adapter.parse_dependencies_only(
        "scripts/build.bat",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.batchfile_adapter.parse_file(
        "scripts/build.bat",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "tools/helper.cmd" and dependency.target_symbol == "helper"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "scripts/build" for symbol in symbols)
    assert any(symbol.symbol_name == "done" for symbol in symbols)
    assert any(
        reference.target_file == "tools/helper.cmd" and reference.target_names == ("helper",)
        for reference in references
    )
    assert any(
        reference.target_file == "scripts/build.bat" and reference.target_names == ("done",)
        for reference in references
    )


def test_makefile_adapter_parse_file_resolves_includes_and_target_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "makefile-parse-repo"
    (repo_path / "mk").mkdir(parents=True)
    (repo_path / "Makefile").write_text(
        "include mk/common.mk\n"
        "build: clean\n"
        "\t$(MAKE) helper\n"
        "clean:\n"
        "\t@echo clean\n",
        encoding="utf-8",
    )
    (repo_path / "mk" / "common.mk").write_text(
        "helper:\n"
        "\t@echo helper\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["Makefile", "mk/common.mk"],
        root_path=repo_path,
    )
    text = (repo_path / "Makefile").read_text(encoding="utf-8")
    dependencies = repository_service.makefile_adapter.parse_dependencies_only(
        "Makefile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.makefile_adapter.parse_file(
        "Makefile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "mk/common.mk" and dependency.target_symbol == "common"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "build" for symbol in symbols)
    assert any(symbol.symbol_name == "clean" for symbol in symbols)
    assert any(
        reference.target_file == "Makefile" and reference.target_names == ("clean",)
        for reference in references
    )
    assert any(reference.target_names == ("helper",) for reference in references)


def test_cmake_adapter_parse_file_resolves_includes_subdirectories_and_target_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cmake-parse-repo"
    (repo_path / "cmake" / "modules").mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text(
        "project(acme)\n"
        "include(cmake/tooling.cmake)\n"
        "add_subdirectory(cmake/modules)\n"
        "find_package(Threads REQUIRED)\n"
        "add_library(acme_core INTERFACE)\n"
        "target_link_libraries(acme_core PRIVATE helper)\n"
        "add_dependencies(acme_core codegen)\n",
        encoding="utf-8",
    )
    (repo_path / "cmake" / "tooling.cmake").write_text(
        "add_library(helper INTERFACE)\n",
        encoding="utf-8",
    )
    (repo_path / "cmake" / "modules" / "CMakeLists.txt").write_text(
        "add_custom_target(codegen)\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "CMakeLists.txt",
            "cmake/tooling.cmake",
            "cmake/modules/CMakeLists.txt",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "CMakeLists.txt").read_text(encoding="utf-8")
    dependencies = repository_service.cmake_adapter.parse_dependencies_only(
        "CMakeLists.txt",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.cmake_adapter.parse_file(
        "CMakeLists.txt",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "cmake/tooling.cmake" and dependency.target_symbol == "tooling"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "cmake/modules/CMakeLists.txt"
        and dependency.target_symbol == "modules"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file is None and dependency.target_symbol == "Threads"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "acme" for symbol in symbols)
    assert any(symbol.symbol_name == "acme_core" for symbol in symbols)
    assert any(
        reference.target_file == "cmake/tooling.cmake" and reference.target_names == ("helper",)
        for reference in references
    )
    assert any(
        reference.target_file == "cmake/modules/CMakeLists.txt"
        and reference.target_names == ("codegen",)
        for reference in references
    )


def test_meson_adapter_parse_file_resolves_subdir_imports_and_target_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "meson-parse-repo"
    (repo_path / "subprojects").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('acme', 'c')\n"
        "subdir('src')\n"
        "python_mod = import('python')\n"
        "zlib_dep = dependency('zlib')\n"
        "library('acme_core', 'src/core.c')\n"
        "executable('acme_cli', 'src/main.c', link_with: helper_lib, dependencies: [zlib_dep, dependency('threads')])\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "meson.build").write_text(
        "helper_lib = static_library('helper_lib', 'helper.c')\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "meson.build",
            "src/meson.build",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "meson.build").read_text(encoding="utf-8")
    dependencies = repository_service.meson_adapter.parse_dependencies_only(
        "meson.build",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.meson_adapter.parse_file(
        "meson.build",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/meson.build" and dependency.target_symbol == "src"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file is None and dependency.target_symbol == "python"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file is None and dependency.target_symbol == "zlib"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "acme" for symbol in symbols)
    assert any(symbol.symbol_name == "acme_core" for symbol in symbols)
    assert any(symbol.symbol_name == "acme_cli" for symbol in symbols)
    assert any(
        reference.target_file == "src/meson.build" and reference.target_names == ("helper_lib",)
        for reference in references
    )
    assert any(reference.target_names == ("zlib_dep",) for reference in references)
    assert any(reference.target_names == ("threads",) for reference in references)


def test_just_adapter_parse_file_resolves_module_dependencies_and_target_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "just-parse-repo"
    (repo_path / "tasks").mkdir(parents=True)
    (repo_path / "Justfile").write_text(
        "mod release 'tasks/release.just'\n"
        "alias ci := check\n"
        "default: check\n"
        "check: release::publish\n"
        "  just build\n"
        "build:\n"
        "  echo build\n",
        encoding="utf-8",
    )
    (repo_path / "tasks" / "release.just").write_text(
        "publish:\n"
        "  echo publish\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "Justfile",
            "tasks/release.just",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "Justfile").read_text(encoding="utf-8")
    dependencies = repository_service.just_adapter.parse_dependencies_only(
        "Justfile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.just_adapter.parse_file(
        "Justfile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "tasks/release.just" and dependency.target_symbol == "release"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "ci" for symbol in symbols)
    assert any(symbol.symbol_name == "check" for symbol in symbols)
    assert any(symbol.symbol_name == "build" for symbol in symbols)
    assert any(
        reference.target_file == "tasks/release.just"
        and reference.target_names == ("release::publish", "publish")
        for reference in references
    )
    assert any(
        reference.target_file == "Justfile" and reference.target_names == ("build",)
        for reference in references
    )
    assert any(
        reference.target_file == "Justfile" and reference.target_names == ("check",)
        for reference in references
    )


def test_qmake_adapter_parse_file_resolves_include_subdir_dependencies_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qmake-parse-repo"
    (repo_path / "libs").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "project.pro").write_text(
        "TEMPLATE = subdirs\n"
        "TARGET = acme_workspace\n"
        "SUBDIRS += libs app\n"
        "libs.file = libs/libs.pro\n"
        "app.file = app/app.pro\n"
        "app.depends = libs\n"
        "include(common.pri)\n",
        encoding="utf-8",
    )
    (repo_path / "common.pri").write_text("CONFIG += ordered\n", encoding="utf-8")
    (repo_path / "libs" / "libs.pro").write_text(
        "TARGET = libs\nSOURCES += helper.cpp\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "app.pro").write_text(
        "TARGET = app\nSOURCES += main.cpp\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "project.pro",
            "common.pri",
            "libs/libs.pro",
            "app/app.pro",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "project.pro").read_text(encoding="utf-8")
    dependencies = repository_service.qmake_adapter.parse_dependencies_only(
        "project.pro",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.qmake_adapter.parse_file(
        "project.pro",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "common.pri" and dependency.target_symbol == "common"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "libs/libs.pro" and dependency.target_symbol == "libs"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "app/app.pro" and dependency.target_symbol == "app"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "acme_workspace" for symbol in symbols)
    assert any(symbol.symbol_name == "libs" for symbol in symbols)
    assert any(symbol.symbol_name == "app" for symbol in symbols)
    assert any(
        reference.target_file == "project.pro" and reference.target_names == ("libs",)
        for reference in references
    )


def test_qml_adapter_parse_file_resolves_imports_qmldir_exports_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qml-parse-repo"
    (repo_path / "components").mkdir(parents=True)
    (repo_path / "qmldir").write_text(
        "module Demo.Controls\n"
        "Button 1.0 components/Button.qml\n",
        encoding="utf-8",
    )
    (repo_path / "components" / "Button.qml").write_text(
        "Rectangle {\n"
        "    id: helperButton\n"
        "    function press() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Main.qml").write_text(
        'import "." as Demo\n'
        "Rectangle {\n"
        "    id: rootItem\n"
        "    function activate() {\n"
        "        helperButton.press()\n"
        "    }\n"
        "    Demo.Button {\n"
        "        id: helperButton\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "qmldir",
            "Main.qml",
            "components/Button.qml",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "Main.qml").read_text(encoding="utf-8")
    dependencies = repository_service.qml_adapter.parse_dependencies_only(
        "Main.qml",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.qml_adapter.parse_file(
        "Main.qml",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "qmldir" and dependency.target_symbol == "Demo"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "Main" for symbol in symbols)
    assert any(symbol.symbol_name == "rootItem" for symbol in symbols)
    assert any(symbol.symbol_name == "activate" for symbol in symbols)
    assert any(
        reference.target_file == "components/Button.qml"
        and reference.target_names == ("Demo.Button", "Button")
        for reference in references
    )
    assert any(
        reference.target_file == "Main.qml" and reference.target_names == ("helperButton",)
        for reference in references
    )


def test_cython_adapter_parse_file_resolves_imports_includes_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cython-parse-repo"
    (repo_path / "pkg").mkdir(parents=True)
    (repo_path / "pkg" / "defs.pxi").write_text(
        "DEF ANSWER = 42\n",
        encoding="utf-8",
    )
    (repo_path / "pkg" / "helpermod.pxd").write_text(
        "cdef int helper()\n",
        encoding="utf-8",
    )
    (repo_path / "pkg" / "main.pyx").write_text(
        'include "defs.pxi"\n'
        "from helpermod cimport helper\n"
        "\n"
        "cpdef int run():\n"
        "    return helper()\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["pkg/main.pyx", "pkg/helpermod.pxd", "pkg/defs.pxi"],
        root_path=repo_path,
    )
    text = (repo_path / "pkg" / "main.pyx").read_text(encoding="utf-8")

    dependencies = repository_service.cython_adapter.parse_dependencies_only(
        "pkg/main.pyx",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.cython_adapter.parse_file(
        "pkg/main.pyx",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "pkg/defs.pxi" for dependency in dependencies)
    assert any(
        dependency.target_file == "pkg/helpermod.pxd" and dependency.target_symbol == "helper"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "pkg/helpermod.pxd" and reference.target_names == ("helper",)
        for reference in references
    )


def test_cuda_adapter_parse_file_resolves_include_and_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "cuda-parse-repo"
    (repo_path / "src" / "kernels").mkdir(parents=True)
    (repo_path / "src" / "kernels" / "math.cuh").write_text(
        "__device__ inline int add_one(int x) {\n"
        "  return x + 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cu").write_text(
        '#include "kernels/math.cuh"\n'
        "__global__ void kernel_run(int* out) {\n"
        "  *out = add_one(*out);\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["src/main.cu", "src/kernels/math.cuh"],
        root_path=repo_path,
    )
    text = (repo_path / "src" / "main.cu").read_text(encoding="utf-8")

    dependencies = repository_service.cuda_adapter.parse_dependencies_only(
        "src/main.cu",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_include=repository_service._resolve_c_family_include,
    )
    symbols, _, references = repository_service.cuda_adapter.parse_file(
        "src/main.cu",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_include=repository_service._resolve_c_family_include,
    )

    assert any(dependency.target_file == "src/kernels/math.cuh" for dependency in dependencies)
    assert any(symbol.symbol_name == "kernel_run" for symbol in symbols)
    assert any(
        reference.target_file == "src/kernels/math.cuh" and reference.target_names == ("add_one",)
        for reference in references
    )


def test_stan_adapter_parse_file_resolves_include_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "stan-parse-repo"
    (repo_path / "models" / "lib").mkdir(parents=True)
    (repo_path / "models" / "lib" / "math.stan").write_text(
        "functions {\n"
        "  real add_one(real x) {\n"
        "    return x + 1;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "main.stan").write_text(
        '#include "lib/math.stan"\n'
        "\n"
        "functions {\n"
        "  real run(real x) {\n"
        "    return add_one(x);\n"
        "  }\n"
        "}\n"
        "\n"
        "data {\n"
        "  real x;\n"
        "}\n"
        "model {\n"
        "  target += run(x);\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["models/main.stan", "models/lib/math.stan"],
        root_path=repo_path,
    )
    text = (repo_path / "models" / "main.stan").read_text(encoding="utf-8")

    dependencies = repository_service.stan_adapter.parse_dependencies_only(
        "models/main.stan",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.stan_adapter.parse_file(
        "models/main.stan",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "models/lib/math.stan" for dependency in dependencies)
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "models/lib/math.stan" and reference.target_names == ("add_one",)
        for reference in references
    )


def test_robotframework_adapter_parse_file_resolves_resource_dependencies_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "robotframework-parse-repo"
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "resources").mkdir(parents=True)
    (repo_path / "resources" / "common.resource").write_text(
        "*** Keywords ***\n"
        "Open Login Page\n"
        "    Log    opened\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "login.robot").write_text(
        "*** Settings ***\n"
        "Resource    ../resources/common.resource\n"
        "\n"
        "*** Test Cases ***\n"
        "Valid Login\n"
        "    Open Login Page\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["tests/login.robot", "resources/common.resource"],
        root_path=repo_path,
    )
    text = (repo_path / "tests" / "login.robot").read_text(encoding="utf-8")

    dependencies = repository_service.robotframework_adapter.parse_dependencies_only(
        "tests/login.robot",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.robotframework_adapter.parse_file(
        "tests/login.robot",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "resources/common.resource"
        and dependency.target_symbol == "common"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "tests/login" for symbol in symbols)
    assert any(symbol.symbol_name == "Valid Login" for symbol in symbols)
    assert any(
        reference.target_file == "resources/common.resource"
        and "Open Login Page" in reference.target_names
        for reference in references
    )


def test_dockerfile_adapter_parse_file_resolves_local_copy_run_and_stage_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dockerfile-parse-repo"
    (repo_path / "docker").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "bootstrap.sh").write_text(
        "#!/usr/bin/env sh\n"
        "echo bootstrap\n",
        encoding="utf-8",
    )
    (repo_path / "docker" / "Dockerfile").write_text(
        "FROM python:3.12-slim AS base\n"
        "COPY ../scripts/bootstrap.sh /usr/local/bin/bootstrap.sh\n"
        "RUN sh ../scripts/bootstrap.sh\n"
        "FROM base AS runtime\n"
        "COPY --from=base /usr/local/bin/bootstrap.sh /usr/local/bin/bootstrap.sh\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["docker/Dockerfile", "scripts/bootstrap.sh"],
        root_path=repo_path,
    )
    text = (repo_path / "docker" / "Dockerfile").read_text(encoding="utf-8")

    dependencies = repository_service.dockerfile_adapter.parse_dependencies_only(
        "docker/Dockerfile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.dockerfile_adapter.parse_file(
        "docker/Dockerfile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "scripts/bootstrap.sh"
        and dependency.dependency_type in {"copies", "executes"}
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "docker/Dockerfile"
        and dependency.target_symbol == "base"
        and dependency.dependency_type in {"builds_from", "copies_from"}
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "docker/Dockerfile" for symbol in symbols)
    assert any(symbol.symbol_name == "base" for symbol in symbols)
    assert any(symbol.symbol_name == "runtime" for symbol in symbols)
    assert any(
        reference.target_file == "docker/Dockerfile" and reference.target_names == ("base",)
        for reference in references
    )


def test_scss_adapter_parse_file_resolves_imports_and_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "scss-parse-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "_mixins.scss").write_text(
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "_functions.scss").write_text(
        "@function helper-fn() {\n"
        "  @return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "main.scss").write_text(
        '@use "mixins" as mixins;\n'
        '@import "functions";\n'
        ".button {\n"
        "  @include mixins.button-base;\n"
        "  color: helper-fn();\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["styles/main.scss", "styles/_mixins.scss", "styles/_functions.scss"],
        root_path=repo_path,
    )
    text = (repo_path / "styles" / "main.scss").read_text(encoding="utf-8")

    dependencies = repository_service.scss_adapter.parse_dependencies_only(
        "styles/main.scss",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.scss_adapter.parse_file(
        "styles/main.scss",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "styles/_mixins.scss"
        and dependency.dependency_type == "uses"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "styles/_functions.scss"
        and dependency.dependency_type == "imports"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "styles/main" for symbol in symbols)
    assert any(symbol.symbol_name == "button-base" for symbol in symbols) is False
    assert any(
        reference.target_file == "styles/_mixins.scss"
        and "button-base" in reference.target_names
        for reference in references
    )
    assert any(
        reference.target_file == "styles/_functions.scss"
        and "helper-fn" in reference.target_names
        for reference in references
    )


def test_typst_adapter_parse_file_resolves_imports_includes_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "typst-parse-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "partials").mkdir(parents=True)
    (repo_path / "src" / "lib" / "math.typ").write_text(
        "#let add(x, y) = x + y\n"
        "#let scale(x) = x * 2\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "partials" / "common.typ").write_text(
        "#let common() = [hello]\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.typ").write_text(
        '#import "lib/math.typ": add\n'
        '#import "lib/math.typ" as math\n'
        '#include "partials/common.typ"\n'
        "#let render() = {\n"
        "  add(1, 2)\n"
        "  math.scale(3)\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["src/main.typ", "src/lib/math.typ", "src/partials/common.typ"],
        root_path=repo_path,
    )
    text = (repo_path / "src" / "main.typ").read_text(encoding="utf-8")

    dependencies = repository_service.typst_adapter.parse_dependencies_only(
        "src/main.typ",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.typst_adapter.parse_file(
        "src/main.typ",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/lib/math.typ"
        and dependency.dependency_type == "imports"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "src/partials/common.typ"
        and dependency.dependency_type == "includes"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "main" for symbol in symbols)
    assert any(symbol.symbol_name == "render" for symbol in symbols)
    assert any(
        reference.target_file == "src/lib/math.typ" and "add" in reference.target_names
        for reference in references
    )
    assert any(
        reference.target_file == "src/lib/math.typ" and "scale" in reference.target_names
        for reference in references
    )


def test_shaderlab_adapter_module_aliases_include_shader_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shaderlab-alias-repo"
    (repo_path / "Shaders").mkdir(parents=True)
    (repo_path / "Shaders" / "Main.shader").write_text(
        'Shader "Demo/Main" {\n'
        "SubShader {\n"
        "Pass {\n"
        "CGPROGRAM\n"
        "float4 frag() : SV_Target {\n"
        "  return float4(0.0, 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDCG\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.shaderlab_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Shaders/Main.shader",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Shaders/Main.shader" in aliases
    assert "Shaders/Main" in aliases
    assert "Main" in aliases
    assert "Demo/Main" in aliases
    assert "frag" in aliases


def test_shaderlab_adapter_parse_file_resolves_include_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shaderlab-parse-repo"
    (repo_path / "Shaders" / "Includes").mkdir(parents=True)
    (repo_path / "Shaders" / "Includes" / "Common.cginc").write_text(
        "float NoiseValue() {\n"
        "  return 0.25;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Shaders" / "Main.shader").write_text(
        'Shader "Demo/Main" {\n'
        "SubShader {\n"
        "Pass {\n"
        "HLSLPROGRAM\n"
        '#include "Includes/Common.cginc"\n'
        "float4 frag() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDHLSL\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["Shaders/Main.shader", "Shaders/Includes/Common.cginc"],
        root_path=repo_path,
    )
    text = (repo_path / "Shaders" / "Main.shader").read_text(encoding="utf-8")

    dependencies = repository_service.shaderlab_adapter.parse_dependencies_only(
        "Shaders/Main.shader",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.shaderlab_adapter.parse_file(
        "Shaders/Main.shader",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "Shaders/Includes/Common.cginc" for dependency in dependencies)
    assert any(symbol.symbol_name == "Demo/Main" for symbol in symbols)
    assert any(symbol.symbol_name == "frag" for symbol in symbols)
    assert any(
        reference.target_file == "Shaders/Includes/Common.cginc"
        and reference.target_names == ("NoiseValue",)
        for reference in references
    )


def test_bitbake_adapter_parse_file_resolves_include_and_inherit_dependencies(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bitbake-parse-repo"
    (repo_path / "conf").mkdir(parents=True)
    (repo_path / "classes").mkdir(parents=True)
    (repo_path / "recipes-core" / "base").mkdir(parents=True)
    (repo_path / "recipes-core" / "images").mkdir(parents=True)
    (repo_path / "conf" / "layer.conf").write_text(
        'BBPATH .= ":${LAYERDIR}"\n'
        'BBFILES += "${LAYERDIR}/recipes-*/*/*.bb"\n',
        encoding="utf-8",
    )
    (repo_path / "classes" / "image.bbclass").write_text(
        "python do_rootfs() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "recipes-core" / "base" / "base.inc").write_text(
        'BASE_NAME = "base"\n',
        encoding="utf-8",
    )
    (repo_path / "recipes-core" / "images" / "core-image-minimal.bb").write_text(
        "require ../base/base.inc\n"
        "inherit image\n"
        'BASE_NAME = "core"\n'
        "python do_install() {\n"
        "    bb.plain(\"${BASE_NAME}\")\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        (
            "conf/layer.conf",
            "classes/image.bbclass",
            "recipes-core/base/base.inc",
            "recipes-core/images/core-image-minimal.bb",
        ),
        root_path=repo_path,
    )
    text = (repo_path / "recipes-core" / "images" / "core-image-minimal.bb").read_text(
        encoding="utf-8"
    )
    dependencies = repository_service.bitbake_adapter.parse_dependencies_only(
        "recipes-core/images/core-image-minimal.bb",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.bitbake_adapter.parse_file(
        "recipes-core/images/core-image-minimal.bb",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "recipes-core/base/base.inc"
        and dependency.dependency_type == "require"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "classes/image.bbclass"
        and dependency.dependency_type == "inherit"
        for dependency in dependencies
    )
    base_symbol = next(symbol for symbol in symbols if symbol.symbol_name == "BASE_NAME")
    assert any(symbol.symbol_name == "do_install" for symbol in symbols)
    assert any(reference.target_symbol_id == base_symbol.symbol_id for reference in references)


def test_repository_intelligence_nushell_helpers_are_modularized() -> None:
    assert repository_service.nushell_adapter.strip_comments is (
        repository_nushell_primitives.strip_comments
    )
    assert repository_service.nushell_adapter.has_nushell_path_hints is (
        repository_nushell_primitives.has_nushell_path_hints
    )
    assert repository_service.nushell_adapter.is_probable_nushell_source is (
        repository_nushell_primitives.is_probable_nushell_source
    )
    assert repository_service.nushell_adapter.parse_use_targets is (
        repository_nushell_primitives.parse_use_targets
    )
    assert repository_service.nushell_adapter.module_aliases_for_path is (
        repository_nushell_analysis_support.module_aliases_for_path
    )
    assert repository_service.nushell_adapter.resolve_import is (
        repository_nushell_analysis_support.resolve_import
    )
    assert repository_service.nushell_adapter.parse_dependencies_only is (
        repository_nushell_analysis_support.parse_dependencies_only
    )
    assert repository_service.nushell_adapter.parse_file is (
        repository_nushell_analysis_support.parse_file
    )


def test_repository_intelligence_fish_helpers_are_modularized() -> None:
    assert repository_service.fish_adapter.strip_comments is (
        repository_fish_primitives.strip_comments
    )
    assert repository_service.fish_adapter.has_fish_path_hints is (
        repository_fish_primitives.has_fish_path_hints
    )
    assert repository_service.fish_adapter.is_probable_fish_source is (
        repository_fish_primitives.is_probable_fish_source
    )
    assert repository_service.fish_adapter.iter_symbol_entries is (
        repository_fish_primitives.iter_symbol_entries
    )
    assert repository_service.fish_adapter.iter_source_statements is (
        repository_fish_primitives.iter_source_statements
    )
    assert repository_service.fish_adapter.iter_reference_names is (
        repository_fish_primitives.iter_reference_names
    )
    assert repository_service.fish_adapter.module_aliases_for_path is (
        repository_fish_analysis_support.module_aliases_for_path
    )
    assert repository_service.fish_adapter.resolve_import is (
        repository_fish_analysis_support.resolve_import
    )
    assert repository_service.fish_adapter.parse_dependencies_only is (
        repository_fish_analysis_support.parse_dependencies_only
    )
    assert repository_service.fish_adapter.parse_file is (
        repository_fish_analysis_support.parse_file
    )


def test_repository_intelligence_batchfile_helpers_are_modularized() -> None:
    assert repository_service.batchfile_adapter.strip_comments is (
        repository_batchfile_primitives.strip_comments
    )
    assert repository_service.batchfile_adapter.has_batchfile_path_hints is (
        repository_batchfile_primitives.has_batchfile_path_hints
    )
    assert repository_service.batchfile_adapter.is_probable_batchfile_source is (
        repository_batchfile_primitives.is_probable_batchfile_source
    )
    assert repository_service.batchfile_adapter.iter_symbol_entries is (
        repository_batchfile_primitives.iter_symbol_entries
    )
    assert repository_service.batchfile_adapter.iter_script_calls is (
        repository_batchfile_primitives.iter_script_calls
    )
    assert repository_service.batchfile_adapter.iter_reference_names is (
        repository_batchfile_primitives.iter_reference_names
    )
    assert repository_service.batchfile_adapter.module_aliases_for_path is (
        repository_batchfile_analysis_support.module_aliases_for_path
    )
    assert repository_service.batchfile_adapter.resolve_import is (
        repository_batchfile_analysis_support.resolve_import
    )
    assert repository_service.batchfile_adapter.parse_dependencies_only is (
        repository_batchfile_analysis_support.parse_dependencies_only
    )
    assert repository_service.batchfile_adapter.parse_file is (
        repository_batchfile_analysis_support.parse_file
    )


def test_repository_intelligence_odin_helpers_are_modularized() -> None:
    assert repository_service.odin_adapter.strip_comments is (
        repository_odin_primitives.strip_comments
    )
    assert repository_service.odin_adapter.has_odin_path_hints is (
        repository_odin_primitives.has_odin_path_hints
    )
    assert repository_service.odin_adapter.is_probable_odin_source is (
        repository_odin_analysis_support.is_probable_odin_source
    )
    assert repository_service.odin_adapter.parse_import_statements is (
        repository_odin_primitives.parse_import_statements
    )
    assert repository_service.odin_adapter.parse_ols_checker_paths is (
        repository_odin_analysis_support.parse_ols_checker_paths
    )
    assert repository_service.odin_adapter.parse_ols_collections is (
        repository_odin_analysis_support.parse_ols_collections
    )
    assert repository_service.odin_adapter.module_aliases_for_path is (
        repository_odin_analysis_support.module_aliases_for_path
    )
    assert repository_service.odin_adapter.resolve_import is (
        repository_odin_analysis_support.resolve_import
    )
    assert repository_service.odin_adapter.parse_dependencies_only is (
        repository_odin_analysis_support.parse_dependencies_only
    )
    assert repository_service.odin_adapter.parse_file is (
        repository_odin_analysis_support.parse_file
    )


def test_repository_intelligence_factor_helpers_are_modularized() -> None:
    assert repository_service.factor_adapter.strip_comments is (
        repository_factor_primitives.strip_comments
    )
    assert repository_service.factor_adapter.has_factor_path_hints is (
        repository_factor_primitives.has_factor_path_hints
    )
    assert repository_service.factor_adapter.is_probable_factor_source is (
        repository_factor_analysis_support.is_probable_factor_source
    )
    assert repository_service.factor_adapter.parse_import_statements is (
        repository_factor_primitives.parse_import_statements
    )
    assert repository_service.factor_adapter.parse_reference_targets is (
        repository_factor_primitives.parse_reference_targets
    )
    assert repository_service.factor_adapter.vocabulary_name_from_text is (
        repository_factor_primitives.vocabulary_name_from_text
    )
    assert repository_service.factor_adapter.module_aliases_for_path is (
        repository_factor_analysis_support.module_aliases_for_path
    )
    assert repository_service.factor_adapter.resolve_import is (
        repository_factor_analysis_support.resolve_import
    )
    assert repository_service.factor_adapter.parse_dependencies_only is (
        repository_factor_analysis_support.parse_dependencies_only
    )
    assert repository_service.factor_adapter.parse_file is (
        repository_factor_analysis_support.parse_file
    )


def test_repository_intelligence_cue_helpers_are_modularized() -> None:
    assert repository_service.cue_adapter.strip_comments is (
        repository_cue_primitives.strip_comments
    )
    assert repository_service.cue_adapter.has_cue_path_hints is (
        repository_cue_primitives.has_cue_path_hints
    )
    assert repository_service.cue_adapter.is_probable_cue_source is (
        repository_cue_analysis_support.is_probable_cue_source
    )
    assert repository_service.cue_adapter.parse_import_statements is (
        repository_cue_primitives.parse_import_statements
    )
    assert repository_service.cue_adapter.parse_reference_targets is (
        repository_cue_primitives.parse_reference_targets
    )
    assert repository_service.cue_adapter.package_name_from_text is (
        repository_cue_analysis_support.package_name_from_text
    )
    assert repository_service.cue_adapter.module_aliases_for_path is (
        repository_cue_analysis_support.module_aliases_for_path
    )
    assert repository_service.cue_adapter.resolve_import is (
        repository_cue_analysis_support.resolve_import
    )
    assert repository_service.cue_adapter.parse_dependencies_only is (
        repository_cue_analysis_support.parse_dependencies_only
    )
    assert repository_service.cue_adapter.parse_file is (
        repository_cue_analysis_support.parse_file
    )


def test_repository_intelligence_makefile_helpers_are_modularized() -> None:
    assert repository_service.makefile_adapter.strip_comments is (
        repository_makefile_primitives.strip_comments
    )
    assert repository_service.makefile_adapter.has_makefile_path_hints is (
        repository_makefile_primitives.has_makefile_path_hints
    )
    assert repository_service.makefile_adapter.is_probable_makefile_source is (
        repository_makefile_primitives.is_probable_makefile_source
    )
    assert repository_service.makefile_adapter.iter_include_targets is (
        repository_makefile_primitives.iter_include_targets
    )
    assert repository_service.makefile_adapter.iter_symbol_entries is (
        repository_makefile_primitives.iter_symbol_entries
    )
    assert repository_service.makefile_adapter.iter_reference_names is (
        repository_makefile_primitives.iter_reference_names
    )
    assert repository_service.makefile_adapter.module_aliases_for_path is (
        repository_makefile_analysis_support.module_aliases_for_path
    )
    assert repository_service.makefile_adapter.resolve_import is (
        repository_makefile_analysis_support.resolve_import
    )
    assert repository_service.makefile_adapter.parse_dependencies_only is (
        repository_makefile_analysis_support.parse_dependencies_only
    )
    assert repository_service.makefile_adapter.parse_file is (
        repository_makefile_analysis_support.parse_file
    )


def test_repository_intelligence_cmake_helpers_are_modularized() -> None:
    assert repository_service.cmake_adapter.strip_comments is (
        repository_cmake_primitives.strip_comments
    )
    assert repository_service.cmake_adapter.has_cmake_path_hints is (
        repository_cmake_primitives.has_cmake_path_hints
    )
    assert repository_service.cmake_adapter.is_probable_cmake_source is (
        repository_cmake_primitives.is_probable_cmake_source
    )
    assert repository_service.cmake_adapter.iter_command_entries is (
        repository_cmake_primitives.iter_command_entries
    )
    assert repository_service.cmake_adapter.iter_include_targets is (
        repository_cmake_primitives.iter_include_targets
    )
    assert repository_service.cmake_adapter.iter_subdirectory_targets is (
        repository_cmake_primitives.iter_subdirectory_targets
    )
    assert repository_service.cmake_adapter.iter_package_targets is (
        repository_cmake_primitives.iter_package_targets
    )
    assert repository_service.cmake_adapter.iter_symbol_entries is (
        repository_cmake_primitives.iter_symbol_entries
    )
    assert repository_service.cmake_adapter.iter_reference_names is (
        repository_cmake_primitives.iter_reference_names
    )
    assert repository_service.cmake_adapter.module_aliases_for_path is (
        repository_cmake_analysis_support.module_aliases_for_path
    )
    assert repository_service.cmake_adapter.resolve_import is (
        repository_cmake_analysis_support.resolve_import
    )
    assert repository_service.cmake_adapter.parse_dependencies_only is (
        repository_cmake_analysis_support.parse_dependencies_only
    )
    assert repository_service.cmake_adapter.parse_file is (
        repository_cmake_analysis_support.parse_file
    )


def test_repository_intelligence_meson_helpers_are_modularized() -> None:
    assert repository_service.meson_adapter.strip_comments is (
        repository_meson_primitives.strip_comments
    )
    assert repository_service.meson_adapter.has_meson_path_hints is (
        repository_meson_primitives.has_meson_path_hints
    )
    assert repository_service.meson_adapter.is_probable_meson_source is (
        repository_meson_primitives.is_probable_meson_source
    )
    assert repository_service.meson_adapter.iter_call_entries is (
        repository_meson_primitives.iter_call_entries
    )
    assert repository_service.meson_adapter.iter_subdir_targets is (
        repository_meson_primitives.iter_subdir_targets
    )
    assert repository_service.meson_adapter.iter_import_targets is (
        repository_meson_primitives.iter_import_targets
    )
    assert repository_service.meson_adapter.iter_dependency_targets is (
        repository_meson_primitives.iter_dependency_targets
    )
    assert repository_service.meson_adapter.iter_symbol_entries is (
        repository_meson_primitives.iter_symbol_entries
    )
    assert repository_service.meson_adapter.iter_reference_names is (
        repository_meson_primitives.iter_reference_names
    )
    assert repository_service.meson_adapter.module_aliases_for_path is (
        repository_meson_analysis_support.module_aliases_for_path
    )
    assert repository_service.meson_adapter.resolve_import is (
        repository_meson_analysis_support.resolve_import
    )
    assert repository_service.meson_adapter.parse_dependencies_only is (
        repository_meson_analysis_support.parse_dependencies_only
    )
    assert repository_service.meson_adapter.parse_file is (
        repository_meson_analysis_support.parse_file
    )


def test_repository_intelligence_just_helpers_are_modularized() -> None:
    assert repository_service.just_adapter.strip_comments is (
        repository_just_primitives.strip_comments
    )
    assert repository_service.just_adapter.has_just_path_hints is (
        repository_just_primitives.has_just_path_hints
    )
    assert repository_service.just_adapter.is_probable_just_source is (
        repository_just_primitives.is_probable_just_source
    )
    assert repository_service.just_adapter.iter_alias_entries is (
        repository_just_primitives.iter_alias_entries
    )
    assert repository_service.just_adapter.iter_import_targets is (
        repository_just_primitives.iter_import_targets
    )
    assert repository_service.just_adapter.iter_mod_targets is (
        repository_just_primitives.iter_mod_targets
    )
    assert repository_service.just_adapter.iter_recipe_entries is (
        repository_just_primitives.iter_recipe_entries
    )
    assert repository_service.just_adapter.iter_symbol_entries is (
        repository_just_primitives.iter_symbol_entries
    )
    assert repository_service.just_adapter.iter_reference_names is (
        repository_just_primitives.iter_reference_names
    )
    assert repository_service.just_adapter.module_aliases_for_path is (
        repository_just_analysis_support.module_aliases_for_path
    )
    assert repository_service.just_adapter.resolve_import is (
        repository_just_analysis_support.resolve_import
    )
    assert repository_service.just_adapter.parse_dependencies_only is (
        repository_just_analysis_support.parse_dependencies_only
    )
    assert repository_service.just_adapter.parse_file is (
        repository_just_analysis_support.parse_file
    )


def test_repository_intelligence_qmake_helpers_are_modularized() -> None:
    assert repository_service.qmake_adapter.strip_comments is (
        repository_qmake_primitives.strip_comments
    )
    assert repository_service.qmake_adapter.normalize_continuations is (
        repository_qmake_primitives.normalize_continuations
    )
    assert repository_service.qmake_adapter.has_qmake_path_hints is (
        repository_qmake_primitives.has_qmake_path_hints
    )
    assert repository_service.qmake_adapter.is_probable_qmake_source is (
        repository_qmake_primitives.is_probable_qmake_source
    )
    assert repository_service.qmake_adapter.iter_assignment_entries is (
        repository_qmake_primitives.iter_assignment_entries
    )
    assert repository_service.qmake_adapter.iter_include_targets is (
        repository_qmake_primitives.iter_include_targets
    )
    assert repository_service.qmake_adapter.iter_load_targets is (
        repository_qmake_primitives.iter_load_targets
    )
    assert repository_service.qmake_adapter.iter_subdir_entries is (
        repository_qmake_primitives.iter_subdir_entries
    )
    assert repository_service.qmake_adapter.iter_symbol_entries is (
        repository_qmake_primitives.iter_symbol_entries
    )
    assert repository_service.qmake_adapter.iter_reference_names is (
        repository_qmake_primitives.iter_reference_names
    )
    assert repository_service.qmake_adapter.module_aliases_for_path is (
        repository_qmake_analysis_support.module_aliases_for_path
    )
    assert repository_service.qmake_adapter.resolve_import is (
        repository_qmake_analysis_support.resolve_import
    )
    assert repository_service.qmake_adapter.parse_dependencies_only is (
        repository_qmake_analysis_support.parse_dependencies_only
    )
    assert repository_service.qmake_adapter.parse_file is (
        repository_qmake_analysis_support.parse_file
    )


def test_repository_intelligence_qml_helpers_are_modularized() -> None:
    assert repository_service.qml_adapter.strip_comments is repository_qml_primitives.strip_comments
    assert repository_service.qml_adapter.has_qml_path_hints is (
        repository_qml_primitives.has_qml_path_hints
    )
    assert repository_service.qml_adapter.is_probable_qml_source is (
        repository_qml_primitives.is_probable_qml_source
    )
    assert repository_service.qml_adapter.iter_import_entries is (
        repository_qml_primitives.iter_import_entries
    )
    assert repository_service.qml_adapter.iter_qmldir_exports is (
        repository_qml_primitives.iter_qmldir_exports
    )
    assert repository_service.qml_adapter.iter_qmldir_module_names is (
        repository_qml_primitives.iter_qmldir_module_names
    )
    assert repository_service.qml_adapter.iter_symbol_entries is (
        repository_qml_primitives.iter_symbol_entries
    )
    assert repository_service.qml_adapter.iter_reference_names is (
        repository_qml_primitives.iter_reference_names
    )
    assert repository_service.qml_adapter.module_name_from_path is (
        repository_qml_primitives.module_name_from_path
    )
    assert repository_service.qml_adapter.module_aliases_for_path is (
        repository_qml_analysis_support.module_aliases_for_path
    )
    assert repository_service.qml_adapter.resolve_import is (
        repository_qml_analysis_support.resolve_import
    )
    assert repository_service.qml_adapter.parse_dependencies_only is (
        repository_qml_analysis_support.parse_dependencies_only
    )
    assert repository_service.qml_adapter.parse_file is repository_qml_analysis_support.parse_file


def test_repository_intelligence_bitbake_helpers_are_modularized() -> None:
    assert repository_service.bitbake_adapter.strip_comments is (
        repository_bitbake_primitives.strip_comments
    )
    assert repository_service.bitbake_adapter.has_bitbake_path_hints is (
        repository_bitbake_primitives.has_bitbake_path_hints
    )
    assert repository_service.bitbake_adapter.is_probable_bitbake_source is (
        repository_bitbake_primitives.is_probable_bitbake_source
    )
    assert repository_service.bitbake_adapter.iter_include_targets is (
        repository_bitbake_primitives.iter_include_targets
    )
    assert repository_service.bitbake_adapter.iter_inherit_targets is (
        repository_bitbake_primitives.iter_inherit_targets
    )
    assert repository_service.bitbake_adapter.iter_symbol_entries is (
        repository_bitbake_primitives.iter_symbol_entries
    )
    assert repository_service.bitbake_adapter.iter_reference_names is (
        repository_bitbake_primitives.iter_reference_names
    )
    assert repository_service.bitbake_adapter.module_aliases_for_path is (
        repository_bitbake_analysis_support.module_aliases_for_path
    )
    assert repository_service.bitbake_adapter.resolve_include_target is (
        repository_bitbake_analysis_support.resolve_include_target
    )
    assert repository_service.bitbake_adapter.resolve_inherit_target is (
        repository_bitbake_analysis_support.resolve_inherit_target
    )
    assert repository_service.bitbake_adapter.parse_dependencies_only is (
        repository_bitbake_analysis_support.parse_dependencies_only
    )
    assert repository_service.bitbake_adapter.parse_file is (
        repository_bitbake_analysis_support.parse_file
    )


def test_repository_intelligence_haxe_helpers_are_modularized() -> None:
    assert repository_service.haxe_adapter.strip_comments is (
        repository_haxe_primitives.strip_comments
    )
    assert repository_service.haxe_adapter.has_haxe_path_hints is (
        repository_haxe_primitives.has_haxe_path_hints
    )
    assert repository_service.haxe_adapter.is_probable_haxe_source is (
        repository_haxe_primitives.is_probable_haxe_source
    )
    assert repository_service.haxe_adapter.import_statements is (
        repository_haxe_primitives.import_statements
    )
    assert repository_service.haxe_adapter.module_aliases_for_path is (
        repository_haxe_analysis_support.module_aliases_for_path
    )
    assert repository_service.haxe_adapter.resolve_import is (
        repository_haxe_analysis_support.resolve_import
    )
    assert repository_service.haxe_adapter.parse_dependencies_only is (
        repository_haxe_analysis_support.parse_dependencies_only
    )
    assert repository_service.haxe_adapter.parse_file is (
        repository_haxe_analysis_support.parse_file
    )


def test_repository_intelligence_hack_helpers_are_modularized() -> None:
    assert repository_service.hack_adapter.strip_comments is (
        repository_hack_primitives.strip_comments
    )
    assert repository_service.hack_adapter.has_hack_path_hints is (
        repository_hack_primitives.has_hack_path_hints
    )
    assert repository_service.hack_adapter.parse_hack_autoload_roots is (
        repository_hack_primitives.parse_hack_autoload_roots
    )
    assert repository_service.hack_adapter.is_probable_hack_source is (
        repository_hack_analysis_support.is_probable_hack_source
    )
    assert repository_service.hack_adapter.module_aliases_for_path is (
        repository_hack_analysis_support.module_aliases_for_path
    )
    assert repository_service.hack_adapter.resolve_import is (
        repository_hack_analysis_support.resolve_import
    )
    assert repository_service.hack_adapter.parse_dependencies_only is (
        repository_hack_analysis_support.parse_dependencies_only
    )
    assert repository_service.hack_adapter.parse_file is (
        repository_hack_analysis_support.parse_file
    )


def test_repository_intelligence_autohotkey_helpers_are_modularized() -> None:
    assert repository_service.autohotkey_adapter.strip_comments is (
        repository_autohotkey_primitives.strip_comments
    )
    assert repository_service.autohotkey_adapter.has_autohotkey_path_hints is (
        repository_autohotkey_primitives.has_autohotkey_path_hints
    )
    assert repository_service.autohotkey_adapter.is_probable_autohotkey_source is (
        repository_autohotkey_primitives.is_probable_autohotkey_source
    )
    assert repository_service.autohotkey_adapter.import_statements is (
        repository_autohotkey_primitives.import_statements
    )
    assert repository_service.autohotkey_adapter.module_aliases_for_path is (
        repository_autohotkey_analysis_support.module_aliases_for_path
    )
    assert repository_service.autohotkey_adapter.resolve_include is (
        repository_autohotkey_analysis_support.resolve_include
    )
    assert repository_service.autohotkey_adapter.parse_dependencies_only is (
        repository_autohotkey_analysis_support.parse_dependencies_only
    )
    assert repository_service.autohotkey_adapter.parse_file is (
        repository_autohotkey_analysis_support.parse_file
    )


def test_repository_intelligence_autoit_helpers_are_modularized() -> None:
    assert repository_service.autoit_adapter.strip_comments is (
        repository_autoit_primitives.strip_comments
    )
    assert repository_service.autoit_adapter.has_autoit_path_hints is (
        repository_autoit_primitives.has_autoit_path_hints
    )
    assert repository_service.autoit_adapter.is_probable_autoit_source is (
        repository_autoit_primitives.is_probable_autoit_source
    )
    assert repository_service.autoit_adapter.import_statements is (
        repository_autoit_primitives.import_statements
    )
    assert repository_service.autoit_adapter.module_aliases_for_path is (
        repository_autoit_analysis_support.module_aliases_for_path
    )
    assert repository_service.autoit_adapter.resolve_include is (
        repository_autoit_analysis_support.resolve_include
    )
    assert repository_service.autoit_adapter.parse_dependencies_only is (
        repository_autoit_analysis_support.parse_dependencies_only
    )
    assert repository_service.autoit_adapter.parse_file is (
        repository_autoit_analysis_support.parse_file
    )


def test_repository_intelligence_squirrel_helpers_are_modularized() -> None:
    assert repository_service.squirrel_adapter.strip_comments is (
        repository_squirrel_primitives.strip_comments
    )
    assert repository_service.squirrel_adapter.has_squirrel_path_hints is (
        repository_squirrel_primitives.has_squirrel_path_hints
    )
    assert repository_service.squirrel_adapter.is_probable_squirrel_source is (
        repository_squirrel_primitives.is_probable_squirrel_source
    )
    assert repository_service.squirrel_adapter.import_statements is (
        repository_squirrel_primitives.import_statements
    )
    assert repository_service.squirrel_adapter.module_name_from_path is (
        repository_squirrel_primitives.module_name_from_path
    )
    assert repository_service.squirrel_adapter.module_aliases_for_path is (
        repository_squirrel_analysis_support.module_aliases_for_path
    )
    assert repository_service.squirrel_adapter.resolve_include is (
        repository_squirrel_analysis_support.resolve_include
    )
    assert repository_service.squirrel_adapter.parse_dependencies_only is (
        repository_squirrel_analysis_support.parse_dependencies_only
    )
    assert repository_service.squirrel_adapter.parse_file is (
        repository_squirrel_analysis_support.parse_file
    )


def test_repository_intelligence_cython_helpers_are_modularized() -> None:
    assert repository_service.cython_adapter.strip_comments is (
        repository_cython_primitives.strip_comments
    )
    assert repository_service.cython_adapter.has_cython_path_hints is (
        repository_cython_primitives.has_cython_path_hints
    )
    assert repository_service.cython_adapter.is_probable_cython_source is (
        repository_cython_primitives.is_probable_cython_source
    )
    assert repository_service.cython_adapter.include_statements is (
        repository_cython_primitives.include_statements
    )
    assert repository_service.cython_adapter.import_statements is (
        repository_cython_primitives.import_statements
    )
    assert repository_service.cython_adapter.iter_symbol_entries is (
        repository_cython_primitives.iter_symbol_entries
    )
    assert repository_service.cython_adapter.module_name_from_path is (
        repository_cython_primitives.module_name_from_path
    )
    assert repository_service.cython_adapter.module_aliases_for_path is (
        repository_cython_analysis_support.module_aliases_for_path
    )
    assert repository_service.cython_adapter.resolve_import is (
        repository_cython_analysis_support.resolve_import
    )
    assert repository_service.cython_adapter.resolve_include is (
        repository_cython_analysis_support.resolve_include
    )
    assert repository_service.cython_adapter.parse_dependencies_only is (
        repository_cython_analysis_support.parse_dependencies_only
    )
    assert repository_service.cython_adapter.parse_file is (
        repository_cython_analysis_support.parse_file
    )


def test_repository_intelligence_cuda_helpers_are_modularized() -> None:
    assert repository_service.cuda_adapter.strip_comments is (
        repository_cuda_primitives.strip_comments
    )
    assert repository_service.cuda_adapter.has_cuda_path_hints is (
        repository_cuda_primitives.has_cuda_path_hints
    )
    assert repository_service.cuda_adapter.is_probable_cuda_source is (
        repository_cuda_primitives.is_probable_cuda_source
    )
    assert repository_service.cuda_adapter.candidate_module_keys is (
        repository_cuda_primitives.candidate_module_keys
    )
    assert repository_service.cuda_adapter.module_name_from_path is (
        repository_cuda_primitives.module_name_from_path
    )
    assert repository_service.cuda_adapter.module_aliases_for_path is (
        repository_cuda_analysis_support.module_aliases_for_path
    )
    assert repository_service.cuda_adapter.resolve_include is (
        repository_cuda_analysis_support.resolve_include
    )
    assert repository_service.cuda_adapter.parse_dependencies_only is (
        repository_cuda_analysis_support.parse_dependencies_only
    )
    assert repository_service.cuda_adapter.parse_file is (
        repository_cuda_analysis_support.parse_file
    )


def test_repository_intelligence_stan_helpers_are_modularized() -> None:
    assert repository_service.stan_adapter.strip_comments is (
        repository_stan_primitives.strip_comments
    )
    assert repository_service.stan_adapter.has_stan_path_hints is (
        repository_stan_primitives.has_stan_path_hints
    )
    assert repository_service.stan_adapter.is_probable_stan_source is (
        repository_stan_primitives.is_probable_stan_source
    )
    assert repository_service.stan_adapter.include_statements is (
        repository_stan_primitives.include_statements
    )
    assert repository_service.stan_adapter.iter_symbol_entries is (
        repository_stan_primitives.iter_symbol_entries
    )
    assert repository_service.stan_adapter.module_name_from_path is (
        repository_stan_primitives.module_name_from_path
    )
    assert repository_service.stan_adapter.module_aliases_for_path is (
        repository_stan_analysis_support.module_aliases_for_path
    )
    assert repository_service.stan_adapter.resolve_include is (
        repository_stan_analysis_support.resolve_include
    )
    assert repository_service.stan_adapter.parse_dependencies_only is (
        repository_stan_analysis_support.parse_dependencies_only
    )
    assert repository_service.stan_adapter.parse_file is (
        repository_stan_analysis_support.parse_file
    )


def test_repository_intelligence_typst_helpers_are_modularized() -> None:
    assert repository_service.typst_adapter.strip_comments is (
        repository_typst_primitives.strip_comments
    )
    assert repository_service.typst_adapter.has_typst_path_hints is (
        repository_typst_primitives.has_typst_path_hints
    )
    assert repository_service.typst_adapter.is_probable_typst_source is (
        repository_typst_primitives.is_probable_typst_source
    )
    assert repository_service.typst_adapter.is_probable_typst_config is (
        repository_typst_primitives.is_probable_typst_config
    )
    assert repository_service.typst_adapter.include_statements is (
        repository_typst_primitives.include_statements
    )
    assert repository_service.typst_adapter.iter_import_entries is (
        repository_typst_primitives.iter_import_entries
    )
    assert repository_service.typst_adapter.iter_symbol_entries is (
        repository_typst_primitives.iter_symbol_entries
    )
    assert repository_service.typst_adapter.iter_reference_entries is (
        repository_typst_primitives.iter_reference_entries
    )
    assert repository_service.typst_adapter.module_aliases_for_path is (
        repository_typst_analysis_support.module_aliases_for_path
    )
    assert repository_service.typst_adapter.resolve_import is (
        repository_typst_analysis_support.resolve_import
    )
    assert repository_service.typst_adapter.parse_dependencies_only is (
        repository_typst_analysis_support.parse_dependencies_only
    )
    assert repository_service.typst_adapter.parse_file is (
        repository_typst_analysis_support.parse_file
    )


def test_repository_intelligence_starlark_helpers_are_modularized() -> None:
    assert repository_service.starlark_adapter.strip_comments is (
        repository_starlark_primitives.strip_comments
    )
    assert repository_service.starlark_adapter.has_starlark_path_hints is (
        repository_starlark_primitives.has_starlark_path_hints
    )
    assert repository_service.starlark_adapter.is_probable_starlark_source is (
        repository_starlark_primitives.is_probable_starlark_source
    )
    assert repository_service.starlark_adapter.iter_load_statements is (
        repository_starlark_primitives.iter_load_statements
    )
    assert repository_service.starlark_adapter.parse_loaded_symbols is (
        repository_starlark_primitives.parse_loaded_symbols
    )
    assert repository_service.starlark_adapter.module_aliases_for_path is (
        repository_starlark_analysis_support.module_aliases_for_path
    )
    assert repository_service.starlark_adapter.resolve_load_target is (
        repository_starlark_analysis_support.resolve_load_target
    )
    assert repository_service.starlark_adapter.parse_dependencies_only is (
        repository_starlark_analysis_support.parse_dependencies_only
    )
    assert repository_service.starlark_adapter.parse_file is (
        repository_starlark_analysis_support.parse_file
    )


def test_repository_intelligence_nix_helpers_are_modularized() -> None:
    assert repository_service.nix_adapter.strip_comments is (
        repository_nix_primitives.strip_comments
    )
    assert repository_service.nix_adapter.has_nix_path_hints is (
        repository_nix_primitives.has_nix_path_hints
    )
    assert repository_service.nix_adapter.is_probable_nix_source is (
        repository_nix_primitives.is_probable_nix_source
    )
    assert repository_service.nix_adapter.import_targets_for_text is (
        repository_nix_primitives.import_targets_for_text
    )
    assert repository_service.nix_adapter.module_aliases_for_path is (
        repository_nix_analysis_support.module_aliases_for_path
    )
    assert repository_service.nix_adapter.resolve_import is (
        repository_nix_analysis_support.resolve_import
    )
    assert repository_service.nix_adapter.parse_dependencies_only is (
        repository_nix_analysis_support.parse_dependencies_only
    )
    assert repository_service.nix_adapter.parse_file is (
        repository_nix_analysis_support.parse_file
    )


def test_repository_intelligence_v_helpers_are_modularized() -> None:
    assert repository_service.v_adapter.strip_comments is (
        repository_vlang_primitives.strip_comments
    )
    assert repository_service.v_adapter.has_v_path_hints is (
        repository_vlang_primitives.has_v_path_hints
    )
    assert repository_service.v_adapter.is_probable_v_source is (
        repository_vlang_primitives.is_probable_v_source
    )
    assert repository_service.v_adapter.import_targets_for_text is (
        repository_vlang_primitives.import_targets_for_text
    )
    assert repository_service.v_adapter.module_aliases_for_path is (
        repository_vlang_analysis_support.module_aliases_for_path
    )
    assert repository_service.v_adapter.resolve_import is (
        repository_vlang_analysis_support.resolve_import
    )
    assert repository_service.v_adapter.parse_dependencies_only is (
        repository_vlang_analysis_support.parse_dependencies_only
    )
    assert repository_service.v_adapter.parse_file is (
        repository_vlang_analysis_support.parse_file
    )


def test_repository_intelligence_smalltalk_helpers_are_modularized() -> None:
    assert repository_service.smalltalk_adapter.strip_comments is (
        repository_smalltalk_primitives.strip_comments
    )
    assert repository_service.smalltalk_adapter.has_smalltalk_path_hints is (
        repository_smalltalk_primitives.has_smalltalk_path_hints
    )
    assert repository_service.smalltalk_adapter.is_probable_smalltalk_source is (
        repository_smalltalk_primitives.is_probable_smalltalk_source
    )
    assert repository_service.smalltalk_adapter.module_aliases_for_path is (
        repository_smalltalk_analysis_support.module_aliases_for_path
    )
    assert repository_service.smalltalk_adapter.parse_dependencies_only is (
        repository_smalltalk_analysis_support.parse_dependencies_only
    )
    assert repository_service.smalltalk_adapter.parse_file is (
        repository_smalltalk_analysis_support.parse_file
    )


def test_repository_intelligence_cfml_helpers_are_modularized() -> None:
    assert repository_service.cfml_adapter.strip_comments is (
        repository_cfml_primitives.strip_comments
    )
    assert repository_service.cfml_adapter.is_probable_cfml_source is (
        repository_cfml_primitives.is_probable_cfml_source
    )
    assert repository_service.cfml_adapter.module_aliases_for_path is (
        repository_cfml_analysis_support.module_aliases_for_path
    )
    assert repository_service.cfml_adapter.parse_dependencies_only is (
        repository_cfml_analysis_support.parse_dependencies_only
    )
    assert repository_service.cfml_adapter.parse_file is (
        repository_cfml_analysis_support.parse_file
    )
    assert repository_adapter_parser_dispatch._parse_cfml_dependencies_only is (
        repository_cfml_parser_dispatch._parse_cfml_dependencies_only
    )
    assert repository_adapter_parser_dispatch._parse_cfml_file is (
        repository_cfml_parser_dispatch._parse_cfml_file
    )


def test_repository_intelligence_elm_helpers_are_modularized() -> None:
    assert repository_service.elm_adapter.strip_comments is (
        repository_elm_primitives.strip_comments
    )
    assert repository_service.elm_adapter.is_probable_elm_source is (
        repository_elm_primitives.is_probable_elm_source
    )
    assert repository_service.elm_adapter.has_elm_path_hints is (
        repository_elm_primitives.has_elm_path_hints
    )
    assert repository_service.elm_adapter.module_aliases_for_path is (
        repository_elm_analysis_support.module_aliases_for_path
    )
    assert repository_service.elm_adapter.parse_dependencies_only is (
        repository_elm_analysis_support.parse_dependencies_only
    )
    assert repository_service.elm_adapter.parse_file is (
        repository_elm_analysis_support.parse_file
    )


def test_repository_intelligence_emacslisp_helpers_are_modularized() -> None:
    assert repository_service.emacslisp_adapter.strip_comments is (
        repository_emacslisp_primitives.strip_comments
    )
    assert repository_service.emacslisp_adapter.has_emacslisp_path_hints is (
        repository_emacslisp_primitives.has_emacslisp_path_hints
    )
    assert repository_service.emacslisp_adapter.is_probable_emacslisp_source is (
        repository_emacslisp_primitives.is_probable_emacslisp_source
    )
    assert repository_service.emacslisp_adapter.provided_features is (
        repository_emacslisp_primitives.provided_features
    )
    assert repository_service.emacslisp_adapter.cask_package_file_entries is (
        repository_emacslisp_primitives.cask_package_file_entries
    )
    assert repository_service.emacslisp_adapter.collect_symbol_entries is (
        repository_emacslisp_primitives.collect_symbol_entries
    )
    assert repository_service.emacslisp_adapter.module_aliases_for_path is (
        repository_emacslisp_analysis_support.module_aliases_for_path
    )
    assert repository_service.emacslisp_adapter.resolve_import is (
        repository_emacslisp_analysis_support.resolve_import
    )
    assert repository_service.emacslisp_adapter.parse_dependencies_only is (
        repository_emacslisp_analysis_support.parse_dependencies_only
    )
    assert repository_service.emacslisp_adapter.parse_file is (
        repository_emacslisp_analysis_support.parse_file
    )


def test_repository_intelligence_vimscript_helpers_are_modularized() -> None:
    assert repository_service.vimscript_adapter.strip_comments is (
        repository_vimscript_primitives.strip_comments
    )
    assert repository_service.vimscript_adapter.has_vimscript_path_hints is (
        repository_vimscript_primitives.has_vimscript_path_hints
    )
    assert repository_service.vimscript_adapter.is_probable_vimscript_source is (
        repository_vimscript_primitives.is_probable_vimscript_source
    )
    assert repository_service.vimscript_adapter.iter_source_statements is (
        repository_vimscript_primitives.iter_source_statements
    )
    assert repository_service.vimscript_adapter.iter_symbol_entries is (
        repository_vimscript_primitives.iter_symbol_entries
    )
    assert repository_service.vimscript_adapter.iter_reference_names is (
        repository_vimscript_primitives.iter_reference_names
    )
    assert repository_service.vimscript_adapter.module_aliases_for_path is (
        repository_vimscript_analysis_support.module_aliases_for_path
    )
    assert repository_service.vimscript_adapter.resolve_import is (
        repository_vimscript_analysis_support.resolve_import
    )
    assert repository_service.vimscript_adapter.parse_dependencies_only is (
        repository_vimscript_analysis_support.parse_dependencies_only
    )
    assert repository_service.vimscript_adapter.parse_file is (
        repository_vimscript_analysis_support.parse_file
    )


def test_repository_intelligence_racket_helpers_are_modularized() -> None:
    assert repository_service.racket_adapter.strip_comments is (
        repository_racket_primitives.strip_comments
    )
    assert repository_service.racket_adapter.has_racket_path_hints is (
        repository_racket_primitives.has_racket_path_hints
    )
    assert repository_service.racket_adapter.is_probable_racket_source is (
        repository_racket_primitives.is_probable_racket_source
    )
    assert repository_service.racket_adapter.collect_symbol_entries is (
        repository_racket_primitives.collect_symbol_entries
    )
    assert repository_service.racket_adapter.module_aliases_for_path is (
        repository_racket_analysis_support.module_aliases_for_path
    )
    assert repository_service.racket_adapter.resolve_import is (
        repository_racket_analysis_support.resolve_import
    )
    assert repository_service.racket_adapter.parse_dependencies_only is (
        repository_racket_analysis_support.parse_dependencies_only
    )
    assert repository_service.racket_adapter.parse_file is (
        repository_racket_analysis_support.parse_file
    )


def test_repository_intelligence_xpp_helpers_are_modularized() -> None:
    assert repository_service.xpp_adapter.strip_comments is (
        repository_xpp_primitives.strip_comments
    )
    assert repository_service.xpp_adapter.is_probable_xpp_source is (
        repository_xpp_primitives.is_probable_xpp_source
    )
    assert repository_service.xpp_adapter.is_probable_xpp_descriptor_config is (
        repository_xpp_primitives.is_probable_xpp_descriptor_config
    )
    assert repository_service.xpp_adapter.has_xpp_path_hints is (
        repository_xpp_primitives.has_xpp_path_hints
    )
    assert repository_service.xpp_adapter.module_aliases_for_path is (
        repository_xpp_analysis_support.module_aliases_for_path
    )
    assert repository_service.xpp_adapter.parse_dependencies_only is (
        repository_xpp_analysis_support.parse_dependencies_only
    )
    assert repository_service.xpp_adapter.parse_file is (
        repository_xpp_analysis_support.parse_file
    )
    assert repository_adapter_parser_dispatch._parse_xpp_dependencies_only is (
        repository_xpp_parser_dispatch._parse_xpp_dependencies_only
    )
    assert repository_adapter_parser_dispatch._parse_xpp_file is (
        repository_xpp_parser_dispatch._parse_xpp_file
    )


def test_repository_intelligence_scratch_helpers_are_modularized() -> None:
    assert repository_service.scratch_adapter.load_project_payload is (
        repository_scratch_primitives.load_project_payload
    )
    assert repository_service.scratch_adapter.has_scratch_path_hints is (
        repository_scratch_primitives.has_scratch_path_hints
    )
    assert repository_service.scratch_adapter.module_aliases_for_path is (
        repository_scratch_analysis_support.module_aliases_for_path
    )
    assert repository_service.scratch_adapter.parse_dependencies_only is (
        repository_scratch_analysis_support.parse_dependencies_only
    )
    assert repository_service.scratch_adapter.parse_file is (
        repository_scratch_analysis_support.parse_file
    )


def test_repository_intelligence_gml_helpers_are_modularized() -> None:
    assert repository_service.gml_adapter.strip_comments is (
        repository_gml_primitives.strip_comments
    )
    assert repository_service.gml_adapter.has_gml_path_hints is (
        repository_gml_primitives.has_gml_path_hints
    )
    assert repository_service.gml_adapter.load_game_maker_json is (
        repository_gml_primitives.load_game_maker_json
    )
    assert repository_service.gml_adapter.module_aliases_for_path is (
        repository_gml_analysis_support.module_aliases_for_path
    )
    assert repository_service.gml_adapter.parse_dependencies_only is (
        repository_gml_analysis_support.parse_dependencies_only
    )
    assert repository_service.gml_adapter.parse_file is (
        repository_gml_analysis_support.parse_file
    )


def test_repository_intelligence_systemverilog_helpers_are_modularized() -> None:
    assert repository_service.systemverilog_adapter.strip_comments is (
        repository_systemverilog_support.strip_comments
    )
    assert repository_service.systemverilog_adapter.strip_comments is (
        repository_systemverilog_primitives.strip_comments
    )
    assert repository_service.systemverilog_adapter.has_systemverilog_path_hints is (
        repository_systemverilog_support.has_systemverilog_path_hints
    )
    assert repository_service.systemverilog_adapter.has_systemverilog_path_hints is (
        repository_systemverilog_primitives.has_systemverilog_path_hints
    )
    assert repository_service.systemverilog_adapter.module_aliases_for_path is (
        repository_systemverilog_support.module_aliases_for_path
    )
    assert repository_service.systemverilog_adapter.module_aliases_for_path is (
        repository_systemverilog_analysis_support.module_aliases_for_path
    )
    assert repository_service.systemverilog_adapter.parse_dependencies_only is (
        repository_systemverilog_support.parse_dependencies_only
    )
    assert repository_service.systemverilog_adapter.parse_dependencies_only is (
        repository_systemverilog_analysis_support.parse_dependencies_only
    )
    assert repository_service.systemverilog_adapter.parse_file is (
        repository_systemverilog_support.parse_file
    )
    assert repository_service.systemverilog_adapter.parse_file is (
        repository_systemverilog_analysis_support.parse_file
    )


def test_repository_intelligence_verilog_helpers_are_modularized() -> None:
    assert repository_service.verilog_adapter.strip_comments is (
        repository_verilog_support.strip_comments
    )
    assert repository_service.verilog_adapter.strip_comments is (
        repository_verilog_primitives.strip_comments
    )
    assert repository_service.verilog_adapter.has_verilog_path_hints is (
        repository_verilog_support.has_verilog_path_hints
    )
    assert repository_service.verilog_adapter.has_verilog_path_hints is (
        repository_verilog_primitives.has_verilog_path_hints
    )
    assert repository_service.verilog_adapter.module_aliases_for_path is (
        repository_verilog_support.module_aliases_for_path
    )
    assert repository_service.verilog_adapter.module_aliases_for_path is (
        repository_verilog_analysis_support.module_aliases_for_path
    )
    assert repository_service.verilog_adapter.parse_dependencies_only is (
        repository_verilog_support.parse_dependencies_only
    )
    assert repository_service.verilog_adapter.parse_dependencies_only is (
        repository_verilog_analysis_support.parse_dependencies_only
    )
    assert repository_service.verilog_adapter.parse_file is (
        repository_verilog_support.parse_file
    )
    assert repository_service.verilog_adapter.parse_file is (
        repository_verilog_analysis_support.parse_file
    )


def test_repository_intelligence_tcl_helpers_are_modularized() -> None:
    assert repository_service.tcl_adapter._strip_comment_lines is (
        repository_tcl_primitives._strip_comment_lines
    )
    assert repository_service.tcl_adapter.is_probable_tcl_source is (
        repository_tcl_primitives.is_probable_tcl_source
    )
    assert repository_service.tcl_adapter.module_aliases_for_path is (
        repository_tcl_analysis_support.module_aliases_for_path
    )
    assert repository_service.tcl_adapter.parse_dependencies_only is (
        repository_tcl_analysis_support.parse_dependencies_only
    )
    assert repository_service.tcl_adapter.parse_file is (
        repository_tcl_analysis_support.parse_file
    )


def test_repository_intelligence_vbscript_helpers_are_modularized() -> None:
    assert repository_service.vbscript_adapter.strip_comments is (
        repository_vbscript_primitives.strip_comments
    )
    assert repository_service.vbscript_adapter.is_probable_vbscript_source is (
        repository_vbscript_primitives.is_probable_vbscript_source
    )
    assert repository_service.vbscript_adapter.import_targets_for_text is (
        repository_vbscript_primitives.import_targets_for_text
    )
    assert repository_service.vbscript_adapter.module_aliases_for_path is (
        repository_vbscript_analysis_support.module_aliases_for_path
    )
    assert repository_service.vbscript_adapter.parse_dependencies_only is (
        repository_vbscript_analysis_support.parse_dependencies_only
    )
    assert repository_service.vbscript_adapter.parse_file is (
        repository_vbscript_analysis_support.parse_file
    )


def test_repository_intelligence_classic_visual_basic_helpers_are_modularized() -> None:
    assert repository_service.classic_visual_basic_adapter.strip_comments is (
        repository_classic_visual_basic_support.strip_comments
    )
    assert repository_service.classic_visual_basic_adapter.strip_comments is (
        repository_classic_visual_basic_primitives.strip_comments
    )
    assert repository_service.classic_visual_basic_adapter.project_component_entries is (
        repository_classic_visual_basic_support.project_component_entries
    )
    assert repository_service.classic_visual_basic_adapter.project_component_entries is (
        repository_classic_visual_basic_primitives.project_component_entries
    )
    assert repository_service.classic_visual_basic_adapter.collect_symbol_entries is (
        repository_classic_visual_basic_support.collect_symbol_entries
    )
    assert repository_service.classic_visual_basic_adapter.collect_symbol_entries is (
        repository_classic_visual_basic_analysis_support.collect_symbol_entries
    )
    assert repository_service.classic_visual_basic_adapter.resolve_target is (
        repository_classic_visual_basic_support.resolve_target
    )
    assert repository_service.classic_visual_basic_adapter.resolve_target is (
        repository_classic_visual_basic_analysis_support.resolve_target
    )
    assert repository_service.classic_visual_basic_adapter.parse_dependencies_only is (
        repository_classic_visual_basic_support.parse_dependencies_only
    )
    assert repository_service.classic_visual_basic_adapter.parse_dependencies_only is (
        repository_classic_visual_basic_analysis_support.parse_dependencies_only
    )


def test_repository_intelligence_vba_adapter_reuses_classic_visual_basic_support() -> None:
    assert repository_service.vba_adapter.strip_comments is (
        repository_classic_visual_basic_support.strip_comments
    )
    assert repository_service.vba_adapter.collect_symbol_entries is (
        repository_classic_visual_basic_support.collect_symbol_entries
    )
    assert repository_service.vba_adapter.module_aliases_for_path is (
        repository_classic_visual_basic_support.module_aliases_for_path
    )
    assert repository_service.vba_adapter.resolve_target is (
        repository_classic_visual_basic_support.resolve_target
    )
    assert repository_service.vba_adapter.parse_dependencies_only is (
        repository_classic_visual_basic_support.parse_dependencies_only
    )
    assert repository_service.vba_adapter.parse_file is (
        repository_classic_visual_basic_support.parse_file
    )


def test_repository_intelligence_abap_helpers_are_modularized() -> None:
    assert repository_service.abap_adapter.normalize_identifier is (
        repository_abap_primitives.normalize_identifier
    )
    assert repository_service.abap_adapter.statement_entries is (
        repository_abap_primitives.statement_entries
    )
    assert repository_service.abap_adapter.collect_symbol_entries is (
        repository_abap_analysis_support.collect_symbol_entries
    )
    assert repository_service.abap_adapter.resolve_include is (
        repository_abap_analysis_support.resolve_include
    )
    assert repository_service.abap_adapter.resolve_target is (
        repository_abap_analysis_support.resolve_target
    )


def test_repository_intelligence_lisp_helpers_are_modularized() -> None:
    assert repository_service.lisp_adapter.strip_comments is (
        repository_lisp_support.strip_comments
    )
    assert repository_service.lisp_adapter.project_system_names is (
        repository_lisp_support.project_system_names
    )
    assert repository_service.lisp_adapter.collect_symbol_entries is (
        repository_lisp_analysis_support.collect_symbol_entries
    )
    assert repository_service.lisp_adapter.resolve_import is (
        repository_lisp_analysis_support.resolve_import
    )
    assert repository_service.lisp_adapter.parse_dependencies_only is (
        repository_lisp_analysis_support.parse_dependencies_only
    )


def test_repository_intelligence_scheme_helpers_are_modularized() -> None:
    assert repository_service.scheme_adapter.strip_comments is (
        repository_scheme_primitives.strip_comments
    )
    assert repository_service.scheme_adapter.has_scheme_path_hints is (
        repository_scheme_primitives.has_scheme_path_hints
    )
    assert repository_service.scheme_adapter.is_probable_scheme_source is (
        repository_scheme_primitives.is_probable_scheme_source
    )
    assert repository_service.scheme_adapter.collect_symbol_entries is (
        repository_scheme_primitives.collect_symbol_entries
    )
    assert repository_service.scheme_adapter.module_aliases_for_path is (
        repository_scheme_analysis_support.module_aliases_for_path
    )
    assert repository_service.scheme_adapter.resolve_import is (
        repository_scheme_analysis_support.resolve_import
    )
    assert repository_service.scheme_adapter.parse_dependencies_only is (
        repository_scheme_analysis_support.parse_dependencies_only
    )
    assert repository_service.scheme_adapter.parse_file is (
        repository_scheme_analysis_support.parse_file
    )


def test_repository_intelligence_prolog_helpers_are_modularized() -> None:
    assert repository_service.prolog_adapter.strip_comments is (
        repository_prolog_support.strip_comments
    )
    assert repository_service.prolog_adapter.strip_comments is (
        repository_prolog_primitives.strip_comments
    )
    assert repository_service.prolog_adapter.has_prolog_markers is (
        repository_prolog_support.has_prolog_markers
    )
    assert repository_service.prolog_adapter.has_prolog_markers is (
        repository_prolog_primitives.has_prolog_markers
    )
    assert repository_service.prolog_adapter.collect_symbol_entries is (
        repository_prolog_support.collect_symbol_entries
    )
    assert repository_service.prolog_adapter.collect_symbol_entries is (
        repository_prolog_analysis_support.collect_symbol_entries
    )
    assert repository_service.prolog_adapter.resolve_import is (
        repository_prolog_support.resolve_import
    )
    assert repository_service.prolog_adapter.resolve_import is (
        repository_prolog_analysis_support.resolve_import
    )
    assert repository_service.prolog_adapter.resolve_target is (
        repository_prolog_support.resolve_target
    )
    assert repository_service.prolog_adapter.resolve_target is (
        repository_prolog_analysis_support.resolve_target
    )
    assert repository_service.prolog_adapter.parse_dependencies_only is (
        repository_prolog_support.parse_dependencies_only
    )
    assert repository_service.prolog_adapter.parse_dependencies_only is (
        repository_prolog_analysis_support.parse_dependencies_only
    )
    assert repository_service.prolog_adapter.parse_file is (
        repository_prolog_support.parse_file
    )
    assert repository_service.prolog_adapter.parse_file is (
        repository_prolog_analysis_support.parse_file
    )


def test_repository_intelligence_rpg_helpers_are_modularized() -> None:
    assert repository_service.rpg_adapter.strip_comments is (
        repository_rpg_support.strip_comments
    )
    assert repository_service.rpg_adapter.normalize_target is (
        repository_rpg_support.normalize_target
    )
    assert repository_service.rpg_adapter.collect_symbol_entries is (
        repository_rpg_support.collect_symbol_entries
    )
    assert repository_service.rpg_adapter.resolve_import is (
        repository_rpg_support.resolve_import
    )
    assert repository_service.rpg_adapter.extract_import_bindings is (
        repository_rpg_support.extract_import_bindings
    )


def test_repository_intelligence_scripting_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_adapter_parser_dispatch._parse_ruby_file is (
        repository_scripting_parser_dispatch._parse_ruby_file
    )
    assert repository_adapter_parser_dispatch._extract_crystal_import_bindings is (
        repository_scripting_parser_dispatch._extract_crystal_import_bindings
    )
    assert repository_adapter_parser_dispatch._parse_php_dependencies_only is (
        repository_scripting_parser_dispatch._parse_php_dependencies_only
    )
    assert repository_adapter_parser_dispatch._parse_elixir_file is (
        repository_scripting_parser_dispatch._parse_elixir_file
    )


def test_repository_intelligence_typed_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_adapter_parser_dispatch._parse_swift_file is (
        repository_typed_parser_dispatch._parse_swift_file
    )
    assert repository_adapter_parser_dispatch._extract_csharp_import_bindings is (
        repository_typed_parser_dispatch._extract_csharp_import_bindings
    )
    assert repository_adapter_parser_dispatch._parse_jvm_dependencies_only is (
        repository_typed_parser_dispatch._parse_jvm_dependencies_only
    )
    assert repository_adapter_parser_dispatch._parse_jvm_file is (
        repository_typed_parser_dispatch._parse_jvm_file
    )


def test_repository_intelligence_pascal_solidity_helpers_are_modularized() -> None:
    assert repository_service._normalize_pascal_target is (
        repository_pascal_solidity_dispatch._normalize_pascal_target
    )
    assert repository_service._collect_pascal_symbol_entries is (
        repository_pascal_solidity_dispatch._collect_pascal_symbol_entries
    )
    assert repository_service._resolve_pascal_target is (
        repository_pascal_solidity_dispatch._resolve_pascal_target
    )
    assert repository_service._parse_pascal_file is (
        repository_pascal_solidity_dispatch._parse_pascal_file
    )
    assert repository_service._resolve_solidity_import is (
        repository_pascal_solidity_dispatch._resolve_solidity_import
    )
    assert repository_service._parse_solidity_dependencies_only is (
        repository_pascal_solidity_dispatch._parse_solidity_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["pascal"] is (
        repository_pascal_solidity_dispatch._parse_pascal_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["delphi"] is (
        repository_pascal_solidity_dispatch._parse_delphi_dependencies_only
    )
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["delphi"] is (
        repository_pascal_solidity_dispatch._parse_delphi_file
    )
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["solidity"] is (
        repository_pascal_solidity_dispatch._parse_solidity_file
    )


def test_repository_intelligence_storage_helpers_are_modularized() -> None:
    assert repository_service._hash_file is repository_storage._hash_file
    assert repository_service._artifact_ref is repository_storage._artifact_ref
    assert repository_service._extract_tar_handle is repository_storage._extract_tar_handle
    assert repository_service._extract_tar is repository_storage._extract_tar
    assert repository_service._extract_zip is repository_storage._extract_zip
    assert repository_service._extract_archive is repository_storage._extract_archive
    assert repository_service._snapshot_paths is repository_storage._snapshot_paths
    assert repository_service.materialized_snapshot is repository_storage.materialized_snapshot
    assert repository_service._load_snapshot_manifest is repository_storage._load_snapshot_manifest
    assert repository_service._load_triage_manifest is repository_storage._load_triage_manifest
    assert repository_service._load_decision_plan_manifest is (
        repository_storage._load_decision_plan_manifest
    )
    assert repository_service._load_patch_impact_manifest is (
        repository_storage._load_patch_impact_manifest
    )
    assert repository_service._load_simulation_manifest is (
        repository_storage._load_simulation_manifest
    )


def test_repository_intelligence_snapshot_workflow_helpers_are_modularized() -> None:
    assert repository_service._snapshot_lookup_key is (
        repository_snapshot_workflow._snapshot_lookup_key
    )
    assert repository_service._snapshot_lookup_path is (
        repository_snapshot_workflow._snapshot_lookup_path
    )
    assert repository_service._create_source_archive is (
        repository_snapshot_workflow._create_source_archive
    )


def test_repository_intelligence_snapshot_workflow_wrappers_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SimpleNamespace(id="repo-1", org_id="org-1")
    request = RepositorySnapshotCreateRequest()
    snapshot_result = object()
    get_result = object()
    observed: dict[str, dict[str, Any]] = {}

    def _fake_create_repository_snapshot(**kwargs: Any) -> object:
        observed["create"] = kwargs
        return snapshot_result

    def _fake_get_repository_snapshot(**kwargs: Any) -> object:
        observed["get"] = kwargs
        return get_result

    monkeypatch.setattr(
        repository_snapshot_workflow,
        "create_repository_snapshot",
        _fake_create_repository_snapshot,
    )
    monkeypatch.setattr(
        repository_snapshot_workflow,
        "get_repository_snapshot",
        _fake_get_repository_snapshot,
    )

    assert (
        repository_service.create_repository_snapshot(
            connector=connector,
            request=request,
        )
        is snapshot_result
    )
    assert observed["create"]["connector"] is connector
    assert observed["create"]["request"] is request
    assert (
        observed["create"]["engine_revision"]
        == repository_service._REPOSITORY_INTELLIGENCE_ENGINE_REVISION
    )
    assert (
        observed["create"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert observed["create"]["parse_connector_config"] is repository_service._parse_connector_config
    assert observed["create"]["resolved_repository_source"] is repository_service.resolved_repository_source
    assert (
        observed["create"]["compact_repository_focus_paths"]
        is repository_service._compact_repository_focus_paths
    )
    assert observed["create"]["iter_repository_files"] is repository_service._iter_repository_files
    assert observed["create"]["build_module_index"] is repository_service._build_module_index
    assert (
        observed["create"]["build_workspace_package_index"]
        is repository_service._build_workspace_package_index
    )
    assert (
        observed["create"]["build_workspace_go_module_index"]
        is repository_service._build_workspace_go_module_index
    )
    assert (
        observed["create"]["git_tracked_content_hashes"]
        is repository_service._git_tracked_content_hashes
    )
    assert (
        observed["create"]["file_analysis_context_hash"]
        is repository_service._file_analysis_context_hash
    )
    assert observed["create"]["analyze_snapshot_files"] is repository_service._analyze_snapshot_files
    assert (
        observed["create"]["augment_r_package_symbol_references"]
        is repository_service._augment_r_package_symbol_references
    )
    assert (
        observed["create"]["augment_julia_package_symbol_references"]
        is repository_service._augment_julia_package_symbol_references
    )
    assert (
        observed["create"]["resolve_symbol_reference_target"]
        is repository_service._resolve_symbol_reference_target
    )
    assert observed["create"]["hash_file"] is repository_service._hash_file
    assert observed["create"]["write_bytes_with_hash"] is repository_service._write_bytes_with_hash

    assert (
        repository_service.get_repository_snapshot(
            connector=connector,
            snapshot_id="snapshot-1",
        )
        is get_result
    )
    assert observed["get"]["connector"] is connector
    assert observed["get"]["snapshot_id"] == "snapshot-1"
    assert (
        observed["get"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert observed["get"]["load_snapshot_manifest"] is repository_service._load_snapshot_manifest


def test_repository_intelligence_graph_workflow_wrappers_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SimpleNamespace(id="repo-1", org_id="org-1")
    graph_request = repository_service.RepositoryGraphQueryRequest(
        snapshot_id="snapshot-1",
        file_path="src/service.py",
    )
    triage_request = RepositoryTriageRequest(
        snapshot_id="snapshot-1",
        signals={"issue_text": "service failure"},
    )
    query_result = object()
    triage_result = object()
    observed: dict[str, dict[str, Any]] = {}

    def _fake_query_repository_graph(**kwargs: Any) -> object:
        observed["query"] = kwargs
        return query_result

    def _fake_triage_repository(**kwargs: Any) -> object:
        observed["triage"] = kwargs
        return triage_result

    monkeypatch.setattr(
        repository_graph_workflow,
        "query_repository_graph",
        _fake_query_repository_graph,
    )
    monkeypatch.setattr(
        repository_graph_workflow,
        "triage_repository",
        _fake_triage_repository,
    )

    assert (
        repository_service.query_repository_graph(
            connector=connector,
            request=graph_request,
        )
        is query_result
    )
    assert observed["query"]["connector"] is connector
    assert observed["query"]["request"] is graph_request
    assert (
        observed["query"]["engine_revision"]
        == repository_service._REPOSITORY_INTELLIGENCE_ENGINE_REVISION
    )
    assert (
        observed["query"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert observed["query"]["load_snapshot_manifest"] is repository_service._load_snapshot_manifest
    assert observed["query"]["load_triage_manifest"] is repository_service._load_triage_manifest
    assert observed["query"]["read_json"] is repository_service._read_json

    assert (
        repository_service.triage_repository(
            connector=connector,
            request=triage_request,
        )
        is triage_result
    )
    assert observed["triage"]["connector"] is connector
    assert observed["triage"]["request"] is triage_request
    assert (
        observed["triage"]["engine_revision"]
        == repository_service._REPOSITORY_INTELLIGENCE_ENGINE_REVISION
    )
    assert (
        observed["triage"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert (
        observed["triage"]["load_snapshot_manifest"] is repository_service._load_snapshot_manifest
    )
    assert observed["triage"]["read_json"] is repository_service._read_json
    assert observed["triage"]["materialized_snapshot"] is repository_service.materialized_snapshot


def test_repository_intelligence_decision_plan_helpers_are_modularized() -> None:
    assert repository_service._decision_plan_lookup_key is (
        repository_decision_plan_workflow._decision_plan_lookup_key
    )
    assert repository_service._raise_local_planner_unsupported is (
        repository_planner_generation._raise_local_planner_unsupported
    )
    assert repository_service._extract_return_literal_mismatch is (
        repository_planner_generation._extract_return_literal_mismatch
    )
    assert repository_service._workspace_context_value is (
        repository_planner_generation._workspace_context_value
    )
    assert repository_service._position_to_offset is (
        repository_planner_generation._position_to_offset
    )
    assert repository_service._python_string_literal is (
        repository_planner_generation._python_string_literal
    )
    assert repository_service._extract_json_object is (
        repository_planner_generation._extract_json_object
    )
    assert repository_service._decision_plan_integrity is (
        repository_decision_plan_workflow._decision_plan_integrity
    )
    assert repository_service._option_risk is repository_decision_plan_workflow._option_risk


def test_repository_intelligence_patch_analysis_helpers_are_modularized() -> None:
    assert repository_service._patch_changed_files is (
        repository_patch_analysis._patch_changed_files
    )
    assert repository_service._top_level_service is repository_patch_analysis._top_level_service
    assert repository_service._is_test_path is repository_patch_analysis._is_test_path


def test_repository_intelligence_patch_analysis_validate_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_validate_patch_against_snapshot(**kwargs: Any) -> None:
        observed.update(kwargs)

    monkeypatch.setattr(
        repository_patch_analysis,
        "_validate_patch_against_snapshot",
        _fake_validate_patch_against_snapshot,
    )

    snapshot_manifest = {"snapshot_id": "snapshot-1", "source_archive_path": "/tmp/source.tar"}
    patch_diff = "diff --git a/src/app.py b/src/app.py\n"

    repository_service._validate_patch_against_snapshot(
        snapshot_manifest=snapshot_manifest,
        patch_diff=patch_diff,
    )

    assert observed["snapshot_manifest"] is snapshot_manifest
    assert observed["patch_diff"] == patch_diff
    assert observed["materialized_snapshot"] is repository_service.materialized_snapshot
    assert observed["git_command"] is repository_service._git_command


def test_repository_intelligence_fsharp_helpers_are_modularized() -> None:
    assert repository_service._normalize_fsharp_symbol_name is (
        repository_service.fsharp_adapter.normalize_symbol_name
    )
    assert repository_service._normalize_fsharp_target is (
        repository_service.fsharp_adapter.normalize_target
    )
    assert repository_service._fsharp_path_aliases is repository_service.fsharp_adapter.path_aliases
    assert repository_service._fsharp_namespaces_from_text is (
        repository_service.fsharp_adapter.namespaces_from_text
    )
    assert repository_service._fsharp_open_targets is (
        repository_service.fsharp_adapter.open_targets
    )


def test_repository_intelligence_fsharp_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_suffix_match: Any,
        resolve_directory_prefix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["resolve_directory_prefix_match"] = resolve_directory_prefix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.fsharp_adapter, "parse_file", _fake_parse_file)

    module_index = {"Acme.Core": "src/Acme/Core.fs"}

    result = repository_service._parse_fsharp_file(
        "src/Acme/App.fs",
        "module Acme.App",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/Acme/App.fs"
    assert observed["text"] == "module Acme.App"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert callable(observed["resolve_suffix_match"])
    assert callable(observed["resolve_directory_prefix_match"])


def test_repository_intelligence_ruby_helpers_are_modularized() -> None:
    assert repository_service._ruby_module_aliases_for_path is (
        repository_service.ruby_adapter.module_aliases_for_path
    )


def test_repository_intelligence_ruby_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
        module_index_aliases_for_file: Any,
        root_path: Path,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["module_index_aliases_for_file"] = module_index_aliases_for_file
        observed["root_path"] = root_path
        return (), (), ()

    monkeypatch.setattr(repository_service.ruby_adapter, "parse_file", _fake_parse_file)

    module_index = {"lib/acme/widget.rb": "lib/acme/widget.rb"}

    result = repository_service._parse_ruby_file(
        "lib/acme/app.rb",
        "require 'acme/widget'",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "lib/acme/app.rb"
    assert observed["text"] == "require 'acme/widget'"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match
    assert observed["module_index_aliases_for_file"] is (
        repository_service._module_index_aliases_for_file
    )
    assert observed["root_path"] == Path(".")


def test_repository_intelligence_crystal_helpers_are_modularized() -> None:
    assert repository_service._is_crystal_constant_alias is (
        repository_service.crystal_adapter.is_constant_alias
    )
    assert repository_service._crystal_declared_type_aliases_for_path is (
        repository_service.crystal_adapter.declared_type_aliases_for_path
    )
    assert repository_service._crystal_constant_aliases_for_file is (
        repository_service.crystal_adapter.constant_aliases_for_file
    )


def test_repository_intelligence_crystal_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
        module_index_values: Any,
        module_index_aliases_for_file: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["module_index_values"] = module_index_values
        observed["module_index_aliases_for_file"] = module_index_aliases_for_file
        return (), (), ()

    monkeypatch.setattr(repository_service.crystal_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/acme/widget.cr": "src/acme/widget.cr"}

    result = repository_service._parse_crystal_file(
        "src/acme/app.cr",
        "require \"acme/widget\"",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/acme/app.cr"
    assert observed["text"] == 'require "acme/widget"'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match
    assert observed["module_index_values"] is repository_service._module_index_values
    assert observed["module_index_aliases_for_file"] is (
        repository_service._module_index_aliases_for_file
    )


def test_repository_intelligence_php_helpers_are_modularized() -> None:
    assert repository_service._php_current_namespace is repository_service.php_adapter.current_namespace
    assert repository_service._php_leading_docblock is repository_service.php_adapter.leading_docblock
    assert repository_service._php_symbol_declaration_header is (
        repository_service.php_adapter.symbol_declaration_header
    )
    assert repository_service._php_doc_type_tokens is repository_service.php_adapter.doc_type_tokens
    assert repository_service._php_type_tokens_from_header is (
        repository_service.php_adapter.type_tokens_from_header
    )
    assert repository_service._php_module_aliases_for_path is (
        repository_service.php_adapter.module_aliases_for_path
    )


def test_repository_intelligence_php_adapter_helpers_are_modularized() -> None:
    assert repository_service.php_adapter.current_namespace is (
        repository_php_primitives.current_namespace
    )
    assert repository_service.php_adapter.leading_docblock is (
        repository_php_primitives.leading_docblock
    )
    assert repository_service.php_adapter.symbol_declaration_header is (
        repository_php_primitives.symbol_declaration_header
    )
    assert repository_service.php_adapter.doc_type_tokens is (
        repository_php_primitives.doc_type_tokens
    )
    assert repository_service.php_adapter.type_tokens_from_header is (
        repository_php_primitives.type_tokens_from_header
    )
    assert repository_service.php_adapter._symbol_entries is (
        repository_php_primitives._symbol_entries
    )
    assert repository_service.php_adapter.module_aliases_for_path is (
        repository_php_analysis_support.module_aliases_for_path
    )
    assert repository_service.php_adapter.resolve_import is (
        repository_php_analysis_support.resolve_import
    )
    assert repository_service.php_adapter.resolve_same_namespace_reference is (
        repository_php_analysis_support.resolve_same_namespace_reference
    )
    assert repository_service.php_adapter.resolve_reference_target is (
        repository_php_analysis_support.resolve_reference_target
    )
    assert repository_service.php_adapter.iter_reference_targets is (
        repository_php_analysis_support.iter_reference_targets
    )
    assert repository_service.php_adapter.extract_import_bindings is (
        repository_php_analysis_support.extract_import_bindings
    )
    assert repository_service.php_adapter.parse_dependencies_only is (
        repository_php_analysis_support.parse_dependencies_only
    )
    assert repository_service.php_adapter.parse_file is repository_php_analysis_support.parse_file


def test_repository_intelligence_php_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.php_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/Acme/Widget.php": "src/Acme/Widget.php"}

    result = repository_service._parse_php_file(
        "src/Acme/App.php",
        "<?php\nuse Acme\\\\Widget;\n",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/Acme/App.php"
    assert observed["text"] == "<?php\nuse Acme\\\\Widget;\n"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_elixir_helpers_are_modularized() -> None:
    assert repository_service._elixir_module_aliases_for_path is (
        repository_service.elixir_adapter.module_aliases_for_path
    )
    assert repository_service._elixir_module_path_variants is (
        repository_service.elixir_adapter.module_path_variants
    )


def test_repository_intelligence_elixir_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_suffix_match: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_suffix_match"] = resolve_suffix_match
        return ()

    monkeypatch.setattr(
        repository_service.elixir_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"lib/acme/widget.ex": "lib/acme/widget.ex"}

    result = repository_service._parse_elixir_dependencies_only(
        "lib/acme/app.ex",
        "alias Acme.Widget",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "lib/acme/app.ex"
    assert observed["text"] == "alias Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_elixir_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.elixir_adapter, "parse_file", _fake_parse_file)

    module_index = {"lib/acme/widget.ex": "lib/acme/widget.ex"}

    result = repository_service._parse_elixir_file(
        "lib/acme/app.ex",
        "alias Acme.Widget",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "lib/acme/app.ex"
    assert observed["text"] == "alias Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_perl_helpers_are_modularized() -> None:
    assert repository_service._perl_module_aliases_for_path is (
        repository_service.perl_adapter.module_aliases_for_path
    )
    assert repository_service._extract_perl_use_args is (
        repository_service.perl_adapter.extract_use_args
    )
    assert repository_service._is_perl_package_like is (
        repository_service.perl_adapter.is_package_like
    )


def test_repository_intelligence_perl_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return ()

    monkeypatch.setattr(
        repository_service.perl_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"lib/Acme/Widget.pm": "lib/Acme/Widget.pm"}

    result = repository_service._parse_perl_dependencies_only(
        "lib/Acme/App.pm",
        "use Acme::Widget qw(run);",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "lib/Acme/App.pm"
    assert observed["text"] == "use Acme::Widget qw(run);"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_perl_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.perl_adapter, "parse_file", _fake_parse_file)

    module_index = {"lib/Acme/Widget.pm": "lib/Acme/Widget.pm"}

    result = repository_service._parse_perl_file(
        "lib/Acme/App.pm",
        "use Acme::Widget qw(run);",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "lib/Acme/App.pm"
    assert observed["text"] == "use Acme::Widget qw(run);"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_lua_helpers_are_modularized() -> None:
    assert repository_service._LUA_REQUIRE_RE is repository_service.lua_adapter.REQUIRE_RE
    assert repository_service._LUA_REQUIRE_BINDING_RE is (
        repository_service.lua_adapter.REQUIRE_BINDING_RE
    )
    assert repository_service._LUA_RESERVED_SYMBOL_NAMES is (
        repository_service.lua_adapter.RESERVED_SYMBOL_NAMES
    )


def test_repository_intelligence_lua_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        import_target: str,
        *,
        module_index: dict[str, str],
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "lua/acme/util.lua"

    monkeypatch.setattr(repository_service.lua_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"lua/acme/util.lua": "lua/acme/util.lua"}

    result = repository_service._resolve_lua_import("acme.util", module_index)

    assert result == "lua/acme/util.lua"
    assert observed["import_target"] == "acme.util"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_lua_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_suffix_match: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_suffix_match"] = resolve_suffix_match
        return ()

    monkeypatch.setattr(
        repository_service.lua_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"lua/acme/util.lua": "lua/acme/util.lua"}

    result = repository_service._parse_lua_dependencies_only(
        "lua/acme/core.lua",
        'local util = require "acme.util"',
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "lua/acme/core.lua"
    assert observed["text"] == 'local util = require "acme.util"'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_lua_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.lua_adapter, "parse_file", _fake_parse_file)

    module_index = {"lua/acme/util.lua": "lua/acme/util.lua"}

    result = repository_service._parse_lua_file(
        "lua/acme/core.lua",
        'local util = require "acme.util"',
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "lua/acme/core.lua"
    assert observed["text"] == 'local util = require "acme.util"'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_luau_helpers_are_modularized() -> None:
    assert repository_service.luau_adapter.has_luau_path_hints is (
        repository_luau_primitives.has_luau_path_hints
    )
    assert repository_service.luau_adapter.is_probable_luau_source is (
        repository_luau_primitives.is_probable_luau_source
    )
    assert repository_service.luau_adapter.collect_symbol_entries is (
        repository_luau_primitives.collect_symbol_entries
    )
    assert repository_service.luau_adapter.module_aliases_for_path is (
        repository_luau_analysis_support.module_aliases_for_path
    )
    assert repository_service.luau_adapter.parse_dependencies_only is (
        repository_luau_analysis_support.parse_dependencies_only
    )
    assert repository_service.luau_adapter.parse_file is (
        repository_luau_analysis_support.parse_file
    )
    assert repository_adapter_parser_dispatch.REGISTERED_ADAPTER_DEPENDENCY_PARSERS["luau"] is (
        repository_luau_parser_dispatch._parse_luau_dependencies_only
    )
    assert repository_adapter_parser_dispatch.REGISTERED_ADAPTER_FILE_PARSERS["luau"] is (
        repository_luau_parser_dispatch._parse_luau_file
    )


def test_luau_adapter_module_aliases_include_wally_and_modules(tmp_path: Path) -> None:
    repo_path = tmp_path / "luau-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "wally.toml").write_text(
        "[package]\nname = 'ukendio/jecs'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "jecs.luau").write_text("--!strict\nreturn {}\n", encoding="utf-8")
    (repo_path / "modules" / "entity_visualiser.luau").write_text(
        "--!strict\nreturn {}\n",
        encoding="utf-8",
    )

    package_aliases = repository_service.luau_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/jecs.luau",
    )
    module_aliases = repository_service.luau_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/entity_visualiser.luau",
    )

    assert "@jecs" in package_aliases
    assert "src/jecs" in package_aliases
    assert "@modules/entity_visualiser" in module_aliases


def test_language_for_path_detects_luau_suffix_and_markers() -> None:
    assert repository_service._language_for_path(
        Path("src/Main.luau"),
        text="--!strict\nreturn {}\n",
    ) == "luau"
    assert repository_service._language_for_path(
        Path("src/Main.lua"),
        text="--!strict\nexport type Packet = { id: string }\nreturn {}\n",
    ) == "luau"


def test_repository_intelligence_shell_helpers_are_modularized() -> None:
    assert repository_service._SHELL_SOURCE_RE is repository_service.shell_adapter.SOURCE_RE
    assert repository_service._SHELL_CONTROL_PREFIXES is (
        repository_service.shell_adapter.CONTROL_PREFIXES
    )


def test_repository_intelligence_shell_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_source(
        *,
        current_file: str,
        source_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["source_target"] = source_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "scripts/lib.sh"

    monkeypatch.setattr(repository_service.shell_adapter, "resolve_source", _fake_resolve_source)

    module_index = {"scripts/lib.sh": "scripts/lib.sh"}

    result = repository_service._resolve_shell_source(
        current_file="scripts/main.sh",
        source_target="./lib.sh",
        module_index=module_index,
    )

    assert result == "scripts/lib.sh"
    assert observed["current_file"] == "scripts/main.sh"
    assert observed["source_target"] == "./lib.sh"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_shell_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return ()

    monkeypatch.setattr(
        repository_service.shell_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"scripts/lib.sh": "scripts/lib.sh"}

    result = repository_service._parse_shell_dependencies_only(
        "scripts/main.sh",
        "source ./lib.sh",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "scripts/main.sh"
    assert observed["text"] == "source ./lib.sh"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_shell_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.shell_adapter, "parse_file", _fake_parse_file)

    module_index = {"scripts/lib.sh": "scripts/lib.sh"}

    result = repository_service._parse_shell_file(
        "scripts/main.sh",
        "source ./lib.sh",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "scripts/main.sh"
    assert observed["text"] == "source ./lib.sh"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_powershell_helpers_are_modularized() -> None:
    assert repository_service._POWERSHELL_DOT_SOURCE_RE is (
        repository_service.powershell_adapter.DOT_SOURCE_RE
    )
    assert repository_service._POWERSHELL_SOURCE_SUFFIXES is (
        repository_service.powershell_adapter.SOURCE_SUFFIXES
    )


def test_repository_intelligence_powershell_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "Modules/Acme/Acme.psm1"

    monkeypatch.setattr(
        repository_service.powershell_adapter,
        "resolve_import",
        _fake_resolve_import,
    )

    module_index = {"Modules/Acme/Acme.psm1": "Modules/Acme/Acme.psm1"}

    result = repository_service._resolve_powershell_import(
        current_file="Modules/Main.ps1",
        import_target="./Acme.psd1",
        module_index=module_index,
    )

    assert result == "Modules/Acme/Acme.psm1"
    assert observed["current_file"] == "Modules/Main.ps1"
    assert observed["import_target"] == "./Acme.psd1"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_powershell_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return ()

    monkeypatch.setattr(
        repository_service.powershell_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"Modules/Acme/Acme.psm1": "Modules/Acme/Acme.psm1"}

    result = repository_service._parse_powershell_dependencies_only(
        "Modules/Main.ps1",
        "Import-Module ./Acme.psd1",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "Modules/Main.ps1"
    assert observed["text"] == "Import-Module ./Acme.psd1"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_powershell_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(
        repository_service.powershell_adapter,
        "parse_file",
        _fake_parse_file,
    )

    module_index = {"Modules/Acme/Acme.psm1": "Modules/Acme/Acme.psm1"}

    result = repository_service._parse_powershell_file(
        "Modules/Main.ps1",
        "Import-Module ./Acme.psd1",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "Modules/Main.ps1"
    assert observed["text"] == "Import-Module ./Acme.psd1"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_haskell_helpers_are_modularized() -> None:
    assert repository_service._HASKELL_MODULE_RE is repository_service.haskell_adapter.MODULE_RE
    assert repository_service._normalize_haskell_source_line is (
        repository_service.haskell_adapter.normalize_source_line
    )
    assert repository_service._haskell_module_aliases_for_path is (
        repository_service.haskell_adapter.module_aliases_for_path
    )


def test_repository_intelligence_haskell_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        import_target: str,
        module_index: dict[str, str],
        *,
        normalize_repository_relative_path: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return "src/Acme/Widget.hs"

    monkeypatch.setattr(repository_service.haskell_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"src/Acme/Widget.hs": "src/Acme/Widget.hs"}

    result = repository_service._resolve_haskell_import("Acme.Widget", module_index)

    assert result == "src/Acme/Widget.hs"
    assert observed["import_target"] == "Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_haskell_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.haskell_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/Acme/Widget.hs": "src/Acme/Widget.hs"}

    result = repository_service._parse_haskell_dependencies_only(
        "src/Acme/App.hs",
        "import Acme.Widget",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/Acme/App.hs"
    assert observed["text"] == "import Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_haskell_import


def test_repository_intelligence_haskell_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.haskell_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/Acme/Widget.hs": "src/Acme/Widget.hs"}

    result = repository_service._parse_haskell_file(
        "src/Acme/App.hs",
        "import Acme.Widget",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/Acme/App.hs"
    assert observed["text"] == "import Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_haskell_import


def test_repository_intelligence_clojure_helpers_are_modularized() -> None:
    assert repository_service._CLOJURE_NS_RE is repository_service.clojure_adapter.NS_RE
    assert repository_service._extract_clojure_ns_form is (
        repository_service.clojure_adapter.extract_ns_form
    )
    assert repository_service._clojure_module_aliases_for_path is (
        repository_service.clojure_adapter.module_aliases_for_path
    )


def test_repository_intelligence_clojure_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        import_target: str,
        module_index: dict[str, str],
        *,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/acme/widget.clj"

    monkeypatch.setattr(repository_service.clojure_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"src/acme/widget.clj": "src/acme/widget.clj"}

    result = repository_service._resolve_clojure_import("acme.widget", module_index)

    assert result == "src/acme/widget.clj"
    assert observed["import_target"] == "acme.widget"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_clojure_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.clojure_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/acme/widget.clj": "src/acme/widget.clj"}

    result = repository_service._parse_clojure_dependencies_only(
        "src/acme/app.clj",
        "(ns acme.app (:require [acme.widget :as widget]))",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/acme/app.clj"
    assert observed["text"] == "(ns acme.app (:require [acme.widget :as widget]))"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_clojure_import


def test_repository_intelligence_clojure_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.clojure_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/acme/widget.clj": "src/acme/widget.clj"}

    result = repository_service._parse_clojure_file(
        "src/acme/app.clj",
        "(ns acme.app (:require [acme.widget :as widget]))",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/acme/app.clj"
    assert observed["text"] == "(ns acme.app (:require [acme.widget :as widget]))"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_clojure_import


def test_repository_intelligence_ocaml_helpers_are_modularized() -> None:
    assert repository_service._OCAML_OPEN_RE is repository_service.ocaml_adapter.OPEN_RE
    assert repository_service._ocaml_module_aliases_for_path is (
        repository_service.ocaml_adapter.module_aliases_for_path
    )


def test_repository_intelligence_ocaml_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_module(
        import_target: str,
        module_index: dict[str, str],
        *,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/widget.ml"

    monkeypatch.setattr(repository_service.ocaml_adapter, "resolve_module", _fake_resolve_module)

    module_index = {"src/widget.ml": "src/widget.ml"}

    result = repository_service._resolve_ocaml_module("Acme.Widget", module_index)

    assert result == "src/widget.ml"
    assert observed["import_target"] == "Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_ocaml_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module"] = resolve_module
        return ()

    monkeypatch.setattr(
        repository_service.ocaml_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/widget.ml": "src/widget.ml"}

    result = repository_service._parse_ocaml_dependencies_only(
        "src/app.ml",
        "open Acme.Widget",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/app.ml"
    assert observed["text"] == "open Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module"] is repository_service._resolve_ocaml_module


def test_repository_intelligence_ocaml_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module"] = resolve_module
        return (), (), ()

    monkeypatch.setattr(repository_service.ocaml_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/widget.ml": "src/widget.ml"}

    result = repository_service._parse_ocaml_file(
        "src/app.ml",
        "open Acme.Widget",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/app.ml"
    assert observed["text"] == "open Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module"] is repository_service._resolve_ocaml_module


def test_repository_intelligence_erlang_helpers_are_modularized() -> None:
    assert repository_service._ERLANG_MODULE_RE is repository_service.erlang_adapter.MODULE_RE
    assert repository_service._erlang_module_aliases_for_path is (
        repository_service.erlang_adapter.module_aliases_for_path
    )


def test_repository_intelligence_erlang_resolve_module_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_module(
        import_target: str,
        module_index: dict[str, str],
        *,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/cowboy.erl"

    monkeypatch.setattr(repository_service.erlang_adapter, "resolve_module", _fake_resolve_module)

    module_index = {"src/cowboy.erl": "src/cowboy.erl"}

    result = repository_service._resolve_erlang_module("cowboy", module_index)

    assert result == "src/cowboy.erl"
    assert observed["import_target"] == "cowboy"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_erlang_resolve_include_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_include(
        *,
        current_file: str,
        import_target: str,
        is_lib: bool,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["is_lib"] = is_lib
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "include/cowboy.hrl"

    monkeypatch.setattr(repository_service.erlang_adapter, "resolve_include", _fake_resolve_include)

    module_index = {"include/cowboy.hrl": "include/cowboy.hrl"}

    result = repository_service._resolve_erlang_include(
        current_file="src/main.erl",
        import_target="cowboy.hrl",
        is_lib=False,
        module_index=module_index,
    )

    assert result == "include/cowboy.hrl"
    assert observed["current_file"] == "src/main.erl"
    assert observed["import_target"] == "cowboy.hrl"
    assert observed["is_lib"] is False
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_erlang_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module: Any,
        resolve_include: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module"] = resolve_module
        observed["resolve_include"] = resolve_include
        return ()

    monkeypatch.setattr(
        repository_service.erlang_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/cowboy.erl": "src/cowboy.erl"}

    result = repository_service._parse_erlang_dependencies_only(
        "src/main.erl",
        "-import(cowboy, [start/0]).",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/main.erl"
    assert observed["text"] == "-import(cowboy, [start/0])."
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module"] is repository_service._resolve_erlang_module
    assert observed["resolve_include"] is repository_service._resolve_erlang_include


def test_repository_intelligence_erlang_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module: Any,
        resolve_include: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module"] = resolve_module
        observed["resolve_include"] = resolve_include
        return (), (), ()

    monkeypatch.setattr(repository_service.erlang_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/cowboy.erl": "src/cowboy.erl"}

    result = repository_service._parse_erlang_file(
        "src/main.erl",
        "-import(cowboy, [start/0]).",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/main.erl"
    assert observed["text"] == "-import(cowboy, [start/0])."
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module"] is repository_service._resolve_erlang_module
    assert observed["resolve_include"] is repository_service._resolve_erlang_include


def test_repository_intelligence_swift_helpers_are_modularized() -> None:
    assert repository_service._SWIFT_IMPORT_RE is repository_service.swift_adapter.IMPORT_RE
    assert repository_service._SWIFT_TYPE_DECL_RE is repository_service.swift_adapter.TYPE_DECL_RE
    assert repository_service._SWIFT_TYPE_REFERENCE_RE is (
        repository_service.swift_adapter.TYPE_REFERENCE_RE
    )


def test_repository_intelligence_swift_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        import_target: str,
        module_index: dict[str, str],
        *,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "Sources/Acme/Command.swift"

    monkeypatch.setattr(repository_service.swift_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"Sources/Acme/Command.swift": "Sources/Acme/Command.swift"}

    result = repository_service._resolve_swift_import("ArgumentParser", module_index)

    assert result == "Sources/Acme/Command.swift"
    assert observed["import_target"] == "ArgumentParser"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_swift_same_target_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_same_target_reference(
        *,
        current_file: str,
        type_name: str,
        module_index: dict[str, str],
        module_index_values: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["type_name"] = type_name
        observed["module_index"] = module_index
        observed["module_index_values"] = module_index_values
        return "Sources/Acme/CommandConfiguration.swift"

    monkeypatch.setattr(
        repository_service.swift_adapter,
        "resolve_same_target_reference",
        _fake_resolve_same_target_reference,
    )

    module_index = {
        "Sources/Acme/CommandConfiguration.swift": "Sources/Acme/CommandConfiguration.swift"
    }

    result = repository_service._resolve_swift_same_target_reference(
        current_file="Sources/Acme/ParsableCommand.swift",
        type_name="CommandConfiguration",
        module_index=module_index,
    )

    assert result == "Sources/Acme/CommandConfiguration.swift"
    assert observed["current_file"] == "Sources/Acme/ParsableCommand.swift"
    assert observed["type_name"] == "CommandConfiguration"
    assert observed["module_index"] is module_index
    assert observed["module_index_values"] is repository_service._module_index_values


def test_repository_intelligence_swift_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
        resolve_same_target_reference: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        observed["resolve_same_target_reference"] = resolve_same_target_reference
        return ()

    monkeypatch.setattr(
        repository_service.swift_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"Sources/Acme/Command.swift": "Sources/Acme/Command.swift"}

    result = repository_service._parse_swift_dependencies_only(
        "Sources/Acme/App.swift",
        "import ArgumentParser",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "Sources/Acme/App.swift"
    assert observed["text"] == "import ArgumentParser"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_swift_import
    assert observed["resolve_same_target_reference"] is (
        repository_service._resolve_swift_same_target_reference
    )


def test_repository_intelligence_swift_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        collect_type_symbol_entries: Any,
        stable_identifier: Any,
        resolve_import: Any,
        resolve_same_target_reference: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["collect_type_symbol_entries"] = collect_type_symbol_entries
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        observed["resolve_same_target_reference"] = resolve_same_target_reference
        return (), (), ()

    monkeypatch.setattr(repository_service.swift_adapter, "parse_file", _fake_parse_file)

    module_index = {"Sources/Acme/Command.swift": "Sources/Acme/Command.swift"}

    result = repository_service._parse_swift_file(
        "Sources/Acme/App.swift",
        "struct App {}",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "Sources/Acme/App.swift"
    assert observed["text"] == "struct App {}"
    assert observed["module_index"] is module_index
    assert observed["collect_type_symbol_entries"] is repository_service._collect_type_symbol_entries
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_swift_import
    assert observed["resolve_same_target_reference"] is (
        repository_service._resolve_swift_same_target_reference
    )


def test_repository_intelligence_csharp_helpers_are_modularized() -> None:
    assert repository_service._CSHARP_USING_RE is repository_service.csharp_adapter.USING_RE
    assert repository_service._CSHARP_NAMESPACE_RE is repository_service.csharp_adapter.NAMESPACE_RE
    assert repository_service._CSHARP_TYPE_DECL_RE is repository_service.csharp_adapter.TYPE_DECL_RE
    assert repository_service._CSHARP_TYPE_REFERENCE_RE is (
        repository_service.csharp_adapter.TYPE_REFERENCE_RE
    )


def test_repository_intelligence_csharp_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        import_target: str,
        module_index: dict[str, str],
        *,
        resolve_suffix_match: Any,
        resolve_directory_prefix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["resolve_directory_prefix_match"] = resolve_directory_prefix_match
        return "src/Acme/Widget.cs"

    monkeypatch.setattr(repository_service.csharp_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._resolve_csharp_import("Acme.Widget", module_index)

    assert result == "src/Acme/Widget.cs"
    assert observed["import_target"] == "Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match
    assert observed["resolve_directory_prefix_match"] is (
        repository_service._resolve_directory_prefix_match
    )


def test_repository_intelligence_csharp_resolve_for_file_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import_for_file(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        resolve_import: Any,
        normalize_repository_relative_path: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_import"] = resolve_import
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return "src/Acme/Widget.cs"

    monkeypatch.setattr(
        repository_service.csharp_adapter,
        "resolve_import_for_file",
        _fake_resolve_import_for_file,
    )

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._resolve_csharp_import_for_file(
        current_file="src/Acme/App.cs",
        import_target="Acme.Widget",
        module_index=module_index,
    )

    assert result == "src/Acme/Widget.cs"
    assert observed["current_file"] == "src/Acme/App.cs"
    assert observed["import_target"] == "Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["resolve_import"] is repository_service._resolve_csharp_import
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_csharp_same_namespace_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_same_namespace_reference(
        *,
        current_file: str,
        current_namespace: str,
        type_name: str,
        module_index: dict[str, str],
        resolve_import: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["current_namespace"] = current_namespace
        observed["type_name"] = type_name
        observed["module_index"] = module_index
        observed["resolve_import"] = resolve_import
        return "src/Acme/Widget.cs"

    monkeypatch.setattr(
        repository_service.csharp_adapter,
        "resolve_same_namespace_reference",
        _fake_resolve_same_namespace_reference,
    )

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._resolve_csharp_same_namespace_reference(
        current_file="src/Acme/App.cs",
        current_namespace="Acme",
        type_name="Widget",
        module_index=module_index,
    )

    assert result == "src/Acme/Widget.cs"
    assert observed["current_file"] == "src/Acme/App.cs"
    assert observed["current_namespace"] == "Acme"
    assert observed["type_name"] == "Widget"
    assert observed["module_index"] is module_index
    assert observed["resolve_import"] is repository_service._resolve_csharp_import


def test_repository_intelligence_csharp_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import_for_file: Any,
    ) -> tuple[tuple[Any, ...], dict[str, Any], str]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import_for_file"] = resolve_import_for_file
        return (), {}, "Acme"

    monkeypatch.setattr(
        repository_service.csharp_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._extract_csharp_import_bindings(
        "src/Acme/App.cs",
        "using Acme.Widget;",
        module_index,
    )

    assert result == ((), {}, "Acme")
    assert observed["file_path"] == "src/Acme/App.cs"
    assert observed["text"] == "using Acme.Widget;"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import_for_file"] is repository_service._resolve_csharp_import_for_file


def test_repository_intelligence_csharp_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        collect_type_symbol_entries: Any,
        stable_identifier: Any,
        extract_import_bindings: Any,
        resolve_same_namespace_reference: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["collect_type_symbol_entries"] = collect_type_symbol_entries
        observed["stable_identifier"] = stable_identifier
        observed["extract_import_bindings"] = extract_import_bindings
        observed["resolve_same_namespace_reference"] = resolve_same_namespace_reference
        return ()

    monkeypatch.setattr(
        repository_service.csharp_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._parse_csharp_dependencies_only(
        "src/Acme/App.cs",
        "using Acme.Widget;",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/Acme/App.cs"
    assert observed["text"] == "using Acme.Widget;"
    assert observed["module_index"] is module_index
    assert observed["collect_type_symbol_entries"] is repository_service._collect_type_symbol_entries
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["extract_import_bindings"] is repository_service._extract_csharp_import_bindings
    assert observed["resolve_same_namespace_reference"] is (
        repository_service._resolve_csharp_same_namespace_reference
    )


def test_repository_intelligence_csharp_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        collect_type_symbol_entries: Any,
        stable_identifier: Any,
        extract_import_bindings: Any,
        resolve_same_namespace_reference: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["collect_type_symbol_entries"] = collect_type_symbol_entries
        observed["stable_identifier"] = stable_identifier
        observed["extract_import_bindings"] = extract_import_bindings
        observed["resolve_same_namespace_reference"] = resolve_same_namespace_reference
        return (), (), ()

    monkeypatch.setattr(repository_service.csharp_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._parse_csharp_file(
        "src/Acme/App.cs",
        "namespace Acme;",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/Acme/App.cs"
    assert observed["text"] == "namespace Acme;"
    assert observed["module_index"] is module_index
    assert observed["collect_type_symbol_entries"] is repository_service._collect_type_symbol_entries
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["extract_import_bindings"] is repository_service._extract_csharp_import_bindings
    assert observed["resolve_same_namespace_reference"] is (
        repository_service._resolve_csharp_same_namespace_reference
    )


def test_repository_intelligence_python_helpers_are_modularized() -> None:
    assert repository_service.python_adapter.ast_to_module_parts("src/app/main.py") == (
        "src",
        "app",
    )
    assert not hasattr(repository_service, "ast")


def test_repository_intelligence_python_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        current_file: str,
        module: str | None,
        level: int,
        name: str | None,
        module_index: dict[str, str],
    ) -> str | None:
        observed["current_file"] = current_file
        observed["module"] = module
        observed["level"] = level
        observed["name"] = name
        observed["module_index"] = module_index
        return "src/app/helpers.py"

    monkeypatch.setattr(repository_service.python_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"app.helpers": "src/app/helpers.py"}

    result = repository_service._resolve_python_import(
        current_file="src/app/api.py",
        module="app",
        level=0,
        name="helpers",
        module_index=module_index,
    )

    assert result == "src/app/helpers.py"
    assert observed["current_file"] == "src/app/api.py"
    assert observed["module"] == "app"
    assert observed["level"] == 0
    assert observed["name"] == "helpers"
    assert observed["module_index"] is module_index


def test_repository_intelligence_python_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.python_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"app.helpers": "src/app/helpers.py"}

    result = repository_service._parse_python_dependencies_only(
        "src/app/api.py",
        "from app import helpers",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/app/api.py"
    assert observed["text"] == "from app import helpers"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_python_import


def test_repository_intelligence_python_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.python_adapter, "parse_file", _fake_parse_file)

    module_index = {"app.helpers": "src/app/helpers.py"}

    result = repository_service._parse_python_file(
        "src/app/api.py",
        "def handler():\n    return helpers.run()",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/app/api.py"
    assert observed["text"] == "def handler():\n    return helpers.run()"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_python_import


def test_repository_intelligence_rust_helpers_are_modularized() -> None:
    assert repository_service._RUST_USE_RE is repository_service.rust_adapter.USE_RE
    assert repository_service._RUST_MOD_RE is repository_service.rust_adapter.MOD_RE
    assert repository_service._RUST_SYMBOL_LINE_RE is repository_service.rust_adapter.SYMBOL_LINE_RE
    assert repository_service._RUST_CALL_RE is repository_service.rust_adapter.CALL_RE


def test_repository_intelligence_rust_resolve_module_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_module_path(
        *,
        current_file: str,
        module_path: str,
        module_index: dict[str, str],
    ) -> str | None:
        observed["current_file"] = current_file
        observed["module_path"] = module_path
        observed["module_index"] = module_index
        return "src/lib.rs"

    monkeypatch.setattr(
        repository_service.rust_adapter,
        "resolve_module_path",
        _fake_resolve_module_path,
    )

    module_index = {"crate": "src/lib.rs"}

    result = repository_service._resolve_rust_module_path(
        current_file="src/main.rs",
        module_path="crate::util",
        module_index=module_index,
    )

    assert result == "src/lib.rs"
    assert observed["current_file"] == "src/main.rs"
    assert observed["module_path"] == "crate::util"
    assert observed["module_index"] is module_index


def test_repository_intelligence_rust_resolve_child_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_child_module(
        *,
        current_file: str,
        module_name: str,
        module_index: dict[str, str],
    ) -> str | None:
        observed["current_file"] = current_file
        observed["module_name"] = module_name
        observed["module_index"] = module_index
        return "src/util/mod.rs"

    monkeypatch.setattr(
        repository_service.rust_adapter,
        "resolve_child_module",
        _fake_resolve_child_module,
    )

    module_index = {"src/util": "src/util/mod.rs"}

    result = repository_service._resolve_rust_child_module(
        current_file="src/main.rs",
        module_name="util",
        module_index=module_index,
    )

    assert result == "src/util/mod.rs"
    assert observed["current_file"] == "src/main.rs"
    assert observed["module_name"] == "util"
    assert observed["module_index"] is module_index


def test_repository_intelligence_rust_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module_path: Any,
        resolve_child_module: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module_path"] = resolve_module_path
        observed["resolve_child_module"] = resolve_child_module
        return ()

    monkeypatch.setattr(
        repository_service.rust_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"crate": "src/lib.rs"}

    result = repository_service._parse_rust_dependencies_only(
        "src/main.rs",
        "use crate::util;",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/main.rs"
    assert observed["text"] == "use crate::util;"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module_path"] is repository_service._resolve_rust_module_path
    assert observed["resolve_child_module"] is repository_service._resolve_rust_child_module


def test_repository_intelligence_rust_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module_path: Any,
        resolve_child_module: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module_path"] = resolve_module_path
        observed["resolve_child_module"] = resolve_child_module
        return (), (), ()

    monkeypatch.setattr(repository_service.rust_adapter, "parse_file", _fake_parse_file)

    module_index = {"crate": "src/lib.rs"}

    result = repository_service._parse_rust_file(
        "src/main.rs",
        "fn run() { helper(); }",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/main.rs"
    assert observed["text"] == "fn run() { helper(); }"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module_path"] is repository_service._resolve_rust_module_path
    assert observed["resolve_child_module"] is repository_service._resolve_rust_child_module


def test_repository_intelligence_go_helpers_are_modularized() -> None:
    assert repository_service._GO_FUNC_DECL_RE is repository_service.go_adapter.FUNC_DECL_RE
    assert repository_service._GO_TYPE_DECL_RE is repository_service.go_adapter.TYPE_DECL_RE
    assert repository_service._GO_IMPORT_SPEC_RE is repository_service.go_adapter.IMPORT_SPEC_RE
    assert repository_service._GO_PACKAGE_RE is repository_service.go_adapter.PACKAGE_RE
    assert repository_service._GO_SELECTOR_CALL_RE is repository_service.go_adapter.SELECTOR_CALL_RE
    assert repository_service._GO_CALL_RE is repository_service.go_adapter.CALL_RE
    assert repository_service._GO_BUILTIN_CALL_NAMES is (
        repository_service.go_adapter.BUILTIN_CALL_NAMES
    )


def test_repository_intelligence_go_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        import_target: str,
        module_index: dict[str, str],
        workspace_go_module_index: dict[str, tuple[str, ...]],
        normalize_repository_relative_path: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["workspace_go_module_index"] = workspace_go_module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return "internal/service/service.go"

    monkeypatch.setattr(repository_service.go_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"github.com/acme/service": "internal/service/service.go"}
    workspace_go_module_index = {"github.com/acme": ("internal",)}

    result = repository_service._resolve_go_import(
        import_target="github.com/acme/service",
        module_index=module_index,
        workspace_go_module_index=workspace_go_module_index,
    )

    assert result == "internal/service/service.go"
    assert observed["import_target"] == "github.com/acme/service"
    assert observed["module_index"] is module_index
    assert observed["workspace_go_module_index"] is workspace_go_module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_go_package_alias_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_package_symbol_alias(
        *,
        file_path: str,
        package_name: str,
        symbol_name: str,
        normalize_repository_relative_path: Any,
    ) -> str:
        observed["file_path"] = file_path
        observed["package_name"] = package_name
        observed["symbol_name"] = symbol_name
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return "go::internal/service::service::Run"

    monkeypatch.setattr(
        repository_service.go_adapter,
        "package_symbol_alias",
        _fake_package_symbol_alias,
    )

    result = repository_service._go_package_symbol_alias(
        file_path="internal/service/service.go",
        package_name="service",
        symbol_name="Run",
    )

    assert result == "go::internal/service::service::Run"
    assert observed["file_path"] == "internal/service/service.go"
    assert observed["package_name"] == "service"
    assert observed["symbol_name"] == "Run"
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_go_module_index_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extend_module_index_with_package_symbol_aliases(
        *,
        root_path: Path,
        file_paths: Sequence[str],
        index: dict[str, str],
        normalize_repository_relative_path: Any,
        is_test_path: Any,
    ) -> None:
        observed["root_path"] = root_path
        observed["file_paths"] = file_paths
        observed["index"] = index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["is_test_path"] = is_test_path

    monkeypatch.setattr(
        repository_service.go_adapter,
        "extend_module_index_with_package_symbol_aliases",
        _fake_extend_module_index_with_package_symbol_aliases,
    )

    index: dict[str, str] = {}
    file_paths = ("internal/service/service.go",)

    repository_service._extend_module_index_with_go_package_symbol_aliases(
        root_path=tmp_path,
        file_paths=file_paths,
        index=index,
    )

    assert observed["root_path"] == tmp_path
    assert observed["file_paths"] == file_paths
    assert observed["index"] is index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["is_test_path"] is repository_service._is_test_path


def test_repository_intelligence_go_augment_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_augment_package_symbol_references(
        *,
        analyses: Sequence[Any],
        stable_identifier: Any,
        prefer_non_test_package_candidates: Any,
        best_package_symbol_target: Any,
        normalize_repository_relative_path: Any,
    ) -> list[Any]:
        observed["analyses"] = analyses
        observed["stable_identifier"] = stable_identifier
        observed["prefer_non_test_package_candidates"] = prefer_non_test_package_candidates
        observed["best_package_symbol_target"] = best_package_symbol_target
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return list(analyses)

    monkeypatch.setattr(
        repository_service.go_adapter,
        "augment_package_symbol_references",
        _fake_augment_package_symbol_references,
    )

    analyses: Sequence[Any] = ()

    result = repository_service._augment_go_package_symbol_references(analyses=analyses)

    assert result == []
    assert observed["analyses"] == analyses
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["prefer_non_test_package_candidates"] is (
        repository_service._prefer_non_test_package_candidates
    )
    assert observed["best_package_symbol_target"] is repository_service._best_package_symbol_target
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_go_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        workspace_go_module_index: dict[str, tuple[str, ...]],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["workspace_go_module_index"] = workspace_go_module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return ()

    monkeypatch.setattr(
        repository_service.go_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"github.com/acme/service": "internal/service/service.go"}
    workspace_go_module_index = {"github.com/acme": ("internal",)}

    result = repository_service._parse_go_dependencies_only(
        "internal/service/service.go",
        'import "github.com/acme/service"',
        module_index,
        workspace_go_module_index,
    )

    assert result == ()
    assert observed["file_path"] == "internal/service/service.go"
    assert observed["text"] == 'import "github.com/acme/service"'
    assert observed["module_index"] is module_index
    assert observed["workspace_go_module_index"] is workspace_go_module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_go_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        workspace_go_module_index: dict[str, tuple[str, ...]],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["workspace_go_module_index"] = workspace_go_module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return (), (), ()

    monkeypatch.setattr(repository_service.go_adapter, "parse_file", _fake_parse_file)

    module_index = {"github.com/acme/service": "internal/service/service.go"}
    workspace_go_module_index = {"github.com/acme": ("internal",)}

    result = repository_service._parse_go_file(
        "internal/service/service.go",
        "func Run() {}",
        module_index,
        workspace_go_module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "internal/service/service.go"
    assert observed["text"] == "func Run() {}"
    assert observed["module_index"] is module_index
    assert observed["workspace_go_module_index"] is workspace_go_module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_js_like_helpers_are_modularized() -> None:
    assert repository_service._JS_IMPORT_RE is repository_service.js_like_adapter.IMPORT_RE
    assert repository_service._JS_IMPORT_STATEMENT_RE is (
        repository_service.js_like_adapter.IMPORT_STATEMENT_RE
    )
    assert repository_service._JS_EXPORT_FROM_RE is repository_service.js_like_adapter.EXPORT_FROM_RE
    assert repository_service._JS_REQUIRE_ASSIGN_RE is (
        repository_service.js_like_adapter.REQUIRE_ASSIGN_RE
    )
    assert repository_service._JS_IDENTIFIER_RE is repository_service.js_like_adapter.IDENTIFIER_RE
    assert repository_service._JS_SYMBOL_RE is repository_service.js_like_adapter.SYMBOL_RE
    assert repository_service._JS_FUNCTION_DECL_RE is (
        repository_service.js_like_adapter.FUNCTION_DECL_RE
    )
    assert repository_service._JS_CLASS_DECL_RE is repository_service.js_like_adapter.CLASS_DECL_RE
    assert repository_service._JS_INTERFACE_DECL_RE is (
        repository_service.js_like_adapter.INTERFACE_DECL_RE
    )
    assert repository_service._JS_TYPE_DECL_RE is repository_service.js_like_adapter.TYPE_DECL_RE
    assert repository_service._JS_ARROW_ASSIGN_RE is (
        repository_service.js_like_adapter.ARROW_ASSIGN_RE
    )
    assert repository_service._JS_FUNCTION_ASSIGN_RE is (
        repository_service.js_like_adapter.FUNCTION_ASSIGN_RE
    )
    assert repository_service._JS_CLASS_ASSIGN_RE is (
        repository_service.js_like_adapter.CLASS_ASSIGN_RE
    )
    assert repository_service._JS_CONST_DECL_RE is repository_service.js_like_adapter.CONST_DECL_RE
    assert repository_service._JS_METHOD_DECL_RE is (
        repository_service.js_like_adapter.METHOD_DECL_RE
    )
    assert repository_service._JS_CLASS_FIELD_ARROW_RE is (
        repository_service.js_like_adapter.CLASS_FIELD_ARROW_RE
    )
    assert repository_service._sanitize_js_like_line is (
        repository_service.js_like_adapter.sanitize_line
    )
    assert repository_service._match_js_like_symbol is (
        repository_service.js_like_adapter.match_symbol
    )
    assert repository_service._normalize_js_like_binding_name is (
        repository_service.js_like_adapter.normalize_binding_name
    )
    assert repository_service._parse_js_like_named_binding is (
        repository_service.js_like_adapter.parse_named_binding
    )
    assert repository_service._bindings_from_js_like_import_clause is (
        repository_service.js_like_adapter.bindings_from_import_clause
    )
    assert repository_service._iter_js_like_dependency_specs is (
        repository_service.js_like_adapter.iter_dependency_specs
    )
    assert repository_service._compile_js_like_reference_pattern is (
        repository_service.js_like_adapter.compile_reference_pattern
    )
    assert repository_service._js_like_symbol_reference_present is (
        repository_service.js_like_adapter.symbol_reference_present
    )
    assert repository_service._build_js_like_symbol_reference_candidates is (
        repository_service.js_like_adapter.build_symbol_reference_candidates
    )


def test_repository_intelligence_js_like_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        workspace_package_index: dict[str, tuple[str, ...]],
        *,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["workspace_package_index"] = workspace_package_index
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.js_like_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"./util": "src/util.ts"}
    workspace_package_index = {"pkg": ("src",)}

    result = repository_service._extract_js_like_import_bindings(
        file_path="src/app.ts",
        text="import { run } from './util';",
        module_index=module_index,
        workspace_package_index=workspace_package_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/app.ts"
    assert observed["text"] == "import { run } from './util';"
    assert observed["module_index"] is module_index
    assert observed["workspace_package_index"] is workspace_package_index
    assert observed["resolve_import"] is repository_service._resolve_js_like_import


def test_repository_intelligence_js_like_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        workspace_package_index: dict[str, tuple[str, ...]],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["workspace_package_index"] = workspace_package_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.js_like_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"./util": "src/util.ts"}
    workspace_package_index = {"pkg": ("src",)}

    result = repository_service._parse_js_like_dependencies_only(
        "src/app.ts",
        "import { run } from './util';",
        module_index,
        workspace_package_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/app.ts"
    assert observed["text"] == "import { run } from './util';"
    assert observed["module_index"] is module_index
    assert observed["workspace_package_index"] is workspace_package_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_js_like_import


def test_repository_intelligence_js_like_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        workspace_package_index: dict[str, tuple[str, ...]],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["workspace_package_index"] = workspace_package_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.js_like_adapter, "parse_file", _fake_parse_file)

    module_index = {"./util": "src/util.ts"}
    workspace_package_index = {"pkg": ("src",)}

    result = repository_service._parse_js_like_file(
        "src/app.ts",
        "export function run() {}",
        module_index,
        workspace_package_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/app.ts"
    assert observed["text"] == "export function run() {}"
    assert observed["module_index"] is module_index
    assert observed["workspace_package_index"] is workspace_package_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_js_like_import


def test_repository_intelligence_dart_helpers_are_modularized() -> None:
    assert repository_service._DART_IMPORT_DIRECTIVE_RE is (
        repository_service.dart_adapter.IMPORT_DIRECTIVE_RE
    )
    assert repository_service._DART_IMPORT_ALIAS_RE is (
        repository_service.dart_adapter.IMPORT_ALIAS_RE
    )
    assert repository_service._DART_IMPORT_SHOW_RE is repository_service.dart_adapter.IMPORT_SHOW_RE
    assert repository_service._DART_TYPE_DECL_RE is repository_service.dart_adapter.TYPE_DECL_RE
    assert repository_service._DART_EXTENSION_DECL_RE is (
        repository_service.dart_adapter.EXTENSION_DECL_RE
    )
    assert repository_service._DART_TYPEDEF_DECL_RE is (
        repository_service.dart_adapter.TYPEDEF_DECL_RE
    )
    assert repository_service._DART_TOP_LEVEL_FUNCTION_RE is (
        repository_service.dart_adapter.TOP_LEVEL_FUNCTION_RE
    )
    assert repository_service._DART_METHOD_DECL_RE is (
        repository_service.dart_adapter.METHOD_DECL_RE
    )
    assert repository_service._DART_SELECTOR_REFERENCE_RE is (
        repository_service.dart_adapter.SELECTOR_REFERENCE_RE
    )
    assert repository_service._DART_RESERVED_SYMBOL_NAMES is (
        repository_service.dart_adapter.RESERVED_SYMBOL_NAMES
    )
    assert repository_service._match_dart_symbol is repository_service.dart_adapter.match_symbol
    assert repository_service._iter_dart_import_directives is (
        repository_service.dart_adapter.iter_import_directives
    )


def test_repository_intelligence_dart_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), {}

    monkeypatch.setattr(
        repository_service.dart_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"package:acme/util.dart": "lib/src/util.dart"}

    result = repository_service._extract_dart_import_bindings(
        "lib/acme.dart",
        "import 'package:acme/util.dart' show Helper;",
        module_index,
    )

    assert result == ((), {})
    assert observed["file_path"] == "lib/acme.dart"
    assert observed["text"] == "import 'package:acme/util.dart' show Helper;"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_dart_import


def test_repository_intelligence_dart_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.dart_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"package:acme/util.dart": "lib/src/util.dart"}

    result = repository_service._parse_dart_dependencies_only(
        "lib/acme.dart",
        "import 'package:acme/util.dart' show Helper;",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "lib/acme.dart"
    assert observed["text"] == "import 'package:acme/util.dart' show Helper;"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_dart_import


def test_repository_intelligence_dart_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.dart_adapter, "parse_file", _fake_parse_file)

    module_index = {"package:acme/util.dart": "lib/src/util.dart"}

    result = repository_service._parse_dart_file(
        "lib/acme.dart",
        "class Helper {}",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "lib/acme.dart"
    assert observed["text"] == "class Helper {}"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_dart_import


def test_repository_intelligence_c_family_helpers_are_modularized() -> None:
    assert repository_service._C_FAMILY_INCLUDE_RE is repository_service.c_family_adapter.INCLUDE_RE
    assert repository_service._C_FAMILY_ATTRIBUTE_RE is (
        repository_service.c_family_adapter.ATTRIBUTE_RE
    )
    assert repository_service._C_FAMILY_TYPE_DECL_RE is (
        repository_service.c_family_adapter.TYPE_DECL_RE
    )
    assert repository_service._C_FAMILY_FUNCTION_DECL_RE is (
        repository_service.c_family_adapter.FUNCTION_DECL_RE
    )
    assert repository_service._C_FAMILY_SCOPED_REFERENCE_RE is (
        repository_service.c_family_adapter.SCOPED_REFERENCE_RE
    )
    assert repository_service._C_FAMILY_CALL_RE is repository_service.c_family_adapter.CALL_RE
    assert repository_service._C_FAMILY_NON_OPERATIONAL_REFERENCE_NAMES is (
        repository_service.c_family_adapter.NON_OPERATIONAL_REFERENCE_NAMES
    )
    assert repository_service._C_FAMILY_DECLARATION_PREFIX_KEYWORDS is (
        repository_service.c_family_adapter.DECLARATION_PREFIX_KEYWORDS
    )
    assert repository_service._strip_c_family_comments is (
        repository_service.c_family_adapter.strip_comments
    )
    assert repository_service._strip_c_family_attributes is (
        repository_service.c_family_adapter.strip_attributes
    )
    assert repository_service._normalize_c_family_symbol_name is (
        repository_service.c_family_adapter.normalize_symbol_name
    )
    assert repository_service._is_c_family_macro_like_symbol_name is (
        repository_service.c_family_adapter.is_macro_like_symbol_name
    )
    assert repository_service._is_c_family_operational_reference_name is (
        repository_service.c_family_adapter.is_operational_reference_name
    )


def test_repository_intelligence_c_family_candidate_keys_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_candidate_module_keys(
        base_path: str,
        *,
        normalize_repository_relative_path: Any,
    ) -> tuple[str, ...]:
        observed["base_path"] = base_path
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return ("include/widget.hpp", "include/widget")

    monkeypatch.setattr(
        repository_service.c_family_adapter,
        "candidate_module_keys",
        _fake_candidate_module_keys,
    )

    result = repository_service._candidate_c_family_module_keys("include/widget.hpp")

    assert result == ("include/widget.hpp", "include/widget")
    assert observed["base_path"] == "include/widget.hpp"
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_c_family_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_include(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "include/widget.hpp"

    monkeypatch.setattr(
        repository_service.c_family_adapter,
        "resolve_include",
        _fake_resolve_include,
    )

    module_index = {"widget.hpp": "include/widget.hpp"}

    result = repository_service._resolve_c_family_include(
        current_file="src/main.cpp",
        import_target="widget.hpp",
        module_index=module_index,
    )

    assert result == "include/widget.hpp"
    assert observed["current_file"] == "src/main.cpp"
    assert observed["import_target"] == "widget.hpp"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_resolve_c_family_include_uses_keyword_only_suffix_match_helper() -> None:
    module_index = {"include/widget.hpp": "include/widget.hpp"}

    resolved = repository_service._resolve_c_family_include(
        current_file="src/main.cpp",
        import_target="widget.hpp",
        module_index=module_index,
    )

    assert resolved == "include/widget.hpp"


def test_repository_intelligence_c_family_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_include: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_include"] = resolve_include
        return ()

    monkeypatch.setattr(
        repository_service.c_family_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"widget.hpp": "include/widget.hpp"}

    result = repository_service._parse_c_family_dependencies_only(
        "src/main.cpp",
        '#include "widget.hpp"\n',
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/main.cpp"
    assert observed["text"] == '#include "widget.hpp"\n'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_include"] is repository_service._resolve_c_family_include


def test_repository_intelligence_c_family_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_include: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_include"] = resolve_include
        return (), (), ()

    monkeypatch.setattr(repository_service.c_family_adapter, "parse_file", _fake_parse_file)

    module_index = {"widget.hpp": "include/widget.hpp"}

    result = repository_service._parse_c_family_file(
        "src/main.cpp",
        "int run() { return helper(); }",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/main.cpp"
    assert observed["text"] == "int run() { return helper(); }"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_include"] is repository_service._resolve_c_family_include


def test_repository_intelligence_zig_helpers_are_modularized() -> None:
    assert repository_service._ZIG_IMPORT_RE is repository_service.zig_adapter.IMPORT_RE
    assert repository_service._ZIG_IMPORT_BINDING_RE is (
        repository_service.zig_adapter.IMPORT_BINDING_RE
    )
    assert repository_service._ZIG_TOP_LEVEL_CONST_RE is (
        repository_service.zig_adapter.TOP_LEVEL_CONST_RE
    )
    assert repository_service._ZIG_TOP_LEVEL_FUNCTION_RE is (
        repository_service.zig_adapter.TOP_LEVEL_FUNCTION_RE
    )
    assert repository_service._ZIG_SELECTOR_REFERENCE_RE is (
        repository_service.zig_adapter.SELECTOR_REFERENCE_RE
    )


def test_repository_intelligence_zig_candidate_keys_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_candidate_module_keys(
        current_file: str,
        import_target: str,
        *,
        normalize_repository_relative_path: Any,
    ) -> tuple[str, ...]:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return ("src/root.zig",)

    monkeypatch.setattr(
        repository_service.zig_adapter,
        "candidate_module_keys",
        _fake_candidate_module_keys,
    )

    result = repository_service._candidate_zig_module_keys("src/main.zig", "root")

    assert result == ("src/root.zig",)
    assert observed["current_file"] == "src/main.zig"
    assert observed["import_target"] == "root"
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_zig_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return "src/root.zig"

    monkeypatch.setattr(repository_service.zig_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"root": "src/root.zig"}

    result = repository_service._resolve_zig_import(
        current_file="src/main.zig",
        import_target="root",
        module_index=module_index,
    )

    assert result == "src/root.zig"
    assert observed["current_file"] == "src/main.zig"
    assert observed["import_target"] == "root"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_zig_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), {}

    monkeypatch.setattr(
        repository_service.zig_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"root": "src/root.zig"}

    result = repository_service._extract_zig_import_bindings(
        "src/main.zig",
        'const root = @import("root");',
        module_index,
    )

    assert result == ((), {})
    assert observed["file_path"] == "src/main.zig"
    assert observed["text"] == 'const root = @import("root");'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_zig_import


def test_repository_intelligence_zig_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.zig_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"root": "src/root.zig"}

    result = repository_service._parse_zig_dependencies_only(
        "src/main.zig",
        'const root = @import("root");',
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/main.zig"
    assert observed["text"] == 'const root = @import("root");'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_zig_import


def test_repository_intelligence_zig_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.zig_adapter, "parse_file", _fake_parse_file)

    module_index = {"root": "src/root.zig"}

    result = repository_service._parse_zig_file(
        "src/main.zig",
        "pub fn main() void {}",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/main.zig"
    assert observed["text"] == "pub fn main() void {}"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_zig_import


def test_repository_intelligence_mojo_helpers_are_modularized() -> None:
    assert repository_service._MOJO_IMPORT_RE is repository_service.mojo_adapter.IMPORT_RE
    assert repository_service._MOJO_FROM_IMPORT_RE is (
        repository_service.mojo_adapter.FROM_IMPORT_RE
    )
    assert repository_service._MOJO_SYMBOL_RE is repository_service.mojo_adapter.SYMBOL_RE
    assert repository_service._MOJO_SELECTOR_CALL_RE is (
        repository_service.mojo_adapter.SELECTOR_CALL_RE
    )
    assert repository_service._MOJO_CALL_RE is repository_service.mojo_adapter.CALL_RE


def test_repository_intelligence_mojo_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(import_target: str, module_index: dict[str, str]) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        return "helper/util.mojo"

    monkeypatch.setattr(repository_service.mojo_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"helper.util": "helper/util.mojo"}

    result = repository_service._resolve_mojo_import("helper.util", module_index)

    assert result == "helper/util.mojo"
    assert observed["import_target"] == "helper.util"
    assert observed["module_index"] is module_index


def test_repository_intelligence_mojo_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), {}

    monkeypatch.setattr(
        repository_service.mojo_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"helper.util": "helper/util.mojo"}

    result = repository_service._extract_mojo_import_bindings(
        "main.mojo",
        "from helper.util import value",
        module_index,
    )

    assert result == ((), {})
    assert observed["file_path"] == "main.mojo"
    assert observed["text"] == "from helper.util import value"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_mojo_import


def test_repository_intelligence_mojo_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.mojo_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"helper.util": "helper/util.mojo"}

    result = repository_service._parse_mojo_dependencies_only(
        "main.mojo",
        "from helper.util import value",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "main.mojo"
    assert observed["text"] == "from helper.util import value"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_mojo_import


def test_repository_intelligence_mojo_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.mojo_adapter, "parse_file", _fake_parse_file)

    module_index = {"helper.util": "helper/util.mojo"}

    result = repository_service._parse_mojo_file(
        "main.mojo",
        "fn run():\n    value()",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "main.mojo"
    assert observed["text"] == "fn run():\n    value()"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_mojo_import


def test_repository_intelligence_jvm_helpers_are_modularized() -> None:
    assert repository_service._JVM_PACKAGE_RE is repository_service.jvm_adapter.PACKAGE_RE
    assert repository_service._JVM_IMPORT_RE is repository_service.jvm_adapter.IMPORT_RE
    assert repository_service._JVM_TYPE_DECL_RE is repository_service.jvm_adapter.TYPE_DECL_RE
    assert repository_service._JVM_TYPE_REFERENCE_RE is (
        repository_service.jvm_adapter.TYPE_REFERENCE_RE
    )
    assert repository_service._SCALA_PACKAGE_OBJECT_RE is (
        repository_service.jvm_adapter.SCALA_PACKAGE_OBJECT_RE
    )
    assert repository_service._SCALA_PACKAGE_RE is repository_service.jvm_adapter.SCALA_PACKAGE_RE
    assert repository_service._SCALA_IMPORT_RE is repository_service.jvm_adapter.SCALA_IMPORT_RE
    assert repository_service._SCALA_GROUPED_IMPORT_RE is (
        repository_service.jvm_adapter.SCALA_GROUPED_IMPORT_RE
    )
    assert repository_service._SCALA_TYPE_DECL_RE is (
        repository_service.jvm_adapter.SCALA_TYPE_DECL_RE
    )
    assert repository_service._scala_current_package is (
        repository_service.jvm_adapter.scala_current_package
    )
    assert repository_service._iter_scala_import_targets is (
        repository_service.jvm_adapter.iter_scala_import_targets
    )
    assert repository_service._scala_package_aliases_for_path is (
        repository_service.jvm_adapter.scala_package_aliases_for_path
    )
    assert repository_service._jvm_declared_type_aliases_for_path is (
        repository_service.jvm_adapter.declared_type_aliases_for_path
    )


def test_repository_intelligence_jvm_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        import_target: str,
        module_index: dict[str, str],
        *,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/main/java/org/example/Owner.java"

    monkeypatch.setattr(repository_service.jvm_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"org.example.Owner": "src/main/java/org/example/Owner.java"}

    result = repository_service._resolve_jvm_import("org.example.Owner", module_index)

    assert result == "src/main/java/org/example/Owner.java"
    assert observed["import_target"] == "org.example.Owner"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_jvm_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        language: str,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], dict[str, Any], str]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["language"] = language
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), {}, "org.example"

    monkeypatch.setattr(
        repository_service.jvm_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"org.example.Owner": "src/main/java/org/example/Owner.java"}

    result = repository_service._extract_jvm_import_bindings(
        "src/main/java/org/example/OwnerController.java",
        "import org.example.Owner;",
        module_index,
        language="java",
    )

    assert result == ((), {}, "org.example")
    assert observed["file_path"] == "src/main/java/org/example/OwnerController.java"
    assert observed["text"] == "import org.example.Owner;"
    assert observed["module_index"] is module_index
    assert observed["language"] == "java"
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_jvm_import


def test_repository_intelligence_jvm_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        language: str,
        collect_type_symbol_entries: Any,
        stable_identifier: Any,
        extract_import_bindings: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["language"] = language
        observed["collect_type_symbol_entries"] = collect_type_symbol_entries
        observed["stable_identifier"] = stable_identifier
        observed["extract_import_bindings"] = extract_import_bindings
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.jvm_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"org.example.Owner": "src/main/java/org/example/Owner.java"}

    result = repository_service._parse_jvm_dependencies_only(
        "src/main/java/org/example/OwnerController.java",
        "import org.example.Owner;",
        module_index,
        language="java",
    )

    assert result == ()
    assert observed["file_path"] == "src/main/java/org/example/OwnerController.java"
    assert observed["text"] == "import org.example.Owner;"
    assert observed["module_index"] is module_index
    assert observed["language"] == "java"
    assert observed["collect_type_symbol_entries"] is repository_service._collect_type_symbol_entries
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["extract_import_bindings"] is repository_service._extract_jvm_import_bindings
    assert observed["resolve_import"] is repository_service._resolve_jvm_import


def test_repository_intelligence_jvm_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        language: str,
        collect_type_symbol_entries: Any,
        stable_identifier: Any,
        extract_import_bindings: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["language"] = language
        observed["collect_type_symbol_entries"] = collect_type_symbol_entries
        observed["stable_identifier"] = stable_identifier
        observed["extract_import_bindings"] = extract_import_bindings
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.jvm_adapter, "parse_file", _fake_parse_file)

    module_index = {"org.example.Owner": "src/main/java/org/example/Owner.java"}

    result = repository_service._parse_jvm_file(
        "src/main/java/org/example/OwnerController.java",
        "class OwnerController {}",
        module_index,
        language="java",
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/main/java/org/example/OwnerController.java"
    assert observed["text"] == "class OwnerController {}"
    assert observed["module_index"] is module_index
    assert observed["language"] == "java"
    assert observed["collect_type_symbol_entries"] is repository_service._collect_type_symbol_entries
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["extract_import_bindings"] is repository_service._extract_jvm_import_bindings
    assert observed["resolve_import"] is repository_service._resolve_jvm_import


def test_repository_intelligence_julia_helpers_are_modularized() -> None:
    assert repository_service._JULIA_INCLUDE_RE is repository_service.julia_adapter.INCLUDE_RE
    assert repository_service._julia_project_name_from_text is (
        repository_service.julia_adapter.project_name_from_text
    )
    assert repository_service._is_julia_operational_reference_name is (
        repository_service.julia_adapter.is_operational_reference_name
    )


def test_repository_intelligence_julia_resolve_include_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_include(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/Helper.jl"

    monkeypatch.setattr(repository_service.julia_adapter, "resolve_include", _fake_resolve_include)

    module_index = {"src/Helper.jl": "src/Helper.jl"}

    result = repository_service._resolve_julia_include(
        current_file="src/Acme.jl",
        import_target="Helper.jl",
        module_index=module_index,
    )

    assert result == "src/Helper.jl"
    assert observed["current_file"] == "src/Acme.jl"
    assert observed["import_target"] == "Helper.jl"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_julia_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/Helper.jl"

    monkeypatch.setattr(repository_service.julia_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"src/Helper.jl": "src/Helper.jl"}

    result = repository_service._resolve_julia_import(
        current_file="src/Acme.jl",
        import_target=".Helper",
        module_index=module_index,
    )

    assert result == "src/Helper.jl"
    assert observed["current_file"] == "src/Acme.jl"
    assert observed["import_target"] == ".Helper"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_julia_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return ()

    monkeypatch.setattr(
        repository_service.julia_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/Helper.jl": "src/Helper.jl"}

    result = repository_service._parse_julia_dependencies_only(
        "src/Acme.jl",
        'include("Helper.jl")',
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/Acme.jl"
    assert observed["text"] == 'include("Helper.jl")'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_julia_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.julia_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/Helper.jl": "src/Helper.jl"}

    result = repository_service._parse_julia_file(
        "src/Acme.jl",
        'include("Helper.jl")',
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/Acme.jl"
    assert observed["text"] == 'include("Helper.jl")'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_nim_helpers_are_modularized() -> None:
    assert repository_service._NIM_IMPORT_LINE_RE is repository_service.nim_adapter.IMPORT_LINE_RE
    assert repository_service._is_nim_declared_symbol_alias is (
        repository_service.nim_adapter.is_declared_symbol_alias
    )
    assert repository_service._nim_module_aliases_for_path is (
        repository_service.nim_adapter.module_aliases_for_path
    )


def test_repository_intelligence_nim_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/acme/util.nim"

    monkeypatch.setattr(repository_service.nim_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"src/acme/util.nim": "src/acme/util.nim"}

    result = repository_service._resolve_nim_import(
        current_file="src/acme.nim",
        import_target="acme/util",
        module_index=module_index,
    )

    assert result == "src/acme/util.nim"
    assert observed["current_file"] == "src/acme.nim"
    assert observed["import_target"] == "acme/util"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_nim_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
        module_index_aliases_for_file: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["module_index_aliases_for_file"] = module_index_aliases_for_file
        return ()

    monkeypatch.setattr(
        repository_service.nim_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/acme/util.nim": "src/acme/util.nim"}

    result = repository_service._parse_nim_dependencies_only(
        "src/acme.nim",
        "import acme/util",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/acme.nim"
    assert observed["text"] == "import acme/util"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match
    assert observed["module_index_aliases_for_file"] is (
        repository_service._module_index_aliases_for_file
    )


def test_repository_intelligence_nim_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
        module_index_aliases_for_file: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["module_index_aliases_for_file"] = module_index_aliases_for_file
        return (), (), ()

    monkeypatch.setattr(repository_service.nim_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/acme/util.nim": "src/acme/util.nim"}

    result = repository_service._parse_nim_file(
        "src/acme.nim",
        "import acme/util",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/acme.nim"
    assert observed["text"] == "import acme/util"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match
    assert observed["module_index_aliases_for_file"] is (
        repository_service._module_index_aliases_for_file
    )


def test_resolve_ruby_import_uses_keyword_only_suffix_match_helper() -> None:
    module_index = {"src/acme/widget.rb": "src/acme/widget.rb"}

    resolved = repository_service._resolve_ruby_import(
        current_file="app/main.rb",
        import_target="acme/widget",
        is_relative=False,
        module_index=module_index,
    )

    assert resolved == "src/acme/widget.rb"


@pytest.mark.anyio
async def test_repository_intelligence_decision_plan_workflow_wrappers_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SimpleNamespace(id="repo-1", org_id="org-1")
    request = RepositoryDecisionPlanCreateRequest(
        workspace_evidence_bundle_ref="bundle-1",
        snapshot_id="snapshot-1",
    )
    result = object()
    observed: dict[str, dict[str, Any]] = {}

    async def _fake_create_repository_decision_plan(**kwargs: Any) -> object:
        observed["create"] = kwargs
        return result

    monkeypatch.setattr(
        repository_decision_plan_workflow,
        "create_repository_decision_plan",
        _fake_create_repository_decision_plan,
    )

    assert (
        await repository_service.create_repository_decision_plan(
            connector=connector,
            request=request,
        )
        is result
    )
    assert observed["create"]["connector"] is connector
    assert observed["create"]["request"] is request
    assert (
        observed["create"]["engine_revision"]
        == repository_service._REPOSITORY_INTELLIGENCE_ENGINE_REVISION
    )
    assert (
        observed["create"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert (
        observed["create"]["resolve_repository_model"] is repository_service._resolve_repository_model
    )
    assert observed["create"]["read_json"] is repository_service._read_json
    assert (
        observed["create"]["generate_repository_patch_plan"]
        is repository_service._generate_repository_patch_plan
    )
    assert (
        observed["create"]["validate_patch_against_snapshot"]
        is repository_service._validate_patch_against_snapshot
    )
    assert observed["create"]["patch_impact_summary"] is repository_service._patch_impact_summary


def test_language_for_path_keeps_supported_suffixes_explicit() -> None:
    assert repository_service._language_for_path(Path("src/main.c")) == "c"
    assert repository_service._language_for_path(Path("src/Application.cfc")) == "cfml"
    assert repository_service._language_for_path(Path("views/index.cfm")) == "cfml"
    assert repository_service._language_for_path(Path("src/main.php")) == "php"
    assert repository_service._language_for_path(Path("src/Main.elm")) == "elm"
    assert repository_service._language_for_path(Path("src/main.el")) == "emacslisp"
    assert repository_service._language_for_path(Path("functions/helper.fish")) == "fish"
    assert repository_service._language_for_path(Path("plugin/fugitive.vim")) == "unknown"
    assert repository_service._language_for_path(Path("src/Main.as")) == "actionscript"
    assert repository_service._language_for_path(Path("scripts/Main.ahk")) == "autohotkey"
    assert repository_service._language_for_path(Path("scripts/Main.au3")) == "autoit"
    assert repository_service._language_for_path(Path("Dockerfile")) == "dockerfile"
    assert repository_service._language_for_path(Path("Containerfile")) == "dockerfile"
    assert repository_service._language_for_path(Path("docker/build.Dockerfile")) == "dockerfile"
    assert repository_service._language_for_path(Path("src/main.cu")) == "cuda"
    assert repository_service._language_for_path(Path("include/math.cuh")) == "cuda"
    assert repository_service._language_for_path(Path("shaders/main.hlsl")) == "hlsl"
    assert repository_service._language_for_path(Path("shaders/common.hlsli")) == "hlsl"
    assert repository_service._language_for_path(Path("Shaders/Main.shader")) == "shaderlab"
    assert repository_service._language_for_path(Path("pkg/main.pyx")) == "cython"
    assert repository_service._language_for_path(Path("pkg/helpermod.pxd")) == "cython"
    assert repository_service._language_for_path(Path("pkg/defs.pxi")) == "cython"
    assert repository_service._language_for_path(Path("models/main.stan")) == "stan"
    assert repository_service._language_for_path(Path("tests/login.robot")) == "robotframework"
    assert repository_service._language_for_path(Path("resources/common.resource")) == "robotframework"
    assert repository_service._language_for_path(Path("styles/main.scss")) == "scss"
    assert repository_service._language_for_path(Path("docs/main.typ")) == "typst"
    assert repository_service._language_for_path(Path("scripts/vscripts/main.nut")) == "squirrel"
    assert repository_service._language_for_path(Path("lib/math.awk")) == "awk"
    assert repository_service._language_for_path(Path("src/main.coffee")) == "coffeescript"
    assert repository_service._language_for_path(Path("docs/demo.litcoffee")) == "coffeescript"
    assert repository_service._language_for_path(Path("src/main.vala")) == "vala"
    assert repository_service._language_for_path(Path("vapi/demo.vapi")) == "vala"
    assert repository_service._language_for_path(Path("Experts/Main.mq5")) == "mql5"
    assert repository_service._language_for_path(Path("Include/Helper.mqh")) == "mql5"
    assert repository_service._language_for_path(Path("MetaTrader/demo.mqproj")) == "mql5"
    assert repository_service._language_for_path(Path("models/main.gms")) == "gams"
    assert repository_service._language_for_path(Path("models/main.scad")) == "openscad"
    assert repository_service._language_for_path(Path("src/Main.purs")) == "purescript"
    assert repository_service._language_for_path(Path("src/main.gleam")) == "gleam"
    assert repository_service._language_for_path(Path("src/main.janet")) == "janet"
    assert repository_service._language_for_path(Path("src/Main.idr")) == "idris"
    assert repository_service._language_for_path(Path("demo.ipkg")) == "idris"
    assert repository_service._language_for_path(Path("lib/Demo/Helper.rakumod")) == "raku"
    assert repository_service._language_for_path(Path("bin/demo.raku")) == "raku"
    assert repository_service._language_for_path(Path("scripts/main.nu")) == "nushell"
    assert repository_service._language_for_path(Path("src/Main.hx")) == "haxe"
    assert repository_service._language_for_path(Path("src/Main.hack")) == "hack"
    assert repository_service._language_for_path(Path("build.hxml")) == "haxe"
    assert repository_service._language_for_path(Path("BUILD.bazel")) == "starlark"
    assert repository_service._language_for_path(Path("MODULE.bazel")) == "starlark"
    assert repository_service._language_for_path(Path("rules/demo.bzl")) == "starlark"
    assert repository_service._language_for_path(Path("flake.nix")) == "nix"
    assert repository_service._language_for_path(Path("nix/lib/formatter.nix")) == "nix"
    assert repository_service._language_for_path(Path("v.mod")) == "v"
    assert repository_service._language_for_path(Path("src/Demo-Core/package.st")) == "smalltalk"
    assert repository_service._language_for_path(Path("src/Demo-Core/Helper.class.st")) == "smalltalk"
    assert repository_service._language_for_path(Path("games/Maze.sb3")) == "scratch"
    assert (
        repository_service._language_for_path(
            Path("PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml")
        )
        == "xpp"
    )
    assert repository_service._language_for_path(Path("src/main.ex")) == "ex"
    assert repository_service._language_for_path(Path("src/main.cs")) == "cs"
    assert repository_service._language_for_path(Path("src/zcl_math.clas.abap")) == "abap"
    assert repository_service._language_for_path(Path("src/boot.asm")) == "assembly"
    assert repository_service._language_for_path(Path("src/main.prolog")) == "prolog"
    assert repository_service._language_for_path(Path("src/main.cbl")) == "cobol"
    assert repository_service._language_for_path(Path("db/order_api.pkb")) == "plsql"
    assert repository_service._language_for_path(Path("programs/report.sas")) == "sas"
    assert repository_service._language_for_path(Path("src/main.sml")) == "ml"
    assert repository_service._language_for_path(Path("src/core.sig")) == "ml"
    assert repository_service._language_for_path(Path("src/make.fun")) == "ml"
    assert repository_service._language_for_path(Path("logic/Main.L5X")) == "ladder"
    assert repository_service._language_for_path(Path("App.lvproj")) == "labview"
    assert repository_service._language_for_path(Path("Source/Main.vi")) == "labview"
    assert repository_service._language_for_path(Path("systems/acme.asd")) == "lisp"
    assert repository_service._language_for_path(Path("src/app.lisp")) == "lisp"
    assert repository_service._language_for_path(Path("src/app.lsp")) == "lisp"
    assert repository_service._language_for_path(Path("src/main.scm")) == "scheme"
    assert repository_service._language_for_path(Path("src/main.ss")) == "scheme"
    assert repository_service._language_for_path(Path("src/lib.sld")) == "scheme"
    assert repository_service._language_for_path(Path("src/program.sps")) == "scheme"
    assert repository_service._language_for_path(Path("src/main.rkt")) == "racket"
    assert repository_service._language_for_path(Path("src/lib.rktl")) == "racket"
    assert repository_service._language_for_path(Path("policy/main.rego")) == "rego"
    assert repository_service._language_for_path(Path("infra/main.tf")) == "hcl"
    assert repository_service._language_for_path(Path("metadata.json")) == "json"
    assert repository_service._language_for_path(Path("rules/index.yar")) == "yara"
    assert repository_service._language_for_path(Path("Kernel/Helpers.wl")) == "wolfram"
    assert repository_service._language_for_path(Path("Scripts/BuildPaclet.wls")) == "wolfram"
    assert repository_service._language_for_path(Path("scripts/main.tcl")) == "tcl"
    assert repository_service._language_for_path(Path("modules/sha1/sha1.tm")) == "tcl"
    assert repository_service._language_for_path(Path("rtl/top.sv")) == "systemverilog"
    assert repository_service._language_for_path(Path("rtl/defs.svh")) == "systemverilog"
    assert repository_service._language_for_path(Path("App/AcmeApp.dpr")) == "delphi"
    assert repository_service._language_for_path(Path("scripts/player.gd")) == "gdscript"
    assert repository_service._language_for_path(Path("rtl/top.vhd")) == "vhdl"
    assert repository_service._language_for_path(Path("rtl/pkg.vhdl")) == "vhdl"


def test_language_for_path_disambiguates_v_from_verilog_with_content() -> None:
    assert (
        repository_service._language_for_path(
            Path("src/main.v"),
            text="module main\n\nfn main() {\n}\n",
        )
        == "v"
    )
    assert (
        repository_service._language_for_path(
            Path("rtl/child.v"),
            text="module child;\n  reg ready;\nendmodule\n",
        )
        == "verilog"
    )
    assert (
        repository_service._language_for_path(
            Path("rtl/top.v"),
            text="module top(input logic clk);\nendmodule\n",
        )
        == "systemverilog"
    )
    assert repository_service._language_for_path(Path("database/Acme.sqlproj")) == "tsql"
    assert repository_service._language_for_path(Path("database/Acme.dbproj")) == "tsql"
    assert repository_service._language_for_path(Path("programs/main.prg")) == "unknown"
    assert repository_service._language_for_path(Path("src/module.bas")) == "unknown"
    assert repository_service._language_for_path(Path("src/main.kt")) == "kotlin"
    assert repository_service._language_for_path(Path("src/main.m")) == "unknown"
    assert repository_service._language_for_path(Path("ios/Renderer.mm")) == "objectivec"
    assert repository_service._language_for_path(Path("+acme/helper.m")) == "matlab"
    assert repository_service._language_for_path(Path("Kernel/init.m")) == "wolfram"
    assert (
        repository_service._language_for_path(
            Path("include/common.inc"),
            text="$include ../models/main.gms\nparameter demand(i);\n",
        )
        == "gams"
    )
    assert (
        repository_service._language_for_path(
            Path("parts/gear.scad"),
            text="include <lib/threads.scad>;\nmodule gear(teeth) { cylinder(r=teeth); }\n",
        )
        == "openscad"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.purs"),
            text="module Main where\n\nimport Prelude\n\nmain = unit\n",
        )
        == "purescript"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.agda"),
            text="module Main where\n\nopen import Data.Helper using (helper)\n",
        )
        == "agda"
    )
    assert (
        repository_service._language_for_path(
            Path("standard-library.agda-lib"),
            text="name: demo\ninclude: src\n",
        )
        == "agda"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.gleam"),
            text="import demo/helper.{render_json}\n\npub fn main() {\n  render_json()\n}\n",
        )
        == "gleam"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/main.nu"),
            text="source modules/helper.nu\nuse modules/helper.nu\n\ndef main [] {\n  render-json\n}\n",
        )
        == "nushell"
    )
    assert (
        repository_service._language_for_path(
            Path("terragrunt.hcl"),
            text='locals {\n  env = "prod"\n}\n',
        )
        == "hcl"
    )
    assert (
        repository_service._language_for_path(
            Path("policy/main.rego"),
            text="package policy.main\n\nimport data.policy.lib.helpers as helper\n\nallow if {\n  helper.render_json\n}\n",
        )
        == "rego"
    )
    assert (
        repository_service._language_for_path(
            Path("metadata.json"),
            text='{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        )
        == "puppet"
    )
    assert (
        repository_service._language_for_path(
            Path("Puppetfile"),
            text="mod 'puppetlabs-stdlib'\n",
        )
        == "puppet"
    )
    assert (
        repository_service._language_for_path(
            Path("manifests/init.pp"),
            text="class apache {\n  include apache::params\n}\n",
        )
        == "puppet"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.pp"),
            text="program Main;\nbegin\nend.\n",
        )
        == "pascal"
    )
    assert (
        repository_service._language_for_path(
            Path("rules/main.yar"),
            text='import "pe"\n\nrule main_rule {\n  condition:\n    pe.is_dll\n}\n',
        )
        == "yara"
    )
    assert (
        repository_service._language_for_path(
            Path("functions/helper.fish"),
            text="function helper\n    render_json\nend\n",
        )
        == "fish"
    )
    assert (
        repository_service._language_for_path(
            Path("bin/fish-runner"),
            text="#!/usr/bin/env fish\nfunction helper\n    echo ok\nend\n",
        )
        == "fish"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.hx"),
            text=(
                "package demo;\n"
                "\n"
                "import demo.Helper;\n"
                "\n"
                "class Main {\n"
                "    static function main() {\n"
                "        Helper.renderJson();\n"
                "    }\n"
                "}\n"
            ),
        )
        == "haxe"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.odin"),
            text='package main\n\nimport "core:fmt"\n\nmain :: proc() {\n    fmt.println("ok")\n}\n',
        )
        == "odin"
    )
    assert (
        repository_service._language_for_path(
            Path("ols.json"),
            text='{"profile":"default","profiles":[{"name":"default","checker_path":["src"]}]}\n',
        )
        == "json"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Ref.php"),
            text="<?hh\nnamespace Demo;\nfinal class Ref<T> {}\n",
        )
        == "hack"
    )
    assert (
        repository_service._language_for_path(
            Path("src/User.hack"),
            text="namespace Demo;\nfinal class User {}\n",
        )
        == "hack"
    )
    assert (
        repository_service._language_for_path(
            Path(".hhconfig"),
            text="assume_php = false\n",
        )
        == "hack"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.chpl"),
            text=(
                "module Main {\n"
                "use Utils;\n"
                "proc run() {\n"
                "  return helper();\n"
                "}\n"
                "}\n"
            ),
        )
        == "chapel"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/Main.ahk"),
            text='#Include "Lib/Helper.ahk"\nMain() {\n    RenderJson("{}")\n}\n',
        )
        == "autohotkey"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/Main.au3"),
            text='#include "Includes/Helper.au3"\nFunc Main()\n    Return RenderJson("{}")\nEndFunc\n',
        )
        == "autoit"
    )
    assert (
        repository_service._language_for_path(
            Path("build.hxml"),
            text="-cp src\n-main demo.Main\n",
        )
        == "haxe"
    )
    assert (
        repository_service._language_for_path(
            Path("project.xml"),
            text='<project><source path="src"/><app main="demo.Main"/></project>\n',
        )
        == "haxe"
    )
    assert (
        repository_service._language_for_path(
            Path("flake.nix"),
            text="{ inputs, ... }: { outputs = inputs: { formatter = null; }; }\n",
        )
        == "nix"
    )
    assert (
        repository_service._language_for_path(
            Path("plugin/fugitive.vim"),
            text="function! fugitive#run()\nendfunction\n",
        )
        == "vimscript"
    )
    assert (
        repository_service._language_for_path(
            Path("vimrc"),
            text="set number\n",
        )
        == "vimscript"
    )
    assert (
        repository_service._language_for_path(
            Path(".vimrc"),
            text="let mapleader = ','\n",
        )
        == "vimscript"
    )
    assert (
        repository_service._language_for_path(
            Path("Source/Main.vim"),
            text="RSRC\nLVIN\n",
        )
        == "labview"
    )


def test_language_for_path_detects_extensionless_awk_shebang() -> None:
    assert (
        repository_service._language_for_path(
            Path("bin/translate"),
            text="#!/usr/bin/env gawk -f\nBEGIN { print 1 }\n",
        )
        == "awk"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Application.cfc"),
            text=(
                "component {\n"
                "    function onApplicationStart() {\n"
                "    }\n"
                "}\n"
            ),
        )
        == "cfml"
    )
    assert (
        repository_service._language_for_path(
            Path("views/index.cfm"),
            text='<cfinclude template="../config/app.cfm">\n',
        )
        == "cfml"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.m"),
            text="function value = main()\nvalue = helper();\nend\n",
        )
        == "matlab"
    )
    assert (
        repository_service._language_for_path(
            Path("Kernel/init.m"),
            text='Get["Acme`Helpers`"];\n',
        )
        == "wolfram"
    )
    assert (
        repository_service._language_for_path(
            Path("Source/Controls/Config.ctl"),
            text="RSRC\r\n\x00\x03LVCCLBVW",
        )
        == "labview"
    )
    assert (
        repository_service._language_for_path(
            Path("ios/AppDelegate.m"),
            text="#import <Foundation/Foundation.h>\n@implementation AppDelegate\n@end\n",
        )
        == "objectivec"
    )
    assert (
        repository_service._language_for_path(
            Path("ios/AppDelegate.h"),
            text="#import <Foundation/Foundation.h>\n@interface AppDelegate : NSObject\n@end\n",
        )
        == "objectivec"
    )
    assert (
        repository_service._language_for_path(
            Path("rtl/child.v"),
            text="module child;\n  reg ready;\nendmodule\n",
        )
        == "verilog"
    )
    assert (
        repository_service._language_for_path(
            Path("rtl/defs.vh"),
            text="`ifndef DEFS_VH\n`define DEFS_VH\n`endif\n",
        )
        == "verilog"
    )
    assert (
        repository_service._language_for_path(
            Path("include/io.inc"),
            text="extern print_string\n",
        )
        == "assembly"
    )
    assert (
        repository_service._language_for_path(
            Path("database/Acme.sqlproj"),
            text=(
                "<Project>\n"
                "  <ItemGroup>\n"
                '    <Build Include="dbo\\\\Stored Procedures\\\\LoadCustomers.sql" />\n'
                "  </ItemGroup>\n"
                "</Project>\n"
            ),
        )
        == "tsql"
    )
    assert (
        repository_service._language_for_path(
            Path("database/dbo/Stored Procedures/LoadCustomers.sql"),
            text=(
                "create or alter procedure dbo.LoadCustomers\n"
                "as\n"
                "begin\n"
                "    set nocount on;\n"
                "    exec dbo.LoadHelpers;\n"
                "end\n"
                "go\n"
            ),
        )
        == "tsql"
    )
    assert (
        repository_service._language_for_path(
            Path("src/family.pl"),
            text=":- module(family, [parent/2]).\nparent(alice, bob).\n",
        )
        == "prolog"
    )
    assert (
        repository_service._language_for_path(
            Path("script/app.pl"),
            text="use strict;\nsub run {\n    return 1;\n}\n",
        )
        == "perl"
    )
    assert (
        repository_service._language_for_path(
            Path("App/MainForm.pas"),
            text=(
                "unit MainForm;\n"
                "interface\n"
                "uses System.SysUtils, Vcl.Forms;\n"
                "{$R *.dfm}\n"
                "implementation\n"
                "end.\n"
            ),
        )
        == "delphi"
    )
    assert (
        repository_service._language_for_path(
            Path("app/mainform.pas"),
            text=(
                "unit MainForm;\n"
                "interface\n"
                "{$mode objfpc}{$H+}\n"
                "uses Classes, SysUtils;\n"
                "implementation\n"
                "end.\n"
            ),
        )
        == "pascal"
    )
    assert (
        repository_service._language_for_path(
            Path("src/modMain.bas"),
            text='Attribute VB_Name = "modMain"\nOption Explicit\nPublic Sub RunApp()\nEnd Sub\n',
        )
        == "vba"
    )
    assert (
        repository_service._language_for_path(
            Path("programs/main.prg"),
            text="LPARAMETERS to_json\nFUNCTION main()\n    RETURN to_json\nENDFUNC\n",
        )
        == "foxpro"
    )
    assert (
        repository_service._language_for_path(
            Path("contracts/Counter.sol"),
            text='pragma solidity ^0.8.20;\ncontract Counter {\n    function increment() public {}\n}\n',
        )
        == "solidity"
    )
    assert (
        repository_service._language_for_path(
            Path("PackagesLocalDirectory/Acme/Descriptor/Acme.xml"),
            text=(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                "<AxModelInfo>\n"
                "  <Name>Acme</Name>\n"
                "</AxModelInfo>\n"
            ),
        )
        == "xpp"
    )
    assert (
        repository_service._language_for_path(
            Path("Cakefile"),
            text="task 'build', ->\n  console.log 'ok'\n",
        )
        == "coffeescript"
    )
    assert (
        repository_service._language_for_path(
            Path("PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml"),
            text=(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                "<AxClass>\n"
                "  <Name>AcmeMain</Name>\n"
                "  <SourceCode>\n"
                "    <Declaration><![CDATA[\n"
                "class AcmeMain\n"
                "{\n"
                "}\n"
                "]]></Declaration>\n"
                "  </SourceCode>\n"
                "</AxClass>\n"
            ),
        )
        == "xpp"
    )
    assert (
        repository_service._language_for_path(
            Path("force-app/main/default/classes/AccountTriggerHandler.cls"),
            text=(
                "public with sharing class AccountTriggerHandler {\n"
                "    public static void run() {\n"
                "    }\n"
                "}\n"
            ),
        )
        == "apex"
    )
    assert (
        repository_service._language_for_path(
            Path("force-app/main/default/triggers/AccountTrigger.trigger"),
            text=(
                "trigger AccountTrigger on Account (before insert) {\n"
                "    AccountTriggerHandler.run();\n"
                "}\n"
            ),
        )
        == "apex"
    )
    assert repository_service._language_for_path(Path("scripts/build.vbs")) == "vbscript"
    assert repository_service._language_for_path(Path("scripts/Helper.applescript")) == "applescript"
    assert repository_service._language_for_path(Path("QRPGLESRC/ORD100.PGM.RPGLE")) == "rpg"
    assert repository_service._language_for_path(Path("QPROTOSRC/CUSTOMER.RPGLEINC")) == "rpg"
    assert repository_service._language_for_path(Path("src/report.sqlrpgle")) == "rpg"
    assert (
        repository_service._language_for_path(
            Path("scripts/main.wsf"),
            text=(
                '<job>\n'
                '  <script language="VBScript" src="lib/helper.vbs"></script>\n'
                '  <script language="VBScript">\n'
                "    Option Explicit\n"
                "    Sub Main()\n"
                "    End Sub\n"
                "  </script>\n"
                "</job>\n"
            ),
        )
        == "vbscript"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/Helper.scpt"),
            text=(
                "script HelperScript\n"
                "    on RenderJson(value)\n"
                "        return value\n"
                "    end RenderJson\n"
                "end script\n"
            ),
        )
        == "applescript"
    )
    assert (
        repository_service._language_for_path(
            Path("src/cHelper.cls"),
            text='VERSION 1.0 CLASS\nAttribute VB_Name = "cHelper"\nOption Explicit\n',
        )
        == "vba"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Form1.frm"),
            text='VERSION 5.00\nBegin VB.Form Form1\nEnd\nAttribute VB_Name = "Form1"\n',
        )
        == "vb6"
    )
    assert (
        repository_service._language_for_path(
            Path("src/ctxWinsock.ctl"),
            text='Begin VB.UserControl ctxWinsock\nEnd\nAttribute VB_Name = "ctxWinsock"\n',
        )
        == "vb6"
    )
    assert (
        repository_service._language_for_path(
            Path("Project1.vbp"),
            text='Type=Exe\nForm=src/Form1.frm\nStartup="Form1"\nName="Project1"\n',
        )
        == "vb6"
    )
    assert repository_service._language_for_path(Path("src/main.adb_body")) == "unknown"


def test_language_for_path_uses_vbp_repo_context_before_vba(tmp_path: Path) -> None:
    repo_path = tmp_path / "vb6-context-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project1.vbp").write_text(
        'Type=Exe\n'
        'Class=cHelper; src/cHelper.cls\n'
        'Module=modMain; src/modMain.bas\n'
        'Startup="modMain"\n'
        'Name="Project1"\n',
        encoding="utf-8",
    )
    module_text = (
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n"
    )
    class_text = (
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "cHelper"\n'
        "Option Explicit\n"
    )

    assert repository_service._language_for_path(
        repo_path / "src" / "modMain.bas",
        text=module_text,
        repo_root=repo_path,
    ) == "vb6"
    assert repository_service._language_for_path(
        repo_path / "src" / "cHelper.cls",
        text=class_text,
        repo_root=repo_path,
    ) == "vb6"
    assert repository_service._language_for_path(
        Path("src/modMain.bas"),
        text=module_text,
    ) == "vba"
    assert repository_service._language_for_path(
        Path("src/cHelper.cls"),
        text=class_text,
    ) == "vba"


@pytest.mark.anyio
async def test_repository_intelligence_execution_workflow_wrappers_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SimpleNamespace(id="repo-1", org_id="org-1")
    simulation_request = RepositorySimulationRequest(
        snapshot_id="snapshot-1",
        decision_plan_id="plan-1",
    )
    apply_request = RepositoryApplyRequest(
        snapshot_id="snapshot-1",
        decision_plan_id="plan-1",
        simulation_id="simulation-1",
        mode=RepositoryApplyMode.PATCH_ONLY,
    )
    simulation_result = object()
    apply_result = object()
    observed: dict[str, dict[str, Any]] = {}

    async def _fake_simulate_repository_decision(**kwargs: Any) -> object:
        observed["simulate"] = kwargs
        return simulation_result

    async def _fake_apply_repository_decision(**kwargs: Any) -> object:
        observed["apply"] = kwargs
        return apply_result

    monkeypatch.setattr(
        repository_execution_workflow,
        "simulate_repository_decision",
        _fake_simulate_repository_decision,
    )
    monkeypatch.setattr(
        repository_execution_workflow,
        "apply_repository_decision",
        _fake_apply_repository_decision,
    )

    assert (
        await repository_service.simulate_repository_decision(
            connector=connector,
            request=simulation_request,
        )
        is simulation_result
    )
    assert observed["simulate"]["connector"] is connector
    assert observed["simulate"]["request"] is simulation_request
    assert (
        observed["simulate"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert observed["simulate"]["get_policy"] is repository_service.get_policy
    assert (
        observed["simulate"]["load_decision_plan_manifest"]
        is repository_service._load_decision_plan_manifest
    )
    assert observed["simulate"]["simulation_lookup_key"] is repository_service._simulation_lookup_key
    assert observed["simulate"]["read_json"] is repository_service._read_json
    assert observed["simulate"]["run_simulation_fast"] is repository_service.run_simulation_fast
    assert observed["simulate"]["stable_identifier"] is repository_service._stable_identifier

    assert (
        await repository_service.apply_repository_decision(
            connector=connector,
            request=apply_request,
        )
        is apply_result
    )
    assert observed["apply"]["connector"] is connector
    assert observed["apply"]["request"] is apply_request
    assert (
        observed["apply"]["require_repository_connector"]
        is repository_service._require_repository_connector
    )
    assert observed["apply"]["parse_connector_config"] is repository_service._parse_connector_config
    assert (
        observed["apply"]["load_decision_plan_manifest"]
        is repository_service._load_decision_plan_manifest
    )
    assert observed["apply"]["load_simulation_manifest"] is repository_service._load_simulation_manifest
    assert observed["apply"]["patch_changed_files"] is repository_service._patch_changed_files
    assert observed["apply"]["resolved_repository_source"] is repository_service.resolved_repository_source
    assert observed["apply"]["git_command"] is repository_service._git_command
    assert observed["apply"]["repository_url"] is repository_service._repository_url
    assert (
        observed["apply"]["authenticated_repository_url"]
        is repository_service._authenticated_repository_url
    )
    assert observed["apply"]["repo_access_token"] is repository_service._repo_access_token
    assert observed["apply"]["stable_identifier"] is repository_service._stable_identifier


def test_repository_snapshot_graph_contains_ada_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ada-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "alire.toml").write_text(
        'name = "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme-util.adb").write_text(
        "package body Acme.Util is\n"
        "   procedure Helper is\n"
        "   begin\n"
        "      null;\n"
        "   end Helper;\n"
        "end Acme.Util;\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.adb").write_text(
        "with Acme.Util;\n"
        "procedure Main is\n"
        "begin\n"
        "   Acme.Util.Helper;\n"
        "end Main;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "alire.toml"],
            include_patterns=[
                "src/**/*.adb",
                "src/*.adb",
                "src/**/*.ads",
                "src/*.ads",
                "*.adb",
                "*.ads",
                "*.ada",
                "alire.toml",
                "*.gpr",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.adb"
        and str(row["target_node"]) == "file:src/acme-util.adb"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/main.adb", "Main")]
    helper_symbol_id = symbol_ids[("src/acme-util.adb", "Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_cobol_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cobol-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "copybooks").mkdir(parents=True)
    (repo_path / "copybooks" / "PERSON-REC.cpy").write_text(
        "       01 PERSON-REC.\n"
        "          05 PERSON-ID PIC 9(4).\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "UTILS.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. UTILS.\n"
        "       PROCEDURE DIVISION.\n"
        "       UTILS-MAIN.\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "MAINAPP.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. MAINAPP.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       COPY PERSON-REC.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           CALL \"UTILS\".\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "copybooks"],
            include_patterns=[
                "src/**/*.cbl",
                "src/*.cbl",
                "src/**/*.cob",
                "src/*.cob",
                "copybooks/**/*.cpy",
                "copybooks/*.cpy",
                "*.cbl",
                "*.cob",
                "*.cobol",
                "*.cpy",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/MAINAPP.cbl"
        and str(row["target_node"]) == "file:copybooks/PERSON-REC.cpy"
        for row in graph_rows
    )
    main_para_symbol_id = symbol_ids[("src/MAINAPP.cbl", "main-para")]
    utils_symbol_id = symbol_ids[("src/UTILS.cbl", "utils")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_para_symbol_id}"
        and str(row["target_node"]) == f"symbol:{utils_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_plsql_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "plsql-dependency-repo"
    (repo_path / "db").mkdir(parents=True)
    (repo_path / "db" / "app_util.pks").write_text(
        "create or replace package app_util as\n"
        "  procedure record_order(p_order_id in number);\n"
        "end app_util;\n"
        "/\n",
        encoding="utf-8",
    )
    (repo_path / "db" / "order_api.pks").write_text(
        "create or replace package order_api as\n"
        "  procedure submit_order;\n"
        "end order_api;\n"
        "/\n",
        encoding="utf-8",
    )
    (repo_path / "db" / "order_api.pkb").write_text(
        "create or replace package body order_api as\n"
        "  procedure submit_order is\n"
        "  begin\n"
        "    app_util.record_order(42);\n"
        "  end submit_order;\n"
        "end order_api;\n"
        "/\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["db"],
            include_patterns=[
                "db/**/*.pkb",
                "db/*.pkb",
                "db/**/*.pks",
                "db/*.pks",
                "db/**/*.pls",
                "db/*.pls",
                "db/**/*.prc",
                "db/*.prc",
                "db/**/*.fnc",
                "db/*.fnc",
                "db/**/*.trg",
                "db/*.trg",
                "*.pkb",
                "*.pks",
                "*.pls",
                "*.prc",
                "*.fnc",
                "*.trg",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:db/order_api.pkb"
        and str(row["target_node"]) == "file:db/order_api.pks"
        for row in graph_rows
    )
    submit_order_symbol_id = symbol_ids[("db/order_api.pkb", "submit_order")]
    record_order_symbol_id = symbol_ids[("db/app_util.pks", "record_order")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{submit_order_symbol_id}"
        and str(row["target_node"]) == f"symbol:{record_order_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_sas_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "sas-dependency-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "macros").mkdir(parents=True)
    (repo_path / "macros" / "render_table.sas").write_text(
        "%macro render_table();\n"
        "  %put rendering table;\n"
        "%mend render_table;\n",
        encoding="utf-8",
    )
    (repo_path / "programs" / "report.sas").write_text(
        "%include \"../macros/render_table.sas\";\n"
        "%macro build_report();\n"
        "  %render_table();\n"
        "%mend build_report;\n"
        "%build_report();\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["programs", "macros"],
            include_patterns=[
                "programs/**/*.sas",
                "programs/*.sas",
                "macros/**/*.sas",
                "macros/*.sas",
                "*.sas",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:programs/report.sas"
        and str(row["target_node"]) == "file:macros/render_table.sas"
        for row in graph_rows
    )
    build_report_symbol_id = symbol_ids[("programs/report.sas", "build_report")]
    render_table_symbol_id = symbol_ids[("macros/render_table.sas", "render_table")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_report_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_table_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_abap_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "abap-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "zcl_math.clas.abap").write_text(
        "CLASS zcl_math DEFINITION PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    CLASS-METHODS add_one IMPORTING iv_value TYPE i RETURNING VALUE(rv_value) TYPE i.\n"
        "ENDCLASS.\n"
        "\n"
        "CLASS zcl_math IMPLEMENTATION.\n"
        "  METHOD add_one.\n"
        "    rv_value = iv_value + 1.\n"
        "  ENDMETHOD.\n"
        "ENDCLASS.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "zcl_report.clas.abap").write_text(
        "CLASS zcl_report DEFINITION PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    METHODS run.\n"
        "ENDCLASS.\n"
        "\n"
        "CLASS zcl_report IMPLEMENTATION.\n"
        "  INCLUDE zcl_report.clas.locals_imp.\n"
        "ENDCLASS.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "zcl_report.clas.locals_imp.abap").write_text(
        "METHOD run.\n"
        "  DATA(result) = zcl_math=>add_one( 1 ).\n"
        "ENDMETHOD.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.abap", "src/*.abap", "*.abap"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    run_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "src/zcl_report.clas.locals_imp.abap"
        and str(row["symbol_name"]) == "run"
    )
    add_one_symbol_ids = {
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "src/zcl_math.clas.abap"
        and str(row["symbol_name"]) == "add_one"
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/zcl_report.clas.abap"
        and str(row["target_node"]) == "file:src/zcl_report.clas.locals_imp.abap"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) in {f"symbol:{symbol_id}" for symbol_id in add_one_symbol_ids}
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_pascal_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "pascal-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Acme.lpi").write_text("<CONFIG></CONFIG>\n", encoding="utf-8")
    (repo_path / "src" / "AcmeUtil.pas").write_text(
        "unit AcmeUtil;\n"
        "interface\n"
        "procedure Helper;\n"
        "implementation\n"
        "procedure Helper;\n"
        "begin\n"
        "end;\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "main.lpr").write_text(
        "program AcmeApp;\n"
        "uses AcmeUtil;\n"
        "begin\n"
        "  AcmeUtil.Helper;\n"
        "end.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "main.lpr", "Acme.lpi"],
            include_patterns=[
                "src/**/*.pas",
                "src/*.pas",
                "*.pas",
                "*.pp",
                "*.lpr",
                "*.dpr",
                "*.dpk",
                "*.lpi",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.lpr"
        and str(row["target_node"]) == "file:src/AcmeUtil.pas"
        for row in graph_rows
    )
    app_symbol_id = symbol_ids[("main.lpr", "AcmeApp")]
    helper_symbol_id = symbol_ids[("src/AcmeUtil.pas", "Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{app_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_delphi_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "delphi-dependency-repo"
    (repo_path / "App").mkdir(parents=True)
    (repo_path / "App" / "AcmeApp.dproj").write_text(
        "<Project>\n"
        "  <MainSource>AcmeApp.dpr</MainSource>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "MainForm.pas").write_text(
        "unit MainForm;\n"
        "interface\n"
        "uses System.SysUtils, Vcl.Forms;\n"
        "type\n"
        "  TMainForm = class(TForm)\n"
        "  public\n"
        "    class procedure Run;\n"
        "  end;\n"
        "{$R *.dfm}\n"
        "implementation\n"
        "class procedure TMainForm.Run;\n"
        "begin\n"
        "end;\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "AcmeApp.dpr").write_text(
        "program AcmeApp;\n"
        "uses MainForm in 'MainForm.pas';\n"
        "begin\n"
        "  MainForm.Run;\n"
        "end.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["App"],
            include_patterns=[
                "App/**/*.pas",
                "App/*.pas",
                "App/*.dpr",
                "App/*.dproj",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:App/AcmeApp.dpr"
        and str(row["target_node"]) == "file:App/MainForm.pas"
        for row in graph_rows
    )
    app_symbol_id = symbol_ids[("App/AcmeApp.dpr", "AcmeApp")]
    run_symbol_ids = {
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "App/MainForm.pas" and str(row["symbol_name"]) == "Run"
    }
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{app_symbol_id}"
        and str(row["target_node"]) in {f"symbol:{symbol_id}" for symbol_id in run_symbol_ids}
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_foxpro_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "foxpro-dependency-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "programs" / "util.prg").write_text(
        "FUNCTION helper()\n"
        "    RETURN 1\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    (repo_path / "programs" / "main.prg").write_text(
        "SET PROCEDURE TO programs/util ADDITIVE\n"
        "FUNCTION run()\n"
        "    RETURN helper()\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["programs"],
            include_patterns=["programs/**/*.prg", "programs/*.prg", "*.prg"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:programs/main.prg"
        and str(row["target_node"]) == "file:programs/util.prg"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("programs/main.prg", "run")]
    helper_symbol_id = symbol_ids[("programs/util.prg", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_solidity_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "solidity-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "foundry.toml").write_text(
        '[profile.default]\nsrc = "src"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Ownable.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "abstract contract Ownable {\n"
        "    function owner() public view returns (address) {}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Counter.sol").write_text(
        'pragma solidity ^0.8.20;\n'
        'import {Ownable} from "./Ownable.sol";\n'
        "contract Counter is Ownable {\n"
        "    function increment() public {}\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.sol", "src/*.sol", "*.sol"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/Counter.sol"
        and str(row["target_node"]) == "file:src/Ownable.sol"
        for row in graph_rows
    )
    counter_symbol_id = symbol_ids[("src/Counter.sol", "Counter")]
    ownable_symbol_id = symbol_ids[("src/Ownable.sol", "Ownable")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{counter_symbol_id}"
        and str(row["target_node"]) == f"symbol:{ownable_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_ladder_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ladder-dependency-repo"
    (repo_path / "logic").mkdir(parents=True)
    (repo_path / "logic" / "Child.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="SupportProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="ChildRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[XIC(StartPB)OTE(RunMotor);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "logic" / "Main.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="MainProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="MainRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[JSR(ChildRoutine,0);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["logic"],
            include_patterns=[
                "logic/**/*.L5X",
                "logic/*.L5X",
                "*.L5X",
                "logic/**/*.l5x",
                "logic/*.l5x",
                "*.l5x",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:logic/Main.L5X"
        and str(row["target_node"]) == "file:logic/Child.L5X"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("logic/Main.L5X", "MainRoutine")]
    child_symbol_id = symbol_ids[("logic/Child.L5X", "ChildRoutine")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{child_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_labview_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "labview-dependency-repo"
    (repo_path / "Source" / "Libraries").mkdir(parents=True)
    (repo_path / "Source" / "Controls").mkdir(parents=True)
    (repo_path / "App.lvproj").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Project Type=\"Project\">\n"
        '  <Item Name="Main" Type="VI" URL="Source/Main.vi" />\n'
        '  <Item Name="Helpers" Type="Library" URL="Source/Libraries/Helpers.lvlib" />\n'
        '  <Item Name="Config" Type="Control" URL="Source/Controls/Config.ctl" />\n'
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "Source" / "Libraries" / "Helpers.lvlib").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Library Name=\"Helpers\">\n"
        '  <Item Name="Helper" Type="VI" URL="Helper.vi" />\n'
        "</Library>\n",
        encoding="utf-8",
    )
    (repo_path / "Source" / "Main.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")
    (repo_path / "Source" / "Libraries" / "Helper.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")
    (repo_path / "Source" / "Controls" / "Config.ctl").write_bytes(b"RSRC\r\n\x00\x03LVCCLBVW")
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=[
                "**/*.lvproj",
                "*.lvproj",
                "**/*.lvlib",
                "*.lvlib",
                "**/*.lvclass",
                "*.lvclass",
                "**/*.vi",
                "*.vi",
                "**/*.vim",
                "*.vim",
                "**/*.vit",
                "*.vit",
                "**/*.ctl",
                "*.ctl",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:App.lvproj"
        and str(row["target_node"]) == "file:Source/Libraries/Helpers.lvlib"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:Source/Libraries/Helpers.lvlib"
        and str(row["target_node"]) == "file:Source/Libraries/Helper.vi"
        for row in graph_rows
    )
    helpers_symbol_id = symbol_ids[("Source/Libraries/Helpers.lvlib", "Helpers")]
    helper_symbol_id = symbol_ids[("Source/Libraries/Helper.vi", "Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{helpers_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_actionscript_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "actionscript-dependency-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "base").mkdir(parents=True)
    (repo_path / "src" / "demo" / "utils").mkdir(parents=True)
    (repo_path / "src" / "demo" / "base" / "BaseActor.as").write_text(
        "package demo.base {\n"
        "    public class BaseActor {\n"
        "        public function baseReady():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "utils" / "Utils.as").write_text(
        "package demo.utils {\n"
        "    public class Utils {\n"
        "        public static function helper():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "app" / "Main.as").write_text(
        "package demo.app {\n"
        "    import demo.base.BaseActor;\n"
        "    import demo.utils.Utils;\n"
        "    public class Main extends BaseActor {\n"
        "        public function boot():void {\n"
        "            var utils:Utils = new Utils();\n"
        "            Utils.helper();\n"
        "            utils.helper();\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["**/*.as", "*.as", "asconfig.json"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/demo/app/Main.as"
        and str(row["target_node"]) == "file:src/demo/base/BaseActor.as"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/demo/app/Main.as"
        and str(row["target_node"]) == "file:src/demo/utils/Utils.as"
        for row in graph_rows
    )
    boot_symbol_id = symbol_ids[("src/demo/app/Main.as", "boot")]
    helper_symbol_id = symbol_ids[("src/demo/utils/Utils.as", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{boot_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_coffeescript_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "coffeescript-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.coffee").write_text(
        "renderJson = ->\n"
        "  '{}'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.coffee").write_text(
        "helper = require './helper'\n"
        "\n"
        "run = ->\n"
        "  helper.renderJson('{}')\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.coffee", "src/*.coffee", "*.coffee", "Cakefile"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.coffee"
        and str(row["target_node"]) == "file:src/helper.coffee"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/main.coffee", "run")]
    render_symbol_id = symbol_ids[("src/helper.coffee", "renderJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_gams_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "gams-dependency-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "include" / "common.inc").write_text(
        "parameter demand(i);\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "main.gms").write_text(
        "$include ../include/common.inc\n"
        "set i /a,b/;\n"
        "parameter cost(i);\n"
        "equation balance;\n"
        "balance.. demand('a') =e= cost('a');\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["models", "include"],
            include_patterns=[
                "models/**/*.gms",
                "models/*.gms",
                "include/**/*.inc",
                "include/*.inc",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:models/main.gms"
        and str(row["target_node"]) == "file:include/common.inc"
        for row in graph_rows
    )
    balance_symbol_id = symbol_ids[("models/main.gms", "balance")]
    demand_symbol_id = symbol_ids[("include/common.inc", "demand")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{balance_symbol_id}"
        and str(row["target_node"]) == f"symbol:{demand_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_openscad_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "openscad-dependency-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "helper.scad").write_text(
        "function edge_radius(size) = size / 2;\n"
        "module gusset(width) {\n"
        "  cylinder(r=edge_radius(width));\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.scad").write_text(
        "include <lib/helper.scad>;\n"
        "module build() {\n"
        "  gusset(10);\n"
        "  edge_radius(10);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.scad", "*.scad"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.scad"
        and str(row["target_node"]) == "file:lib/helper.scad"
        for row in graph_rows
    )
    build_symbol_id = symbol_ids[("main.scad", "build")]
    gusset_symbol_id = symbol_ids[("lib/helper.scad", "gusset")]
    edge_radius_symbol_id = symbol_ids[("lib/helper.scad", "edge_radius")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{gusset_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{edge_radius_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_purescript_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "purescript-dependency-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "src" / "Data" / "Helper.purs").write_text(
        "module Data.Helper where\n"
        "\n"
        "data Helper = Helper\n"
        "\n"
        "helperValue :: Int\n"
        "helperValue = 1\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.purs").write_text(
        "module Main where\n"
        "\n"
        "import Data.Helper (Helper, helperValue)\n"
        "\n"
        "main = helperValue\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.purs", "src/*.purs", "*.purs", "spago.yaml", "bower.json"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/Main.purs"
        and str(row["target_node"]) == "file:src/Data/Helper.purs"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/Main.purs", "main")]
    helper_value_symbol_id = symbol_ids[("src/Data/Helper.purs", "helperValue")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_value_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_hcl_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "hcl-dependency-repo"
    (repo_path / "modules" / "child").mkdir(parents=True)
    (repo_path / "modules" / "child" / "main.tf").write_text(
        'output "child_id" {\n'
        '  value = "child"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.tf").write_text(
        'module "child" {\n'
        '  source = "./modules/child"\n'
        '}\n\n'
        'variable "name" {\n'
        '  default = "demo"\n'
        '}\n\n'
        "locals {\n"
        '  prefix = "vpc-${var.name}"\n'
        "}\n\n"
        'output "full_name" {\n'
        "  value = local.prefix\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.tf", "*.tf", "**/*.hcl", "*.hcl"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.tf"
        and str(row["target_node"]) == "file:modules/child/main.tf"
        for row in graph_rows
    )
    output_symbol_id = symbol_ids[("main.tf", "output.full_name")]
    local_symbol_id = symbol_ids[("main.tf", "local.prefix")]
    variable_symbol_id = symbol_ids[("main.tf", "var.name")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{output_symbol_id}"
        and str(row["target_node"]) == f"symbol:{local_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{local_symbol_id}"
        and str(row["target_node"]) == f"symbol:{variable_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_gleam_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "gleam-dependency-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "helper.gleam").write_text(
        "pub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.gleam").write_text(
        "import demo/helper.{render_json}\n\npub fn main() {\n  render_json()\n}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.gleam", "src/*.gleam", "*.gleam", "gleam.toml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.gleam"
        and str(row["target_node"]) == "file:src/demo/helper.gleam"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/main.gleam", "main")]
    helper_symbol_id = symbol_ids[("src/demo/helper.gleam", "render_json")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_janet_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "janet-dependency-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "project.janet").write_text(
        '(declare-project :name "demo" :source @["src"] :main "src/main.janet")\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "helper.janet").write_text(
        "(defn render-json [] @{})\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.janet").write_text(
        '(import ./demo/helper :as helper)\n\n(defn main []\n  (helper/render-json))\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.janet", "src/*.janet", "*.janet", "project.janet"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.janet"
        and str(row["target_node"]) == "file:src/demo/helper.janet"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/main.janet", "main")]
    helper_symbol_id = symbol_ids[("src/demo/helper.janet", "render-json")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_raku_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "raku-dependency-repo"
    (repo_path / "lib" / "Demo").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "META6.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "provides": {"Demo::Helper": "lib/Demo/Helper.rakumod"},
                "bin": ["demo"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "lib" / "Demo" / "Helper.rakumod").write_text(
        "unit module Demo::Helper;\n\nsub render-json() { }\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "demo.raku").write_text(
        "use Demo::Helper;\n\nsub main() {\n    Demo::Helper::render-json();\n}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib", "bin"],
            include_patterns=["lib/**/*.rakumod", "bin/**/*.raku", "*.json"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:bin/demo.raku"
        and str(row["target_node"]) == "file:lib/Demo/Helper.rakumod"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("bin/demo.raku", "main")]
    helper_symbol_id = symbol_ids[("lib/Demo/Helper.rakumod", "render-json")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_nushell_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "nushell-dependency-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "modules" / "helper.nu").write_text(
        "export def render-json [] {\n"
        "  '{}'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.nu").write_text(
        "source modules/helper.nu\n\n"
        "def main [] {\n"
        "  render-json\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["modules/**/*.nu", "*.nu"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.nu"
        and str(row["target_node"]) == "file:modules/helper.nu"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("main.nu", "main")]
    helper_symbol_id = symbol_ids[("modules/helper.nu", "render-json")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_fish_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "fish-dependency-repo"
    (repo_path / "functions").mkdir(parents=True)
    (repo_path / "functions" / "helper.fish").write_text(
        "function helper\n"
        "    echo '{}'\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "main.fish").write_text(
        "source functions/helper.fish\n\n"
        "function main\n"
        "    helper\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["functions/**/*.fish", "*.fish"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.fish"
        and str(row["target_node"]) == "file:functions/helper.fish"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("main.fish", "main")]
    helper_symbol_id = symbol_ids[("functions/helper.fish", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_batchfile_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "batchfile-dependency-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "tools" / "helper.cmd").write_text(
        "@echo off\n"
        ":helper\n"
        "echo helper\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "build.bat").write_text(
        "@echo off\n"
        "call ..\\tools\\helper.cmd\n"
        "goto :done\n"
        ":done\n"
        "exit /b 0\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts", "tools"],
            include_patterns=["scripts/**/*.bat", "tools/**/*.cmd", "*.bat", "*.cmd"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:scripts/build.bat"
        and str(row["target_node"]) == "file:tools/helper.cmd"
        for row in graph_rows
    )
    build_symbol_id = symbol_ids[("scripts/build.bat", "scripts/build")]
    done_symbol_id = symbol_ids[("scripts/build.bat", "done")]
    helper_symbol_id = symbol_ids[("tools/helper.cmd", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{done_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_makefile_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "makefile-dependency-repo"
    (repo_path / "mk").mkdir(parents=True)
    (repo_path / "mk" / "common.mk").write_text(
        "helper:\n"
        "\t@echo helper\n",
        encoding="utf-8",
    )
    (repo_path / "Makefile").write_text(
        "include mk/common.mk\n"
        "build: clean\n"
        "\t$(MAKE) helper\n"
        "clean:\n"
        "\t@echo clean\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["Makefile", "**/*.mk"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:Makefile"
        and str(row["target_node"]) == "file:mk/common.mk"
        for row in graph_rows
    )
    build_symbol_id = symbol_ids[("Makefile", "build")]
    clean_symbol_id = symbol_ids[("Makefile", "clean")]
    helper_symbol_id = symbol_ids[("mk/common.mk", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{clean_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_qmake_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "qmake-dependency-repo"
    (repo_path / "libs").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "project.pro").write_text(
        "TEMPLATE = subdirs\n"
        "TARGET = acme_workspace\n"
        "SUBDIRS += libs app\n"
        "libs.file = libs/libs.pro\n"
        "app.file = app/app.pro\n"
        "app.depends = libs\n"
        "include(common.pri)\n",
        encoding="utf-8",
    )
    (repo_path / "common.pri").write_text("CONFIG += ordered\n", encoding="utf-8")
    (repo_path / "libs" / "libs.pro").write_text(
        "TARGET = libs\nSOURCES += helper.cpp\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "app.pro").write_text(
        "TARGET = app\nSOURCES += main.cpp\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.pro", "*.pri", "**/*.pro", "**/*.pri"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:project.pro"
        and str(row["target_node"]) == "file:common.pri"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:project.pro"
        and str(row["target_node"]) == "file:libs/libs.pro"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:project.pro"
        and str(row["target_node"]) == "file:app/app.pro"
        for row in graph_rows
    )
    app_symbol_id = symbol_ids[("project.pro", "app")]
    libs_symbol_id = symbol_ids[("project.pro", "libs")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{app_symbol_id}"
        and str(row["target_node"]) == f"symbol:{libs_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_qml_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "qml-dependency-repo"
    (repo_path / "components").mkdir(parents=True)
    (repo_path / "qmldir").write_text(
        "module Demo.Controls\n"
        "Button 1.0 components/Button.qml\n",
        encoding="utf-8",
    )
    (repo_path / "components" / "Button.qml").write_text(
        "Rectangle {\n"
        "    id: buttonRoot\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Main.qml").write_text(
        'import "." as Demo\n'
        "Rectangle {\n"
        "    id: rootItem\n"
        "    Demo.Button {\n"
        "        id: helperButton\n"
        "    }\n"
        "    function activate() {\n"
        "        helperButton.visible = true\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.qml", "qmldir", "**/*.qml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    main_symbol_ids = {
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "Main.qml"
    }
    button_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "components/Button.qml" and str(row["symbol_name"]) == "Button"
    )

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:Main.qml"
        and str(row["target_node"]) == "file:qmldir"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]).removeprefix("symbol:") in main_symbol_ids
        and str(row["target_node"]) == f"symbol:{button_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_just_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "just-dependency-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "tasks.just").write_text(
        "helper:\n"
        "\t@echo helper\n",
        encoding="utf-8",
    )
    (repo_path / "Justfile").write_text(
        "mod tasks 'tasks.just'\n"
        "build: clean (tasks::helper)\n"
        "\tjust clean\n"
        "clean:\n"
        "\t@echo clean\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["Justfile", "*.just", ".justfile", "justfile"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:Justfile"
        and str(row["target_node"]) == "file:tasks.just"
        for row in graph_rows
    )
    build_symbol_id = symbol_ids[("Justfile", "build")]
    clean_symbol_id = symbol_ids[("Justfile", "clean")]
    helper_symbol_id = symbol_ids[("tasks.just", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{clean_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_haxe_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "haxe-dependency-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "Helper.hx").write_text(
        "package demo;\n"
        "\n"
        "class Helper {\n"
        "    public static function renderJson():String {\n"
        '        return "{}";\n'
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "Main.hx").write_text(
        "package demo;\n"
        "\n"
        "import demo.Helper;\n"
        "\n"
        "class Main {\n"
        "    static function main() {\n"
        "        Helper.renderJson();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "build.hxml").write_text("-cp src\n-main demo.Main\n", encoding="utf-8")
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.hx", "src/*.hx", "*.hx", "*.hxml", "project.xml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/demo/Main.hx"
        and str(row["target_node"]) == "file:src/demo/Helper.hx"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/demo/Main.hx", "main")]
    helper_symbol_id = symbol_ids[("src/demo/Helper.hx", "renderJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_chapel_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "chapel-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Utils.chpl").write_text(
        "module Utils {\n"
        "proc helper() { return 1; }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.chpl").write_text(
        "module Main {\n"
        "use Utils;\n"
        "proc run() {\n"
        "  return helper();\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.chpl", "src/**/*.chpl", "src/*.chpl"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.chpl"
        and str(row["target_node"]) == "file:src/Utils.chpl"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("main.chpl", "run")]
    helper_symbol_id = symbol_ids[("src/Utils.chpl", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_odin_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "odin-dependency-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    (repo_path / "src" / "common" / "helper.odin").write_text(
        "package common\n"
        "\n"
        "helper :: proc() -> int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.odin").write_text(
        "package main\n"
        "\n"
        'import "src:common"\n'
        "\n"
        "run :: proc() -> int {\n"
        "    return common.helper()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.odin", "src/*.odin", "*.odin", "ols.json"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.odin"
        and str(row["target_node"]) == "file:src/common/helper.odin"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/main.odin", "run")]
    helper_symbol_id = symbol_ids[("src/common/helper.odin", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_factor_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "factor-dependency-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "math" / "math.factor").write_text(
        "IN: math\n\n: square ( n -- n ) dup * ;\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "main.factor").write_text(
        "USING: math ;\n"
        "IN: app.main\n\n"
        ": run ( n -- n ) square ;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.factor", "*.factor"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:app/main.factor"
        and str(row["target_node"]) == "file:math/math.factor"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("app/main.factor", "run")]
    square_symbol_id = symbol_ids[("math/math.factor", "square")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{square_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_cue_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cue-dependency-repo"
    (repo_path / "cue.mod").mkdir(parents=True)
    (repo_path / "pkg" / "schema").mkdir(parents=True)
    (repo_path / "cue.mod" / "module.cue").write_text(
        'module: "example.com/demo"\n',
        encoding="utf-8",
    )
    (repo_path / "pkg" / "schema" / "schema.cue").write_text(
        "package schema\n\n#Answer: 42\n",
        encoding="utf-8",
    )
    (repo_path / "main.cue").write_text(
        'package main\n\nimport schema "example.com/demo/pkg/schema"\n\nvalue: schema.#Answer\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.cue", "*.cue"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.cue"
        and str(row["target_node"]) == "file:pkg/schema/schema.cue"
        for row in graph_rows
    )
    value_symbol_id = symbol_ids[("main.cue", "value")]
    answer_symbol_id = symbol_ids[("pkg/schema/schema.cue", "#Answer")]
    assert any(
        str(row["edge_type"]) in {"references", "references_symbol"}
        and str(row["source_node"]) == f"symbol:{value_symbol_id}"
        and str(row["target_node"]) == f"symbol:{answer_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_autohotkey_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "autohotkey-dependency-repo"
    (repo_path / "Lib").mkdir(parents=True)
    (repo_path / "Lib" / "Helper.ahk").write_text(
        "RenderJson(value) {\n"
        "    return value\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "Main.ahk").write_text(
        '#Include "../Lib/Helper.ahk"\n'
        "\n"
        "Main() {\n"
        '    return RenderJson("{}")\n'
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts", "Lib"],
            include_patterns=["scripts/**/*.ahk", "scripts/*.ahk", "Lib/**/*.ahk", "Lib/*.ahk"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:scripts/Main.ahk"
        and str(row["target_node"]) == "file:Lib/Helper.ahk"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("scripts/Main.ahk", "Main")]
    helper_symbol_id = symbol_ids[("Lib/Helper.ahk", "RenderJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_autoit_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "autoit-dependency-repo"
    (repo_path / "Includes").mkdir(parents=True)
    (repo_path / "Includes" / "Helper.au3").write_text(
        "Func RenderJson($value)\n"
        "    Return $value\n"
        "EndFunc\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "Main.au3").write_text(
        '#include "../Includes/Helper.au3"\n'
        "\n"
        "Func Main()\n"
        '    Return RenderJson("{}")\n'
        "EndFunc\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts", "Includes"],
            include_patterns=[
                "scripts/**/*.au3",
                "scripts/*.au3",
                "Includes/**/*.au3",
                "Includes/*.au3",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:scripts/Main.au3"
        and str(row["target_node"]) == "file:Includes/Helper.au3"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("scripts/Main.au3", "Main")]
    helper_symbol_id = symbol_ids[("Includes/Helper.au3", "RenderJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_squirrel_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "squirrel-dependency-repo"
    (repo_path / "scripts" / "vscripts").mkdir(parents=True)
    (repo_path / "scripts" / "vscripts" / "ppmod.nut").write_text(
        "::ppmod <- {\n"
        "  run = function () {\n"
        '    return "ok";\n'
        "  }\n"
        "};\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "vscripts" / "main.nut").write_text(
        'IncludeScript("ppmod");\n'
        "\n"
        '::main <- function () {\n'
        "  ppmod.run();\n"
        "};\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts/vscripts"],
            include_patterns=[
                "scripts/vscripts/**/*.nut",
                "scripts/vscripts/*.nut",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:scripts/vscripts/main.nut"
        and str(row["target_node"]) == "file:scripts/vscripts/ppmod.nut"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("scripts/vscripts/main.nut", "main")]
    helper_symbol_id = symbol_ids[("scripts/vscripts/ppmod.nut", "ppmod")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_cython_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cython-dependency-repo"
    (repo_path / "pkg").mkdir(parents=True)
    (repo_path / "pkg" / "defs.pxi").write_text(
        "DEF ANSWER = 42\n",
        encoding="utf-8",
    )
    (repo_path / "pkg" / "helpermod.pxd").write_text(
        "cdef int helper()\n",
        encoding="utf-8",
    )
    (repo_path / "pkg" / "main.pyx").write_text(
        'include "defs.pxi"\n'
        "from helpermod cimport helper\n"
        "\n"
        "cpdef int run():\n"
        "    return helper()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["pkg"],
            include_patterns=[
                "pkg/**/*.pyx",
                "pkg/**/*.pxd",
                "pkg/**/*.pxi",
                "pkg/*.pyx",
                "pkg/*.pxd",
                "pkg/*.pxi",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:pkg/main.pyx"
        and str(row["target_node"]) == "file:pkg/helpermod.pxd"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "includes"
        and str(row["source_node"]) == "file:pkg/main.pyx"
        and str(row["target_node"]) == "file:pkg/defs.pxi"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("pkg/main.pyx", "run")]
    helper_symbol_id = symbol_ids[("pkg/helpermod.pxd", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_stan_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "stan-dependency-repo"
    (repo_path / "models" / "lib").mkdir(parents=True)
    (repo_path / "models" / "lib" / "math.stan").write_text(
        "functions {\n"
        "  real add_one(real x) {\n"
        "    return x + 1;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "main.stan").write_text(
        '#include "lib/math.stan"\n'
        "\n"
        "functions {\n"
        "  real run(real x) {\n"
        "    return add_one(x);\n"
        "  }\n"
        "}\n"
        "\n"
        "data {\n"
        "  real x;\n"
        "}\n"
        "model {\n"
        "  target += run(x);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["models"],
            include_patterns=["models/**/*.stan", "models/*.stan"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "includes"
        and str(row["source_node"]) == "file:models/main.stan"
        and str(row["target_node"]) == "file:models/lib/math.stan"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("models/main.stan", "run")]
    helper_symbol_id = symbol_ids[("models/lib/math.stan", "add_one")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_robotframework_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "robotframework-dependency-repo"
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "resources").mkdir(parents=True)
    (repo_path / "resources" / "common.resource").write_text(
        "*** Keywords ***\n"
        "Open Login Page\n"
        "    Log    opened\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "login.robot").write_text(
        "*** Settings ***\n"
        "Resource    ../resources/common.resource\n"
        "\n"
        "*** Test Cases ***\n"
        "Valid Login\n"
        "    Open Login Page\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["tests", "resources"],
            include_patterns=[
                "tests/**/*.robot",
                "tests/*.robot",
                "resources/**/*.resource",
                "resources/*.resource",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:tests/login.robot"
        and str(row["target_node"]) == "file:resources/common.resource"
        for row in graph_rows
    )
    test_symbol_id = symbol_ids[("tests/login.robot", "Valid Login")]
    helper_symbol_id = symbol_ids[("resources/common.resource", "Open Login Page")]
    assert any(
        str(row["edge_type"]) == "calls"
        and str(row["source_node"]) == f"symbol:{test_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scss_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scss-dependency-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "_mixins.scss").write_text(
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "_functions.scss").write_text(
        "@function helper-fn() {\n"
        "  @return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "main.scss").write_text(
        '@use "mixins" as mixins;\n'
        '@import "functions";\n'
        ".button {\n"
        "  @include mixins.button-base;\n"
        "  color: helper-fn();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["styles"],
            include_patterns=["styles/*.scss", "styles/**/*.scss"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "uses"
        and str(row["source_node"]) == "file:styles/main.scss"
        and str(row["target_node"]) == "file:styles/_mixins.scss"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("styles/main.scss", "styles/main")]
    helper_symbol_id = symbol_ids[("styles/_functions.scss", "helper-fn")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_typst_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "typst-dependency-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "partials").mkdir(parents=True)
    (repo_path / "src" / "lib" / "math.typ").write_text(
        "#let add(x, y) = x + y\n"
        "#let scale(x) = x * 2\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "partials" / "common.typ").write_text(
        "#let common() = [hello]\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.typ").write_text(
        '#import "lib/math.typ": add\n'
        '#import "lib/math.typ" as math\n'
        '#include "partials/common.typ"\n'
        "#let render() = {\n"
        "  add(1, 2)\n"
        "  math.scale(3)\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/*.typ", "src/**/*.typ"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.typ"
        and str(row["target_node"]) == "file:src/lib/math.typ"
        for row in graph_rows
    )
    render_symbol_id = symbol_ids[("src/main.typ", "render")]
    scale_symbol_id = symbol_ids[("src/lib/math.typ", "scale")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{render_symbol_id}"
        and str(row["target_node"]) == f"symbol:{scale_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_cuda_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cuda-dependency-repo"
    (repo_path / "src" / "kernels").mkdir(parents=True)
    (repo_path / "src" / "kernels" / "math.cuh").write_text(
        "__device__ inline int add_one(int x) {\n"
        "  return x + 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cu").write_text(
        '#include "kernels/math.cuh"\n'
        "__global__ void kernel_run(int* out) {\n"
        "  *out = add_one(*out);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.cu", "src/**/*.cuh", "src/*.cu", "src/*.cuh"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.cu"
        and str(row["target_node"]) == "file:src/kernels/math.cuh"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/main.cu", "kernel_run")]
    helper_symbol_id = symbol_ids[("src/kernels/math.cuh", "add_one")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_hlsl_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "hlsl-dependency-repo"
    (repo_path / "shaders" / "lib").mkdir(parents=True)
    (repo_path / "shaders" / "lib" / "noise.hlsli").write_text(
        "float NoiseValue() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "shaders" / "main.hlsl").write_text(
        '#include "lib/noise.hlsli"\n'
        "float4 RenderMain() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["shaders"],
            include_patterns=["shaders/**/*.hlsl", "shaders/**/*.hlsli", "shaders/*.hlsl"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "includes"
        and str(row["source_node"]) == "file:shaders/main.hlsl"
        and str(row["target_node"]) == "file:shaders/lib/noise.hlsli"
        for row in graph_rows
    )
    render_symbol_id = symbol_ids[("shaders/main.hlsl", "RenderMain")]
    helper_symbol_id = symbol_ids[("shaders/lib/noise.hlsli", "NoiseValue")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{render_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_wgsl_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "wgsl-dependency-repo"
    (repo_path / "shaders" / "lib").mkdir(parents=True)
    (repo_path / "shaders" / "lib" / "noise.wgsl").write_text(
        "fn NoiseValue() -> f32 {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "shaders" / "main.wgsl").write_text(
        '#include "lib/noise.wgsl"\n'
        "@fragment\n"
        "fn fs_main() -> vec4f {\n"
        "  return vec4f(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["shaders"],
            include_patterns=["shaders/**/*.wgsl", "shaders/*.wgsl"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "includes"
        and str(row["source_node"]) == "file:shaders/main.wgsl"
        and str(row["target_node"]) == "file:shaders/lib/noise.wgsl"
        for row in graph_rows
    )
    render_symbol_id = symbol_ids[("shaders/main.wgsl", "fs_main")]
    helper_symbol_id = symbol_ids[("shaders/lib/noise.wgsl", "NoiseValue")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{render_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_shaderlab_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "shaderlab-dependency-repo"
    (repo_path / "Shaders" / "Includes").mkdir(parents=True)
    (repo_path / "Shaders" / "Includes" / "Common.cginc").write_text(
        "float NoiseValue() {\n"
        "  return 0.25;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Shaders" / "Main.shader").write_text(
        'Shader "Demo/Main" {\n'
        "SubShader {\n"
        "Pass {\n"
        "CGPROGRAM\n"
        '#include "Includes/Common.cginc"\n'
        "float4 frag() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDCG\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Shaders"],
            include_patterns=["Shaders/**/*.shader", "Shaders/**/*.cginc", "Shaders/*.shader"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "includes"
        and str(row["source_node"]) == "file:Shaders/Main.shader"
        and str(row["target_node"]) == "file:Shaders/Includes/Common.cginc"
        for row in graph_rows
    )
    frag_symbol_id = symbol_ids[("Shaders/Main.shader", "frag")]
    helper_symbol_id = symbol_ids[("Shaders/Includes/Common.cginc", "NoiseValue")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{frag_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_starlark_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "starlark-dependency-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "lib" / "common.bzl").write_text(
        "def render_json(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "demo.bzl").write_text(
        'load("//lib:common.bzl", "render_json")\n'
        "\n"
        "def demo_macro(name):\n"
        "    return render_json(name)\n",
        encoding="utf-8",
    )
    (repo_path / "BUILD.bazel").write_text(
        'load("//rules:demo.bzl", "demo_macro")\n'
        '\n'
        'demo_macro(name = "app")\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=[
                "**/*.bzl",
                "*.bzl",
                "**/*.star",
                "*.star",
                "**/BUILD.bazel",
                "BUILD.bazel",
                "**/BUILD",
                "BUILD",
                "MODULE.bazel",
                "WORKSPACE",
                "WORKSPACE.bazel",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:BUILD.bazel"
        and str(row["target_node"]) == "file:rules/demo.bzl"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:rules/demo.bzl"
        and str(row["target_node"]) == "file:lib/common.bzl"
        for row in graph_rows
    )
    demo_macro_symbol_id = symbol_ids[("rules/demo.bzl", "demo_macro")]
    render_json_symbol_id = symbol_ids[("lib/common.bzl", "render_json")]
    assert any(
        str(row["edge_type"]) == "calls"
        and str(row["source_node"]) == f"symbol:{demo_macro_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_json_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_nix_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "nix-dependency-repo"
    (repo_path / "nix" / "lib").mkdir(parents=True)
    (repo_path / "nix" / "lib" / "formatter.nix").write_text(
        "{ pkgs }:\n"
        "{\n"
        "  mkFormatter = package: package;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "flake.nix").write_text(
        "{\n"
        "  inputs.nixpkgs.url = \"github:NixOS/nixpkgs\";\n"
        "  outputs = { self, nixpkgs }:\n"
        "    let formatter = import ./nix/lib/formatter.nix { pkgs = nixpkgs.legacyPackages.x86_64-linux; }; in {\n"
        "      formatter = formatter.mkFormatter nixpkgs.legacyPackages.x86_64-linux.alejandra;\n"
        "    };\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.nix", "*.nix"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:flake.nix"
        and str(row["target_node"]) == "file:nix/lib/formatter.nix"
        for row in graph_rows
    )
    flake_formatter_symbol_id = symbol_ids[("flake.nix", "formatter")]
    formatter_symbol_id = symbol_ids[("nix/lib/formatter.nix", "mkFormatter")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{flake_formatter_symbol_id}"
        and str(row["target_node"]) == f"symbol:{formatter_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_v_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "v-dependency-repo"
    repo_path.mkdir()
    (repo_path / "main.v").write_text(
        "module main\n"
        "\n"
        "import helper\n"
        "\n"
        "fn run() {\n"
        "    helper.render_json()\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "helper.v").write_text(
        "module helper\n"
        "\n"
        "pub fn render_json() string {\n"
        "    return '{}'\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.v", "*.v", "v.mod"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.v"
        and str(row["target_node"]) == "file:helper.v"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("main.v", "run")]
    render_json_symbol_id = symbol_ids[("helper.v", "render_json")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_json_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_vala_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "vala-dependency-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "util").mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('demo', 'vala')\n"
        "executable('demo', ['src/demo/app/Main.vala', 'src/demo/util/Helper.vala'])\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "util" / "Helper.vala").write_text(
        "namespace Demo.Util {\n"
        "    public class Helper : Object {\n"
        "        public string render_json () {\n"
        '            return "{}";\n'
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "app" / "Main.vala").write_text(
        "using Demo.Util;\n"
        "\n"
        "namespace Demo.App {\n"
        "    public class App : Object {\n"
        "        public void run () {\n"
        "            Helper helper = new Helper ();\n"
        "            helper.render_json ();\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "meson.build"],
            include_patterns=[
                "src/**/*.vala",
                "src/*.vala",
                "*.vala",
                "**/*.vapi",
                "*.vapi",
                "meson.build",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:src/demo/app/Main.vala"
        and str(row["target_node"]) == "file:src/demo/util/Helper.vala"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/demo/app/Main.vala", "run")]
    render_symbol_id = symbol_ids[("src/demo/util/Helper.vala", "render_json")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_mql5_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "mql5-dependency-repo"
    (repo_path / "Experts").mkdir(parents=True)
    (repo_path / "Include").mkdir(parents=True)
    (repo_path / "demo.mqproj").write_text(
        '<Project><Files><File>Experts/Main.mq5</File><File>Include/Helper.mqh</File></Files></Project>\n',
        encoding="utf-8",
    )
    (repo_path / "Include" / "Helper.mqh").write_text(
        "class Helper\n"
        "{\n"
        "public:\n"
        "   string RenderJson()\n"
        "     {\n"
        '      return "{}";\n'
        "     }\n"
        "};\n",
        encoding="utf-8",
    )
    (repo_path / "Experts" / "Main.mq5").write_text(
        '#include "../Include/Helper.mqh"\n'
        "\n"
        "void OnStart()\n"
        "{\n"
        "   Helper helper;\n"
        "   helper.RenderJson();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Experts", "Include", "demo.mqproj"],
            include_patterns=[
                "Experts/**/*.mq5",
                "Experts/*.mq5",
                "Include/**/*.mqh",
                "Include/*.mqh",
                "*.mqproj",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:Experts/Main.mq5"
        and str(row["target_node"]) == "file:Include/Helper.mqh"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("Experts/Main.mq5", "OnStart")]
    render_symbol_id = symbol_ids[("Include/Helper.mqh", "RenderJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_smalltalk_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "smalltalk-dependency-repo"
    (repo_path / "src" / "Demo-App").mkdir(parents=True)
    (repo_path / "src" / "Demo-Core").mkdir(parents=True)
    (repo_path / ".smalltalk.ston").write_text("{ }\n", encoding="utf-8")
    (repo_path / "src" / "Demo-Core" / "package.st").write_text(
        "Package { #name : 'Demo-Core' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-Core" / "Helper.class.st").write_text(
        "Class {\n"
        "\t#name : 'Helper',\n"
        "\t#superclass : 'Object',\n"
        "\t#category : 'Demo-Core',\n"
        "\t#package : 'Demo-Core'\n"
        "}\n"
        "\n"
        "{ #category : 'rendering' }\n"
        "Helper class >> renderJson [\n"
        "\t^ '{}'\n"
        "]\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-App" / "package.st").write_text(
        "Package { #name : 'Demo-App' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-App" / "Main.class.st").write_text(
        "Class {\n"
        "\t#name : 'Main',\n"
        "\t#superclass : 'Object',\n"
        "\t#category : 'Demo-App',\n"
        "\t#package : 'Demo-App'\n"
        "}\n"
        "\n"
        "{ #category : 'running' }\n"
        "Main >> run [\n"
        "\t^ Helper renderJson\n"
        "]\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", ".smalltalk.ston"],
            include_patterns=["**/*.st", "*.st", "**/*.ston", "*.ston"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:src/Demo-App/Main.class.st"
        and str(row["target_node"]) == "file:src/Demo-Core/Helper.class.st"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/Demo-App/Main.class.st", "run")]
    render_symbol_id = symbol_ids[("src/Demo-Core/Helper.class.st", "renderJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_cfml_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cfml-dependency-repo"
    (repo_path / "config").mkdir(parents=True)
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "config" / "app.cfm").write_text(
        "<cfset request.ready = true />\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "UserService.cfc").write_text(
        "component {\n"
        "    function run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Application.cfc").write_text(
        "component {\n"
        '    include "config/app.cfm";\n'
        "    function onApplicationStart() {\n"
        "        local.userService = new models.UserService();\n"
        "        local.userService.run();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.cfc", "*.cfc", "**/*.cfm", "*.cfm"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:Application.cfc"
        and str(row["target_node"]) == "file:config/app.cfm"
        for row in graph_rows
    )
    on_application_start_symbol_id = symbol_ids[("Application.cfc", "onApplicationStart")]
    run_symbol_id = symbol_ids[("models/UserService.cfc", "run")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{on_application_start_symbol_id}"
        and str(row["target_node"]) == f"symbol:{run_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_awk_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "awk-dependency-repo"
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "math.awk").write_text(
        "function add(a, b) {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "translate").write_text(
        "#!/usr/bin/env gawk -f\n"
        '@include "../lib/math.awk"\n'
        "BEGIN {\n"
        "    print add(1, 2)\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["bin", "lib"],
            include_patterns=["bin/translate", "**/*.awk", "*.awk"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:bin/translate"
        and str(row["target_node"]) == "file:lib/math.awk"
        for row in graph_rows
    )
    begin_symbol_id = symbol_ids[("bin/translate", "BEGIN")]
    add_symbol_id = symbol_ids[("lib/math.awk", "add")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{begin_symbol_id}"
        and str(row["target_node"]) == f"symbol:{add_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_elm_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "elm-dependency-repo"
    (repo_path / "src" / "Page").mkdir(parents=True)
    (repo_path / "elm.json").write_text(
        json.dumps(
            {
                "type": "application",
                "source-directories": ["src"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "src" / "Page" / "Home.elm").write_text(
        "module Page.Home exposing (Model, homeView)\n\n"
        "type alias Model =\n"
        "    { title : String }\n\n"
        "homeView : Model -> String\n"
        "homeView model =\n"
        "    model.title\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.elm").write_text(
        "module Main exposing (main)\n\n"
        "import Page.Home exposing (Model, homeView)\n\n"
        "main : String\n"
        "main =\n"
        "    homeView { title = \"ok\" }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.elm", "src/*.elm", "elm.json"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/Main.elm"
        and str(row["target_node"]) == "file:src/Page/Home.elm"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/Main.elm", "main")]
    home_view_symbol_id = symbol_ids[("src/Page/Home.elm", "homeView")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{home_view_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_racket_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "racket-dependency-repo"
    (repo_path / "private").mkdir(parents=True)
    (repo_path / "info.rkt").write_text(
        "#lang info\n"
        '(define collection "racket-dependency-repo")\n',
        encoding="utf-8",
    )
    (repo_path / "private" / "helper.rkt").write_text(
        "#lang racket\n"
        "(define (helper) 1)\n",
        encoding="utf-8",
    )
    (repo_path / "main.rkt").write_text(
        "#lang racket\n"
        '(require "private/helper.rkt")\n'
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.rkt", "private/**/*.rkt", "private/*.rkt", "info.rkt"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.rkt"
        and str(row["target_node"]) == "file:private/helper.rkt"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("main.rkt", "run")]
    helper_symbol_id = symbol_ids[("private/helper.rkt", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_xpp_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "xpp-dependency-repo"
    (repo_path / "PackagesLocalDirectory" / "Acme" / "Acme" / "AxClass").mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
        / "BaseWorker.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>BaseWorker</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class BaseWorker\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "    <Methods>\n"
        "      <Method>\n"
        "        <Name>doWork</Name>\n"
        "        <Source><![CDATA[\n"
        "public static void doWork()\n"
        "{\n"
        "}\n"
        "]]></Source>\n"
        "      </Method>\n"
        "    </Methods>\n"
        "  </SourceCode>\n"
        "</AxClass>\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
        / "MainWorker.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>MainWorker</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class MainWorker extends BaseWorker\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "    <Methods>\n"
        "      <Method>\n"
        "        <Name>boot</Name>\n"
        "        <Source><![CDATA[\n"
        "public static void boot()\n"
        "{\n"
        "    BaseWorker::doWork();\n"
        "}\n"
        "]]></Source>\n"
        "      </Method>\n"
        "    </Methods>\n"
        "  </SourceCode>\n"
        "</AxClass>\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["PackagesLocalDirectory"],
            include_patterns=["**/*.xml", "*.xml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "extends"
        and str(row["source_node"])
        == "file:PackagesLocalDirectory/Acme/Acme/AxClass/MainWorker.xml"
        and str(row["target_node"])
        == "file:PackagesLocalDirectory/Acme/Acme/AxClass/BaseWorker.xml"
        for row in graph_rows
    )
    boot_symbol_id = symbol_ids[
        ("PackagesLocalDirectory/Acme/Acme/AxClass/MainWorker.xml", "boot")
    ]
    do_work_symbol_id = symbol_ids[
        ("PackagesLocalDirectory/Acme/Acme/AxClass/BaseWorker.xml", "doWork")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{boot_symbol_id}"
        and str(row["target_node"]) == f"symbol:{do_work_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scratch_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scratch-dependency-repo"
    _write_scratch_project(
        repo_path / "games" / "Maze.sb3",
        _scratch_project_payload(),
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["games"],
            include_patterns=["**/*.sb3", "*.sb3"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    init_symbol_id = symbol_ids[("games/Maze.sb3", "init")]
    start_symbol_id = symbol_ids[("games/Maze.sb3", "start")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{init_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{start_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_analyzes_scratch_project_json_when_archive_exceeds_size_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scratch-large-archive-repo"
    large_asset = b"".join(
        hashlib.sha256(f"scratch-asset-{index}".encode()).digest()
        for index in range(14_000)
    )
    _write_scratch_project(
        repo_path / "games" / "Large Maze.sb3",
        _scratch_project_payload(),
        extra_assets={"costumes/large.bin": large_asset},
    )
    assert (repo_path / "games" / "Large Maze.sb3").stat().st_size > 350_000
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["games"],
            include_patterns=["**/*.sb3", "*.sb3"],
            max_file_size_bytes=350_000,
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_names = {
        (str(row["file_path"]), str(row["symbol_name"]))
        for row in symbol_rows
    }

    assert ("games/Large Maze.sb3", "init") in symbol_names
    assert ("games/Large Maze.sb3", "start") in symbol_names


def test_repository_snapshot_graph_contains_tcl_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "tcl-dependency-repo"
    (repo_path / "modules" / "demo").mkdir(parents=True)
    (repo_path / "modules" / "demo" / "pkgIndex.tcl").write_text(
        "package ifneeded demo 1.0 [list source [file join $dir demo.tcl]]\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "demo" / "helpers.tcl").write_text(
        "package provide helpers 1.0\n"
        "namespace eval ::helpers {}\n"
        "proc ::helpers::run {} {\n"
        "    return ok\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "demo" / "demo.tcl").write_text(
        "package provide demo 1.0\n"
        "source helpers.tcl\n"
        "proc ::demo::main {} {\n"
        "    ::helpers::run\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["modules"],
            include_patterns=["**/*.tcl", "*.tcl", "**/*.tm", "*.tm"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:modules/demo/pkgIndex.tcl"
        and str(row["target_node"]) == "file:modules/demo/demo.tcl"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:modules/demo/demo.tcl"
        and str(row["target_node"]) == "file:modules/demo/helpers.tcl"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("modules/demo/demo.tcl", "main")]
    helper_symbol_id = symbol_ids[("modules/demo/helpers.tcl", "run")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_systemverilog_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "systemverilog-dependency-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "defs.svh").write_text(
        "package util_pkg;\n"
        "  function int helper();\n"
        "    return 1;\n"
        "  endfunction\n"
        "endpackage\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.sv").write_text(
        "module child;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.sv").write_text(
        '`include "defs.svh"\n'
        "import util_pkg::*;\n"
        "module top;\n"
        "  child u_child();\n"
        "  int value = util_pkg::helper();\n"
        "endmodule\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["rtl"],
            include_patterns=["**/*.sv", "*.sv", "**/*.svh", "*.svh", "**/*.v", "*.v"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:rtl/top.sv"
        and str(row["target_node"]) == "file:rtl/defs.svh"
        for row in graph_rows
    )
    top_symbol_id = symbol_ids[("rtl/top.sv", "top")]
    child_symbol_id = symbol_ids[("rtl/child.sv", "child")]
    helper_symbol_id = symbol_ids[("rtl/defs.svh", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{top_symbol_id}"
        and str(row["target_node"]) == f"symbol:{child_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{top_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_verilog_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "verilog-dependency-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "defs.vh").write_text(
        "function helper;\n"
        "endfunction\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.v").write_text(
        "module child;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.v").write_text(
        '`include "defs.vh"\n'
        "module top;\n"
        "  child u_child();\n"
        "  assign ready = helper;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["rtl"],
            include_patterns=["**/*.v", "*.v", "**/*.vh", "*.vh"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:rtl/top.v"
        and str(row["target_node"]) == "file:rtl/defs.vh"
        for row in graph_rows
    )
    top_symbol_id = symbol_ids[("rtl/top.v", "top")]
    child_symbol_id = symbol_ids[("rtl/child.v", "child")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{top_symbol_id}"
        and str(row["target_node"]) == f"symbol:{child_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_vhdl_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "vhdl-dependency-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "defs.vhd").write_text(
        "package util_pkg is\n"
        "  function helper return integer;\n"
        "end package;\n"
        "package body util_pkg is\n"
        "  function helper return integer is\n"
        "  begin\n"
        "    return 1;\n"
        "  end function;\n"
        "end package body;\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.vhd").write_text(
        "entity child is\n"
        "end entity;\n"
        "architecture rtl of child is\n"
        "begin\n"
        "end architecture;\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.vhd").write_text(
        "library work;\n"
        "use work.util_pkg.all;\n"
        "entity top is\n"
        "end entity;\n"
        "architecture rtl of top is\n"
        "begin\n"
        "  u_child: entity work.child port map();\n"
        "  value_proc: process is\n"
        "    variable value : integer := util_pkg.helper;\n"
        "  begin\n"
        "    wait;\n"
        "  end process;\n"
        "end architecture;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["rtl"],
            include_patterns=["**/*.vhd", "*.vhd", "**/*.vhdl", "*.vhdl"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:rtl/top.vhd"
        and str(row["target_node"]) == "file:rtl/defs.vhd"
        for row in graph_rows
    )
    top_arch_symbol_id = symbol_ids[("rtl/top.vhd", "top.rtl")]
    child_symbol_id = symbol_ids[("rtl/child.vhd", "child")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{top_arch_symbol_id}"
        and str(row["target_node"]) == f"symbol:{child_symbol_id}"
        for row in graph_rows
    )
    helper_symbol_ids = {
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "rtl/defs.vhd" and str(row["symbol_name"]) == "helper"
    }
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{top_arch_symbol_id}"
        and str(row["target_node"]) in {f"symbol:{symbol_id}" for symbol_id in helper_symbol_ids}
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_gdscript_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "gdscript-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "base_actor.gd").write_text(
        "class_name BaseActor\n"
        "extends Node\n"
        "func base_ready() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "utils.gd").write_text(
        "class_name Utils\n"
        "extends RefCounted\n"
        "func helper() -> int:\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "player.gd").write_text(
        "class_name Player\n"
        'extends "res://src/base_actor.gd"\n'
        'const UtilsRef = preload("res://src/utils.gd")\n'
        "func _ready() -> void:\n"
        "    UtilsRef.helper()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["**/*.gd", "*.gd", "project.godot"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "extends"
        and str(row["source_node"]) == "file:src/player.gd"
        and str(row["target_node"]) == "file:src/base_actor.gd"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/player.gd"
        and str(row["target_node"]) == "file:src/utils.gd"
        for row in graph_rows
    )
    ready_symbol_id = symbol_ids[("src/player.gd", "_ready")]
    helper_symbol_id = symbol_ids[("src/utils.gd", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{ready_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_gml_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "gml-dependency-repo"
    (repo_path / "scripts" / "tree_runtime").mkdir(parents=True)
    (repo_path / "scripts" / "tree_api").mkdir(parents=True)
    (repo_path / "objects" / "Entity").mkdir(parents=True)
    (repo_path / "scripts" / "tree_runtime" / "tree_runtime.gml").write_text(
        "function __BHTree() constructor {\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "tree_api" / "tree_api.gml").write_text(
        "function bh_tree() {\n"
        "    return new __BHTree();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "objects" / "Entity" / "Create_0.gml").write_text(
        "function setup() {\n"
        "    return bh_tree();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts", "objects"],
            include_patterns=["**/*.gml", "*.gml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:objects/Entity/Create_0.gml"
        and str(row["target_node"]) == "file:scripts/tree_api/tree_api.gml"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:scripts/tree_api/tree_api.gml"
        and str(row["target_node"]) == "file:scripts/tree_runtime/tree_runtime.gml"
        for row in graph_rows
    )
    setup_symbol_id = symbol_ids[("objects/Entity/Create_0.gml", "setup")]
    tree_factory_symbol_id = symbol_ids[("scripts/tree_api/tree_api.gml", "bh_tree")]
    tree_api_symbol_id = symbol_ids[("scripts/tree_api/tree_api.gml", "tree_api")]
    runtime_symbol_id = symbol_ids[("scripts/tree_runtime/tree_runtime.gml", "__BHTree")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{setup_symbol_id}"
        and str(row["target_node"]) == f"symbol:{tree_factory_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{tree_api_symbol_id}"
        and str(row["target_node"]) == f"symbol:{runtime_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_vbscript_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "vbscript-dependency-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "helper.vbs").write_text(
        "Class Helper\n"
        "    Public Sub Run()\n"
        "    End Sub\n"
        "End Class\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.wsf").write_text(
        "<job>\n"
        '  <script language="VBScript" src="lib/helper.vbs"></script>\n'
        '  <script language="VBScript">\n'
        "    Option Explicit\n"
        "    Sub Main()\n"
        "        Dim helper\n"
        "        Set helper = New Helper\n"
        "        helper.Run()\n"
        "    End Sub\n"
        "  </script>\n"
        "</job>\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts"],
            include_patterns=["scripts/**/*.vbs", "scripts/**/*.wsf", "scripts/*.vbs", "scripts/*.wsf"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:scripts/main.wsf"
        and str(row["target_node"]) == "file:scripts/lib/helper.vbs"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("scripts/main.wsf", "Main")]
    helper_symbol_id = symbol_ids[("scripts/lib/helper.vbs", "Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_applescript_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "applescript-dependency-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "Helper.applescript").write_text(
        "script HelperScript\n"
        "    on renderJson(value)\n"
        "        return value\n"
        "    end renderJson\n"
        "end script\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "Main.applescript").write_text(
        'property helperScript : load script POSIX file "lib/Helper.applescript"\n'
        "\n"
        "on run\n"
        "    helperScript's renderJson(\"{}\")\n"
        "end run\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts"],
            include_patterns=[
                "scripts/**/*.applescript",
                "scripts/*.applescript",
                "scripts/**/*.scpt",
                "scripts/*.scpt",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:scripts/Main.applescript"
        and str(row["target_node"]) == "file:scripts/lib/Helper.applescript"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("scripts/Main.applescript", "run")]
    render_symbol_id = symbol_ids[("scripts/lib/Helper.applescript", "renderJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_rpg_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "rpg-dependency-repo"
    (repo_path / "QRPGLESRC").mkdir(parents=True)
    (repo_path / "QPROTOSRC").mkdir(parents=True)
    (repo_path / "iproj.json").write_text(
        '{\n'
        '  "includePath": ["QPROTOSRC"]\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "QPROTOSRC" / "CUSTOMER.RPGLEINC").write_text(
        "dcl-ds Customer qualified;\n"
        "   id packed(5);\n"
        "end-ds;\n",
        encoding="utf-8",
    )
    (repo_path / "QRPGLESRC" / "ORD101.PGM.RPGLE").write_text(
        "**free\n"
        "dcl-proc Updord export;\n"
        "   dcl-pi *n ind;\n"
        "      id packed(5);\n"
        "   end-pi;\n"
        "   return *on;\n"
        "end-proc;\n",
        encoding="utf-8",
    )
    (repo_path / "QRPGLESRC" / "ORD100.PGM.RPGLE").write_text(
        "**free\n"
        "/copy CUSTOMER.RPGLEINC\n"
        "dcl-pr Updord extpgm('ORD101');\n"
        "   id packed(5);\n"
        "end-pr;\n"
        "dcl-proc Run export;\n"
        "   dcl-pi *n;\n"
        "   end-pi;\n"
        "   return Updord(1);\n"
        "end-proc;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["QRPGLESRC", "QPROTOSRC"],
            include_patterns=[
                "QRPGLESRC/**/*.RPGLE",
                "QRPGLESRC/*.RPGLE",
                "QPROTOSRC/**/*.RPGLEINC",
                "QPROTOSRC/*.RPGLEINC",
                "iproj.json",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:QRPGLESRC/ORD100.PGM.RPGLE"
        and str(row["target_node"]) == "file:QPROTOSRC/CUSTOMER.RPGLEINC"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:QRPGLESRC/ORD100.PGM.RPGLE"
        and str(row["target_node"]) == "file:QRPGLESRC/ORD101.PGM.RPGLE"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("QRPGLESRC/ORD100.PGM.RPGLE", "Run")]
    updord_symbol_id = symbol_ids[("QRPGLESRC/ORD101.PGM.RPGLE", "Updord")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{updord_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_apex_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "apex-dependency-repo"
    (repo_path / "force-app" / "main" / "default" / "classes").mkdir(parents=True)
    (repo_path / "force-app" / "main" / "default" / "triggers").mkdir(parents=True)
    (repo_path / "sfdx-project.json").write_text(
        '{\n'
        '  "packageDirectories": [\n'
        '    { "path": "force-app", "default": true }\n'
        "  ],\n"
        '  "sourceApiVersion": "60.0"\n'
        '}\n',
        encoding="utf-8",
    )
    (
        repo_path
        / "force-app"
        / "main"
        / "default"
        / "classes"
        / "AccountTriggerHandler.cls"
    ).write_text(
        "public with sharing class AccountTriggerHandler {\n"
        "    public static void run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "force-app"
        / "main"
        / "default"
        / "triggers"
        / "AccountTrigger.trigger"
    ).write_text(
        "trigger AccountTrigger on Account (before insert) {\n"
        "    AccountTriggerHandler.run();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["force-app"],
            include_patterns=[
                "force-app/**/*.cls",
                "force-app/**/*.trigger",
                "sfdx-project.json",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"])
        == "file:force-app/main/default/triggers/AccountTrigger.trigger"
        and str(row["target_node"])
        == "file:force-app/main/default/classes/AccountTriggerHandler.cls"
        for row in graph_rows
    )
    trigger_symbol_id = symbol_ids[
        ("force-app/main/default/triggers/AccountTrigger.trigger", "AccountTrigger")
    ]
    handler_symbol_id = symbol_ids[
        ("force-app/main/default/classes/AccountTriggerHandler.cls", "AccountTriggerHandler")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{trigger_symbol_id}"
        and str(row["target_node"]) == f"symbol:{handler_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_wolfram_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "wolfram-dependency-repo"
    (repo_path / "Kernel").mkdir(parents=True)
    (repo_path / "PacletInfo.wl").write_text(
        'PacletObject[<|"Name" -> "Acme/Test", "Extensions" -> {{"Kernel", "Root" -> "Kernel", "Context" -> {"Acme`"}}}|>]\n',
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "init.m").write_text(
        'Get["Acme`Main`"];\n',
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "Main.wl").write_text(
        'BeginPackage["Acme`", {"Acme`Helpers`"}];\n'
        'run::usage = "run";\n'
        'Begin["`Private`"];\n'
        "run[] := helper[];\n"
        "End[];\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "Helpers.wl").write_text(
        'BeginPackage["Acme`"];\n'
        'helper::usage = "helper";\n'
        'Begin["`Private`"];\n'
        "helper[] := 1;\n"
        "End[];\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Kernel"],
            include_patterns=["Kernel/**/*.wl", "Kernel/**/*.m", "PacletInfo.wl"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "loads"
        and str(row["source_node"]) == "file:Kernel/init.m"
        and str(row["target_node"]) == "file:Kernel/Main.wl"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:Kernel/Main.wl"
        and str(row["target_node"]) == "file:Kernel/Helpers.wl"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("Kernel/Main.wl", "run")]
    helper_symbol_id = symbol_ids[("Kernel/Helpers.wl", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_fsharp_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "fsharp-dependency-repo"
    (repo_path / "src" / "Acme").mkdir(parents=True)
    (repo_path / "src" / "Acme" / "Core.fs").write_text(
        "namespace Acme\n\n"
        "type Request = { Name: string }\n\n"
        "module RequestOps =\n"
        "    let render (request: Request) = request.Name\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme" / "Http.fs").write_text(
        "namespace Acme\n\n"
        "open Acme\n\n"
        "module Http =\n"
        "    let handle (request: Request) = RequestOps.render request\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.fs"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:src/Acme/Http.fs"
        and str(row["target_node"]) == "file:src/Acme/Core.fs"
        for row in graph_rows
    )

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    handle_symbol_id = symbol_ids[("src/Acme/Http.fs", "handle")]
    render_symbol_id = symbol_ids[("src/Acme/Core.fs", "render")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{handle_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_fortran_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "fortran-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "fpm.toml").write_text(
        'name = "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "math_utils.f90").write_text(
        "module math_utils\n"
        "implicit none\n"
        "contains\n"
        "subroutine helper()\n"
        "end subroutine helper\n"
        "end module math_utils\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.f90").write_text(
        "program main\n"
        "use math_utils, only: helper\n"
        "implicit none\n"
        "call helper()\n"
        "end program main\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "fpm.toml"],
            include_patterns=["src/**/*.f90", "src/**/*.f95", "src/**/*.f03", "src/**/*.f08", "src/**/*.f", "src/**/*.for", "fpm.toml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.f90"
        and str(row["target_node"]) == "file:src/math_utils.f90"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/main.f90", "main")]
    helper_symbol_id = symbol_ids[("src/math_utils.f90", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_d_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "d-dependency-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "dub.json").write_text(
        '{\n  "name": "acme"\n}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "utils.d").write_text(
        "module acme.utils;\n"
        "int helper() {\n"
        "    return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "main.d").write_text(
        "module acme.main;\n"
        "import acme.utils : helper;\n"
        "int main() {\n"
        "    return helper();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "dub.json"],
            include_patterns=["src/**/*.d", "src/*.d", "dub.json", "dub.sdl"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/acme/main.d"
        and str(row["target_node"]) == "file:src/acme/utils.d"
        for row in graph_rows
    )

    main_symbol_id = symbol_ids[("src/acme/main.d", "main")]
    helper_symbol_id = symbol_ids[("src/acme/utils.d", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_matlab_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "matlab-dependency-repo"
    (repo_path / "+acme").mkdir(parents=True)
    (repo_path / "+acme" / "helper.m").write_text(
        "function value = helper()\n"
        "value = 1;\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "main.m").write_text(
        "function value = main()\n"
        "import acme.helper\n"
        "value = helper();\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.m", "+acme"],
            include_patterns=["**/*.m", "*.m"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.m"
        and str(row["target_node"]) == "file:+acme/helper.m"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("main.m", "main")]
    helper_symbol_id = symbol_ids[("+acme/helper.m", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_objective_c_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "objective-c-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "ACMHelper.h").write_text(
        "#import <Foundation/Foundation.h>\n"
        "@interface ACMHelper : NSObject\n"
        "+ (void)work;\n"
        "@end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "ACMClient.m").write_text(
        "#import \"ACMHelper.h\"\n"
        "@interface ACMClient : NSObject\n"
        "- (void)run;\n"
        "@end\n"
        "@implementation ACMClient\n"
        "- (void)run {\n"
        "    [ACMHelper work];\n"
        "}\n"
        "@end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.h", "src/*.h", "src/**/*.m", "src/*.m"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/ACMClient.m"
        and str(row["target_node"]) == "file:src/ACMHelper.h"
        for row in graph_rows
    )
    client_run_symbol_id = symbol_ids[("src/ACMClient.m", "run")]
    helper_work_symbol_id = symbol_ids[("src/ACMHelper.h", "work")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{client_run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_work_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_prolog_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "prolog-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "family.pl").write_text(
        ":- module(family, [ancestor/2, parent/2]).\n"
        "parent(alice, bob).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "related.pl").write_text(
        ":- use_module('family.pl', [ancestor/2]).\n"
        "related(X, Y) :- ancestor(X, Y).\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=[
                "src/**/*.pl",
                "src/*.pl",
                "src/**/*.prolog",
                "src/*.prolog",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/related.pl"
        and str(row["target_node"]) == "file:src/family.pl"
        for row in graph_rows
    )
    related_symbol_id = symbol_ids[("src/related.pl", "related")]
    ancestor_symbol_id = symbol_ids[("src/family.pl", "ancestor")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{related_symbol_id}"
        and str(row["target_node"]) == f"symbol:{ancestor_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_ml_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ml-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "project.mlb").write_text(
        "src/Util.sml\n"
        "src/Main.sml\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Util.sml").write_text(
        "structure Util = struct\n"
        "fun helper () = 1\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.sml").write_text(
        "structure Main = struct\n"
        "open Util\n"
        "val run = helper ()\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "project.mlb"],
            include_patterns=[
                "src/**/*.sml",
                "src/*.sml",
                "src/**/*.sig",
                "src/*.sig",
                "src/**/*.fun",
                "src/*.fun",
                "*.mlb",
                "*.cm",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "open"
        and str(row["source_node"]) == "file:src/Main.sml"
        and str(row["target_node"]) == "file:src/Util.sml"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/Main.sml", "run")]
    helper_symbol_id = symbol_ids[("src/Util.sml", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_vba_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "vba-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "JsonData.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "JsonData"\n'
        "Option Explicit\n"
        "\n"
        "Public Function ToJson() As String\n"
        '    ToJson = "{}"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "JsonConverter.bas").write_text(
        'Attribute VB_Name = "JsonConverter"\n'
        "Option Explicit\n"
        "\n"
        "Public Sub Main()\n"
        "    Dim data As JsonData\n"
        "    Set data = New JsonData\n"
        "    Debug.Print data.ToJson()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.bas", "src/*.bas", "src/**/*.cls", "src/*.cls"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:src/JsonConverter.bas"
        and str(row["target_node"]) == "file:src/JsonData.cls"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/JsonConverter.bas", "Main")]
    to_json_symbol_id = symbol_ids[("src/JsonData.cls", "ToJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{to_json_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_classic_visual_basic_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "vb6-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project1.vbp").write_text(
        'Type=Exe\n'
        'Class=cHelper; src/cHelper.cls\n'
        'Module=modMain; src/modMain.bas\n'
        'Form=src/Form1.frm\n'
        'Startup="Form1"\n'
        'Name="Project1"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "cHelper.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "cHelper"\n'
        "Option Explicit\n"
        "\n"
        "Public Function Helper() As String\n"
        '    Helper = "ok"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "modMain.bas").write_text(
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "\n"
        "Public Sub RunApp()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Form1.frm").write_text(
        "VERSION 5.00\n"
        "Begin VB.Form Form1\n"
        '   Caption = "Form1"\n'
        "End\n"
        'Attribute VB_Name = "Form1"\n'
        "Option Explicit\n"
        "\n"
        "Private mHelper As cHelper\n"
        "\n"
        "Private Sub Form_Load()\n"
        "    Set mHelper = New cHelper\n"
        "    Debug.Print mHelper.Helper()\n"
        "    modMain.RunApp\n"
        "End Sub\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "Project1.vbp"],
            include_patterns=[
                "src/**/*.bas",
                "src/*.bas",
                "src/**/*.cls",
                "src/*.cls",
                "src/**/*.frm",
                "src/*.frm",
                "*.vbp",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:src/Form1.frm"
        and str(row["target_node"]) == "file:src/cHelper.cls"
        for row in graph_rows
    )
    form_load_symbol_id = symbol_ids[("src/Form1.frm", "Form_Load")]
    helper_symbol_id = symbol_ids[("src/cHelper.cls", "Helper")]
    run_app_symbol_id = symbol_ids[("src/modMain.bas", "RunApp")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{form_load_symbol_id}"
        and str(row["target_node"]) in {
            f"symbol:{helper_symbol_id}",
            f"symbol:{run_app_symbol_id}",
        }
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_lisp_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "lisp-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "acme.asd").write_text(
        '(asdf:defsystem "acme"\n'
        '  :pathname "src"\n'
        '  :components ((:file "helper") (:file "app")))\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "helper.lisp").write_text(
        "(defpackage #:acme.helper (:use #:cl) (:export #:helper))\n"
        "(in-package #:acme.helper)\n"
        "(defun helper () 1)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "app.lisp").write_text(
        "(defpackage #:acme.app (:use #:cl) (:import-from #:acme.helper #:helper))\n"
        "(in-package #:acme.app)\n"
        "(defun run () (helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "acme.asd"],
            include_patterns=["src/**/*.lisp", "src/*.lisp", "*.asd"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:src/app.lisp"
        and str(row["target_node"]) == "file:src/helper.lisp"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/app.lisp", "run")]
    helper_symbol_id = symbol_ids[("src/helper.lisp", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_emacslisp_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "emacslisp-dependency-repo"
    (repo_path / "lisp").mkdir(parents=True)
    (repo_path / "lisp" / "helper.el").write_text(
        "(provide 'helper)\n"
        "(defun helper-fn () 1)\n",
        encoding="utf-8",
    )
    (repo_path / "main.el").write_text(
        "(require 'helper)\n"
        "(provide 'main)\n"
        "(defun run () (helper-fn))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.el", "lisp"],
            include_patterns=["*.el", "lisp/**/*.el", "lisp/*.el"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:main.el"
        and str(row["target_node"]) == "file:lisp/helper.el"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("main.el", "run")]
    helper_symbol_id = symbol_ids[("lisp/helper.el", "helper-fn")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scheme_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scheme-dependency-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "package.scm").write_text(
        "(define-library (acme app)\n"
        "  (export run)\n"
        "  (import (acme helper))\n"
        "  (begin\n"
        "    (define (run) (helper))))\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "helper.sld").write_text(
        "(define-library (acme helper)\n"
        "  (export helper)\n"
        "  (begin\n"
        "    (define (helper) 1)))\n",
        encoding="utf-8",
    )
    (repo_path / "main.scm").write_text(
        "#!r6rs\n"
        "(import (acme helper))\n"
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.scm", "package.scm", "lib"],
            include_patterns=["*.scm", "lib/**/*.sld", "lib/*.sld", "*.sld"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:main.scm"
        and str(row["target_node"]) == "file:lib/acme/helper.sld"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("main.scm", "run")]
    helper_symbol_id = symbol_ids[("lib/acme/helper.sld", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_assembly_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "assembly-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "include" / "io.inc").write_text(
        "extern print_string\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "io.asm").write_text(
        "global print_string\n"
        "print_string:\n"
        "    ret\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.asm").write_text(
        "%include \"../include/io.inc\"\n"
        "global main\n"
        "main:\n"
        "    call print_string\n"
        "    ret\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "include"],
            include_patterns=[
                "src/**/*.asm",
                "src/*.asm",
                "include/**/*.inc",
                "include/*.inc",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.asm"
        and str(row["target_node"]) == "file:include/io.inc"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/main.asm", "main")]
    print_string_symbol_id = symbol_ids[("src/io.asm", "print_string")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{print_string_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_sql_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "sql-dependency-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "dbt_project.yml").write_text(
        "name: acme\n"
        "model-paths:\n"
        "  - models\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "customers.sql").write_text(
        "create table customers as\n"
        "select 1 as id;\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "orders.sql").write_text(
        "select * from {{ ref('customers') }}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["models", "dbt_project.yml"],
            include_patterns=["models/**/*.sql", "models/*.sql", "dbt_project.yml"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:models/orders.sql"
        and str(row["target_node"]) == "file:models/customers.sql"
        for row in graph_rows
    )

    orders_symbol_id = symbol_ids[("models/orders.sql", "orders")]
    customers_symbol_id = symbol_ids[("models/customers.sql", "customers")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{orders_symbol_id}"
        and str(row["target_node"]) == f"symbol:{customers_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_tsql_execute_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "tsql-dependency-repo"
    (repo_path / "database" / "dbo" / "Stored Procedures").mkdir(parents=True)
    (repo_path / "database" / "Acme.sqlproj").write_text(
        "<Project>\n"
        "  <ItemGroup>\n"
        '    <Build Include="dbo\\Stored Procedures\\LoadCustomers.sql" />\n'
        '    <Build Include="dbo\\Stored Procedures\\LoadOrders.sql" />\n'
        "  </ItemGroup>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (
        repo_path / "database" / "dbo" / "Stored Procedures" / "LoadCustomers.sql"
    ).write_text(
        "create or alter procedure dbo.LoadCustomers\n"
        "as\n"
        "begin\n"
        "    set nocount on;\n"
        "    select 1 as id;\n"
        "end\n"
        "go\n",
        encoding="utf-8",
    )
    (repo_path / "database" / "dbo" / "Stored Procedures" / "LoadOrders.sql").write_text(
        "create or alter procedure dbo.LoadOrders\n"
        "as\n"
        "begin\n"
        "    set nocount on;\n"
        "    exec dbo.LoadCustomers;\n"
        "end\n"
        "go\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["database"],
            include_patterns=["database/**/*.sql", "database/*.sql", "database/*.sqlproj"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:database/dbo/Stored Procedures/LoadOrders.sql"
        and str(row["target_node"])
        == "file:database/dbo/Stored Procedures/LoadCustomers.sql"
        for row in graph_rows
    )

    orders_symbol_id = symbol_ids[
        ("database/dbo/Stored Procedures/LoadOrders.sql", "loadorders")
    ]
    customers_symbol_id = symbol_ids[
        ("database/dbo/Stored Procedures/LoadCustomers.sql", "loadcustomers")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{orders_symbol_id}"
        and str(row["target_node"]) == f"symbol:{customers_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_csharp_same_namespace_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "csharp-same-namespace-repo"
    (repo_path / "src" / "MediatR").mkdir(parents=True)
    (repo_path / "src" / "MediatR" / "IMediator.cs").write_text(
        "namespace MediatR; public interface IMediator {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "MediatR" / "Mediator.cs").write_text(
        "namespace MediatR; public class Mediator : IMediator {}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.cs"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:src/MediatR/Mediator.cs"
        and str(row["target_node"]) == "file:src/MediatR/IMediator.cs"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_java_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "java-dependency-repo"
    package_dir = repo_path / "src" / "main" / "java" / "org" / "example"
    package_dir.mkdir(parents=True)
    (package_dir / "Owner.java").write_text(
        "package org.example;\npublic class Owner {}\n",
        encoding="utf-8",
    )
    (package_dir / "OwnerController.java").write_text(
        "package org.example;\nimport org.example.Owner;\npublic class OwnerController { private Owner owner; }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/java"],
            include_patterns=["src/main/java/**/*.java"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main/java/org/example/OwnerController.java"
        and str(row["target_node"]) == "file:src/main/java/org/example/Owner.java"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_java_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "java-symbol-repo"
    package_dir = repo_path / "src" / "main" / "java" / "org" / "example"
    package_dir.mkdir(parents=True)
    (package_dir / "Owner.java").write_text(
        "package org.example;\npublic class Owner {}\n",
        encoding="utf-8",
    )
    (package_dir / "OwnerController.java").write_text(
        "package org.example;\n"
        "import org.example.Owner;\n"
        "public class OwnerController { private Owner owner; }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/java"],
            include_patterns=["src/main/java/**/*.java"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    controller_symbol_id = symbol_ids[
        ("src/main/java/org/example/OwnerController.java", "OwnerController")
    ]
    owner_symbol_id = symbol_ids[("src/main/java/org/example/Owner.java", "Owner")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{controller_symbol_id}"
        and str(row["target_node"]) == f"symbol:{owner_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_kotlin_same_package_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "kotlin-dependency-repo"
    package_dir = repo_path / "src" / "main" / "kotlin" / "com" / "example"
    package_dir.mkdir(parents=True)
    (package_dir / "BlogProperties.kt").write_text(
        "package com.example\n"
        "data class BlogProperties(val title: String)\n",
        encoding="utf-8",
    )
    (package_dir / "BlogConfiguration.kt").write_text(
        "package com.example\n"
        "class BlogConfiguration(private val properties: BlogProperties)\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/kotlin"],
            include_patterns=["src/main/kotlin/**/*.kt"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:src/main/kotlin/com/example/BlogConfiguration.kt"
        and str(row["target_node"]) == "file:src/main/kotlin/com/example/BlogProperties.kt"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_kotlin_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "kotlin-symbol-repo"
    package_dir = repo_path / "src" / "main" / "kotlin" / "com" / "example"
    package_dir.mkdir(parents=True)
    (package_dir / "BlogProperties.kt").write_text(
        "package com.example\n"
        "data class BlogProperties(val title: String)\n",
        encoding="utf-8",
    )
    (package_dir / "BlogConfiguration.kt").write_text(
        "package com.example\n"
        "class BlogConfiguration(private val properties: BlogProperties)\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/kotlin"],
            include_patterns=["src/main/kotlin/**/*.kt"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    config_symbol_id = symbol_ids[
        ("src/main/kotlin/com/example/BlogConfiguration.kt", "BlogConfiguration")
    ]
    properties_symbol_id = symbol_ids[
        ("src/main/kotlin/com/example/BlogProperties.kt", "BlogProperties")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{config_symbol_id}"
        and str(row["target_node"]) == f"symbol:{properties_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_kotlin_multi_type_file_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "kotlin-multi-type-symbol-repo"
    package_dir = repo_path / "src" / "main" / "kotlin" / "com" / "example"
    package_dir.mkdir(parents=True)
    (package_dir / "Repositories.kt").write_text(
        "package com.example\n"
        "interface ArticleRepository\n"
        "interface UserRepository\n",
        encoding="utf-8",
    )
    (package_dir / "Controllers.kt").write_text(
        "package com.example\n"
        "class HtmlController(\n"
        "    private val articleRepository: ArticleRepository,\n"
        "    private val userRepository: UserRepository,\n"
        ")\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/kotlin"],
            include_patterns=["src/main/kotlin/**/*.kt"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    controller_symbol_id = symbol_ids[
        ("src/main/kotlin/com/example/Controllers.kt", "HtmlController")
    ]
    article_repository_symbol_id = symbol_ids[
        ("src/main/kotlin/com/example/Repositories.kt", "ArticleRepository")
    ]
    user_repository_symbol_id = symbol_ids[
        ("src/main/kotlin/com/example/Repositories.kt", "UserRepository")
    ]
    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:src/main/kotlin/com/example/Controllers.kt"
        and str(row["target_node"]) == "file:src/main/kotlin/com/example/Repositories.kt"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{controller_symbol_id}"
        and str(row["target_node"]) == f"symbol:{article_repository_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{controller_symbol_id}"
        and str(row["target_node"]) == f"symbol:{user_repository_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scala_grouped_import_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scala-grouped-import-repo"
    core_dir = repo_path / "src" / "main" / "scala" / "upickle" / "core"
    upack_dir = repo_path / "src" / "main" / "scala" / "upack"
    core_dir.mkdir(parents=True)
    upack_dir.mkdir(parents=True)
    (core_dir / "Visitor.scala").write_text(
        "package upickle.core\ntrait Visitor\n",
        encoding="utf-8",
    )
    (core_dir / "BufferingInputStreamParser.scala").write_text(
        "package upickle.core\nobject BufferingInputStreamParser\n",
        encoding="utf-8",
    )
    (upack_dir / "MsgPackReader.scala").write_text(
        "package upack\n"
        "import upickle.core.{BufferingInputStreamParser, Visitor}\n"
        "object MsgPackReader {\n"
        "  val parser = BufferingInputStreamParser\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/scala"],
            include_patterns=["src/main/scala/**/*.scala"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main/scala/upack/MsgPackReader.scala"
        and str(row["target_node"]) == "file:src/main/scala/upickle/core/BufferingInputStreamParser.scala"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main/scala/upack/MsgPackReader.scala"
        and str(row["target_node"]) == "file:src/main/scala/upickle/core/Visitor.scala"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scala_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scala-symbol-repo"
    core_dir = repo_path / "src" / "main" / "scala" / "upickle" / "core"
    upack_dir = repo_path / "src" / "main" / "scala" / "upack"
    core_dir.mkdir(parents=True)
    upack_dir.mkdir(parents=True)
    (core_dir / "Visitor.scala").write_text(
        "package upickle.core\ntrait Visitor\n",
        encoding="utf-8",
    )
    (upack_dir / "MsgPackReader.scala").write_text(
        "package upack\n"
        "import upickle.core.Visitor\n"
        "object MsgPackReader {\n"
        "  def render(visitor: Visitor): Visitor = visitor\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/scala"],
            include_patterns=["src/main/scala/**/*.scala"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    reader_symbol_id = symbol_ids[("src/main/scala/upack/MsgPackReader.scala", "MsgPackReader")]
    visitor_symbol_id = symbol_ids[("src/main/scala/upickle/core/Visitor.scala", "Visitor")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{reader_symbol_id}"
        and str(row["target_node"]) == f"symbol:{visitor_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scala_package_wildcard_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scala-package-wildcard-repo"
    syntax_dir = (
        repo_path
        / "src"
        / "main"
        / "scala"
        / "play"
        / "api"
        / "libs"
        / "functional"
        / "syntax"
    )
    functional_dir = syntax_dir.parent
    syntax_dir.mkdir(parents=True)
    functional_dir.mkdir(parents=True, exist_ok=True)
    (syntax_dir / "package.scala").write_text(
        "package play.api.libs.functional.syntax\n"
        "object SyntaxOps\n",
        encoding="utf-8",
    )
    (functional_dir / "UseSyntax.scala").write_text(
        "package play.api.libs.functional\n"
        "import play.api.libs.functional.syntax._\n"
        "object UseSyntax {\n"
        "  val syntax = SyntaxOps\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/scala"],
            include_patterns=["src/main/scala/**/*.scala"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main/scala/play/api/libs/functional/UseSyntax.scala"
        and str(row["target_node"]) == "file:src/main/scala/play/api/libs/functional/syntax/package.scala"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scala_package_alias_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scala-package-alias-repo"
    source_dir = repo_path / "os" / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "Path.scala").write_text(
        "package os\nobject Path\n",
        encoding="utf-8",
    )
    (source_dir / "ProcessOps.scala").write_text(
        "package os\n"
        "import os.Path\n"
        "object ProcessOps {\n"
        "  val path = Path\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["os/src"],
            include_patterns=["os/src/**/*.scala"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:os/src/ProcessOps.scala"
        and str(row["target_node"]) == "file:os/src/Path.scala"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_groovy_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "groovy-dependency-repo"
    source_dir = repo_path / "src" / "main" / "groovy" / "org" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "Owner.groovy").write_text(
        "package org.example\n"
        "class Owner {}\n",
        encoding="utf-8",
    )
    (source_dir / "OwnerController.groovy").write_text(
        "package org.example\n"
        "import org.example.Owner as PetOwner\n"
        "class OwnerController {\n"
        "  PetOwner owner\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/groovy"],
            include_patterns=["src/main/groovy/**/*.groovy"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main/groovy/org/example/OwnerController.groovy"
        and str(row["target_node"]) == "file:src/main/groovy/org/example/Owner.groovy"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_groovy_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "groovy-symbol-repo"
    source_dir = repo_path / "src" / "main" / "groovy" / "org" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "Owner.groovy").write_text(
        "package org.example\n"
        "class Owner {}\n",
        encoding="utf-8",
    )
    (source_dir / "OwnerController.groovy").write_text(
        "package org.example\n"
        "import org.example.Owner as PetOwner\n"
        "class OwnerController {\n"
        "  PetOwner owner\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/groovy"],
            include_patterns=["src/main/groovy/**/*.groovy"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    controller_symbol_id = symbol_ids[
        ("src/main/groovy/org/example/OwnerController.groovy", "OwnerController")
    ]
    owner_symbol_id = symbol_ids[("src/main/groovy/org/example/Owner.groovy", "Owner")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{controller_symbol_id}"
        and str(row["target_node"]) == f"symbol:{owner_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_haskell_module_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "haskell-module-repo"
    source_dir = repo_path / "src" / "Text"
    legacy_dir = source_dir / "ParserCombinators"
    legacy_dir.mkdir(parents=True)
    (repo_path / "parsec.cabal").write_text(
        "name: parsec\n"
        "version: 1.0.0.0\n"
        "library\n"
        "  hs-source-dirs: src\n"
        "  exposed-modules: Text.Parsec, Text.ParserCombinators.Parsec\n",
        encoding="utf-8",
    )
    (source_dir / "Parsec.hs").write_text(
        "module Text.Parsec where\n"
        "data Parser = Parser\n"
        'instance Show Parser where show _ = "Parser"\n',
        encoding="utf-8",
    )
    (legacy_dir / "Parsec.hs").write_text(
        "module Text.ParserCombinators.Parsec where\n"
        "import qualified Text.Parsec as P\n"
        "parser :: P.Parser\n"
        "parser = P.Parser\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.hs", "*.cabal"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    parser_symbol_id = symbol_ids[("src/Text/ParserCombinators/Parsec.hs", "parser")]
    data_symbol_id = symbol_ids[("src/Text/Parsec.hs", "Parser")]

    assert ("src/Text/Parsec.hs", "instance") not in symbol_ids
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/Text/ParserCombinators/Parsec.hs"
        and str(row["target_node"]) == "file:src/Text/Parsec.hs"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{parser_symbol_id}"
        and str(row["target_node"]) == f"symbol:{data_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_haskell_unqualified_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "haskell-unqualified-symbol-repo"
    source_dir = repo_path / "src" / "Text"
    source_dir.mkdir(parents=True)
    (repo_path / "sample.cabal").write_text(
        "name: sample\n"
        "version: 1.0.0.0\n"
        "library\n"
        "  hs-source-dirs: src\n"
        "  exposed-modules: Text.Foo, Text.Bar\n",
        encoding="utf-8",
    )
    (source_dir / "Foo.hs").write_text(
        "module Text.Foo where\n"
        "data Parser = Parser\n"
        "render :: Parser -> String\n"
        'render _ = "ok"\n',
        encoding="utf-8",
    )
    (source_dir / "Bar.hs").write_text(
        "module Text.Bar where\n"
        "import Text.Foo\n"
        "useParser :: Parser -> String\n"
        "useParser input = render input\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.hs", "*.cabal"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    use_parser_symbol_id = symbol_ids[("src/Text/Bar.hs", "useParser")]
    parser_symbol_id = symbol_ids[("src/Text/Foo.hs", "Parser")]
    render_symbol_id = symbol_ids[("src/Text/Foo.hs", "render")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{use_parser_symbol_id}"
        and str(row["target_node"]) == f"symbol:{parser_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{use_parser_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_ignores_haskell_local_bindings_as_top_level_symbols(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "haskell-local-binding-repo"
    source_dir = repo_path / "src" / "Text"
    source_dir.mkdir(parents=True)
    (repo_path / "sample.cabal").write_text(
        "name: sample\n"
        "version: 1.0.0.0\n"
        "library\n"
        "  hs-source-dirs: src\n"
        "  exposed-modules: Text.Local\n",
        encoding="utf-8",
    )
    (source_dir / "Local.hs").write_text(
        "module Text.Local where\n"
        "render :: Int -> Int\n"
        "render value =\n"
        "  let go inner = inner + 1\n"
        "  in go value\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.hs", "*.cabal"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_names = {
        (str(row["file_path"]), str(row["symbol_name"]))
        for row in symbol_rows
    }
    assert ("src/Text/Local.hs", "render") in symbol_names
    assert ("src/Text/Local.hs", "go") not in symbol_names


def test_repository_snapshot_graph_contains_zig_build_module_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "zig-build-module-repo"
    source_dir = repo_path / "src"
    source_dir.mkdir(parents=True)
    (repo_path / "build.zig").write_text(
        'const std = @import("std");\n'
        "pub fn build(b: *std.Build) void {\n"
        '  _ = b.addModule("acme", .{\n'
        '    .root_source_file = b.path("src/root.zig"),\n'
        "  });\n"
        "}\n",
        encoding="utf-8",
    )
    (source_dir / "root.zig").write_text(
        "pub const Answer = 42;\n",
        encoding="utf-8",
    )
    (source_dir / "main.zig").write_text(
        'const acme = @import("acme");\n'
        "pub fn main() void {\n"
        "  _ = acme.Answer;\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.zig"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    main_symbol_id = symbol_ids[("src/main.zig", "main")]
    answer_symbol_id = symbol_ids[("src/root.zig", "Answer")]

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.zig"
        and str(row["target_node"]) == "file:src/root.zig"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{answer_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_swift_same_target_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "swift-dependency-repo"
    target_dir = repo_path / "Sources" / "Acme"
    target_dir.mkdir(parents=True)
    (target_dir / "Documentation.docc").mkdir(parents=True)
    (target_dir / "CommandConfiguration.swift").write_text(
        "struct CommandConfiguration {}\n",
        encoding="utf-8",
    )
    (target_dir / "Documentation.docc" / "CommandConfiguration.md").write_text(
        "# docs\n",
        encoding="utf-8",
    )
    (target_dir / "ParsableCommand.swift").write_text(
        "protocol ParsableCommand {\n"
        "  static var configuration: CommandConfiguration { get }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Sources"],
            include_patterns=["Sources/**/*.swift"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:Sources/Acme/ParsableCommand.swift"
        and str(row["target_node"]) == "file:Sources/Acme/CommandConfiguration.swift"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_swift_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "swift-symbol-repo"
    target_dir = repo_path / "Sources" / "Acme"
    target_dir.mkdir(parents=True)
    (target_dir / "CommandConfiguration.swift").write_text(
        "struct CommandConfiguration {}\n",
        encoding="utf-8",
    )
    (target_dir / "ParsableCommand.swift").write_text(
        "protocol ParsableCommand {\n"
        "  static var configuration: CommandConfiguration { get }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Sources"],
            include_patterns=["Sources/**/*.swift"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    command_symbol_id = symbol_ids[("Sources/Acme/ParsableCommand.swift", "ParsableCommand")]
    configuration_symbol_id = symbol_ids[
        ("Sources/Acme/CommandConfiguration.swift", "CommandConfiguration")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{command_symbol_id}"
        and str(row["target_node"]) == f"symbol:{configuration_symbol_id}"
        for row in graph_rows
    )


@pytest.mark.anyio
async def test_repository_decision_plan_uses_deterministic_local_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN inputs."
                ),
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                    }
                ],
                "failing_tests": ["tests/test_service.py::test_normalize_status_open"],
                "changed_files": ["src/service.py"],
            },
        ),
    )

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _decision_envelope(), {"execution_ms": 11}

    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
        ),
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )
    envelope = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            snapshot_id=snapshot.snapshot_id,
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )
    simulation_id = str(envelope.validated_inputs["simulation_id"])
    applied = await repository_service.apply_repository_decision(
        connector=connector,
        request=RepositoryApplyRequest(
            snapshot_id=snapshot.snapshot_id,
            decision_plan_id=decision_plan.decision_plan_id,
            simulation_id=simulation_id,
            mode=RepositoryApplyMode.LOCAL_BRANCH,
            write_permission=True,
            branch_name="algenta/test-open-fix",
        ),
    )

    current_branch = subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
        text=True,
    ).strip()
    repository_analysis = decision_plan.decision_plan.repository_analysis
    assert repository_analysis is not None
    assert repository_analysis.root_cause == (
        "normalize_status returns 'closed' instead of 'open' at src/service.py:4."
    )
    assert repository_analysis.planner_model_id == (
        repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID
    )
    assert repository_analysis.planner_execution_mode == "deterministic_local"
    assert repository_analysis.planner_provider_backend is None
    assert repository_analysis.generated_patch_ref is not None
    assert repository_analysis.patch_impact_report_ref is not None
    assert decision_plan.decision_plan.recommended_action == (
        "Correct normalize_status in src/service.py to return 'open'."
    )
    assert envelope.recommended_action == "apply_patch"
    assert applied.applied is True
    assert applied.commit_sha
    assert current_branch == "algenta/test-open-fix"
    assert 'return "open"' in (repo_path / "src" / "service.py").read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_repository_decision_plan_deterministic_local_model_fails_closed_when_unsupported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "handle_request crashes when user is null",
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 2,
                        "severity": "error",
                        "message": "AttributeError: 'NoneType' object has no attribute 'name'",
                    }
                ],
            },
        ),
    )

    with pytest.raises(repository_service.RepositoryIntelligenceError) as excinfo:
        await repository_service.create_repository_decision_plan(
            connector=connector,
            request=RepositoryDecisionPlanCreateRequest(
                snapshot_id=snapshot.snapshot_id,
                workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
                model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
            ),
        )

    assert excinfo.value.code == "repository_local_planner_unsupported"


@pytest.mark.anyio
async def test_repository_decision_plan_deterministic_local_model_handles_ts6059_rootdir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_rootdir_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=[
                "services/app",
                "packages/common",
                "services/app/tsconfig.test.json",
                "services/app/tsconfig.json",
            ],
            include_patterns=["services/**/*.ts", "services/**/*.json", "packages/**/*.ts", "packages/**/*.json"],
        ),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "TypeScript test project fails with TS6059 rootDir drift.",
                "diagnostics": [
                    {
                        "path": "packages/common/src/shared.ts",
                        "line": 1,
                        "severity": "error",
                        "code": "TS6059",
                        "message": "File is not under 'rootDir' '/tmp/service'. 'rootDir' is expected to contain all source files.",
                    }
                ],
                "changed_files": ["packages/common/src/shared.ts"],
                "workspace_context": [
                    "command:cd services/app && pnpm exec tsc -p tsconfig.test.json --noEmit",
                    "diagnostic_base_path:services/app",
                    "tsconfig_project:services/app/tsconfig.test.json",
                ],
            },
        ),
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )

    repository_analysis = decision_plan.decision_plan.repository_analysis
    assert repository_analysis is not None
    assert repository_analysis.planner_model_id == (
        repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID
    )
    assert repository_analysis.planner_execution_mode == "deterministic_local"
    assert repository_analysis.generated_patch_ref is not None
    assert repository_analysis.patch_impact_report_ref is not None
    assert "rootDir" in decision_plan.decision_plan.recommended_action

    plan_manifest = repository_service._load_decision_plan_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        decision_plan_id=decision_plan.decision_plan_id,
    )
    patch_text = Path(plan_manifest["patch_path"]).read_text(encoding="utf-8")
    assert "services/app/tsconfig.test.json" in patch_text
    assert '"rootDir": "../.."' in patch_text


@pytest.mark.anyio
async def test_repository_decision_plan_existing_lookup_skips_regeneration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN inputs."
                ),
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                    }
                ],
            },
        ),
    )
    first = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )

    async def _unexpected_generate_repository_patch_plan(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("decision-plan fast path should reuse the persisted plan")

    monkeypatch.setattr(
        repository_service,
        "_generate_repository_patch_plan",
        _unexpected_generate_repository_patch_plan,
    )
    plan_path = repository_service._decision_plans_dir(
        str(connector.org_id),
        str(connector.id),
    ) / f"{first.decision_plan_id}.json"
    original_read_json = repository_service._read_json

    def _read_json_without_plan_manifest(path: Path) -> dict[str, Any]:
        if Path(path) == plan_path:
            raise AssertionError("decision-plan fast path should not reopen the plan manifest")
        return original_read_json(path)

    monkeypatch.setattr(repository_service, "_read_json", _read_json_without_plan_manifest)
    second = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )

    assert second.decision_plan_id == first.decision_plan_id
    assert second.decision_plan == first.decision_plan


@pytest.mark.anyio
async def test_repository_decision_plan_uses_workspace_evidence_bundle_snapshot_when_omitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN inputs."
                ),
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                    }
                ],
            },
        ),
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )

    assert decision_plan.snapshot_id == snapshot.snapshot_id
    assert decision_plan.decision_plan.repository_analysis is not None


@pytest.mark.anyio
async def test_repository_decision_plan_workspace_evidence_bundle_snapshot_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    first_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=first_snapshot.snapshot_id,
            signals={
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN inputs."
                ),
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                    }
                ],
            },
        ),
    )
    (repo_path / "src" / "service.py").write_text(
        "def normalize_status(status: str) -> str:\n"
        "    lowered = status.strip().lower()\n"
        '    if lowered == "open":\n'
        '        return "pending"\n'
        "    return lowered\n",
        encoding="utf-8",
    )
    second_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    with pytest.raises(repository_service.RepositoryIntelligenceError) as excinfo:
        await repository_service.create_repository_decision_plan(
            connector=connector,
            request=RepositoryDecisionPlanCreateRequest(
                snapshot_id=second_snapshot.snapshot_id,
                workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
                model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
            ),
        )

    assert excinfo.value.code == "repository_decision_plan_snapshot_mismatch"


@pytest.mark.anyio
async def test_repository_decision_plan_simulate_and_apply_local_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "handle_request crashes when user is null",
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 2,
                        "severity": "error",
                        "message": "AttributeError: 'NoneType' object has no attribute 'name'",
                    }
                ],
            },
        ),
    )

    source_path = repo_path / "src" / "service.py"
    old_text = source_path.read_text(encoding="utf-8")
    new_text = (
        "def handle_request(user):\n"
        "    if user is None:\n"
        '        return "anonymous"\n'
        "    return user.name\n"
    )
    patch_diff = "".join(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile="a/src/service.py",
            tofile="b/src/service.py",
        )
    )

    async def _fake_generate_repository_patch_plan(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "root_cause": "handle_request dereferences user.name without a null guard.",
            "planner_model_id": "repo-fix-model",
            "planner_execution_mode": "provider_backed_chat",
            "planner_provider_backend": "openai",
            "candidate_fixes": ["Add a null guard before returning user.name."],
            "recommended_action": "Add null guard in handle_request",
            "rationale": "The failing path is isolated to src/service.py and the patch is localized.",
            "confidence": 0.89,
            "patch_diff": patch_diff,
        }

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _decision_envelope(), {"execution_ms": 11}

    monkeypatch.setattr(
        repository_service, "_resolve_repository_model", lambda _model: "repo-fix-model"
    )
    monkeypatch.setattr(
        repository_service,
        "_generate_repository_patch_plan",
        _fake_generate_repository_patch_plan,
    )
    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
        ),
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
        ),
    )
    envelope = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            snapshot_id=snapshot.snapshot_id,
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )
    simulation_id = str(envelope.validated_inputs["simulation_id"])
    applied = await repository_service.apply_repository_decision(
        connector=connector,
        request=RepositoryApplyRequest(
            snapshot_id=snapshot.snapshot_id,
            decision_plan_id=decision_plan.decision_plan_id,
            simulation_id=simulation_id,
            mode=RepositoryApplyMode.LOCAL_BRANCH,
            write_permission=True,
            branch_name="algenta/test-null-guard",
        ),
    )

    current_branch = subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
        text=True,
    ).strip()
    repository_analysis = decision_plan.decision_plan.repository_analysis
    assert repository_analysis is not None
    assert repository_analysis.generated_patch_ref is not None
    assert repository_analysis.planner_model_id == "repo-fix-model"
    assert repository_analysis.planner_execution_mode == "provider_backed_chat"
    assert repository_analysis.planner_provider_backend == "openai"
    assert envelope.recommended_action == "apply_patch"
    assert applied.applied is True
    assert applied.commit_sha
    assert current_branch == "algenta/test-null-guard"
    assert "anonymous" in source_path.read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_repository_simulation_existing_lookup_skips_resimulation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN inputs."
                ),
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                    }
                ],
            },
        ),
    )

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _decision_envelope(), {"execution_ms": 11}

    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
        ),
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )
    first = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            snapshot_id=snapshot.snapshot_id,
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )

    async def _unexpected_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("simulation fast path should reuse the persisted envelope")

    monkeypatch.setattr(repository_service, "run_simulation_fast", _unexpected_run_simulation_fast)
    simulation_id = str(first.validated_inputs["simulation_id"])
    simulation_path = repository_service._simulations_dir(
        str(connector.org_id),
        str(connector.id),
    ) / f"{simulation_id}.json"
    original_read_json = repository_service._read_json

    def _read_json_without_simulation_manifest(path: Path) -> dict[str, Any]:
        if Path(path) == simulation_path:
            raise AssertionError("simulation fast path should not reopen the simulation manifest")
        return original_read_json(path)

    monkeypatch.setattr(repository_service, "_read_json", _read_json_without_simulation_manifest)
    second = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )

    assert second.run_id == first.run_id
    assert second.recommended_action == first.recommended_action
    assert second.score_breakdown == first.score_breakdown


@pytest.mark.anyio
async def test_repository_simulation_uses_decision_plan_snapshot_when_omitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN inputs."
                ),
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                    }
                ],
            },
        ),
    )

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _decision_envelope(), {"execution_ms": 11}

    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
        ),
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )
    envelope = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )

    assert envelope.validated_inputs["snapshot_id"] == snapshot.snapshot_id


@pytest.mark.anyio
async def test_repository_simulation_snapshot_mismatch_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    first_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=first_snapshot.snapshot_id,
            signals={
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN inputs."
                ),
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                    }
                ],
            },
        ),
    )
    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )
    (repo_path / "src" / "service.py").write_text(
        "def normalize_status(status: str) -> str:\n"
        "    lowered = status.strip().lower()\n"
        '    if lowered == "open":\n'
        '        return "pending"\n'
        "    return lowered\n",
        encoding="utf-8",
    )
    second_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    with pytest.raises(repository_service.RepositoryIntelligenceError) as excinfo:
        await repository_service.simulate_repository_decision(
            connector=connector,
            request=RepositorySimulationRequest(
                snapshot_id=second_snapshot.snapshot_id,
                decision_plan_id=decision_plan.decision_plan_id,
            ),
        )

    assert excinfo.value.code == "repository_simulation_snapshot_mismatch"


@pytest.mark.anyio
async def test_repository_apply_patch_only_bypasses_failed_apply_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "handle_request crashes when user is null",
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 2,
                        "severity": "error",
                        "message": "AttributeError: 'NoneType' object has no attribute 'name'",
                    }
                ],
            },
        ),
    )

    source_path = repo_path / "src" / "service.py"
    old_text = source_path.read_text(encoding="utf-8")
    new_text = (
        "def handle_request(user):\n"
        "    if user is None:\n"
        '        return "anonymous"\n'
        "    return user.name\n"
    )
    patch_diff = "".join(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile="a/src/service.py",
            tofile="b/src/service.py",
        )
    )

    async def _fake_generate_repository_patch_plan(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "root_cause": "handle_request dereferences user.name without a null guard.",
            "planner_model_id": "repo-fix-model",
            "planner_execution_mode": "provider_backed_chat",
            "planner_provider_backend": "openai",
            "candidate_fixes": ["Add a null guard before returning user.name."],
            "recommended_action": "Add null guard in handle_request",
            "rationale": "The failing path is isolated to src/service.py and the patch is localized.",
            "confidence": 0.61,
            "patch_diff": patch_diff,
        }

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _decision_envelope(), {"execution_ms": 11}

    monkeypatch.setattr(
        repository_service, "_resolve_repository_model", lambda _model: "repo-fix-model"
    )
    monkeypatch.setattr(
        repository_service,
        "_generate_repository_patch_plan",
        _fake_generate_repository_patch_plan,
    )
    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.99, risk_floor=5.0
        ),
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
        ),
    )
    envelope = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )
    simulation_id = str(envelope.validated_inputs["simulation_id"])
    applied = await repository_service.apply_repository_decision(
        connector=connector,
        request=RepositoryApplyRequest(
            decision_plan_id=decision_plan.decision_plan_id,
            simulation_id=simulation_id,
            mode=RepositoryApplyMode.PATCH_ONLY,
        ),
    )

    assert envelope.recommended_action == "hold_patch"
    assert applied.applied is False
    assert applied.mode == RepositoryApplyMode.PATCH_ONLY
    assert applied.apply_gate["passed"] is False
    assert "anonymous" in applied.patch


@pytest.mark.anyio
async def test_repository_apply_snapshot_mismatch_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN inputs."
                ),
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                    }
                ],
            },
        ),
    )

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _decision_envelope(), {"execution_ms": 11}

    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
        ),
    )

    decision_plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )
    envelope = await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            decision_plan_id=decision_plan.decision_plan_id,
        ),
    )
    simulation_id = str(envelope.validated_inputs["simulation_id"])

    with pytest.raises(repository_service.RepositoryIntelligenceError) as excinfo:
        await repository_service.apply_repository_decision(
            connector=connector,
            request=RepositoryApplyRequest(
                snapshot_id="snapshot_conflict",
                decision_plan_id=decision_plan.decision_plan_id,
                simulation_id=simulation_id,
                mode=RepositoryApplyMode.PATCH_ONLY,
            ),
        )

    assert excinfo.value.code == "repository_apply_requested_snapshot_mismatch"
