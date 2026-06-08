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
    repository_intelligence_erb_parser_dispatch as repository_erb_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    erb_analysis_support as repository_erb_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    erb_primitives as repository_erb_primitives,
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


def test_repository_intelligence_erb_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["erb"] is (
        repository_erb_parser_dispatch._parse_erb_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["erb"] is (
        repository_erb_parser_dispatch._parse_erb_dependencies_only
    )


def test_repository_intelligence_erb_helpers_are_modularized() -> None:
    assert repository_service.erb_adapter.strip_comments is repository_erb_primitives.strip_comments
    assert repository_service.erb_adapter.has_erb_path_hints is (
        repository_erb_primitives.has_erb_path_hints
    )
    assert repository_service.erb_adapter.iter_dependency_entries is (
        repository_erb_primitives.iter_dependency_entries
    )
    assert repository_service.erb_adapter.iter_symbol_entries is (
        repository_erb_primitives.iter_symbol_entries
    )
    assert repository_service.erb_adapter.iter_reference_entries is (
        repository_erb_primitives.iter_reference_entries
    )
    assert repository_service.erb_adapter.resolve_import is repository_erb_primitives.resolve_import
    assert repository_service.erb_adapter.is_probable_erb_source is (
        repository_erb_analysis_support.is_probable_erb_source
    )
    assert repository_service.erb_adapter.module_aliases_for_path is (
        repository_erb_analysis_support.module_aliases_for_path
    )
    assert repository_service.erb_adapter.parse_dependencies_only is (
        repository_erb_analysis_support.parse_dependencies_only
    )
    assert repository_service.erb_adapter.parse_file is repository_erb_analysis_support.parse_file


def test_erb_adapter_module_aliases_include_template_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "erb-alias-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.erb").write_text(
        "<nav>Navigation</nav>\n",
        encoding="utf-8",
    )

    aliases = repository_service.erb_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="app/views/shared/_nav.html.erb",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "app/views/shared/_nav.html.erb" in aliases
    assert "shared._nav.html" in aliases


def test_erb_adapter_parse_file_resolves_partials_and_sections(tmp_path: Path) -> None:
    repo_path = tmp_path / "erb-parse-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.erb").write_text(
        "<nav>Navigation</nav>\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.erb").write_text(
        "<%= yield :sidebar %>\n"
        "<% content_for :sidebar do %>\n"
        "  <aside>Sidebar</aside>\n"
        "<% end %>\n"
        "<%= render \"shared/nav\" %>\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "app/views/pages/home.html.erb",
            "app/views/shared/_nav.html.erb",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "app" / "views" / "pages" / "home.html.erb").read_text(
        encoding="utf-8"
    )

    dependencies = repository_service.erb_adapter.parse_dependencies_only(
        "app/views/pages/home.html.erb",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.erb_adapter.parse_file(
        "app/views/pages/home.html.erb",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "app/views/shared/_nav.html.erb" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "sidebar" for symbol in symbols)
    assert any(
        reference.target_file == "app/views/pages/home.html.erb"
        and "sidebar" in reference.target_names
        for reference in references
    )


def test_erb_language_detection_supports_template_suffixes() -> None:
    assert ".erb" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("app/views/pages/home.html.erb"),
        text='<%= render "shared/nav" %>\n',
    ) == "erb"


def test_operational_seed_plan_without_diagnostics_promotes_erb_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "erb-profile-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.erb").write_text(
        "<nav>Navigation</nav>\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "layouts").mkdir(parents=True)
    (repo_path / "app" / "views" / "layouts" / "application.html.erb").write_text(
        "<html><body><%= yield %></body></html>\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.erb").write_text(
        "<%= render \"shared/nav\" %>\n<main>Home</main>\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages" / "about.html.erb").write_text(
        "<main>About</main>\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "assets").mkdir(parents=True)
    (repo_path / "app" / "assets" / "app.js").write_text("console.log('build')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "erb" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "erb"
    assert "app/views/pages/home.html.erb" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_erb_first_in_ruby_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "erb-mixed-ruby-repo"
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.erb").write_text(
        "<main>Home</main>\n",
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

    assert "erb" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "erb"
    assert "ruby" in seed_plan["operational_ecosystems"]


def test_operational_seed_plan_without_diagnostics_detects_erb_in_mixed_template_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "erb-mixed-template-repo"
    (repo_path / "sandbox" / "app" / "views" / "demos").mkdir(parents=True)
    for name in ("index", "classic", "inline", "form", "context", "multiroot"):
        (repo_path / "sandbox" / "app" / "views" / "demos" / f"{name}.html.erb").write_text(
            "<% content_for :head do %>\n"
            "  <%= stylesheet_link_tag 'demo' %>\n"
            "<% end %>\n"
            "<main>Demo</main>\n",
            encoding="utf-8",
        )
    (repo_path / "lib").mkdir(parents=True)
    for index in range(18):
        (repo_path / "lib" / f"service_{index}.rb").write_text(
            f"class Service{index}\n  def call = :ok\nend\n",
            encoding="utf-8",
        )
    (repo_path / "npm_package" / "src").mkdir(parents=True)
    for index in range(18):
        (repo_path / "npm_package" / "src" / f"entry_{index}.ts").write_text(
            f"export const entry{index} = {index};\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "erb" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "erb"


def test_repository_snapshot_graph_contains_erb_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "erb-graph-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.erb").write_text(
        "<nav>Navigation</nav>\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.erb").write_text(
        "<%= yield :sidebar %>\n"
        "<% content_for :sidebar do %>\n"
        "  <aside>Sidebar</aside>\n"
        "<% end %>\n"
        "<%= render \"shared/nav\" %>\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["app/views/**/*.erb", "app/views/*.erb", "*.erb"],
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
        if row["symbol_name"] == "sidebar" and row["file_path"] == "app/views/pages/home.html.erb"
    )
    root_symbol = next(
        row
        for row in symbol_rows
        if row["symbol_name"] == "pages.home.html"
        and row["file_path"] == "app/views/pages/home.html.erb"
    )

    assert any(
        row["source_node"] == "file:app/views/pages/home.html.erb"
        and row["target_node"] == "file:app/views/shared/_nav.html.erb"
        and row["edge_type"] in {"partial", "layout", "template"}
        for row in dependency_rows
    )
    assert any(
        row["source_node"] == f"symbol:{root_symbol['symbol_id']}"
        and row["target_node"] == f"symbol:{sidebar_symbol['symbol_id']}"
        and row["edge_type"] == "references_symbol"
        for row in dependency_rows
    )
