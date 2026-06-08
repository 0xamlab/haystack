"""Tests for repository_intelligence_service: languages_b.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_bicep_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bicep-alias-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "modules" / "main.bicep").write_text(
        "param name string\n\n"
        "var prefix = name\n\n"
        "output fullName string = prefix\n",
        encoding="utf-8",
    )

    aliases = repository_service.bicep_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/main.bicep",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "modules/main.bicep" in aliases
    assert "modules/main" in aliases
    assert "modules" in aliases
    assert "modules.main" in aliases
    assert "name" in aliases
    assert "prefix" in aliases
    assert "fullName" in aliases
    assert "modules.fullName" in aliases


def test_tlaplus_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tlaplus-alias-repo"
    (repo_path / "specs").mkdir(parents=True)
    (repo_path / "specs" / "Spec.tla").write_text(
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals\n\n"
        "Foo == 1\n"
        "VARIABLES x\n"
        "CONSTANTS Y\n",
        encoding="utf-8",
    )

    aliases = repository_service.tlaplus_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="specs/Spec.tla",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "specs/Spec.tla" in aliases
    assert "specs/Spec" in aliases
    assert "Spec" in aliases
    assert "Foo" in aliases
    assert "Spec.Foo" in aliases
    assert "Spec!Foo" in aliases
    assert "x" in aliases
    assert "Y" in aliases


def test_logtalk_adapter_module_aliases_include_entity_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "logtalk-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.lgt").write_text(
        ":- object(main).\n"
        "    :- public(run/0).\n"
        "    run :- helper::answer(_).\n"
        ":- end_object.\n",
        encoding="utf-8",
    )

    aliases = repository_service.logtalk_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.lgt",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/main.lgt" in aliases
    assert "src/main" in aliases
    assert "main" in aliases
    assert "run" in aliases
    assert "main.run" in aliases


def test_chapel_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "chapel-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Main.chpl").write_text(
        "module Main {\n"
        "proc run() { return helper(); }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.chapel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Main.chpl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Main.chpl" in aliases
    assert "src/Main" in aliases
    assert "Main" in aliases
    assert "run" in aliases
    assert "Main.run" in aliases


def test_eiffel_adapter_module_aliases_include_class_and_feature_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "eiffel-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )

    aliases = repository_service.eiffel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/application.e",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/application.e" in aliases
    assert "src/application" in aliases
    assert "application" in aliases
    assert "APPLICATION" in aliases
    assert "make" in aliases
    assert "APPLICATION.make" in aliases


def test_raku_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "raku-alias-repo"
    (repo_path / "lib" / "Demo").mkdir(parents=True)
    (repo_path / "lib" / "Demo" / "Helper.rakumod").write_text(
        "unit module Demo::Helper;\n\nsub render-json() { }\nclass Builder { }\n",
        encoding="utf-8",
    )

    aliases = repository_service.raku_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="lib/Demo/Helper.rakumod",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "lib/Demo/Helper.rakumod" in aliases
    assert "lib/Demo/Helper" in aliases
    assert "Demo::Helper" in aliases
    assert "Demo/Helper" in aliases
    assert "Helper" in aliases
    assert "render-json" in aliases
    assert "Builder" in aliases
    assert "Demo::Helper::render-json" in aliases


def test_agda_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "agda-alias-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "src" / "Data" / "Helper.agda").write_text(
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n",
        encoding="utf-8",
    )

    aliases = repository_service.agda_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Data/Helper.agda",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Data/Helper.agda" in aliases
    assert "src/Data/Helper" in aliases
    assert "src.Data.Helper" in aliases
    assert "Data.Helper" in aliases
    assert "Data/Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases
    assert "Data.Helper.helper" in aliases


def test_idris_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "idris-alias-repo"
    (repo_path / "src" / "Demo").mkdir(parents=True)
    (repo_path / "src" / "Demo" / "Helper.idr").write_text(
        "module Demo.Helper\n\n"
        "record Builder where\n"
        "  constructor MkBuilder\n\n"
        "renderJson : IO ()\n"
        "renderJson = pure ()\n",
        encoding="utf-8",
    )

    aliases = repository_service.idris_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Demo/Helper.idr",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Demo/Helper.idr" in aliases
    assert "src/Demo/Helper" in aliases
    assert "src.Demo.Helper" in aliases
    assert "Demo.Helper" in aliases
    assert "Demo/Helper" in aliases
    assert "Helper" in aliases
    assert "Builder" in aliases
    assert "renderJson" in aliases
    assert "Demo.Helper.renderJson" in aliases


def test_nushell_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nushell-alias-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "modules" / "helper.nu").write_text(
        "export def render-json [] {\n"
        "  '{}'\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.nushell_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/helper.nu",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "modules/helper.nu" in aliases
    assert "modules/helper" in aliases
    assert "helper" in aliases
    assert "render-json" in aliases
    assert "helper render-json" in aliases


def test_fish_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fish-alias-repo"
    (repo_path / "functions").mkdir(parents=True)
    (repo_path / "functions" / "helper.fish").write_text(
        "function helper --description 'render data'\n"
        "    render_json\n"
        "end\n",
        encoding="utf-8",
    )

    aliases = repository_service.fish_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="functions/helper.fish",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "functions/helper.fish" in aliases
    assert "functions/helper" in aliases
    assert "functions.helper" in aliases
    assert "helper" in aliases
    assert "helper.helper" in aliases


def test_batchfile_adapter_module_aliases_include_script_and_label_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "batchfile-alias-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "build.bat").write_text(
        "@echo off\n"
        ":setup\n"
        "call :done\n"
        ":done\n"
        "exit /b 0\n",
        encoding="utf-8",
    )

    aliases = repository_service.batchfile_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/build.bat",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/build.bat" in aliases
    assert "scripts/build" in aliases
    assert "scripts.build" in aliases
    assert "build" in aliases
    assert "setup" in aliases
    assert "done" in aliases


def test_makefile_adapter_module_aliases_include_makefile_and_target_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "makefile-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "Makefile").write_text(
        "build: clean\n"
        "\t$(MAKE) helper\n"
        "clean:\n"
        "\t@echo clean\n",
        encoding="utf-8",
    )

    aliases = repository_service.makefile_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Makefile",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Makefile" in aliases
    assert "build" in aliases
    assert "clean" in aliases


def test_cmake_adapter_module_aliases_include_project_and_target_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cmake-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text(
        "project(acme)\n"
        "add_library(acme_core INTERFACE)\n"
        "function(configure_runtime target)\n"
        "endfunction()\n",
        encoding="utf-8",
    )

    aliases = repository_service.cmake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="CMakeLists.txt",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "CMakeLists.txt" in aliases
    assert "acme" in aliases
    assert "acme_core" in aliases
    assert "configure_runtime" in aliases


def test_meson_adapter_module_aliases_include_project_and_target_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "meson-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('acme', 'c')\n"
        "library('acme_core', 'src/core.c')\n"
        "custom_target('codegen')\n",
        encoding="utf-8",
    )

    aliases = repository_service.meson_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="meson.build",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "meson.build" in aliases
    assert "acme" in aliases
    assert "acme_core" in aliases
    assert "codegen" in aliases


def test_just_adapter_module_aliases_include_recipe_and_alias_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "just-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "Justfile").write_text(
        "alias ci := check\n"
        "check:\n"
        "  just build\n"
        "build:\n"
        "  echo build\n",
        encoding="utf-8",
    )

    aliases = repository_service.just_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Justfile",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Justfile" in aliases
    assert "ci" in aliases
    assert "check" in aliases
    assert "build" in aliases


def test_qmake_adapter_module_aliases_include_target_and_subdir_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qmake-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "project.pro").write_text(
        "TEMPLATE = subdirs\n"
        "TARGET = acme\n"
        "SUBDIRS += core app\n"
        "app.depends = core\n",
        encoding="utf-8",
    )

    aliases = repository_service.qmake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="project.pro",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "project.pro" in aliases
    assert "acme" in aliases
    assert "core" in aliases
    assert "app" in aliases


def test_qml_adapter_module_aliases_include_qmldir_module_component_and_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qml-alias-repo"
    (repo_path / "controls").mkdir(parents=True)
    (repo_path / "qmldir").write_text(
        "module Demo.Controls\n"
        "Button 1.0 controls/Button.qml\n",
        encoding="utf-8",
    )
    (repo_path / "controls" / "Button.qml").write_text(
        "Rectangle {\n"
        "    id: buttonRoot\n"
        "    function press() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.qml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="controls/Button.qml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "controls/Button.qml" in aliases
    assert "Button" in aliases
    assert "Demo.Controls.Button" in aliases
    assert "buttonRoot" in aliases
    assert "press" in aliases


def test_bitbake_adapter_module_aliases_include_recipe_class_and_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bitbake-alias-repo"
    (repo_path / "recipes-core" / "images").mkdir(parents=True)
    (repo_path / "classes").mkdir(parents=True)
    (repo_path / "recipes-core" / "images" / "core-image-minimal.bb").write_text(
        'require ../base/base.inc\n'
        "inherit image\n"
        'IMAGE_FEATURES += "ssh-server-dropbear"\n'
        "python do_install() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "classes" / "image.bbclass").write_text(
        "python image_do_rootfs() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.bitbake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="recipes-core/images/core-image-minimal.bb",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "recipes-core/images/core-image-minimal.bb" in aliases
    assert "recipes-core/images/core-image-minimal" in aliases
    assert "recipes-core.images.core-image-minimal" in aliases
    assert "core-image-minimal" in aliases
    assert "recipe:core-image-minimal" in aliases
    assert "do_install" in aliases


def test_bitbake_adapter_module_aliases_use_supplied_text_without_rereading(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bitbake-inline-text-repo"
    recipe_text = (
        'DESCRIPTION = "demo"\n'
        "python do_install() {\n"
        "    pass\n"
        "}\n"
    )

    aliases = repository_service.bitbake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="recipes-core/images/core-image-minimal.bb",
        stable_identifier=repository_service._stable_identifier,
        text=recipe_text,
    )

    assert "recipes-core/images/core-image-minimal.bb" in aliases
    assert "core-image-minimal" in aliases
    assert "recipe:core-image-minimal" in aliases
    assert "do_install" in aliases


def test_cue_adapter_module_aliases_include_module_prefix_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cue-alias-repo"
    (repo_path / "cue.mod").mkdir(parents=True)
    (repo_path / "pkg" / "schema").mkdir(parents=True)
    (repo_path / "cue.mod" / "module.cue").write_text(
        'module: "example.com/demo"\n',
        encoding="utf-8",
    )
    (repo_path / "pkg" / "schema" / "schema.cue").write_text(
        "package schema\n\n#Answer: 42\nconfig: #Answer\n",
        encoding="utf-8",
    )

    aliases = repository_service.cue_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="pkg/schema/schema.cue",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "pkg/schema/schema.cue" in aliases
    assert "pkg/schema" in aliases
    assert "example.com/demo/pkg/schema" in aliases
    assert "schema" in aliases
    assert "#Answer" in aliases
    assert "schema.#Answer" in aliases


def test_factor_adapter_module_aliases_include_vocabulary_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "factor-alias-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "math" / "math.factor").write_text(
        "IN: math\n\n: square ( n -- n ) dup * ;\n",
        encoding="utf-8",
    )

    aliases = repository_service.factor_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="math/math.factor",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "math/math.factor" in aliases
    assert "math/math" in aliases
    assert "math" in aliases
    assert "square" in aliases
    assert "math.square" in aliases


def test_haxe_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haxe-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
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

    aliases = repository_service.haxe_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/Helper.hx",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/Helper.hx" in aliases
    assert "src/demo/Helper" in aliases
    assert "src.demo.Helper" in aliases
    assert "demo.Helper" in aliases
    assert "Helper" in aliases
    assert "renderJson" in aliases
    assert "demo.renderJson" not in aliases
    assert "demo.Helper.renderJson" in aliases


def test_glsl_adapter_module_aliases_include_shader_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "glsl-alias-repo"
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "shaders" / "noise.glsl").write_text(
        "struct Params {\n"
        "  float gain;\n"
        "};\n"
        "\n"
        "float noise() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.glsl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="shaders/noise.glsl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "shaders/noise.glsl" in aliases
    assert "shaders/noise" in aliases
    assert "noise" in aliases
    assert "Params" in aliases


def test_hlsl_adapter_module_aliases_include_shader_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hlsl-alias-repo"
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "shaders" / "lighting.hlsli").write_text(
        "struct LightingParams {\n"
        "  float intensity;\n"
        "};\n"
        "\n"
        "float4 ShadeMain(float3 normal) : SV_Target {\n"
        "  return float4(normal, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.hlsl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="shaders/lighting.hlsli",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "shaders/lighting.hlsli" in aliases
    assert "shaders/lighting" in aliases
    assert "lighting" in aliases
    assert "LightingParams" in aliases
    assert "ShadeMain" in aliases


def test_hack_adapter_module_aliases_include_namespace_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hack-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Ref.php").write_text(
        "<?hh\n"
        "namespace Demo;\n"
        "\n"
        "final class Ref<T> {}\n",
        encoding="utf-8",
    )

    aliases = repository_service.hack_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Ref.php",
    )

    assert "src/Ref.php" in aliases
    assert "src/Ref" in aliases
    assert "src.Ref" in aliases
    assert "Ref" in aliases
    assert "Demo\\Ref" in aliases


def test_odin_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-alias-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    (repo_path / "src" / "common" / "helper.odin").write_text(
        "package common\n"
        "\n"
        "Config :: struct {\n"
        "    value: int,\n"
        "}\n"
        "\n"
        "helper :: proc() -> int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.odin_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/common/helper.odin",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/common/helper.odin" in aliases
    assert "src/common/helper" in aliases
    assert "helper" in aliases
    assert "src:common" in aliases
    assert "common" in aliases
    assert "common.Config" in aliases
    assert "common.helper" in aliases


def test_autohotkey_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autohotkey-alias-repo"
    (repo_path / "Lib").mkdir(parents=True)
    (repo_path / "Lib" / "Helper.ahk").write_text(
        "class Helper {\n"
        "    RenderJson(value) {\n"
        "        return value\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.autohotkey_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Lib/Helper.ahk",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Lib/Helper.ahk" in aliases
    assert "Lib/Helper" in aliases
    assert "Lib.Helper" in aliases
    assert "Helper" in aliases
    assert "RenderJson" in aliases
    assert "Helper.RenderJson" in aliases


def test_autoit_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autoit-alias-repo"
    (repo_path / "Includes").mkdir(parents=True)
    (repo_path / "Includes" / "Helper.au3").write_text(
        "Func RenderJson($value)\n"
        "    Return $value\n"
        "EndFunc\n",
        encoding="utf-8",
    )

    aliases = repository_service.autoit_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Includes/Helper.au3",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Includes/Helper.au3" in aliases
    assert "Includes/Helper" in aliases
    assert "Includes.Helper" in aliases
    assert "Helper" in aliases
    assert "RenderJson" in aliases
    assert "Helper.RenderJson" in aliases


def test_squirrel_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "squirrel-alias-repo"
    (repo_path / "scripts" / "vscripts").mkdir(parents=True)
    (repo_path / "scripts" / "vscripts" / "ppmod.nut").write_text(
        "::ppmod <- {\n"
        "  run = function () {\n"
        '    return "ok";\n'
        "  }\n"
        "};\n",
        encoding="utf-8",
    )

    aliases = repository_service.squirrel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/vscripts/ppmod.nut",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/vscripts/ppmod.nut" in aliases
    assert "scripts/vscripts/ppmod" in aliases
    assert "scripts.vscripts.ppmod" in aliases
    assert "ppmod" in aliases


