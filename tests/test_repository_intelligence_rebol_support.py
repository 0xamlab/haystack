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
    repository_intelligence_rebol_parser_dispatch as repository_rebol_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    rebol_analysis_support as repository_rebol_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    rebol_primitives as repository_rebol_primitives,
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


def test_repository_intelligence_rebol_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["rebol"] is (
        repository_rebol_parser_dispatch._parse_rebol_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["rebol"] is (
        repository_rebol_parser_dispatch._parse_rebol_dependencies_only
    )


def test_repository_intelligence_rebol_helpers_are_modularized() -> None:
    assert repository_service.rebol_adapter.has_rebol_path_hints is (
        repository_rebol_primitives.has_rebol_path_hints
    )
    assert repository_service.rebol_adapter.is_probable_rebol_source is (
        repository_rebol_analysis_support.is_probable_rebol_source
    )
    assert repository_service.rebol_adapter.iter_dependency_entries is (
        repository_rebol_primitives.iter_dependency_entries
    )
    assert repository_service.rebol_adapter.resolve_import_module is (
        repository_rebol_analysis_support.resolve_import_module
    )
    assert repository_service.rebol_adapter.parse_file is (
        repository_rebol_analysis_support.parse_file
    )


def test_rebol_adapter_parse_file_extracts_needs_and_symbol_references() -> None:
    text = "REBOL [\n    Needs: [helper]\n]\nrun: func [] [helper]\n"

    symbols, dependencies, references = repository_service.rebol_adapter.parse_file(
        "main.reb",
        text,
        {"helper": "lib/helper.reb", "lib/helper.reb": "lib/helper.reb"},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "lib/helper.reb" and dependency.target_symbol == "helper"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "lib/helper.reb" and reference.target_names == ("helper",)
        for reference in references
    )


def test_rebol_adapter_parse_file_reuses_stripped_text(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "REBOL [\n    Needs: [helper]\n]\nrun: func [] [helper]\n"
    strip_count = {"value": 0}
    original_strip_comments = repository_rebol_primitives.strip_comments

    def _counting_strip_comments(value: str) -> str:
        strip_count["value"] += 1
        return original_strip_comments(value)

    monkeypatch.setattr(repository_rebol_primitives, "strip_comments", _counting_strip_comments)
    monkeypatch.setattr(repository_rebol_analysis_support, "strip_comments", _counting_strip_comments)

    repository_service.rebol_adapter.parse_file(
        "main.reb",
        text,
        {"helper": "lib/helper.reb", "lib/helper.reb": "lib/helper.reb"},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_count["value"] == 1


def test_rebol_language_detection_supports_r_suffix_without_overclaiming() -> None:
    assert ".reb" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("scripts/index.reb"),
            text="Rebol []\nhelper: do %lib/helper.reb\n",
        )
        == "rebol"
    )
    assert (
        repository_service._language_for_path(
            Path("protocols/prot-http.r"),
            text="REBOL [\n    Name: 'http\n]\nhttp-awake: func [event] [event]\n",
        )
        == "rebol"
    )
    assert (
        repository_service._language_for_path(
            Path("analysis/model.r"),
            text="x <- 1\nprint(x)\n",
        )
        == "r"
    )


def test_operational_seed_plan_without_diagnostics_promotes_rebol_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rebol-profile-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    for index in range(6):
        (repo_path / f"script_{index}.reb").write_text(
            "REBOL [\n    Needs: [helper]\n]\nrun: func [] [helper]\n",
            encoding="utf-8",
        )
    (repo_path / "lib" / "helper.reb").write_text(
        "REBOL []\nhelper: func [] [1]\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "print('helper')\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "rebol" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "rebol"


def test_repository_snapshot_graph_contains_rebol_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "rebol-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.reb").write_text(
        "REBOL []\n"
        "helper: func [] [1]\n"
        "run: func [] [helper]\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.reb"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "main.reb" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
