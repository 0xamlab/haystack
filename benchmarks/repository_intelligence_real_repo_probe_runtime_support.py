from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.api_server.schemas.repositories import (
    RepositoryApplyMode,
    RepositoryApplyRequest,
    RepositoryDecisionPlanCreateRequest,
    RepositoryDiagnostic,
    RepositoryGraphQueryRequest,
    RepositorySimulationRequest,
    RepositorySnapshotCreateRequest,
    RepositoryTriageRequest,
)
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import repository_intelligence_runtime as runtime_service


@dataclass(frozen=True)
class ProbePrepassDependencies:
    default_exclude_patterns: list[str]
    default_include_patterns: list[str]
    prepass_cache_schema_version: str
    build_connected_dependency_map: Callable[..., dict[str, Any]]
    candidate_config_focus_paths: Callable[..., list[str]]
    candidate_solutions: Callable[[list[RepositoryDiagnostic]], list[dict[str, Any]]]
    derive_operational_seed_plan_without_diagnostics: Callable[..., dict[str, Any]]
    effective_focus_paths_for_snapshot: Callable[..., list[str]]
    focus_paths_from_diagnostics: Callable[..., list[str]]
    inventory_repo_surface: Callable[..., dict[str, Any]]
    parse_repository_diagnostics: Callable[..., list[RepositoryDiagnostic]]
    resolve_diagnostic_base_path: Callable[..., Path]
    resolve_diagnostic_project_path: Callable[..., str | None]
    run_command: Callable[[Path, str], dict[str, Any]]


@dataclass(frozen=True)
class ProbeRunDependencies:
    default_exclude_patterns: list[str]
    default_include_patterns: list[str]
    compute_probe_prepass: Callable[..., dict[str, Any]]
    load_snapshot_graph_summary: Callable[..., dict[str, Any]]
    repository_connector: Callable[[Path], Any]


def probe_repo_state(repo_path: Path) -> dict[str, Any]:
    if not repository_service._is_git_repository(repo_path):  # type: ignore[attr-defined]
        return {
            "cache_enabled": False,
            "cache_mode": "disabled",
            "reason": "non_git_repository",
            "resolved_revision": None,
            "state_id": None,
            "dirty": None,
            "status_entry_count": None,
            "status_hash": None,
        }
    try:
        resolved_revision = str(
            repository_service._git_command(  # type: ignore[attr-defined]
                ["git", "-C", str(repo_path), "rev-parse", "HEAD"]
            )
        ).strip()
        status_text = str(
            repository_service._git_command(  # type: ignore[attr-defined]
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "status",
                    "--porcelain=v1",
                    "--untracked-files=all",
                    "--ignored=no",
                ],
                timeout=60.0,
            )
        )
    except Exception:  # noqa: BLE001
        return {
            "cache_enabled": False,
            "cache_mode": "disabled",
            "reason": "git_state_unavailable",
            "resolved_revision": None,
            "state_id": None,
            "dirty": None,
            "status_entry_count": None,
            "status_hash": None,
        }
    status_lines = [line.rstrip("\n") for line in status_text.splitlines() if line.strip()]
    return {
        "cache_enabled": True,
        "cache_mode": "git",
        "reason": None,
        "resolved_revision": resolved_revision,
        "state_id": repository_service._hash_payload(  # type: ignore[attr-defined]
            {"resolved_revision": resolved_revision, "status_lines": status_lines}
        ),
        "dirty": bool(status_lines),
        "status_entry_count": len(status_lines),
        "status_hash": repository_service._hash_payload(status_lines),  # type: ignore[attr-defined]
    }


def probe_prepass_cache_key(
    *,
    repo_state: dict[str, Any],
    focus_paths: list[str],
    diagnostic_command: str | None,
    diagnostic_base_path: str | None,
    include_patterns: list[str],
    exclude_patterns: list[str],
    max_files: int,
    max_file_size_bytes: int,
    max_dependency_depth: int,
    max_connected_files: int,
    prepass_cache_schema_version: str,
) -> str | None:
    state_id = repo_state.get("state_id")
    if not state_id:
        return None
    return repository_service._hash_payload(  # type: ignore[attr-defined]
        {
            "schema_version": prepass_cache_schema_version,
            "repo_state_id": state_id,
            "focus_paths": list(focus_paths),
            "diagnostic_command": diagnostic_command,
            "diagnostic_base_path": diagnostic_base_path,
            "include_patterns": list(include_patterns),
            "exclude_patterns": list(exclude_patterns),
            "max_files": max_files,
            "max_file_size_bytes": max_file_size_bytes,
            "max_dependency_depth": max_dependency_depth,
            "max_connected_files": max_connected_files,
        }
    )


