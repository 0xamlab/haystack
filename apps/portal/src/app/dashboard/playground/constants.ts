/**
 * Playground page — constants, types, and utilities.
 * Extracted so page.tsx stays under 800 lines.
 */

export type Mode = "auto" | "expert"

export type TemplatePayload = Record<string, unknown>

export const SIM_MODELS = [
  { value: "monte_carlo",         label: "Monte Carlo" },
  { value: "qmc_sobol",          label: "QMC Sobol" },
  { value: "lhs",                label: "Latin Hypercube" },
  { value: "bootstrap",          label: "Bootstrap" },
  { value: "scenario",           label: "Scenario Analysis" },
  { value: "sensitivity",        label: "Sensitivity" },
  { value: "mcmc",               label: "MCMC Bayesian" },
  { value: "decision_tree",      label: "Decision Tree" },
  { value: "time_series",        label: "Time Series" },
  { value: "compare",            label: "Compare Scenarios" },
  { value: "importance_sampling",label: "Importance Sampling" },
]

/** Extract a numeric representative value from distribution params */
export function paramVal(params: Record<string, number>): number {
  return (
    params.mean   ??
    params.mode   ??
    params.value  ??
    params.mu     ??
    params.lambda ??
    params.low    ??
    0
  )
}

/** Build a fresh JSON payload for auto mode from current template payload and slider vals */
export function applySliderVals(
  templatePayload: TemplatePayload,
  vals: Record<string, number>,
  runs: number,
  seed: number,
): TemplatePayload {
  const sim = (templatePayload as Record<string, unknown>).simulation as
    | Record<string, unknown>
    | undefined
  if (!sim) return { ...templatePayload, runs, seed }
  const vars = (sim.variables as Array<Record<string, unknown>>) ?? []
  const updatedVars = vars.map((v) => {
    const name = v.name as string
    if (vals[name] !== undefined) {
      const params = v.params as Record<string, number>
      const key = Object.keys(params).find((k) =>
        ["mean", "mode", "value", "mu", "lambda", "low"].includes(k),
      )
      if (key) return { ...v, params: { ...params, [key]: vals[name] } }
    }
    return v
  })
  return { ...templatePayload, runs, seed, simulation: { ...sim, variables: updatedVars } }
}

