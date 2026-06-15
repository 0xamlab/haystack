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
    repository_intelligence_astro_parser_dispatch as repository_astro_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    astro_analysis_support as repository_astro_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    astro_primitives as repository_astro_primitives,
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
    subprocess.run(["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-qm", "Initial commit"], check=True)


def test_repository_intelligence_astro_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["astro"] is (
        repository_astro_parser_dispatch._parse_astro_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["astro"] is (
        repository_astro_parser_dispatch._parse_astro_dependencies_only
    )


def test_repository_intelligence_astro_helpers_are_modularized() -> None:
    assert repository_service.astro_adapter.has_astro_path_hints is (
        repository_astro_primitives.has_astro_path_hints
    )
    assert repository_service.astro_adapter.iter_import_entries is (
        repository_astro_primitives.iter_import_entries
    )
    assert repository_service.astro_adapter.iter_component_references is (
        repository_astro_primitives.iter_component_references
    )
    assert repository_service.astro_adapter.is_probable_astro_source is (
        repository_astro_analysis_support.is_probable_astro_source
    )
    assert repository_service.astro_adapter.module_aliases_for_path is (
        repository_astro_analysis_support.module_aliases_for_path
    )
    assert repository_service.astro_adapter.parse_dependencies_only is (
        repository_astro_analysis_support.parse_dependencies_only
    )
    assert repository_service.astro_adapter.parse_file is (
        repository_astro_analysis_support.parse_file
    )


def test_astro_adapter_module_aliases_include_path_module_and_component_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "astro-alias-repo"
    (repo_path / "src" / "components").mkdir(parents=True)
    (repo_path / "src" / "components" / "Button.astro").write_text(
        "---\nconst { label = 'ok' } = Astro.props;\n---\n<button>{label}</button>\n",
        encoding="utf-8",
    )

    aliases = repository_service.astro_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/components/Button.astro",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/components/Button.astro" in aliases
    assert "src.components.Button" in aliases
    assert "Button" in aliases
    assert "components.Button" in aliases


def test_astro_adapter_parse_file_resolves_imports_and_component_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "astro-parse-repo"
    (repo_path / "src" / "components").mkdir(parents=True)
    (repo_path / "src" / "components" / "Button.astro").write_text(
        "---\nconst { label = 'ok' } = Astro.props;\n---\n<button>{label}</button>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "pages").mkdir(parents=True)
    (repo_path / "src" / "pages" / "index.astro").write_text(
        "---\nimport Button from '../components/Button.astro';\n---\n<Button />\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["src/components/Button.astro", "src/pages/index.astro"],
        root_path=repo_path,
    )
    text = (repo_path / "src" / "pages" / "index.astro").read_text(encoding="utf-8")

    dependencies = repository_service.astro_adapter.parse_dependencies_only(
        "src/pages/index.astro",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.astro_adapter.parse_file(
        "src/pages/index.astro",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "src/components/Button.astro" for dependency in dependencies)
    assert any(symbol.symbol_name == "pages.index" for symbol in symbols)
    assert any(
        reference.target_file == "src/components/Button.astro" and "Button" in reference.target_names
        for reference in references
    )


def test_astro_resolve_import_supports_aliases_and_directory_indexes() -> None:
    module_index = {
        "src/components/Button.astro": "src/components/Button.astro",
        "src/components/Card/index.astro": "src/components/Card/index.astro",
    }

    alias_target = repository_astro_primitives.resolve_import(
        current_file="src/pages/index.astro",
        import_target="@components/Button.astro",
        module_index=module_index,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    directory_index_target = repository_astro_primitives.resolve_import(
        current_file="src/pages/index.astro",
        import_target="../components/Card",
        module_index=module_index,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert alias_target == "src/components/Button.astro"
    assert directory_index_target == "src/components/Card/index.astro"


def test_astro_language_detection_supports_astro_suffix() -> None:
    assert repository_service._language_for_path(
        Path("src/pages/index.astro"),
        text="---\nconst x = 1;\n---\n<div>{x}</div>\n",
    ) == "astro"


def test_operational_seed_plan_without_diagnostics_promotes_astro_when_surface_dominates(tmp_path: Path) -> None:
    repo_path = tmp_path / "astro-profile-repo"
    (repo_path / "src" / "components").mkdir(parents=True)
    (repo_path / "src" / "components" / "Card.astro").write_text(
        "---\nconst { title = 'ok' } = Astro.props;\n---\n<article>{title}</article>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "pages").mkdir(parents=True)
    (repo_path / "src" / "pages" / "index.astro").write_text(
        "---\nimport Card from '../components/Card.astro';\n---\n<Card />\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        '{"name":"astro-demo","scripts":{"dev":"astro dev","build":"astro build"}}\n',
        encoding="utf-8",
    )
    (repo_path / "astro.config.mjs").write_text("export default {};\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "astro" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "astro"
    assert any(path.endswith("index.astro") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_does_not_force_astro_first_in_ts_repo(tmp_path: Path) -> None:
    repo_path = tmp_path / "astro-mixed-ts-repo"
    (repo_path / "src" / "pages").mkdir(parents=True)
    (repo_path / "src" / "pages" / "index.astro").write_text(
        "---\nconst value = 1;\n---\n<div>{value}</div>\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        '{"name":"mixed-astro","scripts":{"dev":"astro dev","build":"astro build"}}\n',
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

    assert "astro" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "astro"
    assert "typescript" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_astro_dependency_and_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "astro-graph-repo"
    (repo_path / "src" / "components").mkdir(parents=True)
    (repo_path / "src" / "components" / "Button.astro").write_text(
        "---\nconst { label = 'graph', tone = 'primary' } = Astro.props;\n---\n<button data-tone={tone}>{label}</button>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "pages").mkdir(parents=True)
    (repo_path / "src" / "pages" / "index.astro").write_text(
        "---\nimport Button from '../components/Button.astro';\nconst tone = 'snapshot';\n---\n<Button tone={tone} />\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text('{"name":"astro-graph"}\n', encoding="utf-8")
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["src/**/*.astro", "src/*.astro", "*.astro"],
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
        and str(row["source_node"]) == "file:src/pages/index.astro"
        and str(row["target_node"]) == "file:src/components/Button.astro"
        for row in graph_rows
    )
    page_symbol_id = symbol_ids[("src/pages/index.astro", "pages.index")]
    button_symbol_id = symbol_ids[("src/components/Button.astro", "components.Button")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{page_symbol_id}"
        and str(row["target_node"]) == f"symbol:{button_symbol_id}"
        for row in graph_rows
    )
