from __future__ import annotations

from typing import Any


def dict_to_node(col: dict[str, Any]) -> Any:
    """Reconstruct a ColumnNode-like object from schema metadata dict."""
    from apps.api_server.routers.query import ColumnNode, _col_name_signals_id

    role = col.get("role", "metric")
    if role == "derived_measure":
        if not col.get("formula"):
            role = "metric"
        elif _col_name_signals_id(col.get("name", "")):
            role = "identifier"

    if role == "metric" and col.get("is_numeric"):
        mean_val = col.get("mean", 0.0)
        mean_has_decimal = mean_val > 0 and abs(mean_val - int(mean_val)) > 0.01
        if mean_has_decimal:
            role = "unit_measure"

    return ColumnNode(
        name=col.get("name", ""),
        role=role,
        formula=col.get("formula"),
        mean=col.get("mean", 0.0),
        std=0.0,
        is_numeric=col.get("is_numeric", False),
        magnitude_class=col.get("magnitude", "medium"),
        semantic_type=col.get("semantic_type") or "",
        confidence=0.55 if role == "unit_measure" and not col.get("formula") else 0.6,
    )
