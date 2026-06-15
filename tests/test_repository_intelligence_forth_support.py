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
    repository_intelligence_forth_parser_dispatch as repository_intelligence_forth_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    forth_analysis_support as repository_forth_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    forth_primitives as repository_forth_primitives,
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


def test_repository_intelligence_forth_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["forth"] is (
        repository_intelligence_forth_parser_dispatch._parse_forth_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["forth"] is (
        repository_intelligence_forth_parser_dispatch._parse_forth_dependencies_only
    )


def test_repository_intelligence_forth_helpers_are_modularized() -> None:
    assert repository_service.forth_adapter.has_forth_path_hints is (
        repository_forth_primitives.has_forth_path_hints
    )
    assert repository_service.forth_adapter.is_probable_forth_source is (
        repository_forth_analysis_support.is_probable_forth_source
    )
    assert repository_service.forth_adapter.iter_dependency_entries is (
        repository_forth_primitives.iter_dependency_entries
    )
    assert repository_service.forth_adapter.module_aliases_for_path is (
        repository_forth_analysis_support.module_aliases_for_path
    )
    assert repository_service.forth_adapter.parse_file is (
        repository_forth_analysis_support.parse_file
    )


def test_forth_adapter_parse_file_extracts_include_dependencies_and_references() -> None:
    module_index = {
        "lib.fs": "lib.fs",
        "helpers.fth": "helpers.fth",
    }
    text = "include lib.fs\n: helper 1 ;\n: run helper ;\n"

    symbols, dependencies, references = repository_service.forth_adapter.parse_file(
        "main.fth",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "lib.fs" for dependency in dependencies)
    assert any(symbol.symbol_name == "helper" for symbol in symbols)
    assert any(reference.target_names == ("helper",) for reference in references)


def test_forth_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".fth" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("kernel/main.fth"),
            text=": main 1 ;\n",
        )
        == "forth"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.fs"),
            text="module Demo\nlet x = 1\n",
        )
        == "fsharp"
    )
    assert (
        repository_service._language_for_path(
            Path("src/FSharp.Data.Runtime.Utilities/Caching.fs"),
            text=(
                "/// Creates a cache that uses in-memory collection\n"
                "type ICache<'TKey, 'TValue> =\n"
                "    abstract Set: key: 'TKey * value: 'TValue -> unit\n"
                "let createInMemoryCache (expiration: TimeSpan) =\n"
                "    let dict = ConcurrentDictionary<'TKey_, 'TValue * DateTime>()\n"
            ),
        )
        == "fsharp"
    )
    assert (
        repository_service._language_for_path(
            Path("src/FSharp.Data.Runtime.Utilities/StructuralInference.fs"),
            text=(
                "match infered with\n"
                "    | InferedType.Primitive p ->\n"
                "        { PrimitiveType = p\n"
                "          Value = PrimitiveInferedValue.Create value }\n"
            ),
        )
        == "fsharp"
    )
    assert (
        repository_service._language_for_path(
            Path("src/FSharp.Data.DesignTime/CommonProviderImplementation/Helpers.fs"),
            text=(
                "let providedMembers =\n"
                "    [ yield m :> _ ]\n"
            ),
        )
        == "fsharp"
    )
    assert (
        repository_service._language_for_path(
            Path("src/FSharp.Data.Json.Core/JsonValue.fs"),
            text=(
                "member private x.PrepareRequest(httpMethod, headers) =\n"
                "    HttpRequestHeaders.UserAgent \"demo\" :: headers\n"
            ),
        )
        == "fsharp"
    )
    assert (
        repository_service._language_for_path(
            Path("src/FSharp.Data.Json.Core/JsonValue.fs"),
            text=(
                "type JsonValue() =\n"
                "    member _.Clone(value) =\n"
                "        value\n"
                "\n"
                "    member _.PrepareRequest(headers) =\n"
                "        headers\n"
            ),
        )
        == "fsharp"
    )
    assert (
        repository_service._language_for_path(
            Path("src/FSharp.Data.DesignTime/Xml/XmlGenerator.fs"),
            text=(
                "let builder =\n"
                "    (\n"
                "                                     : Expr)\n"
                ")\n"
            ),
        )
        == "fsharp"
    )


def test_operational_seed_plan_without_diagnostics_promotes_forth_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "forth-profile-repo"
    (repo_path / "kernel").mkdir(parents=True)
    for index in range(6):
        (repo_path / "kernel" / f"word_{index}.fth").write_text(
            f": word_{index} {index} ;\n",
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

    assert "forth" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "forth"


def test_operational_seed_plan_without_diagnostics_prefers_forth_fs_surface_over_host_fsproj(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "forth-hosted-fs-repo"
    (repo_path / "kernel").mkdir(parents=True)
    for index in range(6):
        (repo_path / "kernel" / f"word_{index}.fs").write_text(
            f": word_{index} {index} ;\n",
            encoding="utf-8",
        )
    (repo_path / "src" / "Host").mkdir(parents=True)
    (repo_path / "src" / "Host" / "Host.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Host" / "Program.fs").write_text(
        "module Host\nlet main = 1\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["kernel"],
        max_files=128,
    )

    assert "forth" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "forth"


def test_repository_snapshot_graph_contains_forth_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "forth-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.fth").write_text(
        ": helper 1 ;\n"
        ": run helper ;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.fth"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "main.fth" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
