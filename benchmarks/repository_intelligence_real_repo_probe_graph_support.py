from __future__ import annotations

from collections.abc import Callable
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.api_server.schemas.repositories import RepositoryDiagnostic


@dataclass(frozen=True)
class ProbeGraphSupportDependencies:
    candidate_repository_file_paths: Callable[..., list[str]]
    connected_map_candidate_file_limit: Callable[..., int]
    looks_like_concrete_file_seed: Callable[[str], bool]
    normalized_candidate_file_paths: Callable[..., list[str]]
    seed_dependency_files: Callable[..., list[str]]
    repository_service: Any


def build_connected_dependency_map(
    *,
    repo_path: Path,
    seed_paths: list[str],
    bridge_paths: list[str],
    candidate_file_paths: list[str] | None = None,
    candidate_scope_paths: list[str] | None = None,
    enable_reverse_bridging: bool = True,
    include_patterns: list[str],
    max_files: int,
    max_file_size_bytes: int,
    max_dependency_depth: int,
    max_connected_files: int,
    deps: ProbeGraphSupportDependencies,
) -> dict[str, Any]:
    _candidate_repository_file_paths = deps.candidate_repository_file_paths
    _connected_map_candidate_file_limit = deps.connected_map_candidate_file_limit
    _looks_like_concrete_file_seed = deps.looks_like_concrete_file_seed
    _normalized_candidate_file_paths = deps.normalized_candidate_file_paths
    _seed_dependency_files = deps.seed_dependency_files
    repository_service = deps.repository_service

    concrete_seed_count = len(
        {
            repository_service._normalize_repository_relative_path(seed_path)
            for seed_path in seed_paths
            if _looks_like_concrete_file_seed(seed_path)
        }
    )
    seed_includes_tests = any(
        repository_service._is_test_path(
            repository_service._normalize_repository_relative_path(seed_path)
        )
        for seed_path in seed_paths
    )
    candidate_file_limit = _connected_map_candidate_file_limit(
        max_files=max_files,
        max_connected_files=max_connected_files,
        concrete_seed_count=concrete_seed_count,
    )
    if candidate_file_paths is not None:
        candidate_file_paths = _normalized_candidate_file_paths(
            repo_path=repo_path,
            candidate_file_paths=candidate_file_paths,
            include_patterns=include_patterns,
            max_files=candidate_file_limit,
        )
    else:
        candidate_file_paths = _candidate_repository_file_paths(
            repo_path=repo_path,
            seed_paths=seed_paths,
            bridge_paths=list(candidate_scope_paths or bridge_paths),
            include_patterns=include_patterns,
            max_files=candidate_file_limit,
        )
    module_index = repository_service._build_module_index(
        candidate_file_paths,
        root_path=repo_path,
    )
    workspace_package_index = repository_service._build_workspace_package_index(repo_path)
    workspace_go_module_index = repository_service._build_workspace_go_module_index(repo_path)
    analysis_context_hash = repository_service._file_analysis_context_hash(
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        engine_revision=repository_service._REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
    )
    git_content_hashes = (
        repository_service._git_tracked_content_hashes(
            repo_path,
            candidate_paths=candidate_file_paths,
        )
        if repository_service._is_git_repository(repo_path)
        else None
    )
    seed_files = _seed_dependency_files(
        candidate_file_paths=candidate_file_paths,
        seed_paths=seed_paths,
        max_connected_files=max_connected_files,
    )
    if not seed_files:
        return {
            "seed_files": [],
            "connected_files": [],
            "candidate_file_limit": candidate_file_limit,
            "candidate_file_count": len(candidate_file_paths),
            "connected_file_count": 0,
            "concrete_seed_count": concrete_seed_count,
            "resolved_dependency_edges": 0,
            "unresolved_dependency_count": 0,
            "max_dependency_depth": max_dependency_depth,
            "top_hubs": [],
        }

    queue: deque[tuple[str, int]] = deque((file_path, 0) for file_path in seed_files)
    visited: set[str] = set()
    dependency_cache: dict[str, tuple[repository_service._Dependency, ...]] = {}
    edges: list[tuple[str, str]] = []
    unresolved_dependencies: Counter[str] = Counter()
    inbound_counts: Counter[str] = Counter()
    outbound_counts: Counter[str] = Counter()

    def _load_dependencies(file_path: str) -> tuple[repository_service._Dependency, ...]:
        candidate = repo_path / file_path
        if not candidate.is_file():
            return ()
        dependencies = dependency_cache.get(file_path)
        if dependencies is None:
            dependencies = repository_service._analyze_file_dependencies_cached(
                root_path=repo_path,
                path=candidate,
                module_index=module_index,
                workspace_package_index=workspace_package_index,
                workspace_go_module_index=workspace_go_module_index,
                max_file_size_bytes=max_file_size_bytes,
                analysis_context_hash=analysis_context_hash,
                git_content_hashes=git_content_hashes,
            )
            dependency_cache[file_path] = dependencies
        return dependencies

    while queue and len(visited) < max_connected_files:
        file_path, depth = queue.popleft()
        if file_path in visited:
            continue
        visited.add(file_path)
        dependencies = _load_dependencies(file_path)
        for dependency in dependencies:
            target_file = dependency.target_file
            if target_file and (repo_path / target_file).is_file():
                edges.append((dependency.source_file, target_file))
                outbound_counts[dependency.source_file] += 1
                inbound_counts[target_file] += 1
                if (
                    target_file not in visited
                    and depth < max_dependency_depth
                    and len(visited) + len(queue) < max_connected_files
                ):
                    queue.append((target_file, depth + 1))
                continue
            unresolved_dependencies[dependency.target_symbol or "<unknown>"] += 1

    bridged_importers: list[str] = []
    if enable_reverse_bridging and bridge_paths:
        bridge_files = _seed_dependency_files(
            candidate_file_paths=candidate_file_paths,
            seed_paths=bridge_paths,
            max_connected_files=max_files,
        )
        bridge_files = [
            file_path
            for file_path in bridge_files
            if seed_includes_tests or not repository_service._is_test_path(file_path)
        ]
        connected_targets = set(visited)
        for bridge_file in bridge_files:
            if len(visited) >= max_connected_files:
                break
            if bridge_file in visited:
                continue
            dependencies = _load_dependencies(bridge_file)
            if not any(
                dependency.target_file and dependency.target_file in connected_targets
                for dependency in dependencies
            ):
                continue
            bridged_importers.append(bridge_file)
            queue.append((bridge_file, 1))

    while queue and len(visited) < max_connected_files:
        file_path, depth = queue.popleft()
        if file_path in visited:
            continue
        visited.add(file_path)
        dependencies = _load_dependencies(file_path)
        for dependency in dependencies:
            target_file = dependency.target_file
            if target_file and (repo_path / target_file).is_file():
                edges.append((dependency.source_file, target_file))
                outbound_counts[dependency.source_file] += 1
                inbound_counts[target_file] += 1
                if (
                    target_file not in visited
                    and depth < max_dependency_depth
                    and len(visited) + len(queue) < max_connected_files
                ):
                    queue.append((target_file, depth + 1))
                continue
            unresolved_dependencies[dependency.target_symbol or "<unknown>"] += 1

    top_hubs = []
    for file_path in sorted(visited):
        total_degree = inbound_counts[file_path] + outbound_counts[file_path]
        if total_degree == 0:
            continue
        top_hubs.append(
            {
                "file_path": file_path,
                "incoming_dependency_count": inbound_counts[file_path],
                "outgoing_dependency_count": outbound_counts[file_path],
                "total_dependency_degree": total_degree,
            }
        )
    top_hubs.sort(
        key=lambda entry: (
            -int(entry["incoming_dependency_count"]),
            -int(entry["outgoing_dependency_count"]),
            str(entry["file_path"]),
        )
    )

    return {
        "seed_files": seed_files,
        "candidate_file_limit": candidate_file_limit,
        "connected_files": sorted(visited),
        "candidate_file_count": len(candidate_file_paths),
        "connected_file_count": len(visited),
        "concrete_seed_count": concrete_seed_count,
        "bridged_importer_count": len(bridged_importers),
        "bridged_importers": sorted(bridged_importers)[:32],
        "resolved_dependency_edges": len(edges),
        "unresolved_dependency_count": sum(unresolved_dependencies.values()),
        "unresolved_dependency_samples": [
            {"target": target, "count": count}
            for target, count in unresolved_dependencies.most_common(12)
        ],
        "max_dependency_depth": max_dependency_depth,
        "top_hubs": top_hubs[:12],
    }


