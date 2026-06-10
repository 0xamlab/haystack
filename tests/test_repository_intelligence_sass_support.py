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
    repository_intelligence_sass_parser_dispatch as repository_sass_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    sass_analysis_support as repository_sass_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    sass_primitives as repository_sass_primitives,
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


def test_repository_intelligence_sass_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["sass"] is (
        repository_sass_parser_dispatch._parse_sass_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["sass"] is (
        repository_sass_parser_dispatch._parse_sass_dependencies_only
    )


def test_repository_intelligence_sass_helpers_are_modularized() -> None:
    assert repository_service.sass_adapter.strip_comments is (
        repository_sass_primitives.strip_comments
    )
    assert repository_service.sass_adapter.has_sass_path_hints is (
        repository_sass_primitives.has_sass_path_hints
    )
    assert repository_service.sass_adapter.is_probable_sass_source is (
        repository_sass_analysis_support.is_probable_sass_source
    )
    assert repository_service.sass_adapter.iter_import_entries is (
        repository_sass_primitives.iter_import_entries
    )
    assert repository_service.sass_adapter.module_aliases_for_path is (
        repository_sass_analysis_support.module_aliases_for_path
    )
    assert repository_service.sass_adapter.parse_dependencies_only is (
        repository_sass_analysis_support.parse_dependencies_only
    )
    assert repository_service.sass_adapter.parse_file is (
        repository_sass_analysis_support.parse_file
    )


def test_sass_adapter_module_aliases_include_module_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "sass-alias-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "_mixins.sass").write_text(
        "=rounded($radius)\n"
        "  border-radius: $radius\n"
        "\n"
        "$brand: #333\n",
        encoding="utf-8",
    )

    aliases = repository_service.sass_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="styles/_mixins.sass",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "styles/_mixins.sass" in aliases
    assert "styles/mixins" in aliases
    assert "styles.mixins" in aliases
    assert "mixins" in aliases
    assert "rounded" in aliases
    assert "brand" in aliases


def test_sass_adapter_parse_file_resolves_imports_and_references() -> None:
    module_index = repository_service._build_module_index(
        ["styles/_mixins.sass", "styles/_functions.sass", "app.sass"],
        root_path=Path("/tmp/sass-index"),
    )
    text = (
        '@use "styles/mixins" as mix\n'
        '@import "styles/functions"\n'
        "$brand: color-scale($base)\n"
        ".button\n"
        "  +mix.rounded(4px)\n"
        "  color: color-scale($brand)\n"
    )

    symbols, dependencies, references = repository_service.sass_adapter.parse_file(
        "app.sass",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "styles/_mixins.sass" for dependency in dependencies)
    assert any(dependency.target_file == "styles/_functions.sass" for dependency in dependencies)
    assert any(symbol.symbol_name == "app" for symbol in symbols)
    assert any(symbol.symbol_name == "brand" for symbol in symbols)
    assert any(reference.target_file == "styles/_mixins.sass" for reference in references)
    assert any(reference.target_names == ("rounded",) for reference in references)
    assert any(reference.target_file == "styles/_functions.sass" for reference in references)
    assert any(reference.target_names == ("color-scale",) for reference in references)


def test_sass_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".sass" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("styles/app.sass"),
            text='=rounded($radius)\n  border-radius: $radius\n',
        )
        == "sass"
    )
    assert (
        repository_service._language_for_path(
            Path("styles/app.sass"),
            text="plain notes without sass constructs\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_sass_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sass-profile-repo"
    (repo_path / "styles").mkdir(parents=True)
    for index in range(6):
        (repo_path / "styles" / f"module_{index}.sass").write_text(
            f"$color-{index}: #{index}{index}{index}\n"
            f"=button-{index}\n"
            f"  color: $color-{index}\n",
            encoding="utf-8",
        )
    (repo_path / "app.sass").write_text(
        '@use "styles/module_0" as mod0\n'
        ".button\n"
        "  +mod0.button-0\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.js").write_text(
            "export const helper = () => 1;\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "sass" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "sass"
    assert "app.sass" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_sass_first_in_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sass-mixed-host-repo"
    (repo_path / "styles").mkdir(parents=True)
    for index in range(5):
        (repo_path / "styles" / f"module_{index}.sass").write_text(
            f"$color-{index}: #{index}{index}{index}\n"
            f"=button-{index}\n"
            f"  color: $color-{index}\n",
            encoding="utf-8",
        )
    (repo_path / "src").mkdir(parents=True)
    for index in range(20):
        (repo_path / "src" / f"Host{index}.ts").write_text(
            "export const host = () => 1;\n",
            encoding="utf-8",
        )
    (repo_path / "package.json").write_text(
        '{"name":"sass-mixed-host","private":true}\n',
        encoding="utf-8",
    )
    (repo_path / "tsconfig.json").write_text(
        '{"compilerOptions":{"module":"esnext","target":"es2022"}}\n',
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "sass" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "sass"


def test_repository_snapshot_graph_contains_sass_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "sass-graph-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "_mixins.sass").write_text(
        "=rounded($radius)\n"
        "  border-radius: $radius\n",
        encoding="utf-8",
    )
    (repo_path / "app.sass").write_text(
        '@use "styles/mixins" as mix\n'
        ".button\n"
        "  +mix.rounded(4px)\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    request = RepositorySnapshotCreateRequest(
        focus_paths=["."],
        include_patterns=["*.sass", "styles/*.sass", "styles/**/*.sass"],
        max_files=8,
    )

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=request,
    )

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    app_symbol_id = symbol_ids[("app.sass", "app")]
    rounded_symbol_id = symbol_ids[("styles/_mixins.sass", "rounded")]

    assert any(
        str(row["symbol_name"]) == "rounded" and str(row["file_path"]) == "styles/_mixins.sass"
        for row in symbol_rows
    )
    assert any(
        str(row["edge_type"]) == "uses"
        and str(row["source_node"]) == "file:app.sass"
        and str(row["target_node"]) == "file:styles/_mixins.sass"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{app_symbol_id}"
        and str(row["target_node"]) == f"symbol:{rounded_symbol_id}"
        for row in graph_rows
    )
