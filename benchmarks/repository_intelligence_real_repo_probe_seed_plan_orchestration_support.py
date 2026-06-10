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
    bitbake_candidate_file_paths: list[str] = []
    if "bitbake" in detected_ecosystems:
        bitbake_candidate_file_paths = probe_module._bitbake_profile_candidate_paths(
            repo_path=repo_path,
            focus_paths=focus_paths,
            config_paths=sorted(config_path_candidates or set(discovered_config_paths)),
            max_files=max_files,
        )

    candidate_file_paths = (
        bitbake_candidate_file_paths
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