def load_snapshot_graph_summary(
    *,
    repository_graph_path: str,
    dependency_graph_path: str,
    symbol_graph_path: str,
    seed_files: list[str],
) -> dict[str, Any]:
    from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    symbol_kind_weights = {
        "async_function": 12,
        "async_function_expression": 12,
        "async_method": 12,
        "arrow_function": 11,
        "class_field_arrow": 11,
        "function": 10,
        "function_expression": 10,
        "method": 10,
        "get_method": 9,
        "set_method": 9,
        "constructor": 9,
        "class": 8,
        "class_expression": 8,
        "const": 4,
        "symbol": 3,
        "type": 1,
        "interface": 1,
    }
    operational_symbol_kinds = {
        "async_function",
        "async_function_expression",
        "async_method",
        "arrow_function",
        "class",
        "class_expression",
        "class_field_arrow",
        "constructor",
        "function",
        "function_expression",
        "get_method",
        "method",
        "set_method",
    }

    repository_graph_rows = pq.read_table(repository_graph_path).to_pylist()
    dependency_rows = pq.read_table(dependency_graph_path).to_pylist()
    symbol_rows = pq.read_table(symbol_graph_path).to_pylist()

    inbound_counts: Counter[str] = Counter()
    outbound_counts: Counter[str] = Counter()
    unresolved_dependency_targets: Counter[str] = Counter()
    cross_boundary_edges = 0
    for row in dependency_rows:
        source_file = str(row.get("source_file") or "")
        target_file = row.get("target_file")
        if target_file:
            target_file = str(target_file)
            outbound_counts[source_file] += 1
            inbound_counts[target_file] += 1
            source_scope = Path(source_file).parts[:1]
            target_scope = Path(target_file).parts[:1]
            if source_scope and target_scope and source_scope != target_scope:
                cross_boundary_edges += 1
            continue
        unresolved_dependency_targets[str(row.get("target_symbol") or "<unknown>")] += 1

    symbol_counts: Counter[str] = Counter()
    nested_symbol_counts: Counter[str] = Counter()
    top_level_symbols: dict[str, list[str]] = {}
    symbol_names_by_id: dict[str, str] = {}
    symbol_rows_by_id: dict[str, dict[str, Any]] = {}
    nested_symbol_examples: dict[str, list[dict[str, str]]] = {}
    for row in symbol_rows:
        symbol_id = str(row.get("symbol_id") or "")
        if symbol_id:
            symbol_names_by_id[symbol_id] = str(row.get("symbol_name") or "")
            symbol_rows_by_id[symbol_id] = row
    for row in symbol_rows:
        file_path = str(row.get("file_path") or "")
        symbol_counts[file_path] += 1
        if row.get("parent_symbol_id"):
            nested_symbol_counts[file_path] += 1
            nested_symbol_examples.setdefault(file_path, [])
            if len(nested_symbol_examples[file_path]) < 8:
                parent_symbol_id = str(row.get("parent_symbol_id") or "")
                nested_symbol_examples[file_path].append(
                    {
                        "parent_symbol": symbol_names_by_id.get(parent_symbol_id, parent_symbol_id),
                        "child_symbol": str(row.get("symbol_name") or ""),
                        "child_kind": str(row.get("symbol_kind") or ""),
                    }
                )
            continue
        top_level_symbols.setdefault(file_path, [])
        if len(top_level_symbols[file_path]) < 8:
            top_level_symbols[file_path].append(str(row.get("symbol_name") or ""))

    risk_rows = []
    for file_path in sorted(set(symbol_counts) | set(inbound_counts) | set(outbound_counts)):
        risk_rows.append(
            {
                "file_path": file_path,
                "incoming_dependency_count": inbound_counts[file_path],
                "outgoing_dependency_count": outbound_counts[file_path],
                "symbol_count": symbol_counts[file_path],
                "nested_symbol_count": nested_symbol_counts[file_path],
                "top_level_symbols": top_level_symbols.get(file_path, []),
                "nested_symbol_examples": nested_symbol_examples.get(file_path, []),
                "seed_related": file_path in seed_files,
            }
        )
    risk_rows.sort(
        key=lambda row: (
            -int(row["incoming_dependency_count"]),
            -int(row["outgoing_dependency_count"]),
            -int(row["symbol_count"]),
            str(row["file_path"]),
        )
    )

    symbol_child_counts: Counter[str] = Counter()
    symbol_reference_inbound_counts: Counter[str] = Counter()
    symbol_reference_outbound_counts: Counter[str] = Counter()
    raw_symbol_reference_edges: list[tuple[str, str]] = []
    for row in repository_graph_rows:
        edge_type = str(row.get("edge_type") or "")
        source_node = str(row.get("source_node") or "")
        target_node = str(row.get("target_node") or "")
        if edge_type == "contains_symbol":
            if not source_node.startswith("symbol:"):
                continue
            parent_symbol_id = source_node.removeprefix("symbol:")
            if parent_symbol_id:
                symbol_child_counts[parent_symbol_id] += 1
            continue
        if (
            edge_type == "references_symbol"
            and source_node.startswith("symbol:")
            and target_node.startswith("symbol:")
        ):
            source_symbol_id = source_node.removeprefix("symbol:")
            target_symbol_id = target_node.removeprefix("symbol:")
            if not source_symbol_id or not target_symbol_id:
                continue
            symbol_reference_outbound_counts[source_symbol_id] += 1
            symbol_reference_inbound_counts[target_symbol_id] += 1
            raw_symbol_reference_edges.append((source_symbol_id, target_symbol_id))

    symbol_risk_rows = []
    symbol_risk_rows_by_id: dict[str, dict[str, Any]] = {}
    for symbol_id, row in symbol_rows_by_id.items():
        file_path = str(row.get("file_path") or "")
        symbol_name = str(row.get("symbol_name") or "")
        symbol_kind = str(row.get("symbol_kind") or "")
        parent_symbol_id = str(row.get("parent_symbol_id") or "")
        depth = 0
        current_parent = parent_symbol_id
        while current_parent:
            depth += 1
            parent_row = symbol_rows_by_id.get(current_parent)
            if parent_row is None:
                break
            current_parent = str(parent_row.get("parent_symbol_id") or "")
        kind_weight = symbol_kind_weights.get(symbol_kind, 2)
        risk_score = (
            symbol_reference_inbound_counts[symbol_id] * 20
            + symbol_reference_outbound_counts[symbol_id] * 8
            + inbound_counts[file_path] * 5
            + outbound_counts[file_path] * 2
            + symbol_child_counts[symbol_id] * 4
            + depth * 2
            + kind_weight * 3
        )
        symbol_risk_rows.append(
            {
                "symbol_id": symbol_id,
                "file_path": file_path,
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "parent_symbol": symbol_names_by_id.get(parent_symbol_id, parent_symbol_id)
                if parent_symbol_id
                else None,
                "child_symbol_count": symbol_child_counts[symbol_id],
                "depth": depth,
                "incoming_symbol_reference_count": symbol_reference_inbound_counts[symbol_id],
                "outgoing_symbol_reference_count": symbol_reference_outbound_counts[symbol_id],
                "incoming_dependency_count": inbound_counts[file_path],
                "outgoing_dependency_count": outbound_counts[file_path],
                "kind_weight": kind_weight,
                "risk_score": risk_score,
            }
        )
        symbol_risk_rows_by_id[symbol_id] = symbol_risk_rows[-1]
    symbol_risk_rows.sort(
        key=lambda row: (
            -int(row["risk_score"]),
            -int(row["child_symbol_count"]),
            -int(row["kind_weight"]),
            -int(row["incoming_dependency_count"]),
            str(row["file_path"]),
            str(row["symbol_name"]),
        )
    )

    def _limit_symbol_rows(
        rows: list[dict[str, Any]],
        *,
        limit: int,
        max_per_file: int,
    ) -> list[dict[str, Any]]:
        per_file_counts: Counter[str] = Counter()
        selected_rows: list[dict[str, Any]] = []
        for row in rows:
            file_path = str(row.get("file_path") or "")
            if per_file_counts[file_path] >= max_per_file:
                continue
            selected_rows.append(row)
            per_file_counts[file_path] += 1
            if len(selected_rows) >= limit:
                break
        return selected_rows

    operational_symbol_risk_rows = [
        row
        for row in symbol_risk_rows
        if str(row.get("symbol_kind") or "") in operational_symbol_kinds
    ]
    symbol_reference_edges = []
    for source_symbol_id, target_symbol_id in raw_symbol_reference_edges:
        source_row = symbol_risk_rows_by_id.get(source_symbol_id)
        target_row = symbol_risk_rows_by_id.get(target_symbol_id)
        if source_row is None or target_row is None:
            continue
        cross_file = str(source_row["file_path"]) != str(target_row["file_path"])
        combined_risk_score = (
            int(source_row["risk_score"])
            + int(target_row["risk_score"])
            + (20 if cross_file else 0)
        )
        symbol_reference_edges.append(
            {
                "source_file": str(source_row["file_path"]),
                "source_symbol": str(source_row["symbol_name"]),
                "source_kind": str(source_row["symbol_kind"]),
                "source_risk_score": int(source_row["risk_score"]),
                "target_file": str(target_row["file_path"]),
                "target_symbol": str(target_row["symbol_name"]),
                "target_kind": str(target_row["symbol_kind"]),
                "target_risk_score": int(target_row["risk_score"]),
                "cross_file": cross_file,
                "combined_risk_score": combined_risk_score,
            }
        )
    symbol_reference_edges.sort(
        key=lambda row: (
            -int(row["combined_risk_score"]),
            -int(row["target_risk_score"]),
            0 if bool(row["cross_file"]) else 1,
            str(row["source_file"]),
            str(row["source_symbol"]),
            str(row["target_file"]),
            str(row["target_symbol"]),
        )
    )
    operational_reference_edges = [
        row
        for row in symbol_reference_edges
        if row["target_kind"] in operational_symbol_kinds
    ]
    operational_reference_edges.sort(
        key=lambda row: (
            -int(row["combined_risk_score"]),
            0 if bool(row["cross_file"]) else 1,
            -int(row["target_risk_score"]),
            str(row["source_file"]),
            str(row["source_symbol"]),
            str(row["target_file"]),
            str(row["target_symbol"]),
        )
    )

    return {
        "resolved_dependency_edge_count": sum(outbound_counts.values()),
        "unresolved_dependency_count": sum(unresolved_dependency_targets.values()),
        "cross_boundary_edge_count": cross_boundary_edges,
        "symbol_count": len(symbol_rows),
        "parent_child_symbol_count": sum(nested_symbol_counts.values()),
        "symbol_reference_edge_count": sum(symbol_reference_outbound_counts.values()),
        "highest_change_risk_files": risk_rows[:16],
        "highest_change_risk_symbols": _limit_symbol_rows(
            symbol_risk_rows,
            limit=24,
            max_per_file=3,
        ),
        "highest_change_risk_operational_symbols": _limit_symbol_rows(
            operational_symbol_risk_rows,
            limit=24,
            max_per_file=2,
        ),
        "top_symbol_reference_edges": symbol_reference_edges[:24],
        "highest_change_risk_operational_edges": operational_reference_edges[:24],
        "unresolved_dependency_samples": [
            {"target": target, "count": count}
            for target, count in unresolved_dependency_targets.most_common(16)
        ],
    }


