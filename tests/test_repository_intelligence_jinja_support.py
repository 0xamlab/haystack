from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_jinja_parser_dispatch as repository_jinja_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    jinja_analysis_support as repository_jinja_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    jinja_primitives as repository_jinja_primitives,
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


def test_repository_intelligence_jinja_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["jinja"] is (
        repository_jinja_parser_dispatch._parse_jinja_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["jinja"] is (
        repository_jinja_parser_dispatch._parse_jinja_dependencies_only
    )


def test_repository_intelligence_jinja_helpers_are_modularized() -> None:
    assert repository_service.jinja_adapter.strip_comments is (
        repository_jinja_primitives.strip_comments
    )
    assert repository_service.jinja_adapter.has_jinja_path_hints is (
        repository_jinja_primitives.has_jinja_path_hints
    )
    assert repository_service.jinja_adapter.iter_dependency_entries is (
        repository_jinja_primitives.iter_dependency_entries
    )
    assert repository_service.jinja_adapter.iter_symbol_entries is (
        repository_jinja_primitives.iter_symbol_entries
    )
    assert repository_service.jinja_adapter.iter_reference_entries is (
        repository_jinja_primitives.iter_reference_entries
    )
    assert repository_service.jinja_adapter.resolve_import is (
        repository_jinja_primitives.resolve_import
    )
    assert repository_service.jinja_adapter.is_probable_jinja_source is (
        repository_jinja_analysis_support.is_probable_jinja_source
    )
    assert repository_service.jinja_adapter.module_aliases_for_path is (
        repository_jinja_analysis_support.module_aliases_for_path
    )
    assert repository_service.jinja_adapter.parse_dependencies_only is (
        repository_jinja_analysis_support.parse_dependencies_only
    )
    assert repository_service.jinja_adapter.parse_file is (
        repository_jinja_analysis_support.parse_file
    )


def test_jinja_adapter_module_aliases_include_module_and_macro_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "jinja-alias-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "partials" / "macros.j2").write_text(
        "{% macro render_button(label) %}\n"
        "  <button>{{ label }}</button>\n"
        "{% endmacro %}\n",
        encoding="utf-8",
    )

    aliases = repository_service.jinja_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="templates/partials/macros.j2",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "templates/partials/macros.j2" in aliases
    assert "templates.partials.macros" in aliases
    assert "partials.macros" in aliases
    assert "render_button" in aliases


def test_jinja_adapter_parse_file_resolves_imports_includes_and_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "jinja-parse-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "partials" / "macros.j2").write_text(
        "{% macro render_button(label) %}\n"
        "  <button>{{ label }}</button>\n"
        "{% endmacro %}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "base.j2").write_text(
        "<html>{% block body %}{% endblock %}</html>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "page.j2").write_text(
        '{% extends "base.j2" %}\n'
        '{% import "partials/macros.j2" as macros %}\n'
        '{% block body %}{{ macros.render_button("Ship it") }}{% endblock %}\n',
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["templates/page.j2", "templates/base.j2", "templates/partials/macros.j2"],
        root_path=repo_path,
    )
    text = (repo_path / "templates" / "page.j2").read_text(encoding="utf-8")

    dependencies = repository_service.jinja_adapter.parse_dependencies_only(
        "templates/page.j2",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.jinja_adapter.parse_file(
        "templates/page.j2",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "templates/base.j2" for dependency in dependencies)
    assert any(
        dependency.target_file == "templates/partials/macros.j2" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "page" for symbol in symbols)
    assert any(
        reference.target_file == "templates/partials/macros.j2"
        and "render_button" in reference.target_names
        for reference in references
    )


def test_jinja_language_detection_supports_template_suffixes() -> None:
    assert repository_service._language_for_path(
        Path("templates/page.j2"),
        text='{{ greeting }}\n{% include "partials/footer.j2" %}\n',
    ) == "jinja"


def test_operational_seed_plan_without_diagnostics_promotes_jinja_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "jinja-profile-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "partials" / "macros.j2").write_text(
        "{% macro render_button(label) %}<button>{{ label }}</button>{% endmacro %}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "base.j2").write_text(
        "<html>{% block body %}{% endblock %}</html>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "page.j2").write_text(
        '{% extends "base.j2" %}\n'
        '{% import "partials/macros.j2" as macros %}\n'
        '{% block body %}{{ macros.render_button("Ship it") }}{% endblock %}\n',
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "deploy.py").write_text("print('deploy')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "jinja" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "jinja"
    assert "templates/page.j2" in seed_plan["entrypoint_files"]
    assert "templates/partials" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_does_not_force_jinja_first_in_python_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "jinja-mixed-python-repo"
    (repo_path / "templates").mkdir(parents=True)
    (repo_path / "templates" / "page.j2").write_text("{{ render_user(name) }}\n", encoding="utf-8")
    (repo_path / "pyproject.toml").write_text(
        '[project]\nname = "jinja-mixed-python"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.py").write_text(
        "from module_0 import render_user_0\nprint(render_user_0('demo'))\n",
        encoding="utf-8",
    )
    for index in range(24):
        (repo_path / "src" / f"module_{index}.py").write_text(
            f"def render_user_{index}(name):\n    return name.upper()\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "jinja" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "jinja"
    assert "python" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_jinja_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "jinja-dependency-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "partials" / "macros.j2").write_text(
        "{% macro render_button(label) %}\n"
        "  <button>{{ label }}</button>\n"
        "{% endmacro %}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "page.j2").write_text(
        '{% import "partials/macros.j2" as macros %}\n'
        '{{ macros.render_button("Ship it") }}\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["templates"],
            include_patterns=["templates/**/*.j2", "templates/*.j2"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:templates/page.j2"
        and str(row["target_node"]) == "file:templates/partials/macros.j2"
        for row in graph_rows
    )
    render_symbol_id = symbol_ids[("templates/page.j2", "page")]
    helper_symbol_id = symbol_ids[("templates/partials/macros.j2", "render_button")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{render_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
