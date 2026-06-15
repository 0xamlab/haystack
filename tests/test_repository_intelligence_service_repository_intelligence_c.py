"""Tests for repository_intelligence_service: repository_intelligence_c.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


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
