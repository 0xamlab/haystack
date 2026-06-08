from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import HTTPException

import apps.api_server.connectors as connectors_pkg
from apps.api_server.routers.connector_data import (
    ConnectorFetchRequest,
    ConnectorTestRequest,
    fetch_and_map,
)
from apps.api_server.routers.connector_data import (
    test_connection as connector_test_connection,
)


class StubConnector:
    def __init__(
        self,
        *,
        data: list[dict[str, Any]] | None = None,
        fetch_exc: Exception | None = None,
        validate_result: tuple[bool, str] = (True, "ok"),
    ) -> None:
        self._data = data if data is not None else []
        self._fetch_exc = fetch_exc
        self._validate_result = validate_result

    async def fetch_data(self) -> list[dict[str, Any]]:
        if self._fetch_exc is not None:
            raise self._fetch_exc
        return self._data

    async def map_to_simulation(
        self,
        data: list[dict[str, Any]],
        *,
        domain: str = "",
    ) -> dict[str, Any]:
        return {
            "variables": [{"name": "revenue"}],
            "domain": domain,
            "_connector_metadata": {"records": len(data)},
        }

    async def validate_connection(self) -> tuple[bool, str]:
        return self._validate_result


def _patch_connector_create(
    monkeypatch: pytest.MonkeyPatch,
    factory: Callable[[str, dict[str, Any]], StubConnector],
) -> None:
    monkeypatch.setattr(
        connectors_pkg.ConnectorRegistry,
        "create",
        classmethod(lambda _cls, connector_type, config: factory(connector_type, config)),
    )


@pytest.mark.anyio
async def test_fetch_and_map_returns_payload_and_connector_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = StubConnector(data=[{"revenue": 100}, {"revenue": 120}])
    _patch_connector_create(monkeypatch, lambda _connector_type, _config: stub)

    response = await fetch_and_map(
        ConnectorFetchRequest(
            connector_type="file",
            config={"path": "/tmp/data.csv"},
            domain="finance",
        )
    )

    assert response.records_fetched == 2
    assert response.fields_detected == ["revenue"]
    assert response.connector_metadata == {"records": 2}
    assert "_connector_metadata" not in response.simulation_payload
    assert response.simulation_payload["domain"] == "finance"


@pytest.mark.anyio
async def test_fetch_and_map_raises_502_with_chained_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_error = RuntimeError("connector offline")
    stub = StubConnector(fetch_exc=upstream_error)
    _patch_connector_create(monkeypatch, lambda _connector_type, _config: stub)

    with pytest.raises(HTTPException) as exc_info:
        await fetch_and_map(
            ConnectorFetchRequest(
                connector_type="sql",
                config={"dsn": "postgres://example"},
            )
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Failed to fetch data: connector offline"
    assert exc_info.value.__cause__ is upstream_error


@pytest.mark.anyio
async def test_test_connection_returns_connector_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = StubConnector(validate_result=(False, "invalid credentials"))
    _patch_connector_create(monkeypatch, lambda _connector_type, _config: stub)

    response = await connector_test_connection(
        ConnectorTestRequest(
            connector_type="rest_api",
            config={"url": "https://example.test"},
        )
    )

    assert response.success is False
    assert response.message == "invalid credentials"
