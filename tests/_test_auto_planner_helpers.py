"""Shared imports + helpers for test_auto_planner_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-5/tests/test_auto_planner.py during modularization.
"""
# ruff: noqa: F401

from pathlib import Path

from types import SimpleNamespace

from apps.api_server.routers import query as query_router

from apps.api_server.routers.query import DERIVED_MEASURE, UNIT_MEASURE, ColumnNode

from apps.api_server.services import auto_planner as auto_planner_module

from apps.api_server.services import source_registry as reg

from apps.api_server.services.auto_planner import AutoPlanner, JoinHop, QueryPlan, _profile_records

def _planner_node(role: str, *, is_numeric: bool = True, fill_rate: float = 1.0):
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
    "query_router",
    "DERIVED_MEASURE",
    "UNIT_MEASURE",
    "ColumnNode",
    "auto_planner_module",
    "reg",
    "AutoPlanner",
    "JoinHop",
    "QueryPlan",
    "_profile_records",
    "_planner_node",
]
