from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_handlebars_parser_dispatch as repository_handlebars_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    handlebars_analysis_support as repository_handlebars_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    handlebars_primitives as repository_handlebars_primitives,
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


def test_repository_intelligence_handlebars_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["handlebars"] is (
        repository_handlebars_parser_dispatch._parse_handlebars_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["handlebars"] is (
        repository_handlebars_parser_dispatch._parse_handlebars_dependencies_only
    )


def test_repository_intelligence_handlebars_helpers_are_modularized() -> None:
    assert repository_service.handlebars_adapter.strip_comments is (
        repository_handlebars_primitives.strip_comments
    )
    assert repository_service.handlebars_adapter.has_handlebars_path_hints is (
        repository_handlebars_primitives.has_handlebars_path_hints
    )
    assert repository_service.handlebars_adapter.iter_dependency_entries is (
        repository_handlebars_primitives.iter_dependency_entries
    )
    assert repository_service.handlebars_adapter.iter_reference_entries is (
        repository_handlebars_primitives.iter_reference_entries
    )
    assert repository_service.handlebars_adapter.resolve_import is (
        repository_handlebars_primitives.resolve_import
    )
    assert repository_service.handlebars_adapter.is_probable_handlebars_source is (
        repository_handlebars_analysis_support.is_probable_handlebars_source
    )
    assert repository_service.handlebars_adapter.module_aliases_for_path is (
        repository_handlebars_analysis_support.module_aliases_for_path
    )
    assert repository_service.handlebars_adapter.parse_dependencies_only is (
        repository_handlebars_analysis_support.parse_dependencies_only
    )
    assert repository_service.handlebars_adapter.parse_file is (
        repository_handlebars_analysis_support.parse_file
    )


def test_handlebars_adapter_module_aliases_include_path_and_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "handlebars-alias-repo"
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "partials" / "card.hbs").write_text("<article>{{title}}</article>\n", encoding="utf-8")

    aliases = repository_service.handlebars_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="partials/card.hbs",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "partials/card.hbs" in aliases
    assert "partials.card" in aliases
    assert "card" in aliases


def test_handlebars_adapter_parse_file_resolves_partial_dependencies(tmp_path: Path) -> None:
    repo_path = tmp_path / "handlebars-parse-repo"
    (repo_path / "layouts").mkdir(parents=True)
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "layouts" / "default.hbs").write_text("<html>{{> body}}</html>\n", encoding="utf-8")
    (repo_path / "partials" / "card.hbs").write_text("<article>{{title}}</article>\n", encoding="utf-8")
    (repo_path / "index.hbs").write_text('{{#> default}}\n{{> card}}\n{{/default}}\n', encoding="utf-8")
    module_index = repository_service._build_module_index(
        ["layouts/default.hbs", "partials/card.hbs", "index.hbs"],
        root_path=repo_path,
    )
    text = (repo_path / "index.hbs").read_text(encoding="utf-8")

    dependencies = repository_service.handlebars_adapter.parse_dependencies_only(
        "index.hbs",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.handlebars_adapter.parse_file(
        "index.hbs",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "layouts/default.hbs" for dependency in dependencies)
    assert any(dependency.target_file == "partials/card.hbs" for dependency in dependencies)
    assert any(symbol.symbol_name == "index" for symbol in symbols)
    assert any(
        reference.target_file == "partials/card.hbs" and "card" in reference.target_names
        for reference in references
    )


def test_handlebars_language_detection_supports_template_suffixes() -> None:
    assert repository_service._language_for_path(
        Path("templates/index.hbs"),
        text="{{> card}}\n",
    ) == "handlebars"
    assert repository_service._language_for_path(
        Path("templates/index.handlebars"),
        text="{{> card}}\n",
    ) == "handlebars"


def test_operational_seed_plan_without_diagnostics_promotes_handlebars_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "handlebars-profile-repo"
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "layouts").mkdir(parents=True)
    (repo_path / "partials" / "card.hbs").write_text("<article>{{title}}</article>\n", encoding="utf-8")
    (repo_path / "partials" / "hero.hbs").write_text("<section>{{headline}}</section>\n", encoding="utf-8")
    (repo_path / "layouts" / "default.hbs").write_text("<html>{{> body}}</html>\n", encoding="utf-8")
    (repo_path / "index.hbs").write_text('{{#> default}}\n{{> hero}}\n{{> card}}\n{{/default}}\n', encoding="utf-8")
    (repo_path / "assets").mkdir(parents=True)
    (repo_path / "assets" / "theme.js").write_text("console.log('theme')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "handlebars" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "handlebars"
    assert "index.hbs" in seed_plan["entrypoint_files"]
    assert "partials" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_does_not_force_handlebars_first_in_js_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "handlebars-mixed-js-repo"
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "partials" / "card.hbs").write_text("<article>{{title}}</article>\n", encoding="utf-8")
    (repo_path / "index.hbs").write_text("{{> card}}\n", encoding="utf-8")
    (repo_path / "package.json").write_text('{"name":"mixed-js","type":"module"}\n', encoding="utf-8")
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

    assert "handlebars" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "handlebars"
    assert "javascript" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_handlebars_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "handlebars-graph-repo"
    (repo_path / "layouts").mkdir(parents=True)
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "layouts" / "default.hbs").write_text("<html>{{> body}}</html>\n", encoding="utf-8")
    (repo_path / "partials" / "card.hbs").write_text("<article>{{title}}</article>\n", encoding="utf-8")
    (repo_path / "index.hbs").write_text('{{#> default}}\n{{> card}}\n{{/default}}\n', encoding="utf-8")
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=[
                "*.hbs",
                "*.handlebars",
                "partials/**/*.hbs",
                "partials/*.hbs",
                "layouts/**/*.hbs",
                "layouts/*.hbs",
            ],
        ),
    )

    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "partial"
        and str(row["source_node"]) == "file:index.hbs"
        and str(row["target_node"]) == "file:layouts/default.hbs"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "partial"
        and str(row["source_node"]) == "file:index.hbs"
        and str(row["target_node"]) == "file:partials/card.hbs"
        for row in graph_rows
    )
    index_symbol_id = symbol_ids[("index.hbs", "index")]
    card_symbol_id = symbol_ids[("partials/card.hbs", "card")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{index_symbol_id}"
        and str(row["target_node"]) == f"symbol:{card_symbol_id}"
        for row in graph_rows
    )
