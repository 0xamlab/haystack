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
    repository_intelligence_roc_parser_dispatch as repository_intelligence_roc_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    roc_analysis_support as repository_roc_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    roc_primitives as repository_roc_primitives,
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


def test_repository_intelligence_roc_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["roc"] is (
        repository_intelligence_roc_parser_dispatch._parse_roc_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["roc"] is (
        repository_intelligence_roc_parser_dispatch._parse_roc_dependencies_only
    )


def test_repository_intelligence_roc_helpers_are_modularized() -> None:
    assert repository_service.roc_adapter.has_roc_path_hints is repository_roc_primitives.has_roc_path_hints
    assert repository_service.roc_adapter.is_probable_roc_source is (
        repository_roc_analysis_support.is_probable_roc_source
    )
    assert repository_service.roc_adapter.iter_dependency_entries is (
        repository_roc_primitives.iter_dependency_entries
    )
    assert repository_service.roc_adapter.module_aliases_for_path is (
        repository_roc_analysis_support.module_aliases_for_path
    )
    assert repository_service.roc_adapter.parse_file is repository_roc_analysis_support.parse_file


def test_roc_adapter_module_aliases_include_path_stem(tmp_path: Path) -> None:
    repo_path = tmp_path / "roc-alias-repo"
    (repo_path / "platform").mkdir(parents=True)
    (repo_path / "platform" / "Cmd.roc").write_text(
        'module [exec!]\n\nexec! : Str, List Str => Result {} _\nexec! = |_cmd, _args| Ok({})\n',
        encoding="utf-8",
    )

    aliases = repository_service.roc_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="platform/Cmd.roc",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "platform/Cmd.roc" in aliases
    assert "Cmd" in aliases
    assert "platform.Cmd" in aliases


def test_roc_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = {
        "platform/Cmd.roc": "platform/Cmd.roc",
        "Cmd.roc": "platform/Cmd.roc",
        "/Cmd.roc": "platform/Cmd.roc",
    }
    text = (
        'app [main!] { cli: platform "platform/main.roc" }\n'
        "import cli.Cmd\n\n"
        "main! : List Str => Result {} _\n"
        "main! = |_args|\n"
        "    helper!({})\n\n"
        "helper! : {} => Result {} _\n"
        'helper! = |{}|\n    Cmd.exec!("roc", ["version"])\n'
    )

    symbols, dependencies, references = repository_service.roc_adapter.parse_file(
        "build.roc",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "platform/Cmd.roc" for dependency in dependencies)
    assert any(symbol.symbol_name == "helper!" for symbol in symbols)
    assert any(reference.target_names == ("helper!",) for reference in references)
    assert any(reference.target_file == "platform/Cmd.roc" for reference in references)


def test_roc_language_detection_supports_roc_without_overclaiming() -> None:
    assert ".roc" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("build.roc"),
        text="import cli.Cmd\nmain! : List Str => Result {} _\nmain! = |_args| Ok({})\n",
    ) == "roc"
    assert repository_service._language_for_path(
        Path("notes.roc"),
        text="plain notes without roc syntax\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_roc_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "roc-profile-repo"
    (repo_path / "platform").mkdir(parents=True)
    for index in range(6):
        (repo_path / "platform" / f"Module{index}.roc").write_text(
            f"module [run{index}!]\n\nrun{index}! : {{}} => Result {{}} _\nrun{index}! = |{{}}| Ok({{}})\n",
            encoding="utf-8",
        )
    (repo_path / "ci").mkdir(parents=True)
    (repo_path / "ci" / "host.rs").write_text("fn main() {}\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "roc" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "roc"
    assert any(path.endswith(".roc") for path in seed_plan["candidate_file_paths"])


def test_operational_seed_plan_without_diagnostics_does_not_force_roc_first_in_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "roc-mixed-host-repo"
    (repo_path / "platform").mkdir(parents=True)
    for index in range(4):
        (repo_path / "platform" / f"Module{index}.roc").write_text(
            f"module [run{index}!]\n\nrun{index}! : {{}} => Result {{}} _\nrun{index}! = |{{}}| Ok({{}})\n",
            encoding="utf-8",
        )
    (repo_path / "src").mkdir(parents=True)
    for index in range(12):
        (repo_path / "src" / f"host_{index}.rs").write_text("fn main() {}\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "roc" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "roc"
    assert "rust" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_roc_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "roc-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "build.roc").write_text(
        "main! : List Str => Result {} _\n"
        "main! = |_args|\n"
        "    helper!({})\n\n"
        "helper! : {} => Result {} _\n"
        "helper! = |{}| Ok({})\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.roc"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "build.roc" and str(row["symbol_name"]) == "helper!"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
