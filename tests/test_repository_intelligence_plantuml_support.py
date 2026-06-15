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
    repository_intelligence_plantuml_parser_dispatch as repository_plantuml_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    plantuml_analysis_support as repository_plantuml_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    plantuml_primitives as repository_plantuml_primitives,
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


def test_repository_intelligence_plantuml_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["plantuml"] is (
        repository_plantuml_parser_dispatch._parse_plantuml_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["plantuml"] is (
        repository_plantuml_parser_dispatch._parse_plantuml_dependencies_only
    )


def test_repository_intelligence_plantuml_helpers_are_modularized() -> None:
    assert repository_service.plantuml_adapter.has_plantuml_path_hints is (
        repository_plantuml_primitives.has_plantuml_path_hints
    )
    assert repository_service.plantuml_adapter.is_probable_plantuml_source is (
        repository_plantuml_analysis_support.is_probable_plantuml_source
    )
    assert repository_service.plantuml_adapter.iter_dependency_entries is (
        repository_plantuml_primitives.iter_dependency_entries
    )
    assert repository_service.plantuml_adapter.module_aliases_for_path is (
        repository_plantuml_analysis_support.module_aliases_for_path
    )
    assert repository_service.plantuml_adapter.parse_file is (
        repository_plantuml_analysis_support.parse_file
    )


def test_plantuml_adapter_module_aliases_include_path_stem(tmp_path: Path) -> None:
    repo_path = tmp_path / "plantuml-alias-repo"
    (repo_path / "diagrams").mkdir(parents=True)
    (repo_path / "diagrams" / "system.puml").write_text(
        "@startuml\nactor User as USER\n@enduml\n",
        encoding="utf-8",
    )

    aliases = repository_service.plantuml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="diagrams/system.puml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "diagrams/system.puml" in aliases
    assert "system" in aliases
    assert "diagrams.system" in aliases


def test_plantuml_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = {
        "common.puml": "diagrams/common.puml",
        "diagrams/common.puml": "diagrams/common.puml",
    }
    text = (
        "!include common.puml\n"
        "@startuml\n"
        "actor api as API\n"
        "database db as DB\n"
        "API --> DB\n"
        "@enduml\n"
    )

    symbols, dependencies, references = repository_service.plantuml_adapter.parse_file(
        "diagrams/flow.puml",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "diagrams/common.puml" for dependency in dependencies)
    assert any(symbol.symbol_name == "API" for symbol in symbols)
    assert any(symbol.symbol_name == "DB" for symbol in symbols)
    assert any(reference.target_names == ("DB",) for reference in references)


def test_plantuml_parse_file_reuses_stripped_text(monkeypatch: pytest.MonkeyPatch) -> None:
    module_index = {
        "common.puml": "diagrams/common.puml",
        "diagrams/common.puml": "diagrams/common.puml",
    }
    text = (
        "' comment\\n"
        "!include common.puml\\n"
        "@startuml\\n"
        "actor api as API\\n"
        "database db as DB\\n"
        "API --> DB\\n"
        "@enduml\\n"
    )
    original_strip_comments = repository_plantuml_primitives.strip_comments
    strip_comment_calls = 0

    def counting_strip_comments(value: str) -> str:
        nonlocal strip_comment_calls
        strip_comment_calls += 1
        return original_strip_comments(value)

    monkeypatch.setattr(
        repository_plantuml_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_plantuml_primitives,
        "strip_comments",
        counting_strip_comments,
    )

    repository_service.plantuml_adapter.parse_file(
        "diagrams/flow.puml",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_comment_calls == 1


def test_plantuml_language_detection_supports_puml_without_overclaiming() -> None:
    assert ".puml" in repository_service._TEXT_FILE_SUFFIXES
    assert ".plantuml" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("diagrams/system.puml"),
        text="@startuml\nactor User as USER\n@enduml\n",
    ) == "plantuml"
    assert repository_service._language_for_path(
        Path("diagrams/plain.puml"),
        text="plain notes without plantuml syntax\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_plantuml_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "plantuml-profile-repo"
    (repo_path / "diagrams").mkdir(parents=True)
    for index in range(6):
        (repo_path / "diagrams" / f"flow_{index}.puml").write_text(
            "@startuml\n"
            f"actor user_{index} as U{index}\n"
            f"component service_{index} as S{index}\n"
            f"U{index} --> S{index}\n"
            "@enduml\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "tools" / "helper.py").write_text("print('plantuml')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "plantuml" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "plantuml"
    assert any(path.endswith(".puml") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_does_not_force_plantuml_first_in_java_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "plantuml-mixed-java-repo"
    (repo_path / "diagrams").mkdir(parents=True)
    for index in range(4):
        (repo_path / "diagrams" / f"flow_{index}.puml").write_text(
            "@startuml\n"
            f"actor user_{index} as U{index}\n"
            f"component service_{index} as S{index}\n"
            f"U{index} --> S{index}\n"
            "@enduml\n",
            encoding="utf-8",
        )
    (repo_path / "src" / "main" / "java" / "app").mkdir(parents=True)
    for index in range(10):
        (repo_path / "src" / "main" / "java" / "app" / f"Service{index}.java").write_text(
            f"package app;\npublic class Service{index} {{}}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "plantuml" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "plantuml"
    assert "java" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_plantuml_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "plantuml-graph-repo"
    (repo_path / "diagrams").mkdir(parents=True)
    (repo_path / "diagrams" / "flow.puml").write_text(
        "@startuml\n"
        "actor api as API\n"
        "database db as DB\n"
        "API --> DB\n"
        "@enduml\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["diagrams/**/*.puml", "diagrams/*.puml", "*.puml"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    api_symbol_id = symbol_ids[("diagrams/flow.puml", "API")]
    db_symbol_id = symbol_ids[("diagrams/flow.puml", "DB")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{api_symbol_id}"
        and str(row["target_node"]) == f"symbol:{db_symbol_id}"
        for row in graph
    )
