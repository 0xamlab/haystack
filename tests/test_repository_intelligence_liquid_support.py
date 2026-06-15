from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_liquid_parser_dispatch as repository_liquid_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    liquid_analysis_support as repository_liquid_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    liquid_primitives as repository_liquid_primitives,
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


def test_repository_intelligence_liquid_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["liquid"] is (
        repository_liquid_parser_dispatch._parse_liquid_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["liquid"] is (
        repository_liquid_parser_dispatch._parse_liquid_dependencies_only
    )


def test_repository_intelligence_liquid_helpers_are_modularized() -> None:
    assert repository_service.liquid_adapter.strip_comments is (
        repository_liquid_primitives.strip_comments
    )
    assert repository_service.liquid_adapter.has_liquid_path_hints is (
        repository_liquid_primitives.has_liquid_path_hints
    )
    assert repository_service.liquid_adapter.iter_dependency_entries is (
        repository_liquid_primitives.iter_dependency_entries
    )
    assert repository_service.liquid_adapter.iter_symbol_entries is (
        repository_liquid_primitives.iter_symbol_entries
    )
    assert repository_service.liquid_adapter.iter_reference_entries is (
        repository_liquid_primitives.iter_reference_entries
    )
    assert repository_service.liquid_adapter.resolve_import is (
        repository_liquid_primitives.resolve_import
    )
    assert repository_service.liquid_adapter.is_probable_liquid_source is (
        repository_liquid_analysis_support.is_probable_liquid_source
    )
    assert repository_service.liquid_adapter.module_aliases_for_path is (
        repository_liquid_analysis_support.module_aliases_for_path
    )
    assert repository_service.liquid_adapter.parse_dependencies_only is (
        repository_liquid_analysis_support.parse_dependencies_only
    )
    assert repository_service.liquid_adapter.parse_file is (
        repository_liquid_analysis_support.parse_file
    )


def test_liquid_adapter_module_aliases_include_module_and_binding_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "liquid-alias-repo"
    (repo_path / "snippets").mkdir(parents=True)
    (repo_path / "snippets" / "card.liquid").write_text(
        "{% assign button_label = product.title %}\n<div>{{ button_label }}</div>\n",
        encoding="utf-8",
    )

    aliases = repository_service.liquid_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="snippets/card.liquid",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "snippets/card.liquid" in aliases
    assert "snippets.card" in aliases
    assert "card" in aliases
    assert "button_label" in aliases


def test_liquid_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "liquid-alias-inline-text-repo"
    (repo_path / "snippets").mkdir(parents=True)
    source_text = "{% assign button_label = product.title %}\n<div>{{ button_label }}</div>\n"
    file_path = repo_path / "snippets" / "card.liquid"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.liquid_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="snippets/card.liquid",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_liquid_primitives.strip_comments(source_text),
    )

    assert "snippets/card.liquid" in aliases
    assert "snippets.card" in aliases
    assert "button_label" in aliases


