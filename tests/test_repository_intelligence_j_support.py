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
    repository_intelligence_j_parser_dispatch as repository_intelligence_j_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    j_analysis_support as repository_j_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    j_primitives as repository_j_primitives,
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


def test_repository_intelligence_j_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["j"] is (
        repository_intelligence_j_parser_dispatch._parse_j_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["j"] is (
        repository_intelligence_j_parser_dispatch._parse_j_dependencies_only
    )


def test_repository_intelligence_j_helpers_are_modularized() -> None:
    assert repository_service.j_adapter.has_j_path_hints is repository_j_primitives.has_j_path_hints
    assert repository_service.j_adapter.is_probable_j_source is (
        repository_j_analysis_support.is_probable_j_source
    )
    assert repository_service.j_adapter.iter_dependency_entries is (
        repository_j_primitives.iter_dependency_entries
    )
    assert repository_service.j_adapter.module_aliases_for_path is (
        repository_j_analysis_support.module_aliases_for_path
    )
    assert repository_service.j_adapter.parse_file is repository_j_analysis_support.parse_file


def test_j_adapter_parse_file_extracts_local_symbol_references() -> None:
    text = "helper =: 3 : 0\n  y + 1\n)\nrunner =: 3 : 0\n  helper y\n)\n"

    symbols, dependencies, references = repository_service.j_adapter.parse_file(
        "main.ijs",
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


def test_j_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".ijs" in repository_service._TEXT_FILE_SUFFIXES
    assert ".ijt" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("src/main.ijs"),
            text="helper =: 3 : 0\n  y + 1\n)\n",
        )
        == "j"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.ijs"),
            text="plain notes without j syntax\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_j_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "j-profile-repo"
    (repo_path / "defs").mkdir(parents=True)
    for index in range(6):
        (repo_path / "defs" / f"module_{index}.ijs").write_text(
            f"helper{index} =: 3 : 0\n  y + {index}\n)\n",
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

    assert "j" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "j"


def test_operational_seed_plan_without_diagnostics_keeps_j_ahead_of_starlark_build_hosts(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "j-starlark-host-repo"
    (repo_path / "defs").mkdir(parents=True)
    for index in range(10):
        (repo_path / "defs" / f"module_{index}.ijs").write_text(
            f"helper{index} =: 3 : 0\n  y + {index}\n)\n",
            encoding="utf-8",
        )
    (repo_path / "defs" / "build").write_text(
        'load(":rules.bzl", "j_module")\n'
        'j_module(name = "defs")\n',
        encoding="utf-8",
    )
    (repo_path / "defs" / "hostdefs.c").write_text(
        "int main(void) { return 0; }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "j" in seed_plan["detected_ecosystems"]
    assert "starlark" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "j"


def test_repository_snapshot_graph_contains_j_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "j-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.ijs").write_text(
        "helper =: 3 : 0\n  y + 1\n)\nrunner =: 3 : 0\n  helper y\n)\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.ijs", "*.ijt"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    runner_symbol_id = symbol_ids[("main.ijs", "runner")]
    helper_symbol_id = symbol_ids[("main.ijs", "helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{runner_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
