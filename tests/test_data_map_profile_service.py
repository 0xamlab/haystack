import pytest

from apps.api_server.services.data_map_matching import _semantic_similarity
from apps.api_server.services.data_map_profiles import (
    build_source_profiles,
    build_unified_schema,
)


def test_build_source_profiles_preserves_sparse_numeric_samples_and_stats() -> None:
    profiles = build_source_profiles(
        {
            "sales": [
                {"sku": "A", "revenue": None, "region": "east"},
                {"sku": "B", "revenue": "10", "region": "west"},
                {"sku": "C", "revenue": None, "region": "east"},
                {"sku": "D", "revenue": "20", "region": "south"},
            ]
        }
    )

    revenue = profiles["sales"]["revenue"]
    assert revenue["numeric"] == [10.0, 20.0]
    assert revenue["is_numeric"] is True
    assert revenue["unique_count"] == 2
    assert revenue["sample_values"] == ["10.0", "20.0"]
    assert revenue["mean"] == 15.0
    assert revenue["min"] == 10.0
    assert revenue["max"] == 20.0

    region = profiles["sales"]["region"]
    assert region["strings"] == ["east", "west", "east", "south"]
    assert region["is_numeric"] is False
    assert region["sample_values"] == ["east", "west", "south"]


@pytest.mark.anyio
async def test_build_unified_schema_merges_semantic_aliases_across_sources() -> None:
    source_profiles = {
        "orders": {
            "qty": {
                "numeric": [1.0, 2.0],
                "strings": [],
                "is_numeric": True,
            }
        },
        "inventory": {
            "quantity": {
                "numeric": [3.0, 4.0],
                "strings": [],
                "is_numeric": True,
            }
        },
    }
    source_mojo_profiles = {
        "orders": {
            "profiles": {
                "qty": {
                    "distribution": "triangular",
                    "polarity": 1,
                    "unit_hint": "units",
                }
            }
        },
        "inventory": {
            "profiles": {
                "quantity": {
                    "distribution": "triangular",
                    "polarity": 1,
                    "unit_hint": "units",
                }
            }
        },
    }

    async def _noop_field_map(
        _numeric_fields: dict[str, list[float]],
    ) -> dict[str, object] | None:
        return None

    result = await build_unified_schema(
        source_profiles,
        source_mojo_profiles,
        semantic_similarity_fn=_semantic_similarity,
        call_mojo_field_map_fn=_noop_field_map,
    )

    assert set(result.unified_schema.keys()) == {"qty"}
    assert result.all_fields_seen == {"qty"}
    schema_field = result.unified_schema["qty"]
    assert schema_field.sources == ["orders", "inventory"]
    assert schema_field.distribution == "triangular"
    assert schema_field.unit == "units"
    assert schema_field.polarity == 1
    assert schema_field.sample_values == [1.0, 2.0]


@pytest.mark.anyio
async def test_build_unified_schema_uses_field_map_fallback_when_profile_missing() -> None:
    source_profiles = {
        "finance": {
            "gross_margin": {
                "numeric": [0.2, 0.3],
                "strings": [],
                "is_numeric": True,
            }
        }
    }
    source_mojo_profiles = {"finance": {"profiles": {}}}

    async def _fake_field_map(
        numeric_fields: dict[str, list[float]],
    ) -> dict[str, object] | None:
        assert numeric_fields == {"gross_margin": [0.2, 0.3]}
        return {
            "field_analysis": {
                "gross_margin": {
                    "distribution": "beta",
                    "polarity": 1,
                    "unit": "ratio",
                }
            }
        }

    result = await build_unified_schema(
        source_profiles,
        source_mojo_profiles,
        semantic_similarity_fn=lambda left, right: (1.0, []) if left == right else (0.0, []),
        call_mojo_field_map_fn=_fake_field_map,
    )

    schema_field = result.unified_schema["gross_margin"]
    assert schema_field.distribution == "beta"
    assert schema_field.unit == "ratio"
    assert schema_field.polarity == 1
    assert schema_field.sample_values == [0.2, 0.3]
