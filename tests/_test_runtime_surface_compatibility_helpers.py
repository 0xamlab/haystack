"""Shared imports + helpers for test_runtime_surface_compatibility_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-4/tests/test_runtime_surface_compatibility.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import importlib

import json

import re

import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALGENTA_CORE = ROOT / "packages" / "algenta"

PYTHON_SDK = ROOT / "packages" / "python-sdk"

for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from algenta import Runtime

from apps.mcp_server.registry import TOOLS, get_tool_specs



__all__ = [
    "annotations",
    "importlib",
    "json",
    "re",
    "sys",
    "Path",
    "ROOT",
    "ALGENTA_CORE",
    "PYTHON_SDK",
    "Runtime",
    "TOOLS",
    "get_tool_specs",
]
