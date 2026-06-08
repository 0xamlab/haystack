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
    repository_intelligence_hy_parser_dispatch as repository_intelligence_hy_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    hy_analysis_support as repository_hy_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    hy_primitives as repository_hy_primitives,
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


def test_repository_intelligence_hy_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["hy"] is (
        repository_intelligence_hy_parser_dispatch._parse_hy_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["hy"] is (
        repository_intelligence_hy_parser_dispatch._parse_hy_dependencies_only
    )


def test_repository_intelligence_hy_helpers_are_modularized() -> None:
    assert repository_service.hy_adapter.has_hy_path_hints is (
        repository_hy_primitives.has_hy_path_hints
    )
    assert repository_service.hy_adapter.is_probable_hy_source is (
        repository_hy_analysis_support.is_probable_hy_source
    )
    assert repository_service.hy_adapter.parse_import_entries is (
        repository_hy_primitives.parse_import_entries
    )
    assert repository_service.hy_adapter.module_aliases_for_path is (
        repository_hy_analysis_support.module_aliases_for_path
    )
    assert repository_service.hy_adapter.parse_file is (
        repository_hy_analysis_support.parse_file
    )


def test_hy_adapter_module_aliases_include_package_forms(tmp_path: Path) -> None:
    repo_path = tmp_path / "hy-alias-repo"
    (repo_path / "demo").mkdir(parents=True)
    (repo_path / "demo" / "hy_init.hy").write_text(
        "(require hyrule [defmain])\n(defn ping [] 1)\n",
        encoding="utf-8",
    )

    aliases = repository_service.hy_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="demo/hy_init.hy",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "demo/hy_init.hy" in aliases
    assert "demo" in aliases
    assert "ping" in aliases


def test_hy_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = {
        "demo.util": "demo/util.hy",
        "demo/util.hy": "demo/util.hy",
        "demo.macros": "demo/macros.hy",
        "demo/macros.hy": "demo/macros.hy",
    }
    text = (
        "(import demo.util [helper :as local-helper])\n"
        "(require demo.macros [expand-one])\n\n"
        "(defn helper [] 1)\n\n"
        "(defn runner []\n"
        "  (local-helper)\n"
        "  (expand-one)\n"
        "  (helper))\n"
    )

    symbols, dependencies, references = repository_service.hy_adapter.parse_file(
        "demo/main.hy",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "demo/util.hy" for dependency in dependencies)
    assert any(dependency.target_file == "demo/macros.hy" for dependency in dependencies)
    assert any(symbol.symbol_name == "runner" for symbol in symbols)
    assert any(reference.target_file == "demo/util.hy" for reference in references)
    assert any(reference.target_file == "demo/macros.hy" for reference in references)
    assert any(reference.target_names == ("helper",) for reference in references)


def test_hy_language_detection_supports_hy_without_overclaiming() -> None:
    assert ".hy" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("demo/main.hy"),
        text="(import os)\n(defn main [] 1)\n",
    ) == "hy"
    assert repository_service._language_for_path(
        Path("notes.hy"),
        text="plain notes without forms\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_hy_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hy-profile-repo"
    (repo_path / "demo").mkdir(parents=True)
    for index in range(8):
        (repo_path / "demo" / f"mod_{index}.hy").write_text(
            f"(import os)\n(defn fn-{index} [] {index})\n",
            encoding="utf-8",
        )
    (repo_path / "python").mkdir(parents=True)
    for index in range(2):
        (repo_path / "python" / f"host_{index}.py").write_text(
            "def main():\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "hy" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "hy"
    assert any(path.endswith(".hy") for path in seed_plan["candidate_file_paths"])


def test_operational_seed_plan_without_diagnostics_does_not_force_hy_first_in_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hy-mixed-host-repo"
    (repo_path / "hy_pkg").mkdir(parents=True)
    for index in range(6):
        (repo_path / "hy_pkg" / f"mod_{index}.hy").write_text(
            f"(import os)\n(defn fn-{index} [] {index})\n",
            encoding="utf-8",
        )
    (repo_path / "python_pkg").mkdir(parents=True)
    for index in range(20):
        (repo_path / "python_pkg" / f"host_{index}.py").write_text(
            "def main():\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "hy" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "hy"
    assert "python" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_hy_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "hy-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.hy").write_text(
        "(defn helper [] 1)\n"
        "(defn runner []\n"
        "  (helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.hy"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "main.hy" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
