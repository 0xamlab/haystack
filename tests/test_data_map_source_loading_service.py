import json

import pytest

from apps.api_server.routers.data_map import DataSource
from apps.api_server.services.data_map_sources import load_source_table


@pytest.mark.anyio
async def test_load_source_table_allows_injected_url_reader() -> None:
    calls = {"count": 0}

    def _fake_read_url_text(_url: str) -> tuple[str, str]:
        calls["count"] += 1
        return (
            json.dumps(
                [
                    {"account_code": "00123", "measure_total": 10.5},
                    {"account_code": "00456", "measure_total": 12.0},
                ]
            ),
            "application/json",
        )

    src = DataSource(name="InjectedUrlJson", url="https://example.com/facts.json")

    table = await load_source_table(src, read_url_text_fn=_fake_read_url_text)

    assert calls["count"] == 1
    assert table.to_pylist() == [
        {"account_code": "00123", "measure_total": 10.5},
        {"account_code": "00456", "measure_total": 12.0},
    ]
