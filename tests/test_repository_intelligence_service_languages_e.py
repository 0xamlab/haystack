"""Tests for repository_intelligence_service: languages_e.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_eiffel_adapter_parse_file_resolves_inherited_class_dependencies(tmp_path: Path) -> None:
    repo_path = tmp_path / "eiffel-parse-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.e").write_text(
        "class HELPER\n"
        "feature\n"
        "    assist\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )
    application_path = repo_path / "src" / "application.e"
    application_path.write_text(
        "class APPLICATION\n"
        "inherit\n"
        "    HELPER\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        local\n"
        "            helper: HELPER\n"
        "        do\n"
        "            create {HELPER} helper\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/helper.e", "src/application.e"],
        root_path=repo_path,
    )
    text = application_path.read_text(encoding="utf-8")
    dependencies = repository_service.eiffel_adapter.parse_dependencies_only(
        "src/application.e",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.eiffel_adapter.parse_file(
        "src/application.e",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/helper.e" and dependency.target_symbol == "HELPER"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "APPLICATION" for symbol in symbols)
    assert any(
        reference.target_file == "src/helper.e" and "HELPER" in reference.target_names
        for reference in references
    )


def test_coq_adapter_parse_file_resolves_require_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coq-parse-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper : nat := 0.\n",
        encoding="utf-8",
    )
    main_path = repo_path / "theories" / "Main.v"
    main_path.write_text(
        "Require Import Helper.\n"
        "Lemma run : nat.\n"
        "Proof.\n"
        "  exact helper.\n"
        "Qed.\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["theories/Helper.v", "theories/Main.v"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.coq_adapter.parse_dependencies_only(
        "theories/Main.v",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.coq_adapter.parse_file(
        "theories/Main.v",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "theories/Helper.v" and dependency.target_symbol == "Helper"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "theories/Helper.v" and "helper" in reference.target_names
        for reference in references
    )


def test_lean_adapter_parse_file_resolves_import_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lean-parse-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    (repo_path / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 0\n",
        encoding="utf-8",
    )
    main_path = repo_path / "Batteries" / "Main.lean"
    main_path.write_text(
        "import Batteries.Helper\n\n"
        "def run : Nat := Batteries.Helper.helper\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["Batteries/Helper.lean", "Batteries/Main.lean"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.lean_adapter.parse_dependencies_only(
        "Batteries/Main.lean",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.lean_adapter.parse_file(
        "Batteries/Main.lean",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "Batteries/Helper.lean"
        and dependency.target_symbol == "Helper"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "Batteries/Helper.lean" and "helper" in reference.target_names
        for reference in references
    )


def test_lean_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_service.lean_adapter.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_service.lean_adapter,
        "strip_comments",
        counting_strip_comments,
    )

    source_text = (
        "import Batteries.Helper\n\n"
        "def helper : Nat := 0\n"
        "def run : Nat := Batteries.Helper.helper\n"
    )
    module_index = {"Batteries.Helper": "Batteries/Helper.lean"}

    repository_service.lean_adapter.parse_dependencies_only(
        "Batteries/Main.lean",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.lean_adapter.parse_file(
        "Batteries/Main.lean",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_glsl_adapter_parse_file_resolves_include_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "glsl-parse-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "lib" / "noise.glsl").write_text(
        "float noise() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    main_path = repo_path / "src" / "main.frag"
    main_path.write_text(
        '#version 300 es\n'
        '#include "./lib/noise.glsl"\n'
        "float render() {\n"
        "  return noise();\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/lib/noise.glsl", "src/main.frag"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.glsl_adapter.parse_dependencies_only(
        "src/main.frag",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.glsl_adapter.parse_file(
        "src/main.frag",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/lib/noise.glsl" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "render" for symbol in symbols)
    assert any(reference.target_names == ("noise",) for reference in references)


def test_hlsl_adapter_parse_file_resolves_include_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hlsl-parse-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "lib" / "noise.hlsli").write_text(
        "float NoiseValue() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    main_path = repo_path / "src" / "main.hlsl"
    main_path.write_text(
        '#include "./lib/noise.hlsli"\n'
        "float4 RenderMain() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/lib/noise.hlsli", "src/main.hlsl"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.hlsl_adapter.parse_dependencies_only(
        "src/main.hlsl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.hlsl_adapter.parse_file(
        "src/main.hlsl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/lib/noise.hlsli" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "RenderMain" for symbol in symbols)
    assert any(reference.target_names == ("NoiseValue",) for reference in references)


def test_hlsl_adapter_iter_symbol_entries_preserve_line_numbers_after_block_comments() -> None:
    entries = repository_service.hlsl_adapter.iter_symbol_entries(
        "/* shader prelude\n"
        "   keep line offsets stable */\n"
        "struct LightingParams {\n"
        "  float intensity;\n"
        "};\n"
        "\n"
        "float4 ShadeMain(float3 normal) : SV_Target {\n"
        "  return float4(normal, 1.0);\n"
        "}\n"
    )

    assert ("LightingParams", "struct", 3) in entries
    assert ("ShadeMain", "function", 7) in entries


def test_batchfile_adapter_parse_file_resolves_call_dependencies_and_label_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "batchfile-parse-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "scripts" / "build.bat").write_text(
        "@echo off\n"
        "call ..\\tools\\helper.cmd\n"
        "goto :done\n"
        ":done\n"
        "exit /b 0\n",
        encoding="utf-8",
    )
    (repo_path / "tools" / "helper.cmd").write_text(
        "@echo off\n"
        ":helper\n"
        "echo helper\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["scripts/build.bat", "tools/helper.cmd"],
        root_path=repo_path,
    )
    text = (repo_path / "scripts" / "build.bat").read_text(encoding="utf-8")
    dependencies = repository_service.batchfile_adapter.parse_dependencies_only(
        "scripts/build.bat",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.batchfile_adapter.parse_file(
        "scripts/build.bat",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "tools/helper.cmd" and dependency.target_symbol == "helper"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "scripts/build" for symbol in symbols)
    assert any(symbol.symbol_name == "done" for symbol in symbols)
    assert any(
        reference.target_file == "tools/helper.cmd" and reference.target_names == ("helper",)
        for reference in references
    )
    assert any(
        reference.target_file == "scripts/build.bat" and reference.target_names == ("done",)
        for reference in references
    )


def test_makefile_adapter_parse_file_resolves_includes_and_target_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "makefile-parse-repo"
    (repo_path / "mk").mkdir(parents=True)
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

    module_index = repository_service._build_module_index(
        ["Makefile", "mk/common.mk"],
        root_path=repo_path,
    )
    text = (repo_path / "Makefile").read_text(encoding="utf-8")
    dependencies = repository_service.makefile_adapter.parse_dependencies_only(
        "Makefile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.makefile_adapter.parse_file(
        "Makefile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "mk/common.mk" and dependency.target_symbol == "common"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "build" for symbol in symbols)
    assert any(symbol.symbol_name == "clean" for symbol in symbols)
    assert any(
        reference.target_file == "Makefile" and reference.target_names == ("clean",)
        for reference in references
    )
    assert any(reference.target_names == ("helper",) for reference in references)


def test_cmake_adapter_parse_file_resolves_includes_subdirectories_and_target_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cmake-parse-repo"
    (repo_path / "cmake" / "modules").mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text(
        "project(acme)\n"
        "include(cmake/tooling.cmake)\n"
        "add_subdirectory(cmake/modules)\n"
        "find_package(Threads REQUIRED)\n"
        "add_library(acme_core INTERFACE)\n"
        "target_link_libraries(acme_core PRIVATE helper)\n"
        "add_dependencies(acme_core codegen)\n",
        encoding="utf-8",
    )
    (repo_path / "cmake" / "tooling.cmake").write_text(
        "add_library(helper INTERFACE)\n",
        encoding="utf-8",
    )
    (repo_path / "cmake" / "modules" / "CMakeLists.txt").write_text(
        "add_custom_target(codegen)\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "CMakeLists.txt",
            "cmake/tooling.cmake",
            "cmake/modules/CMakeLists.txt",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "CMakeLists.txt").read_text(encoding="utf-8")
    dependencies = repository_service.cmake_adapter.parse_dependencies_only(
        "CMakeLists.txt",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.cmake_adapter.parse_file(
        "CMakeLists.txt",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "cmake/tooling.cmake" and dependency.target_symbol == "tooling"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "cmake/modules/CMakeLists.txt"
        and dependency.target_symbol == "modules"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file is None and dependency.target_symbol == "Threads"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "acme" for symbol in symbols)
    assert any(symbol.symbol_name == "acme_core" for symbol in symbols)
    assert any(
        reference.target_file == "cmake/tooling.cmake" and reference.target_names == ("helper",)
        for reference in references
    )
    assert any(
        reference.target_file == "cmake/modules/CMakeLists.txt"
        and reference.target_names == ("codegen",)
        for reference in references
    )


def test_meson_adapter_parse_file_resolves_subdir_imports_and_target_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "meson-parse-repo"
    (repo_path / "subprojects").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('acme', 'c')\n"
        "subdir('src')\n"
        "python_mod = import('python')\n"
        "zlib_dep = dependency('zlib')\n"
        "library('acme_core', 'src/core.c')\n"
        "executable('acme_cli', 'src/main.c', link_with: helper_lib, dependencies: [zlib_dep, dependency('threads')])\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "meson.build").write_text(
        "helper_lib = static_library('helper_lib', 'helper.c')\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "meson.build",
            "src/meson.build",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "meson.build").read_text(encoding="utf-8")
    dependencies = repository_service.meson_adapter.parse_dependencies_only(
        "meson.build",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.meson_adapter.parse_file(
        "meson.build",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/meson.build" and dependency.target_symbol == "src"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file is None and dependency.target_symbol == "python"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file is None and dependency.target_symbol == "zlib"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "acme" for symbol in symbols)
    assert any(symbol.symbol_name == "acme_core" for symbol in symbols)
    assert any(symbol.symbol_name == "acme_cli" for symbol in symbols)
    assert any(
        reference.target_file == "src/meson.build" and reference.target_names == ("helper_lib",)
        for reference in references
    )
    assert any(reference.target_names == ("zlib_dep",) for reference in references)
    assert any(reference.target_names == ("threads",) for reference in references)


def test_just_adapter_parse_file_resolves_module_dependencies_and_target_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "just-parse-repo"
    (repo_path / "tasks").mkdir(parents=True)
    (repo_path / "Justfile").write_text(
        "mod release 'tasks/release.just'\n"
        "alias ci := check\n"
        "default: check\n"
        "check: release::publish\n"
        "  just build\n"
        "build:\n"
        "  echo build\n",
        encoding="utf-8",
    )
    (repo_path / "tasks" / "release.just").write_text(
        "publish:\n"
        "  echo publish\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "Justfile",
            "tasks/release.just",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "Justfile").read_text(encoding="utf-8")
    dependencies = repository_service.just_adapter.parse_dependencies_only(
        "Justfile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.just_adapter.parse_file(
        "Justfile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "tasks/release.just" and dependency.target_symbol == "release"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "ci" for symbol in symbols)
    assert any(symbol.symbol_name == "check" for symbol in symbols)
    assert any(symbol.symbol_name == "build" for symbol in symbols)
    assert any(
        reference.target_file == "tasks/release.just"
        and reference.target_names == ("release::publish", "publish")
        for reference in references
    )
    assert any(
        reference.target_file == "Justfile" and reference.target_names == ("build",)
        for reference in references
    )
    assert any(
        reference.target_file == "Justfile" and reference.target_names == ("check",)
        for reference in references
    )


def test_qmake_adapter_parse_file_resolves_include_subdir_dependencies_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qmake-parse-repo"
    (repo_path / "libs").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "project.pro").write_text(
        "TEMPLATE = subdirs\n"
        "TARGET = acme_workspace\n"
        "SUBDIRS += libs app\n"
        "libs.file = libs/libs.pro\n"
        "app.file = app/app.pro\n"
        "app.depends = libs\n"
        "include(common.pri)\n",
        encoding="utf-8",
    )
    (repo_path / "common.pri").write_text("CONFIG += ordered\n", encoding="utf-8")
    (repo_path / "libs" / "libs.pro").write_text(
        "TARGET = libs\nSOURCES += helper.cpp\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "app.pro").write_text(
        "TARGET = app\nSOURCES += main.cpp\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "project.pro",
            "common.pri",
            "libs/libs.pro",
            "app/app.pro",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "project.pro").read_text(encoding="utf-8")
    dependencies = repository_service.qmake_adapter.parse_dependencies_only(
        "project.pro",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.qmake_adapter.parse_file(
        "project.pro",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "common.pri" and dependency.target_symbol == "common"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "libs/libs.pro" and dependency.target_symbol == "libs"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "app/app.pro" and dependency.target_symbol == "app"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "acme_workspace" for symbol in symbols)
    assert any(symbol.symbol_name == "libs" for symbol in symbols)
    assert any(symbol.symbol_name == "app" for symbol in symbols)
    assert any(
        reference.target_file == "project.pro" and reference.target_names == ("libs",)
        for reference in references
    )


def test_qmake_parse_file_does_not_reinvoke_parse_dependencies_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qmake-parse-file-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "project.pro").write_text(
        "TEMPLATE = subdirs\n"
        "TARGET = workspace\n"
        "SUBDIRS += app\n",
        encoding="utf-8",
    )

    def _fail_parse_dependencies_only(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], ...]:
        raise AssertionError("qmake parse_file should build dependencies without a second dependency pass")

    monkeypatch.setattr(
        repository_qmake_analysis_support,
        "parse_dependencies_only",
        _fail_parse_dependencies_only,
    )

    symbols, dependencies, reference_candidates = repository_service.qmake_adapter.parse_file(
        "project.pro",
        (repo_path / "project.pro").read_text(encoding="utf-8"),
        {
            "project.pro": "project.pro",
            "app/app.pro": "app/app.pro",
        },
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert symbols
    assert isinstance(dependencies, tuple)
    assert isinstance(reference_candidates, tuple)


def test_qml_adapter_parse_file_resolves_imports_qmldir_exports_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qml-parse-repo"
    (repo_path / "components").mkdir(parents=True)
    (repo_path / "qmldir").write_text(
        "module Demo.Controls\n"
        "Button 1.0 components/Button.qml\n",
        encoding="utf-8",
    )
    (repo_path / "components" / "Button.qml").write_text(
        "Rectangle {\n"
        "    id: helperButton\n"
        "    function press() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Main.qml").write_text(
        'import "." as Demo\n'
        "Rectangle {\n"
        "    id: rootItem\n"
        "    function activate() {\n"
        "        helperButton.press()\n"
        "    }\n"
        "    Demo.Button {\n"
        "        id: helperButton\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "qmldir",
            "Main.qml",
            "components/Button.qml",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "Main.qml").read_text(encoding="utf-8")
    dependencies = repository_service.qml_adapter.parse_dependencies_only(
        "Main.qml",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.qml_adapter.parse_file(
        "Main.qml",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "qmldir" and dependency.target_symbol == "Demo"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "Main" for symbol in symbols)
    assert any(symbol.symbol_name == "rootItem" for symbol in symbols)
    assert any(symbol.symbol_name == "activate" for symbol in symbols)
    assert any(
        reference.target_file == "components/Button.qml"
        and reference.target_names == ("Demo.Button", "Button")
        for reference in references
    )
    assert any(
        reference.target_file == "Main.qml" and reference.target_names == ("helperButton",)
        for reference in references
    )


def test_qml_strip_comments_preserves_strings_and_removes_hash_comment_lines() -> None:
    source_text = (
        "import QtQuick 2.0\n"
        "# directive comment\n"
        "Item {\n"
        "    property string url: \"http://example.com//keep\"\n"
        "    // inline comment\n"
        "    Text { text: '// keep' }\n"
        "    /* block comment */\n"
        "}\n"
    )

    stripped_text = repository_qml_primitives.strip_comments(source_text)

    assert stripped_text == (
        "import QtQuick 2.0\n"
        "\n"
        "Item {\n"
        "    property string url: \"http://example.com//keep\"\n"
        "    \n"
        "    Text { text: '// keep' }\n"
        "    \n"
        "}"
    )
