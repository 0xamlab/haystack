import pyarrow as pa

from apps.api_server.routers.query import _find_best_join_key, _profile_arrow_table


def test_profile_arrow_table_handles_chunked_columns_without_null_materialization():
    table = pa.table(
        {
            "amount": pa.chunked_array([[1, None, 2], [2, None, 3]]),
            "customer": pa.chunked_array([["A", None, "B"], ["B", None, "C"]]),
        }
    )

    profile = _profile_arrow_table(table)

    assert profile["amount"]["unique_count"] == 3
    assert profile["amount"]["total_count"] == 4
    assert profile["amount"]["sample_values"] == ["1", "2", "2", "3"]
    assert profile["customer"]["unique_count"] == 3
    assert profile["customer"]["sample_values"] == ["A", "B", "C"]


def test_find_best_join_key_rejects_measure_to_measure_pairs():
    connections = [
        {
            "source_a_name": "S0",
            "source_b_name": "S1",
            "col_a": "measure_left",
            "col_b": "measure_right",
            "confidence": 0.99,
            "cardinality": "many_to_many",
            "col_a_role": "derived_measure",
            "col_b_role": "base_measure",
        }
    ]

    assert _find_best_join_key("S0", "S1", connections, min_confidence=0.50) is None


def test_find_best_join_key_respects_min_confidence_threshold():
    connections = [
        {
            "source_a_name": "S0",
            "source_b_name": "S1",
            "col_a": "entity_left",
            "col_b": "entity_right",
            "confidence": 0.84,
            "cardinality": "many_to_many",
            "col_a_role": "identifier",
            "col_b_role": "identifier",
        }
    ]

    assert _find_best_join_key("S0", "S1", connections, min_confidence=0.85) is None
    assert _find_best_join_key("S0", "S1", connections, min_confidence=0.80) == (
        "entity_left",
        "entity_right",
        0.84,
        "many_to_many",
    )


def test_find_best_join_key_prefers_entity_join_over_higher_confidence_fallback():
    connections = [
        {
            "source_a_name": "S0",
            "source_b_name": "S1",
            "col_a": "entity_left",
            "col_b": "entity_right",
            "confidence": 0.88,
            "cardinality": "many_to_many",
            "col_a_role": "identifier",
            "col_b_role": "identifier",
        },
        {
            "source_a_name": "S0",
            "source_b_name": "S1",
            "col_a": "fallback_left",
            "col_b": "fallback_right",
            "confidence": 0.97,
            "cardinality": "many_to_many",
            "col_a_role": "",
            "col_b_role": "",
        },
    ]

    assert _find_best_join_key("S0", "S1", connections, min_confidence=0.50) == (
        "entity_left",
        "entity_right",
        0.88,
        "many_to_many",
    )


def test_find_best_join_key_normalizes_reversed_source_order():
    connections = [
        {
            "source_a_name": "S1",
            "source_b_name": "S0",
            "col_a": "entity_right",
            "col_b": "entity_left",
            "confidence": 0.91,
            "cardinality": "many_to_many",
            "col_a_role": "identifier",
            "col_b_role": "identifier",
        }
    ]

    assert _find_best_join_key("S0", "S1", connections, min_confidence=0.80) == (
        "entity_left",
        "entity_right",
        0.91,
        "many_to_many",
    )
