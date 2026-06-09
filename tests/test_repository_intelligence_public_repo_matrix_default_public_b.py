"""Tests for test_repository_intelligence_public_repo_matrix: default_public_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-3/tests/test_repository_intelligence_public_repo_matrix.py during modularization.
"""
from __future__ import annotations

from tests._test_repository_intelligence_public_repo_matrix_helpers import *  # noqa: F401,F403


def test_default_public_repository_cases_include_chapel() -> None:
    chapel_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "chapel"
    )

    assert chapel_case.repository_url == "https://github.com/chapel-lang/Crypto.git"
    assert chapel_case.expected_primary_ecosystem == "chapel"


def test_default_public_repository_cases_include_bicep() -> None:
    bicep_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "bicep"
    )

    assert (
        bicep_case.repository_url == "https://github.com/Azure/bicep-registry-modules.git"
    )
    assert bicep_case.expected_primary_ecosystem == "bicep"


def test_default_public_repository_cases_include_dhall() -> None:
    dhall_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "dhall"
    )

    assert dhall_case.repository_url == "https://github.com/regadas/github-actions-dhall.git"
    assert dhall_case.expected_primary_ecosystem == "dhall"


def test_default_public_repository_cases_include_bitbake() -> None:
    bitbake_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "bitbake"
    )

    assert (
        bitbake_case.repository_url
        == "https://github.com/openembedded/meta-openembedded.git"
    )
    assert bitbake_case.expected_primary_ecosystem == "bitbake"


def test_default_public_repository_cases_include_puppet() -> None:
    puppet_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "puppet"
    )

    assert puppet_case.repository_url == "https://github.com/puppetlabs/puppetlabs-apache.git"
    assert puppet_case.expected_primary_ecosystem == "puppet"


def test_default_public_repository_cases_include_openscad() -> None:
    openscad_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "openscad"
    )

    assert openscad_case.repository_url == "https://github.com/BelfrySCAD/BOSL2.git"
    assert openscad_case.expected_primary_ecosystem == "openscad"


def test_default_public_repository_cases_include_haxe() -> None:
    haxe_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "haxe"
    )

    assert haxe_case.repository_url == "https://github.com/HaxeFoundation/hscript.git"
    assert haxe_case.expected_primary_ecosystem == "haxe"


def test_default_public_repository_cases_include_agda() -> None:
    agda_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "agda"
    )

    assert agda_case.repository_url == "https://github.com/agda/agda-stdlib.git"
    assert agda_case.expected_primary_ecosystem == "agda"


def test_default_public_repository_cases_include_idris() -> None:
    idris_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "idris"
    )

    assert idris_case.repository_url == "https://github.com/stefan-hoeck/idris2-pack.git"
    assert idris_case.expected_primary_ecosystem == "idris"


def test_default_public_repository_cases_include_perl() -> None:
    perl_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "perl"
    )

    assert perl_case.repository_url == "https://github.com/dagolden/Path-Tiny.git"
    assert perl_case.expected_primary_ecosystem == "perl"


def test_default_public_repository_cases_include_raku() -> None:
    raku_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "raku"
    )

    assert raku_case.repository_url == "https://github.com/ugexe/zef.git"
    assert raku_case.expected_primary_ecosystem == "raku"


def test_default_public_repository_cases_include_purescript() -> None:
    purescript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "purescript"
    )

    assert (
        purescript_case.repository_url
        == "https://github.com/purescript/purescript-prelude.git"
    )
    assert purescript_case.expected_primary_ecosystem == "purescript"


def test_default_public_repository_cases_include_rescript() -> None:
    rescript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "rescript"
    )

    assert (
        rescript_case.repository_url
        == "https://github.com/glennsl/rescript-json-combinators.git"
    )
    assert rescript_case.expected_primary_ecosystem == "rescript"


def test_default_public_repository_cases_include_gleam() -> None:
    gleam_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "gleam"
    )

    assert gleam_case.repository_url == "https://github.com/gleam-lang/stdlib.git"
    assert gleam_case.expected_primary_ecosystem == "gleam"


