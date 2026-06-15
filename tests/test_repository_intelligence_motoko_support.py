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
    repository_intelligence_motoko_parser_dispatch as repository_intelligence_motoko_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    motoko_analysis_support as repository_motoko_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    motoko_primitives as repository_motoko_primitives,
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


def test_repository_intelligence_motoko_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["motoko"] is (
        repository_intelligence_motoko_parser_dispatch._parse_motoko_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["motoko"] is (
        repository_intelligence_motoko_parser_dispatch._parse_motoko_dependencies_only
    )


def test_repository_intelligence_motoko_helpers_are_modularized() -> None:
    assert repository_service.motoko_adapter.has_motoko_path_hints is (
        repository_motoko_primitives.has_motoko_path_hints
    )
    assert repository_service.motoko_adapter.is_probable_motoko_source is (
        repository_motoko_analysis_support.is_probable_motoko_source
    )
    assert repository_service.motoko_adapter.iter_dependency_entries is (
        repository_motoko_primitives.iter_dependency_entries
    )
    assert repository_service.motoko_adapter.module_aliases_for_path is (
        repository_motoko_analysis_support.module_aliases_for_path
    )
    assert repository_service.motoko_adapter.parse_file is (
        repository_motoko_analysis_support.parse_file
    )


def test_motoko_adapter_parse_file_extracts_import_dependencies_and_references() -> None:
    module_index = {
        "utils.mo": "utils.mo",
        "src/utils.mo": "src/utils.mo",
    }
    text = (
        'import Utils "./utils";\n'
        "actor Main {\n"
        "  public func run() : async () {\n"
        "    Utils.helper();\n"
        "  };\n"
        "  func helper() : () {};\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.motoko_adapter.parse_file(
        "src/main.mo",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file in {"utils.mo", "src/utils.mo"} for dependency in dependencies)
    assert any(symbol.symbol_name == "Main" for symbol in symbols)
    assert any(reference.target_file in {"utils.mo", "src/utils.mo"} for reference in references)


def test_motoko_adapter_preserves_symbol_line_numbers_with_comments() -> None:
    text = (
        "// leading comment\n"
        "/*\n"
        "block comment\n"
        "*/\n"
        "actor Main {\n"
        "  public func run() : async () {\n"
        "    let local = 1;\n"
        "  };\n"
        "}\n"
    )

    symbol_entries = repository_motoko_primitives.iter_symbol_entries(text)

    assert ("Main", "actor", 5) in symbol_entries
    assert ("run", "func", 6) in symbol_entries
    assert ("local", "binding", 7) in symbol_entries


def test_motoko_language_detection_supports_sources_without_overclaiming() -> None:
    assert (
        repository_service._language_for_path(
            Path("src/Main.mo"),
            text='import Array "mo:base/Array";\nactor Main {}\n',
        )
        == "motoko"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.mo"),
            text="model Example\n  Real x;\nequation\n  der(x) = -x;\nend Example;\n",
        )
        == "modelica"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.mo"),
            text="plain notes without motoko or modelica markers\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_motoko_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "motoko-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    for index in range(6):
        (repo_path / "src" / f"Main{index}.mo").write_text(
            f'actor Main{index} {{ public func run() : async () {{}} }}\n',
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    for index in range(2):
        (repo_path / "tools" / f"helper_{index}.py").write_text("print('helper')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "motoko" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "motoko"


def test_repository_snapshot_graph_contains_motoko_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "motoko-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.mo").write_text(
        "actor Main {\n"
        "  func helper() : () {};\n"
        "  public func run() : async () {\n"
        "    helper();\n"
        "  };\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.mo"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "main.mo" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
