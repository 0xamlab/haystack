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
    repository_intelligence_sml_parser_dispatch as repository_sml_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    sml_analysis_support as repository_sml_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    sml_primitives as repository_sml_primitives,
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


def test_repository_intelligence_sml_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["sml"] is (
        repository_sml_parser_dispatch._parse_sml_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["sml"] is (
        repository_sml_parser_dispatch._parse_sml_dependencies_only
    )


def test_repository_intelligence_sml_helpers_are_modularized() -> None:
    assert repository_service.sml_adapter.strip_comments is (
        repository_sml_primitives.strip_comments
    )
    assert repository_service.sml_adapter.has_sml_path_hints is (
        repository_sml_primitives.has_sml_path_hints
    )
    assert repository_service.sml_adapter.is_probable_sml_source is (
        repository_sml_analysis_support.is_probable_sml_source
    )
    assert repository_service.sml_adapter.module_aliases_for_path is (
        repository_sml_analysis_support.module_aliases_for_path
    )
    assert repository_service.sml_adapter.parse_dependencies_only is (
        repository_sml_analysis_support.parse_dependencies_only
    )
    assert repository_service.sml_adapter.parse_file is (
        repository_sml_analysis_support.parse_file
    )


def test_sml_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "sml-alias-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "util.sml").write_text(
        "structure Util = struct\n"
        "fun helper () = 1\n"
        "end\n",
        encoding="utf-8",
    )

    aliases = repository_service.sml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/acme/util.sml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acme/util.sml" in aliases
    assert "src/acme/util" in aliases
    assert "src.acme.util" in aliases
    assert "acme.util" in aliases
    assert "util" in aliases
    assert "helper" in aliases
    assert "util.helper" in aliases


def test_sml_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = repository_service._build_module_index(
        ["src/Util.sml", "src/Main.sml"],
        root_path=Path("/tmp/sml-index"),
    )
    text = (
        "structure Main = struct\n"
        "open Util\n"
        "val run = helper ()\n"
        "end\n"
    )

    symbols, dependencies, references = repository_service.sml_adapter.parse_file(
        "src/Main.sml",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_import=lambda import_target, index: repository_service.sml_adapter.resolve_import(
            import_target,
            module_index=index,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ),
    )

    assert any(dependency["target_file"] == "src/Util.sml" for dependency in dependencies)
    assert any(symbol["symbol_name"] == "run" for symbol in symbols)
    assert any(reference["target_file"] == "src/Util.sml" for reference in references)
    assert any(reference["target_names"] == ("helper",) for reference in references)


def test_sml_language_detection_prefers_explicit_sml_bucket() -> None:
    assert repository_service._language_for_path(Path("src/main.sml")) == "sml"
    assert repository_service._language_for_path(Path("src/core.sig")) == "sml"
    assert repository_service._language_for_path(Path("src/make.fun")) == "sml"


def test_operational_seed_plan_without_diagnostics_promotes_sml_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sml-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "project.mlb").write_text(
        "src/Util.sml\n"
        "src/Main.sml\n",
        encoding="utf-8",
    )
    for name in ("Util", "Main", "ExtraOne", "ExtraTwo", "ExtraThree", "ExtraFour"):
        (repo_path / "src" / f"{name}.sml").write_text(
            f"structure {name} = struct\nval run = 1\nend\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "sml" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "sml"


def test_operational_seed_plan_without_diagnostics_does_not_force_sml_first_in_python_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sml-mixed-host-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "python_host").mkdir(parents=True)
    (repo_path / "project.mlb").write_text(
        "src/Util.sml\n"
        "src/Main.sml\n",
        encoding="utf-8",
    )
    (repo_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "python-host"\n'
        'version = "0.0.0"\n',
        encoding="utf-8",
    )
    for name in ("Util", "Main", "ExtraOne", "ExtraTwo"):
        (repo_path / "src" / f"{name}.sml").write_text(
            f"structure {name} = struct\nval run = 1\nend\n",
            encoding="utf-8",
        )
    for index in range(24):
        (repo_path / "python_host" / f"host_{index}.py").write_text(
            "def run() -> int:\n    return 1\n",
            encoding="utf-8",
        )
    (repo_path / "manage.py").write_text(
        "def main() -> int:\n    return 0\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "sml" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "sml"
    assert "python" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_sml_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "sml-graph-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "project.mlb").write_text(
        "src/Util.sml\n"
        "src/Main.sml\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Util.sml").write_text(
        "structure Util = struct\n"
        "fun helper () = 1\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.sml").write_text(
        "structure Main = struct\n"
        "open Util\n"
        "val run = helper ()\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "project.mlb"],
            include_patterns=[
                "src/**/*.sml",
                "src/*.sml",
                "src/**/*.sig",
                "src/*.sig",
                "src/**/*.fun",
                "src/*.fun",
                "*.mlb",
                "*.cm",
            ],
        ),
    )

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "open"
        and str(row["source_node"]) == "file:src/Main.sml"
        and str(row["target_node"]) == "file:src/Util.sml"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/Main.sml", "run")]
    helper_symbol_id = symbol_ids[("src/Util.sml", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
