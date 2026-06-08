"""Tests for repository_intelligence_real_repo_probe: repository_language.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_repository_language_popularity_order_covers_broad_supported_surface() -> None:
    assert len(REPOSITORY_LANGUAGE_POPULARITY_ORDER) >= 50
    assert REPOSITORY_LANGUAGE_POPULARITY_ORDER[:14] == (
        "typescript",
        "python",
        "javascript",
        "vue",
        "svelte",
        "astro",
        "node",
        "java",
        "cs",
        "dotnet",
        "php",
        "hack",
        "shell",
        "fish",
    )
    assert "c" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "ada" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "assembly" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "cobol" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "scratch" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "pug" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "delphi" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "plsql" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "tsql" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "sas" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "ml" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vb6" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vba" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "abap" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "matlab" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "objectivec" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "prolog" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "lisp" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "scheme" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "racket" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "gdscript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "gml" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "foxpro" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "solidity" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vbscript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "applescript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "ladder" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "apex" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "labview" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "wolfram" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "rpg" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "actionscript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "awk" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "coffeescript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "autohotkey" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "cfml" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "elm" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "agda" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "idris" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "haxe" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "fish" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "emacslisp" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vimscript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "xpp" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "verilog" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "systemverilog" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vhdl" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "tcl" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vala" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "smalltalk" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "mql5" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "gams" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "openscad" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "purescript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "rescript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "roc" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "smarty" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "graphviz" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "mermaid" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "plantuml" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "openqasm" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "gleam" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "janet" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "raku" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "starlark" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "chapel" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "eiffel" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "dhall" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "rego" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "yara" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "nix" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "nushell" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "bitbake" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "jinja" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "liquid" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "handlebars" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vue" in REPOSITORY_LANGUAGE_POPULARITY_ORDER


