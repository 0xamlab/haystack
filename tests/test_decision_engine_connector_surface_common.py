from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))

connector_surface_common = importlib.import_module("decision_engine.connector_surface_common")
build_connect_data_payload = connector_surface_common.build_connect_data_payload
build_create_connector_payload = connector_surface_common.build_create_connector_payload
build_preview_connector_payload = connector_surface_common.build_preview_connector_payload
build_update_connector_payload = connector_surface_common.build_update_connector_payload
iter_page_items = connector_surface_common.iter_page_items
iter_page_items_async = connector_surface_common.iter_page_items_async


def test_connector_surface_common_builders_strip_none_and_merge_kwargs() -> None:
    create_payload = build_create_connector_payload(
        name="Warehouse",
        connector_type="postgres",
        config={"dsn": "postgres://example"},
        description=None,
        visibility="private",
    )
    update_payload = build_update_connector_payload(
        name=None,
        description="analytics warehouse",
        visibility="workspace",
        config=None,
    )
    preview_payload = build_preview_connector_payload(
        connector_type="redis",
        config={"url": "redis://localhost:6379"},
    )
    connect_payload = build_connect_data_payload(
        {"dataset_name": "orders", "connector_id": "conn_123", "selection": None},
        {"persist": True, "description": None},
    )

    assert create_payload == {
        "name": "Warehouse",
        "connector_type": "postgres",
        "config": {"dsn": "postgres://example"},
        "visibility": "private",
    }
    assert update_payload == {
        "description": "analytics warehouse",
        "visibility": "workspace",
    }
    assert preview_payload == {
        "connector_type": "redis",
        "config": {"url": "redis://localhost:6379"},
    }
    assert connect_payload == {
        "dataset_name": "orders",
        "connector_id": "conn_123",
        "persist": True,
    }


def test_connector_surface_common_sync_iterator_handles_pagination_and_max_items() -> None:
    pages = {
        1: SimpleNamespace(connectors=["conn_1"], pages=3),
        2: SimpleNamespace(connectors=["conn_2"], pages=3),
        3: SimpleNamespace(connectors=["conn_3"], pages=3),
    }

    items = list(
        iter_page_items(
            page=1,
            limit=1,
            max_items=2,
            fetch_page=lambda current_page, _current_limit: pages[current_page],
            items_attr="connectors",
        )
    )

    assert items == ["conn_1", "conn_2"]


@pytest.mark.anyio
async def test_connector_surface_common_async_iterator_handles_pagination_and_max_items() -> None:
    pages = {
        1: SimpleNamespace(datasets=["ds_1"], pages=3),
        2: SimpleNamespace(datasets=["ds_2"], pages=3),
        3: SimpleNamespace(datasets=["ds_3"], pages=3),
    }

    async def _fetch_page(current_page: int, _current_limit: int) -> SimpleNamespace:
        return pages[current_page]

    items = [
        item
        async for item in iter_page_items_async(
            page=1,
            limit=1,
            max_items=2,
            fetch_page=_fetch_page,
            items_attr="datasets",
        )
    ]

    assert items == ["ds_1", "ds_2"]
