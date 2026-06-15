from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_q_parser_dispatch as repository_intelligence_q_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    q_analysis_support as repository_q_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    q_primitives as repository_q_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def _connector_for_repo(repo_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )


def _init_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Repo Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-qm", "Initial commit"], check=True)


def test_repository_intelligence_q_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["q"] is (
        repository_intelligence_q_parser_dispatch._parse_q_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["q"] is (
        repository_intelligence_q_parser_dispatch._parse_q_dependencies_only
    )


def test_repository_intelligence_q_helpers_are_modularized() -> None:
    assert repository_service.q_adapter.has_q_path_hints is repository_q_primitives.has_q_path_hints
    assert repository_service.q_adapter.is_probable_q_source is (
        repository_q_analysis_support.is_probable_q_source
    )
    assert repository_service.q_adapter.iter_dependency_entries is (
        repository_q_primitives.iter_dependency_entries
    )
    assert repository_service.q_adapter.module_aliases_for_path is (
        repository_q_analysis_support.module_aliases_for_path
    )
    assert repository_service.q_adapter.parse_file is repository_q_analysis_support.parse_file


def test_q_adapter_parse_file_extracts_local_symbol_references() -> None:
    text = "helper:{[x]\n  x + 1\n}\nrunner:{[x]\n  helper x\n}\n"

    symbols, dependencies, references = repository_service.q_adapter.parse_file(
        "main.q",
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert not dependencies
    assert any(symbol.symbol_name == "helper" for symbol in symbols)
    assert any(symbol.symbol_name == "runner" for symbol in symbols)
    assert any(reference.target_names == ("helper",) for reference in references)


def test_q_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".q" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("scripts/main.q"),
            text="helper:{[x]\n  x + 1\n}\n",
        )
        == "q"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/main.q"),
            text="plain notes without q syntax\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_q_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "q-profile-repo"
    (repo_path / "code").mkdir(parents=True)
    for index in range(6):
        (repo_path / "code" / f"module_{index}.q").write_text(
            f"helper{index}:{{[x]\n  x + {index}\n}}\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    for index in range(2):
        (repo_path / "tools" / f"helper_{index}.py").write_text(
            "print('helper')\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "q" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "q"


def test_repository_snapshot_graph_contains_q_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "q-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.q").write_text(
        "helper:{[x]\n  x + 1\n}\nrunner:{[x]\n  helper x\n}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.q"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    runner_symbol_id = symbol_ids[("main.q", "runner")]
    helper_symbol_id = symbol_ids[("main.q", "helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{runner_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
