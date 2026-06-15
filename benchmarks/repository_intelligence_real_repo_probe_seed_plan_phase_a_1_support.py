from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from typing import Any


def apply_seed_plan_phase_a_1(state: Any) -> None:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _accumulate_detected_ecosystem_scores = probe_module._accumulate_detected_ecosystem_scores
    _autohotkey_profile_hints_from_candidates = probe_module._autohotkey_profile_hints_from_candidates
    _autoit_profile_hints_from_candidates = probe_module._autoit_profile_hints_from_candidates
    _batchfile_profile_hints_from_candidates = probe_module._batchfile_profile_hints_from_candidates
    _candidate_ecosystem_counts = probe_module._candidate_ecosystem_counts
    _candidate_ecosystems_for_path = probe_module._candidate_ecosystems_for_path
    _dockerfile_profile_hints_from_candidates = probe_module._dockerfile_profile_hints_from_candidates
    _fish_profile_hints_from_candidates = probe_module._fish_profile_hints_from_candidates
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _is_repo_profile_code_candidate = probe_module._is_repo_profile_code_candidate
    _just_profile_hints_from_candidates = probe_module._just_profile_hints_from_candidates
    _less_profile_hints_from_candidates = probe_module._less_profile_hints_from_candidates
    _makefile_profile_hints_from_candidates = probe_module._makefile_profile_hints_from_candidates
    _nushell_profile_hints_from_candidates = probe_module._nushell_profile_hints_from_candidates
    _register_candidate_ecosystems = probe_module._register_candidate_ecosystems
    _sass_profile_hints_from_candidates = probe_module._sass_profile_hints_from_candidates
    _scss_profile_hints_from_candidates = probe_module._scss_profile_hints_from_candidates
    _squirrel_profile_hints_from_candidates = probe_module._squirrel_profile_hints_from_candidates
    _stylus_profile_hints_from_candidates = probe_module._stylus_profile_hints_from_candidates
    _vimscript_profile_hints_from_candidates = probe_module._vimscript_profile_hints_from_candidates

    repo_path = state.repo_path
    focus_paths = state.focus_paths
    max_files = state.max_files
    discovered_config_paths = state.discovered_config_paths
    entrypoint_candidates = state.entrypoint_candidates
    support_root_candidates = state.support_root_candidates
    config_path_candidates = state.config_path_candidates
    detected_ecosystems = state.detected_ecosystems
    detected_ecosystem_scores = state.detected_ecosystem_scores
    entrypoint_candidate_ecosystems = state.entrypoint_candidate_ecosystems
    support_root_candidate_ecosystems = state.support_root_candidate_ecosystems
    bitbake_candidate_file_paths = state.bitbake_candidate_file_paths
    candidate_file_paths = state.candidate_file_paths

    if not detected_ecosystems:
        fallback_counts: Counter[str] = Counter()
        for candidate_path in candidate_file_paths:
            if repository_service._is_test_path(candidate_path):
                continue
            if _is_non_operational_profile_path(candidate_path):
                continue
            if not _is_repo_profile_code_candidate(candidate_path, repo_path=repo_path):
                continue
            fallback_counts.update(
                _candidate_ecosystems_for_path(candidate_path, repo_path=repo_path)
            )
        if fallback_counts:
            top_count = max(fallback_counts.values())
            detected_ecosystems.update(
                ecosystem
                for ecosystem, count in fallback_counts.items()
                if count == top_count and ecosystem not in {"unknown", "txt"}
            )

    if "vimscript" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _vimscript_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"vimscript"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"vimscript"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"vimscript"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "autohotkey" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _autohotkey_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"autohotkey"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"autohotkey"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"autohotkey"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "autoit" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _autoit_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"autoit"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"autoit"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"autoit"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "squirrel" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _squirrel_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"squirrel"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"squirrel"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"squirrel"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "nushell" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _nushell_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"nushell"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"nushell"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"nushell"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "fish" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _fish_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"fish"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"fish"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"fish"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "batchfile" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _batchfile_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"batchfile"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"batchfile"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"batchfile"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "makefile" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _makefile_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"makefile"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"makefile"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"makefile"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "just" in detected_ecosystems:
        entrypoints, roots, configs = _just_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"just"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"just"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"just"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    dockerfile_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"dockerfile", "shell", "python", "node", "go", "ruby"},
    )
    if dockerfile_ecosystem_counts["dockerfile"] > 0:
        entrypoints, roots, configs = _dockerfile_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("dockerfile")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"dockerfile"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"dockerfile"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"dockerfile"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            dockerfile_count = dockerfile_ecosystem_counts["dockerfile"]
            host_count = sum(
                dockerfile_ecosystem_counts[ecosystem]
                for ecosystem in ("shell", "python", "node", "go", "ruby")
            )
            if dockerfile_count >= max(6, host_count):
                detected_ecosystem_scores["dockerfile"] += min(180, 60 + dockerfile_count * 8)
            elif dockerfile_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("shell", "python", "node", "go", "ruby"),
                    key=lambda ecosystem: dockerfile_ecosystem_counts[ecosystem],
                )
                if dockerfile_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        160,
                        32 + dockerfile_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["dockerfile"] = max(
                        0,
                        detected_ecosystem_scores["dockerfile"] - 24,
                    )

    scss_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"scss", "ruby", "javascript", "typescript", "css"},
    )
    if scss_ecosystem_counts["scss"] > 0:
        entrypoints, roots, configs = _scss_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("scss")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"scss"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"scss"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"scss"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            scss_count = scss_ecosystem_counts["scss"]
            host_count = sum(
                scss_ecosystem_counts[ecosystem]
                for ecosystem in ("ruby", "javascript", "typescript", "css")
            )
            if scss_count >= max(2, host_count):
                detected_ecosystem_scores["scss"] += min(120, 30 + scss_count * 14)

    sass_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"sass", "ruby", "javascript", "typescript", "css"},
    )
    if sass_ecosystem_counts["sass"] > 0:
        entrypoints, roots, configs = _sass_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("sass")
            sass_count = sass_ecosystem_counts["sass"]
            host_count = sum(
                sass_ecosystem_counts[ecosystem]
                for ecosystem in ("ruby", "javascript", "typescript", "css")
            )
            style_root_count = sum(
                1
                for root in roots
                if PurePosixPath(root).name.lower() in {"sass", "styles", "stylesheets"}
            )
            sass_entrypoint_count = sum(
                1
                for entrypoint in entrypoints
                if "sass"
                in {
                    ecosystem.lower()
                    for ecosystem in _candidate_ecosystems_for_path(
                        entrypoint,
                        repo_path=repo_path,
                    )
                }
            )
            competitive_style_surface = (
                sass_entrypoint_count >= 2
                and style_root_count >= 1
                and sass_count >= 6
                and sass_count * 2 >= max(1, host_count)
            )
            should_operationalize_sass = (
                sass_count >= 2
                and (
                    host_count == 0
                    or sass_count >= host_count
                    or sass_count * 3 >= host_count
                    or competitive_style_surface
                )
            )
            if should_operationalize_sass:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"sass"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"sass"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"sass"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if sass_count >= max(2, host_count):
                    detected_ecosystem_scores["sass"] += min(140, 32 + sass_count * 14)
                elif competitive_style_surface:
                    non_sass_max_score = max(
                        (
                            score
                            for ecosystem, score in detected_ecosystem_scores.items()
                            if ecosystem != "sass"
                        ),
                        default=0,
                    )
                    detected_ecosystem_scores["sass"] = max(
                        detected_ecosystem_scores["sass"],
                        non_sass_max_score + 16,
                    )
            elif sass_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("ruby", "javascript", "typescript", "css"),
                    key=lambda ecosystem: sass_ecosystem_counts[ecosystem],
                )
                if sass_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + sass_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["sass"] = max(
                        0,
                        detected_ecosystem_scores["sass"] - 48,
                    )

    less_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"less", "javascript", "typescript", "css", "vue"},
    )
    if less_ecosystem_counts["less"] > 0:
        entrypoints, roots, configs = _less_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("less")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"less"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"less"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"less"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            less_count = less_ecosystem_counts["less"]
            host_count = sum(
                less_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "css", "vue")
            )
            if less_count >= max(2, host_count):
                detected_ecosystem_scores["less"] += min(120, 30 + less_count * 14)

    stylus_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"stylus", "javascript", "typescript", "css", "vue", "node"},
    )
    if stylus_ecosystem_counts["stylus"] > 0:
        entrypoints, roots, configs = _stylus_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("stylus")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"stylus"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"stylus"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"stylus"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            stylus_count = stylus_ecosystem_counts["stylus"]
            host_count = sum(
                stylus_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "css", "vue", "node")
            )
            if stylus_count >= max(2, host_count):
                detected_ecosystem_scores["stylus"] += min(120, 30 + stylus_count * 14)

    state.bitbake_candidate_file_paths = bitbake_candidate_file_paths
    state.candidate_file_paths = candidate_file_paths
