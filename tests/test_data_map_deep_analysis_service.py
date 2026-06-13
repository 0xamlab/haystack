from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from apps.api_server.schemas.data_map import FieldMapping, SchemaField
from apps.api_server.services.data_map_deep_analysis import (
    deep_store_key,
    run_or_schedule_deep_analysis,
)
from apps.api_server.services.data_map_matching import (
    _detect_derived_relationships,
    _normalize,
)
from apps.api_server.services.data_map_profiles import build_source_profiles


@pytest.mark.anyio
async def test_run_or_schedule_deep_analysis_embeds_completed_result() -> None:
    parsed_sources = {
        "orders": [
            {"order_id": "A1", "extended_price": 10, "quantity": 2, "unit_price": 5},
            {"order_id": "A2", "extended_price": 24, "quantity": 4, "unit_price": 6},
            {"order_id": "A3", "extended_price": 21, "quantity": 3, "unit_price": 7},
        ],
        "shipments": [
            {"order_id": "A1", "quantity": 2},
            {"order_id": "A2", "quantity": 4},
            {"order_id": "A3", "quantity": 3},
        ],
    }
    source_profiles = build_source_profiles(parsed_sources)
    mappings = [
        FieldMapping(
            source_field="order_id",
            source="orders",
            target_field="order_id",
            target="shipments",
            confidence=0.99,
            reason=["exact name match"],
            match_type="exact",
        )
    ]
    unified_schema = {
        "extended_price": SchemaField(
            name="extended_price",
            sources=["orders"],
            distribution="triangular",
            unit="usd",
            polarity=1,
            sample_values=[10.0, 24.0, 21.0],
        )
    }
    deep_store: dict[str, dict[str, object]] = {}

    async def _no_join(
        _source_a: str,
        _source_b: str,
        _columns: dict[str, dict[str, object]],
        _min_confidence: float,
    ) -> dict[str, object] | None:
        return None

    async def _no_relation(
        _source: str,
        _columns: dict[str, list[float]],
    ) -> dict[str, object] | None:
        return None

    async def _field_map(
        numeric_fields: dict[str, list[float]],
    ) -> dict[str, object] | None:
        assert numeric_fields == {"extended_price": [10.0, 24.0, 21.0]}
        return {
            "engine": "monte_carlo",
            "variables": [
                {
                    "name": "extended_price",
                    "distribution": "triangular",
                    "params": {"low": 10.0, "mode": 21.0, "high": 24.0},
                }
            ],
            "objective_function": "sum(extended_price)",
        }

    deep, deep_pending = await run_or_schedule_deep_analysis(
        org_id="org-test",
        map_id="map-inline",
        parsed_sources=parsed_sources,
        source_profiles=source_profiles,
        match_pairs=[("orders", "shipments")],
        mappings=mappings,
        unified_schema=unified_schema,
        deep_store=deep_store,
        deep_budget_s=0.5,
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        call_mojo_join_detect_fn=_no_join,
        call_mojo_relation_detect_fn=_no_relation,
        call_mojo_field_map_fn=_field_map,
        detect_derived_relationships_fn=_detect_derived_relationships,
        normalize_fn=_normalize,
    )

    assert deep_pending is False
    assert deep_store[deep_store_key("org-test", "map-inline")] == deep
    assert deep["join_keys"] == [
        {
            "field": "order_id",
            "source": "orders",
            "mapped_to": "order_id",
            "in_source": "shipments",
            "confidence": 0.99,
        },
        {
            "field": "order_id",
            "source": "shipments",
            "mapped_to": "order_id",
            "in_source": "orders",
            "confidence": 0.99,
        },
    ]
    assert deep["derived_relationships"] == [
        {
            "formula": "extended_price = quantity × unit_price",
            "source": "orders",
            "field_result": "extended_price",
            "field_a": "quantity",
            "field_b": "unit_price",
            "operation": "multiply",
            "confidence": 1.0,
        }
    ]
    assert deep["simulation_ready"] is True
    assert deep["simulation_payload"] == {
        "mode": "expert",
        "simulation_model": "monte_carlo",
        "runs": 10000,
        "simulation": {
            "variables": [
                {
                    "name": "extended_price",
                    "distribution": "triangular",
                    "params": {"low": 10.0, "mode": 21.0, "high": 24.0},
                }
            ],
            "objective_function": "sum(extended_price)",
        },
    }


@pytest.mark.anyio
async def test_run_or_schedule_deep_analysis_persists_background_result_after_timeout() -> None:
    parsed_sources = {
        "orders": [
            {"quantity": 2, "unit_price": 5, "extended_price": 10},
            {"quantity": 4, "unit_price": 6, "extended_price": 24},
            {"quantity": 3, "unit_price": 7, "extended_price": 21},
        ]
    }
    source_profiles = build_source_profiles(parsed_sources)
    deep_store: dict[str, dict[str, object]] = {}

    async def _slow_relation(
        _source: str,
        _columns: dict[str, list[float]],
    ) -> dict[str, object] | None:
        await asyncio.sleep(0.01)
        return {"relationships": []}

    async def _field_map(
        _numeric_fields: dict[str, list[float]],
    ) -> dict[str, object] | None:
        return None

    deep, deep_pending = await run_or_schedule_deep_analysis(
        org_id="org-test",
        map_id="map-background",
        parsed_sources=parsed_sources,
        source_profiles=source_profiles,
        match_pairs=[],
        mappings=[],
        unified_schema={},
        deep_store=deep_store,
        deep_budget_s=0.001,
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        call_mojo_join_detect_fn=lambda *_args, **_kwargs: None,  # type: ignore[arg-type]
        call_mojo_relation_detect_fn=_slow_relation,
        call_mojo_field_map_fn=_field_map,
        detect_derived_relationships_fn=lambda *_args, **_kwargs: [],
        normalize_fn=_normalize,
    )

    assert deep_pending is True
    assert deep == {
        "map_id": "map-background",
        "join_keys": [],
        "derived_relationships": [],
        "simulation_ready": False,
        "simulation_payload": None,
    }

    await asyncio.sleep(0.02)

    assert deep_store[deep_store_key("org-test", "map-background")] == deep
