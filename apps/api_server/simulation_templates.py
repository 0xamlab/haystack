"""
Universal Domain Template Library for the Algenta Decision Engine.

Templates cover any industry — no restrictions on domain, data type, or variable count.
Each template provides a ready-to-run simulation with realistic variable specifications
that users can customize for their specific context.

Usage:
  from apps.api_server.simulation_templates import TEMPLATES, get_template
  template = get_template("financial_npv")
  payload = template.to_simulate_payload(runs=50000)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TemplateVariable:
    name: str
    distribution: str
    params: dict[str, Any]
    unit: str = ""
    description: str = ""
    domain_hint: str = ""


@dataclass
class SimulationTemplate:
    id: str
    name: str
    domain: str
    industry: str
    description: str
    use_case: str
    variables: list[TemplateVariable]
    objective_function: str
    output_labels: list[str]
    output_units: list[str]
    scoring: dict[str, float]
    tags: list[str] = field(default_factory=list)

    def to_simulate_payload(self, runs: int = 50000, seed: int | None = None) -> dict[str, Any]:
        return {
            "mode": "expert",
            "simulation_model": "monte_carlo",
            "runs": runs,
            "seed": seed,
            "simulation": {
                "domain": self.domain,
                "domain_template": self.id,
                "variables": [
                    {
                        "name": v.name,
                        "distribution": v.distribution,
                        "params": v.params,
                        "unit": v.unit,
                        "description": v.description,
                        "domain_hint": v.domain_hint,
                    }
                    for v in self.variables
                ],
                "objective_function": self.objective_function,
                "output_labels": self.output_labels,
                "output_units": self.output_units,
                "scoring": self.scoring,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "industry": self.industry,
            "description": self.description,
            "use_case": self.use_case,
            "objective_function": self.objective_function,
            "output_labels": self.output_labels,
            "output_units": self.output_units,
            "n_variables": len(self.variables),
            "tags": self.tags,
            "variables_preview": [
                {"name": v.name, "distribution": v.distribution, "unit": v.unit}
                for v in self.variables
            ],
        }


# ── Template Registry ─────────────────────────────────────────────────────────

TEMPLATES: dict[str, SimulationTemplate] = {}


def _register(t: SimulationTemplate) -> SimulationTemplate:
    TEMPLATES[t.id] = t
    return t


# ─────────────────────────────────────────────────────────────────────────────
# FINANCE
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="finance_npv",
    name="Project NPV Analysis",
    domain="finance",
    industry="Finance / Corporate",
    description="Net Present Value simulation for capital investment decisions. Models uncertain revenue, costs, discount rate, and project life.",
    use_case="Should we invest in this project? What is the probability of positive NPV?",
    variables=[
        TemplateVariable("initial_investment", "fixed", {"value": 1000000}, "USD", "Upfront capital expenditure"),
        TemplateVariable("annual_revenue", "lognormal", {"mean": 13.5, "std": 0.35}, "USD/year", "Annual revenue projection"),
        TemplateVariable("operating_costs", "triangular", {"low": 200000, "mode": 350000, "high": 600000}, "USD/year"),
        TemplateVariable("discount_rate", "normal", {"mean": 0.10, "std": 0.02}, "rate", "WACC / hurdle rate"),
        TemplateVariable("project_life", "discrete", {"values": [5, 7, 10, 15], "probabilities": [0.1, 0.3, 0.4, 0.2]}, "years"),
        TemplateVariable("terminal_growth", "normal", {"mean": 0.02, "std": 0.01}, "rate"),
    ],
    objective_function="(annual_revenue - operating_costs) / discount_rate * (1 - (1 + discount_rate)^(-project_life)) - initial_investment",
    output_labels=["NPV"],
    output_units=["USD"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["finance", "investment", "npv", "capital"],
))

_register(SimulationTemplate(
    id="finance_portfolio",
    name="Portfolio Value at Risk",
    domain="finance",
    industry="Finance / Asset Management",
    description="Daily portfolio P&L simulation with correlated asset returns. Computes VaR and CVaR.",
    use_case="What is the 95th-percentile daily loss? How correlated are my positions?",
    variables=[
        TemplateVariable("equity_return", "normal", {"mean": 0.0005, "std": 0.012}, "%/day", "Equity portfolio daily return"),
        TemplateVariable("bond_return", "normal", {"mean": 0.0001, "std": 0.003}, "%/day", "Fixed income daily return"),
        TemplateVariable("commodity_return", "normal", {"mean": 0.0002, "std": 0.018}, "%/day", "Commodity daily return"),
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
))

_register(SimulationTemplate(
    id="insurance_claims",
    name="Insurance Claims Reserve",
    domain="finance",
    industry="Insurance / Actuarial",
    description="Claims frequency × severity model for insurance reserving. Uses negative binomial for claim count and lognormal for claim size.",
    use_case="How much reserve should we hold? What is the 99th percentile total claims?",
    variables=[
        TemplateVariable("claim_frequency", "neg_binomial", {"r": 5.0, "p": 0.4}, "claims/year", "Annual claim count"),
        TemplateVariable("claim_severity", "lognormal", {"mean": 10.5, "std": 0.8}, "USD", "Individual claim amount"),
        TemplateVariable("expense_ratio", "beta", {"alpha": 4, "beta": 16}, "ratio", "Operating expense ratio"),
        TemplateVariable("earned_premium", "fixed", {"value": 5000000}, "USD"),
        TemplateVariable("reinsurance_retention", "fixed", {"value": 500000}, "USD", "Per-occurrence retention"),
    ],
    objective_function="earned_premium * (1 - expense_ratio) - min(claim_frequency * claim_severity, reinsurance_retention * 20)",
    output_labels=["Underwriting Profit"],
    output_units=["USD"],
    scoring={"expected_value": 0.5, "downside_risk": 0.5},
    tags=["insurance", "actuarial", "claims", "reserving"],
))

# ─────────────────────────────────────────────────────────────────────────────
# MEDICAL / CLINICAL / PHARMA
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="clinical_trial_power",
    name="Clinical Trial Power Analysis",
    domain="medical",
    industry="Medical / Pharmaceutical",
    description="Simulates trial outcome uncertainty: true treatment effect, measurement noise, dropout rate, and sample size effects.",
    use_case="What is our probability of detecting a significant treatment effect at given sample size?",
    variables=[
        TemplateVariable("true_effect", "normal", {"mean": 0.15, "std": 0.05}, "relative reduction", "True treatment effect size"),
        TemplateVariable("measurement_noise", "halfnormal", {"sigma": 0.03}, "SD", "Measurement variability"),
        TemplateVariable("placebo_response", "beta", {"alpha": 2, "beta": 8}, "rate", "Placebo responder rate"),
        TemplateVariable("dropout_rate", "beta", {"alpha": 1.5, "beta": 18.5}, "rate", "Patient dropout rate"),
        TemplateVariable("sample_size", "poisson", {"lambda": 300}, "patients", "Patients per arm"),
        TemplateVariable("alpha_threshold", "fixed", {"value": 0.05}, "p-value"),
    ],
    objective_function="(true_effect - measurement_noise) * (1 - dropout_rate) * sqrt(sample_size) - placebo_response",
    output_labels=["Standardized Treatment Effect"],
    output_units=["z-score"],
    scoring={"expected_value": 0.7, "downside_risk": 0.3},
    tags=["medical", "clinical", "pharma", "trial", "power"],
))

_register(SimulationTemplate(
    id="hospital_capacity",
    name="Hospital Capacity & Bed Occupancy",
    domain="medical",
    industry="Healthcare / Operations",
    description="ICU/ward capacity simulation: patient arrivals, length-of-stay, and discharge rates.",
    use_case="What is the probability of ICU overflow? Optimal bed count for 95% service level?",
    variables=[
        TemplateVariable("daily_admissions", "poisson", {"lambda": 12}, "patients/day"),
        TemplateVariable("icu_los", "lognormal", {"mean": 1.8, "std": 0.6}, "days", "ICU length of stay"),
        TemplateVariable("ward_los", "gamma", {"shape": 2.5, "scale": 2.0}, "days", "General ward LOS"),
        TemplateVariable("icu_fraction", "beta", {"alpha": 2, "beta": 5}, "fraction", "Fraction needing ICU"),
        TemplateVariable("discharge_delay", "exponential", {"rate": 0.5}, "days", "Administrative discharge delay"),
        TemplateVariable("total_beds", "fixed", {"value": 50}),
        TemplateVariable("icu_beds", "fixed", {"value": 12}),
    ],
    objective_function="total_beds - (daily_admissions * ((1 - icu_fraction) * ward_los + icu_fraction * icu_los) + discharge_delay)",
    output_labels=["Available Beds"],
    output_units=["beds"],
    scoring={"expected_value": 0.3, "downside_risk": 0.7},
    tags=["medical", "hospital", "capacity", "operations"],
))

_register(SimulationTemplate(
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
        TemplateVariable("peak_sales", "lognormal", {"mean": 20.7, "std": 0.8}, "USD M/year", "Peak annual revenue"),
        TemplateVariable("patent_life", "triangular", {"low": 7, "mode": 12, "high": 15}, "years"),
        TemplateVariable("royalty_rate", "beta", {"alpha": 2, "beta": 8}, "rate"),
        TemplateVariable("discount_rate", "normal", {"mean": 0.12, "std": 0.02}, "rate"),
    ],
    objective_function="phase1_success * phase2_success * phase3_success * peak_sales * royalty_rate * patent_life / discount_rate - phase1_cost - phase2_cost * phase2_success - phase3_cost * phase2_success * phase3_success",
    output_labels=["Risk-Adjusted NPV (M USD)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["pharma", "drug", "development", "npv", "pipeline"],
))

# ─────────────────────────────────────────────────────────────────────────────
# MANUFACTURING / INDUSTRIAL
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="manufacturing_yield",
    name="Production Yield & OEE",
    domain="manufacturing",
    industry="Manufacturing / Operations",
    description="Overall Equipment Effectiveness (OEE) simulation: availability, performance, and quality rate variability.",
    use_case="What is our expected OEE? What drives most yield loss?",
    variables=[
        TemplateVariable("availability", "beta", {"alpha": 8, "beta": 2}, "%", "Machine uptime fraction"),
        TemplateVariable("performance_rate", "beta", {"alpha": 9, "beta": 1.5}, "%", "Speed vs. rated speed"),
        TemplateVariable("quality_rate", "beta", {"alpha": 18, "beta": 2}, "%", "First-pass yield"),
        TemplateVariable("planned_production_hrs", "normal", {"mean": 16, "std": 1}, "hours/day"),
        TemplateVariable("unit_margin", "triangular", {"low": 8, "mode": 12, "high": 18}, "USD/unit"),
        TemplateVariable("standard_output_rate", "fixed", {"value": 500}, "units/hour"),
    ],
    objective_function="planned_production_hrs * standard_output_rate * availability * performance_rate * quality_rate * unit_margin",
    output_labels=["Daily Contribution ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["manufacturing", "oee", "yield", "quality"],
))

_register(SimulationTemplate(
    id="reliability_mtbf",
    name="Equipment Reliability & Maintenance Cost",
    domain="manufacturing",
    industry="Manufacturing / Reliability Engineering",
    description="MTBF/MTTR simulation for predictive maintenance planning. Uses Weibull failure distribution.",
    use_case="What is our optimal maintenance interval? Expected annual maintenance cost?",
    variables=[
        TemplateVariable("time_to_failure", "weibull", {"shape": 2.5, "scale": 2000}, "hours", "Weibull failure model (shape>1=wear-out)"),
        TemplateVariable("time_to_repair", "lognormal", {"mean": 3.2, "std": 0.5}, "hours", "MTTR distribution"),
        TemplateVariable("failure_cost", "lognormal", {"mean": 10.5, "std": 0.7}, "USD", "Unplanned failure cost"),
        TemplateVariable("preventive_cost", "normal", {"mean": 2000, "std": 300}, "USD", "Scheduled maintenance cost"),
        TemplateVariable("production_rate", "fixed", {"value": 5000}, "USD/hour", "Lost production per downtime hour"),
        TemplateVariable("n_machines", "fixed", {"value": 20}),
    ],
    objective_function="n_machines * (failure_cost + time_to_repair * production_rate) / (time_to_failure / 8760)",
    output_labels=["Annual Failure Cost ($)"],
    output_units=["USD/year"],
    scoring={"expected_value": 0.4, "downside_risk": 0.6},
    tags=["reliability", "weibull", "mtbf", "maintenance", "manufacturing"],
))

# ─────────────────────────────────────────────────────────────────────────────
# AEROSPACE / DEFENSE
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="aerospace_mission_reliability",
    name="Mission Success Probability",
    domain="aerospace",
    industry="Aerospace / Defense",
    description="System reliability simulation for multi-component mission-critical systems. Models redundancy and failure modes.",
    use_case="What is our mission success probability? Where are the critical failure paths?",
    variables=[
        TemplateVariable("propulsion_reliability", "beta", {"alpha": 99, "beta": 1}, "probability", "Propulsion system reliability"),
        TemplateVariable("avionics_reliability", "beta", {"alpha": 97, "beta": 3}, "probability"),
        TemplateVariable("power_reliability", "beta", {"alpha": 98, "beta": 2}, "probability"),
        TemplateVariable("structure_reliability", "beta", {"alpha": 99.5, "beta": 0.5}, "probability"),
        TemplateVariable("navigation_reliability", "beta", {"alpha": 96, "beta": 4}, "probability"),
        TemplateVariable("comm_reliability", "beta", {"alpha": 95, "beta": 5}, "probability"),
        TemplateVariable("redundancy_factor", "fixed", {"value": 2.0}, "count", "Active redundancy multiplier"),
    ],
    objective_function="1 - (1 - propulsion_reliability^redundancy_factor) * (1 - avionics_reliability) * (1 - power_reliability) * (1 - structure_reliability) * (1 - navigation_reliability)",
    output_labels=["Mission Success Probability"],
    output_units=["probability"],
    scoring={"expected_value": 0.7, "downside_risk": 0.3},
    tags=["aerospace", "defense", "reliability", "mission", "systems"],
))

_register(SimulationTemplate(
    id="defense_procurement_cost",
    name="Defense Program Cost Overrun Risk",
    domain="defense",
    industry="Defense / Government",
    description="Program cost growth simulation using historical defense acquisition data. Models schedule slip, technical risk, and inflation.",
    use_case="What is the 80th percentile cost estimate? Risk of exceeding budget threshold?",
    variables=[
        TemplateVariable("base_cost_estimate", "fixed", {"value": 500e6}, "USD"),
        TemplateVariable("technical_risk_factor", "lognormal", {"mean": 0.15, "std": 0.4}, "factor", "Technical complexity growth"),
        TemplateVariable("schedule_slip", "lognormal", {"mean": 0.3, "std": 0.5}, "years", "Schedule overrun in years"),
        TemplateVariable("inflation_rate", "normal", {"mean": 0.035, "std": 0.01}, "rate/year"),
        TemplateVariable("scope_growth", "pareto", {"alpha": 3.0, "x_min": 0.0}, "USD", "Scope creep additions"),
        TemplateVariable("concurrency_factor", "triangular", {"low": 1.0, "mode": 1.15, "high": 1.5}, "factor"),
    ],
    objective_function="base_cost_estimate * (1 + technical_risk_factor) * concurrency_factor * (1 + inflation_rate)^schedule_slip + scope_growth",
    output_labels=["Total Program Cost ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.3, "downside_risk": 0.7},
    tags=["defense", "procurement", "cost", "government", "acquisition"],
))

# ─────────────────────────────────────────────────────────────────────────────
# ENERGY
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="renewable_energy_output",
    name="Wind Farm Annual Energy Production",
    domain="energy",
    industry="Energy / Renewables",
    description="P50/P90 energy yield simulation for wind farm investment. Models wind resource variability, turbine availability, and grid curtailment.",
    use_case="What is the P50 and P90 annual production? What IRR do we achieve?",
    variables=[
        TemplateVariable("mean_wind_speed", "rayleigh", {"sigma": 8.5}, "m/s", "Annual mean wind speed"),
        TemplateVariable("turbine_availability", "beta", {"alpha": 18, "beta": 2}, "fraction"),
        TemplateVariable("grid_curtailment", "beta", {"alpha": 1, "beta": 19}, "fraction"),
        TemplateVariable("capacity_factor_adj", "normal", {"mean": 1.0, "std": 0.08}, "factor"),
        TemplateVariable("installed_capacity_mw", "fixed", {"value": 100}, "MW"),
        TemplateVariable("electricity_price", "lognormal", {"mean": 4.0, "std": 0.2}, "USD/MWh"),
        TemplateVariable("opex_mw", "normal", {"mean": 40000, "std": 5000}, "USD/MW/year"),
    ],
    objective_function="installed_capacity_mw * 8760 * capacity_factor_adj * 0.35 * turbine_availability * (1 - grid_curtailment) * electricity_price - opex_mw * installed_capacity_mw",
    output_labels=["Annual Revenue ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.5, "downside_risk": 0.5},
    tags=["energy", "wind", "renewable", "p50", "p90"],
))

_register(SimulationTemplate(
    id="oil_gas_reserves",
    name="Oil & Gas Field Reserves Estimation",
    domain="energy",
    industry="Energy / Oil & Gas",
    description="Probabilistic reserves estimation (P10/P50/P90) using geological uncertainty models.",
    use_case="What are our 1P, 2P, 3P reserve estimates? Expected NPV of the field?",
    variables=[
        TemplateVariable("gross_rock_volume", "lognormal", {"mean": 17.5, "std": 0.4}, "M bbl", "GRV from seismic"),
        TemplateVariable("net_to_gross", "beta", {"alpha": 4, "beta": 2}, "fraction"),
        TemplateVariable("porosity", "normal", {"mean": 0.18, "std": 0.03}, "fraction"),
        TemplateVariable("water_saturation", "beta", {"alpha": 2, "beta": 6}, "fraction"),
        TemplateVariable("recovery_factor", "triangular", {"low": 0.15, "mode": 0.30, "high": 0.45}, "fraction"),
        TemplateVariable("oil_price", "lognormal", {"mean": 4.5, "std": 0.3}, "USD/bbl"),
        TemplateVariable("lifting_cost", "normal", {"mean": 12, "std": 3}, "USD/bbl"),
    ],
    objective_function="gross_rock_volume * net_to_gross * porosity * (1 - water_saturation) * recovery_factor * (oil_price - lifting_cost)",
    output_labels=["Field NPV ($M)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["energy", "oil", "gas", "reserves", "geology"],
))

# ─────────────────────────────────────────────────────────────────────────────
# SUPPLY CHAIN / LOGISTICS
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="supply_chain_inventory",
    name="Inventory Optimization & Stockout Risk",
    domain="supply_chain",
    industry="Supply Chain / Logistics",
    description="Demand uncertainty and lead time variability simulation for safety stock calculation and service level optimization.",
    use_case="What safety stock minimizes stockout probability while minimizing holding cost?",
    variables=[
        TemplateVariable("daily_demand", "neg_binomial", {"r": 5.0, "p": 0.4}, "units/day"),
        TemplateVariable("lead_time_days", "lognormal", {"mean": 2.1, "std": 0.4}, "days"),
        TemplateVariable("demand_variability", "gamma", {"shape": 2, "scale": 5}, "units", "Daily demand sigma"),
        TemplateVariable("holding_cost_rate", "normal", {"mean": 0.25, "std": 0.05}, "fraction/year"),
        TemplateVariable("unit_cost", "normal", {"mean": 45, "std": 8}, "USD"),
        TemplateVariable("stockout_cost", "lognormal", {"mean": 5.5, "std": 0.5}, "USD/unit", "Lost sale + backorder cost"),
        TemplateVariable("reorder_point", "fixed", {"value": 200}, "units"),
        TemplateVariable("order_quantity", "fixed", {"value": 500}, "units"),
    ],
    objective_function="if(daily_demand * lead_time_days > reorder_point, stockout_cost * (daily_demand * lead_time_days - reorder_point), -holding_cost_rate * unit_cost * order_quantity / 2)",
    output_labels=["Inventory Cost ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.4, "downside_risk": 0.6},
    tags=["supply_chain", "inventory", "stockout", "logistics"],
))

# ─────────────────────────────────────────────────────────────────────────────
# HOSPITALITY / REVENUE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="hotel_revenue_management",
    name="Hotel RevPAR Optimization",
    domain="hospitality",
    industry="Hospitality / Travel",
    description="Hotel revenue simulation: occupancy rate, ADR, ancillary revenue, and seasonal demand variability.",
    use_case="What is the expected annual RevPAR? Optimal pricing strategy risk analysis.",
    variables=[
        TemplateVariable("base_occupancy", "beta", {"alpha": 6, "beta": 4}, "fraction", "Expected occupancy rate"),
        TemplateVariable("occupancy_volatility", "normal", {"mean": 0.0, "std": 0.08}, "shock", "Random demand shock"),
        TemplateVariable("adr", "lognormal", {"mean": 5.1, "std": 0.25}, "USD/night", "Average Daily Rate"),
        TemplateVariable("ancillary_revenue", "gamma", {"shape": 2, "scale": 15}, "USD/night", "F&B, spa, parking"),
        TemplateVariable("total_rooms", "fixed", {"value": 200}),
        TemplateVariable("variable_cost_per_occupied", "normal", {"mean": 45, "std": 8}, "USD/night"),
        TemplateVariable("fixed_cost_per_night", "normal", {"mean": 8000, "std": 500}, "USD/night"),
    ],
    objective_function="total_rooms * (base_occupancy + occupancy_volatility) * (adr + ancillary_revenue - variable_cost_per_occupied) - fixed_cost_per_night",
    output_labels=["Nightly Profit ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.55, "downside_risk": 0.45},
    tags=["hospitality", "hotel", "revpar", "revenue_management"],
))

# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCTION / REAL ESTATE
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="construction_project_cost",
    name="Construction Project Cost & Schedule Risk",
    domain="construction",
    industry="Construction / Real Estate",
    description="Project cost overrun and schedule delay simulation using PERT distributions for work packages.",
    use_case="What is the 80th percentile total cost? Probability of completing on schedule?",
    variables=[
        TemplateVariable("foundation_cost", "pert", {"low": 800000, "likely": 950000, "high": 1400000}, "USD"),
        TemplateVariable("structural_cost", "pert", {"low": 2000000, "likely": 2400000, "high": 3500000}, "USD"),
        TemplateVariable("mep_cost", "pert", {"low": 1200000, "likely": 1500000, "high": 2200000}, "USD"),
        TemplateVariable("finishes_cost", "pert", {"low": 600000, "likely": 800000, "high": 1300000}, "USD"),
        TemplateVariable("schedule_delay_weeks", "lognormal", {"mean": 2.0, "std": 0.8}, "weeks"),
        TemplateVariable("weekly_penalty", "fixed", {"value": 50000}, "USD/week"),
        TemplateVariable("contingency_pct", "beta", {"alpha": 3, "beta": 17}, "fraction"),
    ],
    objective_function="foundation_cost + structural_cost + mep_cost + finishes_cost + schedule_delay_weeks * weekly_penalty + (foundation_cost + structural_cost + mep_cost + finishes_cost) * contingency_pct",
    output_labels=["Total Project Cost ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.3, "downside_risk": 0.7},
    tags=["construction", "real_estate", "cost", "schedule", "pert"],
))

# ─────────────────────────────────────────────────────────────────────────────
# CYBERSECURITY / OPERATIONAL RISK
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="cyber_risk_quantification",
    name="Cyber Risk Financial Impact (FAIR Model)",
    domain="cybersecurity",
    industry="Technology / Insurance",
    description="FAIR-model cyber risk quantification: threat frequency, vulnerability, impact, and controls effectiveness.",
    use_case="What is the annual loss expectancy (ALE) from cyber incidents? VaR for cyber insurance?",
    variables=[
        TemplateVariable("threat_event_frequency", "lognormal", {"mean": 1.5, "std": 0.8}, "events/year"),
        TemplateVariable("vulnerability", "beta", {"alpha": 2, "beta": 5}, "fraction", "Prob of successful attack given attempt"),
        TemplateVariable("primary_loss", "lognormal", {"mean": 13.5, "std": 1.0}, "USD", "Per-incident primary loss"),
        TemplateVariable("secondary_loss_factor", "lognormal", {"mean": 0.4, "std": 0.5}, "multiplier", "Regulatory/reputation multiplier"),
        TemplateVariable("control_effectiveness", "beta", {"alpha": 7, "beta": 3}, "fraction", "Security control reduction"),
        TemplateVariable("incident_duration_days", "lognormal", {"mean": 2.3, "std": 0.8}, "days"),
    ],
    objective_function="threat_event_frequency * vulnerability * (1 - control_effectiveness) * primary_loss * (1 + secondary_loss_factor)",
    output_labels=["Annual Loss Expectancy ($)"],
    output_units=["USD/year"],
    scoring={"expected_value": 0.3, "downside_risk": 0.7},
    tags=["cybersecurity", "risk", "fair", "insurance", "operational_risk"],
))

# ─────────────────────────────────────────────────────────────────────────────
# ENVIRONMENTAL / CLIMATE
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="climate_impact_agriculture",
    name="Agricultural Yield Under Climate Uncertainty",
    domain="environmental",
    industry="Agriculture / Climate Risk",
    description="Crop yield simulation under climate variability: temperature deviation, precipitation, pest pressure.",
    use_case="What is the distribution of annual yield? Revenue at risk from climate scenarios?",
    variables=[
        TemplateVariable("baseline_yield", "normal", {"mean": 8.5, "std": 0.5}, "t/ha", "Baseline crop yield (wheat)"),
        TemplateVariable("temperature_anomaly", "gumbel", {"mu": 0.8, "beta": 0.4}, "°C", "Growing season temperature deviation"),
        TemplateVariable("precipitation_ratio", "lognormal", {"mean": -0.05, "std": 0.25}, "ratio", "Precip vs. historical mean"),
        TemplateVariable("pest_pressure", "bernoulli", {"p": 0.15}, "binary", "Major pest event"),
        TemplateVariable("pest_yield_loss", "beta", {"alpha": 2, "beta": 8}, "fraction", "Yield loss if pest event"),
        TemplateVariable("commodity_price", "lognormal", {"mean": 5.3, "std": 0.3}, "USD/t"),
        TemplateVariable("area_ha", "fixed", {"value": 500}, "hectares"),
    ],
    objective_function="area_ha * baseline_yield * (1 - 0.05 * temperature_anomaly) * (1 + 0.3 * precipitation_ratio) * (1 - pest_pressure * pest_yield_loss) * commodity_price",
    output_labels=["Annual Farm Revenue ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.5, "downside_risk": 0.5},
    tags=["agriculture", "climate", "yield", "environmental"],
))

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM / GENERIC
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="generic_cost_benefit",
    name="Generic Cost-Benefit Analysis",
    domain="general",
    industry="Any / General",
    description="Universal cost-benefit simulation template. Customize variable names, distributions, and objective for any decision.",
    use_case="Is the expected benefit worth the cost? What is the uncertainty range?",
    variables=[
        TemplateVariable("benefit", "triangular", {"low": 50000, "mode": 120000, "high": 300000}, "USD", "Total expected benefit"),
        TemplateVariable("direct_cost", "lognormal", {"mean": 10.5, "std": 0.4}, "USD"),
        TemplateVariable("indirect_cost", "normal", {"mean": 20000, "std": 5000}, "USD"),
        TemplateVariable("risk_factor", "beta", {"alpha": 2, "beta": 8}, "fraction", "Probability-weighted risk cost"),
        TemplateVariable("probability_success", "beta", {"alpha": 6, "beta": 4}, "probability"),
    ],
    objective_function="probability_success * benefit - direct_cost - indirect_cost - risk_factor * (direct_cost + indirect_cost)",
    output_labels=["Net Benefit ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["generic", "cost_benefit", "decision_analysis"],
))


# ─────────────────────────────────────────────────────────────────────────────
# CRYPTO / DIGITAL ASSETS
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="crypto_portfolio_var",
    name="Crypto Portfolio Value at Risk",
    domain="crypto",
    industry="Crypto / Digital Assets",
    description="Daily VaR for a multi-asset crypto portfolio using fat-tailed returns. Models BTC, ETH, and alt-coin correlations.",
    use_case="What is the 95th-percentile daily loss? How much capital buffer do I need?",
    variables=[
        TemplateVariable("btc_daily_return", "student_t", {"df": 4, "loc": 0.001, "scale": 0.035}, "ratio", "BTC daily log return"),
        TemplateVariable("eth_daily_return", "student_t", {"df": 3, "loc": 0.0012, "scale": 0.045}, "ratio", "ETH daily log return"),
        TemplateVariable("alt_daily_return", "student_t", {"df": 2.5, "loc": 0.0008, "scale": 0.08}, "ratio", "Alt-coin daily return"),
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
))

_register(SimulationTemplate(
    id="crypto_mining_profitability",
    name="Crypto Mining Profitability",
    domain="crypto",
    industry="Crypto / Mining",
    description="Bitcoin mining profitability under hash rate competition, price, difficulty adjustment, and energy cost variability.",
    use_case="Is mining profitable at current electricity costs? Break-even analysis.",
    variables=[
        TemplateVariable("btc_price", "lognormal", {"mean": 11.0, "std": 0.6}, "USD", "BTC price"),
        TemplateVariable("hash_rate_th", "normal", {"mean": 200, "std": 30}, "TH/s", "Mining rig hash rate"),
        TemplateVariable("network_difficulty", "lognormal", {"mean": 52.0, "std": 0.2}, "T", "Network difficulty"),
        TemplateVariable("energy_cost_kwh", "triangular", {"low": 0.04, "mode": 0.07, "high": 0.12}, "USD/kWh"),
        TemplateVariable("power_watts", "normal", {"mean": 3200, "std": 100}, "W", "Rig power consumption"),
        TemplateVariable("pool_fee", "fixed", {"value": 0.02}, "fraction"),
        TemplateVariable("block_reward", "fixed", {"value": 3.125}, "BTC"),
    ],
    objective_function="(hash_rate_th * 1e12 / (network_difficulty * 1e12 * 232)) * block_reward * btc_price * (1 - pool_fee) - power_watts / 1000 * 24 * energy_cost_kwh",
    output_labels=["Daily Mining Profit (USD)"],
    output_units=["USD/day"],
    scoring={"expected_value": 0.5, "downside_risk": 0.5},
    tags=["crypto", "bitcoin", "mining", "energy", "profitability"],
))

_register(SimulationTemplate(
    id="defi_protocol_tvl_risk",
    name="DeFi Protocol TVL & Liquidation Risk",
    domain="crypto",
    industry="Crypto / DeFi",
    description="Total Value Locked simulation for DeFi lending protocol under collateral price shocks and liquidation cascades.",
    use_case="What is the probability of a liquidation cascade? Protocol solvency under tail scenarios?",
    variables=[
        TemplateVariable("collateral_price_shock", "student_t", {"df": 3, "loc": -0.05, "scale": 0.12}, "ratio", "Collateral value change"),
        TemplateVariable("liquidation_threshold", "fixed", {"value": 0.75}, "LTV ratio"),
        TemplateVariable("avg_ltv", "beta", {"alpha": 5, "beta": 3}, "ratio", "Average loan-to-value"),
        TemplateVariable("tvl_usd", "lognormal", {"mean": 20.0, "std": 0.5}, "USD M", "Total value locked"),
        TemplateVariable("protocol_reserve_ratio", "beta", {"alpha": 3, "beta": 47}, "ratio"),
        TemplateVariable("slippage_factor", "lognormal", {"mean": -2.3, "std": 0.5}, "ratio", "Liquidation slippage"),
    ],
    objective_function="tvl_usd * protocol_reserve_ratio - tvl_usd * avg_ltv * max(0, (avg_ltv + collateral_price_shock - liquidation_threshold)) * (1 + slippage_factor)",
    output_labels=["Protocol Excess Reserve ($M)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.3, "downside_risk": 0.7},
    tags=["crypto", "defi", "liquidation", "tvl", "protocol_risk"],
))

# ─────────────────────────────────────────────────────────────────────────────
# SAAS / TECHNOLOGY
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="saas_arr_forecast",
    name="SaaS ARR Growth & Churn Simulation",
    domain="technology",
    industry="SaaS / Software",
    description="Annual Recurring Revenue forecast under uncertain customer acquisition, expansion, and churn rates.",
    use_case="What is our expected ARR in 12 months? What churn rate makes us unprofitable?",
    variables=[
        TemplateVariable("current_arr", "fixed", {"value": 5000000}, "USD"),
        TemplateVariable("new_logo_monthly", "poisson", {"lambda": 15}, "accounts/month", "New customer logos"),
        TemplateVariable("avg_contract_value", "lognormal", {"mean": 10.5, "std": 0.6}, "USD/year"),
        TemplateVariable("monthly_churn_rate", "beta", {"alpha": 2, "beta": 98}, "fraction"),
        TemplateVariable("net_revenue_retention", "normal", {"mean": 1.10, "std": 0.08}, "ratio", "NRR including expansion"),
        TemplateVariable("sales_cycle_months", "lognormal", {"mean": 1.8, "std": 0.4}, "months"),
    ],
    objective_function="current_arr * net_revenue_retention^(1/12) * (1 - monthly_churn_rate) + new_logo_monthly * avg_contract_value / 12",
    output_labels=["Monthly ARR Run Rate ($)"],
    output_units=["USD/month"],
    scoring={"expected_value": 0.65, "downside_risk": 0.35},
    tags=["saas", "arr", "churn", "growth", "technology"],
))

_register(SimulationTemplate(
    id="saas_unit_economics",
    name="SaaS Unit Economics (LTV/CAC)",
    domain="technology",
    industry="SaaS / Software",
    description="Customer lifetime value vs. customer acquisition cost simulation for SaaS businesses.",
    use_case="Is our LTV/CAC ratio sustainable? What churn rate breaks our unit economics?",
    variables=[
        TemplateVariable("monthly_arr_per_customer", "lognormal", {"mean": 8.5, "std": 0.5}, "USD/month"),
        TemplateVariable("gross_margin", "beta", {"alpha": 14, "beta": 6}, "fraction"),
        TemplateVariable("monthly_churn", "beta", {"alpha": 1.5, "beta": 98.5}, "fraction"),
        TemplateVariable("cac", "lognormal", {"mean": 8.0, "std": 0.6}, "USD", "Customer acquisition cost"),
        TemplateVariable("payback_hurdle_months", "fixed", {"value": 18}, "months"),
        TemplateVariable("expansion_monthly", "beta", {"alpha": 3, "beta": 97}, "fraction", "MoM expansion rate"),
    ],
    objective_function="(monthly_arr_per_customer * (1 + expansion_monthly) * gross_margin / monthly_churn) / cac",
    output_labels=["LTV/CAC Ratio"],
    output_units=["ratio"],
    scoring={"expected_value": 0.7, "downside_risk": 0.3},
    tags=["saas", "ltv", "cac", "unit_economics", "technology"],
))

_register(SimulationTemplate(
    id="ai_model_training_cost",
    name="AI Model Training Cost Estimation",
    domain="technology",
    industry="AI / Machine Learning",
    description="Estimates GPU compute cost, time, and carbon footprint for training large AI models under uncertain scaling laws.",
    use_case="What will it cost to train our next model? Where is the cost uncertainty coming from?",
    variables=[
        TemplateVariable("model_params_B", "lognormal", {"mean": 4.6, "std": 0.5}, "B params", "Model size in billions"),
        TemplateVariable("training_tokens_T", "lognormal", {"mean": 5.3, "std": 0.4}, "T tokens", "Training token count"),
        TemplateVariable("gpu_flops_per_second", "normal", {"mean": 312e12, "std": 10e12}, "FLOP/s", "H100 peak FLOPS"),
        TemplateVariable("mfu_efficiency", "beta", {"alpha": 6, "beta": 4}, "fraction", "Model FLOP utilization"),
        TemplateVariable("gpu_cost_per_hour", "normal", {"mean": 3.0, "std": 0.5}, "USD/GPU-hour"),
        TemplateVariable("n_gpus", "fixed", {"value": 1024}),
    ],
    objective_function="(model_params_B * 1e9 * training_tokens_T * 1e12 * 6) / (gpu_flops_per_second * mfu_efficiency * n_gpus) / 3600 * n_gpus * gpu_cost_per_hour",
    output_labels=["Training Cost (USD)"],
    output_units=["USD"],
    scoring={"expected_value": 0.5, "downside_risk": 0.5},
    tags=["ai", "ml", "compute", "training", "cost"],
))

# ─────────────────────────────────────────────────────────────────────────────
# REAL ESTATE
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="real_estate_rental_yield",
    name="Residential Rental Property ROI",
    domain="real_estate",
    industry="Real Estate / Residential",
    description="Buy-to-let investment return simulation: rental income, vacancy, expenses, and property appreciation.",
    use_case="What is my expected annual yield? Probability of negative cash flow?",
    variables=[
        TemplateVariable("purchase_price", "fixed", {"value": 500000}, "USD"),
        TemplateVariable("monthly_rent", "normal", {"mean": 2800, "std": 200}, "USD/month"),
        TemplateVariable("vacancy_rate", "beta", {"alpha": 1.5, "beta": 18.5}, "fraction"),
        TemplateVariable("annual_opex_rate", "triangular", {"low": 0.25, "mode": 0.35, "high": 0.50}, "fraction", "% of gross rent"),
        TemplateVariable("annual_appreciation", "normal", {"mean": 0.04, "std": 0.06}, "rate"),
        TemplateVariable("mortgage_rate", "normal", {"mean": 0.065, "std": 0.005}, "rate"),
        TemplateVariable("ltv", "fixed", {"value": 0.75}, "ratio"),
        TemplateVariable("hold_period_years", "fixed", {"value": 10}, "years"),
    ],
    objective_function="monthly_rent * 12 * (1 - vacancy_rate) * (1 - annual_opex_rate) - purchase_price * ltv * mortgage_rate + purchase_price * annual_appreciation",
    output_labels=["Annual Net Cash Flow ($)"],
    output_units=["USD/year"],
    scoring={"expected_value": 0.55, "downside_risk": 0.45},
    tags=["real_estate", "rental", "yield", "buy_to_let", "residential"],
))

_register(SimulationTemplate(
    id="real_estate_development",
    name="Real Estate Development Feasibility",
    domain="real_estate",
    industry="Real Estate / Development",
    description="Residential development project feasibility: land cost, construction, sales price uncertainty, and absorption rate.",
    use_case="What is the expected developer profit? Probability of project loss?",
    variables=[
        TemplateVariable("n_units", "fixed", {"value": 120}),
        TemplateVariable("sales_price_per_unit", "normal", {"mean": 650000, "std": 60000}, "USD/unit"),
        TemplateVariable("absorption_rate_monthly", "triangular", {"low": 4, "mode": 8, "high": 14}, "units/month"),
        TemplateVariable("land_cost", "fixed", {"value": 8000000}, "USD"),
        TemplateVariable("construction_cost_per_unit", "lognormal", {"mean": 12.5, "std": 0.2}, "USD/unit"),
        TemplateVariable("soft_costs_rate", "beta", {"alpha": 4, "beta": 36}, "fraction", "% of hard costs"),
        TemplateVariable("financing_cost_rate", "normal", {"mean": 0.08, "std": 0.015}, "rate"),
        TemplateVariable("sales_commission_rate", "fixed", {"value": 0.025}, "fraction"),
    ],
    objective_function="n_units * sales_price_per_unit * (1 - sales_commission_rate) - land_cost - n_units * construction_cost_per_unit * (1 + soft_costs_rate) - n_units * construction_cost_per_unit * financing_cost_rate * (n_units / absorption_rate_monthly / 12)",
    output_labels=["Developer Profit ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.55, "downside_risk": 0.45},
    tags=["real_estate", "development", "feasibility", "residential", "construction"],
))

_register(SimulationTemplate(
    id="commercial_real_estate_cap_rate",
    name="Commercial Real Estate Cap Rate & Valuation",
    domain="real_estate",
    industry="Real Estate / Commercial",
    description="Office/retail property valuation under uncertain NOI growth, cap rate expansion, and occupancy.",
    use_case="What is the expected hold-period IRR? Downside if cap rates rise 100bps?",
    variables=[
        TemplateVariable("noi_year1", "normal", {"mean": 1500000, "std": 150000}, "USD/year", "Year 1 Net Operating Income"),
        TemplateVariable("noi_growth_rate", "normal", {"mean": 0.025, "std": 0.015}, "rate"),
        TemplateVariable("entry_cap_rate", "normal", {"mean": 0.055, "std": 0.005}, "rate"),
        TemplateVariable("exit_cap_rate", "normal", {"mean": 0.060, "std": 0.008}, "rate"),
        TemplateVariable("hold_period_years", "fixed", {"value": 7}, "years"),
        TemplateVariable("acquisition_cost_rate", "beta", {"alpha": 2, "beta": 98}, "fraction", "Transaction costs"),
        TemplateVariable("leverage_ratio", "normal", {"mean": 0.60, "std": 0.05}, "fraction"),
        TemplateVariable("debt_cost_rate", "normal", {"mean": 0.065, "std": 0.01}, "rate"),
    ],
    objective_function="(noi_year1 * (1 + noi_growth_rate)^hold_period_years / exit_cap_rate - noi_year1 / entry_cap_rate) + noi_year1 * hold_period_years * (1 + noi_growth_rate / 2) - leverage_ratio * (noi_year1 / entry_cap_rate) * debt_cost_rate * hold_period_years",
    output_labels=["Hold-Period Profit ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.55, "downside_risk": 0.45},
    tags=["real_estate", "commercial", "cap_rate", "noi", "office"],
))

# ─────────────────────────────────────────────────────────────────────────────
# BANKING / CREDIT RISK
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="credit_loan_portfolio_ecl",
    name="Loan Portfolio Expected Credit Loss (IFRS 9)",
    domain="banking",
    industry="Banking / Credit Risk",
    description="IFRS 9 ECL simulation: PD, LGD, and EAD uncertainty across a retail loan portfolio under macro stress scenarios.",
    use_case="What is our ECL provision? Sensitivity to macro downturn scenarios?",
    variables=[
        TemplateVariable("pd_through_cycle", "beta", {"alpha": 3, "beta": 97}, "fraction", "12-month PD"),
        TemplateVariable("lgd", "beta", {"alpha": 4, "beta": 6}, "fraction", "Loss given default"),
        TemplateVariable("ead_usd", "lognormal", {"mean": 18.4, "std": 0.3}, "USD M", "Exposure at default"),
        TemplateVariable("macro_pd_multiplier", "lognormal", {"mean": 0.18, "std": 0.6}, "factor", "Macro stress factor on PD"),
        TemplateVariable("correlation_factor", "beta", {"alpha": 2, "beta": 18}, "fraction", "Asset correlation"),
        TemplateVariable("cure_rate", "beta", {"alpha": 3, "beta": 7}, "fraction", "Recovery cure rate"),
    ],
    objective_function="ead_usd * pd_through_cycle * (1 + macro_pd_multiplier) * lgd * (1 - cure_rate) * (1 + correlation_factor)",
    output_labels=["ECL Provision ($M)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.3, "downside_risk": 0.7},
    tags=["banking", "credit_risk", "ecl", "ifrs9", "loan"],
))

_register(SimulationTemplate(
    id="banking_interest_rate_risk",
    name="Bank Net Interest Income (NII) Sensitivity",
    domain="banking",
    industry="Banking / Market Risk",
    description="NII simulation under parallel rate shifts, yield curve twists, and deposit repricing uncertainty.",
    use_case="How does a +200bps rate shock affect our NII? IRRBB compliance analysis.",
    variables=[
        TemplateVariable("loan_book_size", "fixed", {"value": 10e9}, "USD"),
        TemplateVariable("deposit_book_size", "fixed", {"value": 8e9}, "USD"),
        TemplateVariable("current_loan_yield", "normal", {"mean": 0.065, "std": 0.005}, "rate"),
        TemplateVariable("rate_shock_bps", "normal", {"mean": 200, "std": 50}, "bps", "Parallel rate shock"),
        TemplateVariable("loan_repricing_lag_months", "triangular", {"low": 1, "mode": 6, "high": 24}, "months"),
        TemplateVariable("deposit_beta", "beta", {"alpha": 4, "beta": 6}, "fraction", "Deposit repricing sensitivity"),
        TemplateVariable("funding_cost_spread", "normal", {"mean": 0.015, "std": 0.005}, "spread"),
    ],
    objective_function="loan_book_size * (current_loan_yield + rate_shock_bps / 10000 * (1 / loan_repricing_lag_months * 12)) - deposit_book_size * (deposit_beta * rate_shock_bps / 10000 + funding_cost_spread)",
    output_labels=["Annual NII ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["banking", "interest_rate", "nii", "irrbb", "alm"],
))

# ─────────────────────────────────────────────────────────────────────────────
# RETAIL / E-COMMERCE
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="ecommerce_conversion_revenue",
    name="E-Commerce Revenue Optimization",
    domain="retail",
    industry="Retail / E-Commerce",
    description="Online store revenue simulation: traffic, conversion rate, average order value, and return rate variability.",
    use_case="What is the expected monthly revenue? ROI on traffic acquisition spend?",
    variables=[
        TemplateVariable("monthly_sessions", "lognormal", {"mean": 11.5, "std": 0.4}, "sessions"),
        TemplateVariable("conversion_rate", "beta", {"alpha": 3, "beta": 97}, "fraction"),
        TemplateVariable("avg_order_value", "lognormal", {"mean": 4.5, "std": 0.4}, "USD"),
        TemplateVariable("return_rate", "beta", {"alpha": 2, "beta": 13}, "fraction"),
        TemplateVariable("gross_margin", "beta", {"alpha": 10, "beta": 15}, "fraction"),
        TemplateVariable("customer_acquisition_cost", "lognormal", {"mean": 3.2, "std": 0.5}, "USD"),
        TemplateVariable("paid_traffic_fraction", "beta", {"alpha": 4, "beta": 6}, "fraction"),
    ],
    objective_function="monthly_sessions * conversion_rate * avg_order_value * (1 - return_rate) * gross_margin - monthly_sessions * paid_traffic_fraction * customer_acquisition_cost / 100",
    output_labels=["Monthly Gross Profit ($)"],
    output_units=["USD/month"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["retail", "ecommerce", "conversion", "revenue", "marketing"],
))

_register(SimulationTemplate(
    id="retail_store_profitability",
    name="Brick-and-Mortar Store Profitability",
    domain="retail",
    industry="Retail / Physical",
    description="Physical retail store P&L simulation: foot traffic, conversion, basket size, and fixed cost sensitivity.",
    use_case="What is the break-even monthly revenue? Probability of profitable operations?",
    variables=[
        TemplateVariable("daily_footfall", "negative_binomial", {"r": 10, "p": 0.05}, "visitors/day"),
        TemplateVariable("conversion_rate", "beta", {"alpha": 5, "beta": 20}, "fraction"),
        TemplateVariable("avg_basket_value", "lognormal", {"mean": 4.0, "std": 0.4}, "USD"),
        TemplateVariable("gross_margin", "beta", {"alpha": 12, "beta": 18}, "fraction"),
        TemplateVariable("monthly_rent", "normal", {"mean": 15000, "std": 2000}, "USD/month"),
        TemplateVariable("monthly_labour", "normal", {"mean": 25000, "std": 3000}, "USD/month"),
        TemplateVariable("monthly_other_opex", "lognormal", {"mean": 8.5, "std": 0.3}, "USD/month"),
    ],
    objective_function="daily_footfall * 30 * conversion_rate * avg_basket_value * gross_margin - monthly_rent - monthly_labour - monthly_other_opex",
    output_labels=["Monthly Net Profit ($)"],
    output_units=["USD/month"],
    scoring={"expected_value": 0.55, "downside_risk": 0.45},
    tags=["retail", "physical_store", "footfall", "profitability"],
))

# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE EQUITY / VENTURE CAPITAL
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="pe_fund_moic",
    name="Private Equity Fund MOIC & IRR",
    domain="finance",
    industry="Private Equity",
    description="PE fund returns simulation: portfolio company exit multiples, holding period, and fund-level fee waterfall.",
    use_case="What is the expected fund MOIC and IRR? Probability of returning 2x?",
    variables=[
        TemplateVariable("entry_ev_ebitda", "normal", {"mean": 8.5, "std": 1.5}, "multiple"),
        TemplateVariable("exit_ev_ebitda", "normal", {"mean": 9.5, "std": 2.0}, "multiple"),
        TemplateVariable("ebitda_growth_rate", "normal", {"mean": 0.15, "std": 0.10}, "rate/year"),
        TemplateVariable("hold_years", "discrete", {"values": [3, 4, 5, 6, 7], "probabilities": [0.1, 0.2, 0.35, 0.25, 0.10]}, "years"),
        TemplateVariable("leverage_multiple", "normal", {"mean": 4.5, "std": 0.75}, "x EBITDA"),
        TemplateVariable("interest_rate", "normal", {"mean": 0.07, "std": 0.01}, "rate"),
        TemplateVariable("management_fee", "fixed", {"value": 0.02}, "fraction/year"),
        TemplateVariable("carry", "fixed", {"value": 0.20}, "fraction"),
    ],
    objective_function="(exit_ev_ebitda / entry_ev_ebitda) * (1 + ebitda_growth_rate)^hold_years - leverage_multiple * interest_rate * hold_years - management_fee * hold_years",
    output_labels=["Investment MOIC"],
    output_units=["multiple"],
    scoring={"expected_value": 0.65, "downside_risk": 0.35},
    tags=["private_equity", "moic", "irr", "lbo", "fund"],
))

_register(SimulationTemplate(
    id="vc_portfolio_returns",
    name="Venture Capital Portfolio Power Law Returns",
    domain="finance",
    industry="Venture Capital",
    description="VC fund portfolio simulation: power-law exit distribution, failure rate, and time to liquidity uncertainty.",
    use_case="What is the expected fund DPI/TVPI? Power of portfolio diversification?",
    variables=[
        TemplateVariable("n_investments", "fixed", {"value": 30}),
        TemplateVariable("check_size_usd", "lognormal", {"mean": 14.9, "std": 0.6}, "USD M"),
        TemplateVariable("failure_rate", "beta", {"alpha": 4, "beta": 6}, "fraction", "Portfolio company failure rate"),
        TemplateVariable("median_exit_multiple", "lognormal", {"mean": 1.5, "std": 0.7}, "x", "Median exit multiple"),
        TemplateVariable("power_law_alpha", "normal", {"mean": 1.5, "std": 0.3}, "alpha", "Power law tail exponent"),
        TemplateVariable("hold_years", "normal", {"mean": 7, "std": 2}, "years"),
        TemplateVariable("follow_on_ratio", "beta", {"alpha": 3, "beta": 7}, "fraction", "Follow-on as % of initial"),
    ],
    objective_function="n_investments * check_size_usd * (1 - failure_rate) * median_exit_multiple * power_law_alpha - n_investments * check_size_usd * (1 + follow_on_ratio)",
    output_labels=["Fund Net Profit ($M)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["venture_capital", "startup", "power_law", "portfolio", "fund"],
))

# ─────────────────────────────────────────────────────────────────────────────
# TRANSPORTATION / LOGISTICS
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="airline_route_profitability",
    name="Airline Route Profitability",
    domain="transportation",
    industry="Transportation / Aviation",
    description="Airline route P&L simulation: load factor, yield, fuel price, and passenger demand variability.",
    use_case="Is this route profitable at current fuel prices? Revenue risk from demand shock?",
    variables=[
        TemplateVariable("load_factor", "beta", {"alpha": 7, "beta": 3}, "fraction"),
        TemplateVariable("revenue_per_pax", "lognormal", {"mean": 5.5, "std": 0.3}, "USD", "Average ticket yield"),
        TemplateVariable("aircraft_seats", "fixed", {"value": 180}),
        TemplateVariable("daily_frequency", "fixed", {"value": 2}),
        TemplateVariable("fuel_price_per_gallon", "lognormal", {"mean": 2.2, "std": 0.25}, "USD/gallon"),
        TemplateVariable("fuel_burn_gallons_per_flight", "normal", {"mean": 4500, "std": 300}, "gallons"),
        TemplateVariable("fixed_cost_per_flight", "normal", {"mean": 18000, "std": 2000}, "USD", "Crew, airport, landing"),
        TemplateVariable("variable_cost_per_pax", "normal", {"mean": 45, "std": 8}, "USD"),
    ],
    objective_function="aircraft_seats * load_factor * daily_frequency * (revenue_per_pax - variable_cost_per_pax) - daily_frequency * (fuel_price_per_gallon * fuel_burn_gallons_per_flight + fixed_cost_per_flight)",
    output_labels=["Daily Route Profit ($)"],
    output_units=["USD/day"],
    scoring={"expected_value": 0.55, "downside_risk": 0.45},
    tags=["airline", "aviation", "route", "fuel", "load_factor"],
))

_register(SimulationTemplate(
    id="shipping_freight_rate",
    name="Container Shipping Freight Rate P&L",
    domain="transportation",
    industry="Transportation / Shipping",
    description="Vessel voyage profitability under spot rate, bunker fuel, port costs, and utilization variability.",
    use_case="What is the TCE for this voyage? Break-even bunker price?",
    variables=[
        TemplateVariable("spot_freight_rate_per_teu", "lognormal", {"mean": 7.0, "std": 0.5}, "USD/TEU"),
        TemplateVariable("vessel_capacity_teu", "fixed", {"value": 8000}),
        TemplateVariable("utilization_rate", "beta", {"alpha": 7, "beta": 3}, "fraction"),
        TemplateVariable("voyage_days", "normal", {"mean": 28, "std": 3}, "days"),
        TemplateVariable("bunker_price_per_mt", "lognormal", {"mean": 6.2, "std": 0.3}, "USD/MT"),
        TemplateVariable("fuel_consumption_mt_per_day", "normal", {"mean": 120, "std": 15}, "MT/day"),
        TemplateVariable("port_costs_per_voyage", "normal", {"mean": 150000, "std": 25000}, "USD"),
    ],
    objective_function="spot_freight_rate_per_teu * vessel_capacity_teu * utilization_rate - voyage_days * bunker_price_per_mt * fuel_consumption_mt_per_day - port_costs_per_voyage",
    output_labels=["Voyage P&L ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.55, "downside_risk": 0.45},
    tags=["shipping", "freight", "bunker", "voyage", "maritime"],
))

# ─────────────────────────────────────────────────────────────────────────────
# MINING / NATURAL RESOURCES
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="mining_project_npv",
    name="Mining Project Feasibility & NPV",
    domain="mining",
    industry="Mining / Natural Resources",
    description="Open-pit mine NPV simulation: ore grade uncertainty, commodity price, strip ratio, and operating cost variability.",
    use_case="What is the P50 NPV? What commodity price makes the project marginal?",
    variables=[
        TemplateVariable("ore_grade_g_t", "lognormal", {"mean": 0.7, "std": 0.4}, "g/t", "Gold grade (g/t)"),
        TemplateVariable("ore_tonnes_Mt", "lognormal", {"mean": 2.3, "std": 0.3}, "Mt", "Total mineable ore"),
        TemplateVariable("gold_price_usd_oz", "lognormal", {"mean": 7.5, "std": 0.2}, "USD/oz"),
        TemplateVariable("recovery_rate", "beta", {"alpha": 8, "beta": 2}, "fraction"),
        TemplateVariable("aisc_per_oz", "normal", {"mean": 1100, "std": 150}, "USD/oz", "All-in sustaining cost"),
        TemplateVariable("strip_ratio", "lognormal", {"mean": 1.6, "std": 0.3}, "waste:ore"),
        TemplateVariable("discount_rate", "normal", {"mean": 0.08, "std": 0.015}, "rate"),
        TemplateVariable("mine_life_years", "triangular", {"low": 8, "mode": 12, "high": 18}, "years"),
    ],
    objective_function="ore_tonnes_Mt * 1e6 * ore_grade_g_t / 31.1035 * recovery_rate * (gold_price_usd_oz - aisc_per_oz) / discount_rate * (1 - (1 + discount_rate)^(-mine_life_years))",
    output_labels=["Project NPV ($M)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.55, "downside_risk": 0.45},
    tags=["mining", "gold", "npv", "resources", "feasibility"],
))

# ─────────────────────────────────────────────────────────────────────────────
# ESG / CARBON / SUSTAINABILITY
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="carbon_offset_valuation",
    name="Carbon Offset Project Valuation",
    domain="environmental",
    industry="ESG / Carbon Markets",
    description="Voluntary carbon market project NPV: credit issuance uncertainty, price, additionality risk, and permanence.",
    use_case="What is the expected NPV of our reforestation project? Carbon price sensitivity?",
    variables=[
        TemplateVariable("area_hectares", "fixed", {"value": 10000}),
        TemplateVariable("carbon_sequestration_t_ha_yr", "lognormal", {"mean": 2.0, "std": 0.5}, "tCO2e/ha/yr"),
        TemplateVariable("carbon_price_usd_t", "lognormal", {"mean": 3.5, "std": 0.5}, "USD/tCO2e"),
        TemplateVariable("additionality_buffer", "beta", {"alpha": 3, "beta": 7}, "fraction", "Buffer pool deduction"),
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
))

_register(SimulationTemplate(
    id="renewable_solar_lcoe",
    name="Solar PV Levelized Cost of Energy (LCOE)",
    domain="energy",
    industry="Energy / Solar",
    description="Utility-scale solar project LCOE simulation under capacity factor, CAPEX, OPEX, and degradation uncertainty.",
    use_case="What is our P50 LCOE? Is this project competitive with grid parity?",
    variables=[
        TemplateVariable("capex_per_mw", "lognormal", {"mean": 13.7, "std": 0.2}, "USD/W", "All-in solar CAPEX"),
        TemplateVariable("capacity_mw", "fixed", {"value": 100}),
        TemplateVariable("capacity_factor", "beta", {"alpha": 6, "beta": 4}, "fraction"),
        TemplateVariable("annual_degradation_rate", "normal", {"mean": 0.005, "std": 0.001}, "rate/year"),
        TemplateVariable("opex_per_mw_yr", "normal", {"mean": 15000, "std": 2500}, "USD/MW/yr"),
        TemplateVariable("discount_rate", "normal", {"mean": 0.06, "std": 0.01}, "rate"),
        TemplateVariable("project_life_years", "fixed", {"value": 25}),
    ],
    objective_function="(capex_per_mw * 1000 * capacity_mw + opex_per_mw_yr * capacity_mw / discount_rate) / (capacity_mw * 8760 * capacity_factor / discount_rate * (1 - (1 + discount_rate)^(-project_life_years)))",
    output_labels=["LCOE (USD/MWh)"],
    output_units=["USD/MWh"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["solar", "energy", "lcoe", "renewable", "pv"],
))

# ─────────────────────────────────────────────────────────────────────────────
# BIOTECH / LIFE SCIENCES
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="biotech_clinical_stage_valuation",
    name="Biotech Company rNPV Valuation",
    domain="biotech",
    industry="Biotech / Life Sciences",
    description="Risk-adjusted NPV of a biotech pipeline using probability of technical success at each clinical stage and peak sales uncertainty.",
    use_case="What is the fair value of this biotech? Sensitivity to peak sales and PoS assumptions.",
    variables=[
        TemplateVariable("p_phase2_success", "beta", {"alpha": 4, "beta": 6}, "probability"),
        TemplateVariable("p_phase3_success", "beta", {"alpha": 5, "beta": 5}, "probability"),
        TemplateVariable("p_regulatory_success", "beta", {"alpha": 8, "beta": 2}, "probability"),
        TemplateVariable("peak_sales_usd_M", "lognormal", {"mean": 6.9, "std": 0.8}, "USD M/yr"),
        TemplateVariable("royalty_rate", "beta", {"alpha": 3, "beta": 17}, "fraction"),
        TemplateVariable("years_to_market", "normal", {"mean": 6, "std": 1.5}, "years"),
        TemplateVariable("patent_remaining_years", "triangular", {"low": 6, "mode": 10, "high": 14}, "years"),
        TemplateVariable("phase2_cost_usd_M", "lognormal", {"mean": 3.9, "std": 0.5}, "USD M"),
        TemplateVariable("phase3_cost_usd_M", "lognormal", {"mean": 5.3, "std": 0.6}, "USD M"),
        TemplateVariable("discount_rate", "normal", {"mean": 0.12, "std": 0.02}, "rate"),
    ],
    objective_function="p_phase2_success * p_phase3_success * p_regulatory_success * peak_sales_usd_M * royalty_rate / discount_rate * (1 - (1 + discount_rate)^(-patent_remaining_years)) / (1 + discount_rate)^years_to_market - phase2_cost_usd_M - p_phase2_success * phase3_cost_usd_M",
    output_labels=["rNPV ($M)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["biotech", "rnpv", "clinical", "pipeline", "valuation"],
))

# ─────────────────────────────────────────────────────────────────────────────
# TELECOM
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="telecom_5g_roi",
    name="5G Network Deployment ROI",
    domain="telecom",
    industry="Telecom / Networks",
    description="5G capex investment return simulation: spectrum cost, equipment, subscriber adoption, and ARPU evolution.",
    use_case="What is the payback period for 5G rollout? IRR sensitivity to adoption speed.",
    variables=[
        TemplateVariable("spectrum_cost_usd_M", "lognormal", {"mean": 6.5, "std": 0.4}, "USD M"),
        TemplateVariable("equipment_cost_per_site", "normal", {"mean": 250000, "std": 30000}, "USD"),
        TemplateVariable("n_sites", "fixed", {"value": 5000}),
        TemplateVariable("subscriber_adoption_yr1", "beta", {"alpha": 3, "beta": 17}, "fraction"),
        TemplateVariable("total_subscribers_M", "fixed", {"value": 20}),
        TemplateVariable("arpu_premium_usd", "normal", {"mean": 8, "std": 2}, "USD/month", "5G ARPU premium"),
        TemplateVariable("opex_per_site_yr", "normal", {"mean": 20000, "std": 3000}, "USD/site/yr"),
        TemplateVariable("hold_years", "fixed", {"value": 10}),
    ],
    objective_function="total_subscribers_M * 1e6 * subscriber_adoption_yr1 * arpu_premium_usd * 12 * hold_years - spectrum_cost_usd_M * 1e6 - equipment_cost_per_site * n_sites - opex_per_site_yr * n_sites * hold_years",
    output_labels=["10-Year Net Value ($M)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.55, "downside_risk": 0.45},
    tags=["telecom", "5g", "network", "capex", "roi"],
))

# ─────────────────────────────────────────────────────────────────────────────
# HUMAN CAPITAL / WORKFORCE
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="workforce_attrition_cost",
    name="Employee Attrition Cost & Retention ROI",
    domain="hr",
    industry="Human Resources / Workforce",
    description="Annual workforce attrition cost simulation: replacement cost, productivity loss, and retention program ROI.",
    use_case="What is our total cost of attrition? ROI of retention investment?",
    variables=[
        TemplateVariable("total_headcount", "fixed", {"value": 500}),
        TemplateVariable("annual_attrition_rate", "beta", {"alpha": 3, "beta": 17}, "fraction"),
        TemplateVariable("avg_annual_salary", "lognormal", {"mean": 11.2, "std": 0.4}, "USD"),
        TemplateVariable("replacement_cost_multiple", "triangular", {"low": 0.5, "mode": 1.0, "high": 2.0}, "multiple", "Replacement as % of salary"),
        TemplateVariable("productivity_loss_months", "triangular", {"low": 2, "mode": 4, "high": 8}, "months"),
        TemplateVariable("retention_program_cost_per_employee", "normal", {"mean": 2000, "std": 500}, "USD/yr"),
        TemplateVariable("retention_effectiveness", "beta", {"alpha": 4, "beta": 6}, "fraction", "% reduction in attrition"),
    ],
    objective_function="total_headcount * annual_attrition_rate * avg_annual_salary * (replacement_cost_multiple + productivity_loss_months / 12) - total_headcount * retention_program_cost_per_employee + total_headcount * annual_attrition_rate * retention_effectiveness * avg_annual_salary * replacement_cost_multiple",
    output_labels=["Net Attrition Cost ($)"],
    output_units=["USD/year"],
    scoring={"expected_value": 0.4, "downside_risk": 0.6},
    tags=["hr", "workforce", "attrition", "retention", "human_capital"],
))

# ─────────────────────────────────────────────────────────────────────────────
# M&A / TRANSACTION
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="ma_synergy_valuation",
    name="M&A Synergy Realization & Deal Value",
    domain="finance",
    industry="M&A / Corporate Finance",
    description="M&A deal value simulation: revenue synergies, cost synergies, integration costs, and realization timing uncertainty.",
    use_case="What is the probability this deal creates value? Synergy risk sensitivity?",
    variables=[
        TemplateVariable("deal_enterprise_value", "fixed", {"value": 500e6}, "USD"),
        TemplateVariable("target_ebitda", "normal", {"mean": 50e6, "std": 5e6}, "USD"),
        TemplateVariable("revenue_synergy_usd_M", "lognormal", {"mean": 3.0, "std": 0.8}, "USD M/yr"),
        TemplateVariable("cost_synergy_usd_M", "lognormal", {"mean": 2.5, "std": 0.6}, "USD M/yr"),
        TemplateVariable("synergy_realization_pct", "beta", {"alpha": 6, "beta": 4}, "fraction"),
        TemplateVariable("integration_cost_usd_M", "lognormal", {"mean": 2.3, "std": 0.5}, "USD M"),
        TemplateVariable("synergy_timeline_years", "triangular", {"low": 2, "mode": 3, "high": 5}, "years"),
        TemplateVariable("discount_rate", "normal", {"mean": 0.10, "std": 0.015}, "rate"),
    ],
    objective_function="(revenue_synergy_usd_M + cost_synergy_usd_M) * 1e6 * synergy_realization_pct / discount_rate * (1 - (1 + discount_rate)^(-10)) / (1 + discount_rate)^synergy_timeline_years - integration_cost_usd_M * 1e6 - deal_enterprise_value + target_ebitda * 10",
    output_labels=["Deal Value Creation ($M)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["ma", "synergy", "acquisition", "corporate_finance", "valuation"],
))

# ─────────────────────────────────────────────────────────────────────────────
# GAMING / MEDIA
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="video_game_launch_revenue",
    name="Video Game Launch Revenue Forecast",
    domain="media",
    industry="Gaming / Entertainment",
    description="Game launch revenue simulation: unit sales, pricing, DLC/microtransaction revenue, and marketing efficiency.",
    use_case="What is the expected launch window revenue? Probability of recovering development costs?",
    variables=[
        TemplateVariable("launch_units_sold", "lognormal", {"mean": 13.1, "std": 0.8}, "units", "First-year units"),
        TemplateVariable("avg_selling_price", "normal", {"mean": 55, "std": 8}, "USD"),
        TemplateVariable("platform_rev_share", "normal", {"mean": 0.30, "std": 0.02}, "fraction"),
        TemplateVariable("dlc_attach_rate", "beta", {"alpha": 3, "beta": 7}, "fraction"),
        TemplateVariable("dlc_avg_revenue", "normal", {"mean": 25, "std": 5}, "USD/buyer"),
        TemplateVariable("marketing_cost_usd_M", "lognormal", {"mean": 3.2, "std": 0.5}, "USD M"),
        TemplateVariable("dev_cost_usd_M", "fixed", {"value": 80}, "USD M"),
    ],
    objective_function="launch_units_sold * avg_selling_price * (1 - platform_rev_share) + launch_units_sold * dlc_attach_rate * dlc_avg_revenue * (1 - platform_rev_share) - marketing_cost_usd_M * 1e6 - dev_cost_usd_M * 1e6",
    output_labels=["Launch Net Profit ($M)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["gaming", "entertainment", "launch", "revenue", "media"],
))

_register(SimulationTemplate(
    id="streaming_content_roi",
    name="Streaming Platform Content ROI",
    domain="media",
    industry="Media / Streaming",
    description="Original content investment ROI for streaming platform: subscriber acquisition, retention lift, and content cost.",
    use_case="What subscriber lift do we need to justify this content investment?",
    variables=[
        TemplateVariable("content_cost_usd_M", "lognormal", {"mean": 3.0, "std": 0.6}, "USD M"),
        TemplateVariable("new_subscriber_lift", "poisson", {"lambda": 50000}, "subscribers"),
        TemplateVariable("retention_improvement_pct", "beta", {"alpha": 2, "beta": 48}, "fraction"),
        TemplateVariable("current_subscribers_M", "fixed", {"value": 5}),
        TemplateVariable("monthly_arpu", "normal", {"mean": 14, "std": 2}, "USD/month"),
        TemplateVariable("avg_retention_months", "lognormal", {"mean": 3.0, "std": 0.4}, "months", "Incremental retention"),
        TemplateVariable("content_depreciation_years", "fixed", {"value": 3}),
    ],
    objective_function="new_subscriber_lift * monthly_arpu * avg_retention_months + current_subscribers_M * 1e6 * retention_improvement_pct * monthly_arpu * 12 - content_cost_usd_M * 1e6",
    output_labels=["Content ROI ($)"],
    output_units=["USD"],
    scoring={"expected_value": 0.55, "downside_risk": 0.45},
    tags=["streaming", "media", "content", "subscriber", "roi"],
))

# ─────────────────────────────────────────────────────────────────────────────
# LEGAL / LITIGATION
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="litigation_expected_value",
    name="Litigation Expected Value Analysis",
    domain="legal",
    industry="Legal / Dispute Resolution",
    description="Decision tree + Monte Carlo litigation EV analysis: probability of winning, damages, legal costs, and settlement alternatives.",
    use_case="Should we litigate or settle? What is the expected value of going to trial?",
    variables=[
        TemplateVariable("p_win_liability", "beta", {"alpha": 5, "beta": 5}, "probability"),
        TemplateVariable("p_win_damages_full", "beta", {"alpha": 4, "beta": 6}, "probability"),
        TemplateVariable("claimed_damages", "lognormal", {"mean": 14.9, "std": 0.5}, "USD M"),
        TemplateVariable("damages_reduction_factor", "beta", {"alpha": 4, "beta": 6}, "fraction"),
        TemplateVariable("plaintiff_legal_cost", "lognormal", {"mean": 13.1, "std": 0.5}, "USD M"),
        TemplateVariable("settlement_offer", "lognormal", {"mean": 13.8, "std": 0.4}, "USD M"),
        TemplateVariable("trial_duration_years", "triangular", {"low": 1.5, "mode": 3, "high": 5}, "years"),
        TemplateVariable("discount_rate", "fixed", {"value": 0.05}, "rate"),
    ],
    objective_function="p_win_liability * (p_win_damages_full * claimed_damages + (1 - p_win_damages_full) * claimed_damages * damages_reduction_factor) * (1 + discount_rate)^(-trial_duration_years) - plaintiff_legal_cost",
    output_labels=["Trial EV ($M)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.5, "downside_risk": 0.5},
    tags=["legal", "litigation", "settlement", "expected_value", "decision_analysis"],
))

# ─────────────────────────────────────────────────────────────────────────────
# FOOD & BEVERAGE
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="restaurant_profitability",
    name="Restaurant Unit Economics",
    domain="hospitality",
    industry="Food & Beverage / Restaurant",
    description="Restaurant P&L simulation: covers, average check, food cost, labor, and occupancy variability.",
    use_case="What is the expected monthly profit? Prime cost sensitivity analysis.",
    variables=[
        TemplateVariable("seats", "fixed", {"value": 80}),
        TemplateVariable("daily_turns", "triangular", {"low": 1.5, "mode": 2.2, "high": 3.0}, "turns/day"),
        TemplateVariable("average_check_usd", "lognormal", {"mean": 3.8, "std": 0.3}, "USD/cover"),
        TemplateVariable("food_cost_pct", "normal", {"mean": 0.30, "std": 0.03}, "fraction"),
        TemplateVariable("labor_cost_pct", "normal", {"mean": 0.32, "std": 0.04}, "fraction"),
        TemplateVariable("monthly_rent", "normal", {"mean": 12000, "std": 2000}, "USD/month"),
        TemplateVariable("other_opex_pct", "beta", {"alpha": 3, "beta": 17}, "fraction"),
        TemplateVariable("days_open_per_month", "fixed", {"value": 26}),
    ],
    objective_function="seats * daily_turns * average_check_usd * days_open_per_month * (1 - food_cost_pct - labor_cost_pct - other_opex_pct) - monthly_rent",
    output_labels=["Monthly Net Profit ($)"],
    output_units=["USD/month"],
    scoring={"expected_value": 0.55, "downside_risk": 0.45},
    tags=["restaurant", "food_beverage", "hospitality", "unit_economics"],
))

# ─────────────────────────────────────────────────────────────────────────────
# QUALITY / SIX SIGMA
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="six_sigma_process_capability",
    name="Process Capability & Defect Rate (Cpk)",
    domain="manufacturing",
    industry="Manufacturing / Quality",
    description="Process capability simulation: natural process variation, spec limits, and Cpk under measurement uncertainty.",
    use_case="What is our expected Cpk? Probability of exceeding defect budget?",
    variables=[
        TemplateVariable("process_mean", "normal", {"mean": 0.0, "std": 0.5}, "mm", "Process mean deviation from target"),
        TemplateVariable("process_std", "lognormal", {"mean": -1.6, "std": 0.2}, "mm", "Within-subgroup sigma"),
        TemplateVariable("usl", "fixed", {"value": 3.0}, "mm", "Upper spec limit"),
        TemplateVariable("lsl", "fixed", {"value": -3.0}, "mm", "Lower spec limit"),
        TemplateVariable("measurement_error_std", "halfnormal", {"sigma": 0.1}, "mm", "Gauge R&R contribution"),
        TemplateVariable("shift_factor", "normal", {"mean": 1.5, "std": 0.3}, "sigma", "Long-term process shift"),
    ],
    objective_function="min((usl - process_mean) / (3 * (process_std + measurement_error_std)), (process_mean - lsl) / (3 * (process_std + measurement_error_std))) - shift_factor / 3",
    output_labels=["Process Cpk"],
    output_units=["cpk"],
    scoring={"expected_value": 0.7, "downside_risk": 0.3},
    tags=["quality", "six_sigma", "cpk", "manufacturing", "process"],
))

# ─────────────────────────────────────────────────────────────────────────────
# INSURANCE — ADDITIONAL
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="cat_bond_expected_loss",
    name="Catastrophe Bond Expected Loss",
    domain="finance",
    industry="Insurance / Catastrophe Risk",
    description="Cat bond expected annual loss simulation: natural catastrophe frequency, severity, and reinsurance attachment.",
    use_case="What is the EL for our cat bond? Risk-adjusted return vs. spread?",
    variables=[
        TemplateVariable("annual_cat_frequency", "poisson", {"lambda": 0.3}, "events/year"),
        TemplateVariable("event_severity_usd_B", "lognormal", {"mean": 2.3, "std": 0.8}, "USD B"),
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
))

_register(SimulationTemplate(
    id="life_insurance_mortality",
    name="Life Insurance Mortality Risk",
    domain="finance",
    industry="Insurance / Life",
    description="Life insurer mortality rate simulation: pandemic shock, longevity trend, and claims reserve adequacy.",
    use_case="What mortality rate stress tests our reserve? P99 claims in adverse scenario?",
    variables=[
        TemplateVariable("base_mortality_rate", "beta", {"alpha": 2, "beta": 1998}, "fraction", "Annual qx per policy"),
        TemplateVariable("mortality_multiplier", "lognormal", {"mean": 0.0, "std": 0.3}, "factor", "Stress/improvement factor"),
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
))

# ─────────────────────────────────────────────────────────────────────────────
# SPORTS ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="sports_player_contract_value",
    name="Sports Player Contract Value-Over-Replacement",
    domain="sports",
    industry="Sports Analytics",
    description="Player contract ROI simulation: projected WAR/WAA, market rate per win, injury probability, and performance decline.",
    use_case="Is this contract justified? Expected surplus value over contract term?",
    variables=[
        TemplateVariable("projected_war_yr1", "normal", {"mean": 4.0, "std": 1.5}, "WAR"),
        TemplateVariable("war_decline_rate", "normal", {"mean": 0.15, "std": 0.08}, "rate/year"),
        TemplateVariable("injury_probability_annual", "beta", {"alpha": 2, "beta": 8}, "fraction"),
        TemplateVariable("injury_war_impact", "beta", {"alpha": 3, "beta": 7}, "fraction"),
        TemplateVariable("market_rate_per_war", "normal", {"mean": 8e6, "std": 1e6}, "USD/WAR"),
        TemplateVariable("contract_value_per_year", "fixed", {"value": 25e6}, "USD"),
        TemplateVariable("contract_years", "fixed", {"value": 5}, "years"),
    ],
    objective_function="sum([projected_war_yr1 * (1 - war_decline_rate)^i * (1 - injury_probability_annual * injury_war_impact) * market_rate_per_war - contract_value_per_year for i in range(int(contract_years))])",
    output_labels=["Total Contract Surplus ($M)"],
    output_units=["USD M"],
    scoring={"expected_value": 0.6, "downside_risk": 0.4},
    tags=["sports", "analytics", "contract", "war", "performance"],
))

# ─────────────────────────────────────────────────────────────────────────────
# PROCUREMENT / SOURCING
# ─────────────────────────────────────────────────────────────────────────────

_register(SimulationTemplate(
    id="procurement_supplier_risk",
    name="Supplier Concentration & Disruption Cost",
    domain="supply_chain",
    industry="Procurement / Sourcing",
    description="Supply disruption cost simulation: probability of supplier failure, lead time extension, and dual-sourcing premium trade-off.",
    use_case="How much should I pay for a second supplier? Expected cost of supply disruption?",
    variables=[
        TemplateVariable("annual_spend_with_supplier", "fixed", {"value": 10e6}, "USD"),
        TemplateVariable("disruption_probability", "beta", {"alpha": 1, "beta": 24}, "fraction"),
        TemplateVariable("disruption_duration_weeks", "lognormal", {"mean": 2.0, "std": 0.6}, "weeks"),
        TemplateVariable("weekly_production_loss", "normal", {"mean": 500000, "std": 100000}, "USD/week"),
        TemplateVariable("expediting_cost_factor", "triangular", {"low": 1.1, "mode": 1.25, "high": 1.5}, "factor"),
        TemplateVariable("dual_source_premium", "beta", {"alpha": 3, "beta": 47}, "fraction", "% premium for second source"),
        TemplateVariable("safety_stock_holding_cost", "normal", {"mean": 50000, "std": 10000}, "USD/year"),
    ],
    objective_function="disruption_probability * (disruption_duration_weeks * weekly_production_loss + annual_spend_with_supplier * (expediting_cost_factor - 1)) - annual_spend_with_supplier * dual_source_premium - safety_stock_holding_cost",
    output_labels=["Expected Annual Disruption Cost ($)"],
    output_units=["USD/year"],
    scoring={"expected_value": 0.3, "downside_risk": 0.7},
    tags=["procurement", "supplier", "disruption", "supply_chain", "risk"],
))


def get_template(template_id: str) -> SimulationTemplate | None:
    return TEMPLATES.get(template_id)


def list_templates(domain: str | None = None, industry: str | None = None) -> list[dict]:
    templates = list(TEMPLATES.values())
    if domain:
        templates = [t for t in templates if domain.lower() in t.domain.lower()]
    if industry:
        templates = [t for t in templates if industry.lower() in t.industry.lower()]
    return [t.to_dict() for t in templates]


def get_all_domains() -> list[str]:
    return sorted(set(t.domain for t in TEMPLATES.values()))


def get_all_tags() -> list[str]:
    tags: set[str] = set()
    for t in TEMPLATES.values():
        tags.update(t.tags)
    return sorted(tags)
