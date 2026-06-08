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
    repository_intelligence_fennel_parser_dispatch as repository_intelligence_fennel_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    fennel_analysis_support as repository_fennel_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    fennel_primitives as repository_fennel_primitives,
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


def test_repository_intelligence_fennel_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["fennel"] is (
        repository_intelligence_fennel_parser_dispatch._parse_fennel_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["fennel"] is (
        repository_intelligence_fennel_parser_dispatch._parse_fennel_dependencies_only
    )


def test_repository_intelligence_fennel_helpers_are_modularized() -> None:
    assert repository_service.fennel_adapter.has_fennel_path_hints is (
        repository_fennel_primitives.has_fennel_path_hints
    )
    assert repository_service.fennel_adapter.is_probable_fennel_source is (
        repository_fennel_analysis_support.is_probable_fennel_source
    )
    assert repository_service.fennel_adapter.parse_import_entries is (
        repository_fennel_primitives.parse_import_entries
    )
    assert repository_service.fennel_adapter.module_aliases_for_path is (
        repository_fennel_analysis_support.module_aliases_for_path
    )
    assert repository_service.fennel_adapter.parse_file is (
        repository_fennel_analysis_support.parse_file
    )


def test_fennel_adapter_module_aliases_include_module_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "fennel-alias-repo"
    (repo_path / "fnl" / "demo").mkdir(parents=True)
    (repo_path / "fnl" / "demo" / "init.fnl").write_text(
        "(local util (require :demo.util))\n"
        "(lambda setup [] true)\n"
        "(global demo {:setup setup})\n",
        encoding="utf-8",
    )

    aliases = repository_service.fennel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="fnl/demo/init.fnl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "fnl/demo/init.fnl" in aliases
    assert "demo" in aliases
    assert "setup" in aliases


def test_fennel_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = {
        "demo.util": "fnl/demo/util.fnl",
        "demo/macros": "fnl/demo/macros.fnl",
        "demo.macros": "fnl/demo/macros.fnl",
        "fnl/demo/util.fnl": "fnl/demo/util.fnl",
        "fnl/demo/macros.fnl": "fnl/demo/macros.fnl",
    }
    text = (
        "(local util (require :demo.util))\n"
        "(import-macros {: setup} :demo.macros)\n"
        "(fn helper [] 1)\n"
        "(lambda runner []\n"
        "  (setup)\n"
        "  (util.run)\n"
        "  (helper))\n"
    )

    symbols, dependencies, references = repository_service.fennel_adapter.parse_file(
        "fnl/demo/init.fnl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "fnl/demo/util.fnl" for dependency in dependencies)
    assert any(dependency.target_file == "fnl/demo/macros.fnl" for dependency in dependencies)
    assert any(symbol.symbol_name == "runner" for symbol in symbols)
    assert any(reference.target_file == "fnl/demo/util.fnl" for reference in references)
    assert any(reference.target_file == "fnl/demo/macros.fnl" for reference in references)
    assert any(reference.target_names == ("helper",) for reference in references)


def test_fennel_language_detection_supports_fennel_without_overclaiming() -> None:
    assert ".fnl" in repository_service._TEXT_FILE_SUFFIXES
    assert ".fnlm" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("fnl/demo/init.fnl"),
        text="(local util (require :demo.util))\n(lambda setup [] true)\n",
    ) == "fennel"
    assert repository_service._language_for_path(
        Path("macro/demo.fnlm"),
        text="(macro setup [] '(print :ok))\n",
    ) == "fennel"
    assert repository_service._language_for_path(
        Path("notes.fnl"),
        text="plain notes without fennel forms\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_fennel_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fennel-profile-repo"
    (repo_path / "fnl" / "demo").mkdir(parents=True)
    for index in range(8):
        (repo_path / "fnl" / "demo" / f"mod_{index}.fnl").write_text(
            f"(local util (require :demo.util))\n(fn fn-{index} [] {index})\n",
            encoding="utf-8",
        )
    (repo_path / "lua").mkdir(parents=True)
    for index in range(2):
        (repo_path / "lua" / f"host_{index}.lua").write_text(
            "local M = {}\nreturn M\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "fennel" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "fennel"
    assert any(path.endswith(".fnl") for path in seed_plan["candidate_file_paths"])


def test_operational_seed_plan_without_diagnostics_does_not_force_fennel_first_in_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fennel-mixed-host-repo"
    (repo_path / "fnl" / "demo").mkdir(parents=True)
    for index in range(6):
        (repo_path / "fnl" / "demo" / f"mod_{index}.fnl").write_text(
            f"(local util (require :demo.util))\n(fn fn-{index} [] {index})\n",
            encoding="utf-8",
        )
    (repo_path / "lua").mkdir(parents=True)
    for index in range(24):
        (repo_path / "lua" / f"host_{index}.lua").write_text(
            "local M = {}\nfunction M.run() return true end\nreturn M\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "fennel" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "fennel"
    assert "lua" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_fennel_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "fennel-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.fnl").write_text(
        "(fn helper [] 1)\n"
        "(lambda runner []\n"
        "  (helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.fnl", "*.fnlm"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "main.fnl" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
