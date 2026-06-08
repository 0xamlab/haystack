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
    repository_intelligence_mermaid_parser_dispatch as repository_mermaid_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    mermaid_analysis_support as repository_mermaid_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    mermaid_primitives as repository_mermaid_primitives,
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


def test_repository_intelligence_mermaid_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["mermaid"] is (
        repository_mermaid_parser_dispatch._parse_mermaid_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["mermaid"] is (
        repository_mermaid_parser_dispatch._parse_mermaid_dependencies_only
    )


def test_repository_intelligence_mermaid_helpers_are_modularized() -> None:
    assert repository_service.mermaid_adapter.has_mermaid_path_hints is (
        repository_mermaid_primitives.has_mermaid_path_hints
    )
    assert repository_service.mermaid_adapter.is_probable_mermaid_source is (
        repository_mermaid_analysis_support.is_probable_mermaid_source
    )
    assert repository_service.mermaid_adapter.iter_edge_entries is (
        repository_mermaid_primitives.iter_edge_entries
    )
    assert repository_service.mermaid_adapter.module_aliases_for_path is (
        repository_mermaid_analysis_support.module_aliases_for_path
    )
    assert repository_service.mermaid_adapter.parse_file is (
        repository_mermaid_analysis_support.parse_file
    )


def test_mermaid_adapter_module_aliases_include_path_stem(tmp_path: Path) -> None:
    repo_path = tmp_path / "mermaid-alias-repo"
    (repo_path / "diagrams").mkdir(parents=True)
    (repo_path / "diagrams" / "system.mmd").write_text(
        "flowchart TD\n  api --> db\n",
        encoding="utf-8",
    )

    aliases = repository_service.mermaid_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="diagrams/system.mmd",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "diagrams/system.mmd" in aliases
    assert "system" in aliases
    assert "diagrams.system" in aliases


def test_mermaid_adapter_parse_file_extracts_node_references() -> None:
    text = "flowchart TD\n  api --> db\n  db --> cache\n"

    symbols, dependencies, references = repository_service.mermaid_adapter.parse_file(
        "diagrams/flow.mmd",
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


def test_mermaid_language_detection_supports_mmd_without_overclaiming() -> None:
    assert ".mmd" in repository_service._TEXT_FILE_SUFFIXES
    assert ".mermaid" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("diagrams/flow.mmd"),
        text="flowchart TD\n  api --> db\n",
    ) == "mermaid"
    assert repository_service._language_for_path(
        Path("diagrams/plain.mmd"),
        text="plain notes without mermaid syntax\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_mermaid_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mermaid-profile-repo"
    (repo_path / "diagrams").mkdir(parents=True)
    for index in range(6):
        (repo_path / "diagrams" / f"flow_{index}.mmd").write_text(
            f"flowchart TD\n  node_{index} --> node_{index + 1}\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "tools" / "helper.py").write_text("print('mermaid')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "mermaid" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "mermaid"
    assert any(path.endswith(".mmd") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_does_not_force_mermaid_first_in_ts_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mermaid-mixed-ts-repo"
    (repo_path / "diagrams").mkdir(parents=True)
    for index in range(4):
        (repo_path / "diagrams" / f"flow_{index}.mmd").write_text(
            f"flowchart TD\n  a_{index} --> b_{index}\n",
            encoding="utf-8",
        )
    (repo_path / "src").mkdir(parents=True)
    for index in range(10):
        (repo_path / "src" / f"lib_{index}.ts").write_text(
            f"export const value{index} = {index};\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "mermaid" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "mermaid"
    assert "typescript" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_mermaid_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "mermaid-graph-repo"
    (repo_path / "diagrams").mkdir(parents=True)
    (repo_path / "diagrams" / "flow.mmd").write_text(
        "flowchart TD\n  api --> db\n  db --> cache\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["diagrams/**/*.mmd", "diagrams/*.mmd", "*.mmd"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    api_symbol_id = symbol_ids[("diagrams/flow.mmd", "api")]
    db_symbol_id = symbol_ids[("diagrams/flow.mmd", "db")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{api_symbol_id}"
        and str(row["target_node"]) == f"symbol:{db_symbol_id}"
        for row in graph
    )
