"""Tests for repository_intelligence_service: resolve.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_resolve_suffix_match_preserves_sorted_first_match_for_nested_suffixes() -> None:
    module_index = {
        "alpha": "packages/alpha/src/FSharpPlus/Control/Functor.fs",
        "beta": "packages/beta/src/FSharpPlus/Control/Functor.fs",
    }

    resolved = repository_service._resolve_suffix_match(
        module_index=module_index,
        suffixes=("src/FSharpPlus/Control/Functor.fs", "Functor.fs"),
    )

    assert resolved == "packages/alpha/src/FSharpPlus/Control/Functor.fs"


def test_resolve_directory_prefix_match_finds_nested_directory_suffixes() -> None:
    module_index = {
        "alpha": "packages/alpha/src/FSharpPlus/Control/Functor.fs",
        "beta": "packages/beta/src/Other/Control/Functor.fs",
    }

    resolved = repository_service._resolve_directory_prefix_match(
        module_index=module_index,
        prefixes=("src/FSharpPlus/Control",),
    )

    assert resolved == "packages/alpha/src/FSharpPlus/Control/Functor.fs"


def test_resolve_c_family_include_uses_keyword_only_suffix_match_helper() -> None:
    module_index = {"include/widget.hpp": "include/widget.hpp"}

    resolved = repository_service._resolve_c_family_include(
        current_file="src/main.cpp",
        import_target="widget.hpp",
        module_index=module_index,
    )

    assert resolved == "include/widget.hpp"


def test_resolve_ruby_import_uses_keyword_only_suffix_match_helper() -> None:
    module_index = {"src/acme/widget.rb": "src/acme/widget.rb"}

    resolved = repository_service._resolve_ruby_import(
        current_file="app/main.rb",
        import_target="acme/widget",
        is_relative=False,
        module_index=module_index,
    )

    assert resolved == "src/acme/widget.rb"


