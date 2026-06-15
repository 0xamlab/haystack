"""Tests for repository_intelligence_service: repository_intelligence_a.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


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


def test_repository_intelligence_objective_c_sanitize_text_reuses_cached_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = (
        '#import <Foundation/Foundation.h>\n'
        '@interface ACMHelper : NSObject\n'
        '+ (void)work:(NSString *)value;\n'
        '@end\n'
    )

    repository_objective_c_primitives.clear_sanitize_text_cache()
    first = repository_objective_c_primitives.sanitize_text(source_text)

    def _unexpected_strip_comments(_text: str) -> str:
        raise AssertionError("expected Objective-C sanitize_text cache hit")

    monkeypatch.setattr(
        repository_objective_c_primitives,
        "strip_comments",
        _unexpected_strip_comments,
    )

    second = repository_objective_c_primitives.sanitize_text(source_text)

    assert second == first


def test_repository_intelligence_objective_c_reference_helpers_reuse_cached_line_offsets() -> None:
    source_text = (
        '#import "ACMHelper.h"\n'
        "@interface ACMHelper : NSObject\n"
        "+ (void)work:(NSString *)value;\n"
        "@end\n"
        "[ACMHelper work:@\"value\"];\n"
    )

    repository_objective_c_primitives._line_start_offsets.cache_clear()
    imports = repository_objective_c_primitives.iter_import_targets(source_text)
    messages = repository_objective_c_primitives.iter_message_sends(source_text)
    tokens = repository_objective_c_primitives.iter_type_reference_tokens(source_text)
    cache_info = repository_objective_c_primitives._line_start_offsets.cache_info()

    assert imports
    assert messages
    assert tokens
    assert cache_info.hits >= 1
    assert cache_info.misses == 1


def test_repository_intelligence_contracts_and_shared_helpers_are_modularized() -> None:
    assert repository_service.RepositoryIntelligenceError is (
        repository_contracts.RepositoryIntelligenceError
    )
    assert repository_service.RepositoryIntelligenceError.__module__ == (
        repository_contracts.__name__
    )
    assert repository_service._stable_identifier is repository_shared._stable_identifier
    assert repository_service._stable_identifier.__module__ == repository_shared.__name__


def test_repository_intelligence_stable_identifier_caches_repeat_payload_hashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_shared._payload_ascii_for_cache_key.cache_clear()
    repository_shared._payload_digest.cache_clear()
    repository_shared._stable_identifier_from_json.cache_clear()
    hash_call_count = {"value": 0}
    original_sha256 = repository_shared.hashlib.sha256

    def _counting_sha256(*args: object, **kwargs: object) -> object:
        hash_call_count["value"] += 1
        return original_sha256(*args, **kwargs)

    monkeypatch.setattr(repository_shared.hashlib, "sha256", _counting_sha256)
    payload = {"file_path": "src/Main.elm", "target_names": ("map",), "type": "references_symbol"}

    first = repository_shared._stable_identifier("ref", payload)
    first_ascii_cache = repository_shared._payload_ascii_for_cache_key.cache_info()
    first_digest_cache = repository_shared._payload_digest.cache_info()
    first_identifier_cache = repository_shared._stable_identifier_from_json.cache_info()
    second = repository_shared._stable_identifier("ref", payload)
    second_ascii_cache = repository_shared._payload_ascii_for_cache_key.cache_info()
    second_digest_cache = repository_shared._payload_digest.cache_info()
    second_identifier_cache = repository_shared._stable_identifier_from_json.cache_info()
    third = repository_shared._stable_identifier("sym", payload)
    third_ascii_cache = repository_shared._payload_ascii_for_cache_key.cache_info()
    third_digest_cache = repository_shared._payload_digest.cache_info()
    third_identifier_cache = repository_shared._stable_identifier_from_json.cache_info()

    assert first == second
    assert first.startswith("ref_")
    assert third.startswith("sym_")
    assert hash_call_count["value"] == 1
    assert first_ascii_cache.misses == 1
    assert second_ascii_cache.hits >= 1
    assert third_ascii_cache.hits >= 2
    assert first_digest_cache.misses == 1
    assert second_digest_cache.misses == 1
    assert third_digest_cache.misses == 1
    assert first_identifier_cache.misses == 1
    assert second_identifier_cache.hits >= 1
    assert third_identifier_cache.misses == 2


def test_repository_intelligence_stable_identifier_ignores_mapping_and_set_order() -> None:
    first = repository_shared._stable_identifier(
        "sym",
        {
            "names": {"beta", "alpha"},
            "location": ["src/main.py", 12],
            "metadata": {"kind": "function", "exported": True},
        },
    )
    second = repository_shared._stable_identifier(
        "sym",
        {
            "metadata": {"exported": True, "kind": "function"},
            "location": ["src/main.py", 12],
            "names": {"alpha", "beta"},
        },
    )

    assert first == second


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
    # Registry/aggregator modules hold one entry (import + dispatch/compat/suffix/alias
    # line) per supported language, so their size scales with the language count (180+),
    # not with logic complexity. Exempt them from the per-module line budget so wiring a
    # new language never requires bumping this test; the budget still guards every module
    # that carries real logic.
    aggregator_modules = frozenset(
        {
            "repository_intelligence_adapter_parser_dispatch.py",
            "repository_intelligence_compat_exports.py",
            "repository_intelligence_indexing.py",
            "repository_intelligence_root_scoped_aliases.py",
        }
    )
    over_budget: list[tuple[str, int]] = []
    for path in file_paths:
        if path.name in aggregator_modules:
            continue
        line_count = sum(1 for _ in path.open())
        if line_count <= 1000:
            continue
        over_budget.append(
            (str(path.relative_to(services_dir.parent.parent.parent)), line_count)
        )

    assert over_budget == []


def test_repository_intelligence_core_keeps_compat_exports_lazy() -> None:
    assert "repository_compat_exports" not in repository_service.__dict__
    assert repository_service.__getattr__("opencl_adapter") is repository_service.opencl_adapter
    assert "repository_compat_exports" not in repository_service.__dict__


def test_repository_intelligence_core_keeps_adapter_parser_dispatch_lazy_until_needed() -> None:
    result = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import json, sys; "
                "import apps.api_server.services.repository_intelligence as service; "
                "adapter='apps.api_server.services.repository_intelligence_adapter_parser_dispatch'; "
                "compat='apps.api_server.services.repository_intelligence_compat_exports'; "
                "before=(adapter in sys.modules, compat in sys.modules); "
                "_ = service._REGISTERED_ADAPTER_FILE_PARSERS; "
                "after=(adapter in sys.modules, compat in sys.modules); "
                "print(json.dumps({'before': before, 'after': after}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed == {
        "before": [False, False],
        "after": [True, False],
    }


def test_repository_intelligence_adapters_package_stays_lazy_until_named_export_requested() -> None:
    result = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import json, sys; "
                "pkg='apps.api_server.services.repository_intelligence_adapters'; "
                "import apps.api_server.services.repository_intelligence_adapters as adapters; "
                "before=sorted(name for name in sys.modules if name.startswith(pkg + '.')); "
                "_ = adapters.autoit; "
                "after=sorted(name for name in sys.modules if name.startswith(pkg + '.')); "
                "print(json.dumps({'before': before, 'after': after}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed["before"] == []
    assert "apps.api_server.services.repository_intelligence_adapters.autoit" in observed["after"]
    assert "apps.api_server.services.repository_intelligence_adapters.abap" not in observed["after"]


def test_repository_intelligence_adapters_package_discovers_on_disk_adapter_modules() -> None:
    result = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import json, sys; "
                "pkg='apps.api_server.services.repository_intelligence_adapters'; "
                "import apps.api_server.services.repository_intelligence_adapters as adapters; "
                "before=sorted(name for name in sys.modules if name.startswith(pkg + '.')); "
                "_ = adapters.emacslisp; "
                "_ = adapters.vyper; "
                "after=sorted(name for name in sys.modules if name.startswith(pkg + '.')); "
                "print(json.dumps({'before': before, 'after': after}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed["before"] == []
    assert "apps.api_server.services.repository_intelligence_adapters.emacslisp" in observed[
        "after"
    ]
    assert "apps.api_server.services.repository_intelligence_adapters.vyper" in observed["after"]
    assert "apps.api_server.services.repository_intelligence_adapters.abap" not in observed["after"]


def test_repository_intelligence_indexing_stays_lazy_until_specific_adapter_is_used() -> None:
    result = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import json, sys; "
                "pkg='apps.api_server.services.repository_intelligence_adapters'; "
                "import apps.api_server.services.repository_intelligence_indexing as indexing; "
                "before=sorted(name for name in sys.modules if name.startswith(pkg + '.')); "
                "_ = indexing.autoit_adapter.is_probable_autoit_source; "
                "after=sorted(name for name in sys.modules if name.startswith(pkg + '.')); "
                "print(json.dumps({'before': before, 'after': after}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed["before"] == []
    assert "apps.api_server.services.repository_intelligence_adapters.autoit" in observed["after"]
    assert "apps.api_server.services.repository_intelligence_adapters.abap" not in observed["after"]


def test_repository_intelligence_indexing_lazy_adapter_caches_loaded_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()

    class _FakeModule:
        def __init__(self) -> None:
            self.attribute_lookups = 0

        def __getattribute__(self, name: str) -> object:
            if name == "is_probable_autoit_source":
                object.__setattr__(
                    self,
                    "attribute_lookups",
                    object.__getattribute__(self, "attribute_lookups") + 1,
                )
                return sentinel
            return object.__getattribute__(self, name)

    class _FakeAdapters:
        def __init__(self) -> None:
            self.load_count = 0
            self._module = _FakeModule()

        def __getattr__(self, name: str) -> object:
            assert name == "autoit"
            self.load_count += 1
            return self._module

    fake_adapters = _FakeAdapters()
    monkeypatch.setattr(repository_indexing, "repository_adapters", fake_adapters)
    proxy = repository_indexing._lazy_adapter_module("autoit")

    assert proxy.is_probable_autoit_source is sentinel
    assert proxy.is_probable_autoit_source is sentinel
    assert fake_adapters.load_count == 1
    assert fake_adapters._module.attribute_lookups == 1


def test_repository_intelligence_native_resolution_lazy_adapter_caches_loaded_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()

    class _FakeModule:
        def __init__(self) -> None:
            self.attribute_lookups = 0

        def __getattribute__(self, name: str) -> object:
            if name == "parse_native_dependencies":
                object.__setattr__(
                    self,
                    "attribute_lookups",
                    object.__getattribute__(self, "attribute_lookups") + 1,
                )
                return lambda *_args, **_kwargs: sentinel
            return object.__getattribute__(self, name)

    class _FakeAdapters:
        def __init__(self) -> None:
            self.load_count = 0
            self._module = _FakeModule()

        def __getattr__(self, name: str) -> object:
            assert name == "assembly"
            self.load_count += 1
            return self._module

    fake_adapters = _FakeAdapters()
    monkeypatch.setattr(repository_native_resolution, "repository_adapters", fake_adapters)
    proxy = repository_native_resolution._lazy_adapter_module("assembly")

    assert proxy.parse_native_dependencies() is sentinel
    assert proxy.parse_native_dependencies() is sentinel
    assert fake_adapters.load_count == 1
    assert fake_adapters._module.attribute_lookups == 1


def test_repository_intelligence_core_keeps_simulation_imports_lazy() -> None:
    result = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import json, sys; "
                "simulate='apps.api_server.services.simulation_service'; "
                "import apps.api_server.services.repository_intelligence_core as core; "
                "after_import={"
                "'simulate': simulate in sys.modules"
                "}; "
                "_ = core.get_repository_intelligence_capabilities(); "
                "after_capabilities={"
                "'simulate': simulate in sys.modules"
                "}; "
                "print(json.dumps({'after_import': after_import, 'after_capabilities': after_capabilities}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed == {
        "after_import": {
            "simulate": False,
        },
        "after_capabilities": {
            "simulate": False,
        },
    }


def test_repository_intelligence_runtime_language_support_keeps_registry_imports_lazy() -> None:
    result = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import json, sys; "
                "dispatch='apps.api_server.services.repository_intelligence_adapter_parser_dispatch'; "
                "import apps.api_server.services.repository_intelligence_runtime_language_support as runtime_support; "
                "after_import={"
                "'dispatch_loaded': dispatch in sys.modules"
                "}; "
                "_ = runtime_support.build_repository_runtime_language_support_report(); "
                "after_report={"
                "'dispatch_loaded': dispatch in sys.modules"
                "}; "
                "print(json.dumps({'after_import': after_import, 'after_report': after_report}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed == {
        "after_import": {
            "dispatch_loaded": False,
        },
        "after_report": {
            "dispatch_loaded": True,
        },
    }


def test_repository_intelligence_core_keeps_decision_plan_workflow_lazy() -> None:
    result = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import json, sys; "
                "workflow='apps.api_server.services.repository_intelligence_decision_plan_workflow'; "
                "execution='apps.api_server.services.repository_intelligence_execution_workflow'; "
                "graph='apps.api_server.services.repository_intelligence_graph_workflow'; "
                "planner='apps.api_server.services.repository_intelligence_planner_generation'; "
                "snapshot='apps.api_server.services.repository_intelligence_snapshot_workflow'; "
                "analysis='apps.api_server.services.repository_intelligence_analysis_workflow'; "
                "simple='apps.api_server.services.repository_intelligence_simple_parser_dispatch'; "
                "language='apps.api_server.services.repository_intelligence_language_resolution'; "
                "aliases='apps.api_server.services.repository_intelligence_module_aliases'; "
                "autoit='apps.api_server.services.repository_intelligence_autoit_parser_dispatch'; "
                "fish='apps.api_server.services.repository_intelligence_fish_parser_dispatch'; "
                "janet='apps.api_server.services.repository_intelligence_janet_parser_dispatch'; "
                "squirrel='apps.api_server.services.repository_intelligence_squirrel_parser_dispatch'; "
                "source='apps.api_server.services.repository_intelligence_repository_source'; "
                "storage='apps.api_server.services.repository_intelligence_storage'; "
                "connector_model='apps.api_server.models.data_connector'; "
                "import apps.api_server.services.repository_intelligence_core as core; "
                "after_import={"
                "'workflow_loaded': workflow in sys.modules, "
                "'execution_loaded': execution in sys.modules, "
                "'graph_loaded': graph in sys.modules, "
                "'planner_loaded': planner in sys.modules, "
                "'snapshot_loaded': snapshot in sys.modules, "
                "'analysis_loaded': analysis in sys.modules, "
                "'simple_loaded': simple in sys.modules, "
                "'language_loaded': language in sys.modules, "
                "'aliases_loaded': aliases in sys.modules, "
                "'autoit_loaded': autoit in sys.modules, "
                "'fish_loaded': fish in sys.modules, "
                "'janet_loaded': janet in sys.modules, "
                "'squirrel_loaded': squirrel in sys.modules, "
                "'source_loaded': source in sys.modules, "
                "'storage_loaded': storage in sys.modules, "
                "'connector_model_loaded': connector_model in sys.modules"
                "}; "
                "_ = core.get_repository_intelligence_capabilities(); "
                "after_capabilities={"
                "'workflow_loaded': workflow in sys.modules, "
                "'execution_loaded': execution in sys.modules, "
                "'graph_loaded': graph in sys.modules, "
                "'planner_loaded': planner in sys.modules, "
                "'snapshot_loaded': snapshot in sys.modules, "
                "'analysis_loaded': analysis in sys.modules, "
                "'simple_loaded': simple in sys.modules, "
                "'language_loaded': language in sys.modules, "
                "'aliases_loaded': aliases in sys.modules, "
                "'autoit_loaded': autoit in sys.modules, "
                "'fish_loaded': fish in sys.modules, "
                "'janet_loaded': janet in sys.modules, "
                "'squirrel_loaded': squirrel in sys.modules, "
                "'source_loaded': source in sys.modules, "
                "'storage_loaded': storage in sys.modules, "
                "'connector_model_loaded': connector_model in sys.modules"
                "}; "
                "print(json.dumps({'after_import': after_import, 'after_capabilities': after_capabilities}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed == {
        "after_import": {
            "workflow_loaded": False,
            "execution_loaded": False,
            "graph_loaded": False,
            "planner_loaded": False,
            "snapshot_loaded": False,
            "analysis_loaded": False,
            "simple_loaded": False,
            "language_loaded": False,
            "aliases_loaded": False,
            "autoit_loaded": False,
            "fish_loaded": False,
            "janet_loaded": False,
            "squirrel_loaded": False,
            "source_loaded": False,
            "storage_loaded": False,
            "connector_model_loaded": False,
        },
        "after_capabilities": {
            "workflow_loaded": False,
            "execution_loaded": False,
            "graph_loaded": False,
            "planner_loaded": False,
            "snapshot_loaded": False,
            "analysis_loaded": False,
            "simple_loaded": False,
            "language_loaded": False,
            "aliases_loaded": False,
            "autoit_loaded": False,
            "fish_loaded": False,
            "janet_loaded": False,
            "squirrel_loaded": False,
            "source_loaded": False,
            "storage_loaded": False,
            "connector_model_loaded": False,
        },
    }


def test_repository_intelligence_root_scoped_aliases_stays_lazy_until_specific_dependencies_are_used() -> None:
    result = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import json, sys; "
                "pkg='apps.api_server.services.repository_intelligence_adapters'; "
                "pas='apps.api_server.services.repository_intelligence_pascal_solidity_dispatch'; "
                "import apps.api_server.services.repository_intelligence_root_scoped_aliases as aliases; "
                "before={"
                "'adapter_modules': sorted(name for name in sys.modules if name.startswith(pkg + '.')), "
                "'pascal_loaded': pas in sys.modules"
                "}; "
                "_ = aliases.jvm_adapter.scala_package_aliases_for_path; "
                "_ = aliases._normalize_pascal_target('Foo.Bar'); "
                "after={"
                "'adapter_modules': sorted(name for name in sys.modules if name.startswith(pkg + '.')), "
                "'pascal_loaded': pas in sys.modules"
                "}; "
                "print(json.dumps({'before': before, 'after': after}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed["before"] == {
        "adapter_modules": [],
        "pascal_loaded": False,
    }
    assert "apps.api_server.services.repository_intelligence_adapters.jvm" in observed["after"][
        "adapter_modules"
    ]
    assert (
        "apps.api_server.services.repository_intelligence_adapters.abap"
        not in observed["after"]["adapter_modules"]
    )
    assert observed["after"]["pascal_loaded"] is True


def test_repository_intelligence_native_resolution_stays_lazy_until_specific_adapter_is_used() -> None:
    result = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import json, sys; "
                "pkg='apps.api_server.services.repository_intelligence_adapters'; "
                "import apps.api_server.services.repository_intelligence_native_resolution as native_resolution; "
                "before=sorted(name for name in sys.modules if name.startswith(pkg + '.')); "
                "_ = native_resolution.assembly_adapter.resolve_import; "
                "after=sorted(name for name in sys.modules if name.startswith(pkg + '.')); "
                "print(json.dumps({'before': before, 'after': after}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed["before"] == []
    assert "apps.api_server.services.repository_intelligence_adapters.assembly_support" in observed[
        "after"
    ]
    assert "apps.api_server.services.repository_intelligence_adapters.abap_support" not in observed[
        "after"
    ]


def test_repository_intelligence_native_dispatch_stays_lazy_until_specific_paths_are_used() -> None:
    result = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import json, sys; "
                "pkg='apps.api_server.services.repository_intelligence_adapters'; "
                "native='apps.api_server.services.repository_intelligence_native_resolution'; "
                "apple='apps.api_server.services.repository_intelligence_applescript_parser_dispatch'; "
                "vba='apps.api_server.services.repository_intelligence_vba_parser_dispatch'; "
                "import apps.api_server.services.repository_intelligence_native_dispatch as dispatch; "
                "before={"
                "'adapter_modules': sorted(name for name in sys.modules if name.startswith(pkg + '.')), "
                "'native_loaded': native in sys.modules, "
                "'apple_loaded': apple in sys.modules, "
                "'vba_loaded': vba in sys.modules"
                "}; "
                "_ = dispatch._parse_applescript_dependencies_only('Script.applescript', '', {}); "
                "_ = dispatch._parse_assembly_dependencies_only('src/foo.asm', '', {}); "
                "after={"
                "'adapter_modules': sorted(name for name in sys.modules if name.startswith(pkg + '.')), "
                "'native_loaded': native in sys.modules, "
                "'apple_loaded': apple in sys.modules, "
                "'vba_loaded': vba in sys.modules"
                "}; "
                "print(json.dumps({'before': before, 'after': after}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed["before"] == {
        "adapter_modules": [],
        "native_loaded": False,
        "apple_loaded": False,
        "vba_loaded": False,
    }
    assert "apps.api_server.services.repository_intelligence_adapters.assembly_support" in observed[
        "after"
    ]["adapter_modules"]
    assert "apps.api_server.services.repository_intelligence_adapters.abap_support" not in observed[
        "after"
    ]["adapter_modules"]
    assert observed["after"]["native_loaded"] is True
    assert observed["after"]["apple_loaded"] is True
    assert observed["after"]["vba_loaded"] is False


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
