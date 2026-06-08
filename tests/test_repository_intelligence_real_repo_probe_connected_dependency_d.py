"""Tests for repository_intelligence_real_repo_probe: connected_dependency_d.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_connected_dependency_map_follows_gleam_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gleam-connected-map-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "gleam.toml").write_text(
        'name = "demo"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.gleam").write_text(
        "import demo/helper.{render_json}\n\npub fn main() {\n  render_json()\n}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "helper.gleam").write_text(
        "pub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.gleam"],
        bridge_paths=["src", "gleam.toml"],
        include_patterns=["src/**/*.gleam", "src/*.gleam", "*.gleam", "gleam.toml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/demo/helper.gleam",
        "src/main.gleam",
    }


def test_connected_dependency_map_follows_janet_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "janet-connected-map-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "project.janet").write_text(
        '(declare-project :name "demo" :source @["src"] :main "src/main.janet")\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.janet").write_text(
        '(import ./demo/helper :as helper)\n\n(defn main []\n  (helper/render-json))\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "helper.janet").write_text(
        "(defn render-json [] @{})\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.janet"],
        bridge_paths=["src", "project.janet"],
        include_patterns=["src/**/*.janet", "src/*.janet", "*.janet", "project.janet"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/demo/helper.janet",
        "src/main.janet",
    }


def test_connected_dependency_map_follows_rego_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rego-connected-map-repo"
    (repo_path / "policy" / "lib").mkdir(parents=True)
    (repo_path / "policy" / "main.rego").write_text(
        "package policy.main\n\n"
        "import data.policy.lib.helpers as helper\n\n"
        "allow if {\n"
        "    helper.render_json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "policy" / "lib" / "helpers.rego").write_text(
        "package policy.lib.helpers\n\n"
        "render_json if {\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["policy/main.rego"],
        bridge_paths=["policy", "policy/lib"],
        include_patterns=["**/*.rego", "*.rego"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "policy/lib/helpers.rego",
        "policy/main.rego",
    }


def test_connected_dependency_map_follows_yara_include_and_rule_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "yara-connected-map-repo"
    (repo_path / "rules" / "lib").mkdir(parents=True)
    (repo_path / "rules" / "index.yar").write_text(
        'include "./main.yar"\n'
        'include "./lib/helper.yar"\n',
        encoding="utf-8",
    )
    (repo_path / "rules" / "main.yar").write_text(
        "rule main_rule {\n"
        "  condition:\n"
        "    helper_rule\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "lib" / "helper.yar").write_text(
        "private rule helper_rule {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["rules/index.yar"],
        bridge_paths=["rules", "rules/lib"],
        include_patterns=["**/*.yar", "*.yar", "**/*.yara", "*.yara"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert set(connected_map["connected_files"]) == {
        "rules/index.yar",
        "rules/lib/helper.yar",
        "rules/main.yar",
    }


def test_connected_dependency_map_follows_hcl_module_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hcl-connected-map-repo"
    (repo_path / "modules" / "child").mkdir(parents=True)
    (repo_path / "main.tf").write_text(
        'module "child" {\n'
        '  source = "./modules/child"\n'
        '}\n\n'
        'variable "name" {\n'
        '  default = "demo"\n'
        '}\n\n'
        "locals {\n"
        '  prefix = "vpc-${var.name}"\n'
        "}\n\n"
        'output "full_name" {\n'
        "  value = local.prefix\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "child" / "main.tf").write_text(
        'output "child_id" {\n'
        '  value = "child"\n'
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.tf"],
        bridge_paths=[".", "modules/child"],
        include_patterns=["**/*.tf", "*.tf", "**/*.hcl", "*.hcl"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "main.tf",
        "modules/child/main.tf",
    }


def test_connected_dependency_map_follows_agda_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "agda-connected-map-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "standard-library.agda-lib").write_text(
        "name: demo\ninclude: src\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.agda").write_text(
        "module Main where\n\n"
        "open import Data.Helper using (helper)\n\n"
        "main : Set\n"
        "main = helper\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Data" / "Helper.agda").write_text(
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.agda"],
        bridge_paths=["src", "standard-library.agda-lib"],
        include_patterns=["src/**/*.agda", "src/*.agda", "*.agda", "*.agda-lib"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/Data/Helper.agda",
        "src/Main.agda",
    }


def test_connected_dependency_map_follows_idris_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "idris-connected-map-repo"
    (repo_path / "src" / "Demo").mkdir(parents=True)
    (repo_path / "demo.ipkg").write_text(
        "package demo\n"
        "sourcedir = src\n"
        "modules = Demo.Helper\n"
        "main = Main\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.idr").write_text(
        "module Main\n\n"
        "import Demo.Helper\n\n"
        "main : IO ()\n"
        "main = renderJson\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo" / "Helper.idr").write_text(
        "module Demo.Helper\n\n"
        "renderJson : IO ()\n"
        "renderJson = pure ()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.idr"],
        bridge_paths=["src", "demo.ipkg"],
        include_patterns=["src/**/*.idr", "src/*.idr", "*.idr", "*.lidr", "*.ipkg"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/Demo/Helper.idr",
        "src/Main.idr",
    }


def test_connected_dependency_map_follows_raku_use_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "raku-connected-map-repo"
    (repo_path / "lib" / "Demo").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "META6.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "provides": {"Demo::Helper": "lib/Demo/Helper.rakumod"},
                "bin": ["demo.raku"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "lib" / "Demo" / "Helper.rakumod").write_text(
        "unit module Demo::Helper;\n\nsub render-json() is export { \"{}\" }\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "demo.raku").write_text(
        "use Demo::Helper;\n\nsub main() {\n    Demo::Helper::render-json();\n}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["bin/demo.raku"],
        bridge_paths=["bin", "lib", "META6.json"],
        include_patterns=[
            "bin/**/*.raku",
            "bin/*.raku",
            "lib/**/*.rakumod",
            "lib/*.rakumod",
            "META6.json",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "bin/demo.raku",
        "lib/Demo/Helper.rakumod",
    }


def test_connected_dependency_map_follows_nushell_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nushell-connected-map-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "main.nu").write_text(
        "source modules/helper.nu\n\n"
        "def main [] {\n"
        "  render-json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "helper.nu").write_text(
        "export def render-json [] {\n"
        "  '{}'\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.nu"],
        bridge_paths=["modules"],
        include_patterns=["modules/**/*.nu", "*.nu"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "main.nu",
        "modules/helper.nu",
    }


def test_connected_dependency_map_follows_fish_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fish-connected-map-repo"
    (repo_path / "functions").mkdir(parents=True)
    (repo_path / "main.fish").write_text(
        "source functions/helper.fish\n\n"
        "function main\n"
        "    helper\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "functions" / "helper.fish").write_text(
        "function helper\n"
        "    echo '{}'\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.fish"],
        bridge_paths=["functions"],
        include_patterns=["functions/**/*.fish", "*.fish"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "functions/helper.fish",
        "main.fish",
    }


def test_connected_dependency_map_follows_haxe_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haxe-connected-map-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "Main.hx").write_text(
        "package demo;\n"
        "\n"
        "import demo.Helper;\n"
        "\n"
        "class Main {\n"
        "    static function main() {\n"
        "        Helper.renderJson();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "Helper.hx").write_text(
        "package demo;\n"
        "\n"
        "class Helper {\n"
        "    public static function renderJson():String {\n"
        '        return "{}";\n'
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/demo/Main.hx"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.hx", "src/*.hx", "*.hx", "*.hxml", "project.xml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1


def test_connected_dependency_map_follows_autohotkey_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autohotkey-connected-map-repo"
    (repo_path / "Lib").mkdir(parents=True)
    (repo_path / "Lib" / "Helper.ahk").write_text(
        "RenderJson(value) {\n"
        "    return value\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "Main.ahk").write_text(
        '#Include "../Lib/Helper.ahk"\n'
        "\n"
        "Main() {\n"
        '    return RenderJson("{}")\n'
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/Main.ahk"],
        bridge_paths=["scripts", "Lib"],
        include_patterns=["scripts/**/*.ahk", "scripts/*.ahk", "Lib/**/*.ahk", "Lib/*.ahk"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "scripts/Main.ahk" in connected_map["connected_files"]
    assert "Lib/Helper.ahk" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {"scripts/Main.ahk", "Lib/Helper.ahk"}


def test_connected_dependency_map_follows_autoit_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autoit-connected-map-repo"
    (repo_path / "Includes").mkdir(parents=True)
    (repo_path / "Includes" / "Helper.au3").write_text(
        "Func RenderJson($value)\n"
        "    Return $value\n"
        "EndFunc\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "Main.au3").write_text(
        '#include "../Includes/Helper.au3"\n'
        "\n"
        "Func Main()\n"
        '    Return RenderJson("{}")\n'
        "EndFunc\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/Main.au3"],
        bridge_paths=["scripts", "Includes"],
        include_patterns=[
            "scripts/**/*.au3",
            "scripts/*.au3",
            "Includes/**/*.au3",
            "Includes/*.au3",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "scripts/Main.au3" in connected_map["connected_files"]
    assert "Includes/Helper.au3" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "scripts/Main.au3",
        "Includes/Helper.au3",
    }


def test_connected_dependency_map_follows_squirrel_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "squirrel-connected-map-repo"
    (repo_path / "scripts" / "vscripts").mkdir(parents=True)
    (repo_path / "scripts" / "vscripts" / "main.nut").write_text(
        'IncludeScript("ppmod");\n'
        '::main <- function () {\n'
        "  ppmod.run();\n"
        "};\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "vscripts" / "ppmod.nut").write_text(
        "::ppmod <- {\n"
        "  run = function () {\n"
        '    return "ok";\n'
        "  }\n"
        "};\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/vscripts/main.nut"],
        bridge_paths=["scripts/vscripts"],
        include_patterns=[
            "scripts/vscripts/**/*.nut",
            "scripts/vscripts/*.nut",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "scripts/vscripts/main.nut" in connected_map["connected_files"]
    assert "scripts/vscripts/ppmod.nut" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "scripts/vscripts/main.nut",
        "scripts/vscripts/ppmod.nut",
    }


def test_connected_dependency_map_follows_cython_import_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cython-connected-map-repo"
    (repo_path / "pkg").mkdir(parents=True)
    (repo_path / "pkg" / "defs.pxi").write_text(
        "DEF ANSWER = 42\n",
        encoding="utf-8",
    )
    (repo_path / "pkg" / "helpermod.pxd").write_text(
        "cdef int helper()\n",
        encoding="utf-8",
    )
    (repo_path / "pkg" / "main.pyx").write_text(
        'include "defs.pxi"\n'
        "from helpermod cimport helper\n"
        "\n"
        "cpdef int run():\n"
        "    return helper()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["pkg/main.pyx"],
        bridge_paths=["pkg"],
        include_patterns=[
            "pkg/**/*.pyx",
            "pkg/**/*.pxd",
            "pkg/**/*.pxi",
            "pkg/*.pyx",
            "pkg/*.pxd",
            "pkg/*.pxi",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "pkg/main.pyx" in connected_map["connected_files"]
    assert "pkg/helpermod.pxd" in connected_map["connected_files"]
    assert "pkg/defs.pxi" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 2


def test_connected_dependency_map_follows_cuda_include_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "cuda-connected-map-repo"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.cu"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.cu", "src/**/*.cuh", "src/*.cu", "src/*.cuh"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "src/main.cu" in connected_map["connected_files"]
    assert "src/kernels/math.cuh" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1


def test_connected_dependency_map_follows_hlsl_include_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "hlsl-connected-map-repo"
    (repo_path / "shaders" / "include").mkdir(parents=True)
    (repo_path / "shaders" / "include" / "noise.hlsli").write_text(
        "float NoiseValue() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "shaders" / "main.hlsl").write_text(
        '#include "include/noise.hlsli"\n'
        "float4 RenderMain() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["shaders/main.hlsl"],
        bridge_paths=["shaders"],
        include_patterns=["shaders/**/*.hlsl", "shaders/**/*.hlsli", "shaders/*.hlsl"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "shaders/main.hlsl" in connected_map["connected_files"]
    assert "shaders/include/noise.hlsli" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1


def test_connected_dependency_map_follows_shaderlab_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shaderlab-connected-map-repo"
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
        "HLSLPROGRAM\n"
        '#include "Includes/Common.cginc"\n'
        "float4 frag() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDHLSL\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["Shaders/Main.shader"],
        bridge_paths=["Shaders"],
        include_patterns=["Shaders/**/*.shader", "Shaders/**/*.cginc", "Shaders/*.shader"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "Shaders/Main.shader" in connected_map["connected_files"]
    assert "Shaders/Includes/Common.cginc" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1


