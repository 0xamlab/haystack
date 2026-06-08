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
    repository_intelligence_smarty_parser_dispatch as repository_smarty_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    smarty_analysis_support as repository_smarty_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    smarty_primitives as repository_smarty_primitives,
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


def test_repository_intelligence_smarty_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["smarty"] is (
        repository_smarty_parser_dispatch._parse_smarty_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["smarty"] is (
        repository_smarty_parser_dispatch._parse_smarty_dependencies_only
    )


def test_repository_intelligence_smarty_helpers_are_modularized() -> None:
    assert repository_service.smarty_adapter.strip_comments is repository_smarty_primitives.strip_comments
    assert repository_service.smarty_adapter.has_smarty_path_hints is (
        repository_smarty_primitives.has_smarty_path_hints
    )
    assert repository_service.smarty_adapter.iter_dependency_entries is (
        repository_smarty_primitives.iter_dependency_entries
    )
    assert repository_service.smarty_adapter.iter_reference_entries is (
        repository_smarty_primitives.iter_reference_entries
    )
    assert repository_service.smarty_adapter.iter_symbol_entries is (
        repository_smarty_primitives.iter_symbol_entries
    )
    assert repository_service.smarty_adapter.resolve_import is (
        repository_smarty_primitives.resolve_import
    )
    assert repository_service.smarty_adapter.is_probable_smarty_source is (
        repository_smarty_analysis_support.is_probable_smarty_source
    )
    assert repository_service.smarty_adapter.module_aliases_for_path is (
        repository_smarty_analysis_support.module_aliases_for_path
    )
    assert repository_service.smarty_adapter.parse_dependencies_only is (
        repository_smarty_analysis_support.parse_dependencies_only
    )
    assert repository_service.smarty_adapter.parse_file is (
        repository_smarty_analysis_support.parse_file
    )


def test_smarty_adapter_module_aliases_include_template_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "smarty-alias-repo"
    (repo_path / "templates" / "layouts").mkdir(parents=True)
    (repo_path / "templates" / "layouts" / "base.tpl").write_text(
        "{block name='content'}{/block}\n",
        encoding="utf-8",
    )

    aliases = repository_service.smarty_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="templates/layouts/base.tpl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "templates/layouts/base.tpl" in aliases
    assert "templates/layouts/base" in aliases
    assert "layouts.base" in aliases


def test_smarty_adapter_parse_file_resolves_template_dependencies_and_function_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "smarty-parse-repo"
    (repo_path / "templates" / "layouts").mkdir(parents=True)
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "layouts" / "base.tpl").write_text(
        "{block name='content'}{/block}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "partials" / "card.tpl").write_text(
        "<article>{$title}</article>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "home.tpl").write_text(
        "{extends file='layouts/base.tpl'}\n"
        "{include file='partials/card.tpl'}\n"
        "{function name='helper'}ok{/function}\n"
        "{helper}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "templates/layouts/base.tpl",
            "templates/partials/card.tpl",
            "templates/home.tpl",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "templates" / "home.tpl").read_text(encoding="utf-8")

    dependencies = repository_service.smarty_adapter.parse_dependencies_only(
        "templates/home.tpl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.smarty_adapter.parse_file(
        "templates/home.tpl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "templates/layouts/base.tpl" for dependency in dependencies
    )
    assert any(
        dependency.target_file == "templates/partials/card.tpl" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "home" for symbol in symbols)
    assert any(symbol.symbol_name == "helper" for symbol in symbols)
    assert any(
        reference.target_file == "templates/layouts/base.tpl"
        and reference.target_names == ("layouts.base",)
        for reference in references
    )
    assert any(
        reference.target_file == "templates/partials/card.tpl"
        and reference.target_names == ("partials.card",)
        for reference in references
    )
    assert any(
        reference.target_file == "templates/home.tpl"
        and reference.target_names == ("helper",)
        and reference.source_symbol_id != reference.target_symbol_id
        for reference in references
    )


