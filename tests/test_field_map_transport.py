from __future__ import annotations

import pytest

from apps.api_server.routers import data_map, ingest


@pytest.fixture(autouse=True)
def _reset_optional_mojo_state() -> None:
    data_map._MOJO_WARNING_STATE.clear()
    data_map._MOJO_OPTIONAL_ENGINE_FAILURE_STATE.clear()


@pytest.mark.anyio
async def test_call_mojo_field_map_routes_through_invoke_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    async def _fake_invoke_engine(
        payload: dict[str, object],
        *,
        timeout: float | None = None,
    ) -> dict[str, object]:
        seen["payload"] = payload
        seen["timeout"] = timeout
        return {"mapped_fields": {"revenue": "revenue"}}

    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _fake_invoke_engine)

    result = await data_map._call_mojo_field_map({"revenue": [10.0, 12.0]})

    assert result == {"mapped_fields": {"revenue": "revenue"}}
    assert seen["payload"] == {
        "engine_type": "field_map",
        "data": {"revenue": [10.0, 12.0]},
    }
    assert seen["timeout"] == data_map._OPTIONAL_MOJO_TIMEOUT_S


@pytest.mark.anyio
async def test_map_via_mojo_routes_through_invoke_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    async def _fake_invoke_engine(
        payload: dict[str, object],
        *,
        timeout: float | None = None,
    ) -> dict[str, object]:
        seen["payload"] = payload
        seen["timeout"] = timeout
        return {"mapped_fields": {"cost": "cost"}}

    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _fake_invoke_engine)

    result = await ingest._map_via_mojo({"cost": [1.0, 2.0, 3.0]})

    assert result == {"mapped_fields": {"cost": "cost"}}
    assert seen["payload"] == {
        "engine_type": "field_map",
        "data": {"cost": [1.0, 2.0, 3.0]},
    }
    assert seen["timeout"] is None
