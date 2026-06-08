"""Tests for repository_intelligence_real_repo_probe: non_operational.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_non_operational_profile_path_ignores_common_package_namespace_segments() -> None:
    assert (
        probe_module._is_non_operational_profile_path("src/main/kotlin/com/example/blog/App.kt")
        is False
    )


def test_non_operational_profile_path_ignores_jvm_samples_namespace_segments() -> None:
    assert (
        probe_module._is_non_operational_profile_path(
            "src/main/java/org/springframework/samples/petclinic/PetClinicApplication.java"
        )
        is False
    )


def test_non_operational_profile_path_matches_dotted_benchmark_segments() -> None:
    assert (
        probe_module._is_non_operational_profile_path(
            "src/FluentValidation.Tests.Benchmarks/Program.cs"
        )
        is True
    )


def test_non_operational_profile_path_matches_docsrc_segments() -> None:
    assert (
        probe_module._is_non_operational_profile_path("docsrc/content/tutorial.fsx") is True
    )


def test_non_operational_profile_path_matches_docs_segments() -> None:
    assert probe_module._is_non_operational_profile_path("docs/make.jl") is True


def test_non_operational_project_path_matches_docs_project_segments() -> None:
    assert probe_module._is_non_operational_project_path("src/FSharpPlus.Docs") is True


