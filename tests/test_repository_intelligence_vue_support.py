from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_vue_parser_dispatch as repository_vue_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    vue_analysis_support as repository_vue_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vue_primitives as repository_vue_primitives,
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


def test_repository_intelligence_vue_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["vue"] is (
        repository_vue_parser_dispatch._parse_vue_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["vue"] is (
        repository_vue_parser_dispatch._parse_vue_dependencies_only
    )


def test_repository_intelligence_vue_helpers_are_modularized() -> None:
    assert repository_service.vue_adapter.has_vue_path_hints is (
        repository_vue_primitives.has_vue_path_hints
    )
    assert repository_service.vue_adapter.iter_import_entries is (
        repository_vue_primitives.iter_import_entries
    )
    assert repository_service.vue_adapter.iter_template_component_references is (
        repository_vue_primitives.iter_template_component_references
    )
    assert repository_service.vue_adapter.resolve_import is (
        repository_vue_primitives.resolve_import
    )
    assert repository_service.vue_adapter.is_probable_vue_source is (
        repository_vue_analysis_support.is_probable_vue_source
    )
    assert repository_service.vue_adapter.module_aliases_for_path is (
        repository_vue_analysis_support.module_aliases_for_path
    )
    assert repository_service.vue_adapter.parse_dependencies_only is (
        repository_vue_analysis_support.parse_dependencies_only
    )
    assert repository_service.vue_adapter.parse_file is (
        repository_vue_analysis_support.parse_file
    )


def test_vue_adapter_module_aliases_include_path_and_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "vue-alias-repo"
    (repo_path / "src" / "components").mkdir(parents=True)
    (repo_path / "src" / "components" / "HelloCard.vue").write_text(
        "<template><article>Hello</article></template>\n",
        encoding="utf-8",
    )

    aliases = repository_service.vue_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/components/HelloCard.vue",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/components/HelloCard.vue" in aliases
    assert "src.components.HelloCard" in aliases
    assert "HelloCard" in aliases


def test_vue_adapter_parse_file_resolves_component_dependencies(tmp_path: Path) -> None:
    repo_path = tmp_path / "vue-parse-repo"
    (repo_path / "src" / "components").mkdir(parents=True)
    (repo_path / "src" / "components" / "HelloCard.vue").write_text(
        "<template><article>{{ title }}</article></template>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "App.vue").write_text(
        "<template><HelloCard /></template>\n"
        "<script setup>\n"
        "import HelloCard from './components/HelloCard.vue';\n"
        "</script>\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["src/components/HelloCard.vue", "src/App.vue"],
        root_path=repo_path,
    )
    text = (repo_path / "src" / "App.vue").read_text(encoding="utf-8")

    dependencies = repository_service.vue_adapter.parse_dependencies_only(
        "src/App.vue",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.vue_adapter.parse_file(
        "src/App.vue",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "src/components/HelloCard.vue" for dependency in dependencies)
    assert any(symbol.symbol_name == "App" for symbol in symbols)
    assert any(
        reference.target_file == "src/components/HelloCard.vue" and "HelloCard" in reference.target_names
        for reference in references
    )


def test_vue_resolve_import_supports_directory_index_components() -> None:
    module_index = {
        "src/components/Card/index.vue": "src/components/Card/index.vue",
    }

    resolved_target = repository_vue_primitives.resolve_import(
        current_file="src/App.vue",
        import_target="./components/Card",
        module_index=module_index,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert resolved_target == "src/components/Card/index.vue"


def test_vue_language_detection_supports_single_file_component_suffix() -> None:
    assert repository_service._language_for_path(
        Path("src/App.vue"),
        text="<template><main /></template>\n",
    ) == "vue"


def test_operational_seed_plan_without_diagnostics_promotes_vue_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vue-profile-repo"
    (repo_path / "src" / "components").mkdir(parents=True)
    (repo_path / "src" / "components" / "HeroBanner.vue").write_text(
        "<template><section>Hero</section></template>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "components" / "HelloCard.vue").write_text(
        "<template><article>Hello</article></template>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "App.vue").write_text(
        "<template><HeroBanner /><HelloCard /></template>\n"
        "<script setup>\n"
        "import HeroBanner from './components/HeroBanner.vue';\n"
        "import HelloCard from './components/HelloCard.vue';\n"
        "</script>\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        '{"name":"vue-demo","scripts":{"dev":"vite","build":"vite build"}}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.ts").write_text("import './App.vue';\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "vue" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "vue"
    assert "src/App.vue" in seed_plan["entrypoint_files"]
    assert "src/components" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_does_not_force_vue_first_in_ts_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vue-mixed-ts-repo"
    (repo_path / "src" / "components").mkdir(parents=True)
    (repo_path / "src" / "components" / "HelloCard.vue").write_text(
        "<template><article>Hello</article></template>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "App.vue").write_text(
        "<template><HelloCard /></template>\n"
        "<script setup>\n"
        "import HelloCard from './components/HelloCard.vue';\n"
        "</script>\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        '{"name":"mixed-ts","scripts":{"dev":"vite","build":"vite build"}}\n',
        encoding="utf-8",
    )
    for index in range(24):
        (repo_path / "src" / f"page_{index}.ts").write_text(
            f"export function page{index}() {{ return {index}; }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "vue" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "vue"
    assert "typescript" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_vue_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "vue-graph-repo"
    (repo_path / "src" / "components").mkdir(parents=True)
    (repo_path / "src" / "components" / "HelloCard.vue").write_text(
        "<template><article>Hello graph contract v2</article></template>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "App.vue").write_text(
        "<template><HelloCard /></template>\n"
        "<script setup>\n"
        "import HelloCard from './components/HelloCard.vue';\n"
        "const graphContractMarker = 'vue-graph-contract-v2';\n"
        "</script>\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["src/**/*.vue", "src/*.vue", "*.vue"],
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
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/App.vue"
        and str(row["target_node"]) == "file:src/components/HelloCard.vue"
        for row in graph_rows
    )
    app_symbol_id = symbol_ids[("src/App.vue", "App")]
    card_symbol_id = symbol_ids[("src/components/HelloCard.vue", "HelloCard")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{app_symbol_id}"
        and str(row["target_node"]) == f"symbol:{card_symbol_id}"
        for row in graph_rows
    )
