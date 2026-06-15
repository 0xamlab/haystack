from __future__ import annotations

from collections import Counter
from pathlib import Path

from apps.api_server.services.repository_language_priority import canonical_repository_language


def documentation_host_ecosystem_counts(
    candidate_file_paths: list[str],
    *,
    repo_path: Path,
    documentation_ecosystem: str,
) -> Counter[str]:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    from benchmarks.repository_intelligence_real_repo_probe_seed_plan_support import (
        candidate_ecosystems_for_path,
    )

    canonical_documentation_ecosystem = canonical_repository_language(documentation_ecosystem)
    if not canonical_documentation_ecosystem:
        return Counter()
    documentation_ecosystems = {
        canonical_repository_language(ecosystem)
        for ecosystem in probe_module._DOCUMENTATION_PRIMARY_ECOSYSTEMS
        if canonical_repository_language(ecosystem)
    }
    counts: Counter[str] = Counter()
    for candidate_path in candidate_file_paths:
        for ecosystem in candidate_ecosystems_for_path(candidate_path, repo_path=repo_path):
            canonical_ecosystem = canonical_repository_language(ecosystem)
            if not canonical_ecosystem:
                continue
            if canonical_ecosystem == canonical_documentation_ecosystem:
                counts[canonical_ecosystem] += 1
                continue
            if canonical_ecosystem in documentation_ecosystems:
                continue
            if probe_module._is_non_operational_profile_path_for_ecosystems(
                candidate_path,
                ecosystems={canonical_ecosystem},
                repo_path=repo_path,
            ):
                continue
            counts[canonical_ecosystem] += 1
    return counts


def documentation_ecosystems_suppressed_in_finalize(
    detected_ecosystems: set[str],
    *,
    ecosystem_scores: Counter[str],
) -> set[str]:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    documentation_ecosystems = {
        canonical_repository_language(ecosystem)
        for ecosystem in probe_module._DOCUMENTATION_PRIMARY_ECOSYSTEMS
        if canonical_repository_language(ecosystem)
    }
    detected_documentation_ecosystems = detected_ecosystems & documentation_ecosystems
    if not detected_documentation_ecosystems:
        return set()
    detected_non_documentation_ecosystems = detected_ecosystems - documentation_ecosystems
    if not detected_non_documentation_ecosystems:
        return set()
    return {
        ecosystem
        for ecosystem in detected_documentation_ecosystems
        if any(
            ecosystem_scores[non_documentation_ecosystem] >= ecosystem_scores[ecosystem]
            for non_documentation_ecosystem in detected_non_documentation_ecosystems
        )
    }


def apply_documentation_host_ecosystem_scores(
    scores: Counter[str],
    *,
    documentation_ecosystem: str,
    ecosystem_counts: Counter[str],
    host_ecosystems: tuple[str, ...] = (),
    dominant_threshold: int = 4,
    documentation_bonus_cap: int = 160,
    documentation_bonus_base: int = 36,
    documentation_bonus_step: int = 12,
    host_bonus_cap: int = 140,
    host_bonus_base: int = 24,
    host_bonus_step: int = 8,
    documentation_penalty: int = 48,
) -> None:
    documentation_count = ecosystem_counts[documentation_ecosystem]
    if documentation_count <= 0:
        return
    resolved_host_ecosystems = host_ecosystems or tuple(
        ecosystem
        for ecosystem in ecosystem_counts
        if ecosystem != documentation_ecosystem
    )
    host_count = sum(ecosystem_counts[ecosystem] for ecosystem in resolved_host_ecosystems)
    if documentation_count >= dominant_threshold and documentation_count > host_count:
        scores[documentation_ecosystem] += min(
            documentation_bonus_cap,
            documentation_bonus_base + documentation_count * documentation_bonus_step,
        )
        return
    if not resolved_host_ecosystems:
        return
    dominant_host = max(
        resolved_host_ecosystems,
        key=lambda ecosystem: ecosystem_counts[ecosystem],
    )
    dominant_host_count = ecosystem_counts[dominant_host]
    if dominant_host_count <= 0 or documentation_count > max(1, host_count):
        return
    scores[dominant_host] += min(
        host_bonus_cap,
        host_bonus_base + dominant_host_count * host_bonus_step,
    )
    scores[documentation_ecosystem] = max(
        0,
        scores[documentation_ecosystem] - documentation_penalty,
    )
