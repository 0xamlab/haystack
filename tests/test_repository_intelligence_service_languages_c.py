"""Tests for repository_intelligence_service: languages_c.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    cuda as repository_cuda_adapter,
    cuda_primitives as repository_cuda_primitives,
    ladder as repository_ladder_adapter,
)
from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_cython_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cython-alias-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "helpers.pyx").write_text(
        "cpdef int render_json():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    aliases = repository_service.cython_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/acme/helpers.pyx",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acme/helpers.pyx" in aliases
    assert "src/acme/helpers" in aliases
    assert "acme.helpers" in aliases
    assert "helpers" in aliases
    assert "render_json" in aliases
    assert "acme.helpers.render_json" in aliases


def test_cython_adapter_module_aliases_can_skip_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cython-alias-repo-no-symbols"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "helpers.pyx").write_text(
        "cpdef int render_json():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    aliases = repository_service.cython_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/acme/helpers.pyx",
        stable_identifier=repository_service._stable_identifier,
        include_symbol_aliases=False,
    )

    assert "src/acme/helpers.pyx" in aliases
    assert "src/acme/helpers" in aliases
    assert "acme.helpers" in aliases
    assert "helpers" in aliases
    assert "render_json" not in aliases
    assert "acme.helpers.render_json" not in aliases


def test_cuda_adapter_module_aliases_include_file_and_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "cuda-alias-repo"
    (repo_path / "src" / "kernels").mkdir(parents=True)
    (repo_path / "src" / "kernels" / "vector_add.cuh").write_text(
        "__device__ inline int add_one(int x) {\n"
        "  return x + 1;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.cuda_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/kernels/vector_add.cuh",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/kernels/vector_add.cuh" in aliases
    assert "src/kernels/vector_add" in aliases
    assert "vector_add" in aliases


def test_cuda_adapter_module_aliases_can_use_preloaded_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cuda-alias-preloaded-text-repo"
    (repo_path / "src" / "kernels").mkdir(parents=True)
    source_text = (
        "__device__ inline int add_one(int x) {\n"
        "  return x + 1;\n"
        "}\n"
    )
    (repo_path / "src" / "kernels" / "vector_add.cuh").write_text(
        source_text,
        encoding="utf-8",
    )

    def _fail_read_text(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("module_aliases_for_path should reuse preloaded CUDA text")

    monkeypatch.setattr(Path, "read_text", _fail_read_text)

    aliases = repository_service.cuda_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/kernels/vector_add.cuh",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
    )

    assert "src/kernels/vector_add.cuh" in aliases
    assert "vector_add" in aliases


def test_cuda_adapter_module_aliases_strip_comments_once_for_symbol_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cuda-alias-strip-comments-once-repo"
    (repo_path / "src" / "kernels").mkdir(parents=True)
    source_text = (
        "__device__ inline int add_one(int x) {\n"
        "  return x + 1;\n"
        "}\n"
    )
    (repo_path / "src" / "kernels" / "vector_add.cuh").write_text(
        source_text,
        encoding="utf-8",
    )
    observed_texts: list[str] = []
    original_strip_comments = repository_cuda_primitives.strip_comments

    def _recording_strip_comments(text: str) -> str:
        observed_texts.append(text)
        return original_strip_comments(text)

    monkeypatch.setattr(repository_cuda_primitives, "strip_comments", _recording_strip_comments)

    aliases = repository_service.cuda_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/kernels/vector_add.cuh",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
    )

    assert "add_one" in aliases
    assert observed_texts == [source_text]


def test_stan_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "stan-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "helpers.stan").write_text(
        "functions {\n"
        "  real render_json(real x) {\n"
        "    return x;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.stan_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/helpers.stan",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "models/helpers.stan" in aliases
    assert "models/helpers" in aliases
    assert "helpers" in aliases
    assert "render_json" in aliases
    assert "helpers.render_json" in aliases


def test_robotframework_adapter_module_aliases_include_suite_test_and_keyword_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "robotframework-alias-repo"
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "login.robot").write_text(
        "*** Test Cases ***\n"
        "Valid Login\n"
        "    Open Login Page\n"
        "\n"
        "*** Keywords ***\n"
        "Open Login Page\n"
        "    Log    opened\n",
        encoding="utf-8",
    )

    aliases = repository_service.robotframework_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="tests/login.robot",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "tests/login.robot" in aliases
    assert "tests/login" in aliases
    assert "tests.login" in aliases
    assert "login" in aliases
    assert "Valid Login" in aliases
    assert "Open Login Page" in aliases
    assert "tests.login.Open Login Page" in aliases


def test_dockerfile_adapter_module_aliases_include_stage_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "dockerfile-alias-repo"
    (repo_path / "docker").mkdir(parents=True)
    (repo_path / "docker" / "Dockerfile").write_text(
        "FROM python:3.12-slim AS base\n"
        "RUN echo preparing\n"
        "FROM base AS runtime\n"
        'CMD ["python", "--version"]\n',
        encoding="utf-8",
    )

    aliases = repository_service.dockerfile_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="docker/Dockerfile",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "docker/Dockerfile" in aliases
    assert "Dockerfile" in aliases
    assert "docker" in aliases
    assert "docker.Dockerfile" in aliases
    assert "base" in aliases
    assert "runtime" in aliases
    assert "docker.Dockerfile.base" in aliases


def test_scss_adapter_module_aliases_include_module_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "scss-alias-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "_mixins.scss").write_text(
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n"
        "@function helper-fn() {\n"
        "  @return 1;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.scss_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="styles/_mixins.scss",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "styles/_mixins.scss" in aliases
    assert "styles/mixins" in aliases
    assert "styles.mixins" in aliases
    assert "_mixins" in aliases
    assert "mixins" in aliases
    assert "button-base" in aliases
    assert "helper-fn" in aliases
    assert "styles.mixins.button-base" in aliases


def test_scss_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "scss-inline-text-repo"
    (repo_path / "styles").mkdir(parents=True)
    source_text = (
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n"
        "@function helper-fn() {\n"
        "  @return 1;\n"
        "}\n"
    )
    file_path = repo_path / "styles" / "_mixins.scss"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.scss_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="styles/_mixins.scss",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_scss_primitives.strip_comments(source_text),
    )

    assert "styles/_mixins.scss" in aliases
    assert "styles/mixins" in aliases
    assert "button-base" in aliases
    assert "helper-fn" in aliases


def test_scss_adapter_module_aliases_can_skip_symbol_aliases(tmp_path: Path) -> None:
    repo_path = tmp_path / "scss-module-only-alias-repo"
    (repo_path / "styles").mkdir(parents=True)
    source_text = (
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n"
        "@function helper-fn() {\n"
        "  @return 1;\n"
        "}\n"
    )
    (repo_path / "styles" / "_mixins.scss").write_text(source_text, encoding="utf-8")

    aliases = repository_service.scss_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="styles/_mixins.scss",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_scss_primitives.strip_comments(source_text),
        include_symbol_aliases=False,
    )

    assert "styles/_mixins.scss" in aliases
    assert "styles/mixins" in aliases
    assert "button-base" not in aliases
    assert "helper-fn" not in aliases


def test_scss_strip_comments_reuse_cached_results() -> None:
    repository_scss_primitives._strip_comments_cached.cache_clear()
    source_text = (
        "@mixin button-base {\n"
        "  // comment\n"
        "  color: $brand;\n"
        "}\n"
    )

    first_result = repository_scss_primitives.strip_comments(source_text)
    first_cache_info = repository_scss_primitives._strip_comments_cached.cache_info()
    second_result = repository_scss_primitives.strip_comments(source_text)
    second_cache_info = repository_scss_primitives._strip_comments_cached.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_typst_adapter_module_aliases_include_module_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "typst-alias-repo"
    (repo_path / "docs" / "lib").mkdir(parents=True)
    (repo_path / "docs" / "lib" / "utils.typ").write_text(
        "#let add(x, y) = x + y\n"
        "#let scale(x) = x * 2\n",
        encoding="utf-8",
    )

    aliases = repository_service.typst_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="docs/lib/utils.typ",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "docs/lib/utils.typ" in aliases
    assert "docs/lib/utils" in aliases
    assert "docs.lib.utils" in aliases
    assert "lib.utils" in aliases
    assert "utils" in aliases
    assert "add" in aliases
    assert "scale" in aliases
    assert "lib.utils.add" in aliases


def test_starlark_adapter_module_aliases_include_load_labels_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "starlark-alias-repo"
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "rules" / "demo.bzl").write_text(
        "def render_json(name):\n"
        "    return name\n"
        "\n"
        "helper_value = 1\n",
        encoding="utf-8",
    )

    aliases = repository_service.starlark_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rules/demo.bzl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rules/demo.bzl" in aliases
    assert "rules/demo" in aliases
    assert "rules.demo" in aliases
    assert "//rules:demo.bzl" in aliases
    assert "render_json" in aliases
    assert "helper_value" in aliases
    assert "rules.demo.render_json" in aliases


def test_starlark_adapter_resolves_shorthand_load_labels() -> None:
    module_index = {
        "BUILD.bazel": "BUILD.bazel",
        "rules/demo.bzl": "rules/demo.bzl",
        "lib/common.bzl": "lib/common.bzl",
    }

    assert repository_service.starlark_adapter.resolve_load_target(
        current_file="BUILD.bazel",
        import_target="rules:demo.bzl",
        module_index=module_index,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    ) == "rules/demo.bzl"
    assert repository_service.starlark_adapter.resolve_load_target(
        current_file="rules/demo.bzl",
        import_target=":common.bzl",
        module_index={
            **module_index,
            "rules/common.bzl": "rules/common.bzl",
        },
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    ) == "rules/common.bzl"


def test_v_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "v-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.v").write_text(
        "module demo.app\n"
        "\n"
        "pub struct Helper {}\n"
        "\n"
        "pub fn render_json() string {\n"
        "    return '{}'\n"
        "}\n"
        "\n"
        "fn (helper Helper) boot() {\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.v_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.v",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/main.v" in aliases
    assert "src/main" in aliases
    assert "src.main" in aliases
    assert "main" in aliases
    assert "demo.app" in aliases
    assert "Helper" in aliases
    assert "render_json" in aliases
    assert "boot" in aliases
    assert "demo.app.render_json" in aliases
    assert "main.boot" in aliases


def test_smalltalk_adapter_module_aliases_include_package_class_and_selector_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "smalltalk-alias-repo"
    (repo_path / "src" / "Demo-Core").mkdir(parents=True)
    (repo_path / "src" / "Demo-Core" / "Helper.class.st").write_text(
        "Class {\n"
        "\t#name : 'Helper',\n"
        "\t#superclass : 'Object',\n"
        "\t#category : 'Demo-Core',\n"
        "\t#package : 'Demo-Core'\n"
        "}\n"
        "\n"
        "{ #category : 'rendering' }\n"
        "Helper class >> renderJson [\n"
        "\t^ '{}'\n"
        "]\n",
        encoding="utf-8",
    )

    aliases = repository_service.smalltalk_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Demo-Core/Helper.class.st",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Demo-Core/Helper.class.st" in aliases
    assert "src/Demo-Core/Helper.class" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases
    assert "Demo-Core" in aliases
    assert "Demo-Core.Helper" in aliases
    assert "renderJson" in aliases
    assert "Helper.renderJson" in aliases


def test_elm_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "elm-alias-repo"
    (repo_path / "src" / "Page").mkdir(parents=True)
    (repo_path / "src" / "Page" / "Home.elm").write_text(
        "module Page.Home exposing (Model, Msg, init, update)\n\n"
        "type alias Model =\n"
        "    { count : Int }\n\n"
        "type Msg\n"
        "    = Increment\n\n"
        "init : Model\n"
        "init =\n"
        "    { count = 0 }\n\n"
        "update : Msg -> Model -> Model\n"
        "update msg model =\n"
        "    model\n",
        encoding="utf-8",
    )

    aliases = repository_service.elm_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Page/Home.elm",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Page/Home.elm" in aliases
    assert "src/Page/Home" in aliases
    assert "src.Page.Home" in aliases
    assert "Home" in aliases
    assert "Page.Home" in aliases
    assert "Model" in aliases
    assert "Msg" in aliases
    assert "init" in aliases
    assert "update" in aliases
    assert "Page.Home.init" in aliases
    assert "Page.Home.update" in aliases


def test_elm_adapter_module_aliases_accept_preloaded_text_without_file_read(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "elm-preloaded-text-repo"
    (repo_path / "src" / "Page").mkdir(parents=True)
    target_path = repo_path / "src" / "Page" / "Home.elm"
    target_path.write_text(
        "module Page.Home exposing (Model, init)\n\n"
        "type alias Model =\n"
        "    { count : Int }\n\n"
        "init : Model\n"
        "init =\n"
        "    { count = 0 }\n",
        encoding="utf-8",
    )
    text = target_path.read_text(encoding="utf-8")
    target_path.unlink()

    aliases = repository_service.elm_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Page/Home.elm",
        stable_identifier=repository_service._stable_identifier,
        text=text,
    )

    assert "Page.Home" in aliases
    assert "init" in aliases
    assert "Page.Home.init" in aliases


def test_elm_adapter_module_aliases_can_skip_symbol_aliases(tmp_path: Path) -> None:
    repo_path = tmp_path / "elm-module-only-alias-repo"
    (repo_path / "src" / "Page").mkdir(parents=True)
    source_text = (
        "module Page.Home exposing (Model, init)\n\n"
        "type alias Model =\n"
        "    { count : Int }\n\n"
        "init : Model\n"
        "init =\n"
        "    { count = 0 }\n"
    )
    (repo_path / "src" / "Page" / "Home.elm").write_text(
        source_text,
        encoding="utf-8",
    )

    aliases = repository_service.elm_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Page/Home.elm",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        include_symbol_aliases=False,
    )

    assert "src/Page/Home.elm" in aliases
    assert "src/Page/Home" in aliases
    assert "src.Page.Home" in aliases
    assert "Home" in aliases
    assert "Page.Home" in aliases
    assert "Model" not in aliases
    assert "init" not in aliases
    assert "Page.Home.init" not in aliases


def test_elm_adapter_parse_file_scopes_references_to_enclosing_symbol(tmp_path: Path) -> None:
    repo_path = tmp_path / "elm-parse-repo"
    (repo_path / "src" / "Html").mkdir(parents=True)
    (repo_path / "src" / "Html" / "Helpers.elm").write_text(
        "module Html.Helpers exposing (text)\n\n"
        "text : String -> String\n"
        "text value =\n"
        "    value\n",
        encoding="utf-8",
    )
    source_path = repo_path / "src" / "Page.elm"
    source_path.write_text(
        "module Page exposing (helper, view)\n\n"
        "import Html.Helpers exposing (text)\n\n"
        "helper : String -> String\n"
        "helper value =\n"
        "    text value\n\n"
        "view : String -> String\n"
        "view value =\n"
        "    helper value\n"
        "        ++ helper value\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/Html/Helpers.elm", "src/Page.elm"],
        root_path=repo_path,
    )
    text = source_path.read_text(encoding="utf-8")

    symbols, dependencies, references = repository_service.elm_adapter.parse_file(
        "src/Page.elm",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    helper_symbol = next(symbol for symbol in symbols if symbol.symbol_name == "helper")
    view_symbol = next(symbol for symbol in symbols if symbol.symbol_name == "view")
    module_symbol = next(symbol for symbol in symbols if symbol.symbol_kind == "module")

    assert any(
        dependency.target_file == "src/Html/Helpers.elm" and dependency.target_symbol == "Helpers"
        for dependency in dependencies
    )
    assert any(
        reference.source_symbol_id == helper_symbol.symbol_id
        and reference.target_file == "src/Html/Helpers.elm"
        and reference.target_names == ("text",)
        for reference in references
    )
    assert any(
        reference.source_symbol_id == view_symbol.symbol_id
        and reference.target_symbol_id == helper_symbol.symbol_id
        and reference.target_names == ("helper",)
        for reference in references
    )
    assert (
        sum(
            1
            for reference in references
            if reference.source_symbol_id == view_symbol.symbol_id
            and reference.target_symbol_id == helper_symbol.symbol_id
            and reference.target_names == ("helper",)
        )
        == 1
    )
    assert not any(
        reference.source_symbol_id == helper_symbol.symbol_id
        and reference.target_symbol_id == helper_symbol.symbol_id
        for reference in references
    )
    assert not any(
        reference.source_symbol_id == module_symbol.symbol_id
        and (
            reference.target_file == "src/Html/Helpers.elm"
            or reference.target_symbol_id == helper_symbol.symbol_id
        )
        for reference in references
    )


def test_elm_adapter_parse_file_supports_mixed_local_and_imported_targets_per_symbol(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "elm-mixed-target-repo"
    (repo_path / "src" / "Html").mkdir(parents=True)
    (repo_path / "src" / "Html" / "Helpers.elm").write_text(
        "module Html.Helpers exposing (text)\n\n"
        "text : String -> String\n"
        "text value =\n"
        "    value\n",
        encoding="utf-8",
    )
    source_path = repo_path / "src" / "Page.elm"
    source_path.write_text(
        "module Page exposing (helper, view)\n\n"
        "import Html.Helpers exposing (text)\n\n"
        "helper : String -> String\n"
        "helper value =\n"
        "    text value\n\n"
        "view : String -> String\n"
        "view value =\n"
        "    helper (text value)\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/Html/Helpers.elm", "src/Page.elm"],
        root_path=repo_path,
    )
    symbols, _dependencies, references = repository_service.elm_adapter.parse_file(
        "src/Page.elm",
        source_path.read_text(encoding="utf-8"),
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    view_symbol = next(symbol for symbol in symbols if symbol.symbol_name == "view")

    assert any(
        reference.source_symbol_id == view_symbol.symbol_id
        and reference.target_file == "src/Html/Helpers.elm"
        and reference.target_names == ("text",)
        for reference in references
    )
    assert any(
        reference.source_symbol_id == view_symbol.symbol_id
        and reference.target_names == ("helper",)
        for reference in references
    )


def test_emacslisp_adapter_module_aliases_include_feature_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "emacslisp-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.el").write_text(
        "(provide 'main)\n"
        "(defun run () 1)\n",
        encoding="utf-8",
    )

    aliases = repository_service.emacslisp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="main.el",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "main.el" in aliases
    assert "main" in aliases
    assert "run" in aliases
    assert "main.run" in aliases


def test_emacslisp_module_aliases_reuse_cached_comment_stripping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "emacslisp-strip-cache-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.el").write_text(
        ";;; main.el --- demo -*- lexical-binding: t; -*-\n"
        "(provide 'main)\n"
        "(defun run ()\n"
        "  ;; comment\n"
        "  1)\n",
        encoding="utf-8",
    )

    repository_lisp_support.clear_strip_comments_cache()
    original = repository_lisp_support._strip_comments_uncached
    uncached_call_count = 0

    def _counting_strip_comments_uncached(source_text: str) -> str:
        nonlocal uncached_call_count
        uncached_call_count += 1
        return original(source_text)

    monkeypatch.setattr(
        repository_lisp_support,
        "_strip_comments_uncached",
        _counting_strip_comments_uncached,
    )

    aliases = repository_service.emacslisp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="main.el",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "main.run" in aliases
    assert uncached_call_count == 1


def test_vimscript_adapter_module_aliases_include_autoload_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vimscript-alias-repo"
    (repo_path / "autoload").mkdir(parents=True)
    (repo_path / "autoload" / "fugitive.vim").write_text(
        "function! fugitive#run()\n"
        "  return '{}'\n"
        "endfunction\n"
        "let g:fugitive_loaded = 1\n",
        encoding="utf-8",
    )

    aliases = repository_service.vimscript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="autoload/fugitive.vim",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "autoload/fugitive.vim" in aliases
    assert "autoload/fugitive" in aliases
    assert "autoload.fugitive" in aliases
    assert "fugitive" in aliases
    assert "fugitive#run" in aliases
    assert "g:fugitive_loaded" in aliases
    assert "fugitive.fugitive#run" in aliases


def test_vimscript_symbol_reference_and_source_line_numbers_are_stable() -> None:
    text = (
        "source autoload/fugitive.vim\n"
        "\n"
        "function! fugitive#run()\n"
        "  return '{}'\n"
        "endfunction\n"
        "let g:fugitive_loaded = 1\n"
        "call fugitive#run()\n"
    )

    assert repository_service.vimscript_adapter.iter_source_statements(text) == (
        ("autoload/fugitive.vim", 1),
    )
    assert repository_service.vimscript_adapter.iter_symbol_entries(text) == (
        ("fugitive#run", "function", 3),
        ("g:fugitive_loaded", "value", 6),
    )
    assert repository_service.vimscript_adapter.iter_reference_names(text) == (
        ("fugitive#run", 3),
        ("fugitive#run", 7),
    )


def test_racket_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "racket-alias-repo"
    (repo_path / "private").mkdir(parents=True)
    (repo_path / "main.rkt").write_text(
        "#lang racket\n"
        '(require "private/helper.rkt")\n'
        "(define (run) (helper))\n",
        encoding="utf-8",
    )

    aliases = repository_service.racket_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="main.rkt",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "main.rkt" in aliases
    assert "main" in aliases
    assert "run" in aliases
    assert "main.run" in aliases


def test_xpp_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "xpp-alias-repo"
    (repo_path / "PackagesLocalDirectory" / "Acme" / "Acme" / "AxClass").mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
        / "AcmeMain.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>AcmeMain</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class AcmeMain\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "    <Methods>\n"
        "      <Method>\n"
        "        <Name>boot</Name>\n"
        "        <Source><![CDATA[\n"
        "public static void boot()\n"
        "{\n"
        "}\n"
        "]]></Source>\n"
        "      </Method>\n"
        "    </Methods>\n"
        "  </SourceCode>\n"
        "</AxClass>\n",
        encoding="utf-8",
    )

    aliases = repository_service.xpp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml" in aliases
    assert "PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain" in aliases
    assert "AcmeMain" in aliases
    assert "boot" in aliases
    assert "AcmeMain.boot" in aliases
    assert "AcmeMain::boot" in aliases


def test_xpp_adapter_module_aliases_accept_preloaded_text_without_file_read(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "xpp-preloaded-text-repo"
    source_path = (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
        / "AcmeMain.xml"
    )
    source_path.parent.mkdir(parents=True)
    source_text = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>AcmeMain</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class AcmeMain\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "    <Methods>\n"
        "      <Method>\n"
        "        <Name>boot</Name>\n"
        "        <Source><![CDATA[\n"
        "public static void boot()\n"
        "{\n"
        "}\n"
        "]]></Source>\n"
        "      </Method>\n"
        "    </Methods>\n"
        "  </SourceCode>\n"
        "</AxClass>\n"
    )
    source_path.write_text(source_text, encoding="utf-8")

    aliases = repository_service.xpp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
    )

    assert "AcmeMain::boot" in aliases
    source_path.unlink()
    aliases_without_disk_read = repository_service.xpp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
    )
    assert aliases_without_disk_read == aliases


def test_xpp_adapter_parse_file_reuses_cached_strip_comments() -> None:
    repository_xpp_primitives.clear_strip_comments_cache()
    text = (
        "class AcmeMain // class comment\n"
        "{\n"
        "    /* block comment */\n"
        "    public static void boot()\n"
        "    {\n"
        "        Worker worker = new Worker();\n"
        "        worker.run();\n"
        "        AcmeHelper::start();\n"
        "        #include AcmeShared\n"
        "    }\n"
        "}\n"
    )
    original_strip_comments = repository_xpp_primitives._strip_comments_uncached
    call_count = 0

    def _counting_strip_comments(source: str) -> str:
        nonlocal call_count
        call_count += 1
        return original_strip_comments(source)

    repository_xpp_primitives._strip_comments_uncached = _counting_strip_comments
    try:
        symbols, dependencies, references = repository_service.xpp_adapter.parse_file(
            "src/AcmeMain.xpp",
            text,
            {
                "Worker": "src/Worker.xpp",
                "AcmeHelper": "src/AcmeHelper.xpp",
                "AcmeShared": "src/AcmeShared.xpp",
            },
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        )
    finally:
        repository_xpp_primitives._strip_comments_uncached = original_strip_comments

    assert symbols
    assert dependencies
    assert references
    assert call_count == 3


def test_scratch_adapter_module_aliases_include_project_target_and_procedure_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scratch-alias-repo"
    _write_scratch_project(
        repo_path / "games" / "Maze.sb3",
        _scratch_project_payload(),
    )

    aliases = repository_service.scratch_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="games/Maze.sb3",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "games/Maze.sb3" in aliases
    assert "Maze" in aliases
    assert "games/Maze" in aliases
    assert "games.Maze" in aliases
    assert "project:Maze" in aliases
    assert "Stage" in aliases
    assert "Cat" in aliases
    assert "init" in aliases
    assert "procedure:init" in aliases
    assert "start" in aliases
    assert "broadcast:start" in aliases


def test_vhdl_adapter_module_aliases_include_entity_package_and_routine_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vhdl-alias-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "top.vhd").write_text(
        "package util_pkg is\n"
        "  function helper return integer;\n"
        "end package;\n"
        "entity top is\n"
        "end entity;\n"
        "architecture rtl of top is\n"
        "begin\n"
        "end architecture;\n",
        encoding="utf-8",
    )

    aliases = repository_service.vhdl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rtl/top.vhd",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rtl/top.vhd" in aliases
    assert "rtl/top" in aliases
    assert "rtl.top" in aliases
    assert "top" in aliases
    assert "entity:top" in aliases
    assert "util_pkg" in aliases
    assert "package:util_pkg" in aliases
    assert "helper" in aliases
    assert "util_pkg.helper" in aliases


def test_gdscript_adapter_module_aliases_include_class_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gdscript-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "player.gd").write_text(
        "class_name Player\n"
        "extends Node\n"
        "signal jumped\n"
        "func ready_up() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )

    aliases = repository_service.gdscript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/player.gd",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/player.gd" in aliases
    assert "src/player" in aliases
    assert "src.player" in aliases
    assert "res://src/player.gd" in aliases
    assert "Player" in aliases
    assert "class:Player" in aliases
    assert "ready_up" in aliases
    assert "Player.ready_up" in aliases


def test_gml_adapter_module_aliases_include_script_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gml-alias-repo"
    (repo_path / "scripts" / "Input").mkdir(parents=True)
    (repo_path / "scripts" / "Input" / "Input.gml").write_text(
        "#macro INPUT_OK 1\n"
        "enum InputState { Idle, Active }\n"
        "function InputService() constructor {\n"
        "}\n"
        "helper = function() {\n"
        "    return INPUT_OK;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.gml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/Input/Input.gml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/Input/Input.gml" in aliases
    assert "scripts/Input/Input" in aliases
    assert "scripts.Input.Input" in aliases
    assert "Input" in aliases
    assert "script:Input" in aliases
    assert "INPUT_OK" in aliases
    assert "macro:INPUT_OK" in aliases
    assert "InputState" in aliases
    assert "enum:InputState" in aliases
    assert "InputService" in aliases
    assert "helper" in aliases
    assert "Input.helper" in aliases


def test_ladder_adapter_module_aliases_include_program_and_routine_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ladder-alias-repo"
    (repo_path / "logic").mkdir(parents=True)
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
        '          <Routine Name="ChildRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="1"><Text><![CDATA[XIC(StartPB)OTE(RunMotor);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )

    aliases = repository_service.ladder_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="logic/Main.L5X",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "logic/Main.L5X" in aliases
    assert "logic/Main" in aliases
    assert "logic.Main" in aliases
    assert "Main" in aliases
    assert "PlantController" in aliases
    assert "MainProgram" in aliases
    assert "MainRoutine" in aliases
    assert "ChildRoutine" in aliases
    assert "MainProgram.MainRoutine" in aliases


def test_ladder_adapter_module_aliases_do_not_require_full_symbol_collection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ladder-alias-fastpath-repo"
    (repo_path / "logic").mkdir(parents=True)
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

    def _fail_collect_symbol_entries(*args: Any, **kwargs: Any) -> tuple[Any, ...]:
        raise AssertionError("module_aliases_for_path should use the alias fast path")

    monkeypatch.setattr(
        repository_ladder_adapter,
        "collect_symbol_entries",
        _fail_collect_symbol_entries,
    )

    aliases = repository_service.ladder_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="logic/Main.L5X",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "PlantController" in aliases
    assert "MainProgram" in aliases
    assert "MainRoutine" in aliases
    assert "MainProgram.MainRoutine" in aliases


def test_ladder_adapter_module_aliases_can_use_preloaded_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ladder-alias-preloaded-text-repo"
    (repo_path / "logic").mkdir(parents=True)
    source_text = (
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
        "</RSLogix5000Content>\n"
    )
    (repo_path / "logic" / "Main.L5X").write_text(source_text, encoding="utf-8")

    def _fail_read_text(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("module_aliases_for_path should reuse preloaded ladder text")

    monkeypatch.setattr(Path, "read_text", _fail_read_text)

    aliases = repository_service.ladder_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="logic/Main.L5X",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
    )

    assert "PlantController" in aliases
    assert "MainProgram" in aliases
    assert "MainRoutine" in aliases


def test_ladder_adapter_distinguishes_operational_entrypoints_from_datatype_exports() -> None:
    program_text = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        '<RSLogix5000Content TargetType="Program">\n'
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="MainProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="MainRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[XIC(StartPB)OTE(RunMotor);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n"
    )
    datatype_text = (
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
        "</RSLogix5000Content>\n"
    )

    assert repository_service.ladder_adapter.is_probable_ladder_source(
        path=Path("logic/Main.L5X"),
        text=program_text,
    )
    assert repository_service.ladder_adapter.is_probable_operational_entrypoint(
        path=Path("logic/Main.L5X"),
        text=program_text,
    )
    assert repository_service._language_for_path(
        Path("logic/Types.L5X"),
        text=datatype_text,
    ) == "ladder"
    assert not repository_service.ladder_adapter.is_probable_operational_entrypoint(
        path=Path("logic/Types.L5X"),
        text=datatype_text,
    )


def test_ladder_operational_entrypoint_uses_root_target_type_fast_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        '<RSLogix5000Content TargetType="Program">\n'
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="MainProgram">\n'
        "        <Tags>\n"
        + "".join(
            f'          <Tag Name="Signal{index}" DataType="BOOL"/>\n'
            for index in range(500)
        )
        + "        </Tags>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n"
    )

    def _fail_strip_xml_comments(text: str) -> str:
        raise AssertionError("target-type fast path should avoid full ladder normalization")

    monkeypatch.setattr(
        repository_ladder_adapter,
        "_strip_xml_comments",
        _fail_strip_xml_comments,
    )

    assert repository_service.ladder_adapter.is_probable_operational_entrypoint(
        path=Path("logic/Main.L5X"),
        text=source_text,
    )


def test_ladder_non_operational_target_type_uses_root_target_type_fast_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        '<RSLogix5000Content TargetType="DataType">\n'
        '  <Controller Name="PlantController">\n'
        "    <DataTypes>\n"
        '      <DataType Name="MotorStatus">\n'
        "        <Members>\n"
        + "".join(
            f'          <Member Name="Signal{index}" DataType="BOOL"/>\n'
            for index in range(500)
        )
        + "        </Members>\n"
        "      </DataType>\n"
        "    </DataTypes>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n"
    )

    def _fail_strip_xml_comments(text: str) -> str:
        raise AssertionError("target-type fast path should avoid full ladder normalization")

    monkeypatch.setattr(
        repository_ladder_adapter,
        "_strip_xml_comments",
        _fail_strip_xml_comments,
    )

    assert not repository_service.ladder_adapter.is_probable_operational_entrypoint(
        path=Path("logic/Types.L5X"),
        text=source_text,
    )


def test_ladder_strip_xml_comments_reuses_cached_result() -> None:
    source_text = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!-- comment -->\n"
        "<RSLogix5000Content></RSLogix5000Content>\n"
    )
    repository_ladder_adapter._strip_xml_comments_cached.cache_clear()

    first_result = repository_ladder_adapter._strip_xml_comments(source_text)
    first_cache_info = repository_ladder_adapter._strip_xml_comments_cached.cache_info()
    second_result = repository_ladder_adapter._strip_xml_comments(source_text)
    second_cache_info = repository_ladder_adapter._strip_xml_comments_cached.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_ladder_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_xml_comments = repository_ladder_adapter._strip_xml_comments
    strip_call_count = {"value": 0}

    def counting_strip_xml_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_xml_comments(text)

    monkeypatch.setattr(
        repository_ladder_adapter,
        "_strip_xml_comments",
        counting_strip_xml_comments,
    )

    source_text = (
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
        '          <Routine Name="ChildRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="1"><Text><![CDATA[XIC(StartPB)OTE(RunMotor);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n"
    )
    module_index = {"ChildRoutine": "logic/Main.L5X"}

    repository_service.ladder_adapter.parse_dependencies_only(
        "logic/Main.L5X",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
    )
    repository_service.ladder_adapter.parse_file(
        "logic/Main.L5X",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
    )

    assert strip_call_count["value"] == 2


def test_labview_adapter_module_aliases_include_project_artifact_paths(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "labview-alias-repo"
    (repo_path / "Source" / "Libraries").mkdir(parents=True)
    (repo_path / "Source" / "Libraries" / "Helpers.lvlib").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        '<Library Name="Helpers">\n'
        '  <Item Name="Helper" Type="VI" URL="Helper.vi" />\n'
        "</Library>\n",
        encoding="utf-8",
    )

    aliases = repository_service.labview_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Source/Libraries/Helpers.lvlib",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Source/Libraries/Helpers.lvlib" in aliases
    assert "Source/Libraries/Helpers" in aliases
    assert "Source.Libraries.Helpers" in aliases
    assert "Helpers" in aliases


def test_tcl_adapter_module_aliases_include_package_namespace_and_proc_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tcl-alias-repo"
    (repo_path / "modules" / "sha1").mkdir(parents=True)
    (repo_path / "modules" / "sha1" / "sha1.tcl").write_text(
        "package provide sha1 2.0.5\n"
        "namespace eval ::sha1 {\n"
        "    namespace export SHA1Init\n"
        "}\n"
        "proc ::sha1::SHA1Init {} {\n"
        "    return ok\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.tcl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/sha1/sha1.tcl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "modules/sha1/sha1.tcl" in aliases
    assert "modules/sha1/sha1" in aliases
    assert "modules.sha1.sha1" in aliases
    assert "sha1" in aliases
    assert "package:sha1" in aliases
    assert "namespace:sha1" in aliases
    assert "proc:sha1::SHA1Init" in aliases
    assert "SHA1Init" in aliases


def test_language_for_path_detects_suffixless_tcl_script_from_shebang_and_markers() -> None:
    text = (
        "#!/usr/bin/env tclsh\n"
        "namespace eval ::sha1 {\n"
        "    proc init {} { return ok }\n"
        "}\n"
    )

    assert repository_service._language_for_path(
        Path("apps/dtplite"),
        text=text,
    ) == "tcl"


def test_language_for_path_detects_suffixless_shell_script_from_shebang() -> None:
    text = "#!/bin/sh\nset -eu\nprintf 'ok\\n'\n"

    assert repository_service._language_for_path(
        Path("config/install-sh"),
        text=text,
    ) == "shell"


def test_vbscript_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "vbscript-alias-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "helper.vbs").write_text(
        "Class Helper\n"
        "End Class\n"
        "Function Encrypt(value)\n"
        "    Encrypt = value\n"
        "End Function\n",
        encoding="utf-8",
    )

    aliases = repository_service.vbscript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/helper.vbs",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/helper.vbs" in aliases
    assert "scripts/helper" in aliases
    assert "scripts.helper" in aliases
    assert "helper" in aliases
    assert "Helper" in aliases
    assert "Encrypt" in aliases
