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
    repository_intelligence_move_parser_dispatch as repository_move_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    move_analysis_support as repository_move_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    move_primitives as repository_move_primitives,
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


def test_repository_intelligence_move_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["move"] is (
        repository_move_parser_dispatch._parse_move_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["move"] is (
        repository_move_parser_dispatch._parse_move_dependencies_only
    )


def test_repository_intelligence_move_helpers_are_modularized() -> None:
    assert repository_service.move_adapter.has_move_path_hints is (
        repository_move_primitives.has_move_path_hints
    )
    assert repository_service.move_adapter.is_probable_move_source is (
        repository_move_analysis_support.is_probable_move_source
    )
    assert repository_service.move_adapter.parse_dependencies_only is (
        repository_move_analysis_support.parse_dependencies_only
    )
    assert repository_service.move_adapter.parse_file is repository_move_analysis_support.parse_file


def test_move_adapter_module_aliases_include_declared_module_name(tmp_path: Path) -> None:
    repo_path = tmp_path / "move-alias-repo"
    (repo_path / "sources").mkdir(parents=True)
    (repo_path / "sources" / "vault.move").write_text(
        "module 0x1::vault {\n    public fun deposit() {}\n}\n",
        encoding="utf-8",
    )

    aliases = repository_service.move_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="sources/vault.move",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "sources/vault.move" in aliases
    assert "vault" in aliases
    assert "0x1::vault" in aliases


def test_move_adapter_parse_dependencies_resolves_use_and_friend(tmp_path: Path) -> None:
    repo_path = tmp_path / "move-deps-repo"
    (repo_path / "sources").mkdir(parents=True)
    (repo_path / "sources" / "coin.move").write_text(
        "module 0x1::coin { public fun mint() {} }\n",
        encoding="utf-8",
    )
    (repo_path / "sources" / "treasury.move").write_text(
        "module 0x1::treasury { public fun grant() {} }\n",
        encoding="utf-8",
    )
    vault_path = repo_path / "sources" / "vault.move"
    vault_path.write_text(
        "module 0x1::vault {\n"
        "    use 0x1::coin;\n"
        "    friend 0x1::treasury;\n"
        "    public fun deposit() { coin::mint(); }\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["sources/coin.move", "sources/treasury.move", "sources/vault.move"],
        root_path=repo_path,
    )

    dependencies = repository_service.move_adapter.parse_dependencies_only(
        "sources/vault.move",
        vault_path.read_text(encoding="utf-8"),
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert {dependency.target_file for dependency in dependencies} == {
        "sources/coin.move",
        "sources/treasury.move",
    }


def test_move_language_detection_supports_move_suffix_and_manifest() -> None:
    assert ".move" in repository_service._TEXT_FILE_SUFFIXES
    assert "Move.toml" in repository_service._TEXT_FILE_BASENAMES
    assert (
        repository_service._language_for_path(
            Path("sources/vault.move"),
            text="module 0x1::vault { public fun deposit() {} }\n",
        )
        == "move"
    )
    assert (
        repository_service._language_for_path(
            Path("Move.toml"),
            text='[package]\nname = "vault"\nversion = "0.0.1"\n',
        )
        == "move"
    )


def test_operational_seed_plan_without_diagnostics_promotes_move_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "move-profile-repo"
    (repo_path / "sources").mkdir(parents=True)
    (repo_path / "Move.toml").write_text(
        '[package]\nname = "vault"\nversion = "0.0.1"\n',
        encoding="utf-8",
    )
    (repo_path / "sources" / "coin.move").write_text(
        "module 0x1::coin { public fun mint() {} }\n",
        encoding="utf-8",
    )
    (repo_path / "sources" / "vault.move").write_text(
        "module 0x1::vault {\n"
        "    use 0x1::coin;\n"
        "    public entry fun deposit() { coin::mint(); }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "deploy.ts").write_text("console.log('move');\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "move" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "move"
    assert "sources/vault.move" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_move_first_in_rust_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "move-mixed-rust-repo"
    (repo_path / "sources").mkdir(parents=True)
    (repo_path / "Move.toml").write_text(
        '[package]\nname = "vault"\nversion = "0.0.1"\n',
        encoding="utf-8",
    )
    (repo_path / "sources" / "coin.move").write_text(
        "module 0x1::coin { public fun mint() {} }\n",
        encoding="utf-8",
    )
    (repo_path / "sources" / "vault.move").write_text(
        "module 0x1::vault {\n"
        "    use 0x1::coin;\n"
        "    public fun deposit() { coin::mint(); }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src").mkdir(parents=True)
    for index in range(18):
        (repo_path / "src" / f"lib{index}.rs").write_text(
            f"pub fn value_{index}() -> usize {{ {index} }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "move" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "move"
    assert "rust" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_move_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "move-graph-repo"
    (repo_path / "sources").mkdir(parents=True)
    (repo_path / "Move.toml").write_text(
        '[package]\nname = "vault"\nversion = "0.0.1"\n',
        encoding="utf-8",
    )
    (repo_path / "sources" / "coin.move").write_text(
        "module 0x1::coin {\n"
        "    public fun mint() {}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "sources" / "vault.move").write_text(
        "module 0x1::vault {\n"
        "    use 0x1::coin;\n"
        "    public fun deposit() { helper(); coin::mint(); }\n"
        "    fun helper() {}\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["sources/**/*.move", "sources/*.move", "*.move", "Move.toml"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    deposit_symbol_id = symbol_ids[("sources/vault.move", "deposit")]
    helper_symbol_id = symbol_ids[("sources/vault.move", "helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{deposit_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
