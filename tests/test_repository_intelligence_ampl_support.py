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
    repository_intelligence_ampl_parser_dispatch as repository_intelligence_ampl_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    ampl_analysis_support as repository_ampl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ampl_primitives as repository_ampl_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _candidate_ecosystems_for_path,
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


def test_repository_intelligence_ampl_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["ampl"] is (
        repository_intelligence_ampl_parser_dispatch._parse_ampl_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["ampl"] is (
        repository_intelligence_ampl_parser_dispatch._parse_ampl_dependencies_only
    )


def test_repository_intelligence_ampl_helpers_are_modularized() -> None:
    assert repository_service.ampl_adapter.has_ampl_path_hints is (
        repository_ampl_primitives.has_ampl_path_hints
    )
    assert repository_service.ampl_adapter.is_probable_ampl_source is (
        repository_ampl_analysis_support.is_probable_ampl_source
    )
    assert repository_service.ampl_adapter.module_aliases_for_path is (
        repository_ampl_analysis_support.module_aliases_for_path
    )
    assert repository_service.ampl_adapter.parse_dependencies_only is (
        repository_ampl_analysis_support.parse_dependencies_only
    )
    assert repository_service.ampl_adapter.parse_file is repository_ampl_analysis_support.parse_file


def test_ampl_adapter_parse_file_extracts_model_dependencies_and_references() -> None:
    module_index = {
        "models/prod.mod": "models/prod.mod",
        "scripts/helpers.run": "scripts/helpers.run",
    }
    script_text = (
        "model models/prod.mod;\n"
        "include scripts/helpers.run;\n"
        "display Profit;\n"
    )

    symbols, dependencies, references = repository_service.ampl_adapter.parse_file(
        "scripts/main.run",
        script_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert not symbols[1:]
    assert any(dependency.target_file == "models/prod.mod" for dependency in dependencies)
    assert any(dependency.target_file == "scripts/helpers.run" for dependency in dependencies)
    assert any(reference.target_file == "models/prod.mod" for reference in references)


def test_ampl_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".ampl" in repository_service._TEXT_FILE_SUFFIXES
    assert ".mod" in repository_service._TEXT_FILE_SUFFIXES
    assert ".run" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("models/common.ampl"),
            text="param demand;\nvar Make >= 0;\nmaximize Profit: 2 * Make;\n",
        )
        == "ampl"
    )
    assert (
        repository_service._language_for_path(
            Path("models/prod.mod"),
            text="param demand;\nvar Make >= 0;\nmaximize Profit: 2 * Make;\n",
        )
        == "ampl"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/main.run"),
            text="model models/prod.mod;\nsolve;\ndisplay Profit;\n",
        )
        == "ampl"
    )
    assert (
        repository_service._language_for_path(
            Path("notes/readme.mod"),
            text="plain notes only\n",
        )
        == "unknown"
    )


def test_real_repo_probe_candidate_ecosystems_detect_ampl_sources(tmp_path: Path) -> None:
    repo_path = tmp_path / "ampl-candidate-ecosystem-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "models" / "common.ampl").write_text(
        "param demand;\nvar Make >= 0;\nmaximize Profit: 2 * Make;\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "prod.mod").write_text(
        "param demand;\nvar Make >= 0;\nmaximize Profit: 2 * Make;\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.run").write_text(
        "model ../models/prod.mod;\nsolve;\ndisplay Profit;\n",
        encoding="utf-8",
    )

    assert "ampl" in _candidate_ecosystems_for_path("models/common.ampl", repo_path=repo_path)
    assert "ampl" in _candidate_ecosystems_for_path("models/prod.mod", repo_path=repo_path)
    assert "ampl" in _candidate_ecosystems_for_path("scripts/main.run", repo_path=repo_path)


def test_operational_seed_plan_without_diagnostics_promotes_ampl_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ampl-profile-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(5):
        (repo_path / "models" / f"prod_{index}.mod").write_text(
            f"param demand_{index};\nvar Make_{index} >= 0;\nmaximize Profit_{index}: 2 * Make_{index};\n",
            encoding="utf-8",
        )
    for index in range(2):
        (repo_path / "scripts" / f"main_{index}.run").write_text(
            f"model ../models/prod_{index}.mod;\nsolve;\ndisplay Profit_{index};\n",
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

    assert "ampl" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "ampl"


def test_repository_snapshot_graph_contains_ampl_dependency_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "ampl-graph-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "models" / "prod.mod").write_text(
        "param demand;\nvar Make >= 0;\nmaximize Profit: 2 * Make;\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.run").write_text(
        "model ../models/prod.mod;\nsolve;\ndisplay Profit;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.mod", "*.run"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    prod_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "models/prod.mod" and str(row["symbol_name"]) == "prod"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{prod_symbol_id}"
        for row in graph
    )
