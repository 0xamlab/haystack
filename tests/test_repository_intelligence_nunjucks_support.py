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
    repository_intelligence_nunjucks_parser_dispatch as repository_nunjucks_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    nunjucks_analysis_support as repository_nunjucks_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    nunjucks_primitives as repository_nunjucks_primitives,
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


def test_repository_intelligence_nunjucks_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["nunjucks"] is (
        repository_nunjucks_parser_dispatch._parse_nunjucks_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["nunjucks"] is (
        repository_nunjucks_parser_dispatch._parse_nunjucks_dependencies_only
    )


def test_repository_intelligence_nunjucks_helpers_are_modularized() -> None:
    assert repository_service.nunjucks_adapter.strip_comments is (
        repository_nunjucks_primitives.strip_comments
    )
    assert repository_service.nunjucks_adapter.has_nunjucks_path_hints is (
        repository_nunjucks_primitives.has_nunjucks_path_hints
    )
    assert repository_service.nunjucks_adapter.iter_dependency_entries is (
        repository_nunjucks_primitives.iter_dependency_entries
    )
    assert repository_service.nunjucks_adapter.iter_symbol_entries is (
        repository_nunjucks_primitives.iter_symbol_entries
    )
    assert repository_service.nunjucks_adapter.iter_reference_entries is (
        repository_nunjucks_primitives.iter_reference_entries
    )
    assert repository_service.nunjucks_adapter.resolve_import is (
        repository_nunjucks_primitives.resolve_import
    )
    assert repository_service.nunjucks_adapter.is_probable_nunjucks_source is (
        repository_nunjucks_analysis_support.is_probable_nunjucks_source
    )
    assert repository_service.nunjucks_adapter.module_aliases_for_path is (
        repository_nunjucks_analysis_support.module_aliases_for_path
    )
    assert repository_service.nunjucks_adapter.parse_dependencies_only is (
        repository_nunjucks_analysis_support.parse_dependencies_only
    )
    assert repository_service.nunjucks_adapter.parse_file is (
        repository_nunjucks_analysis_support.parse_file
    )


def test_nunjucks_adapter_module_aliases_include_template_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "nunjucks-alias-repo"
    (repo_path / "_includes" / "partials").mkdir(parents=True)
    (repo_path / "_includes" / "partials" / "macros.njk").write_text(
        "{% macro render_button(label) %}\n"
        "  <button>{{ label }}</button>\n"
        "{% endmacro %}\n",
        encoding="utf-8",
    )

    aliases = repository_service.nunjucks_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="_includes/partials/macros.njk",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "_includes/partials/macros.njk" in aliases
    assert "_includes.partials.macros" in aliases
    assert "partials.macros" in aliases
    assert "render_button" in aliases


def test_nunjucks_adapter_parse_file_resolves_imports_includes_and_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "nunjucks-parse-repo"
    (repo_path / "_includes" / "partials").mkdir(parents=True)
    (repo_path / "_includes" / "partials" / "macros.njk").write_text(
        "{% macro render_button(label) %}\n"
        "  <button>{{ label }}</button>\n"
        "{% endmacro %}\n",
        encoding="utf-8",
    )
    (repo_path / "_includes" / "base.njk").write_text(
        "<html>{% block body %}{% endblock %}</html>\n",
        encoding="utf-8",
    )
    (repo_path / "index.njk").write_text(
        '{% extends "_includes/base.njk" %}\n'
        '{% import "_includes/partials/macros.njk" as macros %}\n'
        '{% block body %}{{ macros.render_button("Ship it") }}{% endblock %}\n',
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["index.njk", "_includes/base.njk", "_includes/partials/macros.njk"],
        root_path=repo_path,
    )
    text = (repo_path / "index.njk").read_text(encoding="utf-8")

    dependencies = repository_service.nunjucks_adapter.parse_dependencies_only(
        "index.njk",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.nunjucks_adapter.parse_file(
        "index.njk",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "_includes/base.njk" for dependency in dependencies)
    assert any(
        dependency.target_file == "_includes/partials/macros.njk" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "index" for symbol in symbols)
    assert any(
        reference.target_file == "_includes/partials/macros.njk"
        and "render_button" in reference.target_names
        for reference in references
    )


def test_nunjucks_language_detection_supports_template_suffixes() -> None:
    assert ".njk" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("index.njk"),
        text='{{ greeting }}\n{% include "_includes/footer.njk" %}\n',
    ) == "nunjucks"


def test_operational_seed_plan_without_diagnostics_promotes_nunjucks_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nunjucks-profile-repo"
    (repo_path / "_includes" / "partials").mkdir(parents=True)
    (repo_path / "_includes" / "partials" / "macros.njk").write_text(
        "{% macro render_button(label) %}<button>{{ label }}</button>{% endmacro %}\n",
        encoding="utf-8",
    )
    (repo_path / "_includes" / "base.njk").write_text(
        "<html>{% block body %}{% endblock %}</html>\n",
        encoding="utf-8",
    )
    (repo_path / "index.njk").write_text(
        '{% extends "_includes/base.njk" %}\n'
        '{% import "_includes/partials/macros.njk" as macros %}\n'
        '{% block body %}{{ macros.render_button("Ship it") }}{% endblock %}\n',
        encoding="utf-8",
    )
    (repo_path / "about.njk").write_text(
        '{% extends "_includes/base.njk" %}\n{% block body %}<p>About</p>{% endblock %}\n',
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "build.js").write_text("console.log('build')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "nunjucks" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "nunjucks"
    assert "index.njk" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_nunjucks_first_in_js_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nunjucks-mixed-js-repo"
    (repo_path / "_includes").mkdir(parents=True)
    (repo_path / "_includes" / "page.njk").write_text("{{ render_user(name) }}\n", encoding="utf-8")
    (repo_path / "package.json").write_text('{"name":"mixed-nunjucks","type":"module"}\n', encoding="utf-8")
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.js").write_text(
        "import { renderUser0 } from './module0.js';\nconsole.log(renderUser0('demo'));\n",
        encoding="utf-8",
    )
    for index in range(24):
        (repo_path / "src" / f"module{index}.js").write_text(
            f"export function renderUser{index}(name) {{ return name.toUpperCase(); }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "nunjucks" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "nunjucks"
    assert "javascript" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_nunjucks_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "nunjucks-graph-repo"
    (repo_path / "_includes" / "partials").mkdir(parents=True)
    (repo_path / "_includes" / "partials" / "macros.njk").write_text(
        "{% macro render_button(label) %}\n"
        "  <button>{{ label }}</button>\n"
        "{% endmacro %}\n",
        encoding="utf-8",
    )
    (repo_path / "index.njk").write_text(
        '{% import "_includes/partials/macros.njk" as macros %}\n'
        '{{ macros.render_button("Ship it") }}\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.njk", "_includes/**/*.njk", "_includes/*.njk"],
            max_files=16,
        ),
    )
    edge_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:index.njk"
        and str(row["target_node"]) == "file:_includes/partials/macros.njk"
        for row in edge_rows
    )

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"]) for row in symbol_rows
    }
    index_symbol_id = symbol_ids[("index.njk", "index")]
    macro_symbol_id = symbol_ids[("_includes/partials/macros.njk", "render_button")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{index_symbol_id}"
        and str(row["target_node"]) == f"symbol:{macro_symbol_id}"
        for row in edge_rows
    )
