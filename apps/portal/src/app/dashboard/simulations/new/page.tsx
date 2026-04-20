"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { simulate } from "@/lib/api";

// ── Distribution parameter forms ────────────────────────────────────────────

const DIST_PARAMS: Record<
  string,
  { key: string; label: string; placeholder: string; hint?: string }[]
> = {
  normal: [
    { key: "mean", label: "Mean (μ)", placeholder: "0" },
    { key: "std", label: "Std Dev (σ)", placeholder: "1", hint: "Must be > 0" },
  ],
  uniform: [
    { key: "low", label: "Minimum", placeholder: "0" },
    { key: "high", label: "Maximum", placeholder: "100" },
  ],
  triangular: [
    { key: "low", label: "Minimum", placeholder: "0" },
    { key: "mode", label: "Most Likely", placeholder: "50" },
    { key: "high", label: "Maximum", placeholder: "100" },
  ],
  lognormal: [
    {
      key: "mean",
      label: "Log-mean (μ)",
      placeholder: "0",
      hint: "Mean of ln(X)",
    },
    {
      key: "std",
      label: "Log-std (σ)",
      placeholder: "1",
      hint: "Std of ln(X)",
    },
  ],
  fixed: [{ key: "value", label: "Constant Value", placeholder: "0" }],
  beta: [
    { key: "alpha", label: "Alpha (α)", placeholder: "2" },
    { key: "beta", label: "Beta (β)", placeholder: "5" },
  ],
  exponential: [
    { key: "rate", label: "Rate (λ)", placeholder: "1", hint: "Mean = 1/λ" },
  ],
  weibull: [
    {
      key: "shape",
      label: "Shape (k)",
      placeholder: "2",
      hint: "k>1: wear-out; k=1: random; k<1: infant mortality",
    },
    { key: "scale", label: "Scale (λ)", placeholder: "1" },
  ],
  gamma: [
    { key: "shape", label: "Shape (α)", placeholder: "2" },
    { key: "scale", label: "Scale (θ)", placeholder: "1" },
  ],
  pert: [
    { key: "low", label: "Minimum", placeholder: "0" },
    { key: "likely", label: "Most Likely", placeholder: "50" },
    { key: "high", label: "Maximum", placeholder: "100" },
    {
      key: "gamma",
      label: "Shape γ",
      placeholder: "4",
      hint: "4 = standard PERT; higher = tighter",
    },
  ],
  bernoulli: [
    {
      key: "p",
      label: "Probability p",
      placeholder: "0.5",
      hint: "Returns 1 with prob p, else 0",
    },
  ],
  poisson: [
    {
      key: "lambda",
      label: "Rate (λ)",
      placeholder: "5",
      hint: "Expected count per interval",
    },
  ],
  student_t: [
    {
      key: "df",
      label: "Degrees of Freedom",
      placeholder: "5",
      hint: "Lower = heavier tails",
    },
    { key: "loc", label: "Location (μ)", placeholder: "0" },
    { key: "scale", label: "Scale", placeholder: "1" },
  ],
  cauchy: [
    { key: "location", label: "Location", placeholder: "0" },
    { key: "scale", label: "Scale", placeholder: "1" },
  ],
  laplace: [
    { key: "mu", label: "Location (μ)", placeholder: "0" },
    { key: "b", label: "Scale (b)", placeholder: "1" },
  ],
  pareto: [
    {
      key: "alpha",
      label: "Shape (α)",
      placeholder: "2",
      hint: "Higher α = lighter tail",
    },
    { key: "x_min", label: "Minimum (xₘ)", placeholder: "1" },
  ],
  gumbel: [
    { key: "mu", label: "Location (μ)", placeholder: "0" },
    { key: "beta", label: "Scale (β)", placeholder: "1" },
  ],
  rayleigh: [{ key: "sigma", label: "Scale (σ)", placeholder: "1" }],
  arcsine: [
    { key: "low", label: "Minimum", placeholder: "0" },
    { key: "high", label: "Maximum", placeholder: "1" },
  ],
  logistic: [
    { key: "mu", label: "Location (μ)", placeholder: "0" },
    { key: "scale", label: "Scale", placeholder: "1" },
  ],
  halfnormal: [{ key: "sigma", label: "Scale (σ)", placeholder: "1" }],
  vonmises: [
    { key: "mu", label: "Mean direction (rad)", placeholder: "0" },
    {
      key: "kappa",
      label: "Concentration κ",
      placeholder: "1",
      hint: "0=uniform; higher=more concentrated",
    },
  ],
  neg_binomial: [
    { key: "r", label: "Successes (r)", placeholder: "5" },
    { key: "p", label: "Success prob (p)", placeholder: "0.5" },
  ],
  hypergeometric: [
    { key: "N", label: "Population (N)", placeholder: "100" },
    { key: "K", label: "Success states (K)", placeholder: "50" },
    { key: "n", label: "Draw size (n)", placeholder: "10" },
  ],
  discrete: [], // handled separately
  categorical: [], // handled separately
};

