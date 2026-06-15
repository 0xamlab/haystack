from __future__ import annotations

from pathlib import Path
from typing import Any


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _derive_operational_seed_plan_without_diagnostics(
    *,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
) -> dict[str, Any]:
    probe_module = _probe_module()
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support
    from benchmarks import repository_intelligence_real_repo_probe_seed_plan_support as seed_plan_support
    repository_service = probe_module.repository_service

    concrete_focus_candidate_paths: list[str] = []
    if focus_paths:
        all_focus_paths_are_concrete_files = True
        for raw_focus_path in focus_paths:
            normalized_focus_path = repository_service._normalize_repository_relative_path(
                raw_focus_path
            )
            candidate = (repo_path / normalized_focus_path).resolve()
            if not (
                normalized_focus_path
                and candidate.exists()
                and candidate.is_file()
                and (candidate == repo_path or repo_path in candidate.parents)
            ):
                all_focus_paths_are_concrete_files = False
                break
            concrete_focus_candidate_paths.append(normalized_focus_path)
        if not all_focus_paths_are_concrete_files:
            concrete_focus_candidate_paths = []

    collection_support.begin_git_repo_relative_files_cache_scope()
    seed_plan_support.clear_candidate_ecosystem_path_cache()
    seed_plan_support.clear_candidate_ecosystem_count_cache()
    try:
        discovered_config_paths = probe_module._repo_profile_config_paths(
            repo_path=repo_path,
            focus_paths=focus_paths,
        )
        state = probe_module._SeedPlanState(
            repo_path=repo_path,
            focus_paths=focus_paths,
            max_files=max_files,
            discovered_config_paths=discovered_config_paths,
        )
        probe_module._dispatch_basenames_to_ecosystem(state)

        entrypoint_candidates = state.entrypoint_candidates
        support_root_candidates = state.support_root_candidates
        config_path_candidates = state.config_path_candidates
        detected_ecosystems = state.detected_ecosystems
        detected_ecosystem_scores = state.detected_ecosystem_scores
        operational_ecosystem_order = probe_module._ordered_operational_ecosystems(
            detected_ecosystems,
            ecosystem_scores=detected_ecosystem_scores,
        )
        bitbake_is_primary_operational_ecosystem = (
            bool(operational_ecosystem_order) and operational_ecosystem_order[0] == "bitbake"
        )
        bitbake_candidate_file_paths: list[str] = []
        if "bitbake" in detected_ecosystems:
            bitbake_candidate_file_paths = probe_module._bitbake_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                config_paths=sorted(config_path_candidates or set(discovered_config_paths)),
                max_files=max_files,
            )

        candidate_file_paths = (
            concrete_focus_candidate_paths
            or (
                bitbake_candidate_file_paths
                if bitbake_is_primary_operational_ecosystem
                else []
            )
            or probe_module._seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            )
        )
        if not candidate_file_paths:
            candidate_file_paths = probe_module._repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
        elif not concrete_focus_candidate_paths:
            # The seeded scan bridges from already-discovered entrypoint/support roots. If it
            # only surfaced the manifest config files themselves (no operational source — e.g. a
            # task-runner repo whose only detected manifest is a Containerfile, so the Justfile
            # and the scripts it orchestrates were never seeded), fall back to the broad scan so
            # the real operational surface is still discovered.
            normalized_discovered_config_paths = {
                repository_service._normalize_repository_relative_path(config_path)
                for config_path in discovered_config_paths
            }
            seeded_paths_beyond_manifests = [
                candidate_path
                for candidate_path in candidate_file_paths
                if repository_service._normalize_repository_relative_path(str(candidate_path))
                not in normalized_discovered_config_paths
            ]
            if not seeded_paths_beyond_manifests:
                broad_candidate_file_paths = probe_module._repo_profile_candidate_paths(
                    repo_path=repo_path,
                    focus_paths=focus_paths,
                    max_files=max_files,
                )
                candidate_file_paths = list(
                    dict.fromkeys([*candidate_file_paths, *broad_candidate_file_paths])
                )
        # An explicit, non-trivial directory focus pins the operational surface to that
        # subtree: candidate files outside it (e.g. a host application elsewhere in the repo)
        # must not be scored/ranked, otherwise the host language can outrank the focus
        # subtree's own ecosystem. Concrete-file focus and whole-repo focus are unaffected.
        focus_subtree_prefixes = [
            normalized_focus_path
            for raw_focus_path in focus_paths
            if (
                normalized_focus_path := repository_service._normalize_repository_relative_path(
                    raw_focus_path
                )
            )
            and normalized_focus_path != "."
            and not (repo_path / normalized_focus_path).is_file()
        ]
        if focus_subtree_prefixes and not concrete_focus_candidate_paths:
            focus_scoped_candidate_file_paths = [
                candidate_path
                for candidate_path in candidate_file_paths
                if (
                    normalized_candidate_path := repository_service._normalize_repository_relative_path(
                        str(candidate_path)
                    )
                )
                and any(
                    normalized_candidate_path == focus_prefix
                    or normalized_candidate_path.startswith(f"{focus_prefix}/")
                    for focus_prefix in focus_subtree_prefixes
                )
            ]
            if focus_scoped_candidate_file_paths:
                candidate_file_paths = focus_scoped_candidate_file_paths
        if not candidate_file_paths:
            return {
                "candidate_file_paths": [],
                "entrypoint_files": list(focus_paths),
                "support_roots": list(focus_paths),
                "config_paths": discovered_config_paths,
                "detected_ecosystems": probe_module._ordered_detected_ecosystems(
                    detected_ecosystems,
                ),
                "operational_ecosystems": probe_module._ordered_operational_ecosystems(
                    detected_ecosystems,
                    ecosystem_scores=detected_ecosystem_scores,
                ),
            }

        state.bitbake_candidate_file_paths = bitbake_candidate_file_paths
        state.candidate_file_paths = candidate_file_paths
        probe_module._apply_seed_plan_phase_a_support(state)
        probe_module._apply_seed_plan_phase_b_support(state)
        probe_module._apply_seed_plan_phase_c_support(state)
        probe_module._apply_seed_plan_phase_d_support(state)
        return probe_module._finalize_seed_plan(state)
    finally:
        collection_support.end_git_repo_relative_files_cache_scope()
        seed_plan_support.clear_candidate_ecosystem_path_cache()
        seed_plan_support.clear_candidate_ecosystem_count_cache()


def _derive_operational_seed_paths_without_diagnostics(
    *,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
) -> list[str]:
    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=focus_paths,
        max_files=max_files,
    )
    return list(seed_plan["entrypoint_files"])
