from __future__ import annotations

import json

import pytest

from apps.api_server.services.connectors.tester import test_connector_real


@pytest.mark.asyncio
async def test_connector_real_supports_file_csv_path(tmp_path):
    csv_path = tmp_path / "facts.csv"
    csv_path.write_text("entity_id,measure_total\nA1,10\nA2,20\n", encoding="utf-8")

    success, message, latency_ms = await test_connector_real(
        "file",
        {
            "file_type": "csv",
            "file_path": str(csv_path),
        },
    )

    assert success is True
    assert "2 records" in message
    assert latency_ms >= 0


@pytest.mark.asyncio
async def test_connector_real_supports_file_json_inline():
    payload = json.dumps({"data": {"items": [{"entity_id": "A1", "measure_total": 10}]}})

    success, message, _ = await test_connector_real(
        "file_upload",
        {
            "file_type": "json",
            "content": payload,
            "json_path": "data.items",
        },
    )

    assert success is True
    assert "1 records" in message

