# ruff: noqa: E501
from __future__ import annotations

from collections.abc import Callable

from .simulation_template_models import SimulationTemplate, TemplateVariable


def register_catalog(register: Callable[[SimulationTemplate], SimulationTemplate]) -> None:
    # ─────────────────────────────────────────────────────────────────────────────
    # SUPPLY CHAIN / LOGISTICS
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="supply_chain_inventory",
            name="Inventory Optimization & Stockout Risk",
            domain="supply_chain",
            industry="Supply Chain / Logistics",
            description="Demand uncertainty and lead time variability simulation for safety stock calculation and service level optimization.",
            use_case="What safety stock minimizes stockout probability while minimizing holding cost?",
            variables=[
                TemplateVariable("daily_demand", "neg_binomial", {"r": 5.0, "p": 0.4}, "units/day"),
                TemplateVariable("lead_time_days", "lognormal", {"mean": 2.1, "std": 0.4}, "days"),
                TemplateVariable(
                    "demand_variability",
                    "gamma",
                    {"shape": 2, "scale": 5},
                    "units",
                    "Daily demand sigma",
                ),
                TemplateVariable(
                    "holding_cost_rate", "normal", {"mean": 0.25, "std": 0.05}, "fraction/year"
                ),
                TemplateVariable("unit_cost", "normal", {"mean": 45, "std": 8}, "USD"),
                TemplateVariable(
                    "stockout_cost",
                    "lognormal",
                    {"mean": 5.5, "std": 0.5},
                    "USD/unit",
                    "Lost sale + backorder cost",
                ),
                TemplateVariable("reorder_point", "fixed", {"value": 200}, "units"),
                TemplateVariable("order_quantity", "fixed", {"value": 500}, "units"),
            ],
            objective_function="if(daily_demand * lead_time_days > reorder_point, stockout_cost * (daily_demand * lead_time_days - reorder_point), -holding_cost_rate * unit_cost * order_quantity / 2)",
            output_labels=["Inventory Cost ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.4, "downside_risk": 0.6},
            tags=["supply_chain", "inventory", "stockout", "logistics"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # HOSPITALITY / REVENUE MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="hotel_revenue_management",
            name="Hotel RevPAR Optimization",
            domain="hospitality",
            industry="Hospitality / Travel",
            description="Hotel revenue simulation: occupancy rate, ADR, ancillary revenue, and seasonal demand variability.",
            use_case="What is the expected annual RevPAR? Optimal pricing strategy risk analysis.",
            variables=[
                TemplateVariable(
                    "base_occupancy",
                    "beta",
                    {"alpha": 6, "beta": 4},
                    "fraction",
                    "Expected occupancy rate",
                ),
                TemplateVariable(
                    "occupancy_volatility",
                    "normal",
                    {"mean": 0.0, "std": 0.08},
                    "shock",
                    "Random demand shock",
                ),
                TemplateVariable(
                    "adr",
                    "lognormal",
                    {"mean": 5.1, "std": 0.25},
                    "USD/night",
                    "Average Daily Rate",
                ),
                TemplateVariable(
                    "ancillary_revenue",
                    "gamma",
                    {"shape": 2, "scale": 15},
                    "USD/night",
                    "F&B, spa, parking",
                ),
                TemplateVariable("total_rooms", "fixed", {"value": 200}),
                TemplateVariable(
                    "variable_cost_per_occupied", "normal", {"mean": 45, "std": 8}, "USD/night"
                ),
                TemplateVariable(
                    "fixed_cost_per_night", "normal", {"mean": 8000, "std": 500}, "USD/night"
                ),
            ],
            objective_function="total_rooms * (base_occupancy + occupancy_volatility) * (adr + ancillary_revenue - variable_cost_per_occupied) - fixed_cost_per_night",
            output_labels=["Nightly Profit ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["hospitality", "hotel", "revpar", "revenue_management"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # CONSTRUCTION / REAL ESTATE
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="construction_project_cost",
            name="Construction Project Cost & Schedule Risk",
            domain="construction",
            industry="Construction / Real Estate",
            description="Project cost overrun and schedule delay simulation using PERT distributions for work packages.",
            use_case="What is the 80th percentile total cost? Probability of completing on schedule?",
            variables=[
                TemplateVariable(
                    "foundation_cost",
                    "pert",
                    {"low": 800000, "likely": 950000, "high": 1400000},
                    "USD",
                ),
                TemplateVariable(
                    "structural_cost",
                    "pert",
                    {"low": 2000000, "likely": 2400000, "high": 3500000},
                    "USD",
                ),
                TemplateVariable(
                    "mep_cost", "pert", {"low": 1200000, "likely": 1500000, "high": 2200000}, "USD"
                ),
                TemplateVariable(
                    "finishes_cost",
                    "pert",
                    {"low": 600000, "likely": 800000, "high": 1300000},
                    "USD",
                ),
                TemplateVariable(
                    "schedule_delay_weeks", "lognormal", {"mean": 2.0, "std": 0.8}, "weeks"
                ),
                TemplateVariable("weekly_penalty", "fixed", {"value": 50000}, "USD/week"),
                TemplateVariable("contingency_pct", "beta", {"alpha": 3, "beta": 17}, "fraction"),
            ],
            objective_function="foundation_cost + structural_cost + mep_cost + finishes_cost + schedule_delay_weeks * weekly_penalty + (foundation_cost + structural_cost + mep_cost + finishes_cost) * contingency_pct",
            output_labels=["Total Project Cost ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.3, "downside_risk": 0.7},
            tags=["construction", "real_estate", "cost", "schedule", "pert"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # CYBERSECURITY / OPERATIONAL RISK
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="cyber_risk_quantification",
            name="Cyber Risk Financial Impact (FAIR Model)",
            domain="cybersecurity",
            industry="Technology / Insurance",
            description="FAIR-model cyber risk quantification: threat frequency, vulnerability, impact, and controls effectiveness.",
            use_case="What is the annual loss expectancy (ALE) from cyber incidents? VaR for cyber insurance?",
            variables=[
                TemplateVariable(
                    "threat_event_frequency", "lognormal", {"mean": 1.5, "std": 0.8}, "events/year"
                ),
                TemplateVariable(
                    "vulnerability",
                    "beta",
                    {"alpha": 2, "beta": 5},
                    "fraction",
                    "Prob of successful attack given attempt",
                ),
                TemplateVariable(
                    "primary_loss",
                    "lognormal",
                    {"mean": 13.5, "std": 1.0},
                    "USD",
                    "Per-incident primary loss",
                ),
                TemplateVariable(
                    "secondary_loss_factor",
                    "lognormal",
                    {"mean": 0.4, "std": 0.5},
                    "multiplier",
                    "Regulatory/reputation multiplier",
                ),
                TemplateVariable(
                    "control_effectiveness",
                    "beta",
                    {"alpha": 7, "beta": 3},
                    "fraction",
                    "Security control reduction",
                ),
                TemplateVariable(
                    "incident_duration_days", "lognormal", {"mean": 2.3, "std": 0.8}, "days"
                ),
            ],
            objective_function="threat_event_frequency * vulnerability * (1 - control_effectiveness) * primary_loss * (1 + secondary_loss_factor)",
            output_labels=["Annual Loss Expectancy ($)"],
            output_units=["USD/year"],
            scoring={"expected_value": 0.3, "downside_risk": 0.7},
            tags=["cybersecurity", "risk", "fair", "insurance", "operational_risk"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # ENVIRONMENTAL / CLIMATE
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="climate_impact_agriculture",
            name="Agricultural Yield Under Climate Uncertainty",
            domain="environmental",
            industry="Agriculture / Climate Risk",
            description="Crop yield simulation under climate variability: temperature deviation, precipitation, pest pressure.",
            use_case="What is the distribution of annual yield? Revenue at risk from climate scenarios?",
            variables=[
                TemplateVariable(
                    "baseline_yield",
                    "normal",
                    {"mean": 8.5, "std": 0.5},
                    "t/ha",
                    "Baseline crop yield (wheat)",
                ),
                TemplateVariable(
                    "temperature_anomaly",
                    "gumbel",
                    {"mu": 0.8, "beta": 0.4},
                    "°C",
                    "Growing season temperature deviation",
                ),
                TemplateVariable(
                    "precipitation_ratio",
                    "lognormal",
                    {"mean": -0.05, "std": 0.25},
                    "ratio",
                    "Precip vs. historical mean",
                ),
                TemplateVariable(
                    "pest_pressure", "bernoulli", {"p": 0.15}, "binary", "Major pest event"
                ),
                TemplateVariable(
                    "pest_yield_loss",
                    "beta",
                    {"alpha": 2, "beta": 8},
                    "fraction",
                    "Yield loss if pest event",
                ),
                TemplateVariable(
                    "commodity_price", "lognormal", {"mean": 5.3, "std": 0.3}, "USD/t"
                ),
                TemplateVariable("area_ha", "fixed", {"value": 500}, "hectares"),
            ],
            objective_function="area_ha * baseline_yield * (1 - 0.05 * temperature_anomaly) * (1 + 0.3 * precipitation_ratio) * (1 - pest_pressure * pest_yield_loss) * commodity_price",
            output_labels=["Annual Farm Revenue ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.5, "downside_risk": 0.5},
            tags=["agriculture", "climate", "yield", "environmental"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # CUSTOM / GENERIC
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="generic_cost_benefit",
            name="Generic Cost-Benefit Analysis",
            domain="general",
            industry="Any / General",
            description="Universal cost-benefit simulation template. Customize variable names, distributions, and objective for any decision.",
            use_case="Is the expected benefit worth the cost? What is the uncertainty range?",
            variables=[
                TemplateVariable(
                    "benefit",
                    "triangular",
                    {"low": 50000, "mode": 120000, "high": 300000},
                    "USD",
                    "Total expected benefit",
                ),
                TemplateVariable("direct_cost", "lognormal", {"mean": 10.5, "std": 0.4}, "USD"),
                TemplateVariable("indirect_cost", "normal", {"mean": 20000, "std": 5000}, "USD"),
                TemplateVariable(
                    "risk_factor",
                    "beta",
                    {"alpha": 2, "beta": 8},
                    "fraction",
                    "Probability-weighted risk cost",
                ),
                TemplateVariable(
                    "probability_success", "beta", {"alpha": 6, "beta": 4}, "probability"
                ),
            ],
            objective_function="probability_success * benefit - direct_cost - indirect_cost - risk_factor * (direct_cost + indirect_cost)",
            output_labels=["Net Benefit ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["generic", "cost_benefit", "decision_analysis"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # CRYPTO / DIGITAL ASSETS
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="crypto_portfolio_var",
            name="Crypto Portfolio Value at Risk",
            domain="crypto",
            industry="Crypto / Digital Assets",
            description="Daily VaR for a multi-asset crypto portfolio using fat-tailed returns. Models BTC, ETH, and alt-coin correlations.",
            use_case="What is the 95th-percentile daily loss? How much capital buffer do I need?",
            variables=[
                TemplateVariable(
                    "btc_daily_return",
                    "student_t",
                    {"df": 4, "loc": 0.001, "scale": 0.035},
                    "ratio",
                    "BTC daily log return",
                ),
                TemplateVariable(
                    "eth_daily_return",
                    "student_t",
                    {"df": 3, "loc": 0.0012, "scale": 0.045},
                    "ratio",
                    "ETH daily log return",
                ),
                TemplateVariable(
                    "alt_daily_return",
                    "student_t",
                    {"df": 2.5, "loc": 0.0008, "scale": 0.08},
                    "ratio",
                    "Alt-coin daily return",
                ),
                TemplateVariable("btc_weight", "fixed", {"value": 0.50}, "weight"),
                TemplateVariable("eth_weight", "fixed", {"value": 0.30}, "weight"),
                TemplateVariable("alt_weight", "fixed", {"value": 0.20}, "weight"),
                TemplateVariable("portfolio_value", "fixed", {"value": 1000000}, "USD"),
            ],
            objective_function="portfolio_value * (btc_weight * btc_daily_return + eth_weight * eth_daily_return + alt_weight * alt_daily_return)",
            output_labels=["Daily P&L (USD)"],
            output_units=["USD"],
            scoring={"expected_value": 0.35, "downside_risk": 0.65},
            tags=["crypto", "bitcoin", "ethereum", "var", "portfolio"],
        )
    )

    register(
        SimulationTemplate(
            id="crypto_mining_profitability",
            name="Crypto Mining Profitability",
            domain="crypto",
            industry="Crypto / Mining",
            description="Bitcoin mining profitability under hash rate competition, price, difficulty adjustment, and energy cost variability.",
            use_case="Is mining profitable at current electricity costs? Break-even analysis.",
            variables=[
                TemplateVariable(
                    "btc_price", "lognormal", {"mean": 11.0, "std": 0.6}, "USD", "BTC price"
                ),
                TemplateVariable(
                    "hash_rate_th",
                    "normal",
                    {"mean": 200, "std": 30},
                    "TH/s",
                    "Mining rig hash rate",
                ),
                TemplateVariable(
                    "network_difficulty",
                    "lognormal",
                    {"mean": 52.0, "std": 0.2},
                    "T",
                    "Network difficulty",
                ),
                TemplateVariable(
                    "energy_cost_kwh",
                    "triangular",
                    {"low": 0.04, "mode": 0.07, "high": 0.12},
                    "USD/kWh",
                ),
                TemplateVariable(
                    "power_watts",
                    "normal",
                    {"mean": 3200, "std": 100},
                    "W",
                    "Rig power consumption",
                ),
                TemplateVariable("pool_fee", "fixed", {"value": 0.02}, "fraction"),
                TemplateVariable("block_reward", "fixed", {"value": 3.125}, "BTC"),
            ],
            objective_function="(hash_rate_th * 1e12 / (network_difficulty * 1e12 * 232)) * block_reward * btc_price * (1 - pool_fee) - power_watts / 1000 * 24 * energy_cost_kwh",
            output_labels=["Daily Mining Profit (USD)"],
            output_units=["USD/day"],
            scoring={"expected_value": 0.5, "downside_risk": 0.5},
            tags=["crypto", "bitcoin", "mining", "energy", "profitability"],
        )
    )

    register(
        SimulationTemplate(
            id="defi_protocol_tvl_risk",
            name="DeFi Protocol TVL & Liquidation Risk",
            domain="crypto",
            industry="Crypto / DeFi",
            description="Total Value Locked simulation for DeFi lending protocol under collateral price shocks and liquidation cascades.",
            use_case="What is the probability of a liquidation cascade? Protocol solvency under tail scenarios?",
            variables=[
                TemplateVariable(
                    "collateral_price_shock",
                    "student_t",
                    {"df": 3, "loc": -0.05, "scale": 0.12},
                    "ratio",
                    "Collateral value change",
                ),
                TemplateVariable("liquidation_threshold", "fixed", {"value": 0.75}, "LTV ratio"),
                TemplateVariable(
                    "avg_ltv", "beta", {"alpha": 5, "beta": 3}, "ratio", "Average loan-to-value"
                ),
                TemplateVariable(
                    "tvl_usd",
                    "lognormal",
                    {"mean": 20.0, "std": 0.5},
                    "USD M",
                    "Total value locked",
                ),
                TemplateVariable(
                    "protocol_reserve_ratio", "beta", {"alpha": 3, "beta": 47}, "ratio"
                ),
                TemplateVariable(
                    "slippage_factor",
                    "lognormal",
                    {"mean": -2.3, "std": 0.5},
                    "ratio",
                    "Liquidation slippage",
                ),
            ],
            objective_function="tvl_usd * protocol_reserve_ratio - tvl_usd * avg_ltv * max(0, (avg_ltv + collateral_price_shock - liquidation_threshold)) * (1 + slippage_factor)",
            output_labels=["Protocol Excess Reserve ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.3, "downside_risk": 0.7},
            tags=["crypto", "defi", "liquidation", "tvl", "protocol_risk"],
        )
    )