def test_default_public_repository_cases_include_janet() -> None:
    janet_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "janet"
    )

    assert janet_case.repository_url == "https://github.com/janet-lang/jpm.git"
    assert janet_case.expected_primary_ecosystem == "janet"


def test_default_public_repository_cases_include_nushell() -> None:
    nushell_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "nushell"
    )

    assert nushell_case.repository_url == "https://github.com/nushell/nu_scripts.git"
    assert nushell_case.expected_primary_ecosystem == "nushell"


def test_default_public_repository_cases_include_fish() -> None:
    fish_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "fish"
    )

    assert fish_case.repository_url == "https://github.com/jorgebucaran/fisher.git"
    assert fish_case.expected_primary_ecosystem == "fish"


def test_default_public_repository_cases_include_applescript() -> None:
    applescript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "applescript"
    )

    assert applescript_case.repository_url == "https://github.com/unforswearing/applescript.git"
    assert applescript_case.expected_primary_ecosystem == "applescript"


def test_default_public_repository_cases_include_elm() -> None:
    elm_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "elm"
    )

    assert elm_case.repository_url == "https://github.com/elm/core.git"
    assert elm_case.expected_primary_ecosystem == "elm"


def test_default_public_repository_cases_include_emacslisp() -> None:
    emacslisp_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "emacslisp"
    )

    assert emacslisp_case.repository_url == "https://github.com/magnars/dash.el.git"
    assert emacslisp_case.expected_primary_ecosystem == "emacslisp"


def test_default_public_repository_cases_include_vimscript() -> None:
    vimscript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "vimscript"
    )

    assert vimscript_case.repository_url == "https://github.com/tpope/vim-fugitive.git"
    assert vimscript_case.expected_primary_ecosystem == "vimscript"


def test_default_public_repository_cases_include_vba() -> None:
    vba_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "vba"
    )

    assert vba_case.repository_url == "https://github.com/VBA-tools/VBA-JSON.git"
    assert vba_case.expected_primary_ecosystem == "vba"


def test_default_public_repository_cases_include_racket() -> None:
    racket_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "racket"
    )

    assert racket_case.repository_url == "https://github.com/mbutterick/pollen.git"
    assert racket_case.expected_primary_ecosystem == "racket"


def test_default_public_repository_cases_include_scheme() -> None:
    scheme_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "scheme"
    )

    assert scheme_case.repository_url == "https://github.com/ashinn/irregex.git"
    assert scheme_case.expected_primary_ecosystem == "scheme"


def test_default_public_repository_cases_include_cfml() -> None:
    cfml_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "cfml"
    )

    assert cfml_case.repository_url == "https://github.com/ghidinelli/cfpayment.git"
    assert cfml_case.expected_primary_ecosystem == "cfml"


def test_default_public_repository_cases_include_delphi() -> None:
    delphi_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "delphi"
    )

    assert delphi_case.repository_url == "https://github.com/VSoftTechnologies/DUnitX.git"
    assert delphi_case.expected_primary_ecosystem == "delphi"


def test_default_public_repository_cases_include_tsql() -> None:
    tsql_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "tsql"
    )

    assert (
        tsql_case.repository_url
        == "https://github.com/BrentOzarULTD/SQL-Server-First-Responder-Kit.git"
    )
    assert tsql_case.expected_primary_ecosystem == "tsql"


def test_default_public_repository_cases_include_xpp() -> None:
    xpp_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "xpp"
    )

    assert xpp_case.repository_url == "https://github.com/TrudAX/XppTools.git"
    assert xpp_case.expected_primary_ecosystem == "xpp"


def test_default_public_repository_cases_include_pascal() -> None:
    pascal_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "pascal"
    )

    assert (
        pascal_case.repository_url
        == "https://github.com/transmission-remote-gui/transgui.git"
    )
    assert pascal_case.expected_primary_ecosystem == "pascal"


def test_default_public_repository_cases_include_mojo() -> None:
    mojo_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "mojo"
    )

    assert (
        mojo_case.repository_url
        == "https://github.com/gabrieldemarmiesse/mojo-stdlib-extensions.git"
    )
    assert mojo_case.expected_primary_ecosystem == "mojo"