def probe_prepass_cache_path(repository_runtime_root: Path, cache_key: str | None) -> Path | None:
    if not cache_key:
        return None
    return repository_runtime_root / "probe_prepass" / f"{cache_key}.json"


def load_probe_prepass_cache(
    cache_path: Path | None,
    *,
    prepass_cache_schema_version: str,
) -> dict[str, Any] | None:
    if cache_path is None or not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("schema_version") != prepass_cache_schema_version:
        return None
    return payload


def store_probe_prepass_cache(cache_path: Path | None, payload: dict[str, Any]) -> None:
    if cache_path is None:
        return
    serialized_payload = json.dumps(payload, indent=2, sort_keys=True)
    temp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
    for _attempt in range(2):
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(serialized_payload, encoding="utf-8")
        try:
            temp_path.replace(cache_path)
            return
        except FileNotFoundError:
            continue


def compute_probe_prepass(
    *,
    repo_path: Path,
    focus_paths: list[str],
    diagnostic_command: str | None,
    diagnostic_base_path: str | None,
    repository_runtime_root: Path,
    max_files: int,
    max_file_size_bytes: int,
    max_dependency_depth: int,
    max_connected_files: int,
    deps: ProbePrepassDependencies,
) -> dict[str, Any]:
    default_include_patterns = deps.default_include_patterns
    default_exclude_patterns = deps.default_exclude_patterns
    prepass_cache_schema_version = deps.prepass_cache_schema_version
    _build_connected_dependency_map = deps.build_connected_dependency_map
    _candidate_config_focus_paths = deps.candidate_config_focus_paths
    _candidate_solutions = deps.candidate_solutions
    _derive_operational_seed_plan_without_diagnostics = (
        deps.derive_operational_seed_plan_without_diagnostics
    )
    _effective_focus_paths_for_snapshot = deps.effective_focus_paths_for_snapshot
    _focus_paths_from_diagnostics = deps.focus_paths_from_diagnostics
    _inventory_repo_surface = deps.inventory_repo_surface
    parse_repository_diagnostics = deps.parse_repository_diagnostics
    _resolve_diagnostic_base_path = deps.resolve_diagnostic_base_path
    _resolve_diagnostic_project_path = deps.resolve_diagnostic_project_path
    _run_command = deps.run_command

    started = time.perf_counter_ns()
    repo_state = probe_repo_state(repo_path)
    cache_key = probe_prepass_cache_key(
        repo_state=repo_state,
        focus_paths=focus_paths,
        diagnostic_command=diagnostic_command,
        diagnostic_base_path=diagnostic_base_path,
        include_patterns=default_include_patterns,
        exclude_patterns=default_exclude_patterns,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_dependency_depth=max_dependency_depth,
        max_connected_files=max_connected_files,
        prepass_cache_schema_version=prepass_cache_schema_version,
    )
    cache_path = probe_prepass_cache_path(repository_runtime_root, cache_key)
    cached_payload = load_probe_prepass_cache(
        cache_path,
        prepass_cache_schema_version=prepass_cache_schema_version,
    )
    if cached_payload is not None:
        diagnostics = [
            RepositoryDiagnostic.model_validate(item)
            for item in cached_payload.get("diagnostics", [])
        ]
        return {
            "elapsed_ms": round((time.perf_counter_ns() - started) / 1_000_000.0, 2),
            "cache_status": "hit",
            "cache_enabled": bool(repo_state.get("cache_enabled")),
            "cache_reason": repo_state.get("reason"),
            "cache_key": cache_key,
            "cache_path": str(cache_path) if cache_path else None,
            "repo_state": repo_state,
            "resolved_diagnostic_base_path": Path(
                str(cached_payload["resolved_diagnostic_base_path"])
            ),
            "diagnostic_project_path": cached_payload.get("diagnostic_project_path"),
            "diagnostics": diagnostics,
            "connected_map": cached_payload["connected_map"],
            "fallback_focus_paths": cached_payload["fallback_focus_paths"],
            "config_focus_paths": cached_payload["config_focus_paths"],
            "effective_focus_paths": cached_payload["effective_focus_paths"],
            "inventory": cached_payload["inventory"],
            "candidate_solutions": cached_payload["candidate_solutions"],
            "operational_seed_plan": cached_payload.get("operational_seed_plan"),
            "command": cached_payload.get("command"),
            "command_elapsed_ms": 0.0,
            "cached_command_elapsed_ms": cached_payload.get("command_elapsed_ms"),
            "command_exit_code": cached_payload.get("command_exit_code"),
        }

    command_result = _run_command(repo_path, diagnostic_command) if diagnostic_command else None
    resolved_diagnostic_base_path = _resolve_diagnostic_base_path(
        repo_path,
        diagnostic_command=diagnostic_command,
        diagnostic_base_path=diagnostic_base_path,
    )
    diagnostic_project_path = _resolve_diagnostic_project_path(
        repo_path,
        diagnostic_command=diagnostic_command,
        diagnostic_base_path=resolved_diagnostic_base_path,
    )
    diagnostics = (
        parse_repository_diagnostics(
            repo_path=repo_path,
            output=command_result["combined_output"],
            base_path=resolved_diagnostic_base_path,
        )
        if command_result is not None
        else []
    )
    graph_seed_paths = sorted({item.path for item in diagnostics if item.path})
    operational_seed_plan: dict[str, Any] | None = None
    connected_map_bridge_paths = list(focus_paths)
    if not graph_seed_paths:
        operational_seed_plan = _derive_operational_seed_plan_without_diagnostics(
            repo_path=repo_path,
            focus_paths=focus_paths,
            max_files=max_files,
        )
        graph_seed_paths = list(operational_seed_plan["entrypoint_files"])
        connected_map_bridge_paths = []
    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=graph_seed_paths,
        bridge_paths=connected_map_bridge_paths,
        candidate_file_paths=(
            None
            if operational_seed_plan is None
            else list(operational_seed_plan["candidate_file_paths"])
        ),
        candidate_scope_paths=(
            None
            if operational_seed_plan is None
            else list(operational_seed_plan["support_roots"])
        ),
        enable_reverse_bridging=operational_seed_plan is None,
        include_patterns=default_include_patterns,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_dependency_depth=max_dependency_depth,
        max_connected_files=max_connected_files,
    )
    fallback_focus_paths = _focus_paths_from_diagnostics(
        repo_path=repo_path,
        diagnostics=diagnostics,
        explicit_focus_paths=focus_paths,
    )
    config_focus_paths = _candidate_config_focus_paths(
        repo_path=repo_path,
        focus_paths=focus_paths,
        diagnostic_base_path=resolved_diagnostic_base_path,
        diagnostic_project_path=diagnostic_project_path,
    )
    effective_focus_paths = _effective_focus_paths_for_snapshot(
        diagnostics=diagnostics,
        connected_files=list(connected_map["connected_files"]),
        fallback_focus_paths=fallback_focus_paths,
        config_focus_paths=config_focus_paths,
    )
    inventory = _inventory_repo_surface(
        repo_path=repo_path,
        focus_paths=effective_focus_paths,
        include_patterns=default_include_patterns,
        exclude_dirnames=set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS),
        max_file_size_bytes=max_file_size_bytes,
    )
    candidate_solutions = _candidate_solutions(diagnostics)
    cache_status = "miss_stored" if cache_path is not None else "miss_not_cacheable"
    store_probe_prepass_cache(
        cache_path,
        {
            "schema_version": prepass_cache_schema_version,
            "created_at": repository_service._utc_now().isoformat(),  # type: ignore[attr-defined]
            "repo_state": repo_state,
            "resolved_diagnostic_base_path": str(resolved_diagnostic_base_path),
            "diagnostic_project_path": diagnostic_project_path,
            "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
            "connected_map": connected_map,
            "fallback_focus_paths": fallback_focus_paths,
            "config_focus_paths": config_focus_paths,
            "effective_focus_paths": effective_focus_paths,
            "inventory": inventory,
            "candidate_solutions": candidate_solutions,
            "operational_seed_plan": operational_seed_plan,
            "command": command_result["command"] if command_result else diagnostic_command,
            "command_elapsed_ms": command_result["elapsed_ms"] if command_result else None,
            "command_exit_code": command_result["exit_code"] if command_result else None,
        },
    )
    return {
        "elapsed_ms": round((time.perf_counter_ns() - started) / 1_000_000.0, 2),
        "cache_status": cache_status,
        "cache_enabled": bool(repo_state.get("cache_enabled")),
        "cache_reason": repo_state.get("reason"),
        "cache_key": cache_key,
        "cache_path": str(cache_path) if cache_path else None,
        "repo_state": repo_state,
        "resolved_diagnostic_base_path": resolved_diagnostic_base_path,
        "diagnostic_project_path": diagnostic_project_path,
        "diagnostics": diagnostics,
        "connected_map": connected_map,
        "fallback_focus_paths": fallback_focus_paths,
        "config_focus_paths": config_focus_paths,
        "effective_focus_paths": effective_focus_paths,
        "inventory": inventory,
        "candidate_solutions": candidate_solutions,
        "operational_seed_plan": operational_seed_plan,
        "command": command_result["command"] if command_result else diagnostic_command,
        "command_elapsed_ms": command_result["elapsed_ms"] if command_result else None,
        "cached_command_elapsed_ms": None,
        "command_exit_code": command_result["exit_code"] if command_result else None,
    }


