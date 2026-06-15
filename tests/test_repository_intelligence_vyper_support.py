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
    repository_intelligence_vyper_parser_dispatch as repository_vyper_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    vyper_analysis_support as repository_vyper_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vyper_primitives as repository_vyper_primitives,
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


def test_repository_intelligence_vyper_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["vyper"] is (
        repository_vyper_parser_dispatch._parse_vyper_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["vyper"] is (
        repository_vyper_parser_dispatch._parse_vyper_dependencies_only
    )


def test_repository_intelligence_vyper_helpers_are_modularized() -> None:
    assert repository_service.vyper_adapter.strip_comments is repository_vyper_primitives.strip_comments
    assert repository_service.vyper_adapter.has_vyper_path_hints is (
        repository_vyper_primitives.has_vyper_path_hints
    )
    assert repository_service.vyper_adapter.is_probable_vyper_source is (
        repository_vyper_analysis_support.is_probable_vyper_source
    )
    assert repository_service.vyper_adapter.iter_dependency_entries is (
        repository_vyper_primitives.iter_dependency_entries
    )
    assert repository_service.vyper_adapter.module_aliases_for_path is (
        repository_vyper_analysis_support.module_aliases_for_path
    )
    assert repository_service.vyper_adapter.parse_dependencies_only is (
        repository_vyper_analysis_support.parse_dependencies_only
    )
    assert repository_service.vyper_adapter.parse_file is (
        repository_vyper_analysis_support.parse_file
    )


def test_vyper_adapter_module_aliases_include_module_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "vyper-alias-repo"
    (repo_path / "contracts").mkdir(parents=True)
    (repo_path / "contracts" / "math_utils.vy").write_text(
        "def add(a: uint256, b: uint256) -> uint256:\n"
        "    return a + b\n",
        encoding="utf-8",
    )

    aliases = repository_service.vyper_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="contracts/math_utils.vy",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "contracts/math_utils.vy" in aliases
    assert "math_utils" in aliases
    assert "contracts.math_utils" in aliases
    assert "contracts/math_utils" in aliases
    assert "add" in aliases


def test_vyper_adapter_module_aliases_accept_preloaded_text_without_file_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vyper-alias-text-repo"
    (repo_path / "contracts").mkdir(parents=True)
    source_path = repo_path / "contracts" / "math_utils.vy"
    source_path.write_text(
        "def add(a: uint256, b: uint256) -> uint256:\n"
        "    return a + b\n",
        encoding="utf-8",
    )

    def _unexpected_read_text(*args: object, **kwargs: object) -> str:
        raise AssertionError("module_aliases_for_path reread the file instead of using preloaded text")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.vyper_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="contracts/math_utils.vy",
        stable_identifier=repository_service._stable_identifier,
        text="def add(a: uint256, b: uint256) -> uint256:\n    return a + b\n",
    )

    assert "add" in aliases


def test_vyper_adapter_module_aliases_can_skip_symbol_alias_scans(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vyper-path-only-alias-repo"
    (repo_path / "contracts").mkdir(parents=True)
    file_path = repo_path / "contracts" / "math_utils.vy"
    file_path.write_text(
        "def add(a: uint256, b: uint256) -> uint256:\n"
        "    return a + b\n",
        encoding="utf-8",
    )

    def _unexpected_read_text(self: Path, *args: object, **kwargs: object) -> str:
        raise AssertionError(f"path-only vyper aliases should not reread {self}")

    def _unexpected_iter_symbol_entries(*args: object, **kwargs: object) -> object:
        raise AssertionError("path-only vyper aliases should skip symbol scans")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)
    monkeypatch.setattr(
        repository_vyper_primitives,
        "iter_symbol_entries",
        _unexpected_iter_symbol_entries,
    )

    aliases = repository_service.vyper_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="contracts/math_utils.vy",
        stable_identifier=repository_service._stable_identifier,
        include_symbol_aliases=False,
    )

    assert "contracts/math_utils.vy" in aliases
    assert "contracts/math_utils" in aliases
    assert "contracts.math_utils" in aliases
    assert "math_utils" in aliases
    assert "add" not in aliases


def test_vyper_adapter_parse_file_extracts_import_dependencies_and_references() -> None:
    module_index = {
        "contracts/math_utils.vy": "contracts/math_utils.vy",
        "contracts/math_utils": "contracts/math_utils.vy",
        "contracts.math_utils": "contracts/math_utils.vy",
        "math_utils": "contracts/math_utils.vy",
        "add": "contracts/math_utils.vy",
        "contracts/main.vy": "contracts/main.vy",
        "main": "contracts/main.vy",
        "run": "contracts/main.vy",
    }
    main_text = (
        "import contracts.math_utils as math_utils\n\n"
        "def run(a: uint256, b: uint256) -> uint256:\n"
        "    return math_utils.add(a, b)\n"
    )

    symbols, dependencies, references = repository_service.vyper_adapter.parse_file(
        "contracts/main.vy",
        main_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "contracts/math_utils.vy" for dependency in dependencies)
    assert any(dependency.target_symbol == "math_utils" for dependency in dependencies)
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(reference.target_file == "contracts/math_utils.vy" for reference in references)
    assert any(reference.target_names == ("add",) for reference in references)


