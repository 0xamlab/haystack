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
    repository_intelligence_haml_parser_dispatch as repository_haml_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    haml_analysis_support as repository_haml_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    haml_primitives as repository_haml_primitives,
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


def test_repository_intelligence_haml_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["haml"] is (
        repository_haml_parser_dispatch._parse_haml_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["haml"] is (
        repository_haml_parser_dispatch._parse_haml_dependencies_only
    )


def test_repository_intelligence_haml_helpers_are_modularized() -> None:
    assert repository_service.haml_adapter.strip_comments is repository_haml_primitives.strip_comments
    assert repository_service.haml_adapter.has_haml_path_hints is (
        repository_haml_primitives.has_haml_path_hints
    )
    assert repository_service.haml_adapter.iter_dependency_entries is (
        repository_haml_primitives.iter_dependency_entries
    )
    assert repository_service.haml_adapter.iter_symbol_entries is (
        repository_haml_primitives.iter_symbol_entries
    )
    assert repository_service.haml_adapter.iter_reference_entries is (
        repository_haml_primitives.iter_reference_entries
    )
    assert repository_service.haml_adapter.resolve_import is repository_haml_primitives.resolve_import
    assert repository_service.haml_adapter.is_probable_haml_source is (
        repository_haml_analysis_support.is_probable_haml_source
    )
    assert repository_service.haml_adapter.module_aliases_for_path is (
        repository_haml_analysis_support.module_aliases_for_path
    )
    assert repository_service.haml_adapter.parse_dependencies_only is (
        repository_haml_analysis_support.parse_dependencies_only
    )
    assert repository_service.haml_adapter.parse_file is repository_haml_analysis_support.parse_file


def test_haml_adapter_module_aliases_include_template_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "haml-alias-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.haml").write_text(
        "%nav Navigation\n",
        encoding="utf-8",
    )

    aliases = repository_service.haml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="app/views/shared/_nav.html.haml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "app/views/shared/_nav.html.haml" in aliases
    assert "shared._nav.html" in aliases


def test_haml_adapter_parse_file_resolves_partials_and_sections(tmp_path: Path) -> None:
    repo_path = tmp_path / "haml-parse-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.haml").write_text(
        "%nav Navigation\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.haml").write_text(
        '= yield :sidebar\n'
        '- content_for :sidebar do\n'
        '  %aside Sidebar\n'
        '= render "shared/nav"\n',
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "app/views/pages/home.html.haml",
            "app/views/shared/_nav.html.haml",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "app" / "views" / "pages" / "home.html.haml").read_text(
        encoding="utf-8"
    )

    dependencies = repository_service.haml_adapter.parse_dependencies_only(
        "app/views/pages/home.html.haml",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.haml_adapter.parse_file(
        "app/views/pages/home.html.haml",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "app/views/shared/_nav.html.haml" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "sidebar" for symbol in symbols)
    assert any(
        reference.target_file == "app/views/pages/home.html.haml"
        and "sidebar" in reference.target_names
        for reference in references
    )


def test_haml_language_detection_supports_template_suffixes() -> None:
    assert ".haml" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("app/views/pages/home.html.haml"),
        text='%main\n  = render "shared/nav"\n',
    ) == "haml"


def test_operational_seed_plan_without_diagnostics_promotes_haml_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haml-profile-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.haml").write_text(
        "%nav Navigation\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "layouts").mkdir(parents=True)
    (repo_path / "app" / "views" / "layouts" / "application.html.haml").write_text(
        "%html\n  %body= yield\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.haml").write_text(
        '= render "shared/nav"\n%main Home\n',
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages" / "about.html.haml").write_text(
        "%main About\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "assets").mkdir(parents=True)
    (repo_path / "app" / "assets" / "app.js").write_text("console.log('build')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "haml" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "haml"
    assert "app/views/pages/home.html.haml" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_haml_first_in_ruby_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haml-mixed-ruby-repo"
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.haml").write_text(
        "%main Home\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "models").mkdir(parents=True)
    for index in range(24):
        (repo_path / "app" / "models" / f"model_{index}.rb").write_text(
            f"class Model{index}\n  def call = :ok\nend\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "haml" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "haml"
    assert "ruby" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_haml_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "haml-graph-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.haml").write_text(
        "%nav Navigation\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.haml").write_text(
        '= yield :sidebar\n'
        '- content_for :sidebar do\n'
        '  %aside Sidebar\n'
        '= render "shared/nav"\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["app/views/**/*.haml", "app/views/*.haml", "*.haml"],
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

    sidebar_symbol = next(
        row
        for row in symbol_rows
        if row["symbol_name"] == "sidebar" and row["file_path"] == "app/views/pages/home.html.haml"
    )
    root_symbol = next(
        row
        for row in symbol_rows
        if row["symbol_name"] == "pages.home.html"
        and row["file_path"] == "app/views/pages/home.html.haml"
    )

    assert any(
        row["source_node"] == "file:app/views/pages/home.html.haml"
        and row["target_node"] == "file:app/views/shared/_nav.html.haml"
        and row["edge_type"] in {"partial", "layout"}
        for row in dependency_rows
    )
    assert any(
        row["source_node"] == f"symbol:{root_symbol['symbol_id']}"
        and row["target_node"] == f"symbol:{sidebar_symbol['symbol_id']}"
        and row["edge_type"] == "references_symbol"
        for row in dependency_rows
    )
