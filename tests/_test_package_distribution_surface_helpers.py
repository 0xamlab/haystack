"""Shared imports + helpers for test_package_distribution_surface_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_6761da26-f90-1/tests/test_package_distribution_surface.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import json

import tomllib

from pathlib import Path

from tests._manifest_backed_integrations import (
    assert_manifest_backed_integration_texts_equal,
)

ROOT = Path(__file__).resolve().parents[1]

CLI_DOC = ROOT / "apps" / "docs" / "docs" / "sdks" / "cli.md"



__all__ = [
    "annotations",
    "json",
    "tomllib",
    "Path",
    "assert_manifest_backed_integration_texts_equal",
    "ROOT",
    "CLI_DOC",
]
