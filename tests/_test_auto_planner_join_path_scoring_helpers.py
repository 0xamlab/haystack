"""Shared imports + helpers for test_auto_planner_join_path_scoring_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_3967a6fe-cb7-1/tests/test_auto_planner_join_path_scoring.py during modularization.
"""
# ruff: noqa: F401

from pathlib import Path

from types import SimpleNamespace

from apps.api_server.services.auto_planner import AutoPlanner

def _planner_node(role: str, *, is_numeric: bool = False, fill_rate: float = 1.0):
    node = SimpleNamespace()
    node.role = role
    node.is_numeric = is_numeric
    node.fill_rate = fill_rate
    node.formula = None
    node.magnitude_class = None
    return node



__all__ = [
    "Path",
    "SimpleNamespace",
    "AutoPlanner",
    "_planner_node",
]
