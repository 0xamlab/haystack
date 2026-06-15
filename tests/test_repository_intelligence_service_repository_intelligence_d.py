"""Tests for repository_intelligence_service: repository_intelligence_d.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


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


def test_cfml_adapter_module_aliases_accept_preloaded_text_without_file_read(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cfml-preloaded-text-repo"
    (repo_path / "models").mkdir(parents=True)
    target_path = repo_path / "models" / "UserService.cfc"
    target_path.write_text(
        "component {\n"
        "    function listUsers() {\n"
        "        return [];\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    text = target_path.read_text(encoding="utf-8")
    target_path.unlink()

    aliases = repository_service.cfml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/UserService.cfc",
        stable_identifier=repository_service._stable_identifier,
        text=text,
    )

    assert "models.UserService" in aliases
    assert "listUsers" in aliases


def test_cfml_adapter_parse_file_assigns_component_reference_to_calling_function(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cfml-parse-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "UserService.cfc").write_text(
        "component {\n"
        "    function run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    source_path = repo_path / "Application.cfc"
    source_path.write_text(
        "component {\n"
        "    function onApplicationStart() {\n"
        "        local.userService = new models.UserService();\n"
        "        local.userService.run();\n"
        "    }\n"
        "    function other() {\n"
        "        return true;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["Application.cfc", "models/UserService.cfc"],
        root_path=repo_path,
    )
    text = source_path.read_text(encoding="utf-8")

    symbols, dependencies, references = repository_service.cfml_adapter.parse_file(
        "Application.cfc",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    start_symbol = next(symbol for symbol in symbols if symbol.symbol_name == "onApplicationStart")
    other_symbol = next(symbol for symbol in symbols if symbol.symbol_name == "other")

    assert any(
        dependency.target_file == "models/UserService.cfc"
        and dependency.target_symbol == "run"
        for dependency in dependencies
    )
    assert any(
        reference.source_symbol_id == start_symbol.symbol_id
        and reference.target_file == "models/UserService.cfc"
        and reference.target_names == ("run",)
        for reference in references
    )
    assert not any(
        reference.source_symbol_id == other_symbol.symbol_id
        and reference.target_file == "models/UserService.cfc"
        and reference.target_names == ("run",)
        for reference in references
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
