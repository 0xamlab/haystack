from __future__ import annotations

from pathlib import PurePosixPath

from typing import Any


def apply_seed_plan_phase_c(state: Any) -> None:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _accumulate_detected_ecosystem_scores = probe_module._accumulate_detected_ecosystem_scores
    _asciidoc_profile_hints_from_candidates = probe_module._asciidoc_profile_hints_from_candidates
    _candidate_ecosystem_counts = probe_module._candidate_ecosystem_counts
    _cuda_profile_hints_from_candidates = probe_module._cuda_profile_hints_from_candidates
    _cython_profile_hints_from_candidates = probe_module._cython_profile_hints_from_candidates
    _moonbit_profile_hints_from_candidates = probe_module._moonbit_profile_hints_from_candidates
    _opencl_profile_hints_from_candidates = probe_module._opencl_profile_hints_from_candidates
    _org_profile_hints_from_candidates = probe_module._org_profile_hints_from_candidates
    _register_candidate_ecosystems = probe_module._register_candidate_ecosystems
    _rescript_profile_hints_from_candidates = probe_module._rescript_profile_hints_from_candidates
    _roc_profile_hints_from_candidates = probe_module._roc_profile_hints_from_candidates
    _rst_profile_hints_from_candidates = probe_module._rst_profile_hints_from_candidates
    _stan_profile_hints_from_candidates = probe_module._stan_profile_hints_from_candidates
    _tex_profile_hints_from_candidates = probe_module._tex_profile_hints_from_candidates
    _typst_profile_hints_from_candidates = probe_module._typst_profile_hints_from_candidates

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

    typst_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"typst", "rust", "python", "javascript", "typescript", "go", "ruby"},
    )
    if typst_ecosystem_counts["typst"] > 0:
        entrypoints, roots, configs = _typst_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("typst")
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
            typst_count = typst_ecosystem_counts["typst"]
            host_count = sum(
                typst_ecosystem_counts[ecosystem]
                for ecosystem in ("rust", "python", "javascript", "typescript", "go", "ruby")
            )
            if typst_count >= max(3, host_count):
                detected_ecosystem_scores["typst"] += min(140, 28 + typst_count * 12)
            elif typst_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("rust", "python", "javascript", "typescript", "go", "ruby"),
                    key=lambda ecosystem: typst_ecosystem_counts[ecosystem],
                )
                if typst_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        120,
                        24 + typst_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["typst"] = max(
                        0,
                        detected_ecosystem_scores["typst"] - 24,
                    )

    tex_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"tex", "c", "cpp", "go", "haskell", "javascript", "python", "ruby", "rust", "shell", "typescript"},
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
            tex_count = tex_ecosystem_counts["tex"]
            host_count = sum(
                tex_ecosystem_counts[ecosystem]
                for ecosystem in ("c", "cpp", "go", "haskell", "javascript", "python", "ruby", "rust", "shell", "typescript")
            )
            if tex_count >= max(4, host_count):
                detected_ecosystem_scores["tex"] += min(160, 36 + tex_count * 12)
            elif tex_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("c", "cpp", "go", "haskell", "javascript", "python", "ruby", "rust", "shell", "typescript"),
                    key=lambda ecosystem: tex_ecosystem_counts[ecosystem],
                )
                if tex_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + tex_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["tex"] = max(
                        0,
                        detected_ecosystem_scores["tex"] - 24,
                    )

    rst_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"rst", "python", "javascript", "typescript", "go", "ruby", "rust", "shell"},
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
            rst_count = rst_ecosystem_counts["rst"]
            host_count = sum(
                rst_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "javascript", "typescript", "go", "ruby", "rust", "shell")
            )
            if rst_count >= max(4, host_count):
                detected_ecosystem_scores["rst"] += min(160, 36 + rst_count * 12)
            elif rst_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("python", "javascript", "typescript", "go", "ruby", "rust", "shell"),
                    key=lambda ecosystem: rst_ecosystem_counts[ecosystem],
                )
                if rst_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + rst_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["rst"] = max(
                        0,
                        detected_ecosystem_scores["rst"] - 24,
                    )

    asciidoc_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"asciidoc", "python", "javascript", "typescript", "go", "ruby", "rust", "shell"},
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
            asciidoc_count = asciidoc_ecosystem_counts["asciidoc"]
            host_count = sum(
                asciidoc_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "javascript", "typescript", "go", "ruby", "rust", "shell")
            )
            if asciidoc_count >= max(4, host_count):
                detected_ecosystem_scores["asciidoc"] += min(160, 36 + asciidoc_count * 12)
            elif asciidoc_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("python", "javascript", "typescript", "go", "ruby", "rust", "shell"),
                    key=lambda ecosystem: asciidoc_ecosystem_counts[ecosystem],
                )
                if asciidoc_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + asciidoc_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["asciidoc"] = max(
                        0,
                        detected_ecosystem_scores["asciidoc"] - 24,
                    )

    org_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"org", "emacslisp", "python", "javascript", "typescript", "go", "ruby", "rust", "shell"},
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
            org_count = org_ecosystem_counts["org"]
            host_count = sum(
                org_ecosystem_counts[ecosystem]
                for ecosystem in ("emacslisp", "python", "javascript", "typescript", "go", "ruby", "rust", "shell")
            )
            if org_count >= max(4, host_count):
                detected_ecosystem_scores["org"] += min(160, 36 + org_count * 12)
            elif org_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("emacslisp", "python", "javascript", "typescript", "go", "ruby", "rust", "shell"),
                    key=lambda ecosystem: org_ecosystem_counts[ecosystem],
                )
                if org_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + org_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["org"] = max(
                        0,
                        detected_ecosystem_scores["org"] - 24,
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
                if opencl_count >= max(2, host_count):
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
