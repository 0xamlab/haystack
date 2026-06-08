"""Tests for repository_intelligence_service: languages_f.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_cython_adapter_parse_file_resolves_imports_includes_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cython-parse-repo"
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
    module_index = repository_service._build_module_index(
        ["pkg/main.pyx", "pkg/helpermod.pxd", "pkg/defs.pxi"],
        root_path=repo_path,
    )
    text = (repo_path / "pkg" / "main.pyx").read_text(encoding="utf-8")

    dependencies = repository_service.cython_adapter.parse_dependencies_only(
        "pkg/main.pyx",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.cython_adapter.parse_file(
        "pkg/main.pyx",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "pkg/defs.pxi" for dependency in dependencies)
    assert any(
        dependency.target_file == "pkg/helpermod.pxd" and dependency.target_symbol == "helper"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "pkg/helpermod.pxd" and reference.target_names == ("helper",)
        for reference in references
    )


def test_cuda_adapter_parse_file_resolves_include_and_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "cuda-parse-repo"
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
    module_index = repository_service._build_module_index(
        ["src/main.cu", "src/kernels/math.cuh"],
        root_path=repo_path,
    )
    text = (repo_path / "src" / "main.cu").read_text(encoding="utf-8")

    dependencies = repository_service.cuda_adapter.parse_dependencies_only(
        "src/main.cu",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_include=repository_service._resolve_c_family_include,
    )
    symbols, _, references = repository_service.cuda_adapter.parse_file(
        "src/main.cu",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_include=repository_service._resolve_c_family_include,
    )

    assert any(dependency.target_file == "src/kernels/math.cuh" for dependency in dependencies)
    assert any(symbol.symbol_name == "kernel_run" for symbol in symbols)
    assert any(
        reference.target_file == "src/kernels/math.cuh" and reference.target_names == ("add_one",)
        for reference in references
    )


def test_stan_adapter_parse_file_resolves_include_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "stan-parse-repo"
    (repo_path / "models" / "lib").mkdir(parents=True)
    (repo_path / "models" / "lib" / "math.stan").write_text(
        "functions {\n"
        "  real add_one(real x) {\n"
        "    return x + 1;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "main.stan").write_text(
        '#include "lib/math.stan"\n'
        "\n"
        "functions {\n"
        "  real run(real x) {\n"
        "    return add_one(x);\n"
        "  }\n"
        "}\n"
        "\n"
        "data {\n"
        "  real x;\n"
        "}\n"
        "model {\n"
        "  target += run(x);\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["models/main.stan", "models/lib/math.stan"],
        root_path=repo_path,
    )
    text = (repo_path / "models" / "main.stan").read_text(encoding="utf-8")

    dependencies = repository_service.stan_adapter.parse_dependencies_only(
        "models/main.stan",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.stan_adapter.parse_file(
        "models/main.stan",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "models/lib/math.stan" for dependency in dependencies)
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "models/lib/math.stan" and reference.target_names == ("add_one",)
        for reference in references
    )


def test_robotframework_adapter_parse_file_resolves_resource_dependencies_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "robotframework-parse-repo"
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
    module_index = repository_service._build_module_index(
        ["tests/login.robot", "resources/common.resource"],
        root_path=repo_path,
    )
    text = (repo_path / "tests" / "login.robot").read_text(encoding="utf-8")

    dependencies = repository_service.robotframework_adapter.parse_dependencies_only(
        "tests/login.robot",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.robotframework_adapter.parse_file(
        "tests/login.robot",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "resources/common.resource"
        and dependency.target_symbol == "common"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "tests/login" for symbol in symbols)
    assert any(symbol.symbol_name == "Valid Login" for symbol in symbols)
    assert any(
        reference.target_file == "resources/common.resource"
        and "Open Login Page" in reference.target_names
        for reference in references
    )


def test_dockerfile_adapter_parse_file_resolves_local_copy_run_and_stage_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dockerfile-parse-repo"
    (repo_path / "docker").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "bootstrap.sh").write_text(
        "#!/usr/bin/env sh\n"
        "echo bootstrap\n",
        encoding="utf-8",
    )
    (repo_path / "docker" / "Dockerfile").write_text(
        "FROM python:3.12-slim AS base\n"
        "COPY ../scripts/bootstrap.sh /usr/local/bin/bootstrap.sh\n"
        "RUN sh ../scripts/bootstrap.sh\n"
        "FROM base AS runtime\n"
        "COPY --from=base /usr/local/bin/bootstrap.sh /usr/local/bin/bootstrap.sh\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["docker/Dockerfile", "scripts/bootstrap.sh"],
        root_path=repo_path,
    )
    text = (repo_path / "docker" / "Dockerfile").read_text(encoding="utf-8")

    dependencies = repository_service.dockerfile_adapter.parse_dependencies_only(
        "docker/Dockerfile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.dockerfile_adapter.parse_file(
        "docker/Dockerfile",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "scripts/bootstrap.sh"
        and dependency.dependency_type in {"copies", "executes"}
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "docker/Dockerfile"
        and dependency.target_symbol == "base"
        and dependency.dependency_type in {"builds_from", "copies_from"}
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "docker/Dockerfile" for symbol in symbols)
    assert any(symbol.symbol_name == "base" for symbol in symbols)
    assert any(symbol.symbol_name == "runtime" for symbol in symbols)
    assert any(
        reference.target_file == "docker/Dockerfile" and reference.target_names == ("base",)
        for reference in references
    )


def test_scss_adapter_parse_file_resolves_imports_and_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "scss-parse-repo"
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
    module_index = repository_service._build_module_index(
        ["styles/main.scss", "styles/_mixins.scss", "styles/_functions.scss"],
        root_path=repo_path,
    )
    text = (repo_path / "styles" / "main.scss").read_text(encoding="utf-8")

    dependencies = repository_service.scss_adapter.parse_dependencies_only(
        "styles/main.scss",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.scss_adapter.parse_file(
        "styles/main.scss",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "styles/_mixins.scss"
        and dependency.dependency_type == "uses"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "styles/_functions.scss"
        and dependency.dependency_type == "imports"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "styles/main" for symbol in symbols)
    assert any(symbol.symbol_name == "button-base" for symbol in symbols) is False
    assert any(
        reference.target_file == "styles/_mixins.scss"
        and "button-base" in reference.target_names
        for reference in references
    )
    assert any(
        reference.target_file == "styles/_functions.scss"
        and "helper-fn" in reference.target_names
        for reference in references
    )


def test_typst_adapter_parse_file_resolves_imports_includes_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "typst-parse-repo"
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
    module_index = repository_service._build_module_index(
        ["src/main.typ", "src/lib/math.typ", "src/partials/common.typ"],
        root_path=repo_path,
    )
    text = (repo_path / "src" / "main.typ").read_text(encoding="utf-8")

    dependencies = repository_service.typst_adapter.parse_dependencies_only(
        "src/main.typ",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.typst_adapter.parse_file(
        "src/main.typ",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/lib/math.typ"
        and dependency.dependency_type == "imports"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "src/partials/common.typ"
        and dependency.dependency_type == "includes"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "main" for symbol in symbols)
    assert any(symbol.symbol_name == "render" for symbol in symbols)
    assert any(
        reference.target_file == "src/lib/math.typ" and "add" in reference.target_names
        for reference in references
    )
    assert any(
        reference.target_file == "src/lib/math.typ" and "scale" in reference.target_names
        for reference in references
    )


def test_shaderlab_adapter_module_aliases_include_shader_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shaderlab-alias-repo"
    (repo_path / "Shaders").mkdir(parents=True)
    (repo_path / "Shaders" / "Main.shader").write_text(
        'Shader "Demo/Main" {\n'
        "SubShader {\n"
        "Pass {\n"
        "CGPROGRAM\n"
        "float4 frag() : SV_Target {\n"
        "  return float4(0.0, 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDCG\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.shaderlab_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Shaders/Main.shader",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Shaders/Main.shader" in aliases
    assert "Shaders/Main" in aliases
    assert "Main" in aliases
    assert "Demo/Main" in aliases
    assert "frag" in aliases


def test_shaderlab_adapter_parse_file_resolves_include_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shaderlab-parse-repo"
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
    module_index = repository_service._build_module_index(
        ["Shaders/Main.shader", "Shaders/Includes/Common.cginc"],
        root_path=repo_path,
    )
    text = (repo_path / "Shaders" / "Main.shader").read_text(encoding="utf-8")

    dependencies = repository_service.shaderlab_adapter.parse_dependencies_only(
        "Shaders/Main.shader",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.shaderlab_adapter.parse_file(
        "Shaders/Main.shader",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "Shaders/Includes/Common.cginc" for dependency in dependencies)
    assert any(symbol.symbol_name == "Demo/Main" for symbol in symbols)
    assert any(symbol.symbol_name == "frag" for symbol in symbols)
    assert any(
        reference.target_file == "Shaders/Includes/Common.cginc"
        and reference.target_names == ("NoiseValue",)
        for reference in references
    )


def test_bitbake_adapter_parse_file_resolves_include_and_inherit_dependencies(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bitbake-parse-repo"
    (repo_path / "conf").mkdir(parents=True)
    (repo_path / "classes").mkdir(parents=True)
    (repo_path / "recipes-core" / "base").mkdir(parents=True)
    (repo_path / "recipes-core" / "images").mkdir(parents=True)
    (repo_path / "conf" / "layer.conf").write_text(
        'BBPATH .= ":${LAYERDIR}"\n'
        'BBFILES += "${LAYERDIR}/recipes-*/*/*.bb"\n',
        encoding="utf-8",
    )
    (repo_path / "classes" / "image.bbclass").write_text(
        "python do_rootfs() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "recipes-core" / "base" / "base.inc").write_text(
        'BASE_NAME = "base"\n',
        encoding="utf-8",
    )
    (repo_path / "recipes-core" / "images" / "core-image-minimal.bb").write_text(
        "require ../base/base.inc\n"
        "inherit image\n"
        'BASE_NAME = "core"\n'
        "python do_install() {\n"
        "    bb.plain(\"${BASE_NAME}\")\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        (
            "conf/layer.conf",
            "classes/image.bbclass",
            "recipes-core/base/base.inc",
            "recipes-core/images/core-image-minimal.bb",
        ),
        root_path=repo_path,
    )
    text = (repo_path / "recipes-core" / "images" / "core-image-minimal.bb").read_text(
        encoding="utf-8"
    )
    dependencies = repository_service.bitbake_adapter.parse_dependencies_only(
        "recipes-core/images/core-image-minimal.bb",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.bitbake_adapter.parse_file(
        "recipes-core/images/core-image-minimal.bb",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "recipes-core/base/base.inc"
        and dependency.dependency_type == "require"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "classes/image.bbclass"
        and dependency.dependency_type == "inherit"
        for dependency in dependencies
    )
    base_symbol = next(symbol for symbol in symbols if symbol.symbol_name == "BASE_NAME")
    assert any(symbol.symbol_name == "do_install" for symbol in symbols)
    assert any(reference.target_symbol_id == base_symbol.symbol_id for reference in references)


def test_luau_adapter_module_aliases_include_wally_and_modules(tmp_path: Path) -> None:
    repo_path = tmp_path / "luau-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "wally.toml").write_text(
        "[package]\nname = 'ukendio/jecs'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "jecs.luau").write_text("--!strict\nreturn {}\n", encoding="utf-8")
    (repo_path / "modules" / "entity_visualiser.luau").write_text(
        "--!strict\nreturn {}\n",
        encoding="utf-8",
    )

    package_aliases = repository_service.luau_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/jecs.luau",
    )
    module_aliases = repository_service.luau_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/entity_visualiser.luau",
    )

    assert "@jecs" in package_aliases
    assert "src/jecs" in package_aliases
    assert "@modules/entity_visualiser" in module_aliases


