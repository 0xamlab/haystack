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
    repository_intelligence_opencl_parser_dispatch as repository_opencl_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    opencl_analysis_support as repository_opencl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    opencl_primitives as repository_opencl_primitives,
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


def test_repository_intelligence_opencl_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["opencl"] is (
        repository_opencl_parser_dispatch._parse_opencl_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["opencl"] is (
        repository_opencl_parser_dispatch._parse_opencl_dependencies_only
    )


def test_repository_intelligence_opencl_helpers_are_modularized() -> None:
    assert repository_service.opencl_adapter.strip_comments is (
        repository_opencl_primitives.strip_comments
    )
    assert repository_service.opencl_adapter.has_opencl_path_hints is (
        repository_opencl_primitives.has_opencl_path_hints
    )
    assert repository_service.opencl_adapter.is_probable_opencl_source is (
        repository_opencl_analysis_support.is_probable_opencl_source
    )
    assert repository_service.opencl_adapter.module_aliases_for_path is (
        repository_opencl_analysis_support.module_aliases_for_path
    )
    assert repository_service.opencl_adapter.parse_dependencies_only is (
        repository_opencl_analysis_support.parse_dependencies_only
    )
    assert repository_service.opencl_adapter.parse_file is (
        repository_opencl_analysis_support.parse_file
    )


def test_opencl_adapter_module_aliases_include_symbols_and_paths(tmp_path: Path) -> None:
    repo_path = tmp_path / "opencl-alias-repo"
    (repo_path / "kernels").mkdir(parents=True)
    (repo_path / "kernels" / "common.clh").write_text(
        "__constant int SCALE = 2;\n"
        "inline float scale_value(float value) {\n"
        "    return value * SCALE;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.opencl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="kernels/common.clh",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "kernels/common.clh" in aliases
    assert "common.clh" in aliases
    assert "common" in aliases
    assert "kernels/common" in aliases
    assert "scale_value" in aliases


def test_opencl_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = repository_service._build_module_index(
        ["kernels/common.clh", "kernels/main.cl"],
        root_path=Path("/tmp/opencl-index"),
    )
    text = (
        '#include "common.clh"\n'
        "__kernel void saxpy(__global const float* x, __global float* y) {\n"
        "    int gid = get_global_id(0);\n"
        "    y[gid] = scale_value(x[gid]);\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.opencl_adapter.parse_file(
        "kernels/main.cl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_include=lambda **kwargs: repository_service.opencl_adapter.resolve_include(
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
            **kwargs,
        ),
    )

    assert any(dependency.target_file == "kernels/common.clh" for dependency in dependencies)
    assert any(symbol.symbol_name == "saxpy" for symbol in symbols)
    assert any(reference.target_file == "kernels/common.clh" for reference in references)
    assert any(reference.target_names == ("scale_value",) for reference in references)


def test_opencl_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".cl" in repository_service._TEXT_FILE_SUFFIXES
    assert ".clh" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("kernels/add.cl"),
            text=(
                "__kernel void add(__global const float* x, __global float* y) {\n"
                "    int gid = get_global_id(0);\n"
                "    y[gid] = x[gid];\n"
                "}\n"
            ),
        )
        == "opencl"
    )
    assert (
        repository_service._language_for_path(
            Path("kernels/common.clh"),
            text="__constant int SCALE = 2;\n",
        )
        == "opencl"
    )
    assert (
        repository_service._language_for_path(
            Path("notes.cl"),
            text="plain notes without opencl constructs\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_opencl_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "opencl-profile-repo"
    (repo_path / "kernels").mkdir(parents=True)
    for index in range(6):
        (repo_path / "kernels" / f"Kernel{index}.cl").write_text(
            "__kernel void kernel_main(__global const float* x, __global float* y) {\n"
            "    int gid = get_global_id(0);\n"
            "    y[gid] = x[gid];\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "def helper() -> int:\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "opencl" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "opencl"


def test_operational_seed_plan_without_diagnostics_does_not_force_opencl_first_in_cpp_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "opencl-mixed-host-repo"
    (repo_path / "kernels").mkdir(parents=True)
    for index in range(5):
        (repo_path / "kernels" / f"Kernel{index}.cl").write_text(
            "__kernel void kernel_main(__global const float* x, __global float* y) {\n"
            "    int gid = get_global_id(0);\n"
            "    y[gid] = x[gid];\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "src").mkdir(parents=True)
    for index in range(20):
        (repo_path / "src" / f"Host{index}.cpp").write_text(
            "int run_host() { return 1; }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "opencl" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "opencl"
    assert "cpp" in seed_plan["operational_ecosystems"] or "c" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_opencl_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "opencl-graph-repo"
    (repo_path / "kernels").mkdir(parents=True)
    (repo_path / "kernels" / "common.clh").write_text(
        "__constant int SCALE = 2;\n"
        "inline float scale_value(float value) {\n"
        "    return value * SCALE;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "kernels" / "main.cl").write_text(
        '#include "common.clh"\n'
        "__kernel void saxpy(__global const float* x, __global float* y) {\n"
        "    int gid = get_global_id(0);\n"
        "    y[gid] = scale_value(x[gid]);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["kernels"],
            include_patterns=["kernels/**/*.cl", "kernels/**/*.clh"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    target_ids = {
        row["symbol_id"]
        for row in symbol_rows
        if row["file_path"] == "kernels/common.clh" and row["symbol_name"] == "scale_value"
    }
    assert target_ids
    target_nodes = {f"symbol:{symbol_id}" for symbol_id in target_ids}
    assert any(
        row["edge_type"] == "references_symbol"
        and row["target_node"] in target_nodes
        and row["source_node"].startswith("symbol:")
        for row in graph
    )
