from __future__ import annotations

from typing import Any


def apply_seed_plan_phase_a_2(state: Any) -> None:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _accumulate_detected_ecosystem_scores = probe_module._accumulate_detected_ecosystem_scores
    _candidate_ecosystem_counts = probe_module._candidate_ecosystem_counts
    _haml_profile_hints_from_candidates = probe_module._haml_profile_hints_from_candidates
    _handlebars_profile_hints_from_candidates = probe_module._handlebars_profile_hints_from_candidates
    _jinja_profile_hints_from_candidates = probe_module._jinja_profile_hints_from_candidates
    _liquid_profile_hints_from_candidates = probe_module._liquid_profile_hints_from_candidates
    _mustache_profile_hints_from_candidates = probe_module._mustache_profile_hints_from_candidates
    _nunjucks_profile_hints_from_candidates = probe_module._nunjucks_profile_hints_from_candidates
    _register_candidate_ecosystems = probe_module._register_candidate_ecosystems
    _slim_profile_hints_from_candidates = probe_module._slim_profile_hints_from_candidates
    _smarty_profile_hints_from_candidates = probe_module._smarty_profile_hints_from_candidates
    _supplement_candidate_file_paths_for_suffix_roots = probe_module._supplement_candidate_file_paths_for_suffix_roots
    _twig_profile_hints_from_candidates = probe_module._twig_profile_hints_from_candidates

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

    jinja_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"jinja", "python", "shell", "yaml", "html", "css", "javascript", "typescript"},
    )
    if jinja_ecosystem_counts["jinja"] > 0:
        entrypoints, roots, configs = _jinja_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("jinja")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"jinja"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"jinja"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"jinja"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            jinja_count = jinja_ecosystem_counts["jinja"]
            host_count = sum(
                jinja_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "shell", "yaml", "html", "css", "javascript", "typescript")
            )
            if jinja_count >= max(2, host_count):
                detected_ecosystem_scores["jinja"] += min(120, 30 + jinja_count * 14)

    liquid_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"liquid", "ruby", "markdown", "html", "css", "scss", "javascript", "typescript"},
    )
    if liquid_ecosystem_counts["liquid"] > 0:
        entrypoints, roots, configs = _liquid_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("liquid")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"liquid"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"liquid"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"liquid"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            liquid_count = liquid_ecosystem_counts["liquid"]
            host_count = sum(
                liquid_ecosystem_counts[ecosystem]
                for ecosystem in ("ruby", "markdown", "html", "css", "scss", "javascript", "typescript")
            )
            if liquid_count >= max(2, host_count):
                detected_ecosystem_scores["liquid"] += min(120, 30 + liquid_count * 14)

    handlebars_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"handlebars", "javascript", "typescript", "html", "css", "scss", "ruby"},
    )
    if handlebars_ecosystem_counts["handlebars"] > 0:
        entrypoints, roots, configs = _handlebars_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("handlebars")
            handlebars_count = handlebars_ecosystem_counts["handlebars"]
            host_count = sum(
                handlebars_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "html", "css", "scss", "ruby")
            )
            should_operationalize_handlebars = (
                handlebars_count >= 3
                or host_count == 0
                or handlebars_count >= host_count
            )
            if should_operationalize_handlebars:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"handlebars"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"handlebars"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"handlebars"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if handlebars_count >= max(2, host_count):
                    detected_ecosystem_scores["handlebars"] += min(120, 30 + handlebars_count * 14)

    mustache_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"mustache", "javascript", "typescript", "html", "css", "scss", "ruby", "php"},
    )
    if mustache_ecosystem_counts["mustache"] > 0:
        entrypoints, roots, configs = _mustache_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("mustache")
            mustache_count = mustache_ecosystem_counts["mustache"]
            host_count = sum(
                mustache_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "html", "css", "scss", "ruby", "php")
            )
            should_operationalize_mustache = (
                mustache_count >= 2
                and (
                    host_count == 0
                    or mustache_count >= host_count
                    or (mustache_count >= 4 and mustache_count * 2 >= host_count)
                )
            )
            if should_operationalize_mustache:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"mustache"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"mustache"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"mustache"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if mustache_count >= max(2, host_count):
                    detected_ecosystem_scores["mustache"] += min(140, 32 + mustache_count * 14)

    nunjucks_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"nunjucks", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if nunjucks_ecosystem_counts["nunjucks"] > 0:
        entrypoints, roots, configs = _nunjucks_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("nunjucks")
            nunjucks_count = nunjucks_ecosystem_counts["nunjucks"]
            host_count = sum(
                nunjucks_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_nunjucks = (
                nunjucks_count >= 2
                and (
                    host_count == 0
                    or nunjucks_count >= host_count
                    or (nunjucks_count >= 4 and nunjucks_count * 2 >= host_count)
                )
            )
            if should_operationalize_nunjucks:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"nunjucks"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"nunjucks"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"nunjucks"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if nunjucks_count >= max(2, host_count):
                    detected_ecosystem_scores["nunjucks"] += min(140, 32 + nunjucks_count * 14)

    twig_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"twig", "php", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if twig_ecosystem_counts["twig"] > 0:
        entrypoints, roots, configs = _twig_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("twig")
            twig_count = twig_ecosystem_counts["twig"]
            host_count = sum(
                twig_ecosystem_counts[ecosystem]
                for ecosystem in ("php", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_twig = (
                twig_count >= 2
                and (
                    host_count == 0
                    or twig_count >= host_count
                    or (twig_count >= 4 and twig_count * 2 >= host_count)
                )
            )
            if should_operationalize_twig:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"twig"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"twig"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"twig"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if twig_count >= max(2, host_count):
                    detected_ecosystem_scores["twig"] += min(140, 32 + twig_count * 14)

    haml_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"haml", "ruby", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if haml_ecosystem_counts["haml"] > 0:
        entrypoints, roots, configs = _haml_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("haml")
            haml_count = haml_ecosystem_counts["haml"]
            host_count = sum(
                haml_ecosystem_counts[ecosystem]
                for ecosystem in ("ruby", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_haml = (
                haml_count >= 2
                and (
                    host_count == 0
                    or haml_count >= host_count
                    or (haml_count >= 4 and haml_count * 2 >= host_count)
                )
            )
            if should_operationalize_haml:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"haml"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"haml"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"haml"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if haml_count >= max(2, host_count):
                    detected_ecosystem_scores["haml"] += min(140, 32 + haml_count * 14)

    slim_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"slim", "ruby", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if slim_ecosystem_counts["slim"] > 0:
        entrypoints, roots, configs = _slim_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("slim")
            slim_count = slim_ecosystem_counts["slim"]
            host_count = sum(
                slim_ecosystem_counts[ecosystem]
                for ecosystem in ("ruby", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_slim = (
                slim_count >= 2
                and (
                    host_count == 0
                    or slim_count >= host_count
                    or (slim_count >= 4 and slim_count * 2 >= host_count)
                )
            )
            if should_operationalize_slim:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"slim"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"slim"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"slim"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if slim_count >= max(2, host_count):
                    detected_ecosystem_scores["slim"] += min(140, 32 + slim_count * 14)

    smarty_candidate_file_paths = candidate_file_paths
    smarty_ecosystem_counts = _candidate_ecosystem_counts(
        smarty_candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"smarty", "php", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if smarty_ecosystem_counts["smarty"] == 0:
        supplemented_smarty_candidate_file_paths = _supplement_candidate_file_paths_for_suffix_roots(
            repo_path=repo_path,
            candidate_file_paths=smarty_candidate_file_paths,
            suffixes={".tpl"},
            root_names=("templates", "views", "mails", "modules", "themes"),
            max_extra_files=max(32, min(256, max_files)),
        )
        if len(supplemented_smarty_candidate_file_paths) > len(smarty_candidate_file_paths):
            smarty_candidate_file_paths = supplemented_smarty_candidate_file_paths
            smarty_ecosystem_counts = _candidate_ecosystem_counts(
                smarty_candidate_file_paths,
                repo_path=repo_path,
                ecosystems={
                    "smarty",
                    "php",
                    "javascript",
                    "typescript",
                    "node",
                    "html",
                    "css",
                    "scss",
                },
            )
    if smarty_ecosystem_counts["smarty"] > 0:
        entrypoints, roots, configs = _smarty_profile_hints_from_candidates(
            repo_path,
            smarty_candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("smarty")
            smarty_count = smarty_ecosystem_counts["smarty"]
            host_count = sum(
                smarty_ecosystem_counts[ecosystem]
                for ecosystem in ("php", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_smarty = (
                smarty_count >= 2
                and (
                    host_count == 0
                    or smarty_count >= host_count
                    or (smarty_count >= 6 and smarty_count * 2 >= host_count)
                )
            )
            if should_operationalize_smarty:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"smarty"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"smarty"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"smarty"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if smarty_count >= max(2, host_count):
                    detected_ecosystem_scores["smarty"] += min(140, 32 + smarty_count * 14)
            candidate_file_paths = list(dict.fromkeys(smarty_candidate_file_paths))

    state.bitbake_candidate_file_paths = bitbake_candidate_file_paths
    state.candidate_file_paths = candidate_file_paths