def candidate_solutions(diagnostics: list[RepositoryDiagnostic]) -> list[dict[str, Any]]:
    if not diagnostics:
        return []
    ts6059 = [entry for entry in diagnostics if entry.code == "TS6059"]
    if ts6059:
        impacted_paths = sorted({entry.path for entry in ts6059 if entry.path})
        return [
            {
                "problem_class": "typescript_rootdir_drift",
                "diagnostic_count": len(ts6059),
                "summary": (
                    "TypeScript compilation includes files outside the configured rootDir. "
                    "This usually indicates a monorepo boundary mismatch between the service "
                    "tsconfig and imported workspace packages or testing helpers."
                ),
                "candidate_actions": [
                    "Broaden rootDir or switch to project references for imported "
                    "workspace packages.",
                    "Move test-only includes into a tsconfig that intentionally "
                    "spans the testing subtree.",
                    "Replace deep relative imports that cross workspace boundaries "
                    "with compiled package entrypoints.",
                ],
                "impacted_paths": impacted_paths[:20],
            }
        ]
    grouped = Counter(entry.code or "unclassified" for entry in diagnostics)
    return [
        {
            "problem_class": "generic_compiler_diagnostics",
            "diagnostic_count": len(diagnostics),
            "summary": (
                "Compiler diagnostics were parsed successfully, but no specialized "
                "solution rule matched."
            ),
            "candidate_actions": [
                "Review the top diagnostic clusters and snapshot only the implicated paths.",
                "Feed the bounded evidence bundle into a provider-backed repository "
                "planner when available.",
            ],
            "diagnostic_groups": dict(grouped),
        }
    ]


__all__ = [
    "ProbeGraphSupportDependencies",
    "build_connected_dependency_map",
    "candidate_solutions",
    "load_snapshot_graph_summary",
]
