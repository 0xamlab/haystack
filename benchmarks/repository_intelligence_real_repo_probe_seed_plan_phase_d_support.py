from __future__ import annotations

from pathlib import PurePosixPath

from typing import Any


def apply_seed_plan_phase_d(state: Any) -> None:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _accumulate_detected_ecosystem_scores = probe_module._accumulate_detected_ecosystem_scores
    _balanced_profile_paths = probe_module._balanced_profile_paths
    _bicep_profile_hints_from_candidates = probe_module._bicep_profile_hints_from_candidates
    _candidate_ecosystem_counts = probe_module._candidate_ecosystem_counts
    _candidate_existing_leaf_roots = probe_module._candidate_existing_leaf_roots
    _candidate_existing_paths = probe_module._candidate_existing_paths
    _candidate_repository_file_paths = probe_module._candidate_repository_file_paths
    _chapel_profile_hints_from_candidates = probe_module._chapel_profile_hints_from_candidates
    _cue_profile_hints_from_candidates = probe_module._cue_profile_hints_from_candidates
    _eiffel_profile_hints_from_candidates = probe_module._eiffel_profile_hints_from_candidates
    _factor_profile_hints_from_candidates = probe_module._factor_profile_hints_from_candidates
    _glsl_profile_hints_from_candidates = probe_module._glsl_profile_hints_from_candidates
    _hcl_profile_hints_from_candidates = probe_module._hcl_profile_hints_from_candidates
    _hlsl_profile_hints_from_candidates = probe_module._hlsl_profile_hints_from_candidates
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _is_repo_profile_code_candidate = probe_module._is_repo_profile_code_candidate
    _logtalk_profile_hints_from_candidates = probe_module._logtalk_profile_hints_from_candidates
    _odin_profile_hints_from_candidates = probe_module._odin_profile_hints_from_candidates
    _profile_entrypoint_target_count = probe_module._profile_entrypoint_target_count
    _protobuf_profile_hints_from_candidates = probe_module._protobuf_profile_hints_from_candidates
    _qml_profile_hints_from_candidates = probe_module._qml_profile_hints_from_candidates
    _register_candidate_ecosystems = probe_module._register_candidate_ecosystems
    _rego_profile_hints_from_candidates = probe_module._rego_profile_hints_from_candidates
    _scala_support_roots_from_candidates = probe_module._scala_support_roots_from_candidates
    _shaderlab_profile_hints_from_candidates = probe_module._shaderlab_profile_hints_from_candidates
    _support_roots_requiring_expansion = probe_module._support_roots_requiring_expansion
    _tlaplus_profile_hints_from_candidates = probe_module._tlaplus_profile_hints_from_candidates
    _wgsl_profile_hints_from_candidates = probe_module._wgsl_profile_hints_from_candidates
    _yara_profile_hints_from_candidates = probe_module._yara_profile_hints_from_candidates
    default_include_patterns = probe_module.DEFAULT_INCLUDE_PATTERNS

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

    protobuf_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"protobuf", "cpp", "c", "go", "java", "python", "ruby", "rust", "typescript", "starlark", "dockerfile"},
    )
    if protobuf_ecosystem_counts["protobuf"] > 0:
        entrypoints, roots, configs = _protobuf_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("protobuf")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"protobuf"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"protobuf"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"protobuf"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            protobuf_count = protobuf_ecosystem_counts["protobuf"]
            host_count = sum(
                protobuf_ecosystem_counts[ecosystem]
                for ecosystem in ("cpp", "c", "go", "java", "python", "ruby", "rust", "typescript", "starlark", "dockerfile")
            )
            if protobuf_count >= max(8, host_count * 2):
                non_protobuf_max_score = max(
                    (
                        score
                        for ecosystem, score in detected_ecosystem_scores.items()
                        if ecosystem != "protobuf"
                    ),
                    default=0,
                )
                detected_ecosystem_scores["protobuf"] = max(
                    detected_ecosystem_scores["protobuf"],
                    non_protobuf_max_score + 32,
                )
            if protobuf_count >= max(8, host_count):
                detected_ecosystem_scores["protobuf"] += min(220, 60 + protobuf_count * 6)
            elif protobuf_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("cpp", "c", "go", "java", "python", "ruby", "rust", "typescript"),
                    key=lambda ecosystem: protobuf_ecosystem_counts[ecosystem],
                )
                if protobuf_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] = max(
                        detected_ecosystem_scores.get(dominant_host, 0),
                        28 + protobuf_ecosystem_counts[dominant_host] * 8,
                    )
                detected_ecosystem_scores["protobuf"] = max(
                    0,
                    detected_ecosystem_scores["protobuf"] - 24,
                )

    qml_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"qml", "qmake", "cmake", "c", "cpp", "objectivec", "java", "groovy"},
    )
    if qml_ecosystem_counts["qml"] > 0:
        entrypoints, roots, configs = _qml_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"qml"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"qml"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"qml"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            qml_count = qml_ecosystem_counts["qml"]
            host_count = sum(
                qml_ecosystem_counts[ecosystem]
                for ecosystem in ("qmake", "cmake", "c", "cpp", "objectivec", "java", "groovy")
            )
            if qml_count >= max(2, host_count):
                detected_ecosystem_scores["qml"] += min(120, 30 + qml_count * 14)

    shaderlab_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"shaderlab", "hlsl", "glsl", "cs", "javascript"},
    )
    if shaderlab_ecosystem_counts["shaderlab"] > 0:
        entrypoints, roots, configs = _shaderlab_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"shaderlab"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"shaderlab"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"shaderlab"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            shaderlab_count = shaderlab_ecosystem_counts["shaderlab"]
            host_count = sum(
                shaderlab_ecosystem_counts[ecosystem]
                for ecosystem in ("hlsl", "glsl", "cs", "javascript")
            )
            if shaderlab_count >= max(2, host_count):
                detected_ecosystem_scores["shaderlab"] += min(120, 30 + shaderlab_count * 14)

    wgsl_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"wgsl", "typescript", "javascript", "node", "rust", "cpp", "hlsl", "glsl"},
    )
    if wgsl_ecosystem_counts["wgsl"] > 0:
        entrypoints, roots, configs = _wgsl_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"wgsl"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"wgsl"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"wgsl"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            wgsl_count = wgsl_ecosystem_counts["wgsl"]
            host_count = sum(
                wgsl_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "rust", "cpp", "hlsl", "glsl")
            )
            if wgsl_count >= max(2, host_count):
                detected_ecosystem_scores["wgsl"] += min(120, 30 + wgsl_count * 14)

    if "glsl" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _glsl_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"glsl"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"glsl"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"glsl"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "hlsl" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _hlsl_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"hlsl"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"hlsl"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"hlsl"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "hcl" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _hcl_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"hcl"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"hcl"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"hcl"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "bicep" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _bicep_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"bicep"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"bicep"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"bicep"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "tlaplus" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _tlaplus_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"tlaplus"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"tlaplus"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"tlaplus"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "logtalk" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _logtalk_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"logtalk"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"logtalk"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"logtalk"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "chapel" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _chapel_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"chapel"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"chapel"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"chapel"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "odin" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _odin_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"odin"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"odin"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"odin"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "factor" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _factor_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"factor"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"factor"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"factor"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )
    if "cue" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _cue_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"cue"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"cue"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"cue"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "eiffel" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _eiffel_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"eiffel"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"eiffel"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"eiffel"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "rego" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _rego_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"rego"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"rego"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"rego"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "yara" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _yara_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"yara"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"yara"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"yara"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if support_root_candidates:
        existing_entrypoint_paths = set(
            _candidate_existing_paths(
                repo_path,
                paths=entrypoint_candidates,
            )
        )
        support_scan_roots = _support_roots_requiring_expansion(
            candidate_file_paths=candidate_file_paths,
            support_roots=_candidate_existing_leaf_roots(
                repo_path,
                roots=support_root_candidates,
                entrypoint_paths=existing_entrypoint_paths,
            ),
        )
        if support_scan_roots:
            support_scan_seed_paths = [
                path
                for path in _candidate_existing_paths(
                    repo_path,
                    paths=entrypoint_candidates,
                )
                if _is_repo_profile_code_candidate(path, repo_path=repo_path)
                and not repository_service._is_test_path(path)
                and not _is_non_operational_profile_path(path)
            ]
            support_scan_seed_paths = _balanced_profile_paths(
                paths=support_scan_seed_paths,
                detected_ecosystems=detected_ecosystems,
                repo_path=repo_path,
                support_roots=support_root_candidates,
                limit=_profile_entrypoint_target_count(detected_ecosystems),
                ecosystem_scores=detected_ecosystem_scores,
            )
            support_candidate_paths = _candidate_repository_file_paths(
                repo_path=repo_path,
                seed_paths=support_scan_seed_paths,
                bridge_paths=support_scan_roots,
                include_patterns=default_include_patterns,
                max_files=min(max_files, 512),
            )
            if "bitbake" in detected_ecosystems:
                support_candidate_paths = [
                    path
                    for path in support_candidate_paths
                    if repository_service.bitbake_adapter.has_bitbake_path_hints(
                        PurePosixPath(path)
                    )
                ]
            candidate_file_paths = list(
                dict.fromkeys(candidate_file_paths + support_candidate_paths)
            )

    if "scala" in detected_ecosystems:
        support_root_candidates.update(_scala_support_roots_from_candidates(candidate_file_paths))

    state.bitbake_candidate_file_paths = bitbake_candidate_file_paths
    state.candidate_file_paths = candidate_file_paths
