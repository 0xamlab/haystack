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
    repository_intelligence_graphviz_parser_dispatch as repository_graphviz_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    graphviz_analysis_support as repository_graphviz_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    graphviz_primitives as repository_graphviz_primitives,
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


def test_repository_intelligence_graphviz_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["graphviz"] is (
        repository_graphviz_parser_dispatch._parse_graphviz_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["graphviz"] is (
        repository_graphviz_parser_dispatch._parse_graphviz_dependencies_only
    )


def test_repository_intelligence_graphviz_helpers_are_modularized() -> None:
    assert repository_service.graphviz_adapter.has_graphviz_path_hints is (
        repository_graphviz_primitives.has_graphviz_path_hints
    )
    assert repository_service.graphviz_adapter.is_probable_graphviz_source is (
        repository_graphviz_analysis_support.is_probable_graphviz_source
    )
    assert repository_service.graphviz_adapter.iter_edge_entries is (
        repository_graphviz_primitives.iter_edge_entries
    )
    assert repository_service.graphviz_adapter.iter_node_entries is (
        repository_graphviz_primitives.iter_node_entries
    )
    assert repository_service.graphviz_adapter.module_aliases_for_path is (
        repository_graphviz_analysis_support.module_aliases_for_path
    )
    assert repository_service.graphviz_adapter.parse_file is (
        repository_graphviz_analysis_support.parse_file
    )


def test_graphviz_adapter_module_aliases_include_graph_name(tmp_path: Path) -> None:
    repo_path = tmp_path / "graphviz-alias-repo"
    (repo_path / "graphs").mkdir(parents=True)
    (repo_path / "graphs" / "network.dot").write_text(
        "digraph Network { api -> db; }\n",
        encoding="utf-8",
    )

    aliases = repository_service.graphviz_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="graphs/network.dot",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "graphs/network.dot" in aliases
    assert "network" in aliases
    assert "Network" in aliases


def test_graphviz_adapter_parse_file_extracts_node_references() -> None:
    text = "digraph Flow {\n  api -> db;\n  db -> cache;\n}\n"

    symbols, dependencies, references = repository_service.graphviz_adapter.parse_file(
        "graphs/flow.dot",
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert not dependencies
    assert any(symbol.symbol_name == "api" for symbol in symbols)
    assert any(symbol.symbol_name == "db" for symbol in symbols)
    assert any(reference.target_names == ("db",) for reference in references)
    assert any(reference.target_names == ("cache",) for reference in references)


def test_graphviz_language_detection_supports_dot_and_gv_without_overclaiming() -> None:
    assert ".dot" in repository_service._TEXT_FILE_SUFFIXES
    assert ".gv" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("graphs/flow.dot"),
        text="digraph Flow { api -> db; }\n",
    ) == "graphviz"
    assert repository_service._language_for_path(
        Path("graphs/plain.dot"),
        text="plain notes without graph syntax\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_graphviz_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "graphviz-profile-repo"
    (repo_path / "graphs").mkdir(parents=True)
    for index in range(6):
        (repo_path / "graphs" / f"flow_{index}.dot").write_text(
            f"digraph Flow{index} {{ node_{index} -> node_{index + 1}; }}\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "tools" / "helper.py").write_text("print('graphviz')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "graphviz" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "graphviz"
    assert any(path.endswith(".dot") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_does_not_force_graphviz_first_in_rust_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "graphviz-mixed-rust-repo"
    (repo_path / "graphs").mkdir(parents=True)
    for index in range(4):
        (repo_path / "graphs" / f"flow_{index}.dot").write_text(
            f"digraph Flow{index} {{ a_{index} -> b_{index}; }}\n",
            encoding="utf-8",
        )
    (repo_path / "src").mkdir(parents=True)
    for index in range(10):
        (repo_path / "src" / f"lib_{index}.rs").write_text(
            f"pub fn value_{index}() -> usize {{ {index} }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "graphviz" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "graphviz"
    assert "rust" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_graphviz_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "graphviz-graph-repo"
    (repo_path / "graphs").mkdir(parents=True)
    (repo_path / "graphs" / "flow.dot").write_text(
        "digraph Flow {\n  api -> db;\n  db -> cache;\n}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["graphs/**/*.dot", "graphs/*.dot", "*.dot"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    api_symbol_id = symbol_ids[("graphs/flow.dot", "api")]
    db_symbol_id = symbol_ids[("graphs/flow.dot", "db")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{api_symbol_id}"
        and str(row["target_node"]) == f"symbol:{db_symbol_id}"
        for row in graph
    )
