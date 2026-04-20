"use client";
import type { SimulationModelType } from "@/lib/api";

/** Badge for simulation model type. */
export function ModelBadge({ model }: { model?: string }) {
  if (!model || model === "monte_carlo")
    return (
      <span className="ag-badge ag-badge--muted" style={{ fontSize: 10 }}>
        MC
      </span>
    );
  const short: Record<string, string> = {
    qmc_sobol: "QMC",
    lhs: "LHS",
    bootstrap: "Boot",
    scenario: "Scen",
    sensitivity: "Sens",
    mcmc: "MCMC",
  };
  return (
    <span className="ag-badge ag-badge--primary" style={{ fontSize: 10 }}>
      {short[model] ?? model.toUpperCase().slice(0, 4)}
    </span>
  );
}

/** Shared MODEL_INFO constant used by simulations pages. */
export const MODEL_INFO: Record<
  SimulationModelType,
  { label: string; icon: string; desc: string }
> = {
  monte_carlo: {
    label: "Monte Carlo",
    icon: "fa-dice",
    desc: "Standard MC with full distribution library",
  },
  qmc_sobol: {
    label: "QMC Sobol",
    icon: "fa-wave-square",
    desc: "Quasi-MC: faster convergence, fewer samples",
  },
  lhs: {
    label: "LHS",
    icon: "fa-table-cells",
    desc: "Latin Hypercube: stratified full coverage",
  },
  bootstrap: {
    label: "Bootstrap",
    icon: "fa-rotate",
    desc: "Resample historical data — no distribution needed",
  },
  scenario: {
    label: "Scenario",
    icon: "fa-diagram-project",
    desc: "Discrete Bear/Base/Bull weighted scenarios",
  },
  sensitivity: {
    label: "Sensitivity",
    icon: "fa-sliders",
    desc: "Tornado chart: which variables matter most?",
  },
  mcmc: {
    label: "MCMC",
    icon: "fa-circle-nodes",
    desc: "Bayesian inference from observed data",
  },
};
