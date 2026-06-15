"""Tests for repository_intelligence_real_repo_probe: operational_seed_e.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

import benchmarks.repository_intelligence_real_repo_probe_profile_ecosystem_support as ecosystem_support
import benchmarks.repository_intelligence_real_repo_probe_profile_project_family_support as project_family_support

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_operational_seed_plan_without_diagnostics_detects_manifestless_ladder_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ladder-profile-repo"
    (repo_path / "logic").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "logic" / "Child.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="SupportProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="ChildRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[XIC(StartPB)OTE(RunMotor);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "logic" / "Main.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="MainProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="MainRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[JSR(ChildRoutine,0);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "logic" / "Types.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        '<RSLogix5000Content TargetType="DataType">\n'
        '  <Controller Name="PlantController">\n'
        "    <DataTypes>\n"
        '      <DataType Name="MotorStatus">\n'
        "        <Members>\n"
        '          <Member Name="Running" DataType="BOOL"/>\n'
        "        </Members>\n"
        "      </DataType>\n"
        "    </DataTypes>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "MainTest.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="TestController">\n'
        "    <Programs>\n"
        '      <Program Name="TestProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="TestRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[XIC(TestPB)OTE(TestCoil);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["ladder"]
    assert seed_plan["operational_ecosystems"] == ["ladder"]
    assert "logic" in seed_plan["support_roots"]
    assert "logic/Main.L5X" in seed_plan["entrypoint_files"]
    assert "logic/Child.L5X" in seed_plan["entrypoint_files"]
    assert "logic/Types.L5X" not in seed_plan["entrypoint_files"]
    assert "tests/MainTest.L5X" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_asconfig_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "actionscript-profile-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "base").mkdir(parents=True)
    (repo_path / "src" / "demo" / "utils").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "asconfig.json").write_text(
        "{\n"
        '  "compilerOptions": {\n'
        '    "source-path": ["src"],\n'
        '    "mainClass": "demo.app.Main"\n'
        "  },\n"
        '  "files": ["src/demo/utils/Utils.as"]\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "base" / "BaseActor.as").write_text(
        "package demo.base {\n"
        "    public class BaseActor {\n"
        "        public function baseReady():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "utils" / "Utils.as").write_text(
        "package demo.utils {\n"
        "    public class Utils {\n"
        "        public static function helper():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "app" / "Main.as").write_text(
        "package demo.app {\n"
        "    import demo.base.BaseActor;\n"
        "    import demo.utils.Utils;\n"
        "    public class Main extends BaseActor {\n"
        "        public function boot():void {\n"
        "            Utils.helper();\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "MainTest.as").write_text(
        "package demo.tests {\n"
        "    public class MainTest {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["actionscript"]
    assert seed_plan["operational_ecosystems"] == ["actionscript"]
    assert "asconfig.json" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/demo/app/Main.as" in seed_plan["entrypoint_files"]
    assert "src/demo/utils/Utils.as" in seed_plan["entrypoint_files"]
    assert "tests/MainTest.as" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_awk_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "awk-profile-repo"
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "bin" / "translate").write_text(
        "#!/usr/bin/env gawk -f\n"
        '@include "../lib/math.awk"\n'
        "BEGIN {\n"
        "    print add(1, 2)\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "math.awk").write_text(
        "function add(a, b) {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "translate_test.awk").write_text(
        "BEGIN { print add(0, 0) }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["awk"]
    assert seed_plan["operational_ecosystems"] == ["awk"]
    assert seed_plan["config_paths"] == []
    assert any(root in seed_plan["support_roots"] for root in {"bin", "lib"})
    assert "bin/translate" in seed_plan["entrypoint_files"]
    assert "tests/translate_test.awk" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_cakefile_coffeescript_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coffeescript-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "Cakefile").write_text(
        "task 'build', ->\n"
        "  require './src/main'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper.coffee").write_text(
        "renderJson = (value) ->\n"
        "  value\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.coffee").write_text(
        "helper = require './helper'\n"
        "run = ->\n"
        "  helper.renderJson '{}'\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "main_test.coffee").write_text(
        "run = ->\n"
        "  true\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["coffeescript"]
    assert seed_plan["operational_ecosystems"] == ["coffeescript"]
    assert "Cakefile" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.coffee" in seed_plan["entrypoint_files"]
    assert "src/helper.coffee" in seed_plan["candidate_file_paths"]
    assert "test/main_test.coffee" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_elm_profile(tmp_path: Path) -> None:
    repo_path = tmp_path / "elm-profile-repo"
    (repo_path / "src" / "Page").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "elm.json").write_text(
        json.dumps(
            {
                "type": "application",
                "source-directories": ["src"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.elm").write_text(
        "module Main exposing (main)\n\n"
        "import Page.Home exposing (homeView)\n\n"
        "main : String\n"
        "main =\n"
        "    homeView\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Page" / "Home.elm").write_text(
        "module Page.Home exposing (homeView)\n\n"
        "homeView : String\n"
        "homeView =\n"
        "    \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "MainTest.elm").write_text(
        "module MainTest exposing (suite)\n\nsuite = []\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["elm"]
    assert seed_plan["operational_ecosystems"] == ["elm"]
    assert seed_plan["config_paths"] == ["elm.json"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Main.elm" in seed_plan["entrypoint_files"]
    assert "src/Page/Home.elm" in seed_plan["entrypoint_files"]
    assert "tests/MainTest.elm" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_vala_meson_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vala-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('demo', 'vala')\n"
        "executable('demo', ['src/main.vala', 'src/helper.vala'])\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper.vala").write_text(
        "namespace Demo.Util {\n"
        "    public class Helper : Object {\n"
        "        public string render_json () {\n"
        '            return "{}";\n'
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.vala").write_text(
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
    (repo_path / "tests" / "main_test.vala").write_text(
        "void main () {\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["meson", "vala"]
    assert seed_plan["operational_ecosystems"] == ["vala", "meson"]
    assert "meson.build" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.vala" in seed_plan["entrypoint_files"]
    assert "src/helper.vala" in seed_plan["candidate_file_paths"]
    assert "tests/main_test.vala" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_mql5_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mql5-profile-repo"
    (repo_path / "Experts").mkdir(parents=True)
    (repo_path / "Include").mkdir(parents=True)
    (repo_path / "Tests").mkdir(parents=True)
    (repo_path / "demo.mqproj").write_text(
        '<Project><Files><File>Experts/Main.mq5</File><File>Include/Helper.mqh</File></Files></Project>\n',
        encoding="utf-8",
    )
    (repo_path / "Include" / "Helper.mqh").write_text(
        "class Helper\n"
        "{\n"
        "public:\n"
        "   string RenderJson()\n"
        "     {\n"
        '      return "{}";\n'
        "     }\n"
        "};\n",
        encoding="utf-8",
    )
    (repo_path / "Experts" / "Main.mq5").write_text(
        '#include "../Include/Helper.mqh"\n'
        "void OnStart()\n"
        "{\n"
        "   Helper helper;\n"
        "   helper.RenderJson();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Tests" / "MainTest.mq5").write_text(
        "void OnStart()\n"
        "{\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["mql5"]
    assert seed_plan["operational_ecosystems"] == ["mql5"]
    assert "demo.mqproj" in seed_plan["config_paths"]
    assert "Experts" in seed_plan["support_roots"]
    assert "Include" in seed_plan["support_roots"]
    assert "Experts/Main.mq5" in seed_plan["entrypoint_files"]
    assert "Include/Helper.mqh" in seed_plan["candidate_file_paths"]
    assert "Tests/MainTest.mq5" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_gams_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gams-profile-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "models" / "main.gms").write_text(
        "$include ../include/common.inc\n"
        "set i /a,b/;\n"
        "parameter demand(i);\n",
        encoding="utf-8",
    )
    (repo_path / "include" / "common.inc").write_text(
        "parameter supply(i);\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["gams"]
    assert seed_plan["operational_ecosystems"] == ["gams"]
    assert "models/main.gms" in seed_plan["config_paths"]
    assert "models" in seed_plan["support_roots"]
    assert "include" in seed_plan["support_roots"]
    assert "models/main.gms" in seed_plan["entrypoint_files"]
    assert "include/common.inc" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_openscad_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "openscad-profile-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "examples").mkdir(parents=True)
    (repo_path / "main.scad").write_text(
        "include <lib/helper.scad>;\n"
        "module build() {\n"
        "  gusset(10);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "helper.scad").write_text(
        "module gusset(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "examples" / "demo.scad").write_text(
        "use <../lib/helper.scad>;\n"
        "gusset(5);\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["openscad"]
    assert seed_plan["operational_ecosystems"] == ["openscad"]
    assert "main.scad" in seed_plan["config_paths"]
    assert "main.scad" in seed_plan["entrypoint_files"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/helper.scad" in seed_plan["candidate_file_paths"]
    assert "examples/demo.scad" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_git_listing_for_manifestless_openscad_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "openscad-git-profile-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "examples").mkdir(parents=True)
    (repo_path / "main.scad").write_text(
        "include <lib/helper.scad>;\n"
        "module build() {\n"
        "  gusset(10);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "helper.scad").write_text(
        "module gusset(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "examples" / "demo.scad").write_text(
        "use <../lib/helper.scad>;\n"
        "gusset(5);\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    project_family_support.clear_starlark_profile_hint_cache()

    original_rglob = Path.rglob

    def _guarded_rglob(self: Path, pattern: str):
        if self == repo_path and pattern == "*.scad":
            raise AssertionError(
                "git-backed OpenSCAD seed planning should avoid repo-wide scad rglob"
            )
        return original_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", _guarded_rglob)

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["openscad"]
    assert seed_plan["operational_ecosystems"] == ["openscad"]
    assert "main.scad" in seed_plan["config_paths"]
    assert "main.scad" in seed_plan["entrypoint_files"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/helper.scad" in seed_plan["candidate_file_paths"]
    assert "examples/demo.scad" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_nix_flake_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nix-profile-repo"
    (repo_path / "nix" / "lib").mkdir(parents=True)
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
    (repo_path / "nix" / "lib" / "formatter.nix").write_text(
        "{ pkgs }:\n"
        "{\n"
        "  mkFormatter = package: package;\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["nix"]
    assert seed_plan["operational_ecosystems"] == ["nix"]
    assert "flake.nix" in seed_plan["config_paths"]
    assert "flake.nix" in seed_plan["entrypoint_files"]
    assert "nix/lib" in seed_plan["support_roots"]
    assert "nix/lib/formatter.nix" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_purescript_spago_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "purescript-profile-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "spago.yaml").write_text(
        "package:\n"
        "  name: demo\n"
        "workspace:\n"
        "  package_set:\n"
        "    registry: 64.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.purs").write_text(
        "module Main where\n\nimport Data.Helper (helperValue)\n\nmain = helperValue\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Data" / "Helper.purs").write_text(
        "module Data.Helper where\n\nhelperValue :: Int\nhelperValue = 1\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "Main.purs").write_text(
        "module Test.Main where\n\nmain = 1\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["purescript"]
    assert seed_plan["operational_ecosystems"] == ["purescript"]
    assert "spago.yaml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Main.purs" in seed_plan["entrypoint_files"]
    assert "test/Main.purs" not in seed_plan["entrypoint_files"]
    assert "src/Data/Helper.purs" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_gleam_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gleam-profile-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
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
    (repo_path / "test" / "main.gleam").write_text(
        "pub fn test_main() {\n  Nil\n}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["gleam"]
    assert seed_plan["operational_ecosystems"] == ["gleam"]
    assert "gleam.toml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.gleam" in seed_plan["entrypoint_files"]
    assert "test/main.gleam" not in seed_plan["entrypoint_files"]
    assert "src/demo/helper.gleam" in seed_plan["candidate_file_paths"]


def test_gleam_profile_hints_skip_project_root_rescan_when_conventional_roots_exist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "gleam-profile-hints-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "gleam.toml").write_text(
        'name = "demo"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.gleam").write_text(
        "pub fn main() {\n  Nil\n}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "helper.gleam").write_text(
        "pub fn helper() {\n  Nil\n}\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "main.gleam").write_text(
        "pub fn test_main() {\n  Nil\n}\n",
        encoding="utf-8",
    )

    original_rglob = Path.rglob
    project_root_scan_count = {"value": 0}

    def counting_rglob(self: Path, pattern: str):
        if self == repo_path and pattern == "*.gleam":
            project_root_scan_count["value"] += 1
        return original_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", counting_rglob)

    entrypoints, roots, configs = ecosystem_support._gleam_profile_hints(
        repo_path,
        "gleam.toml",
    )

    assert "src/main.gleam" in entrypoints
    assert "src" in roots
    assert "test" in roots
    assert configs == {"gleam.toml"}
    assert project_root_scan_count["value"] == 0


def test_operational_seed_plan_without_diagnostics_uses_janet_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "janet-profile-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
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
    (repo_path / "test" / "main.janet").write_text(
        "(defn test-main [] @{})\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["janet"]
    assert seed_plan["operational_ecosystems"] == ["janet"]
    assert "project.janet" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.janet" in seed_plan["entrypoint_files"]
    assert "test/main.janet" not in seed_plan["entrypoint_files"]
    assert "src/demo/helper.janet" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_dhall_package_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dhall-profile-repo"
    (repo_path / "schemas").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "package.dhall").write_text(
        "{ Type = ./schemas/Step.dhall }\n",
        encoding="utf-8",
    )
    (repo_path / "schemas" / "Step.dhall").write_text(
        "{ Type = \"step\", default = \"run\" }\n",
        encoding="utf-8",
    )
    (repo_path / "workflow.dhall").write_text(
        "let Package = ./package.dhall\nin Package.Type\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "workflow_test.dhall").write_text(
        "let Package = ../package.dhall\nin Package.Type\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["dhall"]
    assert seed_plan["operational_ecosystems"] == ["dhall"]
    assert "package.dhall" in seed_plan["config_paths"]
    assert "package.dhall" in seed_plan["entrypoint_files"]
    assert "schemas" in seed_plan["support_roots"]
    assert "workflow.dhall" in seed_plan["candidate_file_paths"]
    assert "tests/workflow_test.dhall" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_batchfile_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "batchfile-profile-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "build.bat").write_text(
        "@echo off\n"
        "call scripts\\helper.cmd\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "helper.cmd").write_text(
        "@echo off\n"
        "echo helper\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "ignored.bat").write_text(
        "@echo off\n"
        "echo ignored\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["batchfile"]
    assert seed_plan["operational_ecosystems"] == ["batchfile"]
    assert "build.bat" in seed_plan["entrypoint_files"]
    assert "scripts" in seed_plan["support_roots"]
    assert "tests/ignored.bat" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_makefile_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "makefile-profile-repo"
    (repo_path / "mk").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Makefile").write_text(
        "include mk/common.mk\n"
        "build: clean\n"
        "\t$(MAKE) helper\n"
        "clean:\n"
        "\t@echo clean\n",
        encoding="utf-8",
    )
    (repo_path / "mk" / "common.mk").write_text(
        "helper:\n"
        "\t@echo helper\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "ignored.mk").write_text(
        "ignored:\n"
        "\t@echo ignored\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["makefile"]
    assert seed_plan["operational_ecosystems"] == ["makefile"]
    assert "Makefile" in seed_plan["entrypoint_files"]
    assert "mk" in seed_plan["support_roots"]
    assert "tests/ignored.mk" not in seed_plan["entrypoint_files"]
