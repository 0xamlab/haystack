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
    repository_intelligence_ejs_parser_dispatch as repository_ejs_parser_dispatch,
)
from apps.api_server.services import repository_intelligence_file_selection
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    ejs_analysis_support as repository_ejs_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ejs_primitives as repository_ejs_primitives,
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


def test_repository_intelligence_ejs_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["ejs"] is (
        repository_ejs_parser_dispatch._parse_ejs_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["ejs"] is (
        repository_ejs_parser_dispatch._parse_ejs_dependencies_only
    )


def test_repository_intelligence_ejs_helpers_are_modularized() -> None:
    assert repository_service.ejs_adapter.strip_comments is repository_ejs_primitives.strip_comments
    assert repository_service.ejs_adapter.has_ejs_path_hints is (
        repository_ejs_primitives.has_ejs_path_hints
    )
    assert repository_service.ejs_adapter.iter_dependency_entries is (
        repository_ejs_primitives.iter_dependency_entries
    )
    assert repository_service.ejs_adapter.iter_reference_entries is (
        repository_ejs_primitives.iter_reference_entries
    )
    assert repository_service.ejs_adapter.resolve_import is repository_ejs_primitives.resolve_import
    assert repository_service.ejs_adapter.is_probable_ejs_source is (
        repository_ejs_analysis_support.is_probable_ejs_source
    )
    assert repository_service.ejs_adapter.module_aliases_for_path is (
        repository_ejs_analysis_support.module_aliases_for_path
    )
    assert repository_service.ejs_adapter.parse_dependencies_only is (
        repository_ejs_analysis_support.parse_dependencies_only
    )
    assert repository_service.ejs_adapter.parse_file is (
        repository_ejs_analysis_support.parse_file
    )


def test_ejs_adapter_module_aliases_include_path_and_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "ejs-alias-repo"
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "partials" / "card.ejs").write_text(
        "<article><%= title %></article>\n",
        encoding="utf-8",
    )

    aliases = repository_service.ejs_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="partials/card.ejs",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "partials/card.ejs" in aliases
    assert "partials.card" in aliases
    assert "card" in aliases


def test_ejs_adapter_parse_file_resolves_include_dependencies_and_function_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ejs-parse-repo"
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "partials" / "card.ejs").write_text(
        "<article><%= title %></article>\n",
        encoding="utf-8",
    )
    (repo_path / "views").mkdir(parents=True)
    (repo_path / "views" / "index.ejs").write_text(
        "<%\nfunction renderCard() { return include('../partials/card'); }\n%>\n"
        "<%= include('../partials/card') %>\n<%= renderCard() %>\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["partials/card.ejs", "views/index.ejs"],
        root_path=repo_path,
    )
    text = (repo_path / "views" / "index.ejs").read_text(encoding="utf-8")

    dependencies = repository_service.ejs_adapter.parse_dependencies_only(
        "views/index.ejs",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.ejs_adapter.parse_file(
        "views/index.ejs",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "partials/card.ejs" for dependency in dependencies)
    assert any(symbol.symbol_name == "index" for symbol in symbols)
    assert any(symbol.symbol_name == "renderCard" for symbol in symbols)
    assert any(
        reference.target_file == "partials/card.ejs" and "card" in reference.target_names
        for reference in references
    )
    assert any(
        reference.target_file == "views/index.ejs" and reference.target_names == ("renderCard",)
        for reference in references
    )


def test_ejs_language_detection_supports_ejs_suffix() -> None:
    assert ".ejs" in repository_intelligence_file_selection.TEXT_FILE_SUFFIXES

    assert repository_service._language_for_path(
        Path("views/index.ejs"),
        text="<%= include('partials/card') %>\n",
    ) == "ejs"


def test_operational_seed_plan_without_diagnostics_promotes_ejs_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ejs-profile-repo"
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "views").mkdir(parents=True)
    (repo_path / "partials" / "card.ejs").write_text(
        "<article><%= title %></article>\n",
        encoding="utf-8",
    )
    (repo_path / "partials" / "hero.ejs").write_text(
        "<section><%= headline %></section>\n",
        encoding="utf-8",
    )
    (repo_path / "views" / "index.ejs").write_text(
        "<%= include('../partials/hero') %>\n<%= include('../partials/card') %>\n",
        encoding="utf-8",
    )
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "public" / "theme.js").write_text("console.log('theme')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "ejs" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "ejs"
    assert "views/index.ejs" in seed_plan["entrypoint_files"]
    assert "partials" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_does_not_force_ejs_first_in_js_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ejs-mixed-js-repo"
    (repo_path / "views").mkdir(parents=True)
    (repo_path / "views" / "index.ejs").write_text("<h1><%= title %></h1>\n", encoding="utf-8")
    (repo_path / "package.json").write_text('{"name":"mixed-ejs","type":"module"}\n', encoding="utf-8")
    (repo_path / "src").mkdir(parents=True)
    for index in range(24):
        (repo_path / "src" / f"page_{index}.js").write_text(
            f"export function page{index}() {{ return 'demo'; }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "ejs" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "ejs"
    assert "javascript" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_ejs_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "ejs-graph-repo"
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "partials" / "card.ejs").write_text(
        "<article><%= title %></article>\n",
        encoding="utf-8",
    )
    (repo_path / "views").mkdir(parents=True)
    (repo_path / "views" / "index.ejs").write_text(
        "<%\nfunction renderCard() { return include('../partials/card'); }\n%>\n"
        "<%= include('../partials/card') %>\n<%= renderCard() %>\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.ejs", "views/**/*.ejs", "partials/**/*.ejs", "partials/*.ejs"],
            max_files=16,
        ),
    )

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "include"
        and str(row["source_node"]) == "file:views/index.ejs"
        and str(row["target_node"]) == "file:partials/card.ejs"
        for row in graph_rows
    )
    index_symbol_id = symbol_ids[("views/index.ejs", "index")]
    card_symbol_id = symbol_ids[("partials/card.ejs", "card")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{index_symbol_id}"
        and str(row["target_node"]) == f"symbol:{card_symbol_id}"
        for row in graph_rows
    )
