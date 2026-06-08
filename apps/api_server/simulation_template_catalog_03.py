# ruff: noqa: E501
from __future__ import annotations

from collections.abc import Callable

from .simulation_template_models import SimulationTemplate, TemplateVariable


def register_catalog(register: Callable[[SimulationTemplate], SimulationTemplate]) -> None:

    # ─────────────────────────────────────────────────────────────────────────────
    # SAAS / TECHNOLOGY
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="saas_arr_forecast",
            name="SaaS ARR Growth & Churn Simulation",
            domain="technology",
            industry="SaaS / Software",
            description="Annual Recurring Revenue forecast under uncertain customer acquisition, expansion, and churn rates.",
            use_case="What is our expected ARR in 12 months? What churn rate makes us unprofitable?",
            variables=[
                TemplateVariable("current_arr", "fixed", {"value": 5000000}, "USD"),
                TemplateVariable(
                    "new_logo_monthly",
                    "poisson",
                    {"lambda": 15},
                    "accounts/month",
                    "New customer logos",
                ),
                TemplateVariable(
                    "avg_contract_value", "lognormal", {"mean": 10.5, "std": 0.6}, "USD/year"
                ),
                TemplateVariable(
                    "monthly_churn_rate", "beta", {"alpha": 2, "beta": 98}, "fraction"
                ),
                TemplateVariable(
                    "net_revenue_retention",
                    "normal",
                    {"mean": 1.10, "std": 0.08},
                    "ratio",
                    "NRR including expansion",
                ),
                TemplateVariable(
                    "sales_cycle_months", "lognormal", {"mean": 1.8, "std": 0.4}, "months"
                ),
            ],
            objective_function="current_arr * net_revenue_retention^(1/12) * (1 - monthly_churn_rate) + new_logo_monthly * avg_contract_value / 12",
            output_labels=["Monthly ARR Run Rate ($)"],
            output_units=["USD/month"],
            scoring={"expected_value": 0.65, "downside_risk": 0.35},
            tags=["saas", "arr", "churn", "growth", "technology"],
        )
    )

    register(
        SimulationTemplate(
            id="saas_unit_economics",
            name="SaaS Unit Economics (LTV/CAC)",
            domain="technology",
            industry="SaaS / Software",
            description="Customer lifetime value vs. customer acquisition cost simulation for SaaS businesses.",
            use_case="Is our LTV/CAC ratio sustainable? What churn rate breaks our unit economics?",
            variables=[
                TemplateVariable(
                    "monthly_arr_per_customer", "lognormal", {"mean": 8.5, "std": 0.5}, "USD/month"
                ),
                TemplateVariable("gross_margin", "beta", {"alpha": 14, "beta": 6}, "fraction"),
                TemplateVariable("monthly_churn", "beta", {"alpha": 1.5, "beta": 98.5}, "fraction"),
                TemplateVariable(
                    "cac",
                    "lognormal",
                    {"mean": 8.0, "std": 0.6},
                    "USD",
                    "Customer acquisition cost",
                ),
                TemplateVariable("payback_hurdle_months", "fixed", {"value": 18}, "months"),
                TemplateVariable(
                    "expansion_monthly",
                    "beta",
                    {"alpha": 3, "beta": 97},
                    "fraction",
                    "MoM expansion rate",
                ),
            ],
            objective_function="(monthly_arr_per_customer * (1 + expansion_monthly) * gross_margin / monthly_churn) / cac",
            output_labels=["LTV/CAC Ratio"],
            output_units=["ratio"],
            scoring={"expected_value": 0.7, "downside_risk": 0.3},
            tags=["saas", "ltv", "cac", "unit_economics", "technology"],
        )
    )

    register(
        SimulationTemplate(
            id="ai_model_training_cost",
            name="AI Model Training Cost Estimation",
            domain="technology",
            industry="AI / Machine Learning",
            description="Estimates GPU compute cost, time, and carbon footprint for training large AI models under uncertain scaling laws.",
            use_case="What will it cost to train our next model? Where is the cost uncertainty coming from?",
            variables=[
                TemplateVariable(
                    "model_params_B",
                    "lognormal",
                    {"mean": 4.6, "std": 0.5},
                    "B params",
                    "Model size in billions",
                ),
                TemplateVariable(
                    "training_tokens_T",
                    "lognormal",
                    {"mean": 5.3, "std": 0.4},
                    "T tokens",
                    "Training token count",
                ),
                TemplateVariable(
                    "gpu_flops_per_second",
                    "normal",
                    {"mean": 312e12, "std": 10e12},
                    "FLOP/s",
                    "H100 peak FLOPS",
                ),
                TemplateVariable(
                    "mfu_efficiency",
                    "beta",
                    {"alpha": 6, "beta": 4},
                    "fraction",
                    "Model FLOP utilization",
                ),
                TemplateVariable(
                    "gpu_cost_per_hour", "normal", {"mean": 3.0, "std": 0.5}, "USD/GPU-hour"
                ),
                TemplateVariable("n_gpus", "fixed", {"value": 1024}),
            ],
            objective_function="(model_params_B * 1e9 * training_tokens_T * 1e12 * 6) / (gpu_flops_per_second * mfu_efficiency * n_gpus) / 3600 * n_gpus * gpu_cost_per_hour",
            output_labels=["Training Cost (USD)"],
            output_units=["USD"],
            scoring={"expected_value": 0.5, "downside_risk": 0.5},
            tags=["ai", "ml", "compute", "training", "cost"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # REAL ESTATE
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
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
                TemplateVariable(
                    "annual_opex_rate",
                    "triangular",
                    {"low": 0.25, "mode": 0.35, "high": 0.50},
                    "fraction",
                    "% of gross rent",
                ),
                TemplateVariable(
                    "annual_appreciation", "normal", {"mean": 0.04, "std": 0.06}, "rate"
                ),
                TemplateVariable("mortgage_rate", "normal", {"mean": 0.065, "std": 0.005}, "rate"),
                TemplateVariable("ltv", "fixed", {"value": 0.75}, "ratio"),
                TemplateVariable("hold_period_years", "fixed", {"value": 10}, "years"),
            ],
            objective_function="monthly_rent * 12 * (1 - vacancy_rate) * (1 - annual_opex_rate) - purchase_price * ltv * mortgage_rate + purchase_price * annual_appreciation",
            output_labels=["Annual Net Cash Flow ($)"],
            output_units=["USD/year"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["real_estate", "rental", "yield", "buy_to_let", "residential"],
        )
    )

    register(
        SimulationTemplate(
            id="real_estate_development",
            name="Real Estate Development Feasibility",
            domain="real_estate",
            industry="Real Estate / Development",
            description="Residential development project feasibility: land cost, construction, sales price uncertainty, and absorption rate.",
            use_case="What is the expected developer profit? Probability of project loss?",
            variables=[
                TemplateVariable("n_units", "fixed", {"value": 120}),
                TemplateVariable(
                    "sales_price_per_unit", "normal", {"mean": 650000, "std": 60000}, "USD/unit"
                ),
                TemplateVariable(
                    "absorption_rate_monthly",
                    "triangular",
                    {"low": 4, "mode": 8, "high": 14},
                    "units/month",
                ),
                TemplateVariable("land_cost", "fixed", {"value": 8000000}, "USD"),
                TemplateVariable(
                    "construction_cost_per_unit",
                    "lognormal",
                    {"mean": 12.5, "std": 0.2},
                    "USD/unit",
                ),
                TemplateVariable(
                    "soft_costs_rate",
                    "beta",
                    {"alpha": 4, "beta": 36},
                    "fraction",
                    "% of hard costs",
                ),
                TemplateVariable(
                    "financing_cost_rate", "normal", {"mean": 0.08, "std": 0.015}, "rate"
                ),
                TemplateVariable("sales_commission_rate", "fixed", {"value": 0.025}, "fraction"),
            ],
            objective_function="n_units * sales_price_per_unit * (1 - sales_commission_rate) - land_cost - n_units * construction_cost_per_unit * (1 + soft_costs_rate) - n_units * construction_cost_per_unit * financing_cost_rate * (n_units / absorption_rate_monthly / 12)",
            output_labels=["Developer Profit ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["real_estate", "development", "feasibility", "residential", "construction"],
        )
    )

    register(
        SimulationTemplate(
            id="commercial_real_estate_cap_rate",
            name="Commercial Real Estate Cap Rate & Valuation",
            domain="real_estate",
            industry="Real Estate / Commercial",
            description="Office/retail property valuation under uncertain NOI growth, cap rate expansion, and occupancy.",
            use_case="What is the expected hold-period IRR? Downside if cap rates rise 100bps?",
            variables=[
                TemplateVariable(
                    "noi_year1",
                    "normal",
                    {"mean": 1500000, "std": 150000},
                    "USD/year",
                    "Year 1 Net Operating Income",
                ),
                TemplateVariable(
                    "noi_growth_rate", "normal", {"mean": 0.025, "std": 0.015}, "rate"
                ),
                TemplateVariable("entry_cap_rate", "normal", {"mean": 0.055, "std": 0.005}, "rate"),
                TemplateVariable("exit_cap_rate", "normal", {"mean": 0.060, "std": 0.008}, "rate"),
                TemplateVariable("hold_period_years", "fixed", {"value": 7}, "years"),
                TemplateVariable(
                    "acquisition_cost_rate",
                    "beta",
                    {"alpha": 2, "beta": 98},
                    "fraction",
                    "Transaction costs",
                ),
                TemplateVariable(
                    "leverage_ratio", "normal", {"mean": 0.60, "std": 0.05}, "fraction"
                ),
                TemplateVariable("debt_cost_rate", "normal", {"mean": 0.065, "std": 0.01}, "rate"),
            ],
            objective_function="(noi_year1 * (1 + noi_growth_rate)^hold_period_years / exit_cap_rate - noi_year1 / entry_cap_rate) + noi_year1 * hold_period_years * (1 + noi_growth_rate / 2) - leverage_ratio * (noi_year1 / entry_cap_rate) * debt_cost_rate * hold_period_years",
            output_labels=["Hold-Period Profit ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["real_estate", "commercial", "cap_rate", "noi", "office"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # BANKING / CREDIT RISK
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="credit_loan_portfolio_ecl",
            name="Loan Portfolio Expected Credit Loss (IFRS 9)",
            domain="banking",
            industry="Banking / Credit Risk",
            description="IFRS 9 ECL simulation: PD, LGD, and EAD uncertainty across a retail loan portfolio under macro stress scenarios.",
            use_case="What is our ECL provision? Sensitivity to macro downturn scenarios?",
            variables=[
                TemplateVariable(
                    "pd_through_cycle", "beta", {"alpha": 3, "beta": 97}, "fraction", "12-month PD"
                ),
                TemplateVariable(
                    "lgd", "beta", {"alpha": 4, "beta": 6}, "fraction", "Loss given default"
                ),
                TemplateVariable(
                    "ead_usd",
                    "lognormal",
                    {"mean": 18.4, "std": 0.3},
                    "USD M",
                    "Exposure at default",
                ),
                TemplateVariable(
                    "macro_pd_multiplier",
                    "lognormal",
                    {"mean": 0.18, "std": 0.6},
                    "factor",
                    "Macro stress factor on PD",
                ),
                TemplateVariable(
                    "correlation_factor",
                    "beta",
                    {"alpha": 2, "beta": 18},
                    "fraction",
                    "Asset correlation",
                ),
                TemplateVariable(
                    "cure_rate", "beta", {"alpha": 3, "beta": 7}, "fraction", "Recovery cure rate"
                ),
            ],
            objective_function="ead_usd * pd_through_cycle * (1 + macro_pd_multiplier) * lgd * (1 - cure_rate) * (1 + correlation_factor)",
            output_labels=["ECL Provision ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.3, "downside_risk": 0.7},
            tags=["banking", "credit_risk", "ecl", "ifrs9", "loan"],
        )
    )

    register(
        SimulationTemplate(
            id="banking_interest_rate_risk",
            name="Bank Net Interest Income (NII) Sensitivity",
            domain="banking",
            industry="Banking / Market Risk",
            description="NII simulation under parallel rate shifts, yield curve twists, and deposit repricing uncertainty.",
            use_case="How does a +200bps rate shock affect our NII? IRRBB compliance analysis.",
            variables=[
                TemplateVariable("loan_book_size", "fixed", {"value": 10e9}, "USD"),
                TemplateVariable("deposit_book_size", "fixed", {"value": 8e9}, "USD"),
                TemplateVariable(
                    "current_loan_yield", "normal", {"mean": 0.065, "std": 0.005}, "rate"
                ),
                TemplateVariable(
                    "rate_shock_bps",
                    "normal",
                    {"mean": 200, "std": 50},
                    "bps",
                    "Parallel rate shock",
                ),
                TemplateVariable(
                    "loan_repricing_lag_months",
                    "triangular",
                    {"low": 1, "mode": 6, "high": 24},
                    "months",
                ),
                TemplateVariable(
                    "deposit_beta",
                    "beta",
                    {"alpha": 4, "beta": 6},
                    "fraction",
                    "Deposit repricing sensitivity",
                ),
                TemplateVariable(
                    "funding_cost_spread", "normal", {"mean": 0.015, "std": 0.005}, "spread"
                ),
            ],
            objective_function="loan_book_size * (current_loan_yield + rate_shock_bps / 10000 * (1 / loan_repricing_lag_months * 12)) - deposit_book_size * (deposit_beta * rate_shock_bps / 10000 + funding_cost_spread)",
            output_labels=["Annual NII ($)"],
            output_units=["USD"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["banking", "interest_rate", "nii", "irrbb", "alm"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # RETAIL / E-COMMERCE
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="ecommerce_conversion_revenue",
            name="E-Commerce Revenue Optimization",
            domain="retail",
            industry="Retail / E-Commerce",
            description="Online store revenue simulation: traffic, conversion rate, average order value, and return rate variability.",
            use_case="What is the expected monthly revenue? ROI on traffic acquisition spend?",
            variables=[
                TemplateVariable(
                    "monthly_sessions", "lognormal", {"mean": 11.5, "std": 0.4}, "sessions"
                ),
                TemplateVariable("conversion_rate", "beta", {"alpha": 3, "beta": 97}, "fraction"),
                TemplateVariable("avg_order_value", "lognormal", {"mean": 4.5, "std": 0.4}, "USD"),
                TemplateVariable("return_rate", "beta", {"alpha": 2, "beta": 13}, "fraction"),
                TemplateVariable("gross_margin", "beta", {"alpha": 10, "beta": 15}, "fraction"),
                TemplateVariable(
                    "customer_acquisition_cost", "lognormal", {"mean": 3.2, "std": 0.5}, "USD"
                ),
                TemplateVariable(
                    "paid_traffic_fraction", "beta", {"alpha": 4, "beta": 6}, "fraction"
                ),
            ],
            objective_function="monthly_sessions * conversion_rate * avg_order_value * (1 - return_rate) * gross_margin - monthly_sessions * paid_traffic_fraction * customer_acquisition_cost / 100",
            output_labels=["Monthly Gross Profit ($)"],
            output_units=["USD/month"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["retail", "ecommerce", "conversion", "revenue", "marketing"],
        )
    )

    register(
        SimulationTemplate(
            id="retail_store_profitability",
            name="Brick-and-Mortar Store Profitability",
            domain="retail",
            industry="Retail / Physical",
            description="Physical retail store P&L simulation: foot traffic, conversion, basket size, and fixed cost sensitivity.",
            use_case="What is the break-even monthly revenue? Probability of profitable operations?",
            variables=[
                TemplateVariable(
                    "daily_footfall", "negative_binomial", {"r": 10, "p": 0.05}, "visitors/day"
                ),
                TemplateVariable("conversion_rate", "beta", {"alpha": 5, "beta": 20}, "fraction"),
                TemplateVariable("avg_basket_value", "lognormal", {"mean": 4.0, "std": 0.4}, "USD"),
                TemplateVariable("gross_margin", "beta", {"alpha": 12, "beta": 18}, "fraction"),
                TemplateVariable(
                    "monthly_rent", "normal", {"mean": 15000, "std": 2000}, "USD/month"
                ),
                TemplateVariable(
                    "monthly_labour", "normal", {"mean": 25000, "std": 3000}, "USD/month"
                ),
                TemplateVariable(
                    "monthly_other_opex", "lognormal", {"mean": 8.5, "std": 0.3}, "USD/month"
                ),
            ],
            objective_function="daily_footfall * 30 * conversion_rate * avg_basket_value * gross_margin - monthly_rent - monthly_labour - monthly_other_opex",
            output_labels=["Monthly Net Profit ($)"],
            output_units=["USD/month"],
            scoring={"expected_value": 0.55, "downside_risk": 0.45},
            tags=["retail", "physical_store", "footfall", "profitability"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # PRIVATE EQUITY / VENTURE CAPITAL
    # ─────────────────────────────────────────────────────────────────────────────

    register(
        SimulationTemplate(
            id="pe_fund_moic",
            name="Private Equity Fund MOIC & IRR",
            domain="finance",
            industry="Private Equity",
            description="PE fund returns simulation: portfolio company exit multiples, holding period, and fund-level fee waterfall.",
            use_case="What is the expected fund MOIC and IRR? Probability of returning 2x?",
            variables=[
                TemplateVariable(
                    "entry_ev_ebitda", "normal", {"mean": 8.5, "std": 1.5}, "multiple"
                ),
                TemplateVariable("exit_ev_ebitda", "normal", {"mean": 9.5, "std": 2.0}, "multiple"),
                TemplateVariable(
                    "ebitda_growth_rate", "normal", {"mean": 0.15, "std": 0.10}, "rate/year"
                ),
                TemplateVariable(
                    "hold_years",
                    "discrete",
                    {"values": [3, 4, 5, 6, 7], "probabilities": [0.1, 0.2, 0.35, 0.25, 0.10]},
                    "years",
                ),
                TemplateVariable(
                    "leverage_multiple", "normal", {"mean": 4.5, "std": 0.75}, "x EBITDA"
                ),
                TemplateVariable("interest_rate", "normal", {"mean": 0.07, "std": 0.01}, "rate"),
                TemplateVariable("management_fee", "fixed", {"value": 0.02}, "fraction/year"),
                TemplateVariable("carry", "fixed", {"value": 0.20}, "fraction"),
            ],
            objective_function="(exit_ev_ebitda / entry_ev_ebitda) * (1 + ebitda_growth_rate)^hold_years - leverage_multiple * interest_rate * hold_years - management_fee * hold_years",
            output_labels=["Investment MOIC"],
            output_units=["multiple"],
            scoring={"expected_value": 0.65, "downside_risk": 0.35},
            tags=["private_equity", "moic", "irr", "lbo", "fund"],
        )
    )

    register(
        SimulationTemplate(
            id="vc_portfolio_returns",
            name="Venture Capital Portfolio Power Law Returns",
            domain="finance",
            industry="Venture Capital",
            description="VC fund portfolio simulation: power-law exit distribution, failure rate, and time to liquidity uncertainty.",
            use_case="What is the expected fund DPI/TVPI? Power of portfolio diversification?",
            variables=[
                TemplateVariable("n_investments", "fixed", {"value": 30}),
                TemplateVariable(
                    "check_size_usd", "lognormal", {"mean": 14.9, "std": 0.6}, "USD M"
                ),
                TemplateVariable(
                    "failure_rate",
                    "beta",
                    {"alpha": 4, "beta": 6},
                    "fraction",
                    "Portfolio company failure rate",
                ),
                TemplateVariable(
                    "median_exit_multiple",
                    "lognormal",
                    {"mean": 1.5, "std": 0.7},
                    "x",
                    "Median exit multiple",
                ),
                TemplateVariable(
                    "power_law_alpha",
                    "normal",
                    {"mean": 1.5, "std": 0.3},
                    "alpha",
                    "Power law tail exponent",
                ),
                TemplateVariable("hold_years", "normal", {"mean": 7, "std": 2}, "years"),
                TemplateVariable(
                    "follow_on_ratio",
                    "beta",
                    {"alpha": 3, "beta": 7},
                    "fraction",
                    "Follow-on as % of initial",
                ),
            ],
            objective_function="n_investments * check_size_usd * (1 - failure_rate) * median_exit_multiple * power_law_alpha - n_investments * check_size_usd * (1 + follow_on_ratio)",
            output_labels=["Fund Net Profit ($M)"],
            output_units=["USD M"],
            scoring={"expected_value": 0.6, "downside_risk": 0.4},
            tags=["venture_capital", "startup", "power_law", "portfolio", "fund"],
        )
    )

    # ─────────────────────────────────────────────────────────────────────────────
