"""
Chart-ready output service — produces Vega-Lite compatible JSON specs
and histogram data directly from simulation results.

Phase 6: build_histogram() and build_cdf() check for Mojo-precomputed data
(histogram_data, cdf_data) in the simulation result. If present, Python only
assembles the Vega-Lite wrapper JSON without recomputing bins. This moves the
O(N) bin-computation cost from Python to Mojo (single pass, cache-hot).

build_tornado() and build_fan_chart() also use Mojo-computed data directly
when available in sensitivity_analysis.tornado_chart and time_series_result.fan_chart.
"""

from __future__ import annotations

import math
from typing import Any

# ── Histogram ─────────────────────────────────────────────────────────────────


def build_histogram(
    outcomes: list[float] | None = None,
    n_bins: int = 50,
    unit: str = "",
    title: str = "Outcome Distribution",
    simulation_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a Vega-Lite histogram spec.

    Phase 6: If simulation_result contains "histogram_data" (Mojo-computed),
    use those pre-computed bins directly — skip O(N) Python sort+bucket pass.
    Falls back to full Python computation when Mojo data is absent or outcomes
    list is provided directly.
    """
    # ── Phase 6: Use Mojo-precomputed histogram if available ─────────────────
    if simulation_result is not None:
        mojo_hist = simulation_result.get("histogram_data")
        if mojo_hist and isinstance(mojo_hist.get("bins"), list) and len(mojo_hist["bins"]) > 0:
            mojo_bins = mojo_hist["bins"]
            n = simulation_result.get("scenarios_run", sum(b["count"] for b in mojo_bins))

            # Build Vega-Lite compatible bin records from Mojo output
            bins: list[dict[str, Any]] = []
            # Compute bin_width from first two bins
            bin_width = 1.0
            if len(mojo_bins) >= 2:
                bin_width = mojo_bins[1]["bin_lo"] - mojo_bins[0]["bin_lo"]

            for b in mojo_bins:
                bin_lo = b["bin_lo"]
                count = b["count"]
                bins.append(
                    {
                        "bin_start": bin_lo,
                        "bin_end": bin_lo + bin_width,
                        "count": count,
                        "freq": count / max(n, 1),
                    }
                )

            # Stats from simulation_result summary when outcomes list absent
            summary = simulation_result.get("summary", {})
            pcts = simulation_result.get("percentiles", {})
            risk = simulation_result.get("risk", {})

            return {
                "type": "histogram",
                "title": title,
                "unit": unit,
                "source": "mojo_precomputed",
                "stats": {
                    "mean": summary.get("mean", 0.0),
                    "std": summary.get("std", 0.0),
                    "p5": pcts.get("p5", 0.0),
                    "p50": pcts.get("p50", 0.0),
                    "p95": pcts.get("p95", 0.0),
                    "probability_of_loss": risk.get("probability_of_loss", 0.0),
                    "n": n,
                },
                "bins": bins,
                "vega_lite": _histogram_vega_spec(bins, bin_width, title, unit),
            }

    # ── Python computation fallback ──────────────────────────────────────────
    if not outcomes:
        return {}

    outcomes_sorted = sorted(outcomes)
    n = len(outcomes_sorted)
    bins, bin_width = _compute_python_histogram_bins(outcomes_sorted, n_bins)

    mean_v = sum(outcomes) / n
    var_v = sum((x - mean_v) ** 2 for x in outcomes) / max(n - 1, 1)
    std_v = math.sqrt(var_v)
    p5 = outcomes_sorted[max(0, int(n * 0.05))]
    p95 = outcomes_sorted[min(n - 1, int(n * 0.95))]
    pol = sum(1 for x in outcomes if x < 0) / n

    return {
        "type": "histogram",
        "title": title,
        "unit": unit,
        "source": "python_computed",
        "stats": {
            "mean": mean_v,
            "std": std_v,
            "p5": p5,
            "p50": outcomes_sorted[n // 2],
            "p95": p95,
            "probability_of_loss": pol,
            "n": n,
        },
        "bins": bins,
        "vega_lite": _histogram_vega_spec(bins, bin_width, title, unit),
    }


def _compute_python_histogram_bins(
    outcomes_sorted: list[float],
    n_bins: int,
) -> tuple[list[dict[str, float | int]], float]:
    n = len(outcomes_sorted)
    lo = outcomes_sorted[0]
    display_hi = outcomes_sorted[-1]
    if lo == display_hi:
        display_hi = lo + 1.0
    bin_width = (display_hi - lo) / n_bins

    counts = [0] * n_bins
    for value in outcomes_sorted:
        if value >= display_hi:
            bucket_index = n_bins - 1
        else:
            bucket_index = int((value - lo) / bin_width)
            if bucket_index < 0:
                bucket_index = 0
            elif bucket_index >= n_bins:
                bucket_index = n_bins - 1
        counts[bucket_index] += 1

    bins: list[dict[str, float | int]] = []
    for i, count in enumerate(counts):
        bin_lo = lo + i * bin_width
        bin_hi = bin_lo + bin_width
        bins.append(
            {
                "bin_start": bin_lo,
                "bin_end": bin_hi,
                "count": count,
                "freq": count / n,
            }
        )
    return bins, bin_width


def _histogram_vega_spec(
    bins: list[dict[str, Any]],
    bin_width: float,
    title: str,
    unit: str,
) -> dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {"values": bins},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {
                "field": "bin_start",
                "type": "quantitative",
                "bin": {"binned": True, "step": bin_width},
                "title": unit or "Value",
            },
            "x2": {"field": "bin_end"},
            "y": {
                "field": "freq",
                "type": "quantitative",
                "title": "Frequency",
                "axis": {"format": ".1%"},
            },
            "color": {
                "condition": {"test": "datum.bin_start < 0", "value": "#ef4444"},
                "value": "#6366f1",
            },
            "tooltip": [
                {"field": "bin_start", "type": "quantitative", "format": ".3g", "title": "From"},
                {"field": "bin_end", "type": "quantitative", "format": ".3g", "title": "To"},
                {"field": "count", "type": "quantitative", "title": "Count"},
                {
                    "field": "freq",
                    "type": "quantitative",
                    "format": ".2%",
                    "title": "Frequency",
                },
            ],
        },
    }


# ── CDF ───────────────────────────────────────────────────────────────────────


def build_cdf(
    outcomes: list[float] | None = None,
    n_points: int = 200,
    unit: str = "",
    title: str = "Cumulative Distribution",
    simulation_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a CDF chart.

    Phase 6: Uses Mojo-precomputed cdf_data when available in simulation_result.
    """
    # ── Phase 6: Mojo-precomputed CDF ────────────────────────────────────────
    if simulation_result is not None:
        mojo_cdf = simulation_result.get("cdf_data")
        if mojo_cdf and isinstance(mojo_cdf.get("points"), list) and len(mojo_cdf["points"]) > 0:
            cdf_points = [{"value": p["x"], "cdf": p["cdf"]} for p in mojo_cdf["points"]]
            return {
                "type": "cdf",
                "title": title,
                "unit": unit,
                "source": "mojo_precomputed",
                "data": cdf_points,
                "vega_lite": _cdf_vega_spec(cdf_points, title, unit),
            }

    # ── Python fallback ───────────────────────────────────────────────────────
    if not outcomes:
        return {}

    sorted_outcomes = sorted(outcomes)
    n = len(sorted_outcomes)
    step = max(1, n // n_points)
    cdf_points = [{"value": sorted_outcomes[i], "cdf": (i + 1) / n} for i in range(0, n, step)]

    return {
        "type": "cdf",
        "title": title,
        "unit": unit,
        "source": "python_computed",
        "data": cdf_points,
        "vega_lite": _cdf_vega_spec(cdf_points, title, unit),
    }


def _cdf_vega_spec(
    cdf_points: list[dict[str, Any]],
    title: str,
    unit: str,
) -> dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {"values": cdf_points},
        "mark": {"type": "line", "color": "#6366f1", "strokeWidth": 2},
        "encoding": {
            "x": {"field": "value", "type": "quantitative", "title": unit or "Value"},
            "y": {
                "field": "cdf",
                "type": "quantitative",
                "title": "Cumulative Probability",
                "axis": {"format": ".0%"},
                "scale": {"domain": [0, 1]},
            },
            "tooltip": [
                {"field": "value", "format": ".3g", "title": unit or "Value"},
                {"field": "cdf", "format": ".1%", "title": "Probability"},
            ],
        },
    }


# ── Fan chart ─────────────────────────────────────────────────────────────────


def build_fan_chart(
    time_steps: list[dict[str, Any]] | None = None,
    granularity: str = "period",
    unit: str = "",
    title: str = "Time Series Fan Chart",
    simulation_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a Vega-Lite fan chart from time series results.

    Phase 6: Uses Mojo-computed fan_chart data from time_series_result when available.
    """
    ts_data: list[dict[str, Any]] = time_steps or []

    if simulation_result is not None:
        ts_result = simulation_result.get("time_series_result", {})
        fan = ts_result.get("fan_chart")
        if fan:
            ts_data = fan
            granularity = ts_result.get("granularity", granularity)

    if not ts_data:
        return {}

    return {
        "type": "fan_chart",
        "title": title,
        "granularity": granularity,
        "unit": unit,
        "data": ts_data,
        "vega_lite": {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "title": title,
            "data": {"values": ts_data},
            "layer": [
                {
                    "mark": {"type": "area", "opacity": 0.15, "color": "#6366f1"},
                    "encoding": {
                        "x": {"field": "t", "type": "quantitative", "title": granularity},
                        "y": {"field": "p5", "type": "quantitative"},
                        "y2": {"field": "p95"},
                    },
                },
                {
                    "mark": {"type": "area", "opacity": 0.25, "color": "#6366f1"},
                    "encoding": {
                        "x": {"field": "t", "type": "quantitative"},
                        "y": {"field": "p25", "type": "quantitative"},
                        "y2": {"field": "p75"},
                    },
                },
                {
                    "mark": {"type": "line", "color": "#6366f1", "strokeWidth": 2.5},
                    "encoding": {
                        "x": {"field": "t", "type": "quantitative"},
                        "y": {"field": "p50", "type": "quantitative", "title": unit or "Value"},
                        "tooltip": [
                            {"field": "t", "title": granularity},
                            {"field": "p50", "title": "Median", "format": ".3g"},
                            {"field": "p5", "title": "P5", "format": ".3g"},
                            {"field": "p95", "title": "P95", "format": ".3g"},
                        ],
                    },
                },
            ],
        },
    }


# ── Tornado chart ─────────────────────────────────────────────────────────────


def build_tornado_chart(
    sensitivity_data: list[dict[str, Any]] | None = None,
    base_outcome: float = 0.0,
    unit: str = "",
    title: str = "Sensitivity Tornado Chart",
    top_n: int = 10,
    simulation_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a horizontal tornado chart from sensitivity analysis results.

    Phase 6: Uses Mojo-computed sensitivity_analysis.tornado_chart data directly.
    """
    tornado_input: list[dict[str, Any]] = sensitivity_data or []

    if simulation_result is not None:
        sa = simulation_result.get("sensitivity_analysis", {})
        if sa.get("tornado_chart"):
            tornado_input = sa["tornado_chart"]
            base_outcome = sa.get("base_outcome", base_outcome)

    if not tornado_input:
        return {}

    ranked = sorted(tornado_input, key=lambda x: abs(x.get("range", 0)), reverse=True)[:top_n]

    tornado_rows: list[dict[str, Any]] = []
    for row in ranked:
        tornado_rows.append(
            {
                "variable": row["variable"],
                "low": base_outcome + row["low_swing"],
                "high": base_outcome + row["high_swing"],
                "range": abs(row.get("range", 0)),
                "low_swing": row["low_swing"],
                "high_swing": row["high_swing"],
            }
        )

    return {
        "type": "tornado",
        "title": title,
        "unit": unit,
        "base_outcome": base_outcome,
        "data": tornado_rows,
        "vega_lite": {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "title": title,
            "data": {"values": tornado_rows},
            "mark": "bar",
            "encoding": {
                "y": {"field": "variable", "type": "nominal", "sort": "-x", "title": None},
                "x": {
                    "field": "range",
                    "type": "quantitative",
                    "title": unit or "Impact Range",
                },
                "color": {"field": "range", "type": "quantitative", "scale": {"scheme": "blues"}},
                "tooltip": [
                    {"field": "variable", "title": "Variable"},
                    {"field": "low", "format": ".3g", "title": "Low case"},
                    {"field": "high", "format": ".3g", "title": "High case"},
                    {"field": "range", "format": ".3g", "title": "Range"},
                ],
            },
        },
    }


# ── Scatter (EV vs PoL comparison) ───────────────────────────────────────────


def build_comparison_scatter(
    scenarios: list[dict[str, Any]],
    title: str = "Scenario Comparison",
) -> dict[str, Any]:
    """Build an EV vs probability-of-loss scatter for scenario comparison."""
    return {
        "type": "scatter",
        "title": title,
        "data": scenarios,
        "vega_lite": {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "title": title,
            "data": {"values": scenarios},
            "mark": {"type": "point", "filled": True, "size": 100},
            "encoding": {
                "x": {
                    "field": "expected_value",
                    "type": "quantitative",
                    "title": "Expected Value",
                },
                "y": {
                    "field": "probability_of_loss",
                    "type": "quantitative",
                    "title": "Probability of Loss",
                    "axis": {"format": ".1%"},
                    "scale": {"domain": [0, 1]},
                },
                "color": {"field": "score", "type": "quantitative", "scale": {"scheme": "viridis"}},
                "tooltip": [
                    {"field": "name", "title": "Scenario"},
                    {"field": "expected_value", "format": ".3g", "title": "EV"},
                    {"field": "probability_of_loss", "format": ".1%", "title": "PoL"},
                    {"field": "score", "format": ".3f", "title": "Score"},
                ],
            },
        },
    }


# ── Build all charts from DecisionEnvelope ────────────────────────────────────


def build_charts_from_envelope(
    engine_result: dict[str, Any],
    outcomes: list[float] | None = None,
    unit: str = "",
    title: str | None = None,
) -> dict[str, Any]:
    """
    Build all relevant charts from a raw engine result dict.
    Phase 6: passes simulation_result to chart builders so they can use
    Mojo-precomputed histogram_data / cdf_data when present.
    """
    charts: dict[str, Any] = {}
    t = title or "Simulation Results"

    # Histogram — prefer Mojo-precomputed, fall back to outcomes list
    charts["histogram"] = build_histogram(
        outcomes=outcomes, title=t, unit=unit, simulation_result=engine_result
    )
    # CDF
    charts["cdf"] = build_cdf(
        outcomes=outcomes, unit=unit, title=f"{t} — CDF", simulation_result=engine_result
    )

    # Sensitivity tornado — use Mojo-computed data directly
    if "sensitivity_analysis" in engine_result:
        charts["tornado"] = build_tornado_chart(unit=unit, simulation_result=engine_result)

    # Time series fan chart — use Mojo-computed fan_chart directly
    if "time_series_result" in engine_result:
        charts["fan_chart"] = build_fan_chart(unit=unit, simulation_result=engine_result)

    return charts
