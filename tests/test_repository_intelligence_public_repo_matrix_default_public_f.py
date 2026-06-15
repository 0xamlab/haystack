"""Tests for test_repository_intelligence_public_repo_matrix: default_public_f."""
from __future__ import annotations

from tests._test_repository_intelligence_public_repo_matrix_helpers import *  # noqa: F401,F403


def test_default_public_repository_cases_include_plpgsql() -> None:
    plpgsql_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "plpgsql"
    )

    assert plpgsql_case.repository_url == "https://github.com/pgmq/pgmq.git"
    assert plpgsql_case.expected_primary_ecosystem == "plpgsql"
    assert plpgsql_case.focus_paths == ("pgmq-extension/sql",)


def test_default_public_repository_cases_include_xtend() -> None:
    xtend_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "xtend"
    )

    assert xtend_case.repository_url == "https://github.com/tobykurien/Xtendroid.git"
    assert xtend_case.expected_primary_ecosystem == "xtend"
    assert xtend_case.focus_paths == ("Xtendroid/src",)


def test_default_public_repository_cases_include_ocamllex() -> None:
    ocamllex_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "ocamllex"
    )

    assert ocamllex_case.repository_url == "https://github.com/let-def/ocamllex-refill.git"
    assert ocamllex_case.expected_primary_ecosystem == "ocamllex"
    assert ocamllex_case.focus_paths == ("lexer.mll",)


def test_default_public_repository_cases_include_ocamlyacc() -> None:
    ocamlyacc_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "ocamlyacc"
    )

    assert ocamlyacc_case.repository_url == "https://github.com/amblafont/sedlex-menhir.git"
    assert ocamlyacc_case.expected_primary_ecosystem == "ocamlyacc"
    assert ocamlyacc_case.focus_paths == ("ocamllex-ocamlyacc/parser.mly",)


def test_default_public_repository_cases_include_moonscript() -> None:
    moonscript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "moonscript"
    )

    assert moonscript_case.repository_url == "https://github.com/leafo/moonscript.git"
    assert moonscript_case.expected_primary_ecosystem == "moonscript"
    assert moonscript_case.focus_paths == ("moon", "moonscript", "bin")
