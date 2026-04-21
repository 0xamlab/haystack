from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pytest

from apps.api_server.routers import data_map
from apps.api_server.routers import query as query_router
from apps.api_server.routers import sources as sources_router
from apps.api_server.routers.data_map import DataSource
from apps.api_server.routers.sources import RegisterRequest, register_source
from apps.api_server.services import source_registry as reg


def _sample_profile_payload() -> dict[str, dict[str, object]]:
    return {
        "measure_total": {
            "values": ["10", "20"],
            "strings": [],
            "sample_size": 2,
            "fill_rate": 1.0,
        }
    }


def test_build_mojo_column_profile_columns_separates_finite_numeric_and_string_samples() -> None:
    payload = data_map._build_mojo_column_profile_columns(
        {
            "HASH_ID": {
                "numeric": [],
                "strings": [
                    "6A73804E3D9CF6FD1ABE0C59BB15E647",
                    "A05DC9F776F8A9AAB6B80AF232707C4C",
                ],
                "sample_values": [
                    "6A73804E3D9CF6FD1ABE0C59BB15E647",
                    "A05DC9F776F8A9AAB6B80AF232707C4C",
                ],
                "total_count": 2,
                "fill_rate": 1.0,
            },
            "measure_total": {
                "numeric": [10.0, 20.5, float("inf"), float("nan")],
                "strings": ["10", "20.5"],
                "sample_values": ["10", "20.5"],
                "total_count": 4,
                "fill_rate": 1.0,
            },
        },
        value_limit=4,
        string_limit=3,
        include_fill_rate=True,
    )

    assert payload["HASH_ID"] == {
        "values": [],
        "strings": [
            "6A73804E3D9CF6FD1ABE0C59BB15E647",
            "A05DC9F776F8A9AAB6B80AF232707C4C",
        ],
        "sample_size": 2,
        "fill_rate": 1.0,
    }
    assert payload["measure_total"]["values"] == [10.0, 20.5]
    assert payload["measure_total"]["strings"] == ["10", "20.5"]


def test_mojo_column_profile_sample_limits_shrink_for_wide_schemas() -> None:
    assert data_map._mojo_column_profile_sample_limits(12) == (50, 50)
    assert data_map._mojo_column_profile_sample_limits(48) == (24, 16)
    assert data_map._mojo_column_profile_sample_limits(96) == (16, 12)
    assert data_map._mojo_column_profile_sample_limits(220) == (12, 12)


@pytest.mark.asyncio
async def test_detect_relations_uses_bounded_sample_limit_for_wide_schemas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _fake_invoke_engine(payload: dict[str, object]) -> dict[str, object]:
        captured["payload"] = payload
        return {"relationships": []}

    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _fake_invoke_engine)

    profiles = {
        "WideSource": {
            f"metric_{index:03d}": {
                "is_numeric": True,
                "fill_rate": 1.0,
                "numeric": [float(value) for value in range(300)],
            }
            for index in range(140)
        }
    }

    result = await query_router._detect_relations("WideSource", profiles)

    assert result == []
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["engine_type"] == "relation_detect"
    assert len(payload["columns"]) == 140
    assert all(len(values) == 64 for values in payload["columns"].values())


@pytest.mark.asyncio
async def test_call_mojo_column_profile_returns_disabled_status_when_policy_optional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("profiling boom")

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "optional")
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _raise)

    result = await data_map._call_mojo_column_profile(_sample_profile_payload())

    assert result is not None
    assert result["profiles"] == {}
    assert data_map._mojo_profiling_status_from_result(result) == {
        "status": "disabled",
        "engine_type": "column_profile",
        "reason": "engine_error",
        "message": "profiling boom",
    }


@pytest.mark.asyncio
async def test_call_mojo_column_profile_skips_mojo_when_policy_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoked = False

    async def _should_not_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal invoked
        invoked = True
        raise AssertionError("profiling engine must not run when disabled")

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "disabled")
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _should_not_run)

    result = await data_map._call_mojo_column_profile(_sample_profile_payload())

    assert invoked is False
    assert result is not None
    assert result["profiles"] == {}
    assert data_map._mojo_profiling_status_from_result(result) == {
        "status": "disabled",
        "engine_type": "column_profile",
        "reason": "configured_disabled",
        "message": None,
    }