// ── Builtin fallback templates ────────────────────────────────────────────────
export const BUILTIN_TEMPLATES: Record<string, TemplatePayload> = {
  "SaaS Revenue Model": {
    mode: "expert", runs: 50000, seed: 42,
    simulation: {
      variables: [
        { name: "arr",          distribution: "lognormal",  params: { mean: 14.0, std: 0.35 },   unit: "USD",    description: "Annual Recurring Revenue" },
        { name: "churn_rate",   distribution: "beta",       params: { alpha: 2, beta: 22 },       unit: "%/month",description: "Monthly churn" },
        { name: "growth_rate",  distribution: "normal",     params: { mean: 0.08, std: 0.03 },   unit: "%/month",description: "Net new MRR growth" },
        { name: "cac",          distribution: "lognormal",  params: { mean: 7.5, std: 0.4 },     unit: "USD",    description: "Customer Acquisition Cost" },
        { name: "ltv_multiple", distribution: "triangular", params: { low: 2.5, mode: 4.0, high: 7.0 }, unit: "x", description: "LTV/CAC multiple" },
      ],
      objective_function: "arr * (1 + growth_rate - churn_rate) * ltv_multiple - cac * arr / 5000",
      output_labels: ["ARR Risk-Adjusted Value"],
      output_units: ["USD"],
      scoring: { expected_value: 0.6, downside_risk: 0.4 },
    },
  },
  "Portfolio VaR": {
    mode: "expert", runs: 100000, seed: 7,
    simulation: {
      variables: [
        { name: "equity_return",    distribution: "normal", params: { mean: 0.0005, std: 0.013 }, unit: "%/day", description: "Equity daily return" },
        { name: "bond_return",      distribution: "normal", params: { mean: 0.0001, std: 0.003 }, unit: "%/day", description: "Fixed income daily return" },
        { name: "fx_return",        distribution: "normal", params: { mean: 0.0,    std: 0.006 }, unit: "%/day", description: "FX daily return" },
        { name: "portfolio_value",  distribution: "fixed",  params: { value: 10000000 },          unit: "USD",   description: "Portfolio NAV" },
      ],
      objective_function: "portfolio_value * (0.6 * equity_return + 0.3 * bond_return + 0.1 * fx_return)",
      output_labels: ["Daily P&L"],
      output_units: ["USD"],
      scoring: { expected_value: 0.35, downside_risk: 0.65 },
    },
  },
  "Clinical Trial": {
    mode: "expert", runs: 50000, seed: 99,
    simulation: {
      variables: [
        { name: "treatment_effect",   distribution: "normal",     params: { mean: 0.18, std: 0.06 },    unit: "relative risk reduction" },
        { name: "placebo_response",   distribution: "beta",       params: { alpha: 2, beta: 10 },        unit: "rate" },
        { name: "dropout_rate",       distribution: "beta",       params: { alpha: 1.5, beta: 18 },      unit: "rate" },
        { name: "sample_size",        distribution: "poisson",    params: { lambda: 250 },               unit: "patients/arm" },
        { name: "measurement_noise",  distribution: "halfnormal", params: { sigma: 0.03 },               unit: "SD" },
      ],
      objective_function: "(treatment_effect - measurement_noise) * (1 - dropout_rate) * sqrt(sample_size) - placebo_response",
      output_labels: ["Standardized Effect Size"],
      output_units: ["z-score"],
      scoring: { expected_value: 0.7, downside_risk: 0.3 },
    },
  },
  "Equipment Reliability": {
    mode: "expert", runs: 50000, seed: 17,
    simulation: {
      variables: [
        { name: "time_to_failure",  distribution: "weibull",    params: { shape: 2.5, scale: 2000 }, unit: "hours",    description: "MTBF via Weibull (shape>1=wear-out)" },
        { name: "repair_time",      distribution: "lognormal",  params: { mean: 3.2, std: 0.5 },     unit: "hours",    description: "MTTR distribution" },
        { name: "failure_cost",     distribution: "lognormal",  params: { mean: 10.5, std: 0.7 },    unit: "USD",      description: "Unplanned failure cost" },
        { name: "production_rate",  distribution: "fixed",      params: { value: 5000 },             unit: "USD/hour", description: "Revenue per production hour" },
        { name: "n_machines",       distribution: "fixed",      params: { value: 15 } },
      ],
      objective_function: "n_machines * (failure_cost + repair_time * production_rate) / (time_to_failure / 8760)",
      output_labels: ["Annual Failure Cost"],
      output_units: ["USD/year"],
      scoring: { expected_value: 0.3, downside_risk: 0.7 },
    },
  },
  "Cyber Risk (FAIR)": {
    mode: "expert", runs: 50000, seed: 13,
    simulation: {
      variables: [
        { name: "threat_frequency",      distribution: "lognormal", params: { mean: 1.5, std: 0.8 },    unit: "events/year" },
        { name: "vulnerability",         distribution: "beta",      params: { alpha: 2, beta: 5 },       unit: "probability" },
        { name: "primary_loss",          distribution: "lognormal", params: { mean: 13.5, std: 1.0 },   unit: "USD" },
        { name: "secondary_factor",      distribution: "lognormal", params: { mean: 0.3, std: 0.5 },    unit: "multiplier" },
        { name: "control_effectiveness", distribution: "beta",      params: { alpha: 7, beta: 3 },       unit: "fraction" },
      ],
      objective_function: "threat_frequency * vulnerability * (1 - control_effectiveness) * primary_loss * (1 + secondary_factor)",
      output_labels: ["Annual Loss Expectancy"],
      output_units: ["USD/year"],
      scoring: { expected_value: 0.25, downside_risk: 0.75 },
    },
  },
}
