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
    repository_intelligence_xslt_parser_dispatch as repository_intelligence_xslt_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    xslt_analysis_support as repository_xslt_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    xslt_primitives as repository_xslt_primitives,
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


def test_repository_intelligence_xslt_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["xslt"] is (
        repository_intelligence_xslt_parser_dispatch._parse_xslt_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["xslt"] is (
        repository_intelligence_xslt_parser_dispatch._parse_xslt_dependencies_only
    )


def test_repository_intelligence_xslt_helpers_are_modularized() -> None:
    assert repository_service.xslt_adapter.has_xslt_path_hints is (
        repository_xslt_primitives.has_xslt_path_hints
    )
    assert repository_service.xslt_adapter.is_probable_xslt_source is (
        repository_xslt_analysis_support.is_probable_xslt_source
    )
    assert repository_service.xslt_adapter.iter_dependency_entries is (
        repository_xslt_primitives.iter_dependency_entries
    )
    assert repository_service.xslt_adapter.module_aliases_for_path is (
        repository_xslt_analysis_support.module_aliases_for_path
    )
    assert repository_service.xslt_adapter.parse_file is (
        repository_xslt_analysis_support.parse_file
    )


def test_xslt_adapter_parse_file_extracts_import_dependencies_and_template_references() -> None:
    module_index = {
        "lib/common.xsl": "lib/common.xsl",
        "common.xsl": "lib/common.xsl",
    }
    text = (
        '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">\n'
        '  <xsl:import href="../lib/common.xsl"/>\n'
        '  <xsl:template name="Helper"/>\n'
        '  <xsl:template name="Runner">\n'
        '    <xsl:call-template name="Helper"/>\n'
        "  </xsl:template>\n"
        "</xsl:stylesheet>\n"
    )

    symbols, dependencies, references = repository_service.xslt_adapter.parse_file(
        "styles/main.xsl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "lib/common.xsl" for dependency in dependencies)
    assert any(symbol.symbol_name == "Helper" for symbol in symbols)
    assert any(symbol.symbol_name == "Runner" for symbol in symbols)
    assert any(reference.target_names == ("Helper",) for reference in references)
    assert any(reference.target_file == "lib/common.xsl" for reference in references)


def test_xslt_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".xsl" in repository_service._TEXT_FILE_SUFFIXES
    assert ".xslt" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("styles/main.xsl"),
            text=(
                '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">\n'
                '  <xsl:template name="Helper"/>\n'
                "</xsl:stylesheet>\n"
            ),
        )
        == "xslt"
    )
    assert (
        repository_service._language_for_path(
            Path("styles/main.xsl"),
            text="plain notes without stylesheet markers\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_xslt_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "xslt-profile-repo"
    (repo_path / "xsl").mkdir(parents=True)
    for index in range(6):
        (repo_path / "xsl" / f"sheet_{index}.xsl").write_text(
            '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">\n'
            f'  <xsl:template name="Template{index}"/>\n'
            "</xsl:stylesheet>\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    for index in range(2):
        (repo_path / "tools" / f"helper_{index}.py").write_text(
            "print('helper')\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "xslt" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "xslt"


def test_repository_snapshot_graph_contains_xslt_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "xslt-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.xsl").write_text(
        '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">\n'
        '  <xsl:template name="Helper"/>\n'
        '  <xsl:template name="Runner">\n'
        '    <xsl:call-template name="Helper"/>\n'
        "  </xsl:template>\n"
        "</xsl:stylesheet>\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.xsl", "*.xslt"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    runner_symbol_id = symbol_ids[("main.xsl", "Runner")]
    helper_symbol_id = symbol_ids[("main.xsl", "Helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{runner_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
