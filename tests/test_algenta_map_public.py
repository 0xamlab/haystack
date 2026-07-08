from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_map_data_preserves_matching_and_join_key_behavior() -> None:
    from algenta import map_data

    sales_records = [
        {"customer_id": "c1", "qty": 2, "revenue": 10.0},
        {"customer_id": "c2", "qty": 3, "revenue": 20.0},
    ]
    order_records = [
        {"customer_id": "c1", "quantity": 2, "sales": 10.0},
        {"customer_id": "c2", "quantity": 3, "sales": 20.0},
    ]

    result = map_data(sales_records, order_records, names=["sales", "orders"])

    assert result.sources_analyzed == 2
    assert result.simulation_ready is True
    assert any(
        mapping.source_field == "qty"
        and mapping.target_field == "quantity"
        and mapping.confidence >= 1.0
        for mapping in result.mappings
    )
    assert any(join_key["field"] == "customer_id" for join_key in result.join_keys)


def test_query_data_top_n_grouping_preserves_public_behavior() -> None:
    from algenta import query_data

    records = [
        {"customer": "Acme", "revenue": 10.0},
        {"customer": "Bravo", "revenue": 30.0},
        {"customer": "Acme", "revenue": 25.0},
    ]

    rows = query_data("top 1 customers by revenue", records)

    assert rows == [{"customer": "Acme", "revenue": 35.0, "count": 2}]
