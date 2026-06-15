from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import repository_intelligence_file_selection
from apps.api_server.services import (
    repository_intelligence_pug_parser_dispatch as repository_pug_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    pug_analysis_support as repository_pug_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    pug_primitives as repository_pug_primitives,
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


def test_repository_intelligence_pug_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["pug"] is (
        repository_pug_parser_dispatch._parse_pug_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["pug"] is (
        repository_pug_parser_dispatch._parse_pug_dependencies_only
    )


def test_repository_intelligence_pug_helpers_are_modularized() -> None:
    assert repository_service.pug_adapter.strip_comments is repository_pug_primitives.strip_comments
    assert repository_service.pug_adapter.has_pug_path_hints is (
        repository_pug_primitives.has_pug_path_hints
    )
    assert repository_service.pug_adapter.iter_dependency_entries is (
        repository_pug_primitives.iter_dependency_entries
    )
    assert repository_service.pug_adapter.iter_reference_entries is (
        repository_pug_primitives.iter_reference_entries
    )
    assert repository_service.pug_adapter.resolve_import is repository_pug_primitives.resolve_import
    assert repository_service.pug_adapter.is_probable_pug_source is (
        repository_pug_analysis_support.is_probable_pug_source
    )
    assert repository_service.pug_adapter.module_aliases_for_path is (
        repository_pug_analysis_support.module_aliases_for_path
    )
    assert repository_service.pug_adapter.parse_dependencies_only is (
        repository_pug_analysis_support.parse_dependencies_only
    )
    assert repository_service.pug_adapter.parse_file is (
        repository_pug_analysis_support.parse_file
    )


def test_pug_adapter_module_aliases_include_path_and_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "pug-alias-repo"
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "partials" / "card.pug").write_text("article Card body\n", encoding="utf-8")

    aliases = repository_service.pug_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="partials/card.pug",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "partials/card.pug" in aliases
    assert "partials.card" in aliases
    assert "card" in aliases


def test_pug_adapter_parse_file_resolves_include_dependencies(tmp_path: Path) -> None:
    repo_path = tmp_path / "pug-parse-repo"
    (repo_path / "layouts").mkdir(parents=True)
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "layouts" / "base.pug").write_text("html\n  block content\n", encoding="utf-8")
    (repo_path / "partials" / "card.pug").write_text("mixin card(title)\n  article= title\n", encoding="utf-8")
    (repo_path / "index.pug").write_text(
        "extends layouts/base.pug\ninclude partials/card.pug\nblock content\n  +card('Hello')\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["layouts/base.pug", "partials/card.pug", "index.pug"],
        root_path=repo_path,
    )
    text = (repo_path / "index.pug").read_text(encoding="utf-8")

    dependencies = repository_service.pug_adapter.parse_dependencies_only(
        "index.pug",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.pug_adapter.parse_file(
        "index.pug",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "layouts/base.pug" for dependency in dependencies)
    assert any(dependency.target_file == "partials/card.pug" for dependency in dependencies)
    assert any(symbol.symbol_name == "index" for symbol in symbols)
    assert any(
        reference.target_file == "partials/card.pug" and "card" in reference.target_names
        for reference in references
    )


def test_pug_language_detection_supports_pug_and_jade_suffixes() -> None:
    assert ".pug" in repository_intelligence_file_selection.TEXT_FILE_SUFFIXES
    assert ".jade" in repository_intelligence_file_selection.TEXT_FILE_SUFFIXES

    assert repository_service._language_for_path(
        Path("views/index.pug"),
        text="extends layouts/base.pug\nblock content\n  h1 Hello\n",
    ) == "pug"
    assert repository_service._language_for_path(
        Path("views/index.jade"),
        text="html\n  body\n    h1 Jade\n",
    ) == "pug"


def test_operational_seed_plan_without_diagnostics_promotes_pug_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "pug-profile-repo"
    (repo_path / "layouts").mkdir(parents=True)
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "layouts" / "base.pug").write_text("html\n  block content\n", encoding="utf-8")
    (repo_path / "partials" / "card.pug").write_text("article Card body\n", encoding="utf-8")
    (repo_path / "views").mkdir(parents=True)
    (repo_path / "views" / "index.pug").write_text(
        "extends ../layouts/base.pug\ninclude ../partials/card.pug\nblock content\n  include ../partials/card.pug\n",
        encoding="utf-8",
    )
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "public" / "theme.js").write_text("console.log('theme')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "pug" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "pug"
    assert "views/index.pug" in seed_plan["entrypoint_files"]
    assert "views" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_does_not_force_pug_first_in_js_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "pug-mixed-js-repo"
    (repo_path / "views").mkdir(parents=True)
    (repo_path / "views" / "index.pug").write_text("h1 Hello\n", encoding="utf-8")
    (repo_path / "package.json").write_text('{"name":"mixed-pug","type":"module"}\n', encoding="utf-8")
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

    assert "pug" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "pug"
    assert "javascript" in seed_plan["operational_ecosystems"]


def test_operational_seed_plan_without_diagnostics_promotes_pug_over_scss_in_template_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "pug-template-build-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "package.json").write_text(
        '{"name":"pug-template-build","scripts":{"build":"node scripts/build-pug.js"}}\n',
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    for script_name in (
        "build-pug.js",
        "build-assets.js",
        "build-scripts.js",
        "serve.js",
        "watch.js",
        "clean.js",
    ):
        (repo_path / "scripts" / script_name).write_text(
            "export function run() { return true; }\n",
            encoding="utf-8",
        )
    (repo_path / "src" / "pug" / "layouts").mkdir(parents=True)
    (repo_path / "src" / "pug" / "partials").mkdir(parents=True)
    (repo_path / "src" / "pug" / "pages").mkdir(parents=True)
    (repo_path / "src" / "pug" / "layouts" / "base.pug").write_text(
        "html\n  body\n    block content\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "pug" / "partials" / "card.pug").write_text(
        "mixin card(title)\n  article= title\n",
        encoding="utf-8",
    )
    for index in range(8):
        (repo_path / "src" / "pug" / "pages" / f"page-{index}.pug").write_text(
            "extends ../layouts/base.pug\n"
            "include ../partials/card.pug\n"
            "block content\n"
            f"  +card('page-{index}')\n",
            encoding="utf-8",
        )
    (repo_path / "src" / "scss" / "layout").mkdir(parents=True)
    (repo_path / "src" / "scss" / "styles.scss").write_text(
        "@use 'layout/authentication';\nbody { color: #111; }\n",
        encoding="utf-8",
    )
    for index in range(4):
        (repo_path / "src" / "scss" / "layout" / f"_panel_{index}.scss").write_text(
            ".panel { display: grid; }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "pug" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "pug"
    assert any(path.endswith(".pug") for path in seed_plan["entrypoint_files"])
    assert "src/pug/layouts" in seed_plan["support_roots"]


def test_repository_snapshot_graph_contains_pug_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "pug-graph-repo"
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "partials" / "card.pug").write_text("article Graph card\n", encoding="utf-8")
    (repo_path / "index.pug").write_text("include partials/card.pug\nsection\n  include partials/card.pug\n", encoding="utf-8")
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.pug", "*.jade", "partials/**/*.pug", "partials/*.pug"],
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
        and str(row["source_node"]) == "file:index.pug"
        and str(row["target_node"]) == "file:partials/card.pug"
        for row in graph_rows
    )
    index_symbol_id = symbol_ids[("index.pug", "index")]
    card_symbol_id = symbol_ids[("partials/card.pug", "card")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{index_symbol_id}"
        and str(row["target_node"]) == f"symbol:{card_symbol_id}"
        for row in graph_rows
    )
