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
    repository_intelligence_m4_parser_dispatch as repository_intelligence_m4_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    m4_analysis_support as repository_m4_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    m4_primitives as repository_m4_primitives,
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


def test_repository_intelligence_m4_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["m4"] is (
        repository_intelligence_m4_parser_dispatch._parse_m4_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["m4"] is (
        repository_intelligence_m4_parser_dispatch._parse_m4_dependencies_only
    )


def test_repository_intelligence_m4_helpers_are_modularized() -> None:
    assert repository_service.m4_adapter.has_m4_path_hints is (
        repository_m4_primitives.has_m4_path_hints
    )
    assert repository_service.m4_adapter.is_probable_m4_source is (
        repository_m4_analysis_support.is_probable_m4_source
    )
    assert repository_service.m4_adapter.iter_dependency_entries is (
        repository_m4_primitives.iter_dependency_entries
    )
    assert repository_service.m4_adapter.module_aliases_for_path is (
        repository_m4_analysis_support.module_aliases_for_path
    )
    assert repository_service.m4_adapter.parse_file is repository_m4_analysis_support.parse_file


def test_m4_adapter_parse_file_extracts_include_dependencies_and_references() -> None:
    module_index = {
        "lib/helpers.m4": "lib/helpers.m4",
        "helpers.m4": "lib/helpers.m4",
    }
    text = (
        "m4_include([lib/helpers.m4])\n"
        "AC_DEFUN([AX_RUN], [AX_HELPER])\n"
        "AC_DEFUN([AX_USE], [AX_RUN])\n"
    )

    symbols, dependencies, references = repository_service.m4_adapter.parse_file(
        "macros/main.m4",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "lib/helpers.m4" for dependency in dependencies)
    assert any(symbol.symbol_name == "AX_RUN" for symbol in symbols)
    assert any(reference.target_names == ("AX_RUN",) for reference in references)


def test_m4_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".m4" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("lib/autoconf/autoconf.m4"),
            text="AC_DEFUN([AX_RUN], [AC_INIT([demo], [1.0])])\n",
        )
        == "m4"
    )
    assert (
        repository_service._language_for_path(
            Path("lib/autoconf/autoconf.m4"),
            text="plain notes without m4 macros\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_m4_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "m4-profile-repo"
    (repo_path / "lib" / "autoconf").mkdir(parents=True)
    for index in range(6):
        (repo_path / "lib" / "autoconf" / f"macro_{index}.m4").write_text(
            f"AC_DEFUN([AX_MACRO_{index}], [AC_INIT([demo], [1.0])])\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    for index in range(2):
        (repo_path / "tools" / f"helper_{index}.py").write_text("print('helper')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "m4" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "m4"


def test_repository_snapshot_graph_contains_m4_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "m4-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.m4").write_text(
        "AC_DEFUN([AX_RUN], [AC_INIT([demo], [1.0])])\n"
        "AC_DEFUN([AX_USE], [AX_RUN])\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.m4"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    target_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "main.m4" and str(row["symbol_name"]) == "AX_RUN"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{target_symbol_id}"
        for row in graph
    )
