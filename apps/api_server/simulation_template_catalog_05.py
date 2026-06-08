# ruff: noqa: E501
from __future__ import annotations

from collections.abc import Callable

from .simulation_template_models import SimulationTemplate, TemplateVariable


def register_catalog(register: Callable[[SimulationTemplate], SimulationTemplate]) -> None:
    # ─────────────────────────────────────────────────────────────────────────────
    # LEGAL / LITIGATION
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="litigation_expected_value",
            name="Litigation Expected Value Analysis",
            domain="legal",
            industry="Legal / Dispute Resolution",
            description="Decision tree + Monte Carlo litigation EV analysis: probability of winning, damages, legal costs, and settlement alternatives.",
            use_case="Should we litigate or settle? What is the expected value of going to trial?",
            variables=[
                TemplateVariable("p_win_liability", "beta", {"alpha": 5, "beta": 5}, "probability"),
                TemplateVariable(
                    "p_win_damages_full", "beta", {"alpha": 4, "beta": 6}, "probability"
                ),
                TemplateVariable(
                    "claimed_damages", "lognormal", {"mean": 14.9, "std": 0.5}, "USD M"
                ),
                TemplateVariable(
                    "damages_reduction_factor", "beta", {"alpha": 4, "beta": 6}, "fraction"
                ),
                TemplateVariable(
                    "plaintiff_legal_cost", "lognormal", {"mean": 13.1, "std": 0.5}, "USD M"
                ),
                TemplateVariable(
                    "settlement_offer", "lognormal", {"mean": 13.8, "std": 0.4}, "USD M"
                ),
                TemplateVariable(
                    "trial_duration_years",
                    "triangular",
                    {"low": 1.5, "mode": 3, "high": 5},
                    "years",
                ),
                TemplateVariable("discount_rate", "fixed", {"value": 0.05}, "rate"),
            ],
            objective_function="p_win_liability * (p_win_damages_full * claimed_damages + (1 - p_win_damages_full) * claimed_damages * damages_reduction_factor) * (1 + discount_rate)^(-trial_duration_years) - plaintiff_legal_cost",
            output_labels=["Trial EV ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.5, "downside_risk": 0.5},
            tags=["legal", "litigation", "settlement", "expected_value", "decision_analysis"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # FOOD & BEVERAGE
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="restaurant_profitability",
            name="Restaurant Unit Economics",
            domain="hospitality",
            industry="Food & Beverage / Restaurant",
            description="Restaurant P&L simulation: covers, average check, food cost, labor, and occupancy variability.",
            use_case="What is the expected monthly profit? Prime cost sensitivity analysis.",
            variables=[
                TemplateVariable("seats", "fixed", {"value": 80}),
                TemplateVariable(
                    "daily_turns", "triangular", {"low": 1.5, "mode": 2.2, "high": 3.0}, "turns/day"
                ),
                TemplateVariable(
                    "average_check_usd", "lognormal", {"mean": 3.8, "std": 0.3}, "USD/cover"
                ),
                TemplateVariable(
                    "food_cost_pct", "normal", {"mean": 0.30, "std": 0.03}, "fraction"
                ),
                TemplateVariable(
                    "labor_cost_pct", "normal", {"mean": 0.32, "std": 0.04}, "fraction"
                ),
                TemplateVariable(
                    "monthly_rent", "normal", {"mean": 12000, "std": 2000}, "USD/month"
                ),
                TemplateVariable("other_opex_pct", "beta", {"alpha": 3, "beta": 17}, "fraction"),
                TemplateVariable("days_open_per_month", "fixed", {"value": 26}),
            ],
            objective_function="seats * daily_turns * average_check_usd * days_open_per_month * (1 - food_cost_pct - labor_cost_pct - other_opex_pct) - monthly_rent",
            output_labels=["Monthly Net Profit ($)"],
            output_units=["USD/month"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["restaurant", "food_beverage", "hospitality", "unit_economics"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # QUALITY / SIX SIGMA
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="six_sigma_process_capability",
            name="Process Capability & Defect Rate (Cpk)",
            domain="manufacturing",
            industry="Manufacturing / Quality",
            description="Process capability simulation: natural process variation, spec limits, and Cpk under measurement uncertainty.",
            use_case="What is our expected Cpk? Probability of exceeding defect budget?",
            variables=[
                TemplateVariable(
                    "process_mean",
                    "normal",
                    {"mean": 0.0, "std": 0.5},
                    "mm",
                    "Process mean deviation from target",
                ),
                TemplateVariable(
                    "process_std",
                    "lognormal",
                    {"mean": -1.6, "std": 0.2},
                    "mm",
                    "Within-subgroup sigma",
                ),
                TemplateVariable("usl", "fixed", {"value": 3.0}, "mm", "Upper spec limit"),
                TemplateVariable("lsl", "fixed", {"value": -3.0}, "mm", "Lower spec limit"),
                TemplateVariable(
                    "measurement_error_std",
                    "halfnormal",
                    {"sigma": 0.1},
                    "mm",
                    "Gauge R&R contribution",
                ),
                TemplateVariable(
                    "shift_factor",
                    "normal",
                    {"mean": 1.5, "std": 0.3},
                    "sigma",
                    "Long-term process shift",
                ),
            ],
            objective_function="min((usl - process_mean) / (3 * (process_std + measurement_error_std)), (process_mean - lsl) / (3 * (process_std + measurement_error_std))) - shift_factor / 3",
            output_labels=["Process Cpk"],
            output_units=["cpk"],
            scoring={"expected_value": 0.7, "downside_risk": 0.3},
            tags=["quality", "six_sigma", "cpk", "manufacturing", "process"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # INSURANCE — ADDITIONAL
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="cat_bond_expected_loss",
            name="Catastrophe Bond Expected Loss",
            domain="finance",
            industry="Insurance / Catastrophe Risk",
            description="Cat bond expected annual loss simulation: natural catastrophe frequency, severity, and reinsurance attachment.",
            use_case="What is the EL for our cat bond? Risk-adjusted return vs. spread?",
            variables=[
                TemplateVariable("annual_cat_frequency", "poisson", {"lambda": 0.3}, "events/year"),
                TemplateVariable(
                    "event_severity_usd_B", "lognormal", {"mean": 2.3, "std": 0.8}, "USD B"
                ),
                TemplateVariable("attachment_point_usd_B", "fixed", {"value": 5.0}, "USD B"),
                TemplateVariable("exhaustion_point_usd_B", "fixed", {"value": 8.0}, "USD B"),
                TemplateVariable("bond_notional_usd_M", "fixed", {"value": 300}, "USD M"),
                TemplateVariable("coupon_spread_bps", "fixed", {"value": 450}, "bps"),
            ],
            objective_function="bond_notional_usd_M * coupon_spread_bps / 10000 - annual_cat_frequency * bond_notional_usd_M * max(0, min(event_severity_usd_B - attachment_point_usd_B, exhaustion_point_usd_B - attachment_point_usd_B)) / (exhaustion_point_usd_B - attachment_point_usd_B)",
            output_labels=["Annual Net Return ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.5, "downside_risk": 0.5},
            tags=["insurance", "cat_bond", "reinsurance", "catastrophe", "structured"],
        )
    )

    register(
        SimulationTemplate(
            id="life_insurance_mortality",
            name="Life Insurance Mortality Risk",
            domain="finance",
            industry="Insurance / Life",
            description="Life insurer mortality rate simulation: pandemic shock, longevity trend, and claims reserve adequacy.",
            use_case="What mortality rate stress tests our reserve? P99 claims in adverse scenario?",
            variables=[
                TemplateVariable(
                    "base_mortality_rate",
                    "beta",
                    {"alpha": 2, "beta": 1998},
                    "fraction",
                    "Annual qx per policy",
                ),
                TemplateVariable(
                    "mortality_multiplier",
                    "lognormal",
                    {"mean": 0.0, "std": 0.3},
                    "factor",
                    "Stress/improvement factor",
                ),
                TemplateVariable("n_policies", "fixed", {"value": 100000}),
                TemplateVariable("avg_sum_assured", "lognormal", {"mean": 11.5, "std": 0.5}, "USD"),
                TemplateVariable("premium_rate", "beta", {"alpha": 3, "beta": 47}, "fraction"),
                TemplateVariable("expense_ratio", "beta", {"alpha": 3, "beta": 27}, "fraction"),
            ],
            objective_function="n_policies * avg_sum_assured * premium_rate * (1 - expense_ratio) - n_policies * avg_sum_assured * base_mortality_rate * exp(mortality_multiplier)",
            output_labels=["Annual Underwriting Profit ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.4, "downside_risk": 0.6},
            tags=["insurance", "life", "mortality", "longevity", "actuarial"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # SPORTS ANALYTICS
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="sports_player_contract_value",
            name="Sports Player Contract Value-Over-Replacement",
            domain="sports",
            industry="Sports Analytics",
            description="Player contract ROI simulation: projected WAR/WAA, market rate per win, injury probability, and performance decline.",
            use_case="Is this contract justified? Expected surplus value over contract term?",
            variables=[
                TemplateVariable("projected_war_yr1", "normal", {"mean": 4.0, "std": 1.5}, "WAR"),
                TemplateVariable(
                    "war_decline_rate", "normal", {"mean": 0.15, "std": 0.08}, "rate/year"
                ),
                TemplateVariable(
                    "injury_probability_annual", "beta", {"alpha": 2, "beta": 8}, "fraction"
                ),
                TemplateVariable("injury_war_impact", "beta", {"alpha": 3, "beta": 7}, "fraction"),
                TemplateVariable(
                    "market_rate_per_war", "normal", {"mean": 8e6, "std": 1e6}, "USD/WAR"
                ),
                TemplateVariable("contract_value_per_year", "fixed", {"value": 25e6}, "USD"),
                TemplateVariable("contract_years", "fixed", {"value": 5}, "years"),
            ],
            objective_function="sum([projected_war_yr1 * (1 - war_decline_rate)^i * (1 - injury_probability_annual * injury_war_impact) * market_rate_per_war - contract_value_per_year for i in range(int(contract_years))])",
            output_labels=["Total Contract Surplus ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["sports", "analytics", "contract", "war", "performance"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # PROCUREMENT / SOURCING
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="procurement_supplier_risk",
            name="Supplier Concentration & Disruption Cost",
            domain="supply_chain",
            industry="Procurement / Sourcing",
            description="Supply disruption cost simulation: probability of supplier failure, lead time extension, and dual-sourcing premium trade-off.",
            use_case="How much should I pay for a second supplier? Expected cost of supply disruption?",
            variables=[
                TemplateVariable("annual_spend_with_supplier", "fixed", {"value": 10e6}, "USD"),
                TemplateVariable(
                    "disruption_probability", "beta", {"alpha": 1, "beta": 24}, "fraction"
                ),
                TemplateVariable(
                    "disruption_duration_weeks", "lognormal", {"mean": 2.0, "std": 0.6}, "weeks"
                ),
                TemplateVariable(
                    "weekly_production_loss", "normal", {"mean": 500000, "std": 100000}, "USD/week"
                ),
                TemplateVariable(
                    "expediting_cost_factor",
                    "triangular",
                    {"low": 1.1, "mode": 1.25, "high": 1.5},
                    "factor",
                ),
                TemplateVariable(
                    "dual_source_premium",
                    "beta",
                    {"alpha": 3, "beta": 47},
                    "fraction",
                    "% premium for second source",
                ),
                TemplateVariable(
                    "safety_stock_holding_cost", "normal", {"mean": 50000, "std": 10000}, "USD/year"
                ),
            ],
            objective_function="disruption_probability * (disruption_duration_weeks * weekly_production_loss + annual_spend_with_supplier * (expediting_cost_factor - 1)) - annual_spend_with_supplier * dual_source_premium - safety_stock_holding_cost",
            output_labels=["Expected Annual Disruption Cost ($)"],
            output_units=["USD/year"],
            scoring={"expected_value": 0.3, "downside_risk": 0.7},
            tags=["procurement", "supplier", "disruption", "supply_chain", "risk"],
        )
    )
