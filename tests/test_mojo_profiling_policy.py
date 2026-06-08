from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pytest

from apps.api_server.compute.mojo_errors import MojoEngineError
from apps.api_server.routers import data_map
from apps.api_server.routers import query as query_router
from apps.api_server.routers import sources as sources_router
from apps.api_server.routers.data_map import DataSource
from apps.api_server.routers.sources import RegisterRequest, register_source
from apps.api_server.services import source_registry as reg


def _sample_profile_payload() -> dict[str, dict[str, object]]:
    return {
        "measure_total": {
            "values": ["10", "20", "30", "40", "50", "60", "70", "80"],
            "strings": [],
            "sample_size": 8,
            "fill_rate": 1.0,
        }
    }


@pytest.fixture(autouse=True)
def _reset_optional_mojo_circuits() -> None:
    data_map._MOJO_WARNING_STATE.clear()
    data_map._MOJO_OPTIONAL_ENGINE_FAILURE_STATE.clear()
    query_router._QUERY_RELATION_DETECT_FAILURE = None


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


def test_mojo_column_profile_preflight_skip_reason_for_tiny_sources() -> None:
    columns = {
        "metric_a": {"values": [1.0, 2.0, 3.0], "strings": [], "sample_size": 3},
        "metric_b": {"values": [4.0, 5.0, 6.0], "strings": [], "sample_size": 3},
        "region": {"values": [], "strings": ["US", "CA", "US"], "sample_size": 3},
    }

    assert (
        data_map._mojo_column_profile_preflight_skip_reason(columns)
        == "preflight_insufficient_samples"
    )


def test_mojo_column_profile_preflight_allows_richer_sources() -> None:
    columns = {
        "metric_a": {"values": [1.0, 2.0, 3.0, 4.0], "strings": [], "sample_size": 4},
        "metric_b": {"values": [4.0, 5.0, 6.0, 7.0], "strings": [], "sample_size": 4},
        "region": {
            "values": [],
            "strings": ["US", "CA", "US", "MX"],
            "sample_size": 4,
        },
    }

    assert data_map._mojo_column_profile_preflight_skip_reason(columns) is None


@pytest.mark.anyio
async def test_detect_relations_uses_bounded_sample_limit_for_wide_schemas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _fake_invoke_engine(
        payload: dict[str, object],
        *,
        timeout: float | None = None,
    ) -> dict[str, object]:
        captured["payload"] = payload
        captured["timeout"] = timeout
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
    assert captured["timeout"] == data_map._OPTIONAL_MOJO_TIMEOUT_S


@pytest.mark.anyio
async def test_query_detect_relations_opens_engine_circuit_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    debugs: list[tuple[str, dict[str, object | None]]] = []

    async def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise RuntimeError("Mojo engine exited with code -5")

    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _raise)
    monkeypatch.setattr(query_router, "_QUERY_RELATION_DETECT_FAILURE", None)
    monkeypatch.setattr(
        query_router.logger,
        "debug",
        lambda event, **kwargs: debugs.append((event, kwargs)),
    )

    profiles = {
        "WideSource": {
            "metric_a": {"is_numeric": True, "fill_rate": 1.0, "numeric": [1.0, 2.0, 3.0]},
            "metric_b": {"is_numeric": True, "fill_rate": 1.0, "numeric": [4.0, 5.0, 6.0]},
            "metric_c": {"is_numeric": True, "fill_rate": 1.0, "numeric": [7.0, 8.0, 9.0]},
        }
    }

    first = await query_router._detect_relations("WideSource", profiles)
    second = await query_router._detect_relations("WideSource", profiles)

    assert calls == 1
    assert first == []
    assert second == []
    assert [event for event, _ in debugs] == [
        "query_relation_detect_error",
        "query_relation_detect_circuit_open",
    ]


