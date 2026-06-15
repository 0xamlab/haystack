from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq
import pytest

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_isabelle_parser_dispatch as repository_intelligence_isabelle_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    isabelle_analysis_support as repository_isabelle_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    isabelle_primitives as repository_isabelle_primitives,
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


def test_repository_intelligence_isabelle_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["isabelle"] is (
        repository_intelligence_isabelle_parser_dispatch._parse_isabelle_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["isabelle"] is (
        repository_intelligence_isabelle_parser_dispatch._parse_isabelle_dependencies_only
    )


def test_repository_intelligence_isabelle_helpers_are_modularized() -> None:
    assert repository_service.isabelle_adapter.has_isabelle_path_hints is (
        repository_isabelle_primitives.has_isabelle_path_hints
    )
    assert repository_service.isabelle_adapter.is_probable_isabelle_source is (
        repository_isabelle_analysis_support.is_probable_isabelle_source
    )
    assert repository_service.isabelle_adapter.iter_dependency_entries is (
        repository_isabelle_primitives.iter_dependency_entries
    )
    assert repository_service.isabelle_adapter.module_aliases_for_path is (
        repository_isabelle_analysis_support.module_aliases_for_path
    )
    assert repository_service.isabelle_adapter.parse_file is (
        repository_isabelle_analysis_support.parse_file
    )


def test_isabelle_adapter_parse_file_extracts_import_dependencies_and_references() -> None:
    module_index = {
        "Base.thy": "Base.thy",
        "Theory/Helper.thy": "Theory/Helper.thy",
    }
    text = (
        "theory Main\n"
        "imports Base\n"
        "begin\n"
        "definition helper where \"helper = 1\"\n"
        "lemma run: \"helper = helper\"\n"
        "end\n"
    )

    symbols, dependencies, references = repository_service.isabelle_adapter.parse_file(
        "Main.thy",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "Base.thy" for dependency in dependencies)
    assert any(symbol.symbol_name == "helper" for symbol in symbols)
    assert any(reference.target_names == ("helper",) for reference in references)


def test_isabelle_iter_reference_entries_reuse_cached_stripped_text_entries() -> None:
    repository_isabelle_primitives._iter_reference_entries_from_stripped_text.cache_clear()
    stripped_text = repository_isabelle_primitives.strip_comments(
        "theory Main\nimports Base\nbegin\nlemma run: \"helper = helper\" by simp\nend\n"
    )

    first_result = repository_isabelle_primitives.iter_reference_entries(
        "",
        stripped_text=stripped_text,
    )
    first_cache_info = (
        repository_isabelle_primitives._iter_reference_entries_from_stripped_text.cache_info()
    )
    second_result = repository_isabelle_primitives.iter_reference_entries(
        "",
        stripped_text=stripped_text,
    )
    second_cache_info = (
        repository_isabelle_primitives._iter_reference_entries_from_stripped_text.cache_info()
    )

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_isabelle_adapter_parse_file_reuses_single_stripped_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_index = {
        "Base.thy": "Base.thy",
        "Theory/Helper.thy": "Theory/Helper.thy",
    }
    text = (
        "theory Main\n"
        "imports Base\n"
        "begin\n"
        "definition helper where \"helper = 1\"\n"
        "lemma run: \"helper = helper\"\n"
        "end\n"
    )

    original_strip_comments = repository_isabelle_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(source_text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(source_text)

    monkeypatch.setattr(
        repository_isabelle_primitives,
        "strip_comments",
        counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_isabelle_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    repository_service.isabelle_adapter.parse_dependencies_only(
        "Main.thy",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.isabelle_adapter.parse_file(
        "Main.thy",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_isabelle_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".thy" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("proof/Main.thy"),
            text="theory Main\nimports Base\nbegin\nend\n",
        )
        == "isabelle"
    )
    assert (
        repository_service._language_for_path(
            Path("proof/Main.thy"),
            text="plain notes without proof markers\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_isabelle_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "isabelle-profile-repo"
    (repo_path / "proof").mkdir(parents=True)
    for index in range(6):
        (repo_path / "proof" / f"Theory{index}.thy").write_text(
            f"theory Theory{index}\nimports Base\nbegin\nlemma lemma_{index}: \"True\" by simp\nend\n",
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

    assert "isabelle" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "isabelle"


def test_repository_snapshot_graph_contains_isabelle_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "isabelle-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "Main.thy").write_text(
        "theory Main\n"
        "imports Base\n"
        "begin\n"
        "definition helper where \"helper = 1\"\n"
        "lemma run: \"helper = helper\"\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.thy"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "Main.thy" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
