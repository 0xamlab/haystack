# ruff: noqa: E501
from __future__ import annotations

from collections.abc import Callable

from .simulation_template_models import SimulationTemplate, TemplateVariable


def register_catalog(register: Callable[[SimulationTemplate], SimulationTemplate]) -> None:
    # ─────────────────────────────────────────────────────────────────────────────
    # FINANCE
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="finance_npv",
            name="Project NPV Analysis",
            domain="finance",
            industry="Finance / Corporate",
            description="Net Present Value simulation for capital investment decisions. Models uncertain revenue, costs, discount rate, and project life.",
            use_case="Should we invest in this project? What is the probability of positive NPV?",
            variables=[
                TemplateVariable(
                    "initial_investment",
                    "fixed",
                    {"value": 1000000},
                    "USD",
                    "Upfront capital expenditure",
                ),
                TemplateVariable(
                    "annual_revenue",
                    "lognormal",
                    {"mean": 13.5, "std": 0.35},
                    "USD/year",
                    "Annual revenue projection",
                ),
                TemplateVariable(
                    "operating_costs",
                    "triangular",
                    {"low": 200000, "mode": 350000, "high": 600000},
                    "USD/year",
                ),
                TemplateVariable(
                    "discount_rate",
                    "normal",
                    {"mean": 0.10, "std": 0.02},
                    "rate",
                    "WACC / hurdle rate",
                ),
                TemplateVariable(
                    "project_life",
                    "discrete",
                    {"values": [5, 7, 10, 15], "probabilities": [0.1, 0.3, 0.4, 0.2]},
                    "years",
                ),
                TemplateVariable("terminal_growth", "normal", {"mean": 0.02, "std": 0.01}, "rate"),
            ],
            objective_function="(annual_revenue - operating_costs) / discount_rate * (1 - (1 + discount_rate)^(-project_life)) - initial_investment",
            output_labels=["NPV"],
            output_units=["USD"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["finance", "investment", "npv", "capital"],
        )
    )

    register(
        SimulationTemplate(
            id="finance_portfolio",
            name="Portfolio Value at Risk",
            domain="finance",
            industry="Finance / Asset Management",
            description="Daily portfolio P&L simulation with correlated asset returns. Computes VaR and CVaR.",
            use_case="What is the 95th-percentile daily loss? How correlated are my positions?",
            variables=[
                TemplateVariable(
                    "equity_return",
                    "normal",
                    {"mean": 0.0005, "std": 0.012},
                    "%/day",
                    "Equity portfolio daily return",
                ),
                TemplateVariable(
                    "bond_return",
                    "normal",
                    {"mean": 0.0001, "std": 0.003},
                    "%/day",
                    "Fixed income daily return",
                ),
                TemplateVariable(
                    "commodity_return",
                    "normal",
                    {"mean": 0.0002, "std": 0.018},
                    "%/day",
                    "Commodity daily return",
                ),
                TemplateVariable("equity_weight", "fixed", {"value": 0.60}, "weight"),
                TemplateVariable("bond_weight", "fixed", {"value": 0.30}, "weight"),
                TemplateVariable("commodity_weight", "fixed", {"value": 0.10}, "weight"),
                TemplateVariable("portfolio_value", "fixed", {"value": 10000000}, "USD"),
            ],
            objective_function="portfolio_value * (equity_weight * equity_return + bond_weight * bond_return + commodity_weight * commodity_return)",
            output_labels=["Daily P&L"],
            output_units=["USD"],
            scoring={"expected_value": 0.4, "downside_risk": 0.6},
            tags=["finance", "var", "portfolio", "risk"],
        )
    )

    register(
        SimulationTemplate(
            id="insurance_claims",
            name="Insurance Claims Reserve",
            domain="finance",
            industry="Insurance / Actuarial",
            description="Claims frequency × severity model for insurance reserving. Uses negative binomial for claim count and lognormal for claim size.",
            use_case="How much reserve should we hold? What is the 99th percentile total claims?",
            variables=[
                TemplateVariable(
                    "claim_frequency",
                    "neg_binomial",
                    {"r": 5.0, "p": 0.4},
                    "claims/year",
                    "Annual claim count",
                ),
                TemplateVariable(
                    "claim_severity",
                    "lognormal",
                    {"mean": 10.5, "std": 0.8},
                    "USD",
                    "Individual claim amount",
                ),
                TemplateVariable(
                    "expense_ratio",
                    "beta",
                    {"alpha": 4, "beta": 16},
                    "ratio",
                    "Operating expense ratio",
                ),
                TemplateVariable("earned_premium", "fixed", {"value": 5000000}, "USD"),
                TemplateVariable(
                    "reinsurance_retention",
                    "fixed",
                    {"value": 500000},
                    "USD",
                    "Per-occurrence retention",
                ),
            ],
            objective_function="earned_premium * (1 - expense_ratio) - min(claim_frequency * claim_severity, reinsurance_retention * 20)",
            output_labels=["Underwriting Profit"],
            output_units=["USD"],
            scoring={"expected_value": 0.5, "downside_risk": 0.5},
            tags=["insurance", "actuarial", "claims", "reserving"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # MEDICAL / CLINICAL / PHARMA
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="clinical_trial_power",
            name="Clinical Trial Power Analysis",
            domain="medical",
            industry="Medical / Pharmaceutical",
            description="Simulates trial outcome uncertainty: true treatment effect, measurement noise, dropout rate, and sample size effects.",
            use_case="What is our probability of detecting a significant treatment effect at given sample size?",
            variables=[
                TemplateVariable(
                    "true_effect",
                    "normal",
                    {"mean": 0.15, "std": 0.05},
                    "relative reduction",
                    "True treatment effect size",
                ),
                TemplateVariable(
                    "measurement_noise",
                    "halfnormal",
                    {"sigma": 0.03},
                    "SD",
                    "Measurement variability",
                ),
                TemplateVariable(
                    "placebo_response",
                    "beta",
                    {"alpha": 2, "beta": 8},
                    "rate",
                    "Placebo responder rate",
                ),
                TemplateVariable(
                    "dropout_rate",
                    "beta",
                    {"alpha": 1.5, "beta": 18.5},
                    "rate",
                    "Patient dropout rate",
                ),
                TemplateVariable(
                    "sample_size", "poisson", {"lambda": 300}, "patients", "Patients per arm"
                ),
                TemplateVariable("alpha_threshold", "fixed", {"value": 0.05}, "p-value"),
            ],
            objective_function="(true_effect - measurement_noise) * (1 - dropout_rate) * sqrt(sample_size) - placebo_response",
            output_labels=["Standardized Treatment Effect"],
            output_units=["z-score"],
            scoring={"expected_value": 0.7, "downside_risk": 0.3},
            tags=["medical", "clinical", "pharma", "trial", "power"],
        )
    )

    register(
        SimulationTemplate(
            id="hospital_capacity",
            name="Hospital Capacity & Bed Occupancy",
            domain="medical",
            industry="Healthcare / Operations",
            description="ICU/ward capacity simulation: patient arrivals, length-of-stay, and discharge rates.",
            use_case="What is the probability of ICU overflow? Optimal bed count for 95% service level?",
            variables=[
                TemplateVariable("daily_admissions", "poisson", {"lambda": 12}, "patients/day"),
                TemplateVariable(
                    "icu_los", "lognormal", {"mean": 1.8, "std": 0.6}, "days", "ICU length of stay"
                ),
                TemplateVariable(
                    "ward_los", "gamma", {"shape": 2.5, "scale": 2.0}, "days", "General ward LOS"
                ),
                TemplateVariable(
                    "icu_fraction",
                    "beta",
                    {"alpha": 2, "beta": 5},
                    "fraction",
                    "Fraction needing ICU",
                ),
                TemplateVariable(
                    "discharge_delay",
                    "exponential",
                    {"rate": 0.5},
                    "days",
                    "Administrative discharge delay",
                ),
                TemplateVariable("total_beds", "fixed", {"value": 50}),
                TemplateVariable("icu_beds", "fixed", {"value": 12}),
            ],
            objective_function="total_beds - (daily_admissions * ((1 - icu_fraction) * ward_los + icu_fraction * icu_los) + discharge_delay)",
            output_labels=["Available Beds"],
            output_units=["beds"],
            scoring={"expected_value": 0.3, "downside_risk": 0.7},
            tags=["medical", "hospital", "capacity", "operations"],
        )
    )

    register(
        SimulationTemplate(
            id="drug_development_roi",
            name="Drug Development ROI",
            domain="pharma",
            industry="Pharmaceutical",
            description="Full drug development pipeline simulation: probability of success at each phase, costs, and peak sales revenue.",
            use_case="What is the risk-adjusted NPV of our drug candidate pipeline?",
            variables=[
                TemplateVariable("phase1_success", "bernoulli", {"p": 0.65}, "binary"),
                TemplateVariable("phase2_success", "bernoulli", {"p": 0.45}, "binary"),
                TemplateVariable("phase3_success", "bernoulli", {"p": 0.60}, "binary"),
                TemplateVariable("phase1_cost", "lognormal", {"mean": 18.0, "std": 0.4}, "USD M"),
                TemplateVariable("phase2_cost", "lognormal", {"mean": 19.5, "std": 0.5}, "USD M"),
                TemplateVariable("phase3_cost", "lognormal", {"mean": 21.5, "std": 0.6}, "USD M"),
                TemplateVariable(
                    "peak_sales",
                    "lognormal",
                    {"mean": 20.7, "std": 0.8},
                    "USD M/year",
                    "Peak annual revenue",
                ),
                TemplateVariable(
                    "patent_life", "triangular", {"low": 7, "mode": 12, "high": 15}, "years"
                ),
                TemplateVariable("royalty_rate", "beta", {"alpha": 2, "beta": 8}, "rate"),
                TemplateVariable("discount_rate", "normal", {"mean": 0.12, "std": 0.02}, "rate"),
            ],
            objective_function="phase1_success * phase2_success * phase3_success * peak_sales * royalty_rate * patent_life / discount_rate - phase1_cost - phase2_cost * phase2_success - phase3_cost * phase2_success * phase3_success",
            output_labels=["Risk-Adjusted NPV (M USD)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["pharma", "drug", "development", "npv", "pipeline"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # MANUFACTURING / INDUSTRIAL
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="manufacturing_yield",
            name="Production Yield & OEE",
            domain="manufacturing",
            industry="Manufacturing / Operations",
            description="Overall Equipment Effectiveness (OEE) simulation: availability, performance, and quality rate variability.",
            use_case="What is our expected OEE? What drives most yield loss?",
            variables=[
                TemplateVariable(
                    "availability", "beta", {"alpha": 8, "beta": 2}, "%", "Machine uptime fraction"
                ),
                TemplateVariable(
                    "performance_rate",
                    "beta",
                    {"alpha": 9, "beta": 1.5},
                    "%",
                    "Speed vs. rated speed",
                ),
                TemplateVariable(
                    "quality_rate", "beta", {"alpha": 18, "beta": 2}, "%", "First-pass yield"
                ),
                TemplateVariable(
                    "planned_production_hrs", "normal", {"mean": 16, "std": 1}, "hours/day"
                ),
                TemplateVariable(
                    "unit_margin", "triangular", {"low": 8, "mode": 12, "high": 18}, "USD/unit"
                ),
                TemplateVariable("standard_output_rate", "fixed", {"value": 500}, "units/hour"),
            ],
            objective_function="planned_production_hrs * standard_output_rate * availability * performance_rate * quality_rate * unit_margin",
            output_labels=["Daily Contribution ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["manufacturing", "oee", "yield", "quality"],
        )
    )

    register(
        SimulationTemplate(
            id="reliability_mtbf",
            name="Equipment Reliability & Maintenance Cost",
            domain="manufacturing",
            industry="Manufacturing / Reliability Engineering",
            description="MTBF/MTTR simulation for predictive maintenance planning. Uses Weibull failure distribution.",
            use_case="What is our optimal maintenance interval? Expected annual maintenance cost?",
            variables=[
                TemplateVariable(
                    "time_to_failure",
                    "weibull",
                    {"shape": 2.5, "scale": 2000},
                    "hours",
                    "Weibull failure model (shape>1=wear-out)",
                ),
                TemplateVariable(
                    "time_to_repair",
                    "lognormal",
                    {"mean": 3.2, "std": 0.5},
                    "hours",
                    "MTTR distribution",
                ),
                TemplateVariable(
                    "failure_cost",
                    "lognormal",
                    {"mean": 10.5, "std": 0.7},
                    "USD",
                    "Unplanned failure cost",
                ),
                TemplateVariable(
                    "preventive_cost",
                    "normal",
                    {"mean": 2000, "std": 300},
                    "USD",
                    "Scheduled maintenance cost",
                ),
                TemplateVariable(
                    "production_rate",
                    "fixed",
                    {"value": 5000},
                    "USD/hour",
                    "Lost production per downtime hour",
                ),
                TemplateVariable("n_machines", "fixed", {"value": 20}),
            ],
            objective_function="n_machines * (failure_cost + time_to_repair * production_rate) / (time_to_failure / 8760)",
            output_labels=["Annual Failure Cost ($)"],
            output_units=["USD/year"],
            scoring={"expected_value": 0.4, "downside_risk": 0.6},
            tags=["reliability", "weibull", "mtbf", "maintenance", "manufacturing"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # AEROSPACE / DEFENSE
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="aerospace_mission_reliability",
            name="Mission Success Probability",
            domain="aerospace",
            industry="Aerospace / Defense",
            description="System reliability simulation for multi-component mission-critical systems. Models redundancy and failure modes.",
            use_case="What is our mission success probability? Where are the critical failure paths?",
            variables=[
                TemplateVariable(
                    "propulsion_reliability",
                    "beta",
                    {"alpha": 99, "beta": 1},
                    "probability",
                    "Propulsion system reliability",
                ),
                TemplateVariable(
                    "avionics_reliability", "beta", {"alpha": 97, "beta": 3}, "probability"
                ),
                TemplateVariable(
                    "power_reliability", "beta", {"alpha": 98, "beta": 2}, "probability"
                ),
                TemplateVariable(
                    "structure_reliability", "beta", {"alpha": 99.5, "beta": 0.5}, "probability"
                ),
                TemplateVariable(
                    "navigation_reliability", "beta", {"alpha": 96, "beta": 4}, "probability"
                ),
                TemplateVariable(
                    "comm_reliability", "beta", {"alpha": 95, "beta": 5}, "probability"
                ),
                TemplateVariable(
                    "redundancy_factor",
                    "fixed",
                    {"value": 2.0},
                    "count",
                    "Active redundancy multiplier",
                ),
            ],
            objective_function="1 - (1 - propulsion_reliability^redundancy_factor) * (1 - avionics_reliability) * (1 - power_reliability) * (1 - structure_reliability) * (1 - navigation_reliability)",
            output_labels=["Mission Success Probability"],
            output_units=["probability"],
            scoring={"expected_value": 0.7, "downside_risk": 0.3},
            tags=["aerospace", "defense", "reliability", "mission", "systems"],
        )
    )

    register(
        SimulationTemplate(
            id="defense_procurement_cost",
            name="Defense Program Cost Overrun Risk",
            domain="defense",
            industry="Defense / Government",
            description="Program cost growth simulation using historical defense acquisition data. Models schedule slip, technical risk, and inflation.",
            use_case="What is the 80th percentile cost estimate? Risk of exceeding budget threshold?",
            variables=[
                TemplateVariable("base_cost_estimate", "fixed", {"value": 500e6}, "USD"),
                TemplateVariable(
                    "technical_risk_factor",
                    "lognormal",
                    {"mean": 0.15, "std": 0.4},
                    "factor",
                    "Technical complexity growth",
                ),
                TemplateVariable(
                    "schedule_slip",
                    "lognormal",
                    {"mean": 0.3, "std": 0.5},
                    "years",
                    "Schedule overrun in years",
                ),
                TemplateVariable(
                    "inflation_rate", "normal", {"mean": 0.035, "std": 0.01}, "rate/year"
                ),
                TemplateVariable(
                    "scope_growth",
                    "pareto",
                    {"alpha": 3.0, "x_min": 0.0},
                    "USD",
                    "Scope creep additions",
                ),
                TemplateVariable(
                    "concurrency_factor",
                    "triangular",
                    {"low": 1.0, "mode": 1.15, "high": 1.5},
                    "factor",
                ),
            ],
            objective_function="base_cost_estimate * (1 + technical_risk_factor) * concurrency_factor * (1 + inflation_rate)^schedule_slip + scope_growth",
            output_labels=["Total Program Cost ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.3, "downside_risk": 0.7},
            tags=["defense", "procurement", "cost", "government", "acquisition"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # ENERGY
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="renewable_energy_output",
            name="Wind Farm Annual Energy Production",
            domain="energy",
            industry="Energy / Renewables",
            description="P50/P90 energy yield simulation for wind farm investment. Models wind resource variability, turbine availability, and grid curtailment.",
            use_case="What is the P50 and P90 annual production? What IRR do we achieve?",
            variables=[
                TemplateVariable(
                    "mean_wind_speed", "rayleigh", {"sigma": 8.5}, "m/s", "Annual mean wind speed"
                ),
                TemplateVariable(
                    "turbine_availability", "beta", {"alpha": 18, "beta": 2}, "fraction"
                ),
                TemplateVariable("grid_curtailment", "beta", {"alpha": 1, "beta": 19}, "fraction"),
                TemplateVariable(
                    "capacity_factor_adj", "normal", {"mean": 1.0, "std": 0.08}, "factor"
                ),
                TemplateVariable("installed_capacity_mw", "fixed", {"value": 100}, "MW"),
                TemplateVariable(
                    "electricity_price", "lognormal", {"mean": 4.0, "std": 0.2}, "USD/MWh"
                ),
                TemplateVariable("opex_mw", "normal", {"mean": 40000, "std": 5000}, "USD/MW/year"),
            ],
            objective_function="installed_capacity_mw * 8760 * capacity_factor_adj * 0.35 * turbine_availability * (1 - grid_curtailment) * electricity_price - opex_mw * installed_capacity_mw",
            output_labels=["Annual Revenue ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.5, "downside_risk": 0.5},
            tags=["energy", "wind", "renewable", "p50", "p90"],
        )
    )

    register(
        SimulationTemplate(
            id="oil_gas_reserves",
            name="Oil & Gas Field Reserves Estimation",
            domain="energy",
            industry="Energy / Oil & Gas",
            description="Probabilistic reserves estimation (P10/P50/P90) using geological uncertainty models.",
            use_case="What are our 1P, 2P, 3P reserve estimates? Expected NPV of the field?",
            variables=[
                TemplateVariable(
                    "gross_rock_volume",
                    "lognormal",
                    {"mean": 17.5, "std": 0.4},
                    "M bbl",
                    "GRV from seismic",
                ),
                TemplateVariable("net_to_gross", "beta", {"alpha": 4, "beta": 2}, "fraction"),
                TemplateVariable("porosity", "normal", {"mean": 0.18, "std": 0.03}, "fraction"),
                TemplateVariable("water_saturation", "beta", {"alpha": 2, "beta": 6}, "fraction"),
                TemplateVariable(
                    "recovery_factor",
                    "triangular",
                    {"low": 0.15, "mode": 0.30, "high": 0.45},
                    "fraction",
                ),
                TemplateVariable("oil_price", "lognormal", {"mean": 4.5, "std": 0.3}, "USD/bbl"),
                TemplateVariable("lifting_cost", "normal", {"mean": 12, "std": 3}, "USD/bbl"),
            ],
            objective_function="gross_rock_volume * net_to_gross * porosity * (1 - water_saturation) * recovery_factor * (oil_price - lifting_cost)",
            output_labels=["Field NPV ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["energy", "oil", "gas", "reserves", "geology"],
        )
    )