@pytest.mark.anyio
async def test_query_detect_relations_respects_shared_optional_engine_circuit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    debugs: list[tuple[str, dict[str, object | None]]] = []

    async def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise RuntimeError("Mojo engine exited with code -5")

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "optional")
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _raise)
    monkeypatch.setattr(data_map, "_MOJO_OPTIONAL_ENGINE_FAILURE_STATE", {})
    monkeypatch.setattr(query_router, "_QUERY_RELATION_DETECT_FAILURE", None)
    monkeypatch.setattr(
        query_router.logger,
        "debug",
        lambda event, **kwargs: debugs.append((event, kwargs)),
    )

    await data_map._call_mojo_column_profile(_sample_profile_payload())

    profiles = {
        "WideSource": {
            "metric_a": {"is_numeric": True, "fill_rate": 1.0, "numeric": [1.0, 2.0, 3.0]},
            "metric_b": {"is_numeric": True, "fill_rate": 1.0, "numeric": [4.0, 5.0, 6.0]},
            "metric_c": {"is_numeric": True, "fill_rate": 1.0, "numeric": [7.0, 8.0, 9.0]},
        }
    }

    result = await query_router._detect_relations("WideSource", profiles)

    assert calls == 1
    assert result == []
    assert [event for event, _ in debugs] == ["query_relation_detect_circuit_open"]


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_call_mojo_column_profile_skips_small_payloads_before_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoked = False

    async def _unexpected_invoke(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal invoked
        invoked = True
        return {"profiles": {"metric_a": {"semantic_type": "measure"}}}

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "optional")
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _unexpected_invoke)

    result = await data_map._call_mojo_column_profile(
        {
            "metric_a": {"values": [1.0, 2.0, 3.0], "strings": [], "sample_size": 3},
            "metric_b": {"values": [4.0, 5.0, 6.0], "strings": [], "sample_size": 3},
            "region": {"values": [], "strings": ["US", "CA", "US"], "sample_size": 3},
        }
    )

    assert invoked is False
    assert result is not None
    assert result["profiles"] == {}
    assert data_map._mojo_profiling_status_from_result(result) == {
        "status": "disabled",
        "engine_type": "column_profile",
        "reason": "preflight_insufficient_samples",
        "message": None,
    }


@pytest.mark.anyio
async def test_call_mojo_column_profile_skips_payloads_over_optional_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoked = False

    async def _should_not_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal invoked
        invoked = True
        return {"profiles": {"measure_total": {"semantic_type": "measure"}}}

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "optional")
    monkeypatch.setattr(data_map, "_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES", 32)
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _should_not_run)

    result = await data_map._call_mojo_column_profile(_sample_profile_payload())

    assert invoked is False
    assert result is not None
    assert result["profiles"] == {}
    assert data_map._mojo_profiling_status_from_result(result) == {
        "status": "disabled",
        "engine_type": "column_profile",
        "reason": "preflight_payload_too_large",
        "message": (
            "Optional Mojo payload exceeds configured limit and will use the "
            "deterministic fallback path instead."
        ),
    }
    assert result["_profiling_status"]["engine_status"]["reason"] == "preflight_payload_too_large"


@pytest.mark.anyio
async def test_call_mojo_join_detect_passes_optional_timeout_to_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _fake_invoke_engine(
        payload: dict[str, object],
        *,
        timeout: float | None = None,
    ) -> dict[str, object]:
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {"join_keys": []}

    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _fake_invoke_engine)

    result = await data_map._call_mojo_join_detect(
        "left",
        "right",
        {
            "left.order_id": {"values": ["A1", "A2"], "sample_size": 2, "unique_ratio": 1.0},
            "right.order_id": {"values": ["A1", "A2"], "sample_size": 2, "unique_ratio": 1.0},
        },
    )

    assert result == {"join_keys": []}
    assert captured["timeout"] == data_map._OPTIONAL_MOJO_TIMEOUT_S