const DIST_CATEGORIES: { label: string; dists: string[] }[] = [
  {
    label: "Core",
    dists: ["normal", "uniform", "triangular", "lognormal", "fixed"],
  },
  {
    label: "Count/Binary",
    dists: ["bernoulli", "poisson", "neg_binomial", "hypergeometric"],
  },
  {
    label: "Continuous",
    dists: ["beta", "exponential", "weibull", "gamma", "pert"],
  },
  {
    label: "Heavy-tailed",
    dists: ["student_t", "cauchy", "laplace", "pareto", "gumbel"],
  },
  {
    label: "Special",
    dists: ["rayleigh", "arcsine", "logistic", "halfnormal", "vonmises"],
  },
  { label: "Discrete", dists: ["discrete", "categorical"] },
];

const DIST_DESCRIPTIONS: Record<string, string> = {
  normal: "Symmetric bell curve. Universal default.",
  uniform: "Equal probability across range.",
  triangular: "When you know min, max, and most likely.",
  lognormal: "Always positive, right-skewed. Revenue, prices, times.",
  fixed: "Constant value — no uncertainty.",
  beta: "Probabilities and rates. Bounded [0,1] by default.",
  exponential: "Time between events. Memoryless.",
  weibull: "Failure/reliability. Shape controls failure mode.",
  gamma: "Positive right-skewed. Wait times, insurance claims.",
  pert: "Like triangular but smoother. Project estimation.",
  bernoulli: "Binary outcome (success/failure). Yes/No.",
  poisson: "Count of events in interval. Arrivals, defects.",
  student_t: "Like normal but heavier tails. Small samples.",
  cauchy: "Extreme heavy tails. No defined mean.",
  laplace: "Double exponential. Sharp peak, fat tails.",
  pareto: "Power law. Wealth, city sizes, 80/20 rule.",
  gumbel: "Extreme value. Maximum of many samples. Floods.",
  rayleigh: "Signal amplitude. Ocean waves. Wind speed.",
  arcsine: "Time in state. Stock prices at extremes.",
  logistic: "S-curve growth. Epidemic spread.",
  halfnormal: "Always positive. Measurement errors, errors.",
  vonmises: "Circular/angular data. Wind direction, seasons.",
  neg_binomial: "Overdispersed counts. More variance than Poisson.",
  hypergeometric: "Sampling without replacement. Lots, batches.",
  discrete: "Custom outcomes with exact probabilities.",
  categorical: "Named categories with probabilities.",
};

const SIM_MODELS = [
  {
    value: "monte_carlo",
    label: "Monte Carlo",
    icon: "fa-dice",
    desc: "Standard random sampling — universal default",
  },
  {
    value: "qmc_sobol",
    label: "QMC Sobol",
    icon: "fa-wave-square",
    desc: "Quasi-random: faster convergence, same N",
  },
  {
    value: "lhs",
    label: "LHS",
    icon: "fa-table-cells",
    desc: "Stratified coverage — guaranteed full range",
  },
  {
    value: "sensitivity",
    label: "Sensitivity",
    icon: "fa-sliders",
    desc: "Which variables matter most? Tornado chart.",
  },
];

// ── Variable row ──────────────────────────────────────────────────────────────

interface Variable {
  id: number;
  name: string;
  distribution: string;
  params: Record<string, string>;
  unit: string;
  description: string;
  discrete_values: string; // comma-separated for discrete/categorical
  discrete_probs: string; // comma-separated
  discrete_labels: string; // comma-separated for categorical
}

