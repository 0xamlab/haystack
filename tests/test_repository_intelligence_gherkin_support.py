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
    repository_intelligence_gherkin_parser_dispatch as repository_gherkin_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    gherkin_analysis_support as repository_gherkin_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gherkin_primitives as repository_gherkin_primitives,
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


def test_repository_intelligence_gherkin_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["gherkin"] is (
        repository_gherkin_parser_dispatch._parse_gherkin_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["gherkin"] is (
        repository_gherkin_parser_dispatch._parse_gherkin_dependencies_only
    )


def test_repository_intelligence_gherkin_helpers_are_modularized() -> None:
    assert repository_service.gherkin_adapter.has_gherkin_path_hints is (
        repository_gherkin_primitives.has_gherkin_path_hints
    )
    assert repository_service.gherkin_adapter.is_probable_gherkin_source is (
        repository_gherkin_analysis_support.is_probable_gherkin_source
    )
    assert repository_service.gherkin_adapter.iter_symbol_entries is (
        repository_gherkin_primitives.iter_symbol_entries
    )
    assert repository_service.gherkin_adapter.iter_reference_entries is (
        repository_gherkin_primitives.iter_reference_entries
    )
    assert repository_service.gherkin_adapter.module_aliases_for_path is (
        repository_gherkin_analysis_support.module_aliases_for_path
    )
    assert repository_service.gherkin_adapter.parse_dependencies_only is (
        repository_gherkin_analysis_support.parse_dependencies_only
    )
    assert repository_service.gherkin_adapter.parse_file is (
        repository_gherkin_analysis_support.parse_file
    )


def test_gherkin_adapter_module_aliases_include_feature_and_scenario_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "gherkin-alias-repo"
    (repo_path / "features").mkdir(parents=True)
    (repo_path / "features" / "login.feature").write_text(
        "Feature: Login\n\nScenario: Successful login\n  Given a user exists\n",
        encoding="utf-8",
    )

    aliases = repository_service.gherkin_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="features/login.feature",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "features/login.feature" in aliases
    assert "login" in aliases
    assert "Login" in aliases
    assert "Successful login" in aliases


def test_gherkin_adapter_parse_file_emits_local_background_and_outline_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gherkin-parse-repo"
    (repo_path / "features").mkdir(parents=True)
    feature_path = repo_path / "features" / "login.feature"
    feature_path.write_text(
        "Feature: Login\n\n"
        "Background:\n"
        "  Given a user exists\n\n"
        "Scenario Outline: Login succeeds\n"
        "  When the user logs in with <role>\n"
        "  Then the dashboard appears\n\n"
        "Examples: Allowed roles\n"
        "  | role |\n"
        "  | admin |\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["features/login.feature"],
        root_path=repo_path,
    )
    text = feature_path.read_text(encoding="utf-8")

    dependencies = repository_service.gherkin_adapter.parse_dependencies_only(
        "features/login.feature",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.gherkin_adapter.parse_file(
        "features/login.feature",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert dependencies == ()
    assert any(symbol.symbol_kind == "gherkin" and symbol.symbol_name == "login" for symbol in symbols)
    assert any("Login::Background" in reference.target_names for reference in references)
    assert any("Login succeeds" in reference.target_names for reference in references)


def test_gherkin_language_detection_supports_feature_suffix() -> None:
    assert ".feature" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("features/login.feature"),
        text="Feature: Login\n",
    ) == "gherkin"


def test_operational_seed_plan_without_diagnostics_promotes_gherkin_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gherkin-profile-repo"
    (repo_path / "features").mkdir(parents=True)
    (repo_path / "features" / "login.feature").write_text(
        "Feature: Login\n\nScenario: Successful login\n  Given a user exists\n",
        encoding="utf-8",
    )
    (repo_path / "features" / "checkout.feature").write_text(
        "Feature: Checkout\n\nScenario: Order completes\n  Given an item exists\n",
        encoding="utf-8",
    )
    (repo_path / "steps").mkdir(parents=True)
    (repo_path / "steps" / "helpers.py").write_text("print('gherkin')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "gherkin" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "gherkin"
    assert "features/login.feature" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_gherkin_first_in_python_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gherkin-mixed-python-repo"
    (repo_path / "features").mkdir(parents=True)
    (repo_path / "features" / "login.feature").write_text("Feature: Login\n", encoding="utf-8")
    (repo_path / "features" / "checkout.feature").write_text(
        "Feature: Checkout\n",
        encoding="utf-8",
    )
    (repo_path / "pkg").mkdir(parents=True)
    for index in range(18):
        (repo_path / "pkg" / f"module_{index}.py").write_text(
            f"def fn_{index}():\n    return {index}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "gherkin" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "gherkin"
    assert "python" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_gherkin_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "gherkin-graph-repo"
    (repo_path / "features").mkdir(parents=True)
    (repo_path / "features" / "login.feature").write_text(
        "Feature: Login\n\n"
        "Background:\n"
        "  Given a user exists\n\n"
        "Scenario Outline: Login succeeds\n"
        "  When the user logs in with <role>\n"
        "  Then the dashboard appears\n\n"
        "Examples: Allowed roles\n"
        "  | role |\n"
        "  | admin |\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["features/**/*.feature", "features/*.feature", "*.feature"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    scenario_symbol_id = symbol_ids[("features/login.feature", "Login succeeds")]
    background_symbol_id = symbol_ids[("features/login.feature", "Login::Background")]
    examples_symbol_id = symbol_ids[("features/login.feature", "Login succeeds::Allowed roles")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{scenario_symbol_id}"
        and str(row["target_node"]) == f"symbol:{background_symbol_id}"
        for row in graph
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{examples_symbol_id}"
        and str(row["target_node"]) == f"symbol:{scenario_symbol_id}"
        for row in graph
    )
