from __future__ import annotations

from pathlib import PurePosixPath

from typing import Any


def apply_seed_plan_phase_b_1(state: Any) -> None:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _accumulate_detected_ecosystem_scores = probe_module._accumulate_detected_ecosystem_scores
    _astro_profile_hints_from_candidates = probe_module._astro_profile_hints_from_candidates
    _blade_profile_hints_from_candidates = probe_module._blade_profile_hints_from_candidates
    _candidate_ecosystem_counts = probe_module._candidate_ecosystem_counts
    _candidate_ecosystems_for_path = probe_module._candidate_ecosystems_for_path
    _ejs_profile_hints_from_candidates = probe_module._ejs_profile_hints_from_candidates
    _erb_profile_hints_from_candidates = probe_module._erb_profile_hints_from_candidates
    _nextflow_profile_hints_from_candidates = probe_module._nextflow_profile_hints_from_candidates
    _pug_profile_hints_from_candidates = probe_module._pug_profile_hints_from_candidates
    _register_candidate_ecosystems = probe_module._register_candidate_ecosystems
    _robotframework_profile_hints_from_candidates = probe_module._robotframework_profile_hints_from_candidates
    _svelte_profile_hints_from_candidates = probe_module._svelte_profile_hints_from_candidates
    _vue_profile_hints_from_candidates = probe_module._vue_profile_hints_from_candidates

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

    erb_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"erb", "ruby", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if erb_ecosystem_counts["erb"] > 0:
        entrypoints, roots, configs = _erb_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("erb")
            erb_count = erb_ecosystem_counts["erb"]
            host_count = sum(
                erb_ecosystem_counts[ecosystem]
                for ecosystem in ("ruby", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_erb = (
                erb_count >= 2
                and (
                    host_count == 0
                    or erb_count >= host_count
                    or (erb_count >= 4 and erb_count * 2 >= host_count)
                )
            )
            if should_operationalize_erb:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"erb"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"erb"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"erb"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if erb_count >= max(2, host_count):
                    detected_ecosystem_scores["erb"] += min(140, 32 + erb_count * 14)

    pug_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"pug", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if pug_ecosystem_counts["pug"] > 0:
        entrypoints, roots, configs = _pug_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("pug")
            pug_count = pug_ecosystem_counts["pug"]
            host_count = sum(
                pug_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "node", "html", "css", "scss")
            )
            template_root_count = sum(
                1
                for root in roots
                if PurePosixPath(root).name.lower()
                in {"components", "includes", "layouts", "pages", "partials", "templates", "views"}
            )
            script_host_file_count = sum(
                1
                for candidate_path in candidate_file_paths
                if {
                    ecosystem.lower()
                    for ecosystem in _candidate_ecosystems_for_path(
                        candidate_path,
                        repo_path=repo_path,
                    )
                }.intersection({"javascript", "typescript", "node", "html"})
            )
            style_host_file_count = sum(
                1
                for candidate_path in candidate_file_paths
                if {
                    ecosystem.lower()
                    for ecosystem in _candidate_ecosystems_for_path(
                        candidate_path,
                        repo_path=repo_path,
                    )
                }.intersection({"css", "scss"})
            )
            competitive_template_surface = (
                len(entrypoints) >= 1
                and template_root_count >= 1
                and pug_count >= max(4, style_host_file_count)
                and pug_count >= max(4, script_host_file_count)
            )
            should_operationalize_pug = (
                pug_count >= 2
                and (
                    host_count == 0
                    or pug_count >= host_count
                    or (pug_count >= 4 and pug_count * 2 >= host_count)
                    or competitive_template_surface
                )
            )
            if should_operationalize_pug:
                _register_candidate_ecosystems(entrypoint_candidate_ecosystems, values=entrypoints, ecosystems={"pug"})
                _register_candidate_ecosystems(support_root_candidate_ecosystems, values=roots, ecosystems={"pug"})
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"pug"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if pug_count >= max(2, host_count):
                    detected_ecosystem_scores["pug"] += min(140, 32 + pug_count * 14)
                elif competitive_template_surface:
                    detected_ecosystem_scores["pug"] += min(160, 36 + pug_count * 12)

    ejs_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"ejs", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if ejs_ecosystem_counts["ejs"] > 0:
        entrypoints, roots, configs = _ejs_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("ejs")
            ejs_count = ejs_ecosystem_counts["ejs"]
            host_count = sum(
                ejs_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_ejs = (
                ejs_count >= 2
                and (
                    host_count == 0
                    or ejs_count >= host_count
                    or (ejs_count >= 4 and ejs_count * 2 >= host_count)
                )
            )
            if should_operationalize_ejs:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"ejs"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"ejs"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"ejs"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if ejs_count >= max(2, host_count):
                    detected_ecosystem_scores["ejs"] += min(140, 32 + ejs_count * 14)

    blade_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"blade", "php", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if blade_ecosystem_counts["blade"] > 0:
        entrypoints, roots, configs = _blade_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("blade")
            blade_count = blade_ecosystem_counts["blade"]
            host_count = sum(
                blade_ecosystem_counts[ecosystem]
                for ecosystem in ("php", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_blade = (
                blade_count >= 2
                and (
                    host_count == 0
                    or blade_count >= host_count
                    or (blade_count >= 4 and blade_count * 2 >= host_count)
                )
            )
            if should_operationalize_blade:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"blade"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"blade"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"blade"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["blade"] += min(140, 32 + blade_count * 14)

    vue_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"vue", "typescript", "javascript", "node", "html", "css", "scss"},
    )
    if vue_ecosystem_counts["vue"] > 0:
        entrypoints, roots, configs = _vue_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("vue")
            vue_count = vue_ecosystem_counts["vue"]
            host_count = sum(
                vue_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "html", "css", "scss")
            )
            should_operationalize_vue = (
                vue_count >= 2 and (host_count == 0 or vue_count >= host_count or (vue_count >= 4 and vue_count * 2 >= host_count))
            )
            if should_operationalize_vue:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"vue"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"vue"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"vue"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if vue_count >= max(2, host_count):
                    detected_ecosystem_scores["vue"] += min(140, 32 + vue_count * 14)

    svelte_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"svelte", "typescript", "javascript", "node", "html", "css", "scss"},
    )
    if svelte_ecosystem_counts["svelte"] > 0:
        entrypoints, roots, configs = _svelte_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("svelte")
            svelte_count = svelte_ecosystem_counts["svelte"]
            host_count = sum(
                svelte_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "html", "css", "scss")
            )
            should_operationalize_svelte = (
                svelte_count >= 2
                and (
                    host_count == 0
                    or svelte_count >= host_count
                    or (svelte_count >= 4 and svelte_count * 2 >= host_count)
                )
            )
            if should_operationalize_svelte:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"svelte"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"svelte"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"svelte"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if svelte_count >= max(2, host_count):
                    detected_ecosystem_scores["svelte"] += min(140, 32 + svelte_count * 14)

    astro_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"astro", "typescript", "javascript", "node", "html", "css", "scss"},
    )
    if astro_ecosystem_counts["astro"] > 0:
        entrypoints, roots, configs = _astro_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("astro")
            astro_count = astro_ecosystem_counts["astro"]
            host_count = sum(
                astro_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "html", "css", "scss")
            )
            should_operationalize_astro = (
                astro_count >= 2
                and (
                    host_count == 0
                    or astro_count >= host_count
                    or (astro_count >= 4 and astro_count * 2 >= host_count)
                )
            )
            if should_operationalize_astro:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"astro"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"astro"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"astro"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if astro_count >= max(2, host_count):
                    detected_ecosystem_scores["astro"] += min(140, 32 + astro_count * 14)

    nextflow_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"nextflow", "groovy", "python", "shell", "dockerfile", "javascript", "node"},
    )
    if nextflow_ecosystem_counts["nextflow"] > 0:
        nextflow_manifest_path = next(
            (
                path
                for path in candidate_file_paths
                if PurePosixPath(path).name.lower() == "nextflow.config"
            ),
            None,
        )
        entrypoints, roots, configs = _nextflow_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
            manifest_path=nextflow_manifest_path,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("nextflow")
            nextflow_count = nextflow_ecosystem_counts["nextflow"]
            host_count = sum(
                nextflow_ecosystem_counts[ecosystem]
                for ecosystem in ("groovy", "python", "shell", "dockerfile", "javascript", "node")
            )
            should_operationalize_nextflow = (
                nextflow_count >= 2
                and (
                    host_count == 0
                    or nextflow_count >= host_count
                    or (nextflow_count >= 4 and nextflow_count * 2 >= host_count)
                )
            )
            if should_operationalize_nextflow:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"nextflow"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"nextflow"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"nextflow"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if nextflow_count >= max(2, host_count):
                    detected_ecosystem_scores["nextflow"] += min(140, 32 + nextflow_count * 14)

    robotframework_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"robotframework", "python", "html", "javascript", "rst"},
    )
    if robotframework_ecosystem_counts["robotframework"] > 0:
        entrypoints, roots, configs = _robotframework_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("robotframework")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"robotframework"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"robotframework"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"robotframework"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            robot_count = robotframework_ecosystem_counts["robotframework"]
            # Documentation surfaces (e.g. README.rst / BUILD.rst) are not competing host code
            # for a Robot Framework suite — they must not gate the surface-dominance boost.
            host_count = sum(
                robotframework_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "html", "javascript")
            )
            if robot_count >= max(2, host_count):
                detected_ecosystem_scores["robotframework"] += min(120, 30 + robot_count * 14)
            elif robotframework_ecosystem_counts["rst"] > 0:
                detected_ecosystem_scores["robotframework"] += min(
                    120,
                    24 + robot_count * 14,
                )
                detected_ecosystem_scores["rst"] = max(
                    0,
                    detected_ecosystem_scores["rst"] - 24,
                )

    state.bitbake_candidate_file_paths = bitbake_candidate_file_paths
    state.candidate_file_paths = candidate_file_paths
