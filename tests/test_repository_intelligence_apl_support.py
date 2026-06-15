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
    repository_intelligence_apl_parser_dispatch as repository_intelligence_apl_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    apl_analysis_support as repository_apl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    apl_primitives as repository_apl_primitives,
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


def test_repository_intelligence_apl_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["apl"] is (
        repository_intelligence_apl_parser_dispatch._parse_apl_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["apl"] is (
        repository_intelligence_apl_parser_dispatch._parse_apl_dependencies_only
    )


def test_repository_intelligence_apl_helpers_are_modularized() -> None:
    assert repository_service.apl_adapter.has_apl_path_hints is (
        repository_apl_primitives.has_apl_path_hints
    )
    assert repository_service.apl_adapter.is_probable_apl_source is (
        repository_apl_analysis_support.is_probable_apl_source
    )
    assert repository_service.apl_adapter.iter_reference_entries is (
        repository_apl_primitives.iter_reference_entries
    )
    assert repository_service.apl_adapter.module_aliases_for_path is (
        repository_apl_analysis_support.module_aliases_for_path
    )
    assert repository_service.apl_adapter.parse_file is (
        repository_apl_analysis_support.parse_file
    )


def test_apl_adapter_parse_file_extracts_local_symbol_references() -> None:
    text = "helper←{1}\nrun←{helper ⍵}\n"

    symbols, dependencies, references = repository_service.apl_adapter.parse_file(
        "main.apl",
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert dependencies == ()
    assert any(symbol.symbol_name == "helper" for symbol in symbols)
    assert any(reference.target_names == ("helper",) for reference in references)


def test_apl_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".apl" in repository_service._TEXT_FILE_SUFFIXES
    assert ".aplf" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("tools/buildgui/ImportMethodsAndEvents.aplf"),
            text="eventfiles←(d.GetFiles(⊂'* MethodOrEvent.htm')).Name\n:For event :In eventnames\n",
        )
        == "apl"
    )
    assert (
        repository_service._language_for_path(
            Path("docs/example.apl"),
            text="plain notes without apl operators\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_apl_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "apl-profile-repo"
    (repo_path / "tools" / "buildgui").mkdir(parents=True)
    for index in range(6):
        (repo_path / "tools" / "buildgui" / f"script_{index}.aplf").write_text(
            f"helper{index}←{{{index}}}\nrun{index}←{{helper{index} ⍵}}\n",
            encoding="utf-8",
        )
    (repo_path / "tools" / "helpers").mkdir(parents=True)
    for index in range(2):
        (repo_path / "tools" / "helpers" / f"helper_{index}.py").write_text(
            "print('helper')\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "apl" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "apl"


def test_repository_snapshot_graph_contains_apl_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "apl-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.apl").write_text(
        "helper←{1}\n"
        "run←{helper ⍵}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.apl", "*.aplf", "*.dyalog"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "main.apl" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
