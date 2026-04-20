from __future__ import annotations

from apps.api_server.services.engine_selector import select_engine


def test_select_engine_prefers_time_series_for_forecast_hint() -> None:
    selection = select_engine(
        variables=[{"name": "monthly_revenue", "distribution": "normal", "params": {}}],
        runs=10_000,
        objective="forecast next quarter",
        mode_hint="forecast",
    )

    assert selection.engine == "time_series"


def test_select_engine_prefers_importance_sampling_for_tail_risk() -> None:
    selection = select_engine(
        variables=[{"name": "portfolio_loss", "distribution": "normal", "params": {}}],
        runs=20_000,
        objective="estimate value_at_risk and extreme_loss",
    )

    assert selection.engine == "importance_sampling"


def test_select_engine_prefers_qmc_sobol_for_large_generic_runs() -> None:
    selection = select_engine(
        variables=[
            {"name": "price", "distribution": "normal", "params": {}},
            {"name": "demand", "distribution": "triangular", "params": {}},
        ],
        runs=75_000,
        objective="maximize expected profit",
    )

    assert selection.engine == "qmc_sobol"