@pytest.mark.anyio
async def test_call_mojo_column_profile_suppresses_repeated_engine_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("profiling boom")

    warnings: list[tuple[str, dict[str, object | None]]] = []
    debugs: list[tuple[str, dict[str, object | None]]] = []
    monotonic_values = [0.0, 1.0]

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "optional")
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _raise)
    monkeypatch.setattr(data_map, "_MOJO_WARNING_STATE", {})
    monkeypatch.setattr(
        data_map.logger,
        "warning",
        lambda event, **kwargs: warnings.append((event, kwargs)),
    )
    monkeypatch.setattr(
        data_map.logger,
        "debug",
        lambda event, **kwargs: debugs.append((event, kwargs)),
    )
    monkeypatch.setattr(
        data_map.time,
        "monotonic",
        lambda: monotonic_values.pop(0) if monotonic_values else 1.0,
    )

    await data_map._call_mojo_column_profile(_sample_profile_payload())
    await data_map._call_mojo_column_profile(_sample_profile_payload())

    assert [event for event, _ in warnings] == ["column_profile_mojo_error"]
    assert [event for event, _ in debugs] == ["column_profile_mojo_error_suppressed"]


@pytest.mark.anyio
async def test_call_mojo_column_profile_opens_engine_circuit_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    debugs: list[tuple[str, dict[str, object | None]]] = []

    async def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise RuntimeError("Mojo engine exited with code -5")

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "optional")
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _raise)
    monkeypatch.setattr(data_map, "_MOJO_OPTIONAL_ENGINE_FAILURE_STATE", {})
    monkeypatch.setattr(
        data_map.logger,
        "debug",
        lambda event, **kwargs: debugs.append((event, kwargs)),
    )

    first = await data_map._call_mojo_column_profile(_sample_profile_payload())
    second = await data_map._call_mojo_column_profile(_sample_profile_payload())

    assert calls == 1
    assert first is not None
    assert second is not None
    assert second["_profiling_status"]["reason"] == "engine_error"
    assert [event for event, _ in debugs][-1] == "column_profile_mojo_circuit_open"


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_call_mojo_join_detect_opens_engine_circuit_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    debugs: list[tuple[str, dict[str, object | None]]] = []

    async def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise RuntimeError("Mojo engine exited with code -5")

    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _raise)
    monkeypatch.setattr(data_map, "_MOJO_OPTIONAL_ENGINE_FAILURE_STATE", {})
    monkeypatch.setattr(
        data_map.logger,
        "debug",
        lambda event, **kwargs: debugs.append((event, kwargs)),
    )

    columns = {
        "left.order_id": {"values": ["A1", "A2"], "sample_size": 2, "unique_ratio": 1.0},
        "right.order_id": {"values": ["A1", "A2"], "sample_size": 2, "unique_ratio": 1.0},
    }

    first = await data_map._call_mojo_join_detect("left", "right", columns)
    second = await data_map._call_mojo_join_detect("left", "right", columns)

    assert calls == 1
    assert first is None
    assert second is None
    assert [event for event, _ in debugs] == [
        "join_detect_mojo_error",
        "join_detect_mojo_circuit_open",
    ]


@pytest.mark.anyio
async def test_optional_mojo_global_circuit_skips_other_engine_types_after_process_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    debugs: list[tuple[str, dict[str, object | None]]] = []

    async def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise RuntimeError("Mojo engine exited with code -5")

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "optional")
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _raise)
    monkeypatch.setattr(data_map, "_MOJO_OPTIONAL_ENGINE_FAILURE_STATE", {})
    monkeypatch.setattr(
        data_map.logger,
        "debug",
        lambda event, **kwargs: debugs.append((event, kwargs)),
    )

    profile_result = await data_map._call_mojo_column_profile(_sample_profile_payload())
    join_result = await data_map._call_mojo_join_detect(
        "left",
        "right",
        {
            "left.order_id": {"values": ["A1", "A2"], "sample_size": 2, "unique_ratio": 1.0},
            "right.order_id": {"values": ["A1", "A2"], "sample_size": 2, "unique_ratio": 1.0},
        },
    )

    assert calls == 1
    assert profile_result is not None
    assert join_result is None
    assert [event for event, _ in debugs] == ["join_detect_mojo_circuit_open"]


