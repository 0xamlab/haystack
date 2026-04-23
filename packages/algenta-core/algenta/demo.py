"""Zero-friction deterministic runtime demo for Algenta."""

from __future__ import annotations

import sys
from typing import Any

from algenta.branding import runtime_banner
from algenta.runtime import QueryOutput, ResolveOutput, Runtime

_DEMO_DATA = [
    {"product_line": "Electronics", "revenue": 42193221, "region": "United States"},
    {"product_line": "Apparel", "revenue": 28114992, "region": "United States"},
    {"product_line": "Home", "revenue": 19852111, "region": "United States"},
    {"product_line": "Electronics", "revenue": 1204000, "region": "Canada"},
    {"product_line": "Apparel", "revenue": 814000, "region": "Canada"},
]


def _render_result(result: QueryOutput) -> str:
    if result.result_type != "table" or not isinstance(result.result, list):
        return str(result.result)

    rows: list[dict[str, Any]] = result.result
    if not rows:
        return "(no rows)"

    columns = list(rows[0].keys())
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    header = "  " + "  ".join(column.upper().ljust(widths[column]) for column in columns)
    divider = "  " + "  ".join("─" * widths[column] for column in columns)
    body = [
        "  " + "  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns)
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def _emit(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")


def main() -> int:
    runtime = Runtime()
    imported = runtime.import_preview(
        _DEMO_DATA,
        name="demo_orders",
        source_ref="bundled demo dataset",
    )
    plan = runtime.resolve(
        {
            "source_name": "demo_orders",
            "metric": "revenue",
            "group_by": "product_line",
        }
    )
    result = runtime.query(plan)

    _emit(
        runtime_banner(
            "Algenta Runtime Demo",
            [
                "Local mode | deterministic resolve -> query",
                "Source: demo_orders | dataset bundled with algenta-core",
                "No API key required",
            ],
        )
    )
    _emit()
    _emit(imported.preview)
    _emit()
    _emit("Resolved plan")
    assert isinstance(plan, ResolveOutput)
    assert plan.resolved_plan is not None
    _emit(f"  source={plan.resolved_plan.source_name}")
    _emit(f"  metric={plan.resolved_plan.metric_column}")
    _emit(f"  group_by={plan.resolved_plan.group_column}")
    _emit(f"  aggregation={plan.resolved_plan.aggregation}")
    _emit(f"  confidence={plan.confidence:.3f}")
    _emit(f"  plan_hash={plan.plan_hash}")
    _emit(f"  latency_ms={plan.latency_ms:.3f}")
    _emit()
    _emit("Query result")
    _emit(_render_result(result))
    _emit()
    _emit("Metadata")
    _emit(f"  query_plan_hash={result.plan_hash}")
    _emit(f"  result_type={result.result_type}")
    _emit(f"  latency_ms={result.latency_ms:.3f}")
    _emit()
    _emit("Next step")
    _emit("  Swap the bundled demo source for your own data with Runtime.connect(...)")
    _emit("  Or use Runtime(mode='api', api_key='de_live_...') for the direct API path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
