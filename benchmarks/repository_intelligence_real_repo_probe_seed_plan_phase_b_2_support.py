from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


def apply_seed_plan_phase_b_2(state: Any) -> None:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _accumulate_detected_ecosystem_scores = probe_module._accumulate_detected_ecosystem_scores
    _al_profile_hints_from_candidates = probe_module._al_profile_hints_from_candidates
    _antlr_profile_hints_from_candidates = probe_module._antlr_profile_hints_from_candidates
    _brightscript_profile_hints_from_candidates = (
        probe_module._brightscript_profile_hints_from_candidates
    )
    _candidate_ecosystem_counts = probe_module._candidate_ecosystem_counts
    _codeql_profile_hints_from_candidates = probe_module._codeql_profile_hints_from_candidates
    _circom_profile_hints_from_candidates = probe_module._circom_profile_hints_from_candidates
    _dafny_profile_hints_from_candidates = probe_module._dafny_profile_hints_from_candidates
    _gherkin_profile_hints_from_candidates = probe_module._gherkin_profile_hints_from_candidates
    _graphviz_profile_hints_from_candidates = probe_module._graphviz_profile_hints_from_candidates
    _mermaid_profile_hints_from_candidates = probe_module._mermaid_profile_hints_from_candidates
    _modelica_profile_hints_from_candidates = probe_module._modelica_profile_hints_from_candidates
    _move_profile_hints_from_candidates = probe_module._move_profile_hints_from_candidates
    _openqasm_profile_hints_from_candidates = probe_module._openqasm_profile_hints_from_candidates
    _plantuml_profile_hints_from_candidates = probe_module._plantuml_profile_hints_from_candidates
    _qsharp_profile_hints_from_candidates = probe_module._qsharp_profile_hints_from_candidates
    _register_candidate_ecosystems = probe_module._register_candidate_ecosystems

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

    gherkin_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"gherkin", "python", "javascript", "typescript", "java", "ruby", "go", "rust"},
    )
    if gherkin_ecosystem_counts["gherkin"] > 0:
        entrypoints, roots, configs = _gherkin_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("gherkin")
            gherkin_count = gherkin_ecosystem_counts["gherkin"]
            host_count = sum(
                gherkin_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "javascript", "typescript", "java", "ruby", "go", "rust")
            )
            should_operationalize_gherkin = (
                gherkin_count >= 2
                and (
                    host_count == 0
                    or gherkin_count >= host_count
                    or (gherkin_count >= 4 and gherkin_count * 2 >= host_count)
                )
            )
            if should_operationalize_gherkin:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"gherkin"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"gherkin"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"gherkin"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if gherkin_count >= max(2, host_count):
                    detected_ecosystem_scores["gherkin"] += min(140, 32 + gherkin_count * 14)

    antlr_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"antlr", "java", "python", "javascript", "typescript", "csharp", "cpp", "go", "swift", "dart", "shell"},
    )
    if antlr_ecosystem_counts["antlr"] > 0:
        entrypoints, roots, configs = _antlr_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("antlr")
            antlr_count = antlr_ecosystem_counts["antlr"]
            host_count = sum(
                antlr_ecosystem_counts[ecosystem]
                for ecosystem in ("java", "python", "javascript", "typescript", "csharp", "cpp", "go", "swift", "dart", "shell")
            )
            should_operationalize_antlr = (
                antlr_count >= 2
                and (
                    host_count == 0
                    or antlr_count >= host_count
                    or (antlr_count >= 4 and antlr_count * 2 >= host_count)
                )
            )
            if should_operationalize_antlr:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"antlr"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"antlr"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"antlr"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if antlr_count >= max(2, host_count):
                    detected_ecosystem_scores["antlr"] += min(140, 32 + antlr_count * 14)

    graphviz_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"graphviz", "rust", "python", "javascript", "typescript", "java", "shell"},
    )
    if graphviz_ecosystem_counts["graphviz"] > 0:
        entrypoints, roots, configs = _graphviz_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("graphviz")
            graphviz_count = graphviz_ecosystem_counts["graphviz"]
            host_count = max(
                graphviz_ecosystem_counts[ecosystem]
                for ecosystem in ("rust", "python", "javascript", "typescript", "java", "shell")
            )
            if graphviz_count >= max(2, host_count):
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"graphviz"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"graphviz"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"graphviz"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["graphviz"] += min(140, 32 + graphviz_count * 14)

    mermaid_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"mermaid", "typescript", "javascript", "node", "python", "shell", "rust"},
    )
    if mermaid_ecosystem_counts["mermaid"] > 0:
        entrypoints, roots, configs = _mermaid_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("mermaid")
            mermaid_count = mermaid_ecosystem_counts["mermaid"]
            host_count = max(
                mermaid_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "python", "shell", "rust")
            )
            if mermaid_count >= max(2, host_count):
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"mermaid"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"mermaid"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"mermaid"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["mermaid"] += min(140, 32 + mermaid_count * 14)

    plantuml_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"plantuml", "java", "kotlin", "typescript", "javascript", "node", "shell"},
    )
    if plantuml_ecosystem_counts["plantuml"] > 0:
        entrypoints, roots, configs = _plantuml_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("plantuml")
            plantuml_count = plantuml_ecosystem_counts["plantuml"]
            host_count = max(
                plantuml_ecosystem_counts[ecosystem]
                for ecosystem in ("java", "kotlin", "typescript", "javascript", "node", "shell")
            )
            if plantuml_count >= max(2, host_count):
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"plantuml"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"plantuml"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"plantuml"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["plantuml"] += min(140, 32 + plantuml_count * 14)

    openqasm_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"openqasm", "python", "cpp", "c", "rust", "javascript", "node"},
    )
    if openqasm_ecosystem_counts["openqasm"] > 0:
        entrypoints, roots, configs = _openqasm_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("openqasm")
            openqasm_count = openqasm_ecosystem_counts["openqasm"]
            host_count = max(
                openqasm_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "cpp", "c", "rust", "javascript", "node")
            )
            if openqasm_count >= max(2, host_count):
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"openqasm"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"openqasm"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"openqasm"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["openqasm"] += min(140, 32 + openqasm_count * 14)

    brightscript_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"brightscript", "xml", "javascript", "typescript", "python", "java", "shell"},
    )
    if brightscript_ecosystem_counts["brightscript"] > 0:
        entrypoints, roots, configs = _brightscript_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("brightscript")
            brightscript_count = brightscript_ecosystem_counts["brightscript"]
            host_count = max(
                brightscript_ecosystem_counts[ecosystem]
                for ecosystem in ("xml", "javascript", "typescript", "python", "java", "shell")
            )
            if brightscript_count >= max(2, host_count):
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"brightscript"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"brightscript"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"brightscript"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["brightscript"] += min(
                    140, 32 + brightscript_count * 14
                )

    codeql_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"codeql", "python", "javascript", "typescript", "java", "cs", "cpp", "go", "rust", "shell"},
    )
    if codeql_ecosystem_counts["codeql"] > 0:
        entrypoints, roots, configs = _codeql_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("codeql")
            codeql_count = codeql_ecosystem_counts["codeql"]
            host_count = max(
                codeql_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "javascript", "typescript", "java", "cs", "cpp", "go", "rust", "shell")
            )
            if codeql_count >= max(2, host_count):
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"codeql"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"codeql"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"codeql"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["codeql"] += min(140, 32 + codeql_count * 14)

    qsharp_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"qsharp", "cs", "dotnet", "python"},
    )
    if qsharp_ecosystem_counts["qsharp"] > 0:
        entrypoints, roots, configs = _qsharp_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("qsharp")
            qsharp_count = qsharp_ecosystem_counts["qsharp"]
            host_count = max(
                qsharp_ecosystem_counts["cs"],
                qsharp_ecosystem_counts["dotnet"],
            ) + qsharp_ecosystem_counts["python"]
            should_operationalize_qsharp = (
                qsharp_count >= 2
                and (
                    host_count == 0
                    or qsharp_count >= host_count
                    or qsharp_count * 3 >= host_count
                )
            )
            if should_operationalize_qsharp:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"qsharp"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"qsharp"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"qsharp"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if qsharp_count >= max(2, host_count):
                    detected_ecosystem_scores["qsharp"] += min(140, 32 + qsharp_count * 14)
            elif qsharp_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("cs", "dotnet", "python"),
                    key=lambda ecosystem: qsharp_ecosystem_counts[ecosystem],
                )
                if qsharp_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + qsharp_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["qsharp"] = max(
                        0,
                        detected_ecosystem_scores["qsharp"] - 48,
                    )

    circom_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"circom", "javascript", "node", "python", "rust", "solidity", "typescript"},
    )
    if circom_ecosystem_counts["circom"] > 0:
        entrypoints, roots, configs = _circom_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("circom")
            circom_count = circom_ecosystem_counts["circom"]
            host_count = sum(
                circom_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "node", "python", "rust", "solidity", "typescript")
            )
            should_operationalize_circom = (
                circom_count >= 2
                and (
                    host_count == 0
                    or circom_count >= host_count
                    or circom_count * 3 >= host_count
                )
            )
            if should_operationalize_circom:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"circom"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"circom"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"circom"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if circom_count >= max(2, host_count):
                    detected_ecosystem_scores["circom"] += min(140, 32 + circom_count * 14)

    dafny_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"dafny", "cs", "dotnet", "python"},
    )
    if dafny_ecosystem_counts["dafny"] > 0:
        entrypoints, roots, configs = _dafny_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("dafny")
            dafny_count = dafny_ecosystem_counts["dafny"]
            host_count = max(
                dafny_ecosystem_counts["cs"],
                dafny_ecosystem_counts["dotnet"],
            ) + dafny_ecosystem_counts["python"]
            should_operationalize_dafny = (
                dafny_count >= 2
                and (
                    host_count == 0
                    or dafny_count >= host_count
                    or dafny_count * 3 >= host_count
                )
            )
            if should_operationalize_dafny:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"dafny"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"dafny"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"dafny"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if dafny_count >= max(2, host_count):
                    detected_ecosystem_scores["dafny"] += min(140, 32 + dafny_count * 14)

    clojurescript_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"clojurescript", "clojure", "javascript", "node"},
    )
    if clojurescript_ecosystem_counts["clojurescript"] > 0:
        clojurescript_config_paths = set(discovered_config_paths) | set(config_path_candidates)
        has_shadow_cljs = any(
            PurePosixPath(path).name.lower() == "shadow-cljs.edn"
            for path in clojurescript_config_paths
        )
        if has_shadow_cljs:
            detected_ecosystems.add("clojurescript")
            clojurescript_count = clojurescript_ecosystem_counts["clojurescript"]
            host_count = sum(
                clojurescript_ecosystem_counts[ecosystem]
                for ecosystem in ("clojure", "javascript", "node")
            )
            should_operationalize_clojurescript = (
                clojurescript_count >= 2
                and clojurescript_count >= clojurescript_ecosystem_counts["clojure"]
                and (
                    host_count == 0
                    or clojurescript_count >= host_count
                    or clojurescript_count * 2 >= host_count
                )
            )
            if should_operationalize_clojurescript:
                detected_ecosystem_scores["clojurescript"] += min(
                    160,
                    48 + clojurescript_count * 12,
                )
                non_clojurescript_max_score = max(
                    (
                        score
                        for ecosystem, score in detected_ecosystem_scores.items()
                        if ecosystem != "clojurescript"
                    ),
                    default=0,
                )
                detected_ecosystem_scores["clojurescript"] = max(
                    detected_ecosystem_scores["clojurescript"],
                    non_clojurescript_max_score + 16,
                )
            elif clojurescript_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("clojure", "javascript", "node"),
                    key=lambda ecosystem: clojurescript_ecosystem_counts[ecosystem],
                )
                if clojurescript_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + clojurescript_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["clojurescript"] = max(
                        0,
                        detected_ecosystem_scores["clojurescript"] - 48,
                    )

    dm_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"dm", "cs", "dotnet", "javascript", "typescript", "node", "python", "dockerfile"},
    )
    if dm_ecosystem_counts["dm"] > 0:
        detected_ecosystems.add("dm")
        dm_count = dm_ecosystem_counts["dm"]
        host_count = sum(
            dm_ecosystem_counts[ecosystem]
            for ecosystem in ("cs", "dotnet", "javascript", "typescript", "node", "python", "dockerfile")
        )
        should_operationalize_dm = (
            dm_count >= 2
            and (
                host_count == 0
                or dm_count >= host_count
                or dm_count * 2 >= host_count
            )
        )
        if should_operationalize_dm:
            detected_ecosystem_scores["dm"] += min(180, 40 + dm_count * 12)
            non_dm_max_score = max(
                (
                    score
                    for ecosystem, score in detected_ecosystem_scores.items()
                    if ecosystem != "dm"
                ),
                default=0,
            )
            detected_ecosystem_scores["dm"] = max(
                detected_ecosystem_scores["dm"],
                non_dm_max_score + 16,
            )
        elif dm_count * 2 <= max(1, host_count):
            dominant_host = max(
                ("cs", "dotnet", "javascript", "typescript", "node", "python", "dockerfile"),
                key=lambda ecosystem: dm_ecosystem_counts[ecosystem],
            )
            if dm_ecosystem_counts[dominant_host] > 0:
                detected_ecosystem_scores[dominant_host] += min(
                    140,
                    24 + dm_ecosystem_counts[dominant_host] * 6,
                )
                detected_ecosystem_scores["dm"] = max(
                    0,
                    detected_ecosystem_scores["dm"] - 48,
                )

    al_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"al", "powershell"},
    )
    if al_ecosystem_counts["al"] > 0:
        entrypoints, roots, configs = _al_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("al")
            al_count = al_ecosystem_counts["al"]
            host_count = al_ecosystem_counts["powershell"]
            should_operationalize_al = (
                al_count >= 2
                and (
                    host_count == 0
                    or al_count >= host_count
                    or al_count * 3 >= host_count
                )
            )
            if should_operationalize_al:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"al"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"al"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"al"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if al_count >= max(2, host_count):
                    detected_ecosystem_scores["al"] += min(140, 32 + al_count * 14)
            elif al_count * 2 <= max(1, host_count):
                if al_ecosystem_counts["powershell"] > 0:
                    detected_ecosystem_scores["powershell"] += min(
                        140,
                        24 + al_ecosystem_counts["powershell"] * 6,
                    )
                    detected_ecosystem_scores["al"] = max(
                        0,
                        detected_ecosystem_scores["al"] - 48,
                    )

    sml_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={
            "sml",
            "python",
            "javascript",
            "typescript",
            "java",
            "go",
            "rust",
            "cpp",
            "c",
            "shell",
        },
    )
    if sml_ecosystem_counts["sml"] > 0:
        sml_count = sml_ecosystem_counts["sml"]
        host_count = sum(
            sml_ecosystem_counts[ecosystem]
            for ecosystem in ("python", "javascript", "typescript", "java", "go", "rust", "cpp", "c", "shell")
        )
        if sml_count >= max(2, host_count):
            detected_ecosystem_scores["sml"] += min(140, 32 + sml_count * 14)
        elif sml_count * 2 <= max(1, host_count):
            dominant_host = max(
                ("python", "javascript", "typescript", "java", "go", "rust", "cpp", "c", "shell"),
                key=lambda ecosystem: sml_ecosystem_counts[ecosystem],
            )
            if sml_ecosystem_counts[dominant_host] > 0:
                detected_ecosystem_scores[dominant_host] += min(
                    140,
                    24 + sml_ecosystem_counts[dominant_host] * 6,
                )
                detected_ecosystem_scores["sml"] = max(
                    0,
                    detected_ecosystem_scores["sml"] - 48,
                )

    move_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"move", "rust", "typescript", "javascript", "python", "shell"},
    )
    if move_ecosystem_counts["move"] > 0:
        entrypoints, roots, configs = _move_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("move")
            move_count = move_ecosystem_counts["move"]
            host_count = sum(
                move_ecosystem_counts[ecosystem]
                for ecosystem in ("rust", "typescript", "javascript", "python", "shell")
            )
            should_operationalize_move = (
                move_count >= 2
                and (
                    host_count == 0
                    or move_count >= host_count
                    or move_count * 3 >= host_count
                )
            )
            if should_operationalize_move:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"move"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"move"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"move"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if move_count >= max(2, host_count):
                    detected_ecosystem_scores["move"] += min(140, 32 + move_count * 14)

    modelica_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"modelica", "c", "cpp", "python", "shell", "makefile", "cmake"},
    )
    if modelica_ecosystem_counts["modelica"] > 0:
        entrypoints, roots, configs = _modelica_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("modelica")
            modelica_count = len(entrypoints)
            host_count = sum(
                modelica_ecosystem_counts[ecosystem]
                for ecosystem in ("c", "cpp", "python", "shell", "makefile", "cmake")
            )
            should_operationalize_modelica = modelica_count >= max(6, host_count * 2)
            if should_operationalize_modelica:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"modelica"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"modelica"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"modelica"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["modelica"] += min(140, 28 + modelica_count * 14)
            elif modelica_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("c", "cpp", "python", "shell", "makefile", "cmake"),
                    key=lambda ecosystem: modelica_ecosystem_counts[ecosystem],
                )
                if modelica_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + modelica_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["modelica"] = max(
                        0,
                        detected_ecosystem_scores["modelica"] - 48,
                    )

    state.bitbake_candidate_file_paths = bitbake_candidate_file_paths
    state.candidate_file_paths = candidate_file_paths
