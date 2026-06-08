"""Tests for repository_intelligence_service: repository_intelligence_b.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


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


