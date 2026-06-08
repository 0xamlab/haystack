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
    repository_intelligence_org_parser_dispatch as repository_org_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    org_analysis_support as repository_org_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    org_primitives as repository_org_primitives,
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


def test_repository_intelligence_org_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["org"] is (
        repository_org_parser_dispatch._parse_org_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["org"] is (
        repository_org_parser_dispatch._parse_org_dependencies_only
    )


def test_repository_intelligence_org_helpers_are_modularized() -> None:
    assert repository_service.org_adapter.has_org_path_hints is (
        repository_org_primitives.has_org_path_hints
    )
    assert repository_service.org_adapter.is_probable_org_source is (
        repository_org_analysis_support.is_probable_org_source
    )
    assert repository_service.org_adapter.iter_import_entries is (
        repository_org_primitives.iter_import_entries
    )
    assert repository_service.org_adapter.iter_symbol_entries is (
        repository_org_primitives.iter_symbol_entries
    )
    assert repository_service.org_adapter.iter_reference_entries is (
        repository_org_primitives.iter_reference_entries
    )
    assert repository_service.org_adapter.module_aliases_for_path is (
        repository_org_analysis_support.module_aliases_for_path
    )
    assert repository_service.org_adapter.resolve_import is (
        repository_org_analysis_support.resolve_import
    )
    assert repository_service.org_adapter.parse_dependencies_only is (
        repository_org_analysis_support.parse_dependencies_only
    )
    assert repository_service.org_adapter.parse_file is (
        repository_org_analysis_support.parse_file
    )


def test_org_adapter_module_aliases_include_targets_and_headings(tmp_path: Path) -> None:
    repo_path = tmp_path / "org-alias-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "guide.org").write_text(
        "* Guide\n:PROPERTIES:\n:CUSTOM_ID: guide-anchor\n:END:\n<<guide-target>>\n",
        encoding="utf-8",
    )

    aliases = repository_service.org_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="docs/guide.org",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "docs/guide.org" in aliases
    assert "guide-anchor" in aliases
    assert "guide-target" in aliases
    assert "guide.Guide" in aliases


def test_org_adapter_parse_file_resolves_include_and_file_link(tmp_path: Path) -> None:
    repo_path = tmp_path / "org-parse-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "guide.org").write_text(
        "* Guide\n:PROPERTIES:\n:CUSTOM_ID: guide-anchor\n:END:\n<<guide-target>>\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "index.org").write_text(
        "* Index\n#+INCLUDE: \"guide.org\"\n[[file:guide.org::#guide-anchor][Guide]]\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["docs/index.org", "docs/guide.org"],
        root_path=repo_path,
    )
    text = (repo_path / "docs" / "index.org").read_text(encoding="utf-8")

    dependencies = repository_service.org_adapter.parse_dependencies_only(
        "docs/index.org",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.org_adapter.parse_file(
        "docs/index.org",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "docs/guide.org" for dependency in dependencies)
    assert any(symbol.symbol_kind == "org" and symbol.symbol_name == "index" for symbol in symbols)
    assert any(
        reference.target_file == "docs/guide.org" and "guide-anchor" in reference.target_names
        for reference in references
    )


def test_org_language_detection_supports_suffixes() -> None:
    assert ".org" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("docs/index.org"),
        text="* Index\n",
    ) == "org"


def test_operational_seed_plan_without_diagnostics_promotes_org_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "org-profile-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "index.org").write_text(
        "* Index\n#+INCLUDE: \"guide.org\"\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "guide.org").write_text("* Guide\n", encoding="utf-8")
    (repo_path / "docs" / "reference.org").write_text("* Reference\n", encoding="utf-8")
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "tools" / "build.py").write_text("print('docs')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "org" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "org"
    assert "docs/index.org" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_org_first_in_python_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "org-mixed-python-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "index.org").write_text("* Index\n", encoding="utf-8")
    (repo_path / "docs" / "guide.org").write_text("* Guide\n", encoding="utf-8")
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

    assert "org" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "org"
    assert "python" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_org_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "org-graph-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "guide.org").write_text(
        "* Guide\n:PROPERTIES:\n:CUSTOM_ID: guide-anchor\n:END:\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "index.org").write_text(
        "* Index\n#+INCLUDE: \"guide.org\"\n[[file:guide.org::#guide-anchor][Guide]]\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["docs/**/*.org", "docs/*.org", "*.org"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "include"
        and str(row["source_node"]) == "file:docs/index.org"
        and str(row["target_node"]) == "file:docs/guide.org"
        for row in graph
    )
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    source_symbol_id = symbol_ids[("docs/index.org", "Index")]
    target_symbol_id = symbol_ids[("docs/guide.org", "guide-anchor")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{source_symbol_id}"
        and str(row["target_node"]) == f"symbol:{target_symbol_id}"
        for row in graph
    )
