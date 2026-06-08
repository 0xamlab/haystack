"""Shared imports + helpers for test_repository_intelligence_real_repo_probe_* sub-modules.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import benchmarks.repository_intelligence_real_repo_probe as probe_module
from apps.api_server.schemas.repositories import (
    RepositoryDiagnostic,
    RepositorySnapshotCreateRequest,
)
from apps.api_server.schemas.response import (
    DecisionEnvelope,
    MetricsSummary,
    PercentileSummary,
    RunMetadata,
)
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_language_priority import (
    REPOSITORY_LANGUAGE_POPULARITY_ORDER,
    sort_repository_languages,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _build_connected_dependency_map,
    _candidate_config_focus_paths,
    _candidate_existing_leaf_roots,
    _candidate_repository_file_paths,
    _candidate_solutions,
    _connected_map_candidate_file_limit,
    _derive_operational_seed_paths_without_diagnostics,
    _derive_operational_seed_plan_without_diagnostics,
    _effective_focus_paths_for_snapshot,
    _focus_paths_from_diagnostics,
    _load_snapshot_graph_summary,
    _repo_profile_candidate_paths,
    _repo_profile_config_paths,
    _resolve_diagnostic_base_path,
    _resolve_diagnostic_project_path,
    _should_group_focus_path_scan,
    _should_use_seeded_profile_candidate_scan,
    _store_probe_prepass_cache,
    _support_roots_need_expansion,
    _support_roots_requiring_expansion,
    parse_repository_diagnostics,
    run_probe,
)


def _probe_envelope() -> DecisionEnvelope:
    return DecisionEnvelope(
        run_id="00000000-0000-0000-0000-000000000001",
        engine_version="2026.05.0",
        recommended_action="apply_patch",
        confidence=0.93,
        rationale="Patch simulation satisfies the current execution policy.",
        metrics=MetricsSummary(
            expected_value=91.0,
            median=88.0,
            std_deviation=7.0,
            variance=49.0,
            probability_of_loss=0.05,
            var_95=6.0,
            cvar_95=9.0,
        ),
        percentiles=PercentileSummary(
            p5=-6.0,
            p25=72.0,
            p50=88.0,
            p75=97.0,
            p95=111.0,
        ),
        scenarios_run=5000,
        execution_ms=9,
        metadata=RunMetadata(
            mode="expert",
            seed=42,
            billing_units=1,
            engine_version="2026.05.0",
        ),
    )


def _init_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Repo Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-m", "Initial commit"], check=True)


def _typescript_rootdir_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "probe-rootdir-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        '{"name":"@acme/common"}\n',
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "index.ts").write_text(
        "import { shared } from '@acme/common/shared';\n"
        "export const run = (): string => shared();\n",
        encoding="utf-8",
    )
    (repo_path / "packages" / "common" / "src" / "shared.ts").write_text(
        "export function shared(): string {\n"
        "  return 'shared';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "tsconfig.json").write_text(
        '{\n'
        '  "compilerOptions": { "outDir": "dist", "rootDir": "../.." },\n'
        '  "include": ["src"]\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "tsconfig.test.json").write_text(
        '{\n'
        '  "extends": "./tsconfig.json",\n'
        '  "compilerOptions": {\n'
        '    "noEmit": true,\n'
        '    "rootDir": ".",\n'
        '    "baseUrl": ".",\n'
        '    "paths": {\n'
        '      "@acme/common": ["../../packages/common/src/index.ts"],\n'
        '      "@acme/common/*": ["../../packages/common/src/*"]\n'
        "    }\n"
        "  },\n"
        '  "include": ["src"]\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "diagnostics.txt").write_text(
        "../../packages/common/src/shared.ts(1,1): error TS6059: File is not under 'rootDir'.\n",
        encoding="utf-8",
    )
    return repo_path


def _write_scratch_project(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(payload, indent=2, sort_keys=True))


def _scratch_project_payload(name: str = "Maze") -> dict[str, object]:
    return {
        "extensions": [],
        "meta": {"agent": "pytest", "semver": "3.0.0", "vm": "0.2.0"},
        "monitors": [],
        "targets": [
            {
                "blocks": {
                    "stage_event": {
                        "fields": {},
                        "inputs": {},
                        "next": "stage_broadcast",
                        "opcode": "event_whenflagclicked",
                        "parent": None,
                        "topLevel": True,
                    },
                    "stage_broadcast": {
                        "fields": {},
                        "inputs": {"BROADCAST_INPUT": [1, [11, "start", "broadcast-id"]]},
                        "next": None,
                        "opcode": "event_broadcast",
                        "parent": "stage_event",
                        "topLevel": False,
                    },
                },
                "broadcasts": {"broadcast-id": "start"},
                "comments": {},
                "costumes": [],
                "currentCostume": 0,
                "isStage": True,
                "lists": {},
                "name": "Stage",
                "sounds": [],
                "tempo": 60,
                "variables": {},
                "videoState": "on",
                "videoTransparency": 50,
                "volume": 100,
            },
            {
                "blocks": {
                    "receive": {
                        "fields": {"BROADCAST_OPTION": ["start", "broadcast-id"]},
                        "inputs": {},
                        "next": "call",
                        "opcode": "event_whenbroadcastreceived",
                        "parent": None,
                        "topLevel": True,
                    },
                    "call": {
                        "fields": {},
                        "inputs": {},
                        "mutation": {
                            "argumentids": "[]",
                            "proccode": "init",
                            "warp": "false",
                        },
                        "next": None,
                        "opcode": "procedures_call",
                        "parent": "receive",
                        "topLevel": False,
                    },
                    "define": {
                        "fields": {},
                        "inputs": {"custom_block": [1, "prototype"]},
                        "next": None,
                        "opcode": "procedures_definition",
                        "parent": None,
                        "topLevel": True,
                    },
                    "prototype": {
                        "fields": {},
                        "inputs": {},
                        "mutation": {
                            "argumentids": "[]",
                            "proccode": "init",
                            "warp": "false",
                        },
                        "next": None,
                        "opcode": "procedures_prototype",
                        "parent": "define",
                        "topLevel": False,
                    },
                },
                "broadcasts": {},
                "comments": {},
                "costumes": [],
                "currentCostume": 0,
                "isStage": False,
                "lists": {},
                "name": name,
                "size": 100,
                "sounds": [],
                "variables": {},
                "visible": True,
                "volume": 100,
                "x": 0,
                "y": 0,
            },
        ],
    }



__all__ = [
    "DecisionEnvelope",
    "MetricsSummary",
    "Path",
    "PercentileSummary",
    "REPOSITORY_LANGUAGE_POPULARITY_ORDER",
    "RepositoryDiagnostic",
    "RepositorySnapshotCreateRequest",
    "RunMetadata",
    "SimpleNamespace",
    "_build_connected_dependency_map",
    "_candidate_config_focus_paths",
    "_candidate_existing_leaf_roots",
    "_candidate_repository_file_paths",
    "_candidate_solutions",
    "_connected_map_candidate_file_limit",
    "_derive_operational_seed_paths_without_diagnostics",
    "_derive_operational_seed_plan_without_diagnostics",
    "_effective_focus_paths_for_snapshot",
    "_focus_paths_from_diagnostics",
    "_init_git_repo",
    "_load_snapshot_graph_summary",
    "_probe_envelope",
    "_repo_profile_candidate_paths",
    "_repo_profile_config_paths",
    "_resolve_diagnostic_base_path",
    "_resolve_diagnostic_project_path",
    "_scratch_project_payload",
    "_should_group_focus_path_scan",
    "_should_use_seeded_profile_candidate_scan",
    "_store_probe_prepass_cache",
    "_support_roots_need_expansion",
    "_support_roots_requiring_expansion",
    "_typescript_rootdir_repo",
    "_write_scratch_project",
    "annotations",
    "json",
    "parse_repository_diagnostics",
    "probe_module",
    "pytest",
    "repository_service",
    "run_probe",
    "sort_repository_languages",
    "subprocess",
    "zipfile",
]
