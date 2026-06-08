# ruff: noqa: E501
from __future__ import annotations

from collections.abc import Callable

from .simulation_template_models import SimulationTemplate, TemplateVariable


def register_catalog(register: Callable[[SimulationTemplate], SimulationTemplate]) -> None:
    # TRANSPORTATION / LOGISTICS
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="airline_route_profitability",
            name="Airline Route Profitability",
            domain="transportation",
            industry="Transportation / Aviation",
            description="Airline route P&L simulation: load factor, yield, fuel price, and passenger demand variability.",
            use_case="Is this route profitable at current fuel prices? Revenue risk from demand shock?",
            variables=[
                TemplateVariable("load_factor", "beta", {"alpha": 7, "beta": 3}, "fraction"),
                TemplateVariable(
                    "revenue_per_pax",
                    "lognormal",
                    {"mean": 5.5, "std": 0.3},
                    "USD",
                    "Average ticket yield",
                ),
                TemplateVariable("aircraft_seats", "fixed", {"value": 180}),
                TemplateVariable("daily_frequency", "fixed", {"value": 2}),
                TemplateVariable(
                    "fuel_price_per_gallon", "lognormal", {"mean": 2.2, "std": 0.25}, "USD/gallon"
                ),
                TemplateVariable(
                    "fuel_burn_gallons_per_flight", "normal", {"mean": 4500, "std": 300}, "gallons"
                ),
                TemplateVariable(
                    "fixed_cost_per_flight",
                    "normal",
                    {"mean": 18000, "std": 2000},
                    "USD",
                    "Crew, airport, landing",
                ),
                TemplateVariable("variable_cost_per_pax", "normal", {"mean": 45, "std": 8}, "USD"),
            ],
            objective_function="aircraft_seats * load_factor * daily_frequency * (revenue_per_pax - variable_cost_per_pax) - daily_frequency * (fuel_price_per_gallon * fuel_burn_gallons_per_flight + fixed_cost_per_flight)",
            output_labels=["Daily Route Profit ($)"],
            output_units=["USD/day"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["airline", "aviation", "route", "fuel", "load_factor"],
        )
    )

    register(
        SimulationTemplate(
            id="shipping_freight_rate",
            name="Container Shipping Freight Rate P&L",
            domain="transportation",
            industry="Transportation / Shipping",
            description="Vessel voyage profitability under spot rate, bunker fuel, port costs, and utilization variability.",
            use_case="What is the TCE for this voyage? Break-even bunker price?",
            variables=[
                TemplateVariable(
                    "spot_freight_rate_per_teu", "lognormal", {"mean": 7.0, "std": 0.5}, "USD/TEU"
                ),
                TemplateVariable("vessel_capacity_teu", "fixed", {"value": 8000}),
                TemplateVariable("utilization_rate", "beta", {"alpha": 7, "beta": 3}, "fraction"),
                TemplateVariable("voyage_days", "normal", {"mean": 28, "std": 3}, "days"),
                TemplateVariable(
                    "bunker_price_per_mt", "lognormal", {"mean": 6.2, "std": 0.3}, "USD/MT"
                ),
                TemplateVariable(
                    "fuel_consumption_mt_per_day", "normal", {"mean": 120, "std": 15}, "MT/day"
                ),
                TemplateVariable(
                    "port_costs_per_voyage", "normal", {"mean": 150000, "std": 25000}, "USD"
                ),
            ],
            objective_function="spot_freight_rate_per_teu * vessel_capacity_teu * utilization_rate - voyage_days * bunker_price_per_mt * fuel_consumption_mt_per_day - port_costs_per_voyage",
            output_labels=["Voyage P&L ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["shipping", "freight", "bunker", "voyage", "maritime"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # MINING / NATURAL RESOURCES
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="mining_project_npv",
            name="Mining Project Feasibility & NPV",
            domain="mining",
            industry="Mining / Natural Resources",
            description="Open-pit mine NPV simulation: ore grade uncertainty, commodity price, strip ratio, and operating cost variability.",
            use_case="What is the P50 NPV? What commodity price makes the project marginal?",
            variables=[
                TemplateVariable(
                    "ore_grade_g_t",
                    "lognormal",
                    {"mean": 0.7, "std": 0.4},
                    "g/t",
                    "Gold grade (g/t)",
                ),
                TemplateVariable(
                    "ore_tonnes_Mt",
                    "lognormal",
                    {"mean": 2.3, "std": 0.3},
                    "Mt",
                    "Total mineable ore",
                ),
                TemplateVariable(
                    "gold_price_usd_oz", "lognormal", {"mean": 7.5, "std": 0.2}, "USD/oz"
                ),
                TemplateVariable("recovery_rate", "beta", {"alpha": 8, "beta": 2}, "fraction"),
                TemplateVariable(
                    "aisc_per_oz",
                    "normal",
                    {"mean": 1100, "std": 150},
                    "USD/oz",
                    "All-in sustaining cost",
                ),
                TemplateVariable(
                    "strip_ratio", "lognormal", {"mean": 1.6, "std": 0.3}, "waste:ore"
                ),
                TemplateVariable("discount_rate", "normal", {"mean": 0.08, "std": 0.015}, "rate"),
                TemplateVariable(
                    "mine_life_years", "triangular", {"low": 8, "mode": 12, "high": 18}, "years"
                ),
            ],
            objective_function="ore_tonnes_Mt * 1e6 * ore_grade_g_t / 31.1035 * recovery_rate * (gold_price_usd_oz - aisc_per_oz) / discount_rate * (1 - (1 + discount_rate)^(-mine_life_years))",
            output_labels=["Project NPV ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["mining", "gold", "npv", "resources", "feasibility"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # ESG / CARBON / SUSTAINABILITY
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="carbon_offset_valuation",
            name="Carbon Offset Project Valuation",
            domain="environmental",
            industry="ESG / Carbon Markets",
            description="Voluntary carbon market project NPV: credit issuance uncertainty, price, additionality risk, and permanence.",
            use_case="What is the expected NPV of our reforestation project? Carbon price sensitivity?",
            variables=[
                TemplateVariable("area_hectares", "fixed", {"value": 10000}),
                TemplateVariable(
                    "carbon_sequestration_t_ha_yr",
                    "lognormal",
                    {"mean": 2.0, "std": 0.5},
                    "tCO2e/ha/yr",
                ),
                TemplateVariable(
                    "carbon_price_usd_t", "lognormal", {"mean": 3.5, "std": 0.5}, "USD/tCO2e"
                ),
                TemplateVariable(
                    "additionality_buffer",
                    "beta",
                    {"alpha": 3, "beta": 7},
                    "fraction",
                    "Buffer pool deduction",
                ),
                TemplateVariable("project_life_years", "fixed", {"value": 30}),
                TemplateVariable("opex_per_ha_yr", "normal", {"mean": 80, "std": 20}, "USD/ha/yr"),
                TemplateVariable("leakage_rate", "beta", {"alpha": 1.5, "beta": 18.5}, "fraction"),
                TemplateVariable("discount_rate", "normal", {"mean": 0.08, "std": 0.01}, "rate"),
            ],
            objective_function="area_hectares * carbon_sequestration_t_ha_yr * (1 - additionality_buffer) * (1 - leakage_rate) * carbon_price_usd_t / discount_rate * (1 - (1 + discount_rate)^(-project_life_years)) - area_hectares * opex_per_ha_yr / discount_rate",
            output_labels=["Project NPV ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["esg", "carbon", "offset", "reforestation", "sustainability"],
        )
    )

    register(
        SimulationTemplate(
            id="renewable_solar_lcoe",
            name="Solar PV Levelized Cost of Energy (LCOE)",
            domain="energy",
            industry="Energy / Solar",
            description="Utility-scale solar project LCOE simulation under capacity factor, CAPEX, OPEX, and degradation uncertainty.",
            use_case="What is our P50 LCOE? Is this project competitive with grid parity?",
            variables=[
                TemplateVariable(
                    "capex_per_mw",
                    "lognormal",
                    {"mean": 13.7, "std": 0.2},
                    "USD/W",
                    "All-in solar CAPEX",
                ),
                TemplateVariable("capacity_mw", "fixed", {"value": 100}),
                TemplateVariable("capacity_factor", "beta", {"alpha": 6, "beta": 4}, "fraction"),
                TemplateVariable(
                    "annual_degradation_rate", "normal", {"mean": 0.005, "std": 0.001}, "rate/year"
                ),
                TemplateVariable(
                    "opex_per_mw_yr", "normal", {"mean": 15000, "std": 2500}, "USD/MW/yr"
                ),
                TemplateVariable("discount_rate", "normal", {"mean": 0.06, "std": 0.01}, "rate"),
                TemplateVariable("project_life_years", "fixed", {"value": 25}),
            ],
            objective_function="(capex_per_mw * 1000 * capacity_mw + opex_per_mw_yr * capacity_mw / discount_rate) / (capacity_mw * 8760 * capacity_factor / discount_rate * (1 - (1 + discount_rate)^(-project_life_years)))",
            output_labels=["LCOE (USD/MWh)"],
            output_units=["USD/MWh"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["solar", "energy", "lcoe", "renewable", "pv"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # BIOTECH / LIFE SCIENCES
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="biotech_clinical_stage_valuation",
            name="Biotech Company rNPV Valuation",
            domain="biotech",
            industry="Biotech / Life Sciences",
            description="Risk-adjusted NPV of a biotech pipeline using probability of technical success at each clinical stage and peak sales uncertainty.",
            use_case="What is the fair value of this biotech? Sensitivity to peak sales and PoS assumptions.",
            variables=[
                TemplateVariable(
                    "p_phase2_success", "beta", {"alpha": 4, "beta": 6}, "probability"
                ),
                TemplateVariable(
                    "p_phase3_success", "beta", {"alpha": 5, "beta": 5}, "probability"
                ),
                TemplateVariable(
                    "p_regulatory_success", "beta", {"alpha": 8, "beta": 2}, "probability"
                ),
                TemplateVariable(
                    "peak_sales_usd_M", "lognormal", {"mean": 6.9, "std": 0.8}, "USD M/yr"
                ),
                TemplateVariable("royalty_rate", "beta", {"alpha": 3, "beta": 17}, "fraction"),
                TemplateVariable("years_to_market", "normal", {"mean": 6, "std": 1.5}, "years"),
                TemplateVariable(
                    "patent_remaining_years",
                    "triangular",
                    {"low": 6, "mode": 10, "high": 14},
                    "years",
                ),
                TemplateVariable(
                    "phase2_cost_usd_M", "lognormal", {"mean": 3.9, "std": 0.5}, "USD M"
                ),
                TemplateVariable(
                    "phase3_cost_usd_M", "lognormal", {"mean": 5.3, "std": 0.6}, "USD M"
                ),
                TemplateVariable("discount_rate", "normal", {"mean": 0.12, "std": 0.02}, "rate"),
            ],
            objective_function="p_phase2_success * p_phase3_success * p_regulatory_success * peak_sales_usd_M * royalty_rate / discount_rate * (1 - (1 + discount_rate)^(-patent_remaining_years)) / (1 + discount_rate)^years_to_market - phase2_cost_usd_M - p_phase2_success * phase3_cost_usd_M",
            output_labels=["rNPV ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["biotech", "rnpv", "clinical", "pipeline", "valuation"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # TELECOM
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="telecom_5g_roi",
            name="5G Network Deployment ROI",
            domain="telecom",
            industry="Telecom / Networks",
            description="5G capex investment return simulation: spectrum cost, equipment, subscriber adoption, and ARPU evolution.",
            use_case="What is the payback period for 5G rollout? IRR sensitivity to adoption speed.",
            variables=[
                TemplateVariable(
                    "spectrum_cost_usd_M", "lognormal", {"mean": 6.5, "std": 0.4}, "USD M"
                ),
                TemplateVariable(
                    "equipment_cost_per_site", "normal", {"mean": 250000, "std": 30000}, "USD"
                ),
                TemplateVariable("n_sites", "fixed", {"value": 5000}),
                TemplateVariable(
                    "subscriber_adoption_yr1", "beta", {"alpha": 3, "beta": 17}, "fraction"
                ),
                TemplateVariable("total_subscribers_M", "fixed", {"value": 20}),
                TemplateVariable(
                    "arpu_premium_usd",
                    "normal",
                    {"mean": 8, "std": 2},
                    "USD/month",
                    "5G ARPU premium",
                ),
                TemplateVariable(
                    "opex_per_site_yr", "normal", {"mean": 20000, "std": 3000}, "USD/site/yr"
                ),
                TemplateVariable("hold_years", "fixed", {"value": 10}),
            ],
            objective_function="total_subscribers_M * 1e6 * subscriber_adoption_yr1 * arpu_premium_usd * 12 * hold_years - spectrum_cost_usd_M * 1e6 - equipment_cost_per_site * n_sites - opex_per_site_yr * n_sites * hold_years",
            output_labels=["10-Year Net Value ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["telecom", "5g", "network", "capex", "roi"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # HUMAN CAPITAL / WORKFORCE
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="workforce_attrition_cost",
            name="Employee Attrition Cost & Retention ROI",
            domain="hr",
            industry="Human Resources / Workforce",
            description="Annual workforce attrition cost simulation: replacement cost, productivity loss, and retention program ROI.",
            use_case="What is our total cost of attrition? ROI of retention investment?",
            variables=[
                TemplateVariable("total_headcount", "fixed", {"value": 500}),
                TemplateVariable(
                    "annual_attrition_rate", "beta", {"alpha": 3, "beta": 17}, "fraction"
                ),
                TemplateVariable(
                    "avg_annual_salary", "lognormal", {"mean": 11.2, "std": 0.4}, "USD"
                ),
                TemplateVariable(
                    "replacement_cost_multiple",
                    "triangular",
                    {"low": 0.5, "mode": 1.0, "high": 2.0},
                    "multiple",
                    "Replacement as % of salary",
                ),
                TemplateVariable(
                    "productivity_loss_months",
                    "triangular",
                    {"low": 2, "mode": 4, "high": 8},
                    "months",
                ),
                TemplateVariable(
                    "retention_program_cost_per_employee",
                    "normal",
                    {"mean": 2000, "std": 500},
                    "USD/yr",
                ),
                TemplateVariable(
                    "retention_effectiveness",
                    "beta",
                    {"alpha": 4, "beta": 6},
                    "fraction",
                    "% reduction in attrition",
                ),
            ],
            objective_function="total_headcount * annual_attrition_rate * avg_annual_salary * (replacement_cost_multiple + productivity_loss_months / 12) - total_headcount * retention_program_cost_per_employee + total_headcount * annual_attrition_rate * retention_effectiveness * avg_annual_salary * replacement_cost_multiple",
            output_labels=["Net Attrition Cost ($)"],
            output_units=["USD/year"],
            scoring={"expected_value": 0.4, "downside_risk": 0.6},
            tags=["hr", "workforce", "attrition", "retention", "human_capital"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # M&A / TRANSACTION
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="ma_synergy_valuation",
            name="M&A Synergy Realization & Deal Value",
            domain="finance",
            industry="M&A / Corporate Finance",
            description="M&A deal value simulation: revenue synergies, cost synergies, integration costs, and realization timing uncertainty.",
            use_case="What is the probability this deal creates value? Synergy risk sensitivity?",
            variables=[
                TemplateVariable("deal_enterprise_value", "fixed", {"value": 500e6}, "USD"),
                TemplateVariable("target_ebitda", "normal", {"mean": 50e6, "std": 5e6}, "USD"),
                TemplateVariable(
                    "revenue_synergy_usd_M", "lognormal", {"mean": 3.0, "std": 0.8}, "USD M/yr"
                ),
                TemplateVariable(
                    "cost_synergy_usd_M", "lognormal", {"mean": 2.5, "std": 0.6}, "USD M/yr"
                ),
                TemplateVariable(
                    "synergy_realization_pct", "beta", {"alpha": 6, "beta": 4}, "fraction"
                ),
                TemplateVariable(
                    "integration_cost_usd_M", "lognormal", {"mean": 2.3, "std": 0.5}, "USD M"
                ),
                TemplateVariable(
                    "synergy_timeline_years",
                    "triangular",
                    {"low": 2, "mode": 3, "high": 5},
                    "years",
                ),
                TemplateVariable("discount_rate", "normal", {"mean": 0.10, "std": 0.015}, "rate"),
            ],
            objective_function="(revenue_synergy_usd_M + cost_synergy_usd_M) * 1e6 * synergy_realization_pct / discount_rate * (1 - (1 + discount_rate)^(-10)) / (1 + discount_rate)^synergy_timeline_years - integration_cost_usd_M * 1e6 - deal_enterprise_value + target_ebitda * 10",
            output_labels=["Deal Value Creation ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["ma", "synergy", "acquisition", "corporate_finance", "valuation"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # GAMING / MEDIA
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="video_game_launch_revenue",
            name="Video Game Launch Revenue Forecast",
            domain="media",
            industry="Gaming / Entertainment",
            description="Game launch revenue simulation: unit sales, pricing, DLC/microtransaction revenue, and marketing efficiency.",
            use_case="What is the expected launch window revenue? Probability of recovering development costs?",
            variables=[
                TemplateVariable(
                    "launch_units_sold",
                    "lognormal",
                    {"mean": 13.1, "std": 0.8},
                    "units",
                    "First-year units",
                ),
                TemplateVariable("avg_selling_price", "normal", {"mean": 55, "std": 8}, "USD"),
                TemplateVariable(
                    "platform_rev_share", "normal", {"mean": 0.30, "std": 0.02}, "fraction"
                ),
                TemplateVariable("dlc_attach_rate", "beta", {"alpha": 3, "beta": 7}, "fraction"),
                TemplateVariable("dlc_avg_revenue", "normal", {"mean": 25, "std": 5}, "USD/buyer"),
                TemplateVariable(
                    "marketing_cost_usd_M", "lognormal", {"mean": 3.2, "std": 0.5}, "USD M"
                ),
                TemplateVariable("dev_cost_usd_M", "fixed", {"value": 80}, "USD M"),
            ],
            objective_function="launch_units_sold * avg_selling_price * (1 - platform_rev_share) + launch_units_sold * dlc_attach_rate * dlc_avg_revenue * (1 - platform_rev_share) - marketing_cost_usd_M * 1e6 - dev_cost_usd_M * 1e6",
            output_labels=["Launch Net Profit ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["gaming", "entertainment", "launch", "revenue", "media"],
        )
    )

    register(
        SimulationTemplate(
            id="streaming_content_roi",
            name="Streaming Platform Content ROI",
            domain="media",
            industry="Media / Streaming",
            description="Original content investment ROI for streaming platform: subscriber acquisition, retention lift, and content cost.",
            use_case="What subscriber lift do we need to justify this content investment?",
            variables=[
                TemplateVariable(
                    "content_cost_usd_M", "lognormal", {"mean": 3.0, "std": 0.6}, "USD M"
                ),
                TemplateVariable(
                    "new_subscriber_lift", "poisson", {"lambda": 50000}, "subscribers"
                ),
                TemplateVariable(
                    "retention_improvement_pct", "beta", {"alpha": 2, "beta": 48}, "fraction"
                ),
                TemplateVariable("current_subscribers_M", "fixed", {"value": 5}),
                TemplateVariable("monthly_arpu", "normal", {"mean": 14, "std": 2}, "USD/month"),
                TemplateVariable(
                    "avg_retention_months",
                    "lognormal",
                    {"mean": 3.0, "std": 0.4},
                    "months",
                    "Incremental retention",
                ),
                TemplateVariable("content_depreciation_years", "fixed", {"value": 3}),
            ],
            objective_function="new_subscriber_lift * monthly_arpu * avg_retention_months + current_subscribers_M * 1e6 * retention_improvement_pct * monthly_arpu * 12 - content_cost_usd_M * 1e6",
            output_labels=["Content ROI ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["streaming", "media", "content", "subscriber", "roi"],
        )
    )
