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
    repository_intelligence_al_parser_dispatch as repository_al_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    al_analysis_support as repository_al_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    al_primitives as repository_al_primitives,
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


def test_repository_intelligence_al_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["al"] is (
        repository_al_parser_dispatch._parse_al_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["al"] is (
        repository_al_parser_dispatch._parse_al_dependencies_only
    )


def test_repository_intelligence_al_helpers_are_modularized() -> None:
    assert repository_service.al_adapter.strip_comments is repository_al_primitives.strip_comments
    assert repository_service.al_adapter.has_al_path_hints is (
        repository_al_primitives.has_al_path_hints
    )
    assert repository_service.al_adapter.is_probable_al_source is (
        repository_al_analysis_support.is_probable_al_source
    )
    assert repository_service.al_adapter.iter_dependency_entries is (
        repository_al_primitives.iter_dependency_entries
    )
    assert repository_service.al_adapter.module_aliases_for_path is (
        repository_al_analysis_support.module_aliases_for_path
    )
    assert repository_service.al_adapter.parse_dependencies_only is (
        repository_al_analysis_support.parse_dependencies_only
    )
    assert repository_service.al_adapter.parse_file is (
        repository_al_analysis_support.parse_file
    )


def test_al_adapter_module_aliases_include_object_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "al-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "CustomerCardExt.al").write_text(
        'pageextension 50101 CustomerCardExt extends "Customer Card"\n'
        "{\n"
        "    trigger OnOpenPage()\n"
        "    begin\n"
        "        FormatName();\n"
        "    end;\n"
        "\n"
        "    local procedure FormatName()\n"
        "    begin\n"
        "    end;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.al_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/CustomerCardExt.al",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/CustomerCardExt.al" in aliases
    assert "CustomerCardExt" in aliases
    assert "src.CustomerCardExt" in aliases
    assert "Customer Card" in aliases
    assert "FormatName" in aliases


def test_al_adapter_parse_file_extracts_extends_dependencies_and_references() -> None:
    module_index = {
        "BasePage.al": "BasePage.al",
        "ExtPage.al": "ExtPage.al",
        "Customer Card": "BasePage.al",
        "CustomerCardExt": "ExtPage.al",
        "FormatName": "ExtPage.al",
        "OnOpenPage": "ExtPage.al",
    }
    ext_text = (
        'pageextension 50101 CustomerCardExt extends "Customer Card"\n'
        "{\n"
        "    trigger OnOpenPage()\n"
        "    begin\n"
        "        FormatName();\n"
        "    end;\n"
        "\n"
        "    local procedure FormatName()\n"
        "    begin\n"
        "    end;\n"
        "}\n"
    )

    repository_service.al_adapter.module_aliases_for_path(
        root_path=Path("/tmp/al-index"),
        file_path="BasePage.al",
        stable_identifier=repository_service._stable_identifier,
    )
    symbols, dependencies, references = repository_service.al_adapter.parse_file(
        "ExtPage.al",
        ext_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "BasePage.al" for dependency in dependencies)
    assert any(dependency.target_symbol == "Customer Card" for dependency in dependencies)
    assert any(symbol.symbol_name == "CustomerCardExt" for symbol in symbols)
    assert any(symbol.symbol_name == "OnOpenPage" for symbol in symbols)
    assert any(symbol.symbol_name == "FormatName" for symbol in symbols)
    assert any(reference.target_file == "ExtPage.al" for reference in references)
    assert any(reference.target_names == ("FormatName",) for reference in references)


def test_al_adapter_symbol_and_reference_line_numbers_are_stable() -> None:
    text = (
        'pageextension 50101 CustomerCardExt extends "Customer Card"\n'
        "{\n"
        "    trigger OnOpenPage()\n"
        "    begin\n"
        "        FormatName();\n"
        "    end;\n"
        "\n"
        "    local procedure FormatName()\n"
        "    begin\n"
        "    end;\n"
        "}\n"
    )

    assert repository_al_primitives.iter_symbol_entries(text) == (
        ("pageextension", "CustomerCardExt", 1),
        ("trigger", "OnOpenPage", 3),
        ("procedure", "FormatName", 8),
    )
    assert repository_al_primitives.iter_reference_entries(text) == (
        (None, "FormatName", 5),
    )


def test_al_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".al" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("src/CustomerCardExt.al"),
            text='pageextension 50101 CustomerCardExt extends "Customer Card"\n{\n}\n',
        )
        == "al"
    )
    assert (
        repository_service._language_for_path(
            Path("notes.al"),
            text="plain notes without AL constructs\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_al_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "al-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    for index in range(6):
        (repo_path / "src" / f"Page{index}.al").write_text(
            f'page {50100 + index} "Customer Card {index}"\n'
            "{\n"
            "    trigger OnOpenPage()\n"
            "    begin\n"
            "        FormatName();\n"
            "    end;\n"
            "\n"
            "    local procedure FormatName()\n"
            "    begin\n"
            "    end;\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.ps1").write_text(
            "Write-Host 'helper'\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "al" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "al"
    assert any(path.endswith(".al") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_does_not_force_al_first_in_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "al-mixed-host-repo"
    (repo_path / "src").mkdir(parents=True)
    for index in range(5):
        (repo_path / "src" / f"Page{index}.al").write_text(
            f'page {50100 + index} "Customer Card {index}"\n'
            "{\n"
            "    local procedure FormatName()\n"
            "    begin\n"
            "    end;\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(20):
        (repo_path / "scripts" / f"Deploy{index}.ps1").write_text(
            "Write-Host 'deploy'\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "al" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "al"


def test_repository_snapshot_graph_contains_al_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "al-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "BasePage.al").write_text('page 50100 "Customer Card"\n{\n}\n', encoding="utf-8")
    (repo_path / "ExtPage.al").write_text(
        'pageextension 50101 CustomerCardExt extends "Customer Card"\n'
        "{\n"
        "    trigger OnOpenPage()\n"
        "    begin\n"
        "        FormatName();\n"
        "    end;\n"
        "\n"
        "    local procedure FormatName()\n"
        "    begin\n"
        "    end;\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.al"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    target_ids = {
        row["symbol_id"]
        for row in symbol_rows
        if row["file_path"] == "ExtPage.al" and row["symbol_name"] == "FormatName"
    }
    assert target_ids
    target_nodes = {f"symbol:{symbol_id}" for symbol_id in target_ids}
    assert any(
        row["edge_type"] == "references_symbol"
        and row["target_node"] in target_nodes
        and row["source_node"].startswith("symbol:")
        for row in graph
    )
