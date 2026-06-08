"""Tests for repository_intelligence_real_repo_probe: operational_seed_g.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_operational_seed_plan_prefers_bicep_over_root_node_tooling(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bicep-node-mixed-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        json.dumps(
            {
                "name": "bicep-node-mixed-repo",
                "private": True,
                "scripts": {
                    "lint": "eslint .",
                },
                "devDependencies": {
                    "eslint": "^9.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    (repo_path / ".eslintrc.js").write_text(
        "module.exports = { root: true };\n",
        encoding="utf-8",
    )
    (repo_path / "bicepconfig.json").write_text("{}", encoding="utf-8")
    (repo_path / "main.bicep").write_text(
        "module child './modules/child.bicep' = {\n"
        "  name: 'child'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "child.bicep").write_text(
        "output childId string = 'demo'\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["operational_ecosystems"][0] == "bicep"
    assert "bicepconfig.json" in seed_plan["config_paths"]
    assert "package.json" in seed_plan["config_paths"]
    assert "main.bicep" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_tlaplus_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tlaplus-profile-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "MCSpec.cfg").write_text("SPECIFICATION Spec\n", encoding="utf-8")
    (repo_path / "Spec.tla").write_text(
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals, Util\n\n"
        "VARIABLES x\n\n"
        "Init == x = 0\n"
        "Next == x' = x + 1\n"
        "Spec == Init /\\ [][Next]_x\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "Util.tla").write_text(
        "---- MODULE Util ----\n"
        "Answer == 42\n",
        encoding="utf-8",
    )
    (repo_path / "MCSpec.tla").write_text(
        "---- MODULE MCSpec ----\n"
        "EXTENDS Spec\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["tlaplus"]
    assert seed_plan["operational_ecosystems"] == ["tlaplus"]
    assert "MCSpec.cfg" in seed_plan["config_paths"]
    assert "MCSpec.tla" in seed_plan["entrypoint_files"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/Util.tla" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_logtalk_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "logtalk-profile-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "loader.lgt").write_text(
        ":- initialization((\n"
        "    logtalk_load(main),\n"
        "    logtalk_load(lib/support)\n"
        ")).\n",
        encoding="utf-8",
    )
    (repo_path / "main.lgt").write_text(
        ":- object(main).\n"
        "    :- uses(support, [answer/1]).\n"
        "    run :- support::answer(_).\n"
        ":- end_object.\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "support.lgt").write_text(
        ":- object(support).\n"
        "    :- public(answer/1).\n"
        "    answer(42).\n"
        ":- end_object.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["logtalk"]
    assert seed_plan["operational_ecosystems"] == ["logtalk"]
    assert "main.lgt" in seed_plan["entrypoint_files"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/support.lgt" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_chapel_mason_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "chapel-mason-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Mason.toml").write_text(
        "[brick]\nname = \"Crypto\"\ntype = \"library\"\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Crypto.chpl").write_text(
        "module Crypto {\n"
        "use Utils;\n"
        "proc run() {\n"
        "  return helper();\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Utils.chpl").write_text(
        "module Utils {\nproc helper() { return 1; }\n}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["chapel"]
    assert seed_plan["operational_ecosystems"] == ["chapel"]
    assert "Mason.toml" in seed_plan["config_paths"]
    assert "src/Crypto.chpl" in seed_plan["entrypoint_files"]
    assert "src" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_chapel_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "chapel-manifestless-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "main.chpl").write_text(
        "module Main {\n"
        "use Utils;\n"
        "proc run() {\n"
        "  return helper();\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Utils.chpl").write_text(
        "module Utils {\nproc helper() { return 1; }\n}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["chapel"]
    assert seed_plan["operational_ecosystems"] == ["chapel"]
    assert "main.chpl" in seed_plan["entrypoint_files"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Utils.chpl" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_odin_ols_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-ols-profile-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "ols.json").write_text(
        '{"profile":"default","profiles":[{"name":"default","checker_path":["src"]}]}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.odin").write_text(
        'package main\n\nimport "src:common"\n\nmain :: proc() -> int {\n    return common.helper()\n}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "common" / "helper.odin").write_text(
        "package common\n\nhelper :: proc() -> int {\n    return 1\n}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "helper_test.odin").write_text(
        "package tests\n\nhelper_test :: proc() {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["odin"]
    assert seed_plan["operational_ecosystems"] == ["odin"]
    assert "ols.json" in seed_plan["config_paths"]
    assert "src/main.odin" in seed_plan["entrypoint_files"]
    assert "tests/helper_test.odin" not in seed_plan["entrypoint_files"]
    assert "src/common" in seed_plan["support_roots"] or "src" in seed_plan["support_roots"]
    assert "src/common/helper.odin" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_odin_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-manifestless-profile-repo"
    (repo_path / "lib" / "helper").mkdir(parents=True)
    (repo_path / "main.odin").write_text(
        'package main\n\nimport "lib:helper"\n\nmain :: proc() -> int {\n    return helper.render_json()\n}\n',
        encoding="utf-8",
    )
    (repo_path / "lib" / "helper" / "helper.odin").write_text(
        "package helper\n\nrender_json :: proc() -> int {\n    return 1\n}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["odin"]
    assert seed_plan["operational_ecosystems"] == ["odin"]
    assert "main.odin" in seed_plan["entrypoint_files"]
    assert "lib/helper" in seed_plan["support_roots"]
    assert "lib/helper/helper.odin" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_factor_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "factor-manifestless-profile-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "math" / "math.factor").write_text(
        "IN: math\n\n: square ( n -- n ) dup * ;\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "main.factor").write_text(
        "USING: math ;\nIN: app.main\n\n: run ( n -- n ) square ;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["factor"]
    assert seed_plan["operational_ecosystems"] == ["factor"]
    assert "app/main.factor" in seed_plan["entrypoint_files"]
    assert "math" in seed_plan["support_roots"] or "app" in seed_plan["support_roots"]
    assert "math/math.factor" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_cue_module_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cue-profile-repo"
    (repo_path / "cue.mod").mkdir(parents=True)
    (repo_path / "pkg" / "schema").mkdir(parents=True)
    (repo_path / "cue.mod" / "module.cue").write_text(
        'module: "example.com/demo"\n',
        encoding="utf-8",
    )
    (repo_path / "pkg" / "schema" / "schema.cue").write_text(
        "package schema\n\n#Answer: 42\n",
        encoding="utf-8",
    )
    (repo_path / "main.cue").write_text(
        'package main\n\nimport schema "example.com/demo/pkg/schema"\n\nvalue: schema.#Answer\n',
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["cue"]
    assert seed_plan["operational_ecosystems"] == ["cue"]
    assert "cue.mod/module.cue" in seed_plan["config_paths"]
    assert "main.cue" in seed_plan["entrypoint_files"]
    assert "pkg/schema" in seed_plan["support_roots"]
    assert "pkg/schema/schema.cue" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_haxe_hxml_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haxe-profile-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "build.hxml").write_text(
        "-cp src\n-main demo.Main\n",
        encoding="utf-8",
    )
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

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["haxe"]
    assert seed_plan["operational_ecosystems"] == ["haxe"]
    assert "build.hxml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/demo/Main.hx" in seed_plan["entrypoint_files"]
    assert "src/demo/Helper.hx" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_autohotkey_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autohotkey-profile-repo"
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
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "MainTests.ahk").write_text(
        "MainTests() {\n"
        "    return true\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["autohotkey"]
    assert seed_plan["operational_ecosystems"] == ["autohotkey"]
    assert seed_plan["config_paths"] == []
    assert "scripts/Main.ahk" in seed_plan["entrypoint_files"]
    assert "tests/MainTests.ahk" not in seed_plan["entrypoint_files"]
    assert "Lib" in seed_plan["support_roots"]
    assert "Lib/Helper.ahk" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_autoit_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autoit-profile-repo"
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
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "MainTests.au3").write_text(
        "Func MainTests()\n"
        "    Return True\n"
        "EndFunc\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["autoit"]
    assert seed_plan["operational_ecosystems"] == ["autoit"]
    assert seed_plan["config_paths"] == []
    assert "scripts/Main.au3" in seed_plan["entrypoint_files"]
    assert "tests/MainTests.au3" not in seed_plan["entrypoint_files"]
    assert "Includes" in seed_plan["support_roots"]
    assert "Includes/Helper.au3" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_squirrel_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "squirrel-profile-repo"
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
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "MainTests.nut").write_text(
        "::MainTests <- function () {\n"
        "  return true;\n"
        "};\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["squirrel"]
    assert seed_plan["operational_ecosystems"] == ["squirrel"]
    assert seed_plan["config_paths"] == []
    assert "scripts/vscripts/main.nut" in seed_plan["entrypoint_files"]
    assert "tests/MainTests.nut" not in seed_plan["entrypoint_files"]
    assert "scripts/vscripts" in seed_plan["support_roots"]
    assert "scripts/vscripts/ppmod.nut" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_promotes_cython_when_cython_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cython-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "core.pyx").write_text(
        "from acme.helpers cimport render_json\n"
        "\n"
        "cpdef int run():\n"
        "    return render_json()\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "helpers.pxd").write_text(
        "cdef int render_json()\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "defs.pxi").write_text(
        "DEF ANSWER = 42\n",
        encoding="utf-8",
    )
    (repo_path / "setup.py").write_text(
        "from setuptools import setup\nsetup(name='acme')\n",
        encoding="utf-8",
    )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "test_core.pyx").write_text(
        "cpdef int test_run():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "cython" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "cython"
    assert "src/acme/core.pyx" in seed_plan["entrypoint_files"]
    assert "src/acme/helpers.pxd" in seed_plan["candidate_file_paths"]
    assert "tests/test_core.pyx" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_promotes_cuda_when_cuda_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cuda-profile-repo"
    (repo_path / "src" / "kernels").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "src" / "main.cu").write_text(
        '#include "kernels/math.cuh"\n'
        "__global__ void kernel_run(int* out) {\n"
        "  *out = add_one(*out);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "kernels" / "math.cuh").write_text(
        "__device__ inline int add_one(int x) {\n"
        "  return x + 1;\n"
        "}\n",
        encoding="utf-8",
    )
    for index in range(22):
        (repo_path / "src" / f"extra_{index}.cu").write_text(
            "__global__ void kernel_extra(int* out) {\n"
            "  *out += 1;\n"
            "}\n",
            encoding="utf-8",
        )
    for index in range(6):
        (repo_path / "include" / f"helper_{index}.cuh").write_text(
            "__device__ inline int helper(int x) {\n"
            "  return x;\n"
            "}\n",
            encoding="utf-8",
        )
    for index in range(8):
        (repo_path / "src" / f"host_{index}.cpp").write_text(
            "int run_host() {\n"
            "  return 1;\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "test_kernel.cu").write_text(
        "__global__ void test_only(int* out) {\n"
        "  *out = 0;\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "cuda" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "cuda"
    assert "src/main.cu" in seed_plan["entrypoint_files"]
    assert "src/kernels/math.cuh" in seed_plan["candidate_file_paths"]
    assert "tests/test_kernel.cu" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_promotes_cuda_in_manifest_rich_cmake_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cuda-cmake-profile-repo"
    sample_count = 12
    root_cmakelists = ["cmake_minimum_required(VERSION 3.26)", "project(cuda_samples LANGUAGES CXX CUDA)"]
    for index in range(sample_count):
        sample_dir = repo_path / "samples" / f"sample_{index}"
        sample_dir.mkdir(parents=True)
        root_cmakelists.append(f"add_subdirectory(samples/sample_{index})")
        (sample_dir / "CMakeLists.txt").write_text(
            f"add_executable(sample_{index} main.cpp kernel_{index}.cu)\n",
            encoding="utf-8",
        )
        (sample_dir / "main.cpp").write_text(
            "int main() {\n"
            "  return 0;\n"
            "}\n",
            encoding="utf-8",
        )
        (sample_dir / f"kernel_{index}.cu").write_text(
            f"__global__ void run_kernel_{index}(int* out) {{\n"
            f"  *out += {index};\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "CMakeLists.txt").write_text("\n".join(root_cmakelists) + "\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "cuda" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "cuda"
    assert any(path.endswith(".cu") for path in seed_plan["candidate_file_paths"])
    assert "samples/sample_0/CMakeLists.txt" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_promotes_stan_when_stan_surface_is_substantial(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "stan-profile-repo"
    (repo_path / "models" / "lib").mkdir(parents=True)
    (repo_path / "models" / "main.stan").write_text(
        '#include "lib/math.stan"\n'
        "\n"
        "functions {\n"
        "  real run(real x) {\n"
        "    return add_one(x);\n"
        "  }\n"
        "}\n"
        "data {\n"
        "  real x;\n"
        "}\n"
        "model {\n"
        "  target += run(x);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "lib" / "math.stan").write_text(
        "functions {\n"
        "  real add_one(real x) {\n"
        "    return x + 1;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    for index in range(6):
        (repo_path / "models" / f"extra_{index}.stan").write_text(
            "data {\n"
            f"  real x_{index};\n"
            "}\n"
            "model {\n"
            f"  target += normal_lpdf(x_{index} | 0, 1);\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "analysis").mkdir(parents=True)
    for index in range(4):
        (repo_path / "analysis" / f"plot_{index}.R").write_text(
            "print('stan profile')\n",
            encoding="utf-8",
        )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "test_model.stan").write_text(
        "data {\n  real x;\n}\nmodel {\n  target += normal_lpdf(x | 0, 1);\n}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "stan" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "stan"
    assert "models/main.stan" in seed_plan["entrypoint_files"]
    assert "models/lib/math.stan" in seed_plan["candidate_file_paths"]
    assert "tests/test_model.stan" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_starlark_bazel_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "starlark-profile-repo"
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "MODULE.bazel").write_text(
        'module(name = "acme")\n',
        encoding="utf-8",
    )
    (repo_path / "BUILD.bazel").write_text(
        'load("rules:demo.bzl", "demo_macro")\n'
        '\n'
        'demo_macro(name = "app")\n',
        encoding="utf-8",
    )
    (repo_path / "rules" / "demo.bzl").write_text(
        'load("//lib:common.bzl", "render_json")\n'
        'load(":helper.bzl", "emit_name")\n'
        "\n"
        "def demo_macro(name):\n"
        "    return emit_name(render_json(name))\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "helper.bzl").write_text(
        "def emit_name(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "common.bzl").write_text(
        "def render_json(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "demo_test.bzl").write_text(
        "def test_macro(name):\n"
        "    return name\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["starlark"]
    assert seed_plan["operational_ecosystems"] == ["starlark"]
    assert "MODULE.bazel" in seed_plan["config_paths"]
    assert "BUILD.bazel" in seed_plan["config_paths"]
    assert "BUILD.bazel" in seed_plan["entrypoint_files"]
    assert "rules/demo.bzl" in seed_plan["entrypoint_files"]
    assert "rules" in seed_plan["support_roots"]
    assert "rules/demo.bzl" in seed_plan["candidate_file_paths"]
    assert "rules/helper.bzl" in seed_plan["candidate_file_paths"]
    assert "tests/demo_test.bzl" not in seed_plan["entrypoint_files"]


