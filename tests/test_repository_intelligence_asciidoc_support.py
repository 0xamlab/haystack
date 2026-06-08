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
    repository_intelligence_asciidoc_parser_dispatch as repository_asciidoc_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    asciidoc_analysis_support as repository_asciidoc_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    asciidoc_primitives as repository_asciidoc_primitives,
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


def test_repository_intelligence_asciidoc_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["asciidoc"] is (
        repository_asciidoc_parser_dispatch._parse_asciidoc_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["asciidoc"] is (
        repository_asciidoc_parser_dispatch._parse_asciidoc_dependencies_only
    )


def test_repository_intelligence_asciidoc_helpers_are_modularized() -> None:
    assert repository_service.asciidoc_adapter.has_asciidoc_path_hints is (
        repository_asciidoc_primitives.has_asciidoc_path_hints
    )
    assert repository_service.asciidoc_adapter.is_probable_asciidoc_source is (
        repository_asciidoc_analysis_support.is_probable_asciidoc_source
    )
    assert repository_service.asciidoc_adapter.iter_import_entries is (
        repository_asciidoc_primitives.iter_import_entries
    )
    assert repository_service.asciidoc_adapter.iter_symbol_entries is (
        repository_asciidoc_primitives.iter_symbol_entries
    )
    assert repository_service.asciidoc_adapter.iter_reference_entries is (
        repository_asciidoc_primitives.iter_reference_entries
    )
    assert repository_service.asciidoc_adapter.module_aliases_for_path is (
        repository_asciidoc_analysis_support.module_aliases_for_path
    )
    assert repository_service.asciidoc_adapter.resolve_import is (
        repository_asciidoc_analysis_support.resolve_import
    )
    assert repository_service.asciidoc_adapter.parse_dependencies_only is (
        repository_asciidoc_analysis_support.parse_dependencies_only
    )
    assert repository_service.asciidoc_adapter.parse_file is (
        repository_asciidoc_analysis_support.parse_file
    )


def test_asciidoc_adapter_module_aliases_include_anchors_and_sections(tmp_path: Path) -> None:
    repo_path = tmp_path / "asciidoc-alias-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "guide.adoc").write_text(
        "[[guide-anchor]]\n= Guide\n",
        encoding="utf-8",
    )

    aliases = repository_service.asciidoc_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="docs/guide.adoc",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "docs/guide.adoc" in aliases
    assert "guide-anchor" in aliases
    assert "guide.Guide" in aliases


def test_asciidoc_adapter_parse_file_resolves_include_and_xref(tmp_path: Path) -> None:
    repo_path = tmp_path / "asciidoc-parse-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "guide.adoc").write_text(
        "[[guide-anchor]]\n= Guide\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "index.adoc").write_text(
        "= Index\n\ninclude::guide.adoc[]\n\nxref:guide.adoc#guide-anchor[Guide]\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["docs/index.adoc", "docs/guide.adoc"],
        root_path=repo_path,
    )
    text = (repo_path / "docs" / "index.adoc").read_text(encoding="utf-8")

    dependencies = repository_service.asciidoc_adapter.parse_dependencies_only(
        "docs/index.adoc",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.asciidoc_adapter.parse_file(
        "docs/index.adoc",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "docs/guide.adoc" for dependency in dependencies)
    assert any(
        symbol.symbol_kind == "asciidoc" and symbol.symbol_name == "index" for symbol in symbols
    )
    assert any(
        reference.target_file == "docs/guide.adoc" and "guide-anchor" in reference.target_names
        for reference in references
    )


def test_asciidoc_language_detection_supports_suffixes() -> None:
    assert ".adoc" in repository_service._TEXT_FILE_SUFFIXES
    assert ".asciidoc" in repository_service._TEXT_FILE_SUFFIXES
    assert ".asc" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("docs/index.adoc"),
        text="= Index\n",
    ) == "asciidoc"


def test_operational_seed_plan_without_diagnostics_promotes_asciidoc_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "asciidoc-profile-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "index.adoc").write_text(
        "= Index\n\ninclude::guide.adoc[]\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "guide.adoc").write_text("= Guide\n", encoding="utf-8")
    (repo_path / "docs" / "reference.adoc").write_text("= Reference\n", encoding="utf-8")
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "tools" / "build.py").write_text("print('docs')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "asciidoc" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "asciidoc"
    assert "docs/index.adoc" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_asciidoc_first_in_python_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "asciidoc-mixed-python-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "index.adoc").write_text("= Index\n", encoding="utf-8")
    (repo_path / "docs" / "guide.adoc").write_text("= Guide\n", encoding="utf-8")
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

    assert "asciidoc" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "asciidoc"
    assert "python" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_asciidoc_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "asciidoc-graph-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "guide.adoc").write_text(
        "[[guide-anchor]]\n= Guide\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "index.adoc").write_text(
        "= Index\n\ninclude::guide.adoc[]\n\nxref:guide.adoc#guide-anchor[Guide]\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["docs/**/*.adoc", "docs/*.adoc", "*.adoc"],
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
        row
        for row in symbol_rows
        if row["symbol_name"] == "index" and row["file_path"] == "docs/index.adoc"
    )
    section_symbol = next(
        row
        for row in symbol_rows
        if row["symbol_name"] == "Index" and row["file_path"] == "docs/index.adoc"
    )
    guide_anchor_symbol = next(
        row
        for row in symbol_rows
        if row["symbol_name"] == "guide-anchor" and row["file_path"] == "docs/guide.adoc"
    )

    assert any(
        row["source_node"] == "file:docs/index.adoc"
        and row["target_node"] == "file:docs/guide.adoc"
        and row["edge_type"] == "include"
        for row in dependency_rows
    )
    assert any(
        row["source_node"] in {
            f"symbol:{root_symbol['symbol_id']}",
            f"symbol:{section_symbol['symbol_id']}",
        }
        and row["target_node"] == f"symbol:{guide_anchor_symbol['symbol_id']}"
        and row["edge_type"] == "references_symbol"
        for row in dependency_rows
    )
