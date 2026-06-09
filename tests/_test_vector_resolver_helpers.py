"""Shared imports + helpers for test_vector_resolver sub-modules.

Extracted from /Users/angel/Developer/decision-engine/tests/test_vector_resolver.py during modularization.
"""
from __future__ import annotations
# ruff: noqa: F401,F403
import json

from pathlib import Path

from types import SimpleNamespace

import pytest

try:
    import mojo.engine.vector_kernels.resolver as resolver_module
    from mojo.engine.vector_kernels.resolver import (
        ColumnVectorResolver,
        _cosine,
        build_vec64,
    )
except ImportError:
    pytest.skip("Mojo engine not available", allow_module_level=True)

def _node(role, is_numeric=True, fill_rate=1.0):
    n = SimpleNamespace()
    n.role = role
    n.is_numeric = is_numeric
    n.fill_rate = fill_rate
    n.formula = None
    n.magnitude_class = None
    return n

_POS_SCHEMA = {
    "POS": [
        ("UNIT_PRICE", "unit_measure"),
        ("EXT_PRICE", "derived_measure"),
        ("QTY", "base_measure"),
        ("LINE_TOTAL", "derived_measure"),
        ("ORDERED_ON", "other"),
        ("CUSTOMER_NAME", "other"),
    ]
}

_BACKLOG_SCHEMA = {
    "BACKLOG": [
        ("OH_COST", "derived_measure"),
        ("EXT_COST", "derived_measure"),
        ("UNIT_COST", "unit_measure"),
        ("QTY_ORDERED", "base_measure"),
        ("PART_NUMBER", "other"),
    ]
}

_MULTI_SOURCE_SCHEMA = {**_POS_SCHEMA, **_BACKLOG_SCHEMA}


__all__ = [
    "json",
    "Path",
    "SimpleNamespace",
    "pytest",
    "resolver_module",
    "ColumnVectorResolver",
    "_cosine",
    "build_vec64",
    "_node",
    "_POS_SCHEMA",
    "_BACKLOG_SCHEMA",
    "_MULTI_SOURCE_SCHEMA",
]
