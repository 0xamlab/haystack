from __future__ import annotations

import json
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

from apps.api_server.schemas.repositories import (
    RepositoryDiagnostic,
)
from apps.api_server.services import repository_intelligence as repository_service
from benchmarks.repository_intelligence_real_repo_probe_graph_support import (  # noqa: F401
    ProbeGraphSupportDependencies,
    build_connected_dependency_map as _build_connected_dependency_map_support,
    candidate_solutions as _candidate_solutions_support,
    load_snapshot_graph_summary as _load_snapshot_graph_summary_support,
)
from benchmarks.repository_intelligence_real_repo_probe_seed_plan_phase_a_support import (  # noqa: F401
    apply_seed_plan_phase_a as _apply_seed_plan_phase_a_support,
)
from benchmarks.repository_intelligence_real_repo_probe_seed_plan_phase_b_support import (  # noqa: F401
    apply_seed_plan_phase_b as _apply_seed_plan_phase_b_support,
)
from benchmarks.repository_intelligence_real_repo_probe_seed_plan_phase_c_support import (  # noqa: F401
    apply_seed_plan_phase_c as _apply_seed_plan_phase_c_support,
)
from benchmarks.repository_intelligence_real_repo_probe_seed_plan_phase_d_support import (  # noqa: F401
    apply_seed_plan_phase_d as _apply_seed_plan_phase_d_support,
)
from benchmarks.repository_intelligence_real_repo_probe_seed_plan_dispatch_support import (
    dispatch_basenames_to_ecosystem as _dispatch_basenames_to_ecosystem_support,
)
from benchmarks.repository_intelligence_real_repo_probe_seed_plan_support import (
    best_repository_path_priority as _best_repository_path_priority_support,
    candidate_ecosystem_counts as _candidate_ecosystem_counts_support,
    candidate_ecosystems_for_path as _candidate_ecosystems_for_path_support,
    finalize_seed_plan as _finalize_seed_plan_support,
    ordered_detected_ecosystems as _ordered_detected_ecosystems_support,
    ordered_operational_ecosystems as _ordered_operational_ecosystems_support,
    profile_signal_depth_score as _profile_signal_depth_score_support,
    rank_repo_profile_seed_path as _rank_repo_profile_seed_path_support,
    register_candidate_ecosystems as _register_candidate_ecosystems_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_languages_support import (
    _agda_profile_hints as _agda_profile_hints_support,
    _coq_profile_hints as _coq_profile_hints_support,
    _idris_profile_hints as _idris_profile_hints_support,
    _lean_profile_hints as _lean_profile_hints_support,
    _racket_profile_hints as _racket_profile_hints_support,
    _raku_profile_hints as _raku_profile_hints_support,
    _rockspec_profile_hints as _rockspec_profile_hints_support,
    _scheme_profile_hints as _scheme_profile_hints_support,
    _v_profile_hints as _v_profile_hints_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_project_languages_a_support import (
    _cfml_profile_hints as _cfml_profile_hints_support,
    _classic_visual_basic_profile_hints as _classic_visual_basic_profile_hints_support,
    _elm_profile_hints as _elm_profile_hints_support,
    _ml_profile_hints as _ml_profile_hints_support,
    _ocaml_profile_hints as _ocaml_profile_hints_support,
    _xpp_profile_hints as _xpp_profile_hints_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_project_languages_b_support import (
    _actionscript_profile_hints as _actionscript_profile_hints_support,
    _gdscript_project_profile_hints as _gdscript_project_profile_hints_support,
    _gml_profile_hints as _gml_profile_hints_support,
    _systemverilog_profile_hints as _systemverilog_profile_hints_support,
    _vhdl_profile_hints as _vhdl_profile_hints_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_frontend_templates_support import (
    _astro_profile_hints_from_candidates as _astro_profile_hints_from_candidates_support,
    _blade_profile_hints_from_candidates as _blade_profile_hints_from_candidates_support,
    _ejs_profile_hints_from_candidates as _ejs_profile_hints_from_candidates_support,
    _erb_profile_hints_from_candidates as _erb_profile_hints_from_candidates_support,
    _haml_profile_hints_from_candidates as _haml_profile_hints_from_candidates_support,
    _pug_profile_hints_from_candidates as _pug_profile_hints_from_candidates_support,
    _slim_profile_hints_from_candidates as _slim_profile_hints_from_candidates_support,
    _svelte_profile_hints_from_candidates as _svelte_profile_hints_from_candidates_support,
    _vue_profile_hints_from_candidates as _vue_profile_hints_from_candidates_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_server_templates_support import (
    _handlebars_profile_hints_from_candidates as _handlebars_profile_hints_from_candidates_support,
    _jinja_profile_hints_from_candidates as _jinja_profile_hints_from_candidates_support,
    _liquid_profile_hints_from_candidates as _liquid_profile_hints_from_candidates_support,
    _mako_profile_hints_from_candidates as _mako_profile_hints_from_candidates_support,
    _mustache_profile_hints_from_candidates as _mustache_profile_hints_from_candidates_support,
    _nunjucks_profile_hints_from_candidates as _nunjucks_profile_hints_from_candidates_support,
    _smarty_profile_hints_from_candidates as _smarty_profile_hints_from_candidates_support,
    _twig_profile_hints_from_candidates as _twig_profile_hints_from_candidates_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_diagrams_support import (
    _graphviz_profile_hints_from_candidates as _graphviz_profile_hints_from_candidates_support,
    _mermaid_profile_hints_from_candidates as _mermaid_profile_hints_from_candidates_support,
    _openqasm_profile_hints_from_candidates as _openqasm_profile_hints_from_candidates_support,
    _plantuml_profile_hints_from_candidates as _plantuml_profile_hints_from_candidates_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_build_tooling_support import (
    _bicep_profile_hints_from_candidates as _bicep_profile_hints_from_candidates_support,
    _bitbake_profile_candidate_paths as _bitbake_profile_candidate_paths_support,
    _bitbake_profile_hints_from_candidates as _bitbake_profile_hints_from_candidates_support,
    _chapel_profile_hints as _chapel_profile_hints_support,
    _eiffel_profile_hints as _eiffel_profile_hints_support,
    _eiffel_profile_hints_from_candidates as _eiffel_profile_hints_from_candidates_support,
    _hcl_profile_hints_from_candidates as _hcl_profile_hints_from_candidates_support,
    _resolve_eiffel_config_target as _resolve_eiffel_config_target_support,
    _tlaplus_profile_hints_from_candidates as _tlaplus_profile_hints_from_candidates_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_ecosystem_support import (
    _apex_profile_hints as _apex_profile_hints_support,
    _ballerina_profile_hints as _ballerina_profile_hints_support,
    _dhall_profile_hints_from_candidates as _dhall_profile_hints_from_candidates_support,
    _gleam_profile_hints as _gleam_profile_hints_support,
    _janet_profile_hints as _janet_profile_hints_support,
    _luau_profile_hints as _luau_profile_hints_support,
    _moonbit_profile_candidate_paths as _moonbit_profile_candidate_paths_support,
    _moonbit_profile_hints_from_candidates as _moonbit_profile_hints_from_candidates_support,
    _nextflow_profile_hints_from_candidates as _nextflow_profile_hints_from_candidates_support,
    _solidity_profile_hints as _solidity_profile_hints_support,
    _wolfram_profile_hints as _wolfram_profile_hints_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_path_selection_support import (
    _accumulate_detected_ecosystem_scores as _accumulate_detected_ecosystem_scores_support,
    _balanced_profile_paths as _balanced_profile_paths_support,
    _best_matching_support_root as _best_matching_support_root_support,
    _cuda_profile_hints_from_candidates as _cuda_profile_hints_from_candidates_support,
    _diversify_paths_by_support_root as _diversify_paths_by_support_root_support,
    _expand_profile_entrypoints as _expand_profile_entrypoints_support,
    _is_repo_profile_code_candidate as _is_repo_profile_code_candidate_support,
    _leaf_support_roots as _leaf_support_roots_support,
    _normalized_package_identifier as _normalized_package_identifier_support,
    _path_within_support_roots as _path_within_support_roots_support,
    _prefer_non_text_control_profile_candidates as _prefer_non_text_control_profile_candidates_support,
    _profile_entrypoint_target_count as _profile_entrypoint_target_count_support,
    _repo_profile_candidate_paths as _repo_profile_candidate_paths_support,
    _repo_profile_config_paths as _repo_profile_config_paths_support,
    _ruby_package_entrypoint_paths as _ruby_package_entrypoint_paths_support,
    _ruby_package_names_for_profile as _ruby_package_names_for_profile_support,
    _scala_support_root_from_candidate_path as _scala_support_root_from_candidate_path_support,
    _scala_support_roots_from_candidates as _scala_support_roots_from_candidates_support,
    _seeded_repo_profile_candidate_paths as _seeded_repo_profile_candidate_paths_support,
    _support_roots_need_expansion as _support_roots_need_expansion_support,
    _support_roots_requiring_expansion as _support_roots_requiring_expansion_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_style_candidates_support import (  # noqa: F401
    _al_profile_hints_from_candidates,
    _less_profile_hints_from_candidates,
    _qsharp_profile_hints_from_candidates,
    _sass_profile_hints_from_candidates,
    _scss_profile_hints_from_candidates,
    _stylus_profile_hints_from_candidates,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_candidate_ecosystem_support import (  # noqa: F401
    _antlr_profile_hints_from_candidates,
    _asciidoc_profile_hints_from_candidates,
    _gherkin_profile_hints_from_candidates,
    _move_profile_hints_from_candidates,
    _org_profile_hints_from_candidates,
    _robotframework_profile_hints_from_candidates,
    _rst_profile_hints_from_candidates,
    _supplement_candidate_file_paths_for_surface_dir_parts,
    _supplement_candidate_file_paths_for_suffix_roots,
    _tex_profile_hints_from_candidates,
    _typst_profile_hints_from_candidates,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_candidate_languages_support import (  # noqa: F401
    _bqn_profile_hints_from_candidates,
    _circom_profile_hints_from_candidates,
    _cython_profile_hints_from_candidates,
    _dafny_profile_hints_from_candidates,
    _j_profile_hints_from_candidates,
    _lex_profile_hints_from_candidates,
    _modelica_profile_hints_from_candidates,
    _protobuf_profile_hints_from_candidates,
    _rebol_profile_hints_from_candidates,
    _rescript_profile_hints_from_candidates,
    _roc_profile_hints_from_candidates,
    _stan_profile_hints_from_candidates,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_candidate_projects_support import (
    _cue_profile_hints_from_candidates as _cue_profile_hints_from_candidates_support,
    _dm_profile_hints as _dm_profile_hints_support,
    _factor_profile_hints_from_candidates as _factor_profile_hints_from_candidates_support,
    _four_d_profile_hints_from_candidates as _four_d_profile_hints_from_candidates_support,
    _odin_profile_hints as _odin_profile_hints_support,
    _odin_profile_hints_from_candidates as _odin_profile_hints_from_candidates_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_brightscript_support import (
    _brightscript_profile_hints_from_candidates as _brightscript_profile_hints_from_candidates_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_query_support import (
    _codeql_profile_hints_from_candidates as _codeql_profile_hints_from_candidates_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_project_family_support import (
    _coffeescript_profile_hints as _coffeescript_profile_hints_support,
    _gams_profile_hints as _gams_profile_hints_support,
    _haxe_profile_hints as _haxe_profile_hints_support,
    _logtalk_profile_hints_from_candidates as _logtalk_profile_hints_from_candidates_support,
    _mql5_profile_hints as _mql5_profile_hints_support,
    _nix_profile_hints as _nix_profile_hints_support,
    _openscad_profile_hints as _openscad_profile_hints_support,
    _purescript_profile_hints as _purescript_profile_hints_support,
    _rescript_profile_hints as _rescript_profile_hints_support,
    _smalltalk_profile_hints as _smalltalk_profile_hints_support,
    _starlark_profile_hints as _starlark_profile_hints_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_misc_support import (
    _default_probe_include_patterns as _default_probe_include_patterns_support,
    _julia_profile_hints as _julia_profile_hints_support,
    _perl_profile_hints as _perl_profile_hints_support,
    _r_profile_hints as _r_profile_hints_support,
    _shard_profile_hints as _shard_profile_hints_support,
)
from benchmarks.repository_intelligence_real_repo_probe_constants_support import (  # noqa: F401
    DEFAULT_EXCLUDE_PATTERNS,
    _ADA_PROJECT_FIELD_RE,
    _CLOJURE_MAIN_RE,
    _CLOJURE_QUOTED_STRING_RE,
    _CLOJURE_VECTOR_FIELD_RE,
    _COLON_DIAGNOSTIC_RE,
    _COMMAND_CD_RE,
    _CRYSTAL_SHARD_MAIN_RE,
    _CRYSTAL_SHARD_NAME_RE,
    _C_FAMILY_SOURCE_TOKEN_RE,
    _DOCUMENTATION_OPERATIONAL_PATH_PARTS,
    _DOCUMENTATION_PRIMARY_ECOSYSTEMS,
    _EXAMPLE_OPERATIONAL_PATH_PARTS,
    _EXAMPLE_PRIMARY_ECOSYSTEMS,
    _FOUNDRY_LIST_FIELD_RE,
    _FOUNDRY_STRING_FIELD_RE,
    _GDSCRIPT_RESOURCE_RE,
    _GDSCRIPT_SCENE_SCRIPT_RE,
    _HASKELL_SOURCE_EXTENSIONS,
    _LUAU_PROJECT_PATH_RE,
    _LUAU_WALLY_NAME_RE,
    _LUA_ROCKSPEC_MODULE_RE,
    _LUA_ROCKSPEC_PACKAGE_RE,
    _ML_MANIFEST_PATH_RE,
    _ML_SOURCE_EXTENSIONS,
    _NAMESPACE_PACKAGE_TOKENS,
    _NODE_STACK_FRAME_RE,
    _NON_OPERATIONAL_PROFILE_PATH_PARTS,
    _NON_OPERATIONAL_PROJECT_PATH_PARTS,
    _POWERSHELL_MANIFEST_FIELD_RE,
    _POWERSHELL_MANIFEST_LIST_RE,
    _PREPASS_CACHE_SCHEMA_VERSION,
    _PROJECT_ARG_RE,
    _PYTHON_TRACEBACK_FILE_RE,
    _QUOTED_SEGMENT_RE,
    _REPO_PROFILE_MANIFEST_BASENAMES,
    _RUST_SPAN_RE,
    _SCENARIO_OPERATIONAL_PATH_PARTS,
    _SCENARIO_PRIMARY_ECOSYSTEMS,
    _SLN_PROJECT_RE,
    _SYSTEMVERILOG_MANIFEST_PATH_RE,
    _TEMPLATE_SURFACE_ECOSYSTEMS,
    _TEMPLATE_SURFACE_PARTS,
    _TSC_DIAGNOSTIC_RE,
    _ZIG_SOURCE_TOKEN_RE,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_policy_shader_candidates_support import (
    _glsl_profile_hints_from_candidates as _glsl_profile_hints_from_candidates_support,
    _hlsl_profile_hints_from_candidates as _hlsl_profile_hints_from_candidates_support,
    _metal_profile_hints_from_candidates as _metal_profile_hints_from_candidates_support,
    _opencl_profile_hints_from_candidates as _opencl_profile_hints_from_candidates_support,
    _rego_profile_hints_from_candidates as _rego_profile_hints_from_candidates_support,
    _shaderlab_profile_hints_from_candidates as _shaderlab_profile_hints_from_candidates_support,
    _wgsl_profile_hints_from_candidates as _wgsl_profile_hints_from_candidates_support,
    _yara_profile_hints_from_candidates as _yara_profile_hints_from_candidates_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_path_classification_support import (
    _is_cfml_box_config_path as _is_cfml_box_config_path_support,
    _is_cue_module_config_path as _is_cue_module_config_path_support,
    _is_delphi_project_config_path as _is_delphi_project_config_path_support,
    _is_dm_project_config_path as _is_dm_project_config_path_support,
    _is_eiffel_project_config_path as _is_eiffel_project_config_path_support,
    _is_moonbit_config_path as _is_moonbit_config_path_support,
    _is_namespace_style_source_path as _is_namespace_style_source_path_support,
    _is_non_operational_profile_path as _is_non_operational_profile_path_support,
    _is_non_operational_profile_path_for_ecosystems as _is_non_operational_profile_path_for_ecosystems_support,
    _is_non_operational_project_path as _is_non_operational_project_path_support,
    _is_odin_ols_config_path as _is_odin_ols_config_path_support,
    _is_operational_profile_entrypoint_candidate as _is_operational_profile_entrypoint_candidate_support,
    _is_profile_entrypoint_noise as _is_profile_entrypoint_noise_support,
    _is_puppet_metadata_config_path as _is_puppet_metadata_config_path_support,
    _is_purescript_bower_config_path as _is_purescript_bower_config_path_support,
    _is_qmake_project_config_path as _is_qmake_project_config_path_support,
    _is_repo_profile_manifest_name as _is_repo_profile_manifest_name_support,
    _is_rescript_config_path as _is_rescript_config_path_support,
    _is_xpp_descriptor_config_path as _is_xpp_descriptor_config_path_support,
    _probe_language_for_path as _probe_language_for_path_support,
    _profile_path_tokens as _profile_path_tokens_support,
)
from benchmarks.repository_intelligence_real_repo_probe_collection_support import (
    _candidate_existing_leaf_roots as _candidate_existing_leaf_roots_support,
    _candidate_existing_paths as _candidate_existing_paths_support,
    _candidate_existing_roots as _candidate_existing_roots_support,
    _git_repo_relative_files_for_focus_paths as _git_repo_relative_files_for_focus_paths_support,
    _git_repo_relative_files as _git_repo_relative_files_support,
    _matches_focus_paths as _matches_focus_paths_support,
    _normalized_scannable_support_roots as _normalized_scannable_support_roots_support,
    _probe_collection_rank as _probe_collection_rank_support,
    _prune_top_level_auxiliary_roots_without_entrypoints as _prune_top_level_auxiliary_roots_without_entrypoints_support,
)
from benchmarks.repository_intelligence_real_repo_probe_path_scan_support import (
    _candidate_repository_file_paths as _candidate_repository_file_paths_support,
    _connected_map_candidate_file_limit as _connected_map_candidate_file_limit_support,
    _looks_like_concrete_file_seed as _looks_like_concrete_file_seed_support,
    _normalized_candidate_file_paths as _normalized_candidate_file_paths_support,
    _probe_repository_file_paths as _probe_repository_file_paths_support,
    _seed_dependency_files as _seed_dependency_files_support,
    _should_group_focus_path_scan as _should_group_focus_path_scan_support,
    _should_use_seeded_profile_candidate_scan as _should_use_seeded_profile_candidate_scan_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_qml_chapel_support import (
    _chapel_profile_hints_from_candidates as _chapel_profile_hints_from_candidates_support,
    _qml_profile_hints_from_candidates as _qml_profile_hints_from_candidates_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_scripting_support import (  # noqa: F401
    _tcl_profile_hints,
    _rpg_profile_hints,
    _vbscript_profile_hints,
    _labview_profile_hints,
    _lisp_profile_hints,
    _puppet_profile_hints,
    _hack_profile_hints_from_candidates,
    _emacslisp_profile_hints,
    _vimscript_profile_hints_from_candidates,
    _autohotkey_profile_hints_from_candidates,
    _autoit_profile_hints_from_candidates,
    _squirrel_profile_hints_from_candidates,
    _nushell_profile_hints_from_candidates,
    _fish_profile_hints_from_candidates,
    _batchfile_profile_hints_from_candidates,
    _makefile_profile_hints_from_candidates,
    _just_profile_hints_from_candidates,
    _dockerfile_profile_hints_from_candidates,
)
from benchmarks.repository_intelligence_real_repo_probe_seed_plan_orchestration_support import (
    _derive_operational_seed_paths_without_diagnostics as _derive_operational_seed_paths_without_diagnostics_support,
    _derive_operational_seed_plan_without_diagnostics as _derive_operational_seed_plan_without_diagnostics_support,
)

from benchmarks.repository_intelligence_real_repo_probe_diagnostics_support import (
    _candidate_config_focus_paths as _candidate_config_focus_paths_support,
    _effective_focus_paths_for_snapshot as _effective_focus_paths_for_snapshot_support,
    _focus_paths_from_diagnostics as _focus_paths_from_diagnostics_support,
    _inventory_repo_surface as _inventory_repo_surface_support,
    _normalize_relative_path as _normalize_relative_path_support,
    _resolve_diagnostic_base_path as _resolve_diagnostic_base_path_support,
    _resolve_diagnostic_project_path as _resolve_diagnostic_project_path_support,
    parse_repository_diagnostics as parse_repository_diagnostics_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_manifest_support import (  # noqa: F401
    _package_json_export_targets,
    _package_json_profile_hints,
    _tsconfig_profile_hints,
    _pyproject_profile_hints,
    _pubspec_profile_hints,
    _yaml_path_field_values,
    _dbt_project_profile_hints,
    _cargo_profile_hints,
    _fortran_fpm_profile_hints,
    _pascal_project_profile_hints,
    _delphi_profile_hints,
    _tsql_profile_hints,
    _normalized_ada_unit_stem,
    _ada_project_quoted_values,
    _ada_profile_hints,
    _dub_sdl_quoted_values,
    _normalized_d_package_name,
    _dub_profile_hints,
    _go_module_profile_hints,
    _candidate_clojure_module_paths,
    _collect_clojure_vector_field_values,
    _clojure_profile_hints,
    _pom_profile_hints,
    _normalize_gradle_project_root,
    _gradle_project_root_hints,
    _iter_gradle_included_project_roots,
    _gradle_profile_hints,
    _qsharp_profile_hints,
    _cmake_like_profile_hints,
    _c_family_manifest_ecosystems,
    _cmake_profile_hints,
    _profile_root_from_glob_pattern,
    _podspec_profile_hints,
    _meson_profile_hints,
    _qmake_profile_hints,
    _composer_profile_hints,
    _mix_profile_hints,
    _swift_package_profile_hints,
    _powershell_profile_hints,
    _scala_build_profile_hints,
    _scala_build_support_roots,
    _zig_build_profile_hints,
    _append_manifest_field_value,
    _collect_manifest_field_values,
    _candidate_haskell_module_paths,
    _haskell_cabal_profile_hints,
    _haskell_package_yaml_profile_hints,
    _haskell_project_profile_hints,
    _csproj_profile_hints,
    _sln_project_paths,
    _sln_profile_hints,
    _gemfile_profile_hints,
    _erlang_project_profile_hints,
    _nim_project_profile_hints,
)

from benchmarks.repository_intelligence_real_repo_probe_runtime_support import (  # noqa: F401
    ProbePrepassDependencies,
    ProbeRunDependencies,
    compute_probe_prepass as _compute_probe_prepass_support,
    load_probe_prepass_cache as _load_probe_prepass_cache_support,
    main as _probe_main_support,
    probe_prepass_cache_key as _probe_prepass_cache_key_support,
    probe_prepass_cache_path as _probe_prepass_cache_path_support,
    probe_repo_state as _probe_repo_state_support,
    run_command as _run_command_support,
    run_probe as _run_probe_support,
    store_probe_prepass_cache as _store_probe_prepass_cache_support,
)
from benchmarks.repository_intelligence_real_repo_probe_runtime_deps_support import (
    _probe_graph_support_deps as _probe_graph_support_deps_support,
    _probe_prepass_support_deps as _probe_prepass_support_deps_support,
    _probe_run_support_deps as _probe_run_support_deps_support,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "repository_intelligence_real_repo_probe.json"
DEFAULT_PERSISTED_RUNTIME_DIR = (
    PROJECT_ROOT / "build" / "repository_intelligence_real_repo_probe_runtime"
)


def _default_probe_include_patterns() -> list[str]:
    return _default_probe_include_patterns_support()


DEFAULT_INCLUDE_PATTERNS = _default_probe_include_patterns()


def _perl_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    return _perl_profile_hints_support(repo_path, config_path)


def _r_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    return _r_profile_hints_support(repo_path, config_path)


def _julia_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    return _julia_profile_hints_support(repo_path, config_path)


def _shard_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    return _shard_profile_hints_support(repo_path, config_path)


def _is_repo_profile_manifest_name(name: str) -> bool:
    return _is_repo_profile_manifest_name_support(name)


def _is_xpp_descriptor_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_xpp_descriptor_config_path_support(repo_path, relative_path)


def _is_cfml_box_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_cfml_box_config_path_support(repo_path, relative_path)


def _is_delphi_project_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_delphi_project_config_path_support(repo_path, relative_path)


def _is_dm_project_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_dm_project_config_path_support(repo_path, relative_path)


def _is_eiffel_project_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_eiffel_project_config_path_support(repo_path, relative_path)


def _is_purescript_bower_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_purescript_bower_config_path_support(repo_path, relative_path)


def _is_rescript_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_rescript_config_path_support(repo_path, relative_path)


def _is_moonbit_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_moonbit_config_path_support(repo_path, relative_path)


def _is_puppet_metadata_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_puppet_metadata_config_path_support(repo_path, relative_path)


def _is_odin_ols_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_odin_ols_config_path_support(repo_path, relative_path)


def _is_cue_module_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_cue_module_config_path_support(repo_path, relative_path)


def _is_qmake_project_config_path(repo_path: Path, relative_path: str) -> bool:
    return _is_qmake_project_config_path_support(repo_path, relative_path)


def _profile_path_tokens(path: str) -> set[str]:
    return _profile_path_tokens_support(path)


def _is_namespace_style_source_path(path: str) -> bool:
    return _is_namespace_style_source_path_support(path)


def _is_non_operational_profile_path(path: str) -> bool:
    return _is_non_operational_profile_path_support(path)


def _is_non_operational_profile_path_for_ecosystems(
    path: str,
    *,
    ecosystems: set[str] | None = None,
    repo_path: Path | None = None,
) -> bool:
    return _is_non_operational_profile_path_for_ecosystems_support(
        path,
        ecosystems=ecosystems,
        repo_path=repo_path,
    )


_is_non_operational_project_path = _is_non_operational_project_path_support
_probe_language_for_path = _probe_language_for_path_support
_is_profile_entrypoint_noise = _is_profile_entrypoint_noise_support
_is_operational_profile_entrypoint_candidate = (
    _is_operational_profile_entrypoint_candidate_support
)


def _repository_connector(
    repo_path: Path,
    *,
    assume_clean_git_clone: bool = False,
    resolved_revision: str | None = None,
) -> SimpleNamespace:
    config = {"path": str(repo_path)}
    if assume_clean_git_clone:
        config["assume_clean_git_clone"] = True
    if resolved_revision:
        config["resolved_revision"] = str(resolved_revision)
    return SimpleNamespace(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"repository-probe:{repo_path}"),
        org_id=uuid.uuid5(uuid.NAMESPACE_URL, "repository-probe-org"),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps(config),
    )


_resolve_diagnostic_base_path = _resolve_diagnostic_base_path_support
_resolve_diagnostic_project_path = _resolve_diagnostic_project_path_support
_normalize_relative_path = _normalize_relative_path_support
parse_repository_diagnostics = parse_repository_diagnostics_support
_focus_paths_from_diagnostics = _focus_paths_from_diagnostics_support
_effective_focus_paths_for_snapshot = _effective_focus_paths_for_snapshot_support
_candidate_config_focus_paths = _candidate_config_focus_paths_support
_inventory_repo_surface = _inventory_repo_surface_support
_git_repo_relative_files = _git_repo_relative_files_support
_git_repo_relative_files_for_focus_paths = _git_repo_relative_files_for_focus_paths_support
_matches_focus_paths = _matches_focus_paths_support
_probe_collection_rank = _probe_collection_rank_support
_probe_repository_file_paths = _probe_repository_file_paths_support
_candidate_repository_file_paths = _candidate_repository_file_paths_support
_should_group_focus_path_scan = _should_group_focus_path_scan_support
_should_use_seeded_profile_candidate_scan = (
    _should_use_seeded_profile_candidate_scan_support
)
_normalized_candidate_file_paths = _normalized_candidate_file_paths_support
_looks_like_concrete_file_seed = _looks_like_concrete_file_seed_support
_connected_map_candidate_file_limit = _connected_map_candidate_file_limit_support
_seed_dependency_files = _seed_dependency_files_support


def _safe_load_toml_dict(path: Path) -> dict[str, Any] | None:
    if tomllib is None:
        return None
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


_candidate_existing_paths = _candidate_existing_paths_support
_candidate_existing_roots = _candidate_existing_roots_support
_candidate_existing_leaf_roots = _candidate_existing_leaf_roots_support
_normalized_scannable_support_roots = _normalized_scannable_support_roots_support
_prune_top_level_auxiliary_roots_without_entrypoints = (
    _prune_top_level_auxiliary_roots_without_entrypoints_support
)

_elm_profile_hints = _elm_profile_hints_support
_ocaml_profile_hints = _ocaml_profile_hints_support
_ml_profile_hints = _ml_profile_hints_support
_classic_visual_basic_profile_hints = _classic_visual_basic_profile_hints_support
_xpp_profile_hints = _xpp_profile_hints_support
_cfml_profile_hints = _cfml_profile_hints_support
_actionscript_profile_hints = _actionscript_profile_hints_support
_systemverilog_profile_hints = _systemverilog_profile_hints_support
_gml_profile_hints = _gml_profile_hints_support
_gdscript_project_profile_hints = _gdscript_project_profile_hints_support
_vhdl_profile_hints = _vhdl_profile_hints_support
_jinja_profile_hints_from_candidates = _jinja_profile_hints_from_candidates_support
_mako_profile_hints_from_candidates = _mako_profile_hints_from_candidates_support
_brightscript_profile_hints_from_candidates = _brightscript_profile_hints_from_candidates_support
_codeql_profile_hints_from_candidates = _codeql_profile_hints_from_candidates_support
_liquid_profile_hints_from_candidates = _liquid_profile_hints_from_candidates_support
_handlebars_profile_hints_from_candidates = (
    _handlebars_profile_hints_from_candidates_support
)
_mustache_profile_hints_from_candidates = _mustache_profile_hints_from_candidates_support
_smarty_profile_hints_from_candidates = _smarty_profile_hints_from_candidates_support
_graphviz_profile_hints_from_candidates = _graphviz_profile_hints_from_candidates_support
_mermaid_profile_hints_from_candidates = _mermaid_profile_hints_from_candidates_support
_plantuml_profile_hints_from_candidates = _plantuml_profile_hints_from_candidates_support
_openqasm_profile_hints_from_candidates = _openqasm_profile_hints_from_candidates_support
_nunjucks_profile_hints_from_candidates = _nunjucks_profile_hints_from_candidates_support
_twig_profile_hints_from_candidates = _twig_profile_hints_from_candidates_support
_haml_profile_hints_from_candidates = _haml_profile_hints_from_candidates_support
_slim_profile_hints_from_candidates = _slim_profile_hints_from_candidates_support
_erb_profile_hints_from_candidates = _erb_profile_hints_from_candidates_support
_pug_profile_hints_from_candidates = _pug_profile_hints_from_candidates_support
_ejs_profile_hints_from_candidates = _ejs_profile_hints_from_candidates_support
_blade_profile_hints_from_candidates = _blade_profile_hints_from_candidates_support
_vue_profile_hints_from_candidates = _vue_profile_hints_from_candidates_support
_svelte_profile_hints_from_candidates = _svelte_profile_hints_from_candidates_support
_astro_profile_hints_from_candidates = _astro_profile_hints_from_candidates_support
_qml_profile_hints_from_candidates = _qml_profile_hints_from_candidates_support
_rego_profile_hints_from_candidates = _rego_profile_hints_from_candidates_support
_yara_profile_hints_from_candidates = _yara_profile_hints_from_candidates_support
_glsl_profile_hints_from_candidates = _glsl_profile_hints_from_candidates_support
_opencl_profile_hints_from_candidates = _opencl_profile_hints_from_candidates_support
_hlsl_profile_hints_from_candidates = _hlsl_profile_hints_from_candidates_support
_metal_profile_hints_from_candidates = _metal_profile_hints_from_candidates_support
_wgsl_profile_hints_from_candidates = _wgsl_profile_hints_from_candidates_support
_shaderlab_profile_hints_from_candidates = _shaderlab_profile_hints_from_candidates_support
_bitbake_profile_hints_from_candidates = _bitbake_profile_hints_from_candidates_support
_bitbake_profile_candidate_paths = _bitbake_profile_candidate_paths_support
_hcl_profile_hints_from_candidates = _hcl_profile_hints_from_candidates_support
_bicep_profile_hints_from_candidates = _bicep_profile_hints_from_candidates_support
_tlaplus_profile_hints_from_candidates = _tlaplus_profile_hints_from_candidates_support
_chapel_profile_hints = _chapel_profile_hints_support
_resolve_eiffel_config_target = _resolve_eiffel_config_target_support
_eiffel_profile_hints = _eiffel_profile_hints_support
_eiffel_profile_hints_from_candidates = _eiffel_profile_hints_from_candidates_support
_chapel_profile_hints_from_candidates = _chapel_profile_hints_from_candidates_support
_dm_profile_hints = _dm_profile_hints_support
_odin_profile_hints = _odin_profile_hints_support
_odin_profile_hints_from_candidates = _odin_profile_hints_from_candidates_support
_factor_profile_hints_from_candidates = _factor_profile_hints_from_candidates_support
_cue_profile_hints_from_candidates = _cue_profile_hints_from_candidates_support
_four_d_profile_hints_from_candidates = _four_d_profile_hints_from_candidates_support
_logtalk_profile_hints_from_candidates = _logtalk_profile_hints_from_candidates_support
_smalltalk_profile_hints = _smalltalk_profile_hints_support
_coffeescript_profile_hints = _coffeescript_profile_hints_support
_haxe_profile_hints = _haxe_profile_hints_support
_mql5_profile_hints = _mql5_profile_hints_support
_gams_profile_hints = _gams_profile_hints_support
_openscad_profile_hints = _openscad_profile_hints_support
_nix_profile_hints = _nix_profile_hints_support
_starlark_profile_hints = _starlark_profile_hints_support
_purescript_profile_hints = _purescript_profile_hints_support
_rescript_profile_hints = _rescript_profile_hints_support
_moonbit_profile_candidate_paths = _moonbit_profile_candidate_paths_support
_moonbit_profile_hints_from_candidates = _moonbit_profile_hints_from_candidates_support
_j_profile_hints_from_candidates = _j_profile_hints_from_candidates
_lex_profile_hints_from_candidates = _lex_profile_hints_from_candidates
_gleam_profile_hints = _gleam_profile_hints_support
_ballerina_profile_hints = _ballerina_profile_hints_support
_janet_profile_hints = _janet_profile_hints_support
_nextflow_profile_hints_from_candidates = _nextflow_profile_hints_from_candidates_support
_dhall_profile_hints_from_candidates = _dhall_profile_hints_from_candidates_support
_agda_profile_hints = _agda_profile_hints_support
_coq_profile_hints = _coq_profile_hints_support
_lean_profile_hints = _lean_profile_hints_support
_idris_profile_hints = _idris_profile_hints_support
_raku_profile_hints = _raku_profile_hints_support
_v_profile_hints = _v_profile_hints_support
_scheme_profile_hints = _scheme_profile_hints_support
_racket_profile_hints = _racket_profile_hints_support
_rockspec_profile_hints = _rockspec_profile_hints_support
_luau_profile_hints = _luau_profile_hints_support
_solidity_profile_hints = _solidity_profile_hints_support
_apex_profile_hints = _apex_profile_hints_support
_wolfram_profile_hints = _wolfram_profile_hints_support


_repo_profile_candidate_paths = _repo_profile_candidate_paths_support
_repo_profile_config_paths = _repo_profile_config_paths_support
_seeded_repo_profile_candidate_paths = _seeded_repo_profile_candidate_paths_support
_is_repo_profile_code_candidate = _is_repo_profile_code_candidate_support
_candidate_ecosystems_for_path = _candidate_ecosystems_for_path_support
_best_repository_path_priority = _best_repository_path_priority_support
_ordered_detected_ecosystems = _ordered_detected_ecosystems_support
_ordered_operational_ecosystems = _ordered_operational_ecosystems_support
_profile_signal_depth_score = _profile_signal_depth_score_support
_register_candidate_ecosystems = _register_candidate_ecosystems_support
_candidate_ecosystem_counts = _candidate_ecosystem_counts_support
_cuda_profile_hints_from_candidates = _cuda_profile_hints_from_candidates_support
_accumulate_detected_ecosystem_scores = _accumulate_detected_ecosystem_scores_support
_normalized_package_identifier = _normalized_package_identifier_support
_ruby_package_names_for_profile = _ruby_package_names_for_profile_support
_ruby_package_entrypoint_paths = _ruby_package_entrypoint_paths_support
_rank_repo_profile_seed_path = _rank_repo_profile_seed_path_support
_balanced_profile_paths = _balanced_profile_paths_support
_leaf_support_roots = _leaf_support_roots_support
_best_matching_support_root = _best_matching_support_root_support
_diversify_paths_by_support_root = _diversify_paths_by_support_root_support
_path_within_support_roots = _path_within_support_roots_support
_support_roots_requiring_expansion = _support_roots_requiring_expansion_support
_support_roots_need_expansion = _support_roots_need_expansion_support
_scala_support_root_from_candidate_path = _scala_support_root_from_candidate_path_support
_scala_support_roots_from_candidates = _scala_support_roots_from_candidates_support
_profile_entrypoint_target_count = _profile_entrypoint_target_count_support
_prefer_non_text_control_profile_candidates = (
    _prefer_non_text_control_profile_candidates_support
)
_expand_profile_entrypoints = _expand_profile_entrypoints_support


@dataclass
class _SeedPlanState:
    """Mutable state container shared between the dispatch and finalize phases of
    ``_derive_operational_seed_plan_without_diagnostics``. Holds the discovered
    config paths and every accumulator the dispatch ladder, middle phase, and
    terminal consolidation phase append to or read from."""

    repo_path: Path
    focus_paths: list[str]
    max_files: int
    discovered_config_paths: list[str] = field(default_factory=list)
    entrypoint_candidates: set[str] = field(default_factory=set)
    support_root_candidates: set[str] = field(default_factory=set)
    config_path_candidates: set[str] = field(default_factory=set)
    detected_ecosystems: set[str] = field(default_factory=set)
    detected_ecosystem_scores: Counter[str] = field(default_factory=Counter)
    entrypoint_candidate_ecosystems: dict[str, set[str]] = field(default_factory=dict)
    support_root_candidate_ecosystems: dict[str, set[str]] = field(default_factory=dict)
    bitbake_candidate_file_paths: list[str] = field(default_factory=list)
    candidate_file_paths: list[str] = field(default_factory=list)


_dispatch_basenames_to_ecosystem = _dispatch_basenames_to_ecosystem_support
_finalize_seed_plan = _finalize_seed_plan_support
_derive_operational_seed_plan_without_diagnostics = (
    _derive_operational_seed_plan_without_diagnostics_support
)
_derive_operational_seed_paths_without_diagnostics = (
    _derive_operational_seed_paths_without_diagnostics_support
)
_probe_graph_support_deps = _probe_graph_support_deps_support
_probe_prepass_support_deps = _probe_prepass_support_deps_support
_probe_run_support_deps = _probe_run_support_deps_support


def _build_connected_dependency_map(
    *,
    repo_path: Path,
    seed_paths: list[str],
    bridge_paths: list[str],
    candidate_file_paths: list[str] | None = None,
    candidate_scope_paths: list[str] | None = None,
    enable_reverse_bridging: bool = True,
    include_patterns: list[str],
    max_files: int,
    max_file_size_bytes: int,
    max_dependency_depth: int,
    max_connected_files: int,
) -> dict[str, Any]:
    return _build_connected_dependency_map_support(
        repo_path=repo_path,
        seed_paths=seed_paths,
        bridge_paths=bridge_paths,
        candidate_file_paths=candidate_file_paths,
        candidate_scope_paths=candidate_scope_paths,
        enable_reverse_bridging=enable_reverse_bridging,
        include_patterns=include_patterns,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_dependency_depth=max_dependency_depth,
        max_connected_files=max_connected_files,
        deps=_probe_graph_support_deps(),
    )


def _load_snapshot_graph_summary(
    *,
    repository_graph_path: str,
    dependency_graph_path: str,
    symbol_graph_path: str,
    seed_files: list[str],
) -> dict[str, Any]:
    return _load_snapshot_graph_summary_support(
        repository_graph_path=repository_graph_path,
        dependency_graph_path=dependency_graph_path,
        symbol_graph_path=symbol_graph_path,
        seed_files=seed_files,
    )


def _candidate_solutions(diagnostics: list[RepositoryDiagnostic]) -> list[dict[str, Any]]:
    return _candidate_solutions_support(diagnostics)


def _probe_repo_state(repo_path: Path) -> dict[str, Any]:
    return _probe_repo_state_support(repo_path)


def _probe_prepass_cache_key(
    *,
    repo_state: dict[str, Any],
    focus_paths: list[str],
    diagnostic_command: str | None,
    diagnostic_base_path: str | None,
    include_patterns: list[str],
    exclude_patterns: list[str],
    max_files: int,
    max_file_size_bytes: int,
    max_dependency_depth: int,
    max_connected_files: int,
) -> str | None:
    return _probe_prepass_cache_key_support(
        repo_state=repo_state,
        focus_paths=focus_paths,
        diagnostic_command=diagnostic_command,
        diagnostic_base_path=diagnostic_base_path,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_dependency_depth=max_dependency_depth,
        max_connected_files=max_connected_files,
        prepass_cache_schema_version=_PREPASS_CACHE_SCHEMA_VERSION,
    )


def _probe_prepass_cache_path(repository_runtime_root: Path, cache_key: str | None) -> Path | None:
    return _probe_prepass_cache_path_support(repository_runtime_root, cache_key)


def _load_probe_prepass_cache(cache_path: Path | None) -> dict[str, Any] | None:
    return _load_probe_prepass_cache_support(
        cache_path,
        prepass_cache_schema_version=_PREPASS_CACHE_SCHEMA_VERSION,
    )


def _store_probe_prepass_cache(cache_path: Path | None, payload: dict[str, Any]) -> None:
    _store_probe_prepass_cache_support(cache_path, payload)


def _compute_probe_prepass(
    *,
    repo_path: Path,
    focus_paths: list[str],
    operational_seed_plan: dict[str, Any] | None = None,
    use_seed_files_as_connected_map: bool = False,
    diagnostic_command: str | None,
    diagnostic_base_path: str | None,
    repository_runtime_root: Path,
    max_files: int,
    max_file_size_bytes: int,
    max_dependency_depth: int,
    max_connected_files: int,
) -> dict[str, Any]:
    return _compute_probe_prepass_support(
        repo_path=repo_path,
        focus_paths=focus_paths,
        operational_seed_plan=operational_seed_plan,
        use_seed_files_as_connected_map=use_seed_files_as_connected_map,
        diagnostic_command=diagnostic_command,
        diagnostic_base_path=diagnostic_base_path,
        repository_runtime_root=repository_runtime_root,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_dependency_depth=max_dependency_depth,
        max_connected_files=max_connected_files,
        deps=_probe_prepass_support_deps(),
    )


def _run_command(repo_path: Path, command: str) -> dict[str, Any]:
    return _run_command_support(repo_path, command)


def run_probe(
    *,
    repo_path: Path,
    focus_paths: list[str],
    operational_seed_plan: dict[str, Any] | None = None,
    use_seed_files_as_connected_map: bool = False,
    diagnostic_command: str | None,
    diagnostic_base_path: str | None,
    planner_model: str | None,
    runtime_dir: Path,
    reuse_existing_state: bool,
    max_files: int,
    max_file_size_bytes: int,
    max_total_bytes: int | None,
    max_dependency_depth: int,
    max_connected_files: int,
    assume_clean_git_clone: bool = False,
    resolved_revision: str | None = None,
    perform_warm_snapshot: bool = True,
    load_graph_summary: bool = True,
) -> dict[str, Any]:
    return _run_probe_support(
        repo_path=repo_path,
        focus_paths=focus_paths,
        operational_seed_plan=operational_seed_plan,
        use_seed_files_as_connected_map=use_seed_files_as_connected_map,
        diagnostic_command=diagnostic_command,
        diagnostic_base_path=diagnostic_base_path,
        planner_model=planner_model,
        runtime_dir=runtime_dir,
        reuse_existing_state=reuse_existing_state,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_total_bytes=max_total_bytes,
        max_dependency_depth=max_dependency_depth,
        max_connected_files=max_connected_files,
        assume_clean_git_clone=assume_clean_git_clone,
        resolved_revision=resolved_revision,
        perform_warm_snapshot=perform_warm_snapshot,
        load_graph_summary=load_graph_summary,
        deps=_probe_run_support_deps(),
    )


def main() -> None:
    _probe_main_support(
        run_probe=run_probe,
        default_output=DEFAULT_OUTPUT,
        default_persisted_runtime_dir=DEFAULT_PERSISTED_RUNTIME_DIR,
        default_planner_model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,  # type: ignore[attr-defined]
    )


if __name__ == "__main__":
    main()