@pytest.mark.asyncio
async def test_call_mojo_column_profile_raises_when_policy_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("profiling boom")

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "required")
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _raise)

    with pytest.raises(data_map.MojoInstrumentationError) as excinfo:
        await data_map._call_mojo_column_profile(_sample_profile_payload())

    assert excinfo.value.engine_type == "column_profile"


@pytest.mark.asyncio
async def test_register_source_persists_disabled_profiling_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "disabled")

    async with query_router._CACHE_LOCK:
        query_router._SOURCE_CACHE.clear()
        query_router._PLANNER_CACHE.clear()

    async def _fake_relations(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return []

    async def _fake_get_registry_planner(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return object(), False, "rev_disabled"

    monkeypatch.setattr(sources_router, "_detect_relations", _fake_relations)
    monkeypatch.setattr(sources_router, "_get_registry_planner", _fake_get_registry_planner)

    payload = RegisterRequest(
        source=DataSource(
            name="DisabledProfileSource",
            csv="customer_id,measure_total\nC100,10\nC200,20\n",
        )
    )

    registered = await register_source(payload, auth={"org_id": "org_profile_disabled"})
    meta = reg.get_source_meta("org_profile_disabled", registered["source_id"])

    assert registered["mojo_profiling_status"]["status"] == "disabled"
    assert registered["mojo_profiling_status"]["reason"] == "configured_disabled"
    assert registered["schema"]["mojo_profiling_status"]["status"] == "disabled"
    assert meta is not None
    assert meta["mojo_profiling_status"]["reason"] == "configured_disabled"


@pytest.mark.asyncio
async def test_infer_schema_returns_disabled_profiling_status_when_policy_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_load_profiled_source(*args, **kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            profile={
                "measure_total": {
                    "sample_values": ["10", "20"],
                    "strings": [],
                    "total_count": 2,
                    "fill_rate": 1.0,
                    "is_numeric": True,
                    "numeric": [10.0, 20.0],
                    "unique_count": 2,
                }
            },
            arrow_table=pa.table({"measure_total": [10, 20]}),
            row_count=2,
            ingest_mode="columnar",
        )

    async def _fake_relations(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return []

    async def _should_not_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("profiling engine must not run when disabled")

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "disabled")
    monkeypatch.setattr(query_router, "_load_profiled_source", _fake_load_profiled_source)
    monkeypatch.setattr(query_router, "_detect_relations", _fake_relations)
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _should_not_run)
    query_router._SOURCE_CACHE.clear()

    result = await query_router.infer_schema(
        query_router.SchemaRequest(
            sources=[query_router.DataSource(name="profile_disabled", csv="measure_total\n10\n20\n")]
        ),
        auth={"org_id": "org_profile_disabled"},
    )

    schema_result = result["sources"][0]
    assert schema_result["mojo_profiling_status"]["status"] == "disabled"
    assert schema_result["mojo_profiling_status"]["reason"] == "configured_disabled"
    assert schema_result["schema"]["mojo_profiling_status"]["status"] == "disabled"


@pytest.mark.asyncio
async def test_real_available_inventory_column_profile_stays_json_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary = Path("mojo_build/simulate")
    if not binary.exists():
        pytest.skip("mojo_build/simulate is required for this regression test")

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "optional")

    csv_path = Path(__file__).resolve().parents[1] / "test_files" / "Available_Inventory.csv"
    source = DataSource(
        name="AvailableInventory",
        csv=csv_path.read_text(encoding="utf-8-sig", errors="replace"),
    )
    loaded = await query_router._load_profiled_source(source)
    payload = data_map._build_mojo_column_profile_columns(
        loaded.profile,
        value_limit=50,
        string_limit=50,
        include_fill_rate=True,
    )

    result = await data_map._call_mojo_column_profile(payload)

    assert result is not None
    assert data_map._mojo_profiling_status_from_result(result)["status"] == "enabled"
    assert result["profiles"]["HASH_ID"]["semantic_type"] == "id"
    assert "mean" not in result["profiles"]["HASH_ID"]
    assert "mean" in result["profiles"]["ROW_WID"]
