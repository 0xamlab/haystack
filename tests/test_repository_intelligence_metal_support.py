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
    repository_intelligence_metal_parser_dispatch as repository_metal_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    metal_analysis_support as repository_metal_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    metal_primitives as repository_metal_primitives,
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


def test_repository_intelligence_metal_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["metal"] is (
        repository_metal_parser_dispatch._parse_metal_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["metal"] is (
        repository_metal_parser_dispatch._parse_metal_dependencies_only
    )


def test_repository_intelligence_metal_helpers_are_modularized() -> None:
    assert repository_service.metal_adapter.strip_comments is (
        repository_metal_primitives.strip_comments
    )
    assert repository_service.metal_adapter.has_metal_path_hints is (
        repository_metal_primitives.has_metal_path_hints
    )
    assert repository_service.metal_adapter.is_probable_metal_source is (
        repository_metal_analysis_support.is_probable_metal_source
    )
    assert repository_service.metal_adapter.module_aliases_for_path is (
        repository_metal_analysis_support.module_aliases_for_path
    )
    assert repository_service.metal_adapter.parse_dependencies_only is (
        repository_metal_analysis_support.parse_dependencies_only
    )
    assert repository_service.metal_adapter.parse_file is (
        repository_metal_analysis_support.parse_file
    )


def test_metal_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = repository_service._build_module_index(
        ["shaders/common.metalh", "shaders/grayscale.metal"],
        root_path=Path("/tmp/metal-index"),
    )
    text = (
        '#include "common.metalh"\n'
        "#include <metal_stdlib>\n"
        "using namespace metal;\n"
        "float luminance(float3 color) {\n"
        "    return dot(color, float3(0.2126, 0.7152, 0.0722));\n"
        "}\n"
        "kernel void grayscale(\n"
        "    texture2d<float, access::read> inputTexture [[texture(0)]],\n"
        "    texture2d<float, access::write> outputTexture [[texture(1)]],\n"
        "    uint2 gid [[thread_position_in_grid]]) {\n"
        "    float value = saturate_value(luminance(float3(1.0)));\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.metal_adapter.parse_file(
        "shaders/grayscale.metal",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_include=lambda **kwargs: repository_service.metal_adapter.resolve_include(
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
            **kwargs,
        ),
    )

    assert any(dependency.target_file == "shaders/common.metalh" for dependency in dependencies)
    assert any(symbol.symbol_name == "grayscale" for symbol in symbols)
    assert any(reference.target_file == "shaders/common.metalh" for reference in references)
    assert any(reference.target_names == ("saturate_value",) for reference in references)


def test_metal_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".metal" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("shaders/grayscale.metal"),
            text=(
                "#include <metal_stdlib>\n"
                "using namespace metal;\n"
                "kernel void grayscale(uint2 gid [[thread_position_in_grid]]) {}\n"
            ),
        )
        == "metal"
    )
    assert (
        repository_service._language_for_path(
            Path("shaders/notes.metal"),
            text="plain notes without metal shader syntax\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_metal_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "metal-profile-repo"
    (repo_path / "Sources" / "Shaders").mkdir(parents=True)
    for index in range(6):
        (repo_path / "Sources" / "Shaders" / f"shader_{index}.metal").write_text(
            "#include <metal_stdlib>\n"
            "using namespace metal;\n"
            "kernel void shader_main(uint2 gid [[thread_position_in_grid]]) {}\n",
            encoding="utf-8",
        )
    (repo_path / "Sources" / "Host").mkdir(parents=True)
    for index in range(2):
        (repo_path / "Sources" / "Host" / f"helper_{index}.swift").write_text(
            "struct HostHelper { let value = 1 }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "metal" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "metal"


def test_operational_seed_plan_without_diagnostics_does_not_force_metal_first_in_swift_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "metal-mixed-host-repo"
    (repo_path / "Sources" / "Shaders").mkdir(parents=True)
    for index in range(5):
        (repo_path / "Sources" / "Shaders" / f"shader_{index}.metal").write_text(
            "#include <metal_stdlib>\n"
            "using namespace metal;\n"
            "fragment float4 shader_main() { return float4(1.0); }\n",
            encoding="utf-8",
        )
    (repo_path / "Sources" / "App").mkdir(parents=True)
    for index in range(20):
        (repo_path / "Sources" / "App" / f"View{index}.swift").write_text(
            "struct ExampleView { let value = 1 }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "metal" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "swift"


def test_repository_snapshot_graph_contains_metal_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "metal-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "common.metalh").write_text(
        "#include <metal_stdlib>\n"
        "using namespace metal;\n"
        "float saturate_value(float value) {\n"
        "    return clamp(value, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.metal").write_text(
        '#include "common.metalh"\n'
        "#include <metal_stdlib>\n"
        "using namespace metal;\n"
        "kernel void grayscale(uint2 gid [[thread_position_in_grid]]) {\n"
        "    float value = saturate_value(0.5);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.metal", "*.metalh"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "common.metalh" and str(row["symbol_name"]) == "saturate_value"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
