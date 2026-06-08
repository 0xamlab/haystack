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
    repository_intelligence_wren_parser_dispatch as repository_intelligence_wren_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    wren_analysis_support as repository_wren_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    wren_primitives as repository_wren_primitives,
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


def test_repository_intelligence_wren_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["wren"] is (
        repository_intelligence_wren_parser_dispatch._parse_wren_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["wren"] is (
        repository_intelligence_wren_parser_dispatch._parse_wren_dependencies_only
    )


def test_repository_intelligence_wren_helpers_are_modularized() -> None:
    assert repository_service.wren_adapter.has_wren_path_hints is (
        repository_wren_primitives.has_wren_path_hints
    )
    assert repository_service.wren_adapter.is_probable_wren_source is (
        repository_wren_analysis_support.is_probable_wren_source
    )
    assert repository_service.wren_adapter.parse_import_entries is (
        repository_wren_primitives.parse_import_entries
    )
    assert repository_service.wren_adapter.module_aliases_for_path is (
        repository_wren_analysis_support.module_aliases_for_path
    )
    assert repository_service.wren_adapter.parse_file is (
        repository_wren_analysis_support.parse_file
    )


def test_wren_adapter_module_aliases_include_class_and_method_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "wren-alias-repo"
    (repo_path / "demo").mkdir(parents=True)
    (repo_path / "demo" / "main.wren").write_text(
        'import "demo/util" for Helper\n'
        "class Runner {\n"
        "  construct new() {}\n"
        "  run() { Helper.ping() }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.wren_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="demo/main.wren",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "demo/main.wren" in aliases
    assert "demo/main" in aliases
    assert "Runner" in aliases
    assert "Runner.new" in aliases
    assert "Runner.run" in aliases


def test_wren_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = {
        "demo/util": "demo/util.wren",
        "demo/util.wren": "demo/util.wren",
    }
    text = (
        'import "demo/util" for Helper\n'
        "class Runner {\n"
        "  construct new() {}\n"
        "  run() {\n"
        "    Helper.ping()\n"
        "    Runner.new()\n"
        "    new()\n"
        "  }\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.wren_adapter.parse_file(
        "demo/main.wren",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "demo/util.wren" for dependency in dependencies)
    assert any(symbol.symbol_name == "Runner" for symbol in symbols)
    assert any(symbol.symbol_name == "new" for symbol in symbols)
    assert any(reference.target_file == "demo/util.wren" for reference in references)
    assert any(reference.target_file == "demo/main.wren" for reference in references)
    assert any(reference.target_names == ("new",) for reference in references)


def test_wren_language_detection_supports_wren_without_overclaiming() -> None:
    assert ".wren" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("demo/main.wren"),
        text='import "random" for Random\nclass Runner {}\n',
    ) == "wren"
    assert repository_service._language_for_path(
        Path("notes.wren"),
        text="plain notes without Wren constructs\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_wren_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "wren-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    for index in range(8):
        (repo_path / "src" / f"mod_{index}.wren").write_text(
            f"class Runner{index} {{ run() {{ System.print({index}) }} }}\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    for index in range(2):
        (repo_path / "tools" / f"host_{index}.py").write_text(
            "def main():\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "wren" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "wren"
    assert any(path.endswith(".wren") for path in seed_plan["candidate_file_paths"])


def test_operational_seed_plan_without_diagnostics_does_not_force_wren_first_in_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "wren-mixed-host-repo"
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(6):
        (repo_path / "scripts" / f"mod_{index}.wren").write_text(
            f"class Runner{index} {{ run() {{ System.print({index}) }} }}\n",
            encoding="utf-8",
        )
    (repo_path / "src").mkdir(parents=True)
    for index in range(20):
        (repo_path / "src" / f"host_{index}.c").write_text(
            "int main(void) { return 0; }\n",
            encoding="utf-8",
        )
    for index in range(12):
        (repo_path / "src" / f"host_{index}.h").write_text(
            "int runner(void);\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "wren" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "wren"
    assert "c" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_wren_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "wren-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.wren").write_text(
        "class Helper {\n"
        "  static ping() {}\n"
        "}\n"
        "class Runner {\n"
        "  run() {\n"
        "    Helper.ping()\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.wren"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_ids = {
        row["symbol_id"]
        for row in symbol_rows
        if row["symbol_name"] == "ping" and row["file_path"] == "main.wren"
    }
    assert helper_ids
    helper_nodes = {f"symbol:{symbol_id}" for symbol_id in helper_ids}
    assert any(
        row["edge_type"] == "references_symbol"
        and row["target_node"] in helper_nodes
        and row["source_node"].startswith("symbol:")
        for row in graph
    )