def run_command(repo_path: Path, command: str) -> dict[str, Any]:
    started = time.perf_counter_ns()
    completed = subprocess.run(  # noqa: S603
        ["/bin/zsh", "-lc", command],
        cwd=str(repo_path),
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
    return {
        "command": command,
        "elapsed_ms": round(elapsed_ms, 2),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "combined_output": "\n".join(
            part for part in (completed.stdout.strip(), completed.stderr.strip()) if part
        ).strip(),
    }


def run_probe(
    *,
    repo_path: Path,
    focus_paths: list[str],
    diagnostic_command: str | None,
    diagnostic_base_path: str | None,
    planner_model: str | None,
    runtime_dir: Path,
    reuse_existing_state: bool,
    max_files: int,
    max_file_size_bytes: int,
    max_total_bytes: int | None,
    max_dependency_depth: int,
    max_connected_files: int,
    deps: ProbeRunDependencies,
) -> dict[str, Any]:
    default_include_patterns = deps.default_include_patterns
    default_exclude_patterns = deps.default_exclude_patterns
    _compute_probe_prepass = deps.compute_probe_prepass
    _load_snapshot_graph_summary = deps.load_snapshot_graph_summary
    _repository_connector = deps.repository_connector

    connector = _repository_connector(repo_path)
    snapshot_request = RepositorySnapshotCreateRequest(
        focus_paths=[],
        include_patterns=default_include_patterns,
        exclude_patterns=default_exclude_patterns,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_total_bytes=max_total_bytes,
    )
    runtime_dir = runtime_dir.resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    original_runtime_dir = os.environ.get("ALGENTA_RUNTIME_DIR")
    os.environ["ALGENTA_RUNTIME_DIR"] = str(runtime_dir)
    repository_runtime_root = runtime_service._repo_root_dir(
        str(connector.org_id),
        str(connector.id),
    )
    if not reuse_existing_state and repository_runtime_root.exists():
        shutil.rmtree(repository_runtime_root, ignore_errors=True)
    if planner_model:
        original_planner_model = os.environ.get("ALGENTA_REPOSITORY_INTELLIGENCE_MODEL")
        os.environ["ALGENTA_REPOSITORY_INTELLIGENCE_MODEL"] = planner_model
    else:
        original_planner_model = None
    try:
        prepass = _compute_probe_prepass(
            repo_path=repo_path,
            focus_paths=focus_paths,
            diagnostic_command=diagnostic_command,
            diagnostic_base_path=diagnostic_base_path,
            repository_runtime_root=repository_runtime_root,
            max_files=max_files,
            max_file_size_bytes=max_file_size_bytes,
            max_dependency_depth=max_dependency_depth,
            max_connected_files=max_connected_files,
        )
        diagnostics = list(prepass["diagnostics"])
        connected_map = prepass["connected_map"]
        config_focus_paths = list(prepass["config_focus_paths"])
        effective_focus_paths = list(prepass["effective_focus_paths"])
        inventory = prepass["inventory"]
        resolved_diagnostic_base_path = prepass["resolved_diagnostic_base_path"]
        diagnostic_project_path = prepass["diagnostic_project_path"]
        snapshot_request = snapshot_request.model_copy(
            update={"focus_paths": effective_focus_paths}
        )

        started = time.perf_counter_ns()
        cold_snapshot = repository_service.create_repository_snapshot(
            connector=connector,
            request=snapshot_request,
        )
        cold_snapshot_elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0

        warm_started = time.perf_counter_ns()
        warm_snapshot = repository_service.create_repository_snapshot(
            connector=connector,
            request=snapshot_request,
        )
        warm_snapshot_elapsed_ms = (time.perf_counter_ns() - warm_started) / 1_000_000.0

        graph_summary = _load_snapshot_graph_summary(
            repository_graph_path=cold_snapshot.repository_graph_artifact.storage_path,
            dependency_graph_path=cold_snapshot.dependency_graph_artifact.storage_path,
            symbol_graph_path=cold_snapshot.symbol_graph_artifact.storage_path,
            seed_files=list(connected_map["seed_files"]),
        )

        triage_result: dict[str, Any] | None = None
        triage_elapsed_ms: float | None = None
        graph_query_result: dict[str, Any] | None = None
        graph_query_elapsed_ms: float | None = None
        decision_plan_result: dict[str, Any] | None = None
        decision_plan_elapsed_ms: float | None = None
        simulation_result: dict[str, Any] | None = None
        simulation_elapsed_ms: float | None = None
        apply_patch_only_result: dict[str, Any] | None = None
        apply_patch_only_elapsed_ms: float | None = None
        planner_status = "not_attempted_no_diagnostics"
        if diagnostics:
            workspace_context = []
            if diagnostic_command:
                workspace_context.append(f"command:{diagnostic_command}")
            if resolved_diagnostic_base_path == repo_path:
                diagnostic_base_path_ref = "."
            else:
                diagnostic_base_path_ref = str(
                    resolved_diagnostic_base_path.relative_to(repo_path)
                ).replace("\\", "/")
            workspace_context.append(f"diagnostic_base_path:{diagnostic_base_path_ref}")
            if diagnostic_project_path:
                workspace_context.append(f"tsconfig_project:{diagnostic_project_path}")
            triage_request = RepositoryTriageRequest(
                snapshot_id=cold_snapshot.snapshot_id,
                signals={
                    "issue_text": (
                        f"Read-only repository probe from command: {diagnostic_command}"
                        if diagnostic_command
                        else "Read-only repository probe diagnostics."
                    ),
                    "diagnostics": [item.model_dump(mode="json") for item in diagnostics[:64]],
                    "changed_files": sorted({item.path for item in diagnostics if item.path})[:64],
                    "workspace_context": workspace_context,
                },
                max_evidence_items=16,
                max_snippet_lines=20,
                token_budget=4000,
            )
            triage_started = time.perf_counter_ns()
            triage = repository_service.triage_repository(
                connector=connector,
                request=triage_request,
            )
            triage_elapsed_ms = (time.perf_counter_ns() - triage_started) / 1_000_000.0
            triage_result = triage.model_dump(mode="json")

            graph_seed_file = (
                triage.suspect_files[0]
                if triage.suspect_files
                else (effective_focus_paths[0] if effective_focus_paths else None)
            )
            graph_seed_symbol = None
            if graph_seed_file:
                for item in triage.evidence_items:
                    if item.file_path == graph_seed_file and item.symbol_name:
                        graph_seed_symbol = item.symbol_name
                        break
            if graph_seed_file or graph_seed_symbol:
                graph_query_started = time.perf_counter_ns()
                graph_query = repository_service.query_repository_graph(
                    connector=connector,
                    request=RepositoryGraphQueryRequest(
                        snapshot_id=cold_snapshot.snapshot_id,
                        file_path=graph_seed_file,
                        symbol_name=graph_seed_symbol,
                        direction="both",
                        max_depth=2,
                        max_nodes=96,
                    ),
                )
                graph_query_elapsed_ms = (
                    time.perf_counter_ns() - graph_query_started
                ) / 1_000_000.0
                graph_query_result = graph_query.model_dump(mode="json")

            planner_status = "planning_started"
            try:
                decision_started = time.perf_counter_ns()
                decision_plan = asyncio.run(
                    repository_service.create_repository_decision_plan(
                        connector=connector,
                        request=RepositoryDecisionPlanCreateRequest(
                            snapshot_id=cold_snapshot.snapshot_id,
                            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
                            model=planner_model,
                        ),
                    )
                )
                decision_plan_elapsed_ms = (
                    time.perf_counter_ns() - decision_started
                ) / 1_000_000.0
                decision_plan_result = decision_plan.model_dump(mode="json")
                planner_status = "decision_plan_completed"

                simulation_started = time.perf_counter_ns()
                envelope = asyncio.run(
                    repository_service.simulate_repository_decision(
                        connector=connector,
                        request=RepositorySimulationRequest(
                            snapshot_id=cold_snapshot.snapshot_id,
                            decision_plan_id=decision_plan.decision_plan_id,
                        ),
                    )
                )
                simulation_elapsed_ms = (
                    time.perf_counter_ns() - simulation_started
                ) / 1_000_000.0
                simulation_result = envelope.model_dump(mode="json")
                planner_status = "simulation_completed"

                simulation_id = str(envelope.validated_inputs["simulation_id"])
                apply_started = time.perf_counter_ns()
                apply_patch_only = asyncio.run(
                    repository_service.apply_repository_decision(
                        connector=connector,
                        request=RepositoryApplyRequest(
                            snapshot_id=cold_snapshot.snapshot_id,
                            decision_plan_id=decision_plan.decision_plan_id,
                            simulation_id=simulation_id,
                            mode=RepositoryApplyMode.PATCH_ONLY,
                        ),
                    )
                )
                apply_patch_only_elapsed_ms = (
                    time.perf_counter_ns() - apply_started
                ) / 1_000_000.0
                apply_patch_only_result = apply_patch_only.model_dump(mode="json")
                planner_status = "patch_only_completed"
            except repository_service.RepositoryIntelligenceError as exc:
                planner_status = exc.code
                decision_plan_result = {
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    }
                }
    finally:
        if original_runtime_dir is None:
            os.environ.pop("ALGENTA_RUNTIME_DIR", None)
        else:
            os.environ["ALGENTA_RUNTIME_DIR"] = original_runtime_dir
        if planner_model:
            if original_planner_model is None:
                os.environ.pop("ALGENTA_REPOSITORY_INTELLIGENCE_MODEL", None)
            else:
                os.environ["ALGENTA_REPOSITORY_INTELLIGENCE_MODEL"] = original_planner_model

    return {
        "repo_path": str(repo_path),
        "read_only": True,
        "runtime": {
            "runtime_dir": str(runtime_dir),
            "repository_runtime_root": str(repository_runtime_root),
            "persisted": True,
            "reuse_existing_state": reuse_existing_state,
        },
        "focus_paths": effective_focus_paths,
        "config_focus_paths": config_focus_paths,
        "diagnostic_base_path": str(resolved_diagnostic_base_path),
        "diagnostic_project_path": diagnostic_project_path,
        "prepass": {
            "elapsed_ms": prepass["elapsed_ms"],
            "cache_status": prepass["cache_status"],
            "cache_enabled": prepass["cache_enabled"],
            "cache_reason": prepass["cache_reason"],
            "cache_key": prepass["cache_key"],
            "cache_path": prepass["cache_path"],
            "repo_state": prepass["repo_state"],
        },
        "inventory": inventory,
        "connected_map": connected_map,
        "operational_seed_plan": prepass.get("operational_seed_plan"),
        "diagnostic_command": None
        if diagnostic_command is None
        else {
            "command": prepass["command"],
            "elapsed_ms": prepass["command_elapsed_ms"],
            "cached_elapsed_ms": prepass["cached_command_elapsed_ms"],
            "exit_code": prepass["command_exit_code"],
            "diagnostic_count": len(diagnostics),
            "cache_status": prepass["cache_status"],
        },
        "snapshot": {
            "elapsed_ms": round(cold_snapshot_elapsed_ms, 2),
            "status": cold_snapshot.status,
            "snapshot_id": cold_snapshot.snapshot_id,
            "file_count": cold_snapshot.file_count,
            "raw_repo_token_estimate": cold_snapshot.raw_repo_token_estimate,
            "language_counts": cold_snapshot.language_counts,
            "resolved_revision": cold_snapshot.resolved_revision,
            "warm_elapsed_ms": round(warm_snapshot_elapsed_ms, 2),
            "warm_status": warm_snapshot.status,
            "graph_summary": graph_summary,
        },
        "triage": None
        if triage_result is None
        else {
            "elapsed_ms": round(float(triage_elapsed_ms or 0.0), 2),
            **triage_result,
        },
        "graph_query": None
        if graph_query_result is None
        else {
            "elapsed_ms": round(float(graph_query_elapsed_ms or 0.0), 2),
            **graph_query_result,
        },
        "decision_plan": None
        if decision_plan_result is None
        else {
            "elapsed_ms": round(float(decision_plan_elapsed_ms or 0.0), 2),
            **decision_plan_result,
        },
        "simulation": None
        if simulation_result is None
        else {
            "elapsed_ms": round(float(simulation_elapsed_ms or 0.0), 2),
            **simulation_result,
        },
        "apply_patch_only": None
        if apply_patch_only_result is None
        else {
            "elapsed_ms": round(float(apply_patch_only_elapsed_ms or 0.0), 2),
            **apply_patch_only_result,
        },
        "candidate_solutions": prepass["candidate_solutions"],
        "planner_status": planner_status,
    }


