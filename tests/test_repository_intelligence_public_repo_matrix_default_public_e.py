"""Tests for test_repository_intelligence_public_repo_matrix: default_public_e."""
from __future__ import annotations

from tests._test_repository_intelligence_public_repo_matrix_helpers import *  # noqa: F401,F403


def test_default_public_repository_cases_include_graphql() -> None:
    graphql_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "graphql"
    )

    assert graphql_case.repository_url == "https://github.com/graphql/swapi-graphql.git"
    assert graphql_case.expected_primary_ecosystem == "graphql"
    assert graphql_case.focus_paths == ("doc/example_queries",)


def test_default_public_repository_cases_include_pkl() -> None:
    pkl_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "pkl"
    )

    assert pkl_case.repository_url == "https://github.com/apple/pkl.git"
    assert pkl_case.expected_primary_ecosystem == "pkl"
    assert pkl_case.focus_paths == ("pkl-core/src/test/files/LanguageSnippetTests/input",)


def test_default_public_repository_cases_include_codeql() -> None:
    codeql_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "codeql"
    )

    assert codeql_case.repository_url == "https://github.com/github/codeql.git"
    assert codeql_case.expected_primary_ecosystem == "codeql"
    assert codeql_case.focus_paths == ("python/ql/src",)


def test_default_public_repository_cases_include_brightscript() -> None:
    brightscript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "brightscript"
    )

    assert brightscript_case.repository_url == "https://github.com/rokudev/scenegraph-master-sample.git"
    assert brightscript_case.expected_primary_ecosystem == "brightscript"
    assert brightscript_case.focus_paths == ("DeepLinking",)


def test_default_public_repository_cases_include_gnuplot() -> None:
    gnuplot_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "gnuplot"
    )

    assert gnuplot_case.repository_url == "https://github.com/gnuplot/gnuplot.git"
    assert gnuplot_case.expected_primary_ecosystem == "gnuplot"
    assert gnuplot_case.focus_paths == ("demo",)


def test_default_public_repository_cases_include_dataweave() -> None:
    dataweave_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "dataweave"
    )

    assert dataweave_case.repository_url == "https://github.com/mulesoft/docs-dataweave.git"
    assert dataweave_case.expected_primary_ecosystem == "dataweave"
    assert dataweave_case.focus_paths == ("modules/ROOT/pages/_partials/cookbook-dw",)


def test_default_public_repository_cases_include_common_workflow_language() -> None:
    cwl_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "common workflow language"
    )

    assert cwl_case.repository_url == "https://github.com/common-workflow-language/user_guide.git"
    assert cwl_case.expected_primary_ecosystem == "common workflow language"
    assert cwl_case.focus_paths == ("src/_includes/cwl",)


def test_default_public_repository_cases_include_earthly() -> None:
    earthly_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "earthly"
    )

    assert earthly_case.repository_url == "https://github.com/earthly/earthly.git"
    assert earthly_case.expected_primary_ecosystem == "earthly"
    assert earthly_case.focus_paths == ("tests/import",)


def test_default_public_repository_cases_include_webassembly() -> None:
    webassembly_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "webassembly"
    )

    assert webassembly_case.repository_url == "https://github.com/WebAssembly/spec.git"
    assert webassembly_case.expected_primary_ecosystem == "webassembly"
    assert webassembly_case.focus_paths == ("test/core",)
