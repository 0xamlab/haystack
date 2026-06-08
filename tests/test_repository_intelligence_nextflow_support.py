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
    repository_intelligence_nextflow_parser_dispatch as repository_intelligence_nextflow_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    nextflow_analysis_support as repository_nextflow_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    nextflow_primitives as repository_nextflow_primitives,
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


def test_repository_intelligence_nextflow_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["nextflow"] is (
        repository_intelligence_nextflow_parser_dispatch._parse_nextflow_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["nextflow"] is (
        repository_intelligence_nextflow_parser_dispatch._parse_nextflow_dependencies_only
    )


def test_repository_intelligence_nextflow_helpers_are_modularized() -> None:
    assert repository_service.nextflow_adapter.has_nextflow_path_hints is (
        repository_nextflow_primitives.has_nextflow_path_hints
    )
    assert repository_service.nextflow_adapter.is_probable_nextflow_source is (
        repository_nextflow_analysis_support.is_probable_nextflow_source
    )
    assert repository_service.nextflow_adapter.parse_include_entries is (
        repository_nextflow_primitives.parse_include_entries
    )
    assert repository_service.nextflow_adapter.module_aliases_for_path is (
        repository_nextflow_analysis_support.module_aliases_for_path
    )
    assert repository_service.nextflow_adapter.parse_file is (
        repository_nextflow_analysis_support.parse_file
    )


def test_nextflow_adapter_module_aliases_include_process_and_workflow_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "nextflow-alias-repo"
    (repo_path / "modules" / "qc" / "fastqc").mkdir(parents=True)
    (repo_path / "modules" / "qc" / "fastqc" / "main.nf").write_text(
        "nextflow.enable.dsl=2\n"
        "process FASTQC {\n"
        "  script:\n"
        "  '''\n"
        "  fastqc --help\n"
        "  '''\n"
        "}\n"
        "workflow FASTQC_FLOW {\n"
        "  FASTQC()\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.nextflow_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/qc/fastqc/main.nf",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "modules/qc/fastqc/main.nf" in aliases
    assert "modules/qc/fastqc/main" in aliases
    assert "qc/fastqc" in aliases
    assert "FASTQC" in aliases
    assert "FASTQC_FLOW" in aliases


def test_nextflow_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = {
        "modules/qc/fastqc/main.nf": "modules/qc/fastqc/main.nf",
        "modules/qc/fastqc": "modules/qc/fastqc/main.nf",
        "conf/base.config": "conf/base.config",
    }
    text = (
        "nextflow.enable.dsl=2\n"
        "include { FASTQC as QC } from './modules/qc/fastqc'\n"
        "includeConfig './conf/base'\n"
        "process ALIGN {\n"
        "  script:\n"
        "  '''\n"
        "  echo align\n"
        "  '''\n"
        "}\n"
        "workflow MAIN {\n"
        "  QC()\n"
        "  ALIGN()\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.nextflow_adapter.parse_file(
        "main.nf",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "modules/qc/fastqc/main.nf" for dependency in dependencies)
    assert any(dependency.target_file == "conf/base.config" for dependency in dependencies)
    assert any(symbol.symbol_name == "ALIGN" for symbol in symbols)
    assert any(symbol.symbol_name == "MAIN" for symbol in symbols)
    assert any(reference.target_file == "modules/qc/fastqc/main.nf" for reference in references)
    assert any(reference.target_file == "main.nf" for reference in references)


def test_nextflow_language_detection_supports_nextflow_without_overclaiming() -> None:
    assert ".nf" in repository_service._TEXT_FILE_SUFFIXES
    assert "nextflow.config" in repository_service._TEXT_FILE_BASENAMES
    assert repository_service._language_for_path(
        Path("main.nf"),
        text="nextflow.enable.dsl=2\nworkflow MAIN { FASTQC() }\n",
    ) == "nextflow"
    assert repository_service._language_for_path(
        Path("nextflow.config"),
        text="profiles { standard { process.executor = 'local' } }\n",
    ) == "nextflow"
    assert repository_service._language_for_path(
        Path("notes.nf"),
        text="plain notes without workflow markers\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_nextflow_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nextflow-profile-repo"
    (repo_path / "modules" / "qc" / "fastqc").mkdir(parents=True)
    (repo_path / "nextflow.config").write_text(
        "nextflow.enable.dsl=2\nprofiles { standard { process.executor = 'local' } }\n",
        encoding="utf-8",
    )
    (repo_path / "main.nf").write_text(
        "nextflow.enable.dsl=2\ninclude { FASTQC } from './modules/qc/fastqc'\nworkflow MAIN { FASTQC() }\n",
        encoding="utf-8",
    )
    for index in range(5):
        (repo_path / "modules" / "qc" / "fastqc" / f"step_{index}.nf").write_text(
            f"process STEP_{index} {{\n  script:\n  '''\n  echo {index}\n  '''\n}}\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "def main():\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "nextflow" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "nextflow"
    assert "nextflow.config" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_does_not_force_nextflow_first_in_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nextflow-mixed-host-repo"
    (repo_path / "pipeline").mkdir(parents=True)
    (repo_path / "pipeline" / "main.nf").write_text(
        "nextflow.enable.dsl=2\nworkflow MAIN { ALIGN() }\n",
        encoding="utf-8",
    )
    for index in range(6):
        (repo_path / "pipeline" / f"module_{index}.nf").write_text(
            f"process STEP_{index} {{\n  script:\n  '''\n  echo {index}\n  '''\n}}\n",
            encoding="utf-8",
        )
    (repo_path / "src").mkdir(parents=True)
    for index in range(28):
        (repo_path / "src" / f"host_{index}.groovy").write_text(
            "class Host { static void main(String[] args) {} }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "nextflow" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "nextflow"
    assert "groovy" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_nextflow_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "nextflow-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.nf").write_text(
        "nextflow.enable.dsl=2\n"
        "process FASTQC {\n"
        "  script:\n"
        "  '''\n"
        "  fastqc --help\n"
        "  '''\n"
        "}\n"
        "workflow MAIN {\n"
        "  FASTQC()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.nf", "nextflow.config"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    process_ids = {
        row["symbol_id"]
        for row in symbol_rows
        if row["symbol_name"] == "FASTQC" and row["file_path"] == "main.nf"
    }
    assert process_ids
    process_nodes = {f"symbol:{symbol_id}" for symbol_id in process_ids}
    assert any(
        row["edge_type"] == "references_symbol"
        and row["target_node"] in process_nodes
        and row["source_node"].startswith("symbol:")
        for row in graph
    )
