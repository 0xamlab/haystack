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
    repository_intelligence_rst_parser_dispatch as repository_rst_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    rst_analysis_support as repository_rst_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    rst_primitives as repository_rst_primitives,
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


def test_repository_intelligence_rst_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["rst"] is (
        repository_rst_parser_dispatch._parse_rst_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["rst"] is (
        repository_rst_parser_dispatch._parse_rst_dependencies_only
    )


def test_repository_intelligence_rst_helpers_are_modularized() -> None:
    assert repository_service.rst_adapter.has_rst_path_hints is (
        repository_rst_primitives.has_rst_path_hints
    )
    assert repository_service.rst_adapter.is_probable_rst_source is (
        repository_rst_analysis_support.is_probable_rst_source
    )
    assert repository_service.rst_adapter.iter_import_entries is (
        repository_rst_primitives.iter_import_entries
    )
    assert repository_service.rst_adapter.iter_symbol_entries is (
        repository_rst_primitives.iter_symbol_entries
    )
    assert repository_service.rst_adapter.iter_reference_entries is (
        repository_rst_primitives.iter_reference_entries
    )
    assert repository_service.rst_adapter.module_aliases_for_path is (
        repository_rst_analysis_support.module_aliases_for_path
    )
    assert repository_service.rst_adapter.resolve_import is (
        repository_rst_analysis_support.resolve_import
    )
    assert repository_service.rst_adapter.parse_dependencies_only is (
        repository_rst_analysis_support.parse_dependencies_only
    )
    assert repository_service.rst_adapter.parse_file is repository_rst_analysis_support.parse_file


def test_rst_adapter_module_aliases_include_labels_and_sections(tmp_path: Path) -> None:
    repo_path = tmp_path / "rst-alias-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "guide.rst").write_text(
        ".. _guide-start:\n\nGuide\n=====\n",
        encoding="utf-8",
    )

    aliases = repository_service.rst_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="docs/guide.rst",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "docs/guide.rst" in aliases
    assert "guide-start" in aliases
    assert "guide.Guide" in aliases


def test_rst_adapter_parse_file_resolves_toctree_and_doc_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "rst-parse-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "guide.rst").write_text(
        ".. _guide-label:\n\nGuide\n=====\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "index.rst").write_text(
        ".. _index-label:\n\nIndex\n=====\n\n"
        ".. toctree::\n"
        "   guide\n\n"
        "See :doc:`guide` and :ref:`index-label`.\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["docs/index.rst", "docs/guide.rst"],
        root_path=repo_path,
    )
    text = (repo_path / "docs" / "index.rst").read_text(encoding="utf-8")

    dependencies = repository_service.rst_adapter.parse_dependencies_only(
        "docs/index.rst",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.rst_adapter.parse_file(
        "docs/index.rst",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "docs/guide.rst" for dependency in dependencies)
    assert any(symbol.symbol_kind == "rst" and symbol.symbol_name == "index" for symbol in symbols)
    assert any(
        reference.target_file == "docs/guide.rst" and "guide" in reference.target_names
        for reference in references
    )


def test_rst_language_detection_supports_rst_suffixes() -> None:
    assert ".rst" in repository_service._TEXT_FILE_SUFFIXES
    assert ".rest" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("docs/index.rst"),
        text="Index\n=====\n",
    ) == "rst"


def test_operational_seed_plan_without_diagnostics_promotes_rst_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rst-profile-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "index.rst").write_text(
        "Index\n=====\n\n.. toctree::\n   guide\n   api/reference\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "guide.rst").write_text("Guide\n=====\n", encoding="utf-8")
    (repo_path / "docs" / "api").mkdir(parents=True)
    (repo_path / "docs" / "api" / "reference.rst").write_text(
        "Reference\n=========\n",
        encoding="utf-8",
    )
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "tools" / "build.py").write_text("print('docs')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "rst" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "rst"
    assert "docs/index.rst" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_rst_first_in_python_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rst-mixed-python-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "index.rst").write_text("Index\n=====\n", encoding="utf-8")
    (repo_path / "docs" / "guide.rst").write_text("Guide\n=====\n", encoding="utf-8")
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

    assert "rst" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "rst"
    assert "python" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_rst_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "rst-graph-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "guide.rst").write_text(
        ".. _guide-label:\n\nGuide\n=====\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "index.rst").write_text(
        ".. _index-label:\n\n"
        "Index\n=====\n\n"
        ".. toctree::\n"
        "   guide\n\n"
        "See :doc:`guide` and :ref:`index-label`.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["docs/**/*.rst", "docs/*.rst", "*.rst"],
            max_files=16,
        ),
    )

    dependency_rows = (
        pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
        if snapshot.repository_graph_artifact is not None
        else []
    )
    symbol_rows = (
        pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
        if snapshot.symbol_graph_artifact is not None
        else []
    )

    root_symbol = next(
        row for row in symbol_rows if row["symbol_name"] == "index" and row["file_path"] == "docs/index.rst"
    )
    section_symbol = next(
        row for row in symbol_rows if row["symbol_name"] == "Index" and row["file_path"] == "docs/index.rst"
    )
    index_label_symbol = next(
        row
        for row in symbol_rows
        if row["symbol_name"] == "index-label" and row["file_path"] == "docs/index.rst"
    )

    assert any(
        row["source_node"] == "file:docs/index.rst"
        and row["target_node"] == "file:docs/guide.rst"
        and row["edge_type"] == "toctree"
        for row in dependency_rows
    )
    assert any(
        row["source_node"] in {
            f"symbol:{root_symbol['symbol_id']}",
            f"symbol:{section_symbol['symbol_id']}",
        }
        and row["target_node"] == f"symbol:{index_label_symbol['symbol_id']}"
        and row["edge_type"] == "references_symbol"
        for row in dependency_rows
    )
