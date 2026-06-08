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
    repository_intelligence_slim_parser_dispatch as repository_slim_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    slim_analysis_support as repository_slim_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    slim_primitives as repository_slim_primitives,
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


def test_repository_intelligence_slim_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["slim"] is (
        repository_slim_parser_dispatch._parse_slim_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["slim"] is (
        repository_slim_parser_dispatch._parse_slim_dependencies_only
    )


def test_repository_intelligence_slim_helpers_are_modularized() -> None:
    assert repository_service.slim_adapter.strip_comments is repository_slim_primitives.strip_comments
    assert repository_service.slim_adapter.has_slim_path_hints is (
        repository_slim_primitives.has_slim_path_hints
    )
    assert repository_service.slim_adapter.iter_dependency_entries is (
        repository_slim_primitives.iter_dependency_entries
    )
    assert repository_service.slim_adapter.iter_symbol_entries is (
        repository_slim_primitives.iter_symbol_entries
    )
    assert repository_service.slim_adapter.iter_reference_entries is (
        repository_slim_primitives.iter_reference_entries
    )
    assert repository_service.slim_adapter.resolve_import is repository_slim_primitives.resolve_import
    assert repository_service.slim_adapter.is_probable_slim_source is (
        repository_slim_analysis_support.is_probable_slim_source
    )
    assert repository_service.slim_adapter.module_aliases_for_path is (
        repository_slim_analysis_support.module_aliases_for_path
    )
    assert repository_service.slim_adapter.parse_dependencies_only is (
        repository_slim_analysis_support.parse_dependencies_only
    )
    assert repository_service.slim_adapter.parse_file is repository_slim_analysis_support.parse_file


def test_slim_adapter_module_aliases_include_template_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "slim-alias-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.slim").write_text(
        "nav Navigation\n",
        encoding="utf-8",
    )

    aliases = repository_service.slim_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="app/views/shared/_nav.html.slim",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "app/views/shared/_nav.html.slim" in aliases
    assert "shared._nav.html" in aliases


def test_slim_adapter_parse_file_resolves_partials_and_sections(tmp_path: Path) -> None:
    repo_path = tmp_path / "slim-parse-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.slim").write_text(
        "nav Navigation\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.slim").write_text(
        '= yield :sidebar\n'
        '- content_for :sidebar do\n'
        '  aside Sidebar\n'
        '= render "shared/nav"\n',
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "app/views/pages/home.html.slim",
            "app/views/shared/_nav.html.slim",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "app" / "views" / "pages" / "home.html.slim").read_text(
        encoding="utf-8"
    )

    dependencies = repository_service.slim_adapter.parse_dependencies_only(
        "app/views/pages/home.html.slim",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.slim_adapter.parse_file(
        "app/views/pages/home.html.slim",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "app/views/shared/_nav.html.slim" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "sidebar" for symbol in symbols)
    assert any(
        reference.target_file == "app/views/pages/home.html.slim"
        and "sidebar" in reference.target_names
        for reference in references
    )


def test_slim_language_detection_supports_template_suffixes() -> None:
    assert ".slim" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("app/views/pages/home.html.slim"),
        text='main\n  = render "shared/nav"\n',
    ) == "slim"


def test_operational_seed_plan_without_diagnostics_promotes_slim_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "slim-profile-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.slim").write_text(
        "nav Navigation\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "layouts").mkdir(parents=True)
    (repo_path / "app" / "views" / "layouts" / "application.html.slim").write_text(
        "html\n  body = yield\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.slim").write_text(
        '= render "shared/nav"\nmain Home\n',
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages" / "about.html.slim").write_text(
        "main About\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "assets").mkdir(parents=True)
    (repo_path / "app" / "assets" / "app.js").write_text("console.log('build')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "slim" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "slim"
    assert "app/views/pages/home.html.slim" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_slim_first_in_ruby_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "slim-mixed-ruby-repo"
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.slim").write_text(
        "main Home\n",
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

    assert "slim" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "slim"
    assert "ruby" in seed_plan["operational_ecosystems"]


def test_operational_seed_plan_without_diagnostics_detects_slim_in_mixed_template_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "slim-mixed-template-repo"
    (repo_path / "sandbox" / "app" / "views" / "demos").mkdir(parents=True)
    for name in ("index", "classic", "inline", "form", "context", "multiroot"):
        (repo_path / "sandbox" / "app" / "views" / "demos" / f"{name}.slim").write_text(
            '- content_for :head\n'
            '  = assets_tag\n'
            'main Demo\n',
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

    assert "slim" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "slim"


def test_repository_snapshot_graph_contains_slim_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "slim-graph-repo"
    (repo_path / "app" / "views" / "shared").mkdir(parents=True)
    (repo_path / "app" / "views" / "shared" / "_nav.html.slim").write_text(
        "nav Navigation\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "views" / "pages").mkdir(parents=True)
    (repo_path / "app" / "views" / "pages" / "home.html.slim").write_text(
        '= yield :sidebar\n'
        '- content_for :sidebar do\n'
        '  aside Sidebar\n'
        '= render "shared/nav"\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["app/views/**/*.slim", "app/views/*.slim", "*.slim"],
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
        if row["symbol_name"] == "sidebar" and row["file_path"] == "app/views/pages/home.html.slim"
    )
    root_symbol = next(
        row
        for row in symbol_rows
        if row["symbol_name"] == "pages.home.html"
        and row["file_path"] == "app/views/pages/home.html.slim"
    )

    assert any(
        row["source_node"] == "file:app/views/pages/home.html.slim"
        and row["target_node"] == "file:app/views/shared/_nav.html.slim"
        and row["edge_type"] in {"partial", "layout"}
        for row in dependency_rows
    )
    assert any(
        row["source_node"] == f"symbol:{root_symbol['symbol_id']}"
        and row["target_node"] == f"symbol:{sidebar_symbol['symbol_id']}"
        and row["edge_type"] == "references_symbol"
        for row in dependency_rows
    )