function VariableRow({
  v,
  idx,
  onChange,
  onRemove,
  canRemove,
}: {
  v: Variable;
  idx: number;
  onChange: (id: number, patch: Partial<Variable>) => void;
  onRemove: (id: number) => void;
  canRemove: boolean;
}) {
  const [expanded, setExpanded] = useState(idx < 3);
  const paramDefs = DIST_PARAMS[v.distribution] ?? [];
  const isDiscrete =
    v.distribution === "discrete" || v.distribution === "categorical";

  return (
    <div
      style={{
        background: "var(--ag-bg-surface-0)",
        border: "1px solid var(--ag-border-default)",
        borderRadius: "var(--ag-radius-md)",
        marginBottom: 8,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          cursor: "pointer",
          background: expanded ? "rgba(107,66,252,0.05)" : "transparent",
          borderBottom: expanded
            ? "1px solid var(--ag-border-default)"
            : "none",
        }}
        onClick={() => setExpanded((x) => !x)}
      >
        <span
          style={{
            width: 22,
            height: 22,
            borderRadius: "var(--ag-radius-xs)",
            background: "var(--ag-brand-primary)",
            color: "#fff",
            fontSize: 11,
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          {idx + 1}
        </span>
        <input
          className="ag-input"
          value={v.name}
          style={{
            flex: 1,
            height: 28,
            fontSize: 12,
            fontFamily: "var(--font-mono)",
          }}
          placeholder="variable_name"
          onClick={(e) => e.stopPropagation()}
          onChange={(e) =>
            onChange(v.id, { name: e.target.value.replace(/\s+/g, "_") })
          }
        />
        <select
          className="ag-input"
          value={v.distribution}
          style={{ width: 140, height: 28, fontSize: 11 }}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) =>
            onChange(v.id, { distribution: e.target.value, params: {} })
          }
        >
          {DIST_CATEGORIES.map(({ label, dists }) => (
            <optgroup key={label} label={label}>
              {dists.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        {v.unit && (
          <span className="ag-badge ag-badge--muted" style={{ fontSize: 10 }}>
            {v.unit}
          </span>
        )}
        <i
          className={`fa-solid fa-chevron-${expanded ? "up" : "down"}`}
          style={{ fontSize: 10, color: "var(--ag-text-faint)" }}
        />
        {canRemove && (
          <button
            className="ag-button ag-button--sm"
            style={{ padding: "0 6px", height: 24 }}
            onClick={(e) => {
              e.stopPropagation();
              onRemove(v.id);
            }}
          >
            <i
              className="fa-solid fa-trash"
              style={{ fontSize: 10, color: "var(--ag-danger)" }}
            />
          </button>
        )}
      </div>

      {/* Expanded params */}
      {expanded && (
        <div style={{ padding: "12px 12px 10px" }}>
          {DIST_DESCRIPTIONS[v.distribution] && (
            <p
              className="ag-caption"
              style={{ margin: "0 0 8px", fontStyle: "italic", fontSize: 11 }}
            >
              <i
                className="fa-solid fa-circle-info"
                style={{ marginRight: 5, color: "var(--ag-brand-primary)" }}
              />
              {DIST_DESCRIPTIONS[v.distribution]}
            </p>
          )}

          {/* Standard params */}
          {!isDiscrete && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: `repeat(${Math.min(paramDefs.length, 4)}, 1fr)`,
                gap: 8,
                marginBottom: paramDefs.length > 0 ? 8 : 0,
              }}
            >
              {paramDefs.map((pd) => (
                <div key={pd.key}>
                  <label
                    style={{
                      display: "block",
                      fontSize: 10,
                      fontWeight: 600,
                      color: "var(--ag-text-muted)",
                      marginBottom: 3,
                    }}
                  >
                    {pd.label}
                  </label>
                  <input
                    className="ag-input"
                    value={v.params[pd.key] ?? ""}
                    onChange={(e) =>
                      onChange(v.id, {
                        params: { ...v.params, [pd.key]: e.target.value },
                      })
                    }
                    placeholder={pd.placeholder}
                    style={{ width: "100%", height: 28, fontSize: 12 }}
                  />
                  {pd.hint && (
                    <p
                      className="ag-caption"
                      style={{ margin: "2px 0 0", fontSize: 9 }}
                    >
                      {pd.hint}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Discrete / Categorical */}
          {isDiscrete && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 8,
                marginBottom: 8,
              }}
            >
              <div>
                <label
                  style={{
                    display: "block",
                    fontSize: 10,
                    fontWeight: 600,
                    color: "var(--ag-text-muted)",
                    marginBottom: 3,
                  }}
                >
                  {v.distribution === "categorical"
                    ? "Categories (comma-sep)"
                    : "Values (comma-sep)"}
                </label>
                <input
                  className="ag-input"
                  value={
                    v.distribution === "categorical"
                      ? v.discrete_labels
                      : v.discrete_values
                  }
                  onChange={(e) =>
                    onChange(
                      v.id,
                      v.distribution === "categorical"
                        ? {
                            discrete_labels: e.target.value,
                            discrete_values: e.target.value,
                          }
                        : { discrete_values: e.target.value },
                    )
                  }
                  placeholder={
                    v.distribution === "categorical"
                      ? "Low, Medium, High"
                      : "100, 200, 500"
                  }
                  style={{ width: "100%", height: 28, fontSize: 12 }}
                />
              </div>
              <div>
                <label
                  style={{
                    display: "block",
                    fontSize: 10,
                    fontWeight: 600,
                    color: "var(--ag-text-muted)",
                    marginBottom: 3,
                  }}
                >
                  Probabilities (comma-sep, must sum to 1)
                </label>
                <input
                  className="ag-input"
                  value={v.discrete_probs}
                  onChange={(e) =>
                    onChange(v.id, { discrete_probs: e.target.value })
                  }
                  placeholder="0.3, 0.5, 0.2"
                  style={{ width: "100%", height: 28, fontSize: 12 }}
                />
              </div>
            </div>
          )}

          {/* Unit & Description */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "120px 1fr",
              gap: 8,
            }}
          >
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 10,
                  fontWeight: 600,
                  color: "var(--ag-text-muted)",
                  marginBottom: 3,
                }}
              >
                Unit (optional)
              </label>
              <input
                className="ag-input"
                value={v.unit}
                onChange={(e) => onChange(v.id, { unit: e.target.value })}
                placeholder="USD, %, hours…"
                style={{ width: "100%", height: 28, fontSize: 12 }}
              />
            </div>
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 10,
                  fontWeight: 600,
                  color: "var(--ag-text-muted)",
                  marginBottom: 3,
                }}
              >
                Description (optional)
              </label>
              <input
                className="ag-input"
                value={v.description}
                onChange={(e) =>
                  onChange(v.id, { description: e.target.value })
                }
                placeholder="What does this variable represent?"
                style={{ width: "100%", height: 28, fontSize: 12 }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Correlation row ────────────────────────────────────────────────────────────

interface Correlation {
  id: number;
  var1: string;
  var2: string;
  coefficient: string;
}

// ── Main builder page ─────────────────────────────────────────────────────────

let _id = 0;
function newVar(name = "", dist = "normal"): Variable {
  return {
    id: ++_id,
    name,
    distribution: dist,
    params: {},
    unit: "",
    description: "",
    discrete_values: "",
    discrete_probs: "",
    discrete_labels: "",
  };
}

export default function NewSimulationPage() {
  const router = useRouter();

  // Config
  const [simModel, setSimModel] = useState("monte_carlo");
  const [runs, setRuns] = useState("50000");
  const [seed, setSeed] = useState("");
  const [domain, setDomain] = useState("");
  const [label, setLabel] = useState("");

  // Variables
  const [variables, setVariables] = useState<Variable[]>([
    newVar("revenue", "lognormal"),
    newVar("cost", "triangular"),
  ]);

  // Objective function
  const [objFn, setObjFn] = useState("revenue - cost");
  const [outputLabels, setOutputLabels] = useState("Net Profit");
  const [outputUnits, setOutputUnits] = useState("USD");

  // Correlations
  const [correlations, setCorrelations] = useState<Correlation[]>([]);
  const [showCorr, setShowCorr] = useState(false);

  // Submit
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  // Scoring
  const [wEV, setWEV] = useState("0.6");
  const [wDR, setWDR] = useState("0.4");

  const normalVarNames = variables
    .filter((v) => v.distribution === "normal")
    .map((v) => v.name)
    .filter(Boolean);

  function updateVar(id: number, patch: Partial<Variable>) {
    setVariables((prev) =>
      prev.map((v) => (v.id === id ? { ...v, ...patch } : v)),
    );
  }

  function removeVar(id: number) {
    setVariables((prev) => prev.filter((v) => v.id !== id));
  }

  function addVar() {
    setVariables((prev) => [...prev, newVar(`var_${prev.length + 1}`)]);
  }

  function buildPayload() {
    const variablesPayload = variables.map((v) => {
      const isDiscrete =
        v.distribution === "discrete" || v.distribution === "categorical";
      const params: Record<string, unknown> = {};

      if (isDiscrete) {
        const rawVals =
          v.distribution === "categorical"
            ? (v.discrete_labels || v.discrete_values)
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean)
            : v.discrete_values
                .split(",")
                .map((s) => parseFloat(s.trim()))
                .filter(isFinite);
        const probs = v.discrete_probs
          .split(",")
          .map((s) => parseFloat(s.trim()))
          .filter(isFinite);
        params.values = rawVals;
        params.probabilities = probs;
      } else {
        const defs = DIST_PARAMS[v.distribution] ?? [];
        for (const pd of defs) {
          const raw = v.params[pd.key];
          if (raw !== undefined && raw !== "") {
            params[pd.key] = parseFloat(raw);
          }
        }
        // Defaults for empty params
        if (v.distribution === "normal" && !params.mean) params.mean = 0;
        if (v.distribution === "normal" && !params.std) params.std = 1;
      }

      return {
        name: v.name.trim() || `var_${v.id}`,
        distribution: v.distribution,
        params,
        unit: v.unit,
        description: v.description,
        domain_hint: domain,
        ...(v.distribution === "categorical" && {
          labels: v.discrete_labels
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      };
    });

    const corrPayload = correlations
      .filter((c) => c.var1 && c.var2 && c.coefficient)
      .map((c) => ({
        variables: [c.var1, c.var2],
        coefficient: parseFloat(c.coefficient),
      }));

    const olabels = outputLabels
      .split("|")
      .map((s) => s.trim())
      .filter(Boolean);
    const ounits = outputUnits
      .split("|")
      .map((s) => s.trim())
      .filter(Boolean);

    return {
      mode: "expert" as const,
      simulation_model: simModel,
      runs: parseInt(runs, 10) || 50000,
      seed: seed ? parseInt(seed, 10) : undefined,
      simulation: {
        domain: domain || undefined,
        domain_template: label || undefined,
        variables: variablesPayload,
        correlations: corrPayload.length > 0 ? corrPayload : undefined,
        objective_function: objFn.trim() || undefined,
        output_labels: olabels.length > 0 ? olabels : undefined,
        output_units: ounits.length > 0 ? ounits : undefined,
        scoring: {
          expected_value: parseFloat(wEV) || 0.6,
          downside_risk: parseFloat(wDR) || 0.4,
        },
      },
    };
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (variables.length === 0) {
      setError("Add at least one variable.");
      return;
    }
    if (!objFn.trim()) {
      setError("Objective function is required.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess(false);
    try {
      await simulate(buildPayload());
      setSuccess(true);
      setTimeout(() => router.push("/dashboard/simulations"), 1500);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Simulation failed. Check your configuration.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--ag-bg-canvas)" }}>
      <header
        style={{
          height: "var(--ag-topbar-height)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
          background:
            "linear-gradient(180deg,rgba(255,255,255,0.015),rgba(255,255,255,0)),var(--ag-bg-surface-1)",
          borderBottom: "1px solid var(--ag-border-default)",
          position: "sticky" as const,
          top: 0,
          zIndex: 40,
        }}
      >
        <div>
          <h1 className="ag-page-title">Build Simulation</h1>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="ag-button ag-button--sm"
            onClick={() => router.push("/dashboard/templates")}
          >
            <i className="fa-solid fa-layer-group" style={{ marginRight: 5 }} />
            Browse Templates
          </button>
          <button
            className="ag-button ag-button--sm"
            onClick={() => router.back()}
          >
            <i className="fa-solid fa-arrow-left" style={{ marginRight: 5 }} />
            Back
          </button>
        </div>
      </header>

      <div className="ag-content" style={{ maxWidth: 900 }}>
        <form onSubmit={handleSubmit}>
          {/* Simulation Model */}
          <div className="ag-card" style={{ marginBottom: 16 }}>
            <div style={{ padding: "14px 18px 12px" }}>
              <p className="ag-section-title" style={{ margin: "0 0 10px" }}>
                Simulation Method
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4,1fr)",
                  gap: 8,
                }}
              >
                {SIM_MODELS.map((m) => (
                  <button
                    key={m.value}
                    type="button"
                    onClick={() => setSimModel(m.value)}
                    style={{
                      padding: "10px 12px",
                      borderRadius: "var(--ag-radius-md)",
                      border: `1px solid ${simModel === m.value ? "var(--ag-brand-primary)" : "var(--ag-border-default)"}`,
                      background:
                        simModel === m.value
                          ? "rgba(107,66,252,0.12)"
                          : "var(--ag-bg-surface-0)",
                      color:
                        simModel === m.value
                          ? "var(--ag-brand-primary)"
                          : "var(--ag-text-secondary)",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 7,
                        marginBottom: 4,
                      }}
                    >
                      <i
                        className={`fa-solid ${m.icon}`}
                        style={{ fontSize: 13 }}
                      />
                      <span style={{ fontSize: 12, fontWeight: 700 }}>
                        {m.label}
                      </span>
                    </div>
                    <p
                      className="ag-caption"
                      style={{ margin: 0, fontSize: 10 }}
                    >
                      {m.desc}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Config */}
          <div className="ag-card" style={{ marginBottom: 16 }}>
            <div style={{ padding: "14px 18px 12px" }}>
              <p className="ag-section-title" style={{ margin: "0 0 10px" }}>
                Configuration
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 120px 120px 1fr",
                  gap: 10,
                }}
              >
                <div>
                  <label className="ag-label">
                    Domain / Industry{" "}
                    <span
                      style={{ color: "var(--ag-text-faint)", fontWeight: 400 }}
                    >
                      (optional)
                    </span>
                  </label>
                  <input
                    className="ag-input"
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    placeholder="finance, medical, aerospace…"
                    style={{ width: "100%", height: 34 }}
                  />
                </div>
                <div>
                  <label className="ag-label">Scenarios</label>
                  <select
                    className="ag-input"
                    value={runs}
                    onChange={(e) => setRuns(e.target.value)}
                    style={{ width: "100%", height: 34 }}
                  >
                    {[
                      "1000",
                      "5000",
                      "10000",
                      "50000",
                      "100000",
                      "500000",
                      "1000000",
                    ].map((r) => (
                      <option key={r} value={r}>
                        {parseInt(r).toLocaleString()}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="ag-label">
                    Seed{" "}
                    <span
                      style={{ color: "var(--ag-text-faint)", fontWeight: 400 }}
                    >
                      (optional)
                    </span>
                  </label>
                  <input
                    className="ag-input"
                    value={seed}
                    onChange={(e) => setSeed(e.target.value)}
                    placeholder="42"
                    style={{ width: "100%", height: 34 }}
                  />
                </div>
                <div>
                  <label className="ag-label">
                    Simulation Label{" "}
                    <span
                      style={{ color: "var(--ag-text-faint)", fontWeight: 400 }}
                    >
                      (optional)
                    </span>
                  </label>
                  <input
                    className="ag-input"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder="Q4 NPV Analysis"
                    style={{ width: "100%", height: 34 }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Variables */}
          <div className="ag-card" style={{ marginBottom: 16 }}>
            <div style={{ padding: "14px 18px 4px" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 12,
                }}
              >
                <div>
                  <p className="ag-section-title" style={{ margin: 0 }}>
                    Variables
                    <span
                      className="ag-badge ag-badge--muted"
                      style={{ marginLeft: 8, fontSize: 11 }}
                    >
                      {variables.length}
                    </span>
                  </p>
                  <p className="ag-caption" style={{ margin: "2px 0 0" }}>
                    Add any number of input variables. Names are used in the
                    objective function.
                  </p>
                </div>
                <button
                  type="button"
                  className="ag-button ag-button--sm ag-button--primary"
                  onClick={addVar}
                >
                  <i className="fa-solid fa-plus" style={{ marginRight: 5 }} />
                  Add Variable
                </button>
              </div>

              {variables.length === 0 && (
                <div
                  style={{
                    textAlign: "center",
                    padding: "24px 0",
                    color: "var(--ag-text-muted)",
                  }}
                >
                  <i
                    className="fa-solid fa-variable"
                    style={{ fontSize: 24, display: "block", marginBottom: 8 }}
                  />
                  No variables yet. Click "Add Variable" to start.
                </div>
              )}

              {variables.map((v, idx) => (
                <VariableRow
                  key={v.id}
                  v={v}
                  idx={idx}
                  onChange={updateVar}
                  onRemove={removeVar}
                  canRemove={variables.length > 1}
                />
              ))}
            </div>
          </div>

          {/* Objective function */}
          <div className="ag-card" style={{ marginBottom: 16 }}>
            <div style={{ padding: "14px 18px 14px" }}>
              <p className="ag-section-title" style={{ margin: "0 0 4px" }}>
                Objective Function
              </p>
              <p className="ag-caption" style={{ margin: "0 0 10px" }}>
                Expression evaluated per scenario. Use variable names as
                symbols. Separate multiple outputs with{" "}
                <code
                  style={{
                    background: "var(--ag-bg-surface-0)",
                    padding: "1px 4px",
                    borderRadius: 3,
                  }}
                >
                  |
                </code>
                . Supports:{" "}
                <code
                  style={{
                    background: "var(--ag-bg-surface-0)",
                    padding: "1px 4px",
                    borderRadius: 3,
                    fontSize: 10,
                  }}
                >
                  + - * / ^ % ln() exp() sqrt() abs() floor() ceil() min(a,b)
                  max(a,b) clip(v,lo,hi) if(cond,then,else)
                </code>
              </p>
              <textarea
                className="ag-input"
                value={objFn}
                onChange={(e) => setObjFn(e.target.value)}
                rows={3}
                style={{
                  width: "100%",
                  fontFamily: "var(--font-mono)",
                  fontSize: 13,
                  lineHeight: "1.6",
                  resize: "vertical",
                }}
                placeholder="revenue - cost | (revenue - cost) / revenue * 100 | min(cash_flow, 0)"
              />
              {/* Variable chip hints */}
              {variables.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 4,
                    marginTop: 8,
                  }}
                >
                  {variables
                    .map((v) => v.name.trim())
                    .filter(Boolean)
                    .map((name) => (
                      <button
                        key={name}
                        type="button"
                        style={{
                          padding: "2px 8px",
                          borderRadius: "var(--ag-radius-xs)",
                          border: "1px solid var(--ag-border-default)",
                          background: "var(--ag-bg-surface-0)",
                          color: "var(--ag-brand-primary)",
                          fontSize: 11,
                          fontFamily: "var(--font-mono)",
                          cursor: "pointer",
                        }}
                        onClick={() =>
                          setObjFn(
                            (prev) => prev + (prev.trim() ? " + " : "") + name,
                          )
                        }
                      >
                        + {name}
                      </button>
                    ))}
                </div>
              )}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 10,
                  marginTop: 10,
                }}
              >
                <div>
                  <label className="ag-label">
                    Output Labels{" "}
                    <span
                      style={{ color: "var(--ag-text-faint)", fontWeight: 400 }}
                    >
                      (separate with |)
                    </span>
                  </label>
                  <input
                    className="ag-input"
                    value={outputLabels}
                    onChange={(e) => setOutputLabels(e.target.value)}
                    placeholder="Net Profit | Margin % | Cash Flow"
                    style={{
                      width: "100%",
                      height: 34,
                      fontFamily: "var(--font-mono)",
                      fontSize: 12,
                    }}
                  />
                </div>
                <div>
                  <label className="ag-label">
                    Output Units{" "}
                    <span
                      style={{ color: "var(--ag-text-faint)", fontWeight: 400 }}
                    >
                      (separate with |)
                    </span>
                  </label>
                  <input
                    className="ag-input"
                    value={outputUnits}
                    onChange={(e) => setOutputUnits(e.target.value)}
                    placeholder="USD | % | USD"
                    style={{
                      width: "100%",
                      height: 34,
                      fontFamily: "var(--font-mono)",
                      fontSize: 12,
                    }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Correlations (collapsible) */}
          <div className="ag-card" style={{ marginBottom: 16 }}>
            <div style={{ padding: "12px 18px" }}>
              <button
                type="button"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--ag-text-secondary)",
                  fontSize: 13,
                  fontWeight: 600,
                  padding: 0,
                }}
                onClick={() => setShowCorr((x) => !x)}
              >
                <i
                  className={`fa-solid fa-chevron-${showCorr ? "up" : "down"}`}
                  style={{ fontSize: 10 }}
                />
                Correlations (Cholesky)
                <span
                  className="ag-badge ag-badge--muted"
                  style={{ fontSize: 10, marginLeft: 4 }}
                >
                  {correlations.length > 0
                    ? `${correlations.length} configured`
                    : "Optional"}
                </span>
              </button>

              {showCorr && (
                <div style={{ marginTop: 12 }}>
                  <p className="ag-caption" style={{ margin: "0 0 10px" }}>
                    Correlate Normal variables via Cholesky decomposition.
                    Coefficient: -1 (perfect negative) to +1 (perfect positive).
                  </p>
                  {normalVarNames.length < 2 && (
                    <p
                      className="ag-caption"
                      style={{ color: "var(--ag-warning)" }}
                    >
                      <i
                        className="fa-solid fa-triangle-exclamation"
                        style={{ marginRight: 5 }}
                      />
                      Correlations apply to Normal variables only. Add at least
                      2 Normal variables.
                    </p>
                  )}
                  {correlations.map((c, i) => (
                    <div
                      key={c.id}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr 120px 32px",
                        gap: 8,
                        marginBottom: 6,
                      }}
                    >
                      <select
                        className="ag-input"
                        value={c.var1}
                        onChange={(e) =>
                          setCorrelations((prev) =>
                            prev.map((x) =>
                              x.id === c.id
                                ? { ...x, var1: e.target.value }
                                : x,
                            ),
                          )
                        }
                        style={{ height: 32 }}
                      >
                        <option value="">Variable 1</option>
                        {normalVarNames.map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                      </select>
                      <select
                        className="ag-input"
                        value={c.var2}
                        onChange={(e) =>
                          setCorrelations((prev) =>
                            prev.map((x) =>
                              x.id === c.id
                                ? { ...x, var2: e.target.value }
                                : x,
                            ),
                          )
                        }
                        style={{ height: 32 }}
                      >
                        <option value="">Variable 2</option>
                        {normalVarNames
                          .filter((n) => n !== c.var1)
                          .map((n) => (
                            <option key={n} value={n}>
                              {n}
                            </option>
                          ))}
                      </select>
                      <input
                        className="ag-input"
                        value={c.coefficient}
                        onChange={(e) =>
                          setCorrelations((prev) =>
                            prev.map((x) =>
                              x.id === c.id
                                ? { ...x, coefficient: e.target.value }
                                : x,
                            ),
                          )
                        }
                        placeholder="0.7"
                        style={{ height: 32, textAlign: "center" }}
                      />
                      <button
                        type="button"
                        className="ag-button ag-button--sm"
                        style={{ height: 32, padding: "0 8px" }}
                        onClick={() =>
                          setCorrelations((prev) =>
                            prev.filter((x) => x.id !== c.id),
                          )
                        }
                      >
                        <i
                          className="fa-solid fa-xmark"
                          style={{ fontSize: 11, color: "var(--ag-danger)" }}
                        />
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="ag-button ag-button--sm"
                    onClick={() =>
                      setCorrelations((prev) => [
                        ...prev,
                        { id: ++_id, var1: "", var2: "", coefficient: "0.5" },
                      ])
                    }
                    disabled={normalVarNames.length < 2}
                  >
                    <i
                      className="fa-solid fa-plus"
                      style={{ marginRight: 5 }}
                    />
                    Add Correlation
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Scoring */}
          <div className="ag-card" style={{ marginBottom: 16 }}>
            <div style={{ padding: "12px 18px" }}>
              <p className="ag-section-title" style={{ margin: "0 0 8px" }}>
                Decision Scoring Weights
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 10,
                }}
              >
                <div>
                  <label className="ag-label">Expected Value Weight</label>
                  <input
                    className="ag-input"
                    value={wEV}
                    onChange={(e) => setWEV(e.target.value)}
                    placeholder="0.6"
                    style={{ width: "100%", height: 34 }}
                  />
                </div>
                <div>
                  <label className="ag-label">Downside Risk Weight</label>
                  <input
                    className="ag-input"
                    value={wDR}
                    onChange={(e) => setWDR(e.target.value)}
                    placeholder="0.4"
                    style={{ width: "100%", height: 34 }}
                  />
                  <p
                    className="ag-caption"
                    style={{ margin: "2px 0 0", fontSize: 10 }}
                  >
                    Must sum to 1.0
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Errors / Success */}
          {error && (
            <div
              style={{
                padding: "10px 14px",
                background: "var(--ag-danger-soft)",
                border: "1px solid rgba(239,68,68,0.2)",
                borderRadius: "var(--ag-radius-md)",
                marginBottom: 12,
                fontSize: 13,
                color: "var(--ag-danger)",
              }}
            >
              <i
                className="fa-solid fa-circle-exclamation"
                style={{ marginRight: 6 }}
              />
              {error}
            </div>
          )}
          {success && (
            <div
              style={{
                padding: "10px 14px",
                background: "var(--ag-success-soft)",
                border: "1px solid rgba(0,211,149,0.25)",
                borderRadius: "var(--ag-radius-md)",
                marginBottom: 12,
                fontSize: 13,
                color: "var(--ag-success)",
              }}
            >
              <i
                className="fa-solid fa-circle-check"
                style={{ marginRight: 6 }}
              />
              Simulation submitted! Redirecting to results…
            </div>
          )}

          {/* Submit */}
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 10,
              paddingBottom: 32,
            }}
          >
            <button
              type="button"
              className="ag-button ag-button--sm"
              onClick={() => router.back()}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="ag-button ag-button--sm ag-button--primary"
              disabled={submitting}
              style={{ minWidth: 160 }}
            >
              <i
                className={`fa-solid ${submitting ? "fa-spinner fa-spin" : "fa-rocket"}`}
                style={{ marginRight: 6 }}
              />
              {submitting
                ? "Running in Mojo…"
                : `Run ${parseInt(runs).toLocaleString()} Scenarios`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
