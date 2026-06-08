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
    repository_intelligence_openqasm_parser_dispatch as repository_intelligence_openqasm_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    openqasm_analysis_support as repository_openqasm_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    openqasm_primitives as repository_openqasm_primitives,
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


def test_repository_intelligence_openqasm_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["openqasm"] is (
        repository_intelligence_openqasm_parser_dispatch._parse_openqasm_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["openqasm"] is (
        repository_intelligence_openqasm_parser_dispatch._parse_openqasm_dependencies_only
    )


def test_repository_intelligence_openqasm_helpers_are_modularized() -> None:
    assert repository_service.openqasm_adapter.has_openqasm_path_hints is (
        repository_openqasm_primitives.has_openqasm_path_hints
    )
    assert repository_service.openqasm_adapter.is_probable_openqasm_source is (
        repository_openqasm_analysis_support.is_probable_openqasm_source
    )
    assert repository_service.openqasm_adapter.iter_dependency_entries is (
        repository_openqasm_primitives.iter_dependency_entries
    )
    assert repository_service.openqasm_adapter.module_aliases_for_path is (
        repository_openqasm_analysis_support.module_aliases_for_path
    )
    assert repository_service.openqasm_adapter.parse_file is (
        repository_openqasm_analysis_support.parse_file
    )


def test_openqasm_adapter_module_aliases_include_path_stem(tmp_path: Path) -> None:
    repo_path = tmp_path / "openqasm-alias-repo"
    (repo_path / "circuits").mkdir(parents=True)
    (repo_path / "circuits" / "teleport.qasm").write_text(
        'OPENQASM 3;\ninclude "stdgates.inc";\nqubit[3] q;\n',
        encoding="utf-8",
    )

    aliases = repository_service.openqasm_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="circuits/teleport.qasm",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "circuits/teleport.qasm" in aliases
    assert "teleport" in aliases
    assert "circuits.teleport" in aliases


def test_openqasm_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = {
        "stdgates.inc.qasm": "circuits/stdgates.inc.qasm",
        "circuits/stdgates.inc.qasm": "circuits/stdgates.inc.qasm",
    }
    text = (
        'OPENQASM 3;\n'
        'include "stdgates.inc.qasm";\n'
        "gate post q { }\n"
        "qubit q;\n"
        "post q;\n"
    )

    symbols, dependencies, references = repository_service.openqasm_adapter.parse_file(
        "circuits/teleport.qasm",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "circuits/stdgates.inc.qasm" for dependency in dependencies)
    assert any(symbol.symbol_name == "post" for symbol in symbols)
    assert any(reference.target_names == ("post",) for reference in references)


def test_openqasm_language_detection_supports_qasm_without_overclaiming() -> None:
    assert ".qasm" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("circuits/teleport.qasm"),
        text='OPENQASM 3;\ninclude "stdgates.inc";\nqubit[3] q;\n',
    ) == "openqasm"
    assert repository_service._language_for_path(
        Path("circuits/plain.qasm"),
        text="plain notes without qasm syntax\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_openqasm_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "openqasm-profile-repo"
    (repo_path / "examples").mkdir(parents=True)
    for index in range(6):
        (repo_path / "examples" / f"circuit_{index}.qasm").write_text(
            'OPENQASM 3;\ninclude "stdgates.inc";\n'
            f"gate op{index} q {{ }}\nqubit q;\nop{index} q;\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "tools" / "helper.py").write_text("print('openqasm')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "openqasm" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "openqasm"
    assert any(path.endswith(".qasm") for path in seed_plan["candidate_file_paths"])


def test_operational_seed_plan_without_diagnostics_does_not_force_openqasm_first_in_python_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "openqasm-mixed-python-repo"
    (repo_path / "circuits").mkdir(parents=True)
    for index in range(4):
        (repo_path / "circuits" / f"circuit_{index}.qasm").write_text(
            'OPENQASM 3;\ninclude "stdgates.inc";\n'
            f"gate op{index} q {{ }}\nqubit q;\nop{index} q;\n",
            encoding="utf-8",
        )
    (repo_path / "src").mkdir(parents=True)
    for index in range(10):
        (repo_path / "src" / f"module_{index}.py").write_text(
            f"def run_{index}():\n    return {index}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "openqasm" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "openqasm"
    assert "python" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_openqasm_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "openqasm-graph-repo"
    (repo_path / "circuits").mkdir(parents=True)
    (repo_path / "circuits" / "teleport.qasm").write_text(
        'OPENQASM 3;\ninclude "stdgates.inc";\ngate post q { }\nqubit q;\npost q;\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["circuits/**/*.qasm", "circuits/*.qasm", "*.qasm"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    post_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "circuits/teleport.qasm"
        and str(row["symbol_name"]) == "post"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{post_symbol_id}"
        for row in graph
    )