def test_vyper_adapter_parse_dependencies_only_prepares_source_text_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = repository_vyper_primitives._prepare_source_text
    observed_texts: list[str] = []

    def _recording_prepare_source_text(text: str) -> tuple[str, tuple[int, ...]]:
        observed_texts.append(text)
        return original(text)

    monkeypatch.setattr(
        repository_vyper_primitives,
        "_prepare_source_text",
        _recording_prepare_source_text,
    )

    dependencies = repository_service.vyper_adapter.parse_dependencies_only(
        "contracts/main.vy",
        "import contracts.math_utils as math_utils\n",
        {"contracts.math_utils": "contracts/math_utils.vy"},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert observed_texts == ["import contracts.math_utils as math_utils\n"]
    assert dependencies


def test_vyper_adapter_parse_file_prepares_source_text_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = repository_vyper_primitives._prepare_source_text
    observed_texts: list[str] = []

    def _recording_prepare_source_text(text: str) -> tuple[str, tuple[int, ...]]:
        observed_texts.append(text)
        return original(text)

    monkeypatch.setattr(
        repository_vyper_primitives,
        "_prepare_source_text",
        _recording_prepare_source_text,
    )

    symbols, dependencies, references = repository_service.vyper_adapter.parse_file(
        "contracts/main.vy",
        (
            "import contracts.math_utils as math_utils\n\n"
            "def run(a: uint256, b: uint256) -> uint256:\n"
            "    return math_utils.add(a, b)\n"
        ),
        {
            "contracts/math_utils.vy": "contracts/math_utils.vy",
            "contracts.math_utils": "contracts/math_utils.vy",
            "math_utils": "contracts/math_utils.vy",
            "contracts/main.vy": "contracts/main.vy",
            "main": "contracts/main.vy",
            "run": "contracts/main.vy",
        },
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert observed_texts == [
        "import contracts.math_utils as math_utils\n\n"
        "def run(a: uint256, b: uint256) -> uint256:\n"
        "    return math_utils.add(a, b)\n"
    ]
    assert symbols
    assert dependencies
    assert references


def test_vyper_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".vy" in repository_service._TEXT_FILE_SUFFIXES
    assert ".vyi" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("contracts/token.vy"),
            text="event Transfer:\n    sender: indexed(address)\n",
        )
        == "vyper"
    )
    assert (
        repository_service._language_for_path(
            Path("interfaces/token.vyi"),
            text="interface IERC20:\n    def balanceOf(owner: address) -> uint256: view\n",
        )
        == "vyper"
    )
    assert (
        repository_service._language_for_path(
            Path("notes.vy"),
            text="plain notes without vyper constructs\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_vyper_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vyper-profile-repo"
    (repo_path / "contracts").mkdir(parents=True)
    for index in range(6):
        (repo_path / "contracts" / f"Vault{index}.vy").write_text(
            "event Deposit:\n"
            "    sender: indexed(address)\n\n"
            f"def deposit_{index}(amount: uint256):\n"
            "    pass\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "print('helper')\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "vyper" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "vyper"
    assert any(path.endswith(".vy") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_does_not_force_vyper_first_in_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vyper-mixed-host-repo"
    (repo_path / "contracts").mkdir(parents=True)
    for index in range(4):
        (repo_path / "contracts" / f"Vault{index}.vy").write_text(
            f"def deposit_{index}(amount: uint256):\n    pass\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(14):
        (repo_path / "scripts" / f"deploy_{index}.py").write_text(
            "def deploy() -> None:\n    print('deploy')\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "vyper" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "vyper"


def test_repository_snapshot_graph_contains_vyper_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "vyper-graph-repo"
    (repo_path / "contracts").mkdir(parents=True)
    (repo_path / "contracts" / "math_utils.vy").write_text(
        "def add(a: uint256, b: uint256) -> uint256:\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    (repo_path / "contracts" / "main.vy").write_text(
        "import contracts.math_utils as math_utils\n\n"
        "def run(a: uint256, b: uint256) -> uint256:\n"
        "    return math_utils.add(a, b)\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["contracts"],
            include_patterns=["*.vy", "*.vyi"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbols_table = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    add_symbol_ids = {
        row["symbol_id"] for row in symbols_table if row["symbol_name"] == "add"
    }
    assert add_symbol_ids
    target_nodes = {f"symbol:{symbol_id}" for symbol_id in add_symbol_ids}
    assert any(
        row["edge_type"] == "references_symbol"
        and row["target_node"] in target_nodes
        and row["source_node"].startswith("symbol:")
        for row in graph
    )
