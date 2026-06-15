from __future__ import annotations

from pathlib import PurePosixPath

from typing import Any

from benchmarks.repository_intelligence_real_repo_probe_documentation_score_support import (
    apply_documentation_host_ecosystem_scores,
    documentation_host_ecosystem_counts,
)


def apply_seed_plan_phase_c(state: Any) -> None:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _accumulate_detected_ecosystem_scores = probe_module._accumulate_detected_ecosystem_scores
    _asciidoc_profile_hints_from_candidates = probe_module._asciidoc_profile_hints_from_candidates
    _bqn_profile_hints_from_candidates = probe_module._bqn_profile_hints_from_candidates
    _candidate_ecosystem_counts = probe_module._candidate_ecosystem_counts
    _cuda_profile_hints_from_candidates = probe_module._cuda_profile_hints_from_candidates
    _cython_profile_hints_from_candidates = probe_module._cython_profile_hints_from_candidates
    _j_profile_hints_from_candidates = probe_module._j_profile_hints_from_candidates
    _just_profile_hints_from_candidates = probe_module._just_profile_hints_from_candidates
    _lex_profile_hints_from_candidates = probe_module._lex_profile_hints_from_candidates
    _moonbit_profile_hints_from_candidates = probe_module._moonbit_profile_hints_from_candidates
    _opencl_profile_hints_from_candidates = probe_module._opencl_profile_hints_from_candidates
    _org_profile_hints_from_candidates = probe_module._org_profile_hints_from_candidates
    _rebol_profile_hints_from_candidates = probe_module._rebol_profile_hints_from_candidates
    _register_candidate_ecosystems = probe_module._register_candidate_ecosystems
    _rescript_profile_hints_from_candidates = probe_module._rescript_profile_hints_from_candidates
    _roc_profile_hints_from_candidates = probe_module._roc_profile_hints_from_candidates
    _rst_profile_hints_from_candidates = probe_module._rst_profile_hints_from_candidates
    _stan_profile_hints_from_candidates = probe_module._stan_profile_hints_from_candidates
    _tex_profile_hints_from_candidates = probe_module._tex_profile_hints_from_candidates
    _typst_profile_hints_from_candidates = probe_module._typst_profile_hints_from_candidates
    _supplement_candidate_file_paths_for_surface_dir_parts = (
        probe_module._supplement_candidate_file_paths_for_surface_dir_parts
    )

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

    bqn_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"bqn", "apl", "c", "cpp", "javascript", "node", "makefile"},
    )
    if bqn_ecosystem_counts["bqn"] > 0:
        entrypoints, roots, configs = _bqn_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("bqn")
            bqn_count = bqn_ecosystem_counts["bqn"]
            host_count = sum(
                bqn_ecosystem_counts[ecosystem]
                for ecosystem in ("apl", "c", "cpp", "javascript", "node", "makefile")
            )
            should_operationalize_bqn = (
                bqn_count >= 2
                and (
                    host_count == 0
                    or bqn_count >= host_count
                    or bqn_count * 3 >= host_count
                )
            )
            if should_operationalize_bqn:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"bqn"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"bqn"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"bqn"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if bqn_count >= max(2, host_count):
                    detected_ecosystem_scores["bqn"] += min(140, 32 + bqn_count * 14)
            elif bqn_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("apl", "c", "cpp", "javascript", "node", "makefile"),
                    key=lambda ecosystem: bqn_ecosystem_counts[ecosystem],
                )
                if bqn_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + bqn_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["bqn"] = max(
                        0,
                        detected_ecosystem_scores["bqn"] - 48,
                    )

    j_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"j", "c", "cpp", "makefile", "starlark"},
    )
    if j_ecosystem_counts["j"] > 0:
        entrypoints, roots, configs = _j_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("j")
            j_count = j_ecosystem_counts["j"]
            host_count = sum(
                j_ecosystem_counts[ecosystem]
                for ecosystem in ("c", "cpp", "makefile", "starlark")
            )
            should_operationalize_j = (
                j_count >= 2
                and (
                    host_count == 0
                    or j_count >= host_count
                    or j_count * 3 >= host_count
                )
            )
            if should_operationalize_j:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"j"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"j"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"j"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if j_count >= max(2, host_count):
                    detected_ecosystem_scores["j"] += min(180, 40 + j_count * 12)
            elif j_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("c", "cpp", "makefile", "starlark"),
                    key=lambda ecosystem: j_ecosystem_counts[ecosystem],
                )
                if j_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + j_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["j"] = max(
                        0,
                        detected_ecosystem_scores["j"] - 48,
                    )

    lex_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"lex", "c", "cpp", "cmake", "makefile", "m4", "python", "qmake"},
    )
    if lex_ecosystem_counts["lex"] > 0:
        entrypoints, roots, configs = _lex_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("lex")
            lex_count = lex_ecosystem_counts["lex"]
            host_count = sum(
                lex_ecosystem_counts[ecosystem]
                for ecosystem in ("c", "cpp", "cmake", "makefile", "m4", "python", "qmake")
            )
            should_operationalize_lex = (
                lex_count >= 1
                and (
                    host_count == 0
                    or lex_count >= host_count
                    or lex_count * 2 >= host_count
                )
            )
            if should_operationalize_lex:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"lex"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"lex"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"lex"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["lex"] += min(140, 36 + lex_count * 18)
            elif lex_count * 2 <= max(1, host_count):
                detected_ecosystem_scores["lex"] = max(
                    0,
                    detected_ecosystem_scores["lex"] - 24,
                )

    rebol_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"rebol", "r", "python", "shell", "javascript", "node", "makefile"},
    )
    if rebol_ecosystem_counts["rebol"] > 0:
        entrypoints, roots, configs = _rebol_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("rebol")
            rebol_count = rebol_ecosystem_counts["rebol"]
            host_count = sum(
                rebol_ecosystem_counts[ecosystem]
                for ecosystem in ("r", "python", "shell", "javascript", "node", "makefile")
            )
            should_operationalize_rebol = (
                rebol_count >= 2
                and (
                    host_count == 0
                    or rebol_count >= host_count
                    or rebol_count * 3 >= host_count
                )
            )
            if should_operationalize_rebol:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"rebol"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"rebol"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"rebol"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if rebol_count >= max(2, host_count):
                    detected_ecosystem_scores["rebol"] += min(140, 32 + rebol_count * 14)
            elif rebol_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("r", "python", "shell", "javascript", "node", "makefile"),
                    key=lambda ecosystem: rebol_ecosystem_counts[ecosystem],
                )
                if rebol_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + rebol_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["rebol"] = max(
                        0,
                        detected_ecosystem_scores["rebol"] - 48,
                    )

    rescript_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"rescript", "typescript", "javascript", "node", "shell"},
    )
    if rescript_ecosystem_counts["rescript"] > 0:
        entrypoints, roots, configs = _rescript_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("rescript")
            rescript_count = rescript_ecosystem_counts["rescript"]
            host_count = sum(
                rescript_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "shell")
            )
            should_operationalize_rescript = (
                rescript_count >= 2
                and (
                    host_count == 0
                    or rescript_count >= host_count
                    or rescript_count * 3 >= host_count
                )
            )
            if should_operationalize_rescript:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"rescript"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"rescript"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"rescript"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if rescript_count >= max(2, host_count):
                    detected_ecosystem_scores["rescript"] += min(140, 32 + rescript_count * 14)
            elif rescript_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("typescript", "javascript", "node", "shell"),
                    key=lambda ecosystem: rescript_ecosystem_counts[ecosystem],
                )
                if rescript_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + rescript_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["rescript"] = max(
                        0,
                        detected_ecosystem_scores["rescript"] - 48,
                    )

    just_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"just", "dockerfile", "shell", "python", "node"},
    )
    if just_ecosystem_counts["just"] > 0:
        entrypoints, roots, configs = _just_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("just")
            just_count = just_ecosystem_counts["just"]
            host_count = sum(
                just_ecosystem_counts[ecosystem]
                for ecosystem in ("dockerfile", "shell", "python", "node")
            )
            should_operationalize_just = (
                just_count >= 1
                and (
                    host_count == 0
                    or just_count >= host_count
                    or just_count * 3 >= host_count
                )
            )
            if should_operationalize_just:
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
                detected_ecosystem_scores["just"] += min(140, 32 + just_count * 14)
                non_just_max_score = max(
                    (
                        score
                        for ecosystem, score in detected_ecosystem_scores.items()
                        if ecosystem != "just"
                    ),
                    default=0,
                )
                detected_ecosystem_scores["just"] = max(
                    detected_ecosystem_scores["just"],
                    non_just_max_score + 16,
                )
            elif just_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("dockerfile", "shell", "python", "node"),
                    key=lambda ecosystem: just_ecosystem_counts[ecosystem],
                )
                if just_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + just_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["just"] = max(
                        0,
                        detected_ecosystem_scores["just"] - 48,
                    )

    foxpro_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"foxpro", "node", "javascript", "shell"},
    )
    if foxpro_ecosystem_counts["foxpro"] > 0:
        detected_ecosystems.add("foxpro")
        foxpro_count = foxpro_ecosystem_counts["foxpro"]
        host_count = sum(
            foxpro_ecosystem_counts[ecosystem]
            for ecosystem in ("node", "javascript", "shell")
        )
        should_operationalize_foxpro = (
            foxpro_count >= 2
            and (
                host_count == 0
                or foxpro_count >= host_count
                or foxpro_count * 3 >= host_count
            )
        )
        if should_operationalize_foxpro:
            detected_ecosystem_scores["foxpro"] += min(140, 32 + foxpro_count * 14)
            non_foxpro_max_score = max(
                (
                    score
                    for ecosystem, score in detected_ecosystem_scores.items()
                    if ecosystem != "foxpro"
                ),
                default=0,
            )
            detected_ecosystem_scores["foxpro"] = max(
                detected_ecosystem_scores["foxpro"],
                non_foxpro_max_score + 16,
            )
        elif foxpro_count * 2 <= max(1, host_count):
            dominant_host = max(
                ("node", "javascript", "shell"),
                key=lambda ecosystem: foxpro_ecosystem_counts[ecosystem],
            )
            if foxpro_ecosystem_counts[dominant_host] > 0:
                detected_ecosystem_scores[dominant_host] += min(
                    140,
                    24 + foxpro_ecosystem_counts[dominant_host] * 6,
                )
                detected_ecosystem_scores["foxpro"] = max(
                    0,
                    detected_ecosystem_scores["foxpro"] - 48,
                )

    moonbit_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"moonbit", "rust", "python", "shell", "dockerfile", "javascript", "node"},
    )
    if moonbit_ecosystem_counts["moonbit"] > 0:
        moonbit_config_paths = sorted(config_path_candidates or set(discovered_config_paths))
        moonbit_manifest_path = next(
            (
                path
                for path in moonbit_config_paths
                if PurePosixPath(path).name.lower() == "moon.mod"
            ),
            None,
        ) or next(
            (
                path
                for path in moonbit_config_paths
                if PurePosixPath(path).name.lower() == "moon.pkg"
            ),
            None,
        )
        entrypoints, roots, configs = _moonbit_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
            manifest_path=moonbit_manifest_path or "",
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("moonbit")
            moonbit_count = len(entrypoints)
            host_count = sum(
                moonbit_ecosystem_counts[ecosystem]
                for ecosystem in ("rust", "python", "shell", "dockerfile", "javascript", "node")
            )
            should_operationalize_moonbit = (
                moonbit_count >= 2
                and (
                    host_count == 0
                    or moonbit_count >= host_count
                    or (moonbit_count >= 4 and moonbit_count * 2 >= host_count)
                )
            )
            if should_operationalize_moonbit:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"moonbit"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"moonbit"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"moonbit"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if moonbit_count >= max(2, host_count):
                    detected_ecosystem_scores["moonbit"] += min(140, 32 + moonbit_count * 14)
            elif moonbit_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("rust", "python", "shell", "dockerfile", "javascript", "node"),
                    key=lambda ecosystem: moonbit_ecosystem_counts[ecosystem],
                )
                if moonbit_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + moonbit_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["moonbit"] = max(
                        0,
                        detected_ecosystem_scores["moonbit"] - 48,
                    )

    roc_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"roc", "rust", "zig", "nix", "shell", "python", "javascript", "node"},
    )
    if roc_ecosystem_counts["roc"] > 0:
        entrypoints, roots, configs = _roc_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("roc")
            roc_count = len(entrypoints)
            host_count = sum(
                roc_ecosystem_counts[ecosystem]
                for ecosystem in ("rust", "zig", "nix", "shell", "python", "javascript", "node")
            )
            should_operationalize_roc = roc_count >= max(6, host_count * 2)
            if should_operationalize_roc:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"roc"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"roc"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"roc"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["roc"] += min(140, 28 + roc_count * 14)
            elif roc_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("rust", "zig", "nix", "shell", "python", "javascript", "node"),
                    key=lambda ecosystem: roc_ecosystem_counts[ecosystem],
                )
                if roc_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + roc_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["roc"] = max(
                        0,
                        detected_ecosystem_scores["roc"] - 48,
                    )

    typst_ecosystem_counts = documentation_host_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        documentation_ecosystem="typst",
    )
    if typst_ecosystem_counts["typst"] > 0:
        # A typst package registry spreads ``.typ`` across many ``packages/preview/*/*`` dirs;
        # the bridged candidate scan can sample only part of that surface. Pull in the rest of
        # the ``.typ`` files under typst package dirs so the package-surface dominance gate sees
        # the full registry (mirrors the shaderlab surface supplement in phase_d).
        candidate_file_paths = _supplement_candidate_file_paths_for_surface_dir_parts(
            repo_path=repo_path,
            candidate_file_paths=candidate_file_paths,
            suffixes={".typ"},
            directory_parts={"packages", "preview", "template"},
            max_extra_files=min(max_files, 64),
        )
        state.candidate_file_paths = candidate_file_paths
        typst_ecosystem_counts = documentation_host_ecosystem_counts(
            candidate_file_paths,
            repo_path=repo_path,
            documentation_ecosystem="typst",
        )
        entrypoints, roots, configs = _typst_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("typst")
            typst_count = typst_ecosystem_counts["typst"]
            typst_entrypoint_count = len(entrypoints)
            typst_package_root_count = sum(
                1
                for root in roots
                if PurePosixPath(root).parts
                and PurePosixPath(root).parts[0].lower() in {"package", "packages"}
            )
            typst_host_count = sum(
                typst_ecosystem_counts[ecosystem]
                for ecosystem in ("rust", "node", "shell", "jinja", "toml")
            )
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"typst"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"typst"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"typst"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            apply_documentation_host_ecosystem_scores(
                detected_ecosystem_scores,
                documentation_ecosystem="typst",
                ecosystem_counts=typst_ecosystem_counts,
                dominant_threshold=3,
                documentation_bonus_cap=140,
                documentation_bonus_base=28,
                host_bonus_cap=120,
            )
            competitive_typst_package_surface = (
                typst_count >= 24
                and typst_entrypoint_count >= 16
                and typst_package_root_count >= 8
                and typst_count >= max(24, typst_host_count * 4)
            )
            if competitive_typst_package_surface:
                non_typst_max_score = max(
                    (
                        score
                        for ecosystem, score in detected_ecosystem_scores.items()
                        if ecosystem != "typst"
                    ),
                    default=0,
                )
                detected_ecosystem_scores["typst"] = max(
                    detected_ecosystem_scores["typst"],
                    non_typst_max_score + 16,
                )

    tex_ecosystem_counts = documentation_host_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        documentation_ecosystem="tex",
    )
    if tex_ecosystem_counts["tex"] > 0:
        entrypoints, roots, configs = _tex_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("tex")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"tex"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"tex"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"tex"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            apply_documentation_host_ecosystem_scores(
                detected_ecosystem_scores,
                documentation_ecosystem="tex",
                ecosystem_counts=tex_ecosystem_counts,
            )

    rst_ecosystem_counts = documentation_host_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        documentation_ecosystem="rst",
    )
    if rst_ecosystem_counts["rst"] > 0:
        entrypoints, roots, configs = _rst_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("rst")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"rst"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"rst"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"rst"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            apply_documentation_host_ecosystem_scores(
                detected_ecosystem_scores,
                documentation_ecosystem="rst",
                ecosystem_counts=rst_ecosystem_counts,
            )

    asciidoc_ecosystem_counts = documentation_host_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        documentation_ecosystem="asciidoc",
    )
    if asciidoc_ecosystem_counts["asciidoc"] > 0:
        entrypoints, roots, configs = _asciidoc_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("asciidoc")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"asciidoc"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"asciidoc"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"asciidoc"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            apply_documentation_host_ecosystem_scores(
                detected_ecosystem_scores,
                documentation_ecosystem="asciidoc",
                ecosystem_counts=asciidoc_ecosystem_counts,
            )

    org_ecosystem_counts = documentation_host_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        documentation_ecosystem="org",
    )
    if org_ecosystem_counts["org"] > 0:
        entrypoints, roots, configs = _org_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("org")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"org"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"org"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"org"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            apply_documentation_host_ecosystem_scores(
                detected_ecosystem_scores,
                documentation_ecosystem="org",
                ecosystem_counts=org_ecosystem_counts,
            )

    cython_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"cython", "python", "c", "cpp"},
    )
    if cython_ecosystem_counts["cython"] > 0:
        entrypoints, roots, configs = _cython_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"cython"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"cython"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"cython"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            cython_count = cython_ecosystem_counts["cython"]
            host_count = sum(
                cython_ecosystem_counts[ecosystem] for ecosystem in ("python", "c", "cpp")
            )
            if cython_count >= max(2, host_count):
                detected_ecosystem_scores["cython"] += min(120, 30 + cython_count * 14)

    cuda_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"cuda", "c", "cpp", "python", "cmake"},
    )
    if cuda_ecosystem_counts["cuda"] > 0:
        entrypoints, roots, configs = _cuda_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("cuda")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"cuda"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"cuda"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"cuda"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            cuda_count = cuda_ecosystem_counts["cuda"]
            host_count = sum(
                cuda_ecosystem_counts[ecosystem] for ecosystem in ("c", "cpp", "python", "cmake")
            )
            cuda_entrypoint_root_count = len(
                {
                    normalized_root
                    for path in entrypoints
                    if (
                        normalized_root := repository_service._normalize_repository_relative_path(
                            str(PurePosixPath(path).parent)
                        )
                    )
                }
            )
            cuda_neighbor_config_count = len(configs)
            if (
                cuda_count >= 24
                and cuda_neighbor_config_count >= 8
                and cuda_entrypoint_root_count >= 8
            ):
                non_cuda_max_score = max(
                    (
                        score
                        for ecosystem, score in detected_ecosystem_scores.items()
                        if ecosystem != "cuda"
                    ),
                    default=0,
                )
                detected_ecosystem_scores["cuda"] = max(
                    detected_ecosystem_scores["cuda"],
                    non_cuda_max_score + 32,
                )
            elif cuda_count >= 24 and cuda_count * 2 >= max(1, host_count):
                detected_ecosystem_scores["cuda"] += min(240, 80 + cuda_count // 2)

    opencl_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"opencl", "c", "cpp", "python"},
    )
    if opencl_ecosystem_counts["opencl"] > 0:
        entrypoints, roots, configs = _opencl_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("opencl")
            opencl_count = opencl_ecosystem_counts["opencl"]
            host_count = sum(
                opencl_ecosystem_counts[ecosystem] for ecosystem in ("c", "cpp", "python")
            )
            should_operationalize_opencl = (
                opencl_count >= 2
                and (
                    host_count == 0
                    or opencl_count >= host_count
                    or opencl_count * 3 >= host_count
                )
            )
            if should_operationalize_opencl:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"opencl"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"opencl"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"opencl"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                opencl_entrypoint_root_count = len(
                    {
                        normalized_root
                        for path in entrypoints
                        if (
                            normalized_root := repository_service._normalize_repository_relative_path(
                                str(PurePosixPath(path).parent)
                            )
                        )
                    }
                )
                if (
                    opencl_count >= 8
                    and opencl_entrypoint_root_count >= 6
                    and opencl_count * 2 >= max(1, host_count)
                ):
                    non_opencl_max_score = max(
                        (
                            score
                            for ecosystem, score in detected_ecosystem_scores.items()
                            if ecosystem != "opencl"
                        ),
                        default=0,
                    )
                    detected_ecosystem_scores["opencl"] = max(
                        detected_ecosystem_scores["opencl"],
                        non_opencl_max_score + 24,
                    )
                elif opencl_count >= max(2, host_count):
                    detected_ecosystem_scores["opencl"] += min(140, 32 + opencl_count * 14)
            elif opencl_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("c", "cpp", "python"),
                    key=lambda ecosystem: opencl_ecosystem_counts[ecosystem],
                )
                if opencl_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + opencl_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["opencl"] = max(
                        0,
                        detected_ecosystem_scores["opencl"] - 48,
                    )

    stan_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"stan", "r", "python", "c", "cpp", "julia", "matlab"},
    )
    if stan_ecosystem_counts["stan"] > 0:
        entrypoints, roots, configs = _stan_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"stan"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"stan"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"stan"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            stan_count = stan_ecosystem_counts["stan"]
            host_count = sum(
                stan_ecosystem_counts[ecosystem]
                for ecosystem in ("r", "python", "c", "cpp", "julia", "matlab")
            )
            if stan_count >= 8 and stan_count * 2 >= max(1, host_count):
                detected_ecosystem_scores["stan"] += min(240, 80 + stan_count // 2)

    state.bitbake_candidate_file_paths = bitbake_candidate_file_paths
    state.candidate_file_paths = candidate_file_paths