@pytest.mark.anyio
async def test_optional_mojo_global_circuit_uses_structured_failure_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    debugs: list[tuple[str, dict[str, object | None]]] = []

    async def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise MojoEngineError(
            "Worker 2 became unhealthy during engine execution.",
            code="worker_unhealthy",
            recoverable=True,
            engine_type="column_profile",
            stage="pool_dispatch",
            details={"worker_id": 2},
        )

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "optional")
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _raise)
    monkeypatch.setattr(data_map, "_MOJO_OPTIONAL_ENGINE_FAILURE_STATE", {})
    monkeypatch.setattr(
        data_map.logger,
        "debug",
        lambda event, **kwargs: debugs.append((event, kwargs)),
    )

    profile_result = await data_map._call_mojo_column_profile(_sample_profile_payload())
    join_result = await data_map._call_mojo_join_detect(
        "left",
        "right",
        {
            "left.order_id": {"values": ["A1", "A2"], "sample_size": 2, "unique_ratio": 1.0},
            "right.order_id": {"values": ["A1", "A2"], "sample_size": 2, "unique_ratio": 1.0},
        },
    )

    assert calls == 1
    assert profile_result is not None
    assert profile_result["_profiling_status"]["message"] == (
        "Worker 2 became unhealthy during engine execution."
    )
    assert join_result is None
    assert data_map._MOJO_OPTIONAL_ENGINE_FAILURE_STATE[data_map._GLOBAL_OPTIONAL_MOJO_ENGINE_KEY][
        1
    ].startswith("worker_unhealthy:")
    assert [event for event, _ in debugs] == ["join_detect_mojo_circuit_open"]


def test_optional_mojo_global_circuit_survives_engine_specific_clear() -> None:
    data_map._record_optional_mojo_engine_failure(
        "column_profile",
        MojoEngineError(
            "Worker 2 became unhealthy during engine execution.",
            code="worker_unhealthy",
            recoverable=True,
            engine_type="column_profile",
            stage="pool_dispatch",
        ),
    )

    data_map._clear_optional_mojo_engine_failure("column_profile")

    assert data_map._get_optional_mojo_engine_skip_reason("join_detect") is not None


@pytest.mark.anyio
async def test_optional_mojo_non_global_failure_does_not_disable_other_engine_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def _raise_profile(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise RuntimeError("profiling boom")

    monkeypatch.setattr(data_map.settings, "mojo_profiling_policy", "optional")
    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _raise_profile)
    monkeypatch.setattr(data_map, "_MOJO_OPTIONAL_ENGINE_FAILURE_STATE", {})

    profile_result = await data_map._call_mojo_column_profile(_sample_profile_payload())

    assert profile_result is not None
    assert calls == 1

    async def _join_success(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return {"join_keys": []}

    monkeypatch.setattr("apps.api_server.compute.mojo_adapter.invoke_engine", _join_success)
    join_result = await data_map._call_mojo_join_detect(
        "left",
        "right",
        {
            "left.order_id": {"values": ["A1", "A2"], "sample_size": 2, "unique_ratio": 1.0},
            "right.order_id": {"values": ["A1", "A2"], "sample_size": 2, "unique_ratio": 1.0},
        },
    )

    assert calls == 2
    assert join_result == {"join_keys": []}


@pytest.mark.anyio
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


@pytest.mark.anyio
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


@pytest.mark.anyio
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
            sources=[
                query_router.DataSource(name="profile_disabled", csv="measure_total\n10\n20\n")
            ]
        ),
        auth={"org_id": "org_profile_disabled"},
    )

    schema_result = result["sources"][0]
    assert schema_result["mojo_profiling_status"]["status"] == "disabled"
    assert schema_result["mojo_profiling_status"]["reason"] == "configured_disabled"
    assert schema_result["schema"]["mojo_profiling_status"]["status"] == "disabled"


@pytest.mark.anyio
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
    profiling_status = data_map._mojo_profiling_status_from_result(result)
    if profiling_status["status"] != "enabled":
        pytest.skip(
            "Mojo column profiling unavailable for current binary: "
            f"{profiling_status.get('reason') or 'disabled'}"
        )
    assert result["profiles"]["HASH_ID"]["semantic_type"] == "id"
    assert "mean" not in result["profiles"]["HASH_ID"]
    assert "mean" in result["profiles"]["ROW_WID"]
