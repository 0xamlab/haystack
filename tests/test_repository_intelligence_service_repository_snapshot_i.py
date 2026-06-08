"""Tests for repository_intelligence_service: repository_snapshot_i.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_graph_contains_robotframework_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "robotframework-dependency-repo"
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "resources").mkdir(parents=True)
    (repo_path / "resources" / "common.resource").write_text(
        "*** Keywords ***\n"
        "Open Login Page\n"
        "    Log    opened\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "login.robot").write_text(
        "*** Settings ***\n"
        "Resource    ../resources/common.resource\n"
        "\n"
        "*** Test Cases ***\n"
        "Valid Login\n"
        "    Open Login Page\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["tests", "resources"],
            include_patterns=[
                "tests/**/*.robot",
                "tests/*.robot",
                "resources/**/*.resource",
                "resources/*.resource",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:tests/login.robot"
        and str(row["target_node"]) == "file:resources/common.resource"
        for row in graph_rows
    )
    test_symbol_id = symbol_ids[("tests/login.robot", "Valid Login")]
    helper_symbol_id = symbol_ids[("resources/common.resource", "Open Login Page")]
    assert any(
        str(row["edge_type"]) == "calls"
        and str(row["source_node"]) == f"symbol:{test_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scss_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scss-dependency-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "_mixins.scss").write_text(
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "_functions.scss").write_text(
        "@function helper-fn() {\n"
        "  @return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "main.scss").write_text(
        '@use "mixins" as mixins;\n'
        '@import "functions";\n'
        ".button {\n"
        "  @include mixins.button-base;\n"
        "  color: helper-fn();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["styles"],
            include_patterns=["styles/*.scss", "styles/**/*.scss"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "uses"
        and str(row["source_node"]) == "file:styles/main.scss"
        and str(row["target_node"]) == "file:styles/_mixins.scss"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("styles/main.scss", "styles/main")]
    helper_symbol_id = symbol_ids[("styles/_functions.scss", "helper-fn")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_typst_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "typst-dependency-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "partials").mkdir(parents=True)
    (repo_path / "src" / "lib" / "math.typ").write_text(
        "#let add(x, y) = x + y\n"
        "#let scale(x) = x * 2\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "partials" / "common.typ").write_text(
        "#let common() = [hello]\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.typ").write_text(
        '#import "lib/math.typ": add\n'
        '#import "lib/math.typ" as math\n'
        '#include "partials/common.typ"\n'
        "#let render() = {\n"
        "  add(1, 2)\n"
        "  math.scale(3)\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/*.typ", "src/**/*.typ"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.typ"
        and str(row["target_node"]) == "file:src/lib/math.typ"
        for row in graph_rows
    )
    render_symbol_id = symbol_ids[("src/main.typ", "render")]
    scale_symbol_id = symbol_ids[("src/lib/math.typ", "scale")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{render_symbol_id}"
        and str(row["target_node"]) == f"symbol:{scale_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_cuda_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cuda-dependency-repo"
    (repo_path / "src" / "kernels").mkdir(parents=True)
    (repo_path / "src" / "kernels" / "math.cuh").write_text(
        "__device__ inline int add_one(int x) {\n"
        "  return x + 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cu").write_text(
        '#include "kernels/math.cuh"\n'
        "__global__ void kernel_run(int* out) {\n"
        "  *out = add_one(*out);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.cu", "src/**/*.cuh", "src/*.cu", "src/*.cuh"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.cu"
        and str(row["target_node"]) == "file:src/kernels/math.cuh"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/main.cu", "kernel_run")]
    helper_symbol_id = symbol_ids[("src/kernels/math.cuh", "add_one")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_hlsl_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "hlsl-dependency-repo"
    (repo_path / "shaders" / "lib").mkdir(parents=True)
    (repo_path / "shaders" / "lib" / "noise.hlsli").write_text(
        "float NoiseValue() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "shaders" / "main.hlsl").write_text(
        '#include "lib/noise.hlsli"\n'
        "float4 RenderMain() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["shaders"],
            include_patterns=["shaders/**/*.hlsl", "shaders/**/*.hlsli", "shaders/*.hlsl"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "includes"
        and str(row["source_node"]) == "file:shaders/main.hlsl"
        and str(row["target_node"]) == "file:shaders/lib/noise.hlsli"
        for row in graph_rows
    )
    render_symbol_id = symbol_ids[("shaders/main.hlsl", "RenderMain")]
    helper_symbol_id = symbol_ids[("shaders/lib/noise.hlsli", "NoiseValue")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{render_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_wgsl_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "wgsl-dependency-repo"
    (repo_path / "shaders" / "lib").mkdir(parents=True)
    (repo_path / "shaders" / "lib" / "noise.wgsl").write_text(
        "fn NoiseValue() -> f32 {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "shaders" / "main.wgsl").write_text(
        '#include "lib/noise.wgsl"\n'
        "@fragment\n"
        "fn fs_main() -> vec4f {\n"
        "  return vec4f(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["shaders"],
            include_patterns=["shaders/**/*.wgsl", "shaders/*.wgsl"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "includes"
        and str(row["source_node"]) == "file:shaders/main.wgsl"
        and str(row["target_node"]) == "file:shaders/lib/noise.wgsl"
        for row in graph_rows
    )
    render_symbol_id = symbol_ids[("shaders/main.wgsl", "fs_main")]
    helper_symbol_id = symbol_ids[("shaders/lib/noise.wgsl", "NoiseValue")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{render_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_shaderlab_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "shaderlab-dependency-repo"
    (repo_path / "Shaders" / "Includes").mkdir(parents=True)
    (repo_path / "Shaders" / "Includes" / "Common.cginc").write_text(
        "float NoiseValue() {\n"
        "  return 0.25;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Shaders" / "Main.shader").write_text(
        'Shader "Demo/Main" {\n'
        "SubShader {\n"
        "Pass {\n"
        "CGPROGRAM\n"
        '#include "Includes/Common.cginc"\n'
        "float4 frag() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDCG\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Shaders"],
            include_patterns=["Shaders/**/*.shader", "Shaders/**/*.cginc", "Shaders/*.shader"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "includes"
        and str(row["source_node"]) == "file:Shaders/Main.shader"
        and str(row["target_node"]) == "file:Shaders/Includes/Common.cginc"
        for row in graph_rows
    )
    frag_symbol_id = symbol_ids[("Shaders/Main.shader", "frag")]
    helper_symbol_id = symbol_ids[("Shaders/Includes/Common.cginc", "NoiseValue")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{frag_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_starlark_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "starlark-dependency-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "lib" / "common.bzl").write_text(
        "def render_json(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "demo.bzl").write_text(
        'load("//lib:common.bzl", "render_json")\n'
        "\n"
        "def demo_macro(name):\n"
        "    return render_json(name)\n",
        encoding="utf-8",
    )
    (repo_path / "BUILD.bazel").write_text(
        'load("//rules:demo.bzl", "demo_macro")\n'
        '\n'
        'demo_macro(name = "app")\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=[
                "**/*.bzl",
                "*.bzl",
                "**/*.star",
                "*.star",
                "**/BUILD.bazel",
                "BUILD.bazel",
                "**/BUILD",
                "BUILD",
                "MODULE.bazel",
                "WORKSPACE",
                "WORKSPACE.bazel",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:BUILD.bazel"
        and str(row["target_node"]) == "file:rules/demo.bzl"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:rules/demo.bzl"
        and str(row["target_node"]) == "file:lib/common.bzl"
        for row in graph_rows
    )
    demo_macro_symbol_id = symbol_ids[("rules/demo.bzl", "demo_macro")]
    render_json_symbol_id = symbol_ids[("lib/common.bzl", "render_json")]
    assert any(
        str(row["edge_type"]) == "calls"
        and str(row["source_node"]) == f"symbol:{demo_macro_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_json_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_nix_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "nix-dependency-repo"
    (repo_path / "nix" / "lib").mkdir(parents=True)
    (repo_path / "nix" / "lib" / "formatter.nix").write_text(
        "{ pkgs }:\n"
        "{\n"
        "  mkFormatter = package: package;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "flake.nix").write_text(
        "{\n"
        "  inputs.nixpkgs.url = \"github:NixOS/nixpkgs\";\n"
        "  outputs = { self, nixpkgs }:\n"
        "    let formatter = import ./nix/lib/formatter.nix { pkgs = nixpkgs.legacyPackages.x86_64-linux; }; in {\n"
        "      formatter = formatter.mkFormatter nixpkgs.legacyPackages.x86_64-linux.alejandra;\n"
        "    };\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.nix", "*.nix"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:flake.nix"
        and str(row["target_node"]) == "file:nix/lib/formatter.nix"
        for row in graph_rows
    )
    flake_formatter_symbol_id = symbol_ids[("flake.nix", "formatter")]
    formatter_symbol_id = symbol_ids[("nix/lib/formatter.nix", "mkFormatter")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{flake_formatter_symbol_id}"
        and str(row["target_node"]) == f"symbol:{formatter_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_v_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "v-dependency-repo"
    repo_path.mkdir()
    (repo_path / "main.v").write_text(
        "module main\n"
        "\n"
        "import helper\n"
        "\n"
        "fn run() {\n"
        "    helper.render_json()\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "helper.v").write_text(
        "module helper\n"
        "\n"
        "pub fn render_json() string {\n"
        "    return '{}'\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.v", "*.v", "v.mod"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.v"
        and str(row["target_node"]) == "file:helper.v"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("main.v", "run")]
    render_json_symbol_id = symbol_ids[("helper.v", "render_json")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_json_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_vala_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "vala-dependency-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "util").mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('demo', 'vala')\n"
        "executable('demo', ['src/demo/app/Main.vala', 'src/demo/util/Helper.vala'])\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "util" / "Helper.vala").write_text(
        "namespace Demo.Util {\n"
        "    public class Helper : Object {\n"
        "        public string render_json () {\n"
        '            return "{}";\n'
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "app" / "Main.vala").write_text(
        "using Demo.Util;\n"
        "\n"
        "namespace Demo.App {\n"
        "    public class App : Object {\n"
        "        public void run () {\n"
        "            Helper helper = new Helper ();\n"
        "            helper.render_json ();\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "meson.build"],
            include_patterns=[
                "src/**/*.vala",
                "src/*.vala",
                "*.vala",
                "**/*.vapi",
                "*.vapi",
                "meson.build",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:src/demo/app/Main.vala"
        and str(row["target_node"]) == "file:src/demo/util/Helper.vala"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/demo/app/Main.vala", "run")]
    render_symbol_id = symbol_ids[("src/demo/util/Helper.vala", "render_json")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


