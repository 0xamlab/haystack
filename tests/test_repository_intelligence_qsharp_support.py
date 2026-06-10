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
    repository_intelligence_qsharp_parser_dispatch as repository_qsharp_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    qsharp_analysis_support as repository_qsharp_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    qsharp_primitives as repository_qsharp_primitives,
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


def test_repository_intelligence_qsharp_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["qsharp"] is (
        repository_qsharp_parser_dispatch._parse_qsharp_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["qsharp"] is (
        repository_qsharp_parser_dispatch._parse_qsharp_dependencies_only
    )


def test_repository_intelligence_qsharp_helpers_are_modularized() -> None:
    assert repository_service.qsharp_adapter.strip_comments is (
        repository_qsharp_primitives.strip_comments
    )
    assert repository_service.qsharp_adapter.has_qsharp_path_hints is (
        repository_qsharp_primitives.has_qsharp_path_hints
    )
    assert repository_service.qsharp_adapter.is_probable_qsharp_source is (
        repository_qsharp_analysis_support.is_probable_qsharp_source
    )
    assert repository_service.qsharp_adapter.is_probable_qsharp_config is (
        repository_qsharp_analysis_support.is_probable_qsharp_config
    )
    assert repository_service.qsharp_adapter.iter_dependency_entries is (
        repository_qsharp_primitives.iter_dependency_entries
    )
    assert repository_service.qsharp_adapter.module_aliases_for_path is (
        repository_qsharp_analysis_support.module_aliases_for_path
    )
    assert repository_service.qsharp_adapter.parse_dependencies_only is (
        repository_qsharp_analysis_support.parse_dependencies_only
    )
    assert repository_service.qsharp_adapter.parse_file is (
        repository_qsharp_analysis_support.parse_file
    )


def test_qsharp_adapter_module_aliases_include_namespace_like_paths(tmp_path: Path) -> None:
    repo_path = tmp_path / "qsharp-alias-repo"
    (repo_path / "Demo").mkdir(parents=True)
    (repo_path / "Demo" / "Common.qs").write_text(
        "namespace Demo.Common {\n"
        "    function PrepareCommon() : Int {\n"
        "        return 1;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.qsharp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Demo/Common.qs",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Demo/Common.qs" in aliases
    assert "Common.qs" in aliases
    assert "Common" in aliases
    assert "Demo/Common" in aliases
    assert "Demo.Common" in aliases


def test_qsharp_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = repository_service._build_module_index(
        ["Demo/Common.qs", "Demo/Main.qs", "qsharp.json"],
        root_path=Path("/tmp/qsharp-index"),
    )
    text = (
        "namespace Demo.Main {\n"
        "    open Demo.Common;\n\n"
        "    function Prepare() : Int {\n"
        "        return PrepareCommon();\n"
        "    }\n\n"
        "    operation Run() : Int {\n"
        "        return Prepare();\n"
        "    }\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.qsharp_adapter.parse_file(
        "Demo/Main.qs",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "Demo/Common.qs" for dependency in dependencies)
    assert any(symbol.symbol_name == "Demo.Main" for symbol in symbols)
    assert any(symbol.symbol_name == "Prepare" for symbol in symbols)
    assert any(symbol.symbol_name == "Run" for symbol in symbols)
    assert any(reference.target_file == "Demo/Common.qs" for reference in references)
    assert any(reference.target_names == ("Prepare",) for reference in references)


def test_qsharp_language_detection_supports_sources_and_configs_without_overclaiming() -> None:
    assert ".qs" in repository_service._TEXT_FILE_SUFFIXES
    assert "qsharp.json" in repository_service._TEXT_FILE_BASENAMES
    assert (
        repository_service._language_for_path(
            Path("Demo/Main.qs"),
            text=(
                "namespace Demo.Main {\n"
                "    operation Run() : Unit {\n"
                "        ()\n"
                "    }\n"
                "}\n"
            ),
        )
        == "qsharp"
    )
    assert repository_service._language_for_path(Path("qsharp.json"), text="{}\n") == "qsharp"
    assert (
        repository_service._language_for_path(
            Path("notes.qs"),
            text="plain notes without qsharp constructs\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_qsharp_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qsharp-profile-repo"
    (repo_path / "Demo").mkdir(parents=True)
    (repo_path / "qsharp.json").write_text("{}\n", encoding="utf-8")
    for index in range(6):
        (repo_path / "Demo" / f"Module{index}.qs").write_text(
            "namespace Demo.Module {\n"
            f"    function Prepare{index}() : Int {{\n"
            f"        return {index};\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "def helper() -> int:\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "qsharp" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "qsharp"
    assert "qsharp.json" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_does_not_force_qsharp_first_in_dotnet_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qsharp-mixed-dotnet-repo"
    (repo_path / "Quantum").mkdir(parents=True)
    (repo_path / "qsharp.json").write_text("{}\n", encoding="utf-8")
    for index in range(5):
        (repo_path / "Quantum" / f"Module{index}.qs").write_text(
            "namespace Quantum.Module {\n"
            f"    function Prepare{index}() : Int {{\n"
            f"        return {index};\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "src").mkdir(parents=True)
    for index in range(20):
        (repo_path / "src" / f"Host{index}.cs").write_text(
            "public static class Host { public static int Run() => 1; }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "qsharp" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "qsharp"
    assert "dotnet" in seed_plan["operational_ecosystems"] or "cs" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_qsharp_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "qsharp-graph-repo"
    (repo_path / "Demo").mkdir(parents=True)
    (repo_path / "qsharp.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "Demo" / "Common.qs").write_text(
        "namespace Demo.Common {\n"
        "    function PrepareCommon() : Int {\n"
        "        return 1;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Demo" / "Main.qs").write_text(
        "namespace Demo.Main {\n"
        "    open Demo.Common;\n\n"
        "    operation Run() : Int {\n"
        "        return PrepareCommon();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.qs", "qsharp.json"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    target_ids = {
        row["symbol_id"]
        for row in symbol_rows
        if row["file_path"] == "Demo/Common.qs" and row["symbol_name"] == "PrepareCommon"
    }
    assert target_ids
    target_nodes = {f"symbol:{symbol_id}" for symbol_id in target_ids}
    assert any(
        row["edge_type"] == "references_symbol"
        and row["target_node"] in target_nodes
        and row["source_node"].startswith("symbol:")
        for row in graph
    )