def test_smarty_language_detection_supports_tpl_suffix_without_overclaiming_plain_tpl() -> None:
    assert ".tpl" in repository_intelligence_file_selection.TEXT_FILE_SUFFIXES

    assert repository_service._language_for_path(
        Path("templates/home.tpl"),
        text="{extends file='layouts/base.tpl'}\n{$title}\n",
    ) == "smarty"
    assert repository_service._language_for_path(
        Path("templates/plain.tpl"),
        text="<html><body>plain template</body></html>\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_smarty_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "smarty-profile-repo"
    (repo_path / "templates" / "layouts").mkdir(parents=True)
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "layouts" / "base.tpl").write_text(
        "{block name='content'}{/block}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "partials" / "card.tpl").write_text(
        "<article>{$title}</article>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "index.tpl").write_text(
        "{extends file='layouts/base.tpl'}\n{include file='partials/card.tpl'}\n{$title}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "page.tpl").write_text(
        "{extends file='layouts/base.tpl'}\n{include file='partials/card.tpl'}\n{$content}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "smarty" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "smarty"
    assert any(path.endswith(".tpl") for path in seed_plan["candidate_file_paths"])
    assert any(root.startswith("templates") for root in seed_plan["support_roots"])


def test_operational_seed_plan_without_diagnostics_does_not_force_smarty_first_in_php_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "smarty-mixed-php-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "templates").mkdir(parents=True)
    (repo_path / "src" / "App.php").write_text("<?php\nclass App {}\n", encoding="utf-8")
    (repo_path / "src" / "Controller.php").write_text(
        "<?php\nrequire_once __DIR__ . '/App.php';\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Kernel.php").write_text("<?php\nfunction boot() {}\n", encoding="utf-8")
    (repo_path / "src" / "Helpers.php").write_text("<?php\nfunction helper() {}\n", encoding="utf-8")
    (repo_path / "templates" / "index.tpl").write_text("{$title}\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "smarty" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "php"


def test_operational_seed_plan_without_diagnostics_keeps_smarty_candidates_visible_in_theme_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "smarty-theme-repo"
    (repo_path / "_dev" / "css" / "components").mkdir(parents=True)
    (repo_path / "templates" / "_partials").mkdir(parents=True)
    (repo_path / "templates" / "layouts").mkdir(parents=True)
    (repo_path / "_dev" / "package.json").write_text(
        '{"name":"theme-assets","private":true}\n',
        encoding="utf-8",
    )
    (repo_path / "composer.json").write_text(
        '{"name":"vendor/theme","type":"project"}\n',
        encoding="utf-8",
    )
    for index in range(24):
        (repo_path / "_dev" / "css" / "components" / f"part-{index}.scss").write_text(
            f".part-{index} {{ color: #{index:02x}{index:02x}{index:02x}; }}\n",
            encoding="utf-8",
        )
    (repo_path / "templates" / "layouts" / "base.tpl").write_text(
        "{block name='content'}{/block}\n",
        encoding="utf-8",
    )
    for name in ("index", "page", "contact", "product", "category", "checkout"):
        (repo_path / "templates" / f"{name}.tpl").write_text(
            "{extends file='layouts/base.tpl'}\n{$content}\n",
            encoding="utf-8",
        )
    (repo_path / "templates" / "_partials" / "card.tpl").write_text(
        "<article>{$title}</article>\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "smarty" in seed_plan["detected_ecosystems"]
    assert any(path.endswith(".tpl") for path in seed_plan["candidate_file_paths"])


def test_repository_intelligence_snapshot_graph_includes_smarty_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "smarty-snapshot-repo"
    (repo_path / "templates" / "layouts").mkdir(parents=True)
    (repo_path / "templates" / "layouts" / "base.tpl").write_text(
        "{block name='content'}{/block}\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "index.tpl").write_text(
        "{* smarty snapshot unique *}\n"
        "{extends file='layouts/base.tpl'}\n"
        "{function name='helper'}ok{/function}\n"
        "{helper}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["templates"],
            include_patterns=["templates/**/*.tpl", "templates/*.tpl", "*.tpl"],
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
        str(row["edge_type"]) == "extends"
        and str(row["source_node"]) == "file:templates/index.tpl"
        and str(row["target_node"]) == "file:templates/layouts/base.tpl"
        for row in graph_rows
    )

    index_symbol_id = symbol_ids[("templates/index.tpl", "index")]
    helper_symbol_id = symbol_ids[("templates/index.tpl", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{index_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
