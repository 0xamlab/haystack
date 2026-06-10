from __future__ import annotations


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _probe_graph_support_deps():
    probe_module = _probe_module()

    return probe_module.ProbeGraphSupportDependencies(
        candidate_repository_file_paths=probe_module._candidate_repository_file_paths,
        connected_map_candidate_file_limit=probe_module._connected_map_candidate_file_limit,
        looks_like_concrete_file_seed=probe_module._looks_like_concrete_file_seed,
        normalized_candidate_file_paths=probe_module._normalized_candidate_file_paths,
        seed_dependency_files=probe_module._seed_dependency_files,
        repository_service=probe_module.repository_service,
    )


def _probe_prepass_support_deps():
    probe_module = _probe_module()

    return probe_module.ProbePrepassDependencies(
        default_exclude_patterns=probe_module.DEFAULT_EXCLUDE_PATTERNS,
        default_include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        prepass_cache_schema_version=probe_module._PREPASS_CACHE_SCHEMA_VERSION,
        build_connected_dependency_map=probe_module._build_connected_dependency_map,
        candidate_config_focus_paths=probe_module._candidate_config_focus_paths,
        candidate_solutions=probe_module._candidate_solutions,
        derive_operational_seed_plan_without_diagnostics=probe_module._derive_operational_seed_plan_without_diagnostics,
        effective_focus_paths_for_snapshot=probe_module._effective_focus_paths_for_snapshot,
        focus_paths_from_diagnostics=probe_module._focus_paths_from_diagnostics,
        inventory_repo_surface=probe_module._inventory_repo_surface,
        parse_repository_diagnostics=probe_module.parse_repository_diagnostics,
        resolve_diagnostic_base_path=probe_module._resolve_diagnostic_base_path,
        resolve_diagnostic_project_path=probe_module._resolve_diagnostic_project_path,
        run_command=probe_module._run_command,
    )


def _probe_run_support_deps():
    probe_module = _probe_module()

    return probe_module.ProbeRunDependencies(
        default_exclude_patterns=probe_module.DEFAULT_EXCLUDE_PATTERNS,
        default_include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        compute_probe_prepass=probe_module._compute_probe_prepass,
        load_snapshot_graph_summary=probe_module._load_snapshot_graph_summary,
        repository_connector=probe_module._repository_connector,
    )
