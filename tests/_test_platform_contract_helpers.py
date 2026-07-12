"""Shared imports + helpers for test_platform_contract_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-4/tests/test_platform_contract.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import json

from pathlib import Path

from types import SimpleNamespace

import pytest

import yaml

from pydantic import ValidationError

from apps import platform_contract

from apps.api_server.main import app

from tests import _manifest_backed_integrations as manifest_helpers

from tests._manifest_backed_integrations import (
    MANIFEST_BACKED_INTEGRATIONS,
    NORMALIZED_MANIFEST_BACKED_INTEGRATIONS,
    assert_manifest_backed_integration_texts_equal,
    assert_manifest_backed_integrations,
    contract_integrations_match_manifest,
)

ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = ROOT / "apps" / "docs" / "integration_manifest.v1.json"

EXAMPLE_BASE_URL = "https://your-algenta-base-url.example"

EXAMPLE_MCP_ENDPOINT = f"{EXAMPLE_BASE_URL}/mcp"



__all__ = [
    "annotations",
    "json",
    "Path",
    "SimpleNamespace",
    "pytest",
    "yaml",
    "ValidationError",
    "platform_contract",
    "app",
    "manifest_helpers",
    "MANIFEST_BACKED_INTEGRATIONS",
    "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS",
    "assert_manifest_backed_integration_texts_equal",
    "assert_manifest_backed_integrations",
    "contract_integrations_match_manifest",
    "ROOT",
    "MANIFEST_PATH",
    "EXAMPLE_BASE_URL",
    "EXAMPLE_MCP_ENDPOINT",
]
