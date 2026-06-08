from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_file_selection,
)
from apps.api_server.services import (
    repository_intelligence_mustache_parser_dispatch as repository_mustache_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    mustache_analysis_support as repository_mustache_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    mustache_primitives as repository_mustache_primitives,
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


def test_repository_intelligence_mustache_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["mustache"] is (
        repository_mustache_parser_dispatch._parse_mustache_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["mustache"] is (
        repository_mustache_parser_dispatch._parse_mustache_dependencies_only
    )


def test_repository_intelligence_mustache_helpers_are_modularized() -> None:
    assert repository_service.mustache_adapter.strip_comments is repository_mustache_primitives.strip_comments
    assert repository_service.mustache_adapter.has_mustache_path_hints is (
        repository_mustache_primitives.has_mustache_path_hints
    )
    assert repository_service.mustache_adapter.iter_dependency_entries is (
        repository_mustache_primitives.iter_dependency_entries
    )
    assert repository_service.mustache_adapter.iter_reference_entries is (
        repository_mustache_primitives.iter_reference_entries
    )
    assert repository_service.mustache_adapter.iter_section_entries is (
        repository_mustache_primitives.iter_section_entries
    )
    assert repository_service.mustache_adapter.resolve_import is (
        repository_mustache_primitives.resolve_import
    )
    assert repository_service.mustache_adapter.is_probable_mustache_source is (
        repository_mustache_analysis_support.is_probable_mustache_source
    )
    assert repository_service.mustache_adapter.module_aliases_for_path is (
        repository_mustache_analysis_support.module_aliases_for_path
    )
    assert repository_service.mustache_adapter.parse_dependencies_only is (
        repository_mustache_analysis_support.parse_dependencies_only
    )
    assert repository_service.mustache_adapter.parse_file is (
        repository_mustache_analysis_support.parse_file
    )


def test_mustache_adapter_module_aliases_include_template_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "mustache-alias-repo"
    (repo_path / "templates" / "layouts").mkdir(parents=True)
    (repo_path / "templates" / "layouts" / "app.mustache").write_text(
        "<html>{{$content}}{{/content}}</html>\n",
        encoding="utf-8",
    )

    aliases = repository_service.mustache_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="templates/layouts/app.mustache",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "templates/layouts/app.mustache" in aliases
    assert "templates/layouts/app" in aliases
    assert "layouts.app" in aliases


def test_mustache_adapter_parse_file_resolves_template_dependencies_and_section_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mustache-parse-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "layouts").mkdir(parents=True)
    (repo_path / "templates" / "layouts" / "app.mustache").write_text(
        "<html>{{#content}}{{content}}{{/content}}</html>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "partials" / "card.mustache").write_text(
        "<article>{{title}}</article>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "home.mustache").write_text(
        "{{> layouts/app}}\n"
        "{{> partials/card}}\n"
        "{{#content}}\n"
        "  {{content}}\n"
        "{{/content}}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "templates/layouts/app.mustache",
            "templates/partials/card.mustache",
            "templates/home.mustache",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "templates" / "home.mustache").read_text(encoding="utf-8")

    dependencies = repository_service.mustache_adapter.parse_dependencies_only(
        "templates/home.mustache",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.mustache_adapter.parse_file(
        "templates/home.mustache",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "templates/layouts/app.mustache" for dependency in dependencies
    )
    assert any(
        dependency.target_file == "templates/partials/card.mustache" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "home" for symbol in symbols)
    assert any(symbol.symbol_name == "content" for symbol in symbols)
    assert any(
        reference.target_file == "templates/layouts/app.mustache"
        and "layouts.app" in reference.target_names
        for reference in references
    )
    assert any(
        reference.target_file == "templates/home.mustache"
        and reference.target_names == ("content",)
        for reference in references
    )


def test_mustache_language_detection_supports_mustache_suffix() -> None:
    assert ".mustache" in repository_intelligence_file_selection.TEXT_FILE_SUFFIXES

    assert repository_service._language_for_path(
        Path("templates/home.mustache"),
        text="{{#content}}{{content}}{{/content}}\n",
    ) == "mustache"


def test_operational_seed_plan_without_diagnostics_promotes_mustache_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mustache-profile-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "partials" / "card.mustache").write_text(
        "<article>{{title}}</article>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "layout.mustache").write_text(
        "{{#content}}{{content}}{{/content}}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "index.mustache").write_text(
        "{{> partials/card}}\n{{#content}}{{content}}{{/content}}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "page.mustache").write_text(
        "{{> partials/card}}\n{{title}}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "mustache" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "mustache"
    assert any(path.endswith(".mustache") for path in seed_plan["candidate_file_paths"])
    assert any(root.startswith("templates") for root in seed_plan["support_roots"])


def test_operational_seed_plan_without_diagnostics_does_not_force_mustache_first_in_js_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mustache-mixed-js-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "templates").mkdir(parents=True)
    (repo_path / "src" / "app.ts").write_text("export const app = 1;\n", encoding="utf-8")
    (repo_path / "src" / "main.ts").write_text("import { app } from './app';\nconsole.log(app);\n", encoding="utf-8")
    (repo_path / "src" / "router.ts").write_text("export const routes = [];\n", encoding="utf-8")
    (repo_path / "templates" / "index.mustache").write_text("{{title}}\n", encoding="utf-8")
    (repo_path / "package.json").write_text('{"name":"mixed-js"}\n', encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "mustache" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "mustache"


def test_repository_snapshot_graph_contains_mustache_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "mustache-snapshot-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "partials" / "card.mustache").write_text(
        "<article>{{title}}</article>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "index.mustache").write_text(
        "{{> partials/card}}\n{{#title}}{{title}}{{/title}}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.mustache", "templates/**/*.mustache", "templates/*.mustache"],
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
        str(row["edge_type"]) == "partial"
        and str(row["source_node"]) == "file:templates/index.mustache"
        and str(row["target_node"]) == "file:templates/partials/card.mustache"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"])
        == f"symbol:{symbol_ids[('templates/index.mustache', 'index')]}"
        and str(row["target_node"])
        == f"symbol:{symbol_ids[('templates/partials/card.mustache', 'partials.card')]}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "contains_symbol"
        and str(row["source_node"])
        == f"symbol:{symbol_ids[('templates/index.mustache', 'index')]}"
        and str(row["target_node"])
        == f"symbol:{symbol_ids[('templates/index.mustache', 'title')]}"
        for row in graph_rows
    )
