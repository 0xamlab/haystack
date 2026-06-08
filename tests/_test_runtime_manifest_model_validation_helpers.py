"""Shared imports + helpers for test_runtime_manifest_model_validation_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-2/tests/test_runtime_manifest_model_validation.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import importlib

import sys

from pathlib import Path

import pytest

from pydantic import ValidationError

from apps.runtime_manifest import (
    get_runtime_admin_benchmarks,
    get_runtime_admin_modules,
    get_runtime_manifest,
    get_runtime_release_validation,
)

ROOT = Path(__file__).resolve().parents[1]

ALGENTA_CORE = ROOT / "packages" / "algenta-core"

PYTHON_SDK = ROOT / "packages" / "python-sdk"

for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

decision_engine_manifest_models = importlib.import_module("decision_engine.models_runtime_manifest")

algenta_manifest_models = importlib.import_module("algenta.runtime_model_manifest")

producer_runtime_manifest_models = importlib.import_module("apps.runtime_manifest")

RuntimeAdminModulesOutput = algenta_manifest_models.RuntimeAdminModulesOutput

RuntimeAdminBenchmarksOutput = algenta_manifest_models.RuntimeAdminBenchmarksOutput

RuntimeManifestOutput = algenta_manifest_models.RuntimeManifestOutput

RuntimeReleaseValidationOutput = algenta_manifest_models.RuntimeReleaseValidationOutput

RuntimeAdminModulesResult = decision_engine_manifest_models.RuntimeAdminModulesResult

RuntimeAdminBenchmarksResult = decision_engine_manifest_models.RuntimeAdminBenchmarksResult

RuntimeManifestResult = decision_engine_manifest_models.RuntimeManifestResult

ProducerRuntimeAdminBenchmarksResponse = (
    producer_runtime_manifest_models.RuntimeAdminBenchmarksResponse
)

ProducerRuntimeAdminModulesResponse = producer_runtime_manifest_models.RuntimeAdminModulesResponse

ProducerRuntimeReleaseValidationResponse = (
    producer_runtime_manifest_models.RuntimeReleaseValidationResponse
)

ProducerRuntimeManifestResponse = producer_runtime_manifest_models.RuntimeManifestResponse



__all__ = [
    "annotations",
    "importlib",
    "sys",
    "Path",
    "pytest",
    "ValidationError",
    "get_runtime_admin_benchmarks",
    "get_runtime_admin_modules",
    "get_runtime_manifest",
    "get_runtime_release_validation",
    "ROOT",
    "ALGENTA_CORE",
    "PYTHON_SDK",
    "decision_engine_manifest_models",
    "algenta_manifest_models",
    "producer_runtime_manifest_models",
    "RuntimeAdminModulesOutput",
    "RuntimeAdminBenchmarksOutput",
    "RuntimeManifestOutput",
    "RuntimeReleaseValidationOutput",
    "RuntimeAdminModulesResult",
    "RuntimeAdminBenchmarksResult",
    "RuntimeManifestResult",
    "ProducerRuntimeAdminBenchmarksResponse",
    "ProducerRuntimeAdminModulesResponse",
    "ProducerRuntimeReleaseValidationResponse",
    "ProducerRuntimeManifestResponse",
]
