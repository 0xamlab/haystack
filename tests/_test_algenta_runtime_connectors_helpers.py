"""Shared imports + helpers for test_algenta_runtime_connectors_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_3967a6fe-cb7-2/tests/test_algenta_runtime_connectors.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import importlib

import sys

import time

from pathlib import Path

from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]

ALGENTA_CORE = ROOT / "packages" / "algenta-core"

PYTHON_SDK = ROOT / "packages" / "python-sdk"

for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

algenta_runtime = importlib.import_module("algenta.runtime")

ConnectorBrowseOutput = algenta_runtime.ConnectorBrowseOutput

ConnectorMetadata = algenta_runtime.ConnectorMetadata

ConnectorTestOutput = algenta_runtime.ConnectorTestOutput

DatasetDeleteOutput = algenta_runtime.DatasetDeleteOutput

DatasetDetail = algenta_runtime.DatasetDetail

DatasetList = algenta_runtime.DatasetList

DatasetSelectionSummary = algenta_runtime.DatasetSelectionSummary

DatasetSummary = algenta_runtime.DatasetSummary

Runtime = algenta_runtime.Runtime

RuntimeConfigurationError = algenta_runtime.RuntimeConfigurationError

RuntimeValidationError = algenta_runtime.RuntimeValidationError

SourceRegistration = algenta_runtime.SourceRegistration

def _connector_payload(connector_id: str = "conn_123") -> dict[str, object]:
    return {
        "id": connector_id,
        "name": "Warehouse Postgres",
        "description": "analytics warehouse",
        "connector_type": "postgres",
        "status": "live",
        "visibility": "private",
        "last_tested_at": None,
        "error_message": None,
        "created_at": None,
    }

def _browse_payload(connector_id: str = "conn_123") -> dict[str, object]:
    return {
        "connector_type": "postgres",
        "items": [
            {
                "id": "public.orders",
                "label": "orders",
                "kind": "table",
                "selection": {"table": "orders"},
            }
        ],
        "total": 1,
        "message": "1 table available.",
        "labels": {"entity_noun": "table", "row_noun": "row"},
        "discovery": {"scope_noun": "schema", "returned_count": 1},
        "connector_id": connector_id,
    }

def _dataset_payload(dataset_id: str = "ds_123") -> dict[str, object]:
    return {
        "dataset_id": dataset_id,
        "source_id": dataset_id,
        "dataset_name": "orders_dataset",
        "name": "Orders Dataset",
        "source_name": "orders_dataset",
        "status": "ready",
        "source_names": ["ops_postgres"],
        "description": "orders",
        "connection_id": "conn_123",
        "connection_type": "database",
        "provider": "postgres",
        "visibility": "private",
        "owner_user_id": "u1",
        "owner_key_id": "k1",
        "refreshable": True,
        "row_count": 42,
        "column_count": 3,
        "columns": 3,
        "roles_summary": {"dimensions": 2, "measures": 1},
        "discovery_labels": {"entity_noun": "table", "row_noun": "row"},
        "discovery_metadata": {"scope_noun": "schema"},
        "registered_at": None,
        "selection": {"table": "orders"},
    }



__all__ = [
    "annotations",
    "importlib",
    "sys",
    "time",
    "Path",
    "SimpleNamespace",
    "pytest",
    "ROOT",
    "ALGENTA_CORE",
    "PYTHON_SDK",
    "algenta_runtime",
    "ConnectorBrowseOutput",
    "ConnectorMetadata",
    "ConnectorTestOutput",
    "DatasetDeleteOutput",
    "DatasetDetail",
    "DatasetList",
    "DatasetSelectionSummary",
    "DatasetSummary",
    "Runtime",
    "RuntimeConfigurationError",
    "RuntimeValidationError",
    "SourceRegistration",
    "_connector_payload",
    "_browse_payload",
    "_dataset_payload",
]