def test_liquid_adapter_parse_file_resolves_render_and_layout_dependencies(tmp_path: Path) -> None:
    repo_path = tmp_path / "liquid-parse-repo"
    (repo_path / "layout").mkdir(parents=True)
    (repo_path / "snippets").mkdir(parents=True)
    (repo_path / "templates").mkdir(parents=True)
    (repo_path / "layout" / "theme.liquid").write_text(
        "<html>{{ content_for_layout }}</html>\n",
        encoding="utf-8",
    )
    (repo_path / "snippets" / "card.liquid").write_text(
        "{% assign button_label = product.title %}\n<div>{{ button_label }}</div>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "product.liquid").write_text(
        "{% layout 'theme' %}\n{% render 'card' %}\n{{ button_label }}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["layout/theme.liquid", "snippets/card.liquid", "templates/product.liquid"],
        root_path=repo_path,
    )
    text = (repo_path / "templates" / "product.liquid").read_text(encoding="utf-8")

    dependencies = repository_service.liquid_adapter.parse_dependencies_only(
        "templates/product.liquid",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.liquid_adapter.parse_file(
        "templates/product.liquid",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "layout/theme.liquid" for dependency in dependencies)
    assert any(dependency.target_file == "snippets/card.liquid" for dependency in dependencies)
    assert any(symbol.symbol_name == "product" for symbol in symbols)
    assert any(
        reference.target_file == "snippets/card.liquid" and "card" in reference.target_names
        for reference in references
    )


def test_liquid_language_detection_supports_template_suffix() -> None:
    assert repository_service._language_for_path(
        Path("templates/product.liquid"),
        text="{% render 'card' %}\n{{ product.title }}\n",
    ) == "liquid"


def test_liquid_strip_comments_preserves_newlines_and_removes_comment_blocks() -> None:
    source_text = (
        "{% comment %}\n"
        "{{ hidden }}\n"
        "{% endcomment %}\n"
        "{% render 'card' %}\n"
    )

    stripped_text = repository_liquid_primitives.strip_comments(source_text)

    assert "{{ hidden }}" not in stripped_text
    assert stripped_text.count("\n") == source_text.count("\n")
    assert "{% render 'card' %}" in stripped_text


def test_liquid_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_liquid_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(repository_liquid_primitives, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(repository_liquid_analysis_support, "strip_comments", counting_strip_comments)

    source_text = "{% layout 'theme' %}\n{% render 'card' %}\n{{ button_label }}\n"
    module_index = {
        "layout/theme.liquid": "layout/theme.liquid",
        "snippets/card.liquid": "snippets/card.liquid",
        "templates/product.liquid": "templates/product.liquid",
    }

    repository_service.liquid_adapter.parse_dependencies_only(
        "templates/product.liquid",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.liquid_adapter.parse_file(
        "templates/product.liquid",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_operational_seed_plan_without_diagnostics_promotes_liquid_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "liquid-profile-repo"
    (repo_path / "layout").mkdir(parents=True)
    (repo_path / "snippets").mkdir(parents=True)
    (repo_path / "sections").mkdir(parents=True)
    (repo_path / "templates").mkdir(parents=True)
    (repo_path / "layout" / "theme.liquid").write_text(
        "<html>{{ content_for_layout }}</html>\n",
        encoding="utf-8",
    )
    (repo_path / "snippets" / "card.liquid").write_text(
        "<div>{{ product.title }}</div>\n",
        encoding="utf-8",
    )
    (repo_path / "sections" / "header.liquid").write_text(
        "<header>{{ shop.name }}</header>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "product.liquid").write_text(
        "{% layout 'theme' %}\n{% section 'header' %}\n{% render 'card' %}\n",
        encoding="utf-8",
    )
    (repo_path / "assets").mkdir(parents=True)
    (repo_path / "assets" / "theme.js").write_text("console.log('theme')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "liquid" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "liquid"
    assert "templates/product.liquid" in seed_plan["entrypoint_files"]
    assert "snippets" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_does_not_force_liquid_first_in_ruby_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "liquid-mixed-ruby-repo"
    (repo_path / "templates").mkdir(parents=True)
    (repo_path / "templates" / "page.liquid").write_text(
        "{% render 'card' %}\n{{ site.title }}\n",
        encoding="utf-8",
    )
    (repo_path / "Gemfile").write_text(
        "source 'https://rubygems.org'\ngem 'jekyll'\n",
        encoding="utf-8",
    )
    (repo_path / "lib").mkdir(parents=True)
    for index in range(24):
        (repo_path / "lib" / f"page_{index}.rb").write_text(
            f"class Page{index}\n  def title\n    'demo'\n  end\nend\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "liquid" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "liquid"
    assert "ruby" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_liquid_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "liquid-graph-repo"
    (repo_path / "layout").mkdir(parents=True)
    (repo_path / "snippets").mkdir(parents=True)
    (repo_path / "templates").mkdir(parents=True)
    (repo_path / "layout" / "theme.liquid").write_text(
        "<html>{{ content_for_layout }}</html>\n",
        encoding="utf-8",
    )
    (repo_path / "snippets" / "card.liquid").write_text(
        "{% assign button_label = product.title %}\n<div>{{ button_label }}</div>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "product.liquid").write_text(
        "{% layout 'theme' %}\n{% render 'card' %}\n{{ button_label }}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=[
                "templates/**/*.liquid",
                "templates/*.liquid",
                "layout/**/*.liquid",
                "layout/*.liquid",
                "snippets/**/*.liquid",
                "snippets/*.liquid",
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
        str(row["edge_type"]) == "layout"
        and str(row["source_node"]) == "file:templates/product.liquid"
        and str(row["target_node"]) == "file:layout/theme.liquid"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "render"
        and str(row["source_node"]) == "file:templates/product.liquid"
        and str(row["target_node"]) == "file:snippets/card.liquid"
        for row in graph_rows
    )
    product_symbol_id = symbol_ids[("templates/product.liquid", "product")]
    card_symbol_id = symbol_ids[("snippets/card.liquid", "card")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{product_symbol_id}"
        and str(row["target_node"]) == f"symbol:{card_symbol_id}"
        for row in graph_rows
    )
