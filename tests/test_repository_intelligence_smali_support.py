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
    repository_intelligence_smali_parser_dispatch as repository_intelligence_smali_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    smali_analysis_support as repository_smali_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    smali_primitives as repository_smali_primitives,
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


def test_repository_intelligence_smali_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["smali"] is (
        repository_intelligence_smali_parser_dispatch._parse_smali_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["smali"] is (
        repository_intelligence_smali_parser_dispatch._parse_smali_dependencies_only
    )


def test_repository_intelligence_smali_helpers_are_modularized() -> None:
    assert repository_service.smali_adapter.has_smali_path_hints is (
        repository_smali_primitives.has_smali_path_hints
    )
    assert repository_service.smali_adapter.is_probable_smali_source is (
        repository_smali_analysis_support.is_probable_smali_source
    )
    assert repository_service.smali_adapter.iter_dependency_entries is (
        repository_smali_primitives.iter_dependency_entries
    )
    assert repository_service.smali_adapter.module_aliases_for_path is (
        repository_smali_analysis_support.module_aliases_for_path
    )
    assert repository_service.smali_adapter.parse_file is repository_smali_analysis_support.parse_file


def test_smali_adapter_parse_file_extracts_descriptor_dependencies_and_references() -> None:
    module_index = {
        "com/example/Helper.smali": "com/example/Helper.smali",
    }
    text = (
        ".class public Lcom/example/Main;\n"
        ".super Ljava/lang/Object;\n"
        ".method public run()V\n"
        "    invoke-static {}, Lcom/example/Helper;->doWork()V\n"
        "    return-void\n"
        ".end method\n"
    )

    symbols, dependencies, references = repository_service.smali_adapter.parse_file(
        "com/example/Main.smali",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(dependency.dependency_type == "extends" for dependency in dependencies)
    assert any(reference.target_file == "com/example/Helper.smali" for reference in references)


def test_smali_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".smali" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("smali/com/example/Main.smali"),
            text=".class public Lcom/example/Main;\n.super Ljava/lang/Object;\n",
        )
        == "smali"
    )
    assert (
        repository_service._language_for_path(
            Path("smali/com/example/Main.smali"),
            text="plain notes without smali directives\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_smali_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "smali-profile-repo"
    smali_root = repo_path / "smali" / "com" / "example"
    smali_root.mkdir(parents=True)
    for index in range(6):
        (smali_root / f"Main{index}.smali").write_text(
            ".class public Lcom/example/Main{0};\n"
            ".super Ljava/lang/Object;\n"
            ".method public run()V\n"
            "    return-void\n"
            ".end method\n".format(index),
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

    assert "smali" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "smali"


def test_repository_snapshot_graph_contains_smali_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "smali-graph-repo"
    smali_root = repo_path / "com" / "example"
    smali_root.mkdir(parents=True)
    (smali_root / "Main.smali").write_text(
        ".class public Lcom/example/Main;\n"
        ".super Ljava/lang/Object;\n"
        ".method private helper()V\n"
        "    return-void\n"
        ".end method\n"
        ".method public run()V\n"
        "    invoke-direct {p0}, Lcom/example/Main;->helper()V\n"
        "    return-void\n"
        ".end method\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.smali"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "com/example/Main.smali" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
