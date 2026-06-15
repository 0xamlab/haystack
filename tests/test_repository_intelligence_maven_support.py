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
    repository_intelligence_maven_parser_dispatch as repository_intelligence_maven_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    maven_analysis_support as repository_maven_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    maven_primitives as repository_maven_primitives,
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


def test_repository_intelligence_maven_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["maven"] is (
        repository_intelligence_maven_parser_dispatch._parse_maven_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["maven"] is (
        repository_intelligence_maven_parser_dispatch._parse_maven_dependencies_only
    )


def test_repository_intelligence_maven_helpers_are_modularized() -> None:
    assert repository_service.maven_adapter.strip_comments is (
        repository_maven_primitives.strip_comments
    )
    assert repository_service.maven_adapter.has_maven_path_hints is (
        repository_maven_primitives.has_maven_path_hints
    )
    assert repository_service.maven_adapter.parse_maven_pom is (
        repository_maven_analysis_support.parse_maven_pom
    )
    assert repository_service.maven_adapter.resolve_project_path is (
        repository_maven_analysis_support.resolve_project_path
    )
    assert repository_service.maven_adapter.is_probable_maven_source is (
        repository_maven_analysis_support.is_probable_maven_source
    )
    assert repository_service.maven_adapter.module_aliases_for_path is (
        repository_maven_analysis_support.module_aliases_for_path
    )
    assert repository_service.maven_adapter.parse_dependencies_only is (
        repository_maven_analysis_support.parse_dependencies_only
    )
    assert repository_service.maven_adapter.parse_file is (
        repository_maven_analysis_support.parse_file
    )


def test_maven_adapter_parse_file_extracts_module_parent_and_dependency_edges() -> None:
    module_index = repository_service._build_module_index(
        ["pom.xml", "core/pom.xml"],
        root_path=Path("/tmp/maven-index"),
    )
    root_pom = (
        "<project>\n"
        "  <modelVersion>4.0.0</modelVersion>\n"
        "  <groupId>com.example</groupId>\n"
        "  <artifactId>demo-parent</artifactId>\n"
        "  <modules><module>core</module></modules>\n"
        "  <dependencies>\n"
        "    <dependency><groupId>org.slf4j</groupId><artifactId>slf4j-api</artifactId></dependency>\n"
        "  </dependencies>\n"
        "</project>\n"
    )
    child_pom = (
        "<project>\n"
        "  <modelVersion>4.0.0</modelVersion>\n"
        "  <parent><relativePath>../pom.xml</relativePath></parent>\n"
        "  <artifactId>core</artifactId>\n"
        "</project>\n"
    )

    root_symbols, root_dependencies, root_references = repository_service.maven_adapter.parse_file(
        "pom.xml",
        root_pom,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    _child_symbols, child_dependencies, _child_references = repository_service.maven_adapter.parse_file(
        "core/pom.xml",
        child_pom,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "demo-parent" for symbol in root_symbols)
    assert any(
        dependency.dependency_type == "module" and dependency.target_file == "core/pom.xml"
        for dependency in root_dependencies
    )
    assert any(
        dependency.dependency_type == "dependency"
        and dependency.target_symbol == "org.slf4j:slf4j-api"
        for dependency in root_dependencies
    )
    assert any(
        dependency.dependency_type == "parent" and dependency.target_file == "pom.xml"
        for dependency in child_dependencies
    )
    assert root_references == ()


def test_maven_language_detection_supports_pom_and_maven_config_without_overclaiming() -> None:
    assert repository_service._language_for_path(
        Path("pom.xml"),
        text="<project><modelVersion>4.0.0</modelVersion><artifactId>demo</artifactId></project>\n",
    ) == "maven"
    assert repository_service._language_for_path(
        Path(".mvn/maven.config"),
        text="--batch-mode\n-DskipTests=true\n",
    ) == "maven"
    assert (
        repository_service._language_for_path(
            Path("pom.xml"),
            text="<project />\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_maven_when_config_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "maven-profile-repo"
    (repo_path / ".mvn").mkdir(parents=True)
    (repo_path / "pom.xml").write_text(
        "<project>\n"
        "  <modelVersion>4.0.0</modelVersion>\n"
        "  <groupId>org.example</groupId>\n"
        "  <artifactId>demo-parent</artifactId>\n"
        "  <modules><module>core</module></modules>\n"
        "</project>\n",
        encoding="utf-8",
    )
    (repo_path / ".mvn" / "maven.config").write_text(
        "--batch-mode\n-DskipTests=true\n",
        encoding="utf-8",
    )
    (repo_path / "README.md").write_text("# demo\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["pom.xml", ".mvn"],
        max_files=64,
    )

    assert "maven" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "maven"
    assert "pom.xml" in seed_plan["config_paths"]


def test_repository_snapshot_graph_contains_maven_module_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "maven-graph-repo"
    (repo_path / "core").mkdir(parents=True)
    (repo_path / "pom.xml").write_text(
        "<project>\n"
        "  <modelVersion>4.0.0</modelVersion>\n"
        "  <groupId>com.example</groupId>\n"
        "  <artifactId>demo-parent</artifactId>\n"
        "  <modules><module>core</module></modules>\n"
        "</project>\n",
        encoding="utf-8",
    )
    (repo_path / "core" / "pom.xml").write_text(
        "<project>\n"
        "  <modelVersion>4.0.0</modelVersion>\n"
        "  <parent><relativePath>../pom.xml</relativePath></parent>\n"
        "  <artifactId>core</artifactId>\n"
        "</project>\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/pom.xml", "pom.xml"],
            max_files=16,
        ),
    )
    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "module"
        and str(row["source_node"]) == "file:pom.xml"
        and str(row["target_node"]) == "file:core/pom.xml"
        for row in graph_rows
    )
