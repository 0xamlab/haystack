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
    repository_intelligence_sway_parser_dispatch as repository_sway_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    sway_analysis_support as repository_sway_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    sway_primitives as repository_sway_primitives,
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


def test_repository_intelligence_sway_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["sway"] is (
        repository_sway_parser_dispatch._parse_sway_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["sway"] is (
        repository_sway_parser_dispatch._parse_sway_dependencies_only
    )


def test_repository_intelligence_sway_helpers_are_modularized() -> None:
    assert repository_service.sway_adapter.strip_comments is (
        repository_sway_primitives.strip_comments
    )
    assert repository_service.sway_adapter.has_sway_path_hints is (
        repository_sway_primitives.has_sway_path_hints
    )
    assert repository_service.sway_adapter.is_probable_sway_source is (
        repository_sway_primitives.is_probable_sway_source
    )
    assert repository_service.sway_adapter.module_aliases_for_path is (
        repository_sway_analysis_support.module_aliases_for_path
    )
    assert repository_service.sway_adapter.parse_dependencies_only is (
        repository_sway_analysis_support.parse_dependencies_only
    )
    assert repository_service.sway_adapter.parse_file is (
        repository_sway_analysis_support.parse_file
    )


def test_sway_adapter_module_aliases_include_module_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "sway-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "math_utils.sw").write_text(
        "library;\n"
        "fn add(a: u64, b: u64) -> u64 {\n"
        "    a + b\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.sway_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/math_utils.sw",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/math_utils.sw" in aliases
    assert "src/math_utils" in aliases
    assert "src.math_utils" in aliases
    assert "math_utils" in aliases
    assert "add" in aliases


def test_sway_adapter_parse_dependencies_resolves_use_targets(tmp_path: Path) -> None:
    repo_path = tmp_path / "sway-deps-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "math_utils.sw").write_text(
        "library;\n"
        "fn add(a: u64, b: u64) -> u64 {\n"
        "    a + b\n"
        "}\n",
        encoding="utf-8",
    )
    main_path = repo_path / "src" / "main.sw"
    main_path.write_text(
        "script;\n"
        "use math_utils::add;\n"
        "fn main() -> u64 {\n"
        "    add(1, 2)\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["src/math_utils.sw", "src/main.sw"],
        root_path=repo_path,
    )

    dependencies = repository_service.sway_adapter.parse_dependencies_only(
        "src/main.sw",
        main_path.read_text(encoding="utf-8"),
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert {dependency.target_file for dependency in dependencies} == {"src/math_utils.sw"}


def test_sway_language_detection_supports_sources_and_configs_without_overclaiming() -> None:
    assert ".sw" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("contracts/main.sw"),
            text="script;\nuse std::auth::msg_sender;\nfn main() {}\n",
        )
        == "sway"
    )
    assert (
        repository_service._language_for_path(
            Path("Forc.toml"),
            text="[project]\nname = \"demo\"\nentry = \"main.sw\"\n",
        )
        == "sway"
    )
    assert (
        repository_service._language_for_path(
            Path("notes/main.sw"),
            text="plain notes without sway markers\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_sway_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sway-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Forc.toml").write_text(
        "[project]\nname = \"demo\"\nentry = \"main.sw\"\n",
        encoding="utf-8",
    )
    for index in range(4):
        (repo_path / "src" / f"contract_{index}.sw").write_text(
            "contract;\nfn main() {}\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "helper.py").write_text("print('helper')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert "sway" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "sway"


def test_repository_snapshot_graph_contains_sway_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "sway-graph-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "math_utils.sw").write_text(
        "library;\n"
        "fn add(a: u64, b: u64) -> u64 {\n"
        "    a + b\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.sw").write_text(
        "script;\n"
        "use math_utils::add;\n"
        "fn main() -> u64 {\n"
        "    add(1, 2)\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.sw", "src/*.sw", "Forc.toml"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    add_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "src/math_utils.sw" and str(row["symbol_name"]) == "add"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{add_symbol_id}"
        for row in graph
    )
