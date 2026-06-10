from __future__ import annotations

from pathlib import Path, PurePosixPath


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _diagram_probe_deps():
    probe_module = _probe_module()
    return (
        probe_module.repository_service,
        probe_module._is_non_operational_profile_path,
        probe_module._probe_language_for_path,
    )


def _graphviz_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _diagram_probe_deps()
    )

    graphviz_files: list[str] = []
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {
        "architecture.dot",
        "graph.dot",
        "index.dot",
        "main.dot",
        "overview.dot",
        "system.dot",
    }
    support_dirs = {"diagram", "diagrams", "dot", "dots", "graph", "graphs", "graphviz", "viz"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "graphviz"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.graphviz_adapter.is_probable_graphviz_source(
            path=candidate_file,
            text=text,
        ):
            continue
        graphviz_files.append(normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in graphviz_files:
        path = PurePosixPath(normalized_candidate)
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or path.parent.name.lower() in support_dirs:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(graphviz_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _mermaid_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _diagram_probe_deps()
    )

    mermaid_files: list[str] = []
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {
        "architecture.mmd",
        "diagram.mmd",
        "flowchart.mmd",
        "index.mmd",
        "main.mmd",
        "overview.mmd",
        "system.mmd",
    }
    support_dirs = {
        "architecture",
        "diagram",
        "diagrams",
        "docs",
        "flowcharts",
        "mermaid",
        "mmd",
        "viz",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "mermaid"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.mermaid_adapter.is_probable_mermaid_source(
            path=candidate_file,
            text=text,
        ):
            continue
        mermaid_files.append(normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in mermaid_files:
        path = PurePosixPath(normalized_candidate)
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or path.parent.name.lower() in support_dirs:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(mermaid_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _plantuml_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _diagram_probe_deps()
    )

    plantuml_files: list[str] = []
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {
        "architecture.puml",
        "c4.puml",
        "container.puml",
        "context.puml",
        "diagram.puml",
        "main.puml",
        "overview.puml",
        "system.puml",
    }
    support_dirs = {"architecture", "c4", "diagram", "diagrams", "docs", "plantuml", "puml", "uml", "viz"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "plantuml"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.plantuml_adapter.is_probable_plantuml_source(
            path=candidate_file,
            text=text,
        ):
            continue
        plantuml_files.append(normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in plantuml_files:
        path = PurePosixPath(normalized_candidate)
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or path.parent.name.lower() in support_dirs:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(plantuml_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _openqasm_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _diagram_probe_deps()
    )

    openqasm_files: list[str] = []
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {"adder.qasm", "circuit.qasm", "example.qasm", "main.qasm", "program.qasm", "qft.qasm", "teleport.qasm"}
    support_dirs = {"circuits", "examples", "openqasm", "qasm", "spec", "tests"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "openqasm"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.openqasm_adapter.is_probable_openqasm_source(
            path=candidate_file,
            text=text,
        ):
            continue
        openqasm_files.append(normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in openqasm_files:
        path = PurePosixPath(normalized_candidate)
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or path.parent.name.lower() in support_dirs:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(openqasm_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()
