"""Shared imports + helpers for test_distribution_artifact_privacy_runtime_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-1/tests/test_distribution_artifact_privacy_runtime.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import asyncio

import importlib

import sys

from collections.abc import Iterator

from contextlib import contextmanager

from copy import deepcopy

from datetime import datetime

from pathlib import Path

from types import ModuleType

import pytest

from apps.platform_contract import load_platform_contract_manifest

from tests._manifest_backed_integrations import (
    assert_manifest_backed_integrations,
    assert_manifest_backed_integrations_equal,
)

ROOT = Path(__file__).resolve().parents[1]

def _artifact_contract_payload() -> dict[str, object]:
    return deepcopy(load_platform_contract_manifest())

def _assert_artifact_contract_inventory_matches_source(
    artifact_module: ModuleType,
    source_module: ModuleType,
) -> None:
    assert_manifest_backed_integrations_equal(
        artifact_module.INTEGRATIONS,
        source_module.INTEGRATIONS,
    )

@contextmanager
def _artifact_module(artifact_root: Path, package: str, module_name: str) -> Iterator[ModuleType]:
    original_path = list(sys.path)
    removed_modules = {
        name: module
        for name, module in list(sys.modules.items())
        if name == package or name.startswith(f"{package}.")
    }
    for name in removed_modules:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(artifact_root))
    try:
        yield importlib.import_module(f"{package}.{module_name}")
    finally:
        for name in list(sys.modules):
            if name == package or name.startswith(f"{package}."):
                sys.modules.pop(name, None)
        sys.path[:] = original_path
        sys.modules.update(removed_modules)



__all__ = [
    "annotations",
    "asyncio",
    "importlib",
    "sys",
    "Iterator",
    "contextmanager",
    "deepcopy",
    "datetime",
    "Path",
    "ModuleType",
    "pytest",
    "load_platform_contract_manifest",
    "assert_manifest_backed_integrations",
    "assert_manifest_backed_integrations_equal",
    "ROOT",
    "_artifact_contract_payload",
    "_assert_artifact_contract_inventory_matches_source",
    "_artifact_module",
]
