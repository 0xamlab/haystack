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
    repository_intelligence_svelte_parser_dispatch as repository_svelte_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    svelte_analysis_support as repository_svelte_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    svelte_primitives as repository_svelte_primitives,
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


def test_repository_intelligence_svelte_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["svelte"] is (
        repository_svelte_parser_dispatch._parse_svelte_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["svelte"] is (
        repository_svelte_parser_dispatch._parse_svelte_dependencies_only
    )


def test_repository_intelligence_svelte_helpers_are_modularized() -> None:
    assert repository_service.svelte_adapter.has_svelte_path_hints is (
        repository_svelte_primitives.has_svelte_path_hints
    )
    assert repository_service.svelte_adapter.iter_import_entries is (
        repository_svelte_primitives.iter_import_entries
    )
    assert repository_service.svelte_adapter.iter_component_references is (
        repository_svelte_primitives.iter_component_references
    )
    assert repository_service.svelte_adapter.is_probable_svelte_source is (
        repository_svelte_analysis_support.is_probable_svelte_source
    )
    assert repository_service.svelte_adapter.module_aliases_for_path is (
        repository_svelte_analysis_support.module_aliases_for_path
    )
    assert repository_service.svelte_adapter.parse_dependencies_only is (
        repository_svelte_analysis_support.parse_dependencies_only
    )
    assert repository_service.svelte_adapter.parse_file is (
        repository_svelte_analysis_support.parse_file
    )


def test_svelte_adapter_module_aliases_include_path_module_and_component_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "svelte-alias-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "lib" / "Button.svelte").write_text(
        "<script>export let label = 'ok';</script>\n<button>{label}</button>\n",
        encoding="utf-8",
    )

    aliases = repository_service.svelte_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/lib/Button.svelte",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/lib/Button.svelte" in aliases
    assert "src.lib.Button" in aliases
    assert "Button" in aliases
    assert "lib.Button" in aliases


def test_svelte_adapter_parse_file_resolves_imports_and_component_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "svelte-parse-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "lib" / "Button.svelte").write_text(
        "<script>export let label = 'ok';</script>\n<button>{label}</button>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "App.svelte").write_text(
        "<script>\nimport Button from './lib/Button.svelte';\n</script>\n\n<Button />\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["src/lib/Button.svelte", "src/App.svelte"],
        root_path=repo_path,
    )
    text = (repo_path / "src" / "App.svelte").read_text(encoding="utf-8")

    dependencies = repository_service.svelte_adapter.parse_dependencies_only(
        "src/App.svelte",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.svelte_adapter.parse_file(
        "src/App.svelte",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "src/lib/Button.svelte" for dependency in dependencies)
    assert any(symbol.symbol_name == "App" for symbol in symbols)
    assert any(
        reference.target_file == "src/lib/Button.svelte" and "Button" in reference.target_names
        for reference in references
    )


def test_svelte_language_detection_supports_svelte_suffix() -> None:
    assert repository_service._language_for_path(
        Path("src/App.svelte"),
        text="<script>let count = 0;</script>\n<button>{count}</button>\n",
    ) == "svelte"


def test_operational_seed_plan_without_diagnostics_promotes_svelte_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "svelte-profile-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "lib" / "Button.svelte").write_text(
        "<script>export let label = 'ok';</script>\n<button>{label}</button>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "routes").mkdir(parents=True)
    (repo_path / "src" / "routes" / "+page.svelte").write_text(
        "<script>\nimport Button from '$lib/Button.svelte';\n</script>\n<Button />\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        '{"name":"svelte-demo","scripts":{"dev":"vite","build":"vite build"}}\n',
        encoding="utf-8",
    )
    (repo_path / "vite.config.ts").write_text("export default {};\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "svelte" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "svelte"
    assert any(path.endswith("+page.svelte") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_does_not_force_svelte_first_in_ts_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "svelte-mixed-ts-repo"
    (repo_path / "src" / "components").mkdir(parents=True)
    (repo_path / "src" / "components" / "Widget.svelte").write_text(
        "<script>export let value = 1;</script>\n<div>{value}</div>\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        '{"name":"mixed-svelte","scripts":{"dev":"vite","build":"vite build"}}\n',
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

    assert "svelte" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "svelte"
    assert "typescript" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_svelte_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "svelte-graph-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "lib" / "Button.svelte").write_text(
        "<script>export let label = 'graph';</script>\n<button>{label}</button>\n",
        encoding="utf-8",
    )
    (repo_path / "src").mkdir(parents=True, exist_ok=True)
    (repo_path / "src" / "App.svelte").write_text(
        "<script>\nimport Button from './lib/Button.svelte';\n</script>\n<Button />\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text('{"name":"svelte-graph"}\n', encoding="utf-8")
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["src/**/*.svelte", "src/*.svelte", "*.svelte"],
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
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/App.svelte"
        and str(row["target_node"]) == "file:src/lib/Button.svelte"
        for row in graph_rows
    )
    app_symbol_id = symbol_ids[("src/App.svelte", "App")]
    button_symbol_id = symbol_ids[("src/lib/Button.svelte", "lib.Button")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{app_symbol_id}"
        and str(row["target_node"]) == f"symbol:{button_symbol_id}"
        for row in graph_rows
    )
