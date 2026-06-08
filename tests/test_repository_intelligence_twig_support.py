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
    repository_intelligence_twig_parser_dispatch as repository_twig_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    twig_analysis_support as repository_twig_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    twig_primitives as repository_twig_primitives,
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


def test_repository_intelligence_twig_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["twig"] is (
        repository_twig_parser_dispatch._parse_twig_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["twig"] is (
        repository_twig_parser_dispatch._parse_twig_dependencies_only
    )


def test_repository_intelligence_twig_helpers_are_modularized() -> None:
    assert repository_service.twig_adapter.strip_comments is repository_twig_primitives.strip_comments
    assert repository_service.twig_adapter.has_twig_path_hints is (
        repository_twig_primitives.has_twig_path_hints
    )
    assert repository_service.twig_adapter.iter_dependency_entries is (
        repository_twig_primitives.iter_dependency_entries
    )
    assert repository_service.twig_adapter.iter_symbol_entries is (
        repository_twig_primitives.iter_symbol_entries
    )
    assert repository_service.twig_adapter.iter_reference_entries is (
        repository_twig_primitives.iter_reference_entries
    )
    assert repository_service.twig_adapter.resolve_import is repository_twig_primitives.resolve_import
    assert repository_service.twig_adapter.is_probable_twig_source is (
        repository_twig_analysis_support.is_probable_twig_source
    )
    assert repository_service.twig_adapter.module_aliases_for_path is (
        repository_twig_analysis_support.module_aliases_for_path
    )
    assert repository_service.twig_adapter.parse_dependencies_only is (
        repository_twig_analysis_support.parse_dependencies_only
    )
    assert repository_service.twig_adapter.parse_file is repository_twig_analysis_support.parse_file


def test_twig_adapter_module_aliases_include_template_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "twig-alias-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "partials" / "macros.html.twig").write_text(
        "{% macro render_button(label) %}\n"
        "  <button>{{ label }}</button>\n"
        "{% endmacro %}\n",
        encoding="utf-8",
    )

    aliases = repository_service.twig_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="templates/partials/macros.html.twig",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "templates/partials/macros.html.twig" in aliases
    assert "partials.macros.html" in aliases
    assert "render_button" in aliases


def test_twig_adapter_parse_file_resolves_imports_includes_and_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "twig-parse-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "partials" / "macros.html.twig").write_text(
        "{% macro render_button(label) %}\n"
        "  <button>{{ label }}</button>\n"
        "{% endmacro %}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "base.html.twig").write_text(
        "<html>{% block body %}{% endblock %}</html>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "index.html.twig").write_text(
        '{% extends "templates/base.html.twig" %}\n'
        '{% import "templates/partials/macros.html.twig" as macros %}\n'
        '{% block body %}{{ macros.render_button("Ship it") }}{% endblock %}\n',
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "templates/index.html.twig",
            "templates/base.html.twig",
            "templates/partials/macros.html.twig",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "templates" / "index.html.twig").read_text(encoding="utf-8")

    dependencies = repository_service.twig_adapter.parse_dependencies_only(
        "templates/index.html.twig",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.twig_adapter.parse_file(
        "templates/index.html.twig",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "templates/base.html.twig" for dependency in dependencies)
    assert any(
        dependency.target_file == "templates/partials/macros.html.twig"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "index.html" for symbol in symbols)
    assert any(
        reference.target_file == "templates/partials/macros.html.twig"
        and "render_button" in reference.target_names
        for reference in references
    )


def test_twig_language_detection_supports_template_suffixes() -> None:
    assert ".twig" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("templates/index.html.twig"),
        text='{{ greeting }}\n{% include "templates/footer.html.twig" %}\n',
    ) == "twig"


def test_operational_seed_plan_without_diagnostics_promotes_twig_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "twig-profile-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "partials" / "macros.html.twig").write_text(
        "{% macro render_button(label) %}<button>{{ label }}</button>{% endmacro %}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "base.html.twig").write_text(
        "<html>{% block body %}{% endblock %}</html>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "index.html.twig").write_text(
        '{% extends "templates/base.html.twig" %}\n'
        '{% import "templates/partials/macros.html.twig" as macros %}\n'
        '{% block body %}{{ macros.render_button("Ship it") }}{% endblock %}\n',
        encoding="utf-8",
    )
    (repo_path / "templates" / "about.html.twig").write_text(
        '{% extends "templates/base.html.twig" %}\n{% block body %}<p>About</p>{% endblock %}\n',
        encoding="utf-8",
    )
    (repo_path / "assets").mkdir(parents=True)
    (repo_path / "assets" / "app.js").write_text("console.log('build')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "twig" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "twig"
    assert "templates/index.html.twig" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_twig_first_in_php_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "twig-mixed-php-repo"
    (repo_path / "templates").mkdir(parents=True)
    (repo_path / "templates" / "page.html.twig").write_text(
        "{{ render_user(name) }}\n",
        encoding="utf-8",
    )
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "App.php").write_text(
        "<?php\n"
        "require_once __DIR__ . '/Helper0.php';\n"
        "final class App { public function run(): string { return helper0('demo'); } }\n",
        encoding="utf-8",
    )
    for index in range(24):
        (repo_path / "src" / f"Helper{index}.php").write_text(
            "<?php\n"
            f"function helper{index}(string $name): string {{ return strtoupper($name); }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "twig" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "twig"
    assert "php" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_twig_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "twig-graph-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "partials" / "macros.html.twig").write_text(
        "{% macro render_button(label) %}\n"
        "  <button>{{ label }}</button>\n"
        "{% endmacro %}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "index.html.twig").write_text(
        '{% import "templates/partials/macros.html.twig" as macros %}\n'
        '{{ macros.render_button("Ship it") }}\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.twig", "templates/**/*.twig", "templates/*.twig"],
            max_files=16,
        ),
    )
    edge_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:templates/index.html.twig"
        and str(row["target_node"]) == "file:templates/partials/macros.html.twig"
        for row in edge_rows
    )

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"]) for row in symbol_rows
    }
    index_symbol_id = symbol_ids[("templates/index.html.twig", "index.html")]
    macro_symbol_id = symbol_ids[("templates/partials/macros.html.twig", "render_button")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{index_symbol_id}"
        and str(row["target_node"]) == f"symbol:{macro_symbol_id}"
        for row in edge_rows
    )
