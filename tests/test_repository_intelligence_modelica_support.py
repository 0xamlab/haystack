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
    repository_intelligence_modelica_parser_dispatch as repository_intelligence_modelica_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    modelica_analysis_support as repository_modelica_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    modelica_primitives as repository_modelica_primitives,
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


def test_repository_intelligence_modelica_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["modelica"] is (
        repository_intelligence_modelica_parser_dispatch._parse_modelica_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["modelica"] is (
        repository_intelligence_modelica_parser_dispatch._parse_modelica_dependencies_only
    )


def test_repository_intelligence_modelica_helpers_are_modularized() -> None:
    assert repository_service.modelica_adapter.has_modelica_path_hints is (
        repository_modelica_primitives.has_modelica_path_hints
    )
    assert repository_service.modelica_adapter.is_probable_modelica_source is (
        repository_modelica_analysis_support.is_probable_modelica_source
    )
    assert repository_service.modelica_adapter.iter_dependency_entries is (
        repository_modelica_primitives.iter_dependency_entries
    )
    assert repository_service.modelica_adapter.module_aliases_for_path is (
        repository_modelica_analysis_support.module_aliases_for_path
    )
    assert repository_service.modelica_adapter.parse_file is (
        repository_modelica_analysis_support.parse_file
    )


def test_modelica_adapter_module_aliases_include_package_forms(tmp_path: Path) -> None:
    repo_path = tmp_path / "modelica-alias-repo"
    (repo_path / "Modelica" / "Blocks").mkdir(parents=True)
    (repo_path / "Modelica" / "Blocks" / "package.mo").write_text(
        "within Modelica;\npackage Blocks\nend Blocks;\n",
        encoding="utf-8",
    )

    aliases = repository_service.modelica_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Modelica/Blocks/package.mo",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Modelica/Blocks/package.mo" in aliases
    assert "Modelica.Blocks" in aliases
    assert "Blocks" in aliases


def test_modelica_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = {
        "Demo.BaseModel": "Demo/BaseModel.mo",
        "Demo.Math": "Demo/Math/package.mo",
        "Math": "Demo/Math/package.mo",
        "Demo/Math/package.mo": "Demo/Math/package.mo",
    }
    text = (
        "within Demo;\n"
        "model Runner\n"
        "  import Math = Demo.Math;\n"
        "  extends BaseModel;\n"
        "equation\n"
        "  y = helper(x);\n"
        "  z = Math.sin(x);\n"
        "end Runner;\n\n"
        "function helper\n"
        "  input Real x;\n"
        "  output Real y;\n"
        "algorithm\n"
        "  y := x;\n"
        "end helper;\n"
    )

    symbols, dependencies, references = repository_service.modelica_adapter.parse_file(
        "Demo/Runner.mo",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "Demo/BaseModel.mo" for dependency in dependencies)
    assert any(dependency.target_file == "Demo/Math/package.mo" for dependency in dependencies)
    assert any(symbol.symbol_name == "helper" for symbol in symbols)
    assert any(reference.target_names == ("helper",) for reference in references)
    assert any(reference.target_file == "Demo/Math/package.mo" for reference in references)


def test_modelica_language_detection_supports_modelica_without_overclaiming() -> None:
    assert ".mo" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("Demo/Runner.mo"),
        text="within Demo;\nmodel Runner\nend Runner;\n",
    ) == "modelica"
    assert repository_service._language_for_path(
        Path("notes.mo"),
        text="plain notes without modelica structure\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_modelica_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "modelica-profile-repo"
    (repo_path / "Modelica" / "Blocks").mkdir(parents=True)
    for index in range(8):
        (repo_path / "Modelica" / "Blocks" / f"Model{index}.mo").write_text(
            f"within Modelica.Blocks;\nmodel Model{index}\n  Real y;\nend Model{index};\n",
            encoding="utf-8",
        )
    (repo_path / "src").mkdir(parents=True)
    for index in range(2):
        (repo_path / "src" / f"host_{index}.c").write_text(
            "int main(void) { return 0; }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "modelica" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "modelica"
    assert any(path.endswith(".mo") for path in seed_plan["candidate_file_paths"])


def test_operational_seed_plan_without_diagnostics_does_not_force_modelica_first_in_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "modelica-mixed-host-repo"
    (repo_path / "OMCompiler" / "Compiler").mkdir(parents=True)
    for index in range(6):
        (repo_path / "OMCompiler" / "Compiler" / f"Model{index}.mo").write_text(
            f"within Compiler;\nmodel Model{index}\n  Real y;\nend Model{index};\n",
            encoding="utf-8",
        )
    (repo_path / "OMCompiler" / "Compiler" / "C").mkdir(parents=True)
    for index in range(20):
        (repo_path / "OMCompiler" / "Compiler" / "C" / f"host_{index}.cpp").write_text(
            "int main() { return 0; }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "modelica" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "modelica"
    assert "cpp" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_modelica_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "modelica-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "Runner.mo").write_text(
        "model Runner\n"
        "equation\n"
        "  y = helper(x);\n"
        "end Runner;\n\n"
        "function helper\n"
        "  input Real x;\n"
        "  output Real y;\n"
        "algorithm\n"
        "  y := x;\n"
        "end helper;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.mo"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "Runner.mo" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
