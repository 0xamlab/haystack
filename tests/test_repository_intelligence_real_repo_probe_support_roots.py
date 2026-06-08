"""Tests for repository_intelligence_real_repo_probe: support_roots.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_support_roots_need_expansion_returns_false_when_all_roots_are_covered() -> None:
    assert (
        _support_roots_need_expansion(
            candidate_file_paths=[
                "ujson/src/ujson/AstTransformer.scala",
                "ujson/circe/src/ujson/circe/CirceJson.scala",
                "ujson/play/src/ujson/play/PlayJson.scala",
                "upack/src/upack/Msg.scala",
            ],
            support_roots=[
                "ujson/src/ujson",
                "ujson/circe/src/ujson",
                "ujson/play/src/ujson",
                "upack/src/upack",
            ],
        )
        is False
    )


def test_support_roots_need_expansion_returns_true_when_any_root_is_uncovered() -> None:
    assert (
        _support_roots_need_expansion(
            candidate_file_paths=[
                "pkgs/http/lib/http.dart",
                "pkgs/http/lib/src/client.dart",
            ],
            support_roots=[
                "pkgs/http/lib",
                "pkgs/http_parser/lib",
            ],
        )
        is True
    )


def test_support_roots_requiring_expansion_ignores_auxiliary_bin_roots() -> None:
    assert (
        _support_roots_requiring_expansion(
            candidate_file_paths=[
                "pkg/lib/main.rb",
                "pkg/lib/core.rb",
            ],
            support_roots=[
                "pkg/lib",
                "pkg/bin",
            ],
        )
        == []
    )


def test_support_roots_requiring_expansion_returns_only_uncovered_roots() -> None:
    assert _support_roots_requiring_expansion(
        candidate_file_paths=[
            "pkgs/http/lib/http.dart",
            "pkgs/http/lib/src/client.dart",
        ],
        support_roots=[
            "pkgs/http/lib",
            "pkgs/http_parser/lib",
            "pkgs/http_profile/lib",
        ],
    ) == [
        "pkgs/http_parser/lib",
        "pkgs/http_profile/lib",
    ]


