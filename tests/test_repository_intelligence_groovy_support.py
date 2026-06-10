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
    repository_intelligence_groovy_parser_dispatch as repository_groovy_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    groovy_analysis_support as repository_groovy_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    groovy_primitives as repository_groovy_primitives,
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


def test_repository_intelligence_groovy_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["groovy"] is (
        repository_groovy_parser_dispatch._parse_groovy_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["groovy"] is (
        repository_groovy_parser_dispatch._parse_groovy_dependencies_only
    )


def test_repository_intelligence_groovy_helpers_are_modularized() -> None:
    assert repository_service.groovy_adapter.has_groovy_path_hints is (
        repository_groovy_primitives.has_groovy_path_hints
    )
    assert repository_service.groovy_adapter.is_probable_groovy_source is (
        repository_groovy_analysis_support.is_probable_groovy_source
    )
    assert repository_service.groovy_adapter.module_aliases_for_path is (
        repository_groovy_analysis_support.module_aliases_for_path
    )
    assert repository_service.groovy_adapter.parse_dependencies_only is (
        repository_groovy_analysis_support.parse_dependencies_only
    )
    assert repository_service.groovy_adapter.parse_file is (
        repository_groovy_analysis_support.parse_file
    )


def test_groovy_language_detection_supports_gradle_and_sources_without_overclaiming() -> None:
    assert ".groovy" in repository_service._TEXT_FILE_SUFFIXES
    assert ".gradle" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("build.gradle"),
            text="plugins { id 'groovy' }\nrepositories { mavenCentral() }\n",
        )
        == "groovy"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main/groovy/org/example/Main.groovy"),
            text="package org.example\nclass Main {}\n",
        )
        == "groovy"
    )
    assert (
        repository_service._language_for_path(
            Path("notes.gradle"),
            text="plain notes only\n",
        )
        == "unknown"
    )


def test_groovy_adapter_parse_file_extracts_import_dependencies_and_references() -> None:
    module_index = {
        "src/main/groovy/org/example/Owner.groovy": "src/main/groovy/org/example/Owner.groovy",
        "src/main/groovy/org/example/OwnerController.groovy": (
            "src/main/groovy/org/example/OwnerController.groovy"
        ),
        "org.example.Owner": "src/main/groovy/org/example/Owner.groovy",
        "Owner": "src/main/groovy/org/example/Owner.groovy",
        "org.example.OwnerController": "src/main/groovy/org/example/OwnerController.groovy",
        "OwnerController": "src/main/groovy/org/example/OwnerController.groovy",
    }
    controller_text = (
        "package org.example\n"
        "import org.example.Owner as PetOwner\n"
        "class OwnerController {\n"
        "  PetOwner owner\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.groovy_adapter.parse_file(
        "src/main/groovy/org/example/OwnerController.groovy",
        controller_text,
        module_index,
        collect_type_symbol_entries=repository_service._collect_type_symbol_entries,
        stable_identifier=repository_service._stable_identifier,
        resolve_import=repository_service._resolve_jvm_import,
    )

    assert any(
        dependency.target_file == "src/main/groovy/org/example/Owner.groovy"
        and dependency.target_symbol == "Owner"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "OwnerController" for symbol in symbols)
    assert any(
        reference.target_file == "src/main/groovy/org/example/Owner.groovy"
        and reference.target_names == ("Owner",)
        for reference in references
    )


def test_operational_seed_plan_without_diagnostics_promotes_groovy_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "groovy-profile-repo"
    (repo_path / "src" / "main" / "groovy" / "org" / "example").mkdir(parents=True)
    (repo_path / "build.gradle").write_text(
        "plugins { id 'groovy' }\nrepositories { mavenCentral() }\n",
        encoding="utf-8",
    )
    for index in range(6):
        groovy_path = repo_path / "src" / "main" / "groovy" / "org" / "example" / f"Main{index}.groovy"
        groovy_path.write_text(
            f"package org.example\nclass Main{index} {{}}\n",
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

    assert "groovy" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "groovy"
    assert "build.gradle" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_does_not_force_groovy_first_in_java_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "groovy-mixed-host-repo"
    (repo_path / "src" / "main" / "groovy" / "org" / "example").mkdir(parents=True)
    (repo_path / "src" / "main" / "java" / "org" / "example").mkdir(parents=True)
    (repo_path / "build.gradle").write_text(
        "plugins { id 'groovy' id 'java' }\nrepositories { mavenCentral() }\n",
        encoding="utf-8",
    )
    for index in range(3):
        groovy_path = repo_path / "src" / "main" / "groovy" / "org" / "example" / f"Helper{index}.groovy"
        groovy_path.write_text(
            f"package org.example\nclass Helper{index} {{}}\n",
            encoding="utf-8",
        )
    for index in range(12):
        java_path = repo_path / "src" / "main" / "java" / "org" / "example" / f"Host{index}.java"
        java_path.write_text(
            f"package org.example; public class Host{index} {{}}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "groovy" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "groovy"


def test_repository_snapshot_graph_contains_groovy_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "groovy-graph-repo"
    source_dir = repo_path / "src" / "main" / "groovy" / "org" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "Owner.groovy").write_text(
        "package org.example\n"
        "class Owner {}\n",
        encoding="utf-8",
    )
    (source_dir / "OwnerController.groovy").write_text(
        "package org.example\n"
        "import org.example.Owner as PetOwner\n"
        "class OwnerController {\n"
        "  PetOwner owner\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/groovy"],
            include_patterns=["src/main/groovy/**/*.groovy"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbols_table = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    owner_symbol_ids = {
        row["symbol_id"] for row in symbols_table if row["symbol_name"] == "Owner"
    }
    assert owner_symbol_ids
    target_nodes = {f"symbol:{symbol_id}" for symbol_id in owner_symbol_ids}
    assert any(
        row["edge_type"] == "references_symbol"
        and row["target_node"] in target_nodes
        and row["source_node"].startswith("symbol:")
        for row in graph
    )