def main(
    *,
    run_probe: Callable[..., dict[str, Any]],
    default_output: Path,
    default_persisted_runtime_dir: Path,
    default_planner_model: str | None,
) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run a read-only Algenta Repository Intelligence probe against a real local repository."
        )
    )
    parser.add_argument("--repo", type=Path, required=True, help="Path to the local repository.")
    parser.add_argument(
        "--focus-path",
        dest="focus_paths",
        action="append",
        default=[],
        help="Optional relative path or subtree to snapshot before diagnostics narrow further.",
    )
    parser.add_argument(
        "--diagnostic-command",
        type=str,
        default=None,
        help="Optional read-only command to run inside the repository to collect diagnostics.",
    )
    parser.add_argument(
        "--diagnostic-base-path",
        type=str,
        default=None,
        help="Optional repository-relative base path used to resolve relative diagnostics.",
    )
    parser.add_argument(
        "--planner-model",
        type=str,
        default=default_planner_model,
        help=(
            "Repository planner model to use for decision-plan generation. Defaults to the "
            "bounded deterministic local planner."
        ),
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=default_persisted_runtime_dir,
        help="Persistent runtime directory used to store repository benchmark artifacts.",
    )
    parser.add_argument(
        "--reuse-existing-state",
        action="store_true",
        help="Reuse existing persisted repository runtime state instead of resetting it first.",
    )
    parser.add_argument("--max-files", type=int, default=6000)
    parser.add_argument("--max-file-size-bytes", type=int, default=350_000)
    parser.add_argument("--max-total-bytes", type=int, default=25_000_000)
    parser.add_argument("--max-dependency-depth", type=int, default=4)
    parser.add_argument("--max-connected-files", type=int, default=256)
    parser.add_argument("--output", type=Path, default=default_output)
    args = parser.parse_args()

    result = run_probe(
        repo_path=args.repo.resolve(),
        focus_paths=list(args.focus_paths),
        diagnostic_command=args.diagnostic_command,
        diagnostic_base_path=args.diagnostic_base_path,
        planner_model=args.planner_model,
        runtime_dir=args.runtime_dir,
        reuse_existing_state=bool(args.reuse_existing_state),
        max_files=int(args.max_files),
        max_file_size_bytes=int(args.max_file_size_bytes),
        max_total_bytes=int(args.max_total_bytes),
        max_dependency_depth=int(args.max_dependency_depth),
        max_connected_files=int(args.max_connected_files),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


__all__ = [
    "ProbePrepassDependencies",
    "ProbeRunDependencies",
    "compute_probe_prepass",
    "load_probe_prepass_cache",
    "main",
    "probe_prepass_cache_key",
    "probe_prepass_cache_path",
    "probe_repo_state",
    "run_command",
    "run_probe",
    "store_probe_prepass_cache",
]
