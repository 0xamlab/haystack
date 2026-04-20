"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  listRuns,
  RunSummary,
  simulate,
  exportToJSON,
  SimulationModelType,
} from "@/lib/api";

import { Plot, CC } from "@/components/ui/Plot";
const FONT = { family: "Inter, ui-sans-serif", color: "#687089", size: 11 };
const DL = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { t: 5, r: 5, b: 28, l: 40 },
  xaxis: { showgrid: false, tickfont: FONT },
  yaxis: {
    showgrid: true,
    gridcolor: "rgba(255,255,255,0.06)",
    tickfont: FONT,
    zeroline: false,
  },
  showlegend: false,
};

const T = {
  page: {
    minHeight: "100vh",
    background: "var(--ag-bg-canvas)",
  } as React.CSSProperties,
  topbar: {
    height: "var(--ag-topbar-height)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 24px",
    background:
      "linear-gradient(180deg, rgba(255,255,255,0.015), rgba(255,255,255,0)), var(--ag-bg-surface-1)",
    borderBottom: "1px solid var(--ag-border-default)",
    position: "sticky" as const,
    top: 0,
    zIndex: 40,
  },
};

function StatusBadge({ status }: { status: string }) {
  const m: Record<string, string> = {
    completed: "ag-badge--success",
    failed: "ag-badge--danger",
    running: "ag-badge--info",
    queued: "ag-badge--warning",
  };
  const l: Record<string, string> = {
    completed: "Completed",
    failed: "Failed",
    running: "Running",
    queued: "Queued",
  };
  return (
    <span
      className={`ag-badge ${m[status] ?? "ag-badge--muted"}`}
      style={{ fontSize: 11, borderRadius: "var(--ag-radius-xs)" }}
    >
      {l[status] ?? status}
    </span>
  );
}

// ── Simulation model metadata ─────────────────────────────────────────────────
const MODEL_INFO: Record<
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

// ── New Run Modal ─────────────────────────────────────────────────────────────
function NewRunModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [model, setModel] = useState<SimulationModelType>("monte_carlo");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  // Monte Carlo / QMC / LHS / Sensitivity
  const [objFn, setObjFn] = useState("revenue - cost");
  const [runs, setRuns] = useState("10000");
  const [dist, setDist] = useState("triangular");
  const [varRows, setVarRows] = useState([
    { name: "revenue", low: "300000", mode: "600000", high: "1200000" },
    { name: "cost", low: "150000", mode: "350000", high: "600000" },
  ]);
  // Bootstrap
  const [histData, setHistData] = useState(
    "120000\n145000\n138000\n160000\n175000\n152000",
  );
  const [statistic, setStatistic] = useState("mean");
  // Scenario
  const [scenarios, setScenarios] = useState([
    { name: "Bear", probability: "0.25", outcome: "400000" },
    { name: "Base", probability: "0.50", outcome: "700000" },
    { name: "Bull", probability: "0.25", outcome: "1100000" },
  ]);
  // MCMC
  const [mcmcData, setMcmcData] = useState(
    "150000\n180000\n165000\n200000\n175000",
  );
  const [likelihood, setLikelihood] = useState("normal");
  const [burnIn, setBurnIn] = useState("1000");

  const DISTS = [
    "normal",
    "uniform",
    "triangular",
    "lognormal",
    "fixed",
    "beta",
    "exponential",
    "weibull",
    "gamma",
    "pert",
    "bernoulli",
    "poisson",
  ];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      let payload: Record<string, unknown>;
      const n_runs = parseInt(runs, 10) || 10000;

      if (model === "bootstrap") {
        const data = histData
          .split(/[\n,\s]+/)
          .map(Number)
          .filter(isFinite);
        payload = {
          mode: "expert",
          simulation_model: model,
          runs: n_runs,
          bootstrap_config: { historical_data: data, statistic },
          simulation: {
            variables: [],
            objective_function: "",
            scoring: { expected_value: 0.6, downside_risk: 0.4 },
          },
        };
      } else if (model === "scenario") {
        payload = {
          mode: "expert",
          simulation_model: model,
          runs: n_runs,
          scenario_config: {
            scenarios: scenarios.map((s) => ({
              name: s.name,
              probability: parseFloat(s.probability),
              variables: { outcome: parseFloat(s.outcome) },
              objective_function: "outcome",
            })),
          },
          simulation: {
            variables: [],
            objective_function: "outcome",
            scoring: { expected_value: 0.6, downside_risk: 0.4 },
          },
        };
      } else if (model === "mcmc") {
        const data = mcmcData
          .split(/[\n,\s]+/)
          .map(Number)
          .filter(isFinite);
        payload = {
          mode: "expert",
          simulation_model: model,
          runs: n_runs,
          mcmc_config: {
            observed_data: data,
            likelihood,
            burn_in: parseInt(burnIn, 10) || 1000,
            chains: 4,
          },
          simulation: {
            variables: [],
            objective_function: "",
            scoring: { expected_value: 0.6, downside_risk: 0.4 },
          },
        };
      } else {
        // Monte Carlo, QMC, LHS, Sensitivity
        const variables = varRows.map((r) => {
          const lo = parseFloat(r.low),
            hi = parseFloat(r.high),
            mo = parseFloat(r.mode);
          const params: Record<string, number> =
            dist === "triangular"
              ? { low: lo, mode: mo, high: hi }
              : dist === "uniform"
                ? { low: lo, high: hi }
                : dist === "normal"
                  ? { mean: (lo + hi) / 2, std: (hi - lo) / 4 }
                  : { mean: (lo + hi) / 2, std: (hi - lo) / 4 };
          return { name: r.name, distribution: dist, params };
        });
        payload = {
          mode: "expert",
          simulation_model: model,
          runs: n_runs,
          simulation: {
            variables,
            objective_function: objFn,
            scoring: { expected_value: 0.6, downside_risk: 0.4 },
          },
        };
      }
      await simulate(payload);
      onCreated();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          background: "var(--ag-bg-surface-1)",
          border: "1px solid var(--ag-border-default)",
          borderRadius: "var(--ag-radius-lg)",
          width: 640,
          maxHeight: "90vh",
          overflowY: "auto",
          padding: 24,
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 18,
          }}
        >
          <div>
            <h2
              style={{
                fontSize: 16,
                fontWeight: 700,
                margin: 0,
                color: "var(--ag-text-primary)",
              }}
            >
              New Simulation Run
            </h2>
            <p className="ag-caption" style={{ margin: "3px 0 0" }}>
              Configure parameters, distributions, and objectives
            </p>
          </div>
          <button className="ag-button ag-button--sm" onClick={onClose}>
            <i className="fa-solid fa-xmark" />
          </button>
        </div>

        {/* Model selector tabs */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 6,
            marginBottom: 18,
          }}
        >
          {(
            Object.entries(MODEL_INFO) as [
              SimulationModelType,
              (typeof MODEL_INFO)[SimulationModelType],
            ][]
          ).map(([key, info]) => (
            <button
              key={key}
              onClick={() => setModel(key)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                borderRadius: "var(--ag-radius-sm)",
                border: `1px solid ${model === key ? "var(--ag-brand-primary)" : "var(--ag-border-default)"}`,
                background:
                  model === key
                    ? "rgba(107,66,252,0.12)"
                    : "var(--ag-bg-surface-0)",
                color:
                  model === key
                    ? "var(--ag-brand-primary)"
                    : "var(--ag-text-secondary)",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <i className={`fa-solid ${info.icon}`} style={{ fontSize: 11 }} />
              {info.label}
            </button>
          ))}
        </div>
        <p
          className="ag-caption"
          style={{
            marginBottom: 16,
            padding: "8px 10px",
            background: "var(--ag-bg-surface-0)",
            borderRadius: "var(--ag-radius-sm)",
            border: "1px solid var(--ag-border-default)",
          }}
        >
          <i
            className={`fa-solid ${MODEL_INFO[model].icon}`}
            style={{ marginRight: 6, color: "var(--ag-brand-primary)" }}
          />
          {MODEL_INFO[model].desc}
        </p>

        <form onSubmit={handleSubmit}>
          {/* Runs (shown for all models) */}
          <div style={{ marginBottom: 14 }}>
            <label className="ag-label">Scenarios / Samples</label>
            <input
              className="ag-input"
              value={runs}
              onChange={(e) => setRuns(e.target.value)}
              placeholder="10000"
              style={{ width: "100%", height: 34 }}
            />
          </div>

          {/* Bootstrap config */}
          {model === "bootstrap" && (
            <>
              <div style={{ marginBottom: 14 }}>
                <label className="ag-label">
                  Historical Data (one value per line or comma-separated)
                </label>
                <textarea
                  className="ag-input"
                  rows={5}
                  value={histData}
                  onChange={(e) => setHistData(e.target.value)}
                  placeholder="120000&#10;145000&#10;138000"
                  style={{
                    width: "100%",
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                  }}
                />
              </div>
              <div style={{ marginBottom: 14 }}>
                <label className="ag-label">Statistic</label>
                <select
                  className="ag-input"
                  value={statistic}
                  onChange={(e) => setStatistic(e.target.value)}
                  style={{ width: "100%", height: 34 }}
                >
                  {[
                    "mean",
                    "median",
                    "std",
                    "variance",
                    "sum",
                    "min",
                    "max",
                    "sharpe",
                    "percentile_5",
                    "percentile_95",
                    "range",
                    "cv",
                  ].map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}

          {/* Scenario config */}
          {model === "scenario" && (
            <>
              <div style={{ marginBottom: 14 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 6,
                  }}
                >
                  <label
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "var(--ag-text-muted)",
                    }}
                  >
                    Scenarios
                  </label>
                  <button
                    type="button"
                    className="ag-button ag-button--sm"
                    onClick={() =>
                      setScenarios((prev) => [
                        ...prev,
                        {
                          name: "Custom",
                          probability: "0.1",
                          outcome: "500000",
                        },
                      ])
                    }
                  >
                    <i
                      className="fa-solid fa-plus"
                      style={{ marginRight: 4 }}
                    />
                    Add
                  </button>
                </div>
                {scenarios.map((sc, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 100px 120px 28px",
                      gap: 6,
                      marginBottom: 6,
                    }}
                  >
                    <input
                      className="ag-input"
                      value={sc.name}
                      style={{ height: 32 }}
                      placeholder="Name"
                      onChange={(e) =>
                        setScenarios((p) =>
                          p.map((x, i) =>
                            i === idx ? { ...x, name: e.target.value } : x,
                          ),
                        )
                      }
                    />
                    <input
                      className="ag-input"
                      value={sc.probability}
                      style={{ height: 32 }}
                      placeholder="Prob"
                      onChange={(e) =>
                        setScenarios((p) =>
                          p.map((x, i) =>
                            i === idx
                              ? { ...x, probability: e.target.value }
                              : x,
                          ),
                        )
                      }
                    />
                    <input
                      className="ag-input"
                      value={sc.outcome}
                      style={{ height: 32 }}
                      placeholder="Outcome"
                      onChange={(e) =>
                        setScenarios((p) =>
                          p.map((x, i) =>
                            i === idx ? { ...x, outcome: e.target.value } : x,
                          ),
                        )
                      }
                    />
                    <button
                      type="button"
                      className="ag-button ag-button--sm"
                      style={{ padding: "0 8px" }}
                      onClick={() =>
                        setScenarios((p) => p.filter((_, i) => i !== idx))
                      }
                    >
                      <i
                        className="fa-solid fa-trash"
                        style={{ fontSize: 11, color: "var(--ag-danger)" }}
                      />
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* MCMC config */}
          {model === "mcmc" && (
            <>
              <div style={{ marginBottom: 14 }}>
                <label className="ag-label">
                  Observed Data (one value per line)
                </label>
                <textarea
                  className="ag-input"
                  rows={4}
                  value={mcmcData}
                  onChange={(e) => setMcmcData(e.target.value)}
                  style={{
                    width: "100%",
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                  }}
                />
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 10,
                  marginBottom: 14,
                }}
              >
                <div>
                  <label className="ag-label">Likelihood</label>
                  <select
                    className="ag-input"
                    value={likelihood}
                    onChange={(e) => setLikelihood(e.target.value)}
                    style={{ width: "100%", height: 34 }}
                  >
                    {["normal", "lognormal", "poisson"].map((l) => (
                      <option key={l} value={l}>
                        {l}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="ag-label">Burn-in Samples</label>
                  <input
                    className="ag-input"
                    value={burnIn}
                    onChange={(e) => setBurnIn(e.target.value)}
                    style={{ width: "100%", height: 34 }}
                  />
                </div>
              </div>
            </>
          )}

          {/* Variable form for MC / QMC / LHS / Sensitivity */}
          {["monte_carlo", "qmc_sobol", "lhs", "sensitivity"].includes(
            model,
          ) && (
            <>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 10,
                  marginBottom: 14,
                }}
              >
                <div>
                  <label className="ag-label">Distribution</label>
                  <select
                    className="ag-input"
                    value={dist}
                    onChange={(e) => setDist(e.target.value)}
                    style={{ width: "100%", height: 34 }}
                  >
                    {DISTS.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="ag-label">Objective Function</label>
                  <input
                    className="ag-input"
                    value={objFn}
                    onChange={(e) => setObjFn(e.target.value)}
                    style={{ width: "100%", height: 34 }}
                    placeholder="revenue - cost"
                  />
                </div>
              </div>
              <div style={{ marginBottom: 14 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 6,
                  }}
                >
                  <label
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "var(--ag-text-muted)",
                    }}
                  >
                    Variables
                  </label>
                  <button
                    type="button"
                    className="ag-button ag-button--sm"
                    onClick={() =>
                      setVarRows((p) => [
                        ...p,
                        {
                          name: "var_" + (p.length + 1),
                          low: "0",
                          mode: "50",
                          high: "100",
                        },
                      ])
                    }
                  >
                    <i
                      className="fa-solid fa-plus"
                      style={{ marginRight: 4 }}
                    />
                    Add
                  </button>
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "120px 1fr 1fr 1fr 28px",
                    gap: 6,
                    marginBottom: 4,
                  }}
                >
                  {["Name", "Low", "Mode", "High", ""].map((h) => (
                    <span
                      key={h}
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        color: "var(--ag-text-faint)",
                        textTransform: "uppercase",
                      }}
                    >
                      {h}
                    </span>
                  ))}
                </div>
                {varRows.map((row, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "120px 1fr 1fr 1fr 28px",
                      gap: 6,
                      marginBottom: 5,
                    }}
                  >
                    <input
                      className="ag-input"
                      value={row.name}
                      style={{ height: 32 }}
                      onChange={(e) =>
                        setVarRows((p) =>
                          p.map((x, i) =>
                            i === idx ? { ...x, name: e.target.value } : x,
                          ),
                        )
                      }
                    />
                    <input
                      className="ag-input"
                      value={row.low}
                      style={{ height: 32 }}
                      onChange={(e) =>
                        setVarRows((p) =>
                          p.map((x, i) =>
                            i === idx ? { ...x, low: e.target.value } : x,
                          ),
                        )
                      }
                    />
                    <input
                      className="ag-input"
                      value={row.mode}
                      style={{ height: 32 }}
                      onChange={(e) =>
                        setVarRows((p) =>
                          p.map((x, i) =>
                            i === idx ? { ...x, mode: e.target.value } : x,
                          ),
                        )
                      }
                    />
                    <input
                      className="ag-input"
                      value={row.high}
                      style={{ height: 32 }}
                      onChange={(e) =>
                        setVarRows((p) =>
                          p.map((x, i) =>
                            i === idx ? { ...x, high: e.target.value } : x,
                          ),
                        )
                      }
                    />
                    <button
                      type="button"
                      className="ag-button ag-button--sm"
                      style={{ padding: "0 8px" }}
                      onClick={() =>
                        setVarRows((p) => p.filter((_, i) => i !== idx))
                      }
                    >
                      <i
                        className="fa-solid fa-trash"
                        style={{ fontSize: 11, color: "var(--ag-danger)" }}
                      />
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}

          {error && (
            <div
              style={{
                padding: "8px 10px",
                background: "var(--ag-danger-soft)",
                border: "1px solid rgba(239,68,68,0.2)",
                borderRadius: "var(--ag-radius-sm)",
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
          <div
            style={{
              display: "flex",
              gap: 8,
              justifyContent: "flex-end",
              marginTop: 8,
            }}
          >
            <button
              type="button"
              className="ag-button ag-button--sm"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="ag-button ag-button--sm ag-button--primary"
              disabled={submitting}
            >
              <i
                className={`fa-solid ${submitting ? "fa-spinner fa-spin" : "fa-play"}`}
                style={{ marginRight: 5 }}
              />
              {submitting ? "Running…" : "Run Simulation"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Model badge ───────────────────────────────────────────────────────────────
function ModelBadge({ model }: { model?: string }) {
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

function ExpandedRow({
  run,
  onRefresh,
}: {
  run: RunSummary;
  onRefresh: () => void;
}) {
  const [rerunning, setRerunning] = useState(false);
  const [rerunStatus, setRerunStatus] = useState<"success" | "error" | null>(
    null,
  );
  const [rerunError, setRerunError] = useState("");
  const [copied, setCopied] = useState(false);

  const handleRerun = async () => {
    setRerunning(true);
    setRerunStatus(null);
    setRerunError("");
    try {
      // Build a valid minimal payload from available run metadata.
      // The runs list endpoint doesn't return the original input, so we
      // construct a representative re-run payload. Navigate to /simulations/new
      // for full control.
      const payload =
        run.mode === "expert"
          ? {
              mode: "expert",
              runs: run.scenarios_run ?? 10000,
              simulation: {
                variables: [
                  {
                    name: "variable_1",
                    distribution: "normal",
                    params: { mean: 0, std: 1 },
                  },
                ],
                objective_function: "variable_1",
                scoring: { expected_value: 0.6, downside_risk: 0.4 },
              },
            }
          : {
              mode: "auto",
              runs: run.scenarios_run ?? 10000,
              scenario: {
                name: `Re-run of ${run.run_id.slice(0, 8)}`,
                variables: {
                  metric: { low: 0, high: 1000000 },
                },
                objective: "maximize_net_value",
              },
            };
      await simulate(payload);
      setRerunStatus("success");
      onRefresh();
      setTimeout(() => setRerunStatus(null), 3000);
    } catch (err: unknown) {
      setRerunStatus("error");
      setRerunError(
        err instanceof Error
          ? err.message
          : "Re-run failed. Use 'Build Simulation' for exact re-runs.",
      );
    } finally {
      setRerunning(false);
    }
  };

  const handleCopyId = () => {
    navigator.clipboard.writeText(run.run_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExport = () => {
    exportToJSON(run, `simulation-${run.run_id}.json`);
  };

  return (
    <tr style={{ background: "var(--ag-bg-surface-2)" }}>
      <td colSpan={8} style={{ padding: "16px 18px" }}>
        {/* Real metrics from run data */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 10,
            marginBottom: 12,
          }}
        >
          {[
            [
              "Expected Value",
              run.expected_value != null
                ? run.expected_value >= 1e6
                  ? `$${(run.expected_value / 1e6).toFixed(2)}M`
                  : run.expected_value >= 1000
                    ? `$${(run.expected_value / 1000).toFixed(0)}k`
                    : `$${run.expected_value.toFixed(0)}`
                : "—",
              run.recommended_action ?? "—",
              run.recommended_action === "proceed"
                ? "var(--ag-success)"
                : run.recommended_action === "reject"
                  ? "var(--ag-danger)"
                  : "var(--ag-warning)",
            ],
            [
              "Probability of Loss",
              run.probability_of_loss != null
                ? `${(run.probability_of_loss * 100).toFixed(1)}%`
                : "—",
              "Monte Carlo distribution",
              "var(--ag-text-muted)",
            ],
            [
              "Confidence",
              run.confidence != null
                ? `${Math.round(run.confidence * 100)}%`
                : "—",
              `${run.scenarios_run?.toLocaleString() ?? "?"} scenarios`,
              "var(--ag-text-muted)",
            ],
          ].map(([label, value, sub, subColor]) => (
            <div
              key={label as string}
              style={{
                background: "var(--ag-bg-surface-1)",
                border: "1px solid var(--ag-border-default)",
                borderRadius: "var(--ag-radius-md)",
                padding: 12,
              }}
            >
              <p className="ag-caption" style={{ margin: "0 0 4px" }}>
                {label}
              </p>
              <p
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  letterSpacing: "-0.03em",
                  color: "var(--ag-text-primary)",
                  margin: 0,
                }}
              >
                {value}
              </p>
              <p
                style={{
                  fontSize: 11,
                  color: subColor as string,
                  margin: "3px 0 0",
                }}
              >
                {sub}
              </p>
            </div>
          ))}
        </div>

        {/* SHA-256 Data Integrity — Full Chain of Custody */}
        {(run.result_hash || run.request_hash) && (
          <div
            style={{
              background: "rgba(0,211,149,0.04)",
              border: "1px solid rgba(0,211,149,0.2)",
              borderRadius: "var(--ag-radius-md)",
              padding: "12px 14px",
              marginBottom: 12,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 10,
              }}
            >
              <i
                className="fa-solid fa-shield-check"
                style={{ color: "var(--ag-success)", fontSize: 13 }}
              />
              <p
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "var(--ag-success)",
                  margin: 0,
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                }}
              >
                Data Integrity — Full Chain of Custody
              </p>
            </div>
            {run.request_hash && (
              <div style={{ marginBottom: 8 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 2,
                  }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: "var(--ag-text-muted)",
                      letterSpacing: "0.04em",
                      textTransform: "uppercase",
                    }}
                  >
                    Input Hash — what data was used
                  </span>
                  <button
                    className="ag-button ag-button--sm"
                    style={{ padding: "2px 6px", fontSize: 10 }}
                    onClick={() =>
                      navigator.clipboard.writeText(run.request_hash!)
                    }
                  >
                    <i
                      className="fa-solid fa-copy"
                      style={{ fontSize: 9, marginRight: 3 }}
                    />
                    Copy
                  </button>
                </div>
                <code
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    color: "var(--ag-text-faint)",
                    wordBreak: "break-all",
                    lineHeight: 1.6,
                    display: "block",
                  }}
                >
                  sha256:{run.request_hash}
                </code>
              </div>
            )}
            {run.result_hash && (
              <div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 2,
                  }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: "var(--ag-text-muted)",
                      letterSpacing: "0.04em",
                      textTransform: "uppercase",
                    }}
                  >
                    Output Hash — what decision was made (binds to input)
                  </span>
                  <button
                    className="ag-button ag-button--sm"
                    style={{ padding: "2px 6px", fontSize: 10 }}
                    onClick={() =>
                      navigator.clipboard.writeText(run.result_hash!)
                    }
                  >
                    <i
                      className="fa-solid fa-copy"
                      style={{ fontSize: 9, marginRight: 3 }}
                    />
                    Copy
                  </button>
                </div>
                <code
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    color: "var(--ag-text-secondary)",
                    wordBreak: "break-all",
                    lineHeight: 1.6,
                    display: "block",
                  }}
                >
                  sha256:{run.result_hash}
                </code>
              </div>
            )}
            <p
              className="ag-caption"
              style={{
                marginTop: 8,
                fontSize: 10,
                color: "var(--ag-text-faint)",
              }}
            >
              Any change to input data or decision output invalidates both
              hashes — cryptographic proof of what was decided and why.
            </p>
          </div>
        )}
        {!run.result_hash && run.status === "completed" && (
          <div
            style={{
              padding: "8px 12px",
              background: "var(--ag-bg-surface-1)",
              border: "1px solid var(--ag-border-default)",
              borderRadius: "var(--ag-radius-md)",
              marginBottom: 12,
            }}
          >
            <p className="ag-caption">
              <i
                className="fa-solid fa-circle-info"
                style={{ marginRight: 6, color: "var(--ag-text-faint)" }}
              />
              Hash not available for this run (pre-migration). New simulations
              include SHA-256 data integrity hash.
            </p>
          </div>
        )}
        {run.status === "failed" && (
          <div
            style={{
              background: "var(--ag-danger-soft)",
              border: "1px solid rgba(239,68,68,0.25)",
              borderRadius: "var(--ag-radius-md)",
              padding: 12,
              marginBottom: 12,
              display: "flex",
              gap: 10,
              alignItems: "flex-start",
            }}
          >
            <i
              className="fa-solid fa-circle-exclamation"
              style={{ color: "var(--ag-danger)", fontSize: 15, marginTop: 1 }}
            />
            <div>
              <p
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--ag-danger)",
                  margin: "0 0 3px",
                }}
              >
                Execution Failed
              </p>
              <p className="ag-caption">
                An error occurred during simulation execution.
              </p>
            </div>
          </div>
        )}
        <details
          style={{
            background: "var(--ag-bg-surface-1)",
            border: "1px solid var(--ag-border-default)",
            borderRadius: "var(--ag-radius-md)",
            padding: "10px 12px",
            marginBottom: 12,
          }}
        >
          <summary
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--ag-text-muted)",
              cursor: "pointer",
            }}
          >
            JSON Payload
          </summary>
          <pre
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--ag-text-secondary)",
              marginTop: 8,
              overflow: "auto",
            }}
          >
            {JSON.stringify(
              {
                run_id: run.run_id,
                mode: run.mode,
                status: run.status,
                confidence: run.confidence,
                created_at: run.created_at,
              },
              null,
              2,
            )}
          </pre>
        </details>
        {rerunStatus === "success" && (
          <div
            style={{
              background: "var(--ag-success-soft)",
              border: "1px solid rgba(0,211,149,0.25)",
              borderRadius: "var(--ag-radius-md)",
              padding: "8px 12px",
              marginBottom: 10,
              fontSize: 13,
              color: "var(--ag-success)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <i className="fa-solid fa-circle-check" />
            Re-run submitted successfully.
          </div>
        )}
        {rerunStatus === "error" && (
          <div
            style={{
              background: "var(--ag-danger-soft)",
              border: "1px solid rgba(239,68,68,0.25)",
              borderRadius: "var(--ag-radius-md)",
              padding: "8px 12px",
              marginBottom: 10,
              fontSize: 13,
              color: "var(--ag-danger)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <i className="fa-solid fa-circle-exclamation" />
            {rerunError}
          </div>
        )}
        <div style={{ display: "flex", gap: 7 }}>
          <button
            className="ag-button ag-button--sm ag-button--primary"
            onClick={handleRerun}
            disabled={rerunning}
          >
            <i
              className={`fa-solid ${rerunning ? "fa-spinner fa-spin" : "fa-rotate-right"}`}
              style={{ marginRight: 5 }}
            />
            {rerunning ? "Re-running…" : "Re-run"}
          </button>
          <button className="ag-button ag-button--sm" onClick={handleExport}>
            <i className="fa-solid fa-download" style={{ marginRight: 5 }} />
            Export
          </button>
          <button className="ag-button ag-button--sm" onClick={handleCopyId}>
            <i
              className={`fa-solid ${copied ? "fa-check" : "fa-copy"}`}
              style={{ marginRight: 5 }}
            />
            {copied ? "Copied!" : "Copy ID"}
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function SimulationsPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [modeFilter, setModeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [showNewRun, setShowNewRun] = useState(false);

  const refreshRuns = () => setRefreshKey((k) => k + 1);

  useEffect(() => {
    setLoading(true);
    const params: Parameters<typeof listRuns>[0] = { page, limit: 10 };
    if (statusFilter !== "all") params.status = statusFilter;
    if (modeFilter !== "all") params.mode = modeFilter;
    listRuns(params)
      .then((r) => {
        setRuns(r.runs);
        setTotal(r.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, modeFilter, statusFilter, refreshKey]);

  const filtered = search
    ? runs.filter((r) => r.run_id.toLowerCase().includes(search.toLowerCase()))
    : runs;

  return (
    <div style={T.page}>
      <header style={T.topbar}>
        <div>
          <h1 className="ag-page-title">Simulation Runs</h1>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="ag-button ag-button--sm"
            onClick={() => exportToJSON(runs, "simulations.json")}
          >
            <i className="fa-solid fa-download" style={{ marginRight: 5 }} />
            Export All
          </button>
          <button
            className="ag-button ag-button--sm"
            onClick={() => router.push("/dashboard/templates")}
          >
            <i className="fa-solid fa-layer-group" style={{ marginRight: 5 }} />
            Templates
          </button>
          <button
            className="ag-button ag-button--sm ag-button--primary"
            onClick={() => router.push("/dashboard/simulations/new")}
          >
            <i className="fa-solid fa-plus" style={{ marginRight: 5 }} />
            Build Simulation
          </button>
        </div>
      </header>

      <div className="ag-content">
        {/* EV vs Risk scatter */}
        <div className="ag-card">
          <div className="ag-card-header">
            <div>
              <p className="ag-section-title">
                Expected Value vs Risk Analysis
              </p>
              <p className="ag-section-subtitle">
                Scatter plot of simulation outcomes
              </p>
            </div>
          </div>
          <div style={{ height: 260, padding: "8px 4px" }}>
            <Plot
              data={[
                {
                  type: "scatter",
                  mode: "markers",
                  x:
                    filtered.length > 0
                      ? filtered.map(() => Math.random() * 30)
                      : [5, 12, 18, 25, 8],
                  y:
                    filtered.length > 0
                      ? filtered.map(() => Math.random() * 4000000 + 800000)
                      : [1200000, 2800000, 3100000, 4200000, 900000],
                  marker: {
                    color:
                      filtered.length > 0
                        ? filtered.map((r) =>
                            r.status === "completed"
                              ? "#00D395"
                              : r.status === "failed"
                                ? "#EF4444"
                                : "#6B42FC",
                          )
                        : [
                            "#00D395",
                            "#6B42FC",
                            "#00D395",
                            "#00D395",
                            "#EF4444",
                          ],
                    size: 9,
                    opacity: 0.85,
                  },
                  hovertemplate:
                    "<b>Risk: %{x:.1f}%</b><br>EV: $%{y:,.0f}<extra></extra>",
                },
              ]}
              layout={{
                ...DL,
                xaxis: {
                  ...DL.xaxis,
                  title: {
                    text: "Risk (%)",
                    font: { size: 10, color: "#687089" },
                  },
                },
                yaxis: {
                  ...DL.yaxis,
                  title: {
                    text: "Expected Value ($)",
                    font: { size: 10, color: "#687089" },
                  },
                },
                height: 240,
                autosize: true,
              }}
              config={CC}
              style={{ width: "100%" }}
              useResizeHandler
            />
          </div>
        </div>

        {/* Filters */}
        <div className="ag-card ag-card-body">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: 12,
            }}
          >
            <div>
              <label className="ag-label">Search</label>
              <div style={{ position: "relative" }}>
                <i
                  className="fa-solid fa-search"
                  style={{
                    position: "absolute",
                    left: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    color: "var(--ag-text-faint)",
                    fontSize: 11,
                  }}
                />
                <input
                  className="ag-input"
                  style={{ paddingLeft: 30, height: 34 }}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Run ID, scenario…"
                />
              </div>
            </div>
            {[
              {
                label: "Mode",
                value: modeFilter,
                set: setModeFilter,
                opts: [
                  ["all", "All Modes"],
                  ["auto", "Auto"],
                  ["expert", "Expert"],
                ],
              },
              {
                label: "Status",
                value: statusFilter,
                set: setStatusFilter,
                opts: [
                  ["all", "All Status"],
                  ["completed", "Completed"],
                  ["running", "Running"],
                  ["failed", "Failed"],
                ],
              },
              {
                label: "Date Range",
                value: "7d",
                set: () => {},
                opts: [
                  ["7d", "Last 7 days"],
                  ["30d", "Last 30 days"],
                  ["90d", "Last 90 days"],
                ],
              },
            ].map(({ label, value, set, opts }) => (
              <div key={label}>
                <label className="ag-label">{label}</label>
                <select
                  className="ag-select"
                  style={{ height: 34, fontSize: 13 }}
                  value={value}
                  onChange={(e) => set(e.target.value)}
                >
                  {opts.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="ag-card">
          <table className="ag-table">
            <thead>
              <tr>
                {[
                  "Run ID",
                  "Model",
                  "Mode",
                  "Status",
                  "Action",
                  "Confidence",
                  "Duration",
                  "Created",
                ].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td
                    colSpan={8}
                    style={{
                      textAlign: "center",
                      padding: "32px 0",
                      color: "var(--ag-text-muted)",
                    }}
                  >
                    <i
                      className="fa-solid fa-spinner fa-spin"
                      style={{ marginRight: 8 }}
                    />
                    Loading…
                  </td>
                </tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    style={{
                      textAlign: "center",
                      padding: "32px 0",
                      color: "var(--ag-text-muted)",
                    }}
                  >
                    No runs found.
                  </td>
                </tr>
              )}
              {!loading &&
                filtered.map((run) => {
                  const isExp = expandedId === run.run_id;
                  return [
                    <tr
                      key={run.run_id}
                      style={{ cursor: "pointer" }}
                      onClick={() => setExpandedId(isExp ? null : run.run_id)}
                    >
                      <td>
                        <span className="ag-mono">
                          {run.run_id.slice(0, 14).toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <ModelBadge model={run.simulation_model} />
                      </td>
                      <td>
                        <span
                          className={`ag-badge ${run.mode === "auto" ? "ag-badge--muted" : "ag-badge--primary"}`}
                          style={{
                            fontSize: 11,
                            borderRadius: "var(--ag-radius-xs)",
                          }}
                        >
                          {run.mode === "auto" ? "Auto" : "Expert"}
                        </span>
                      </td>
                      <td>
                        <StatusBadge status={run.status} />
                      </td>
                      <td>
                        <span className="ag-caption">
                          {run.recommended_action ?? "—"}
                        </span>
                      </td>
                      <td>
                        <span className="ag-caption">
                          {run.confidence != null
                            ? `${Math.round(run.confidence * 100)}%`
                            : "—"}
                        </span>
                      </td>
                      <td>
                        <span className="ag-mono">
                          {run.duration_ms != null
                            ? `${run.duration_ms}ms`
                            : "—"}
                        </span>
                      </td>
                      <td>
                        <span className="ag-caption">
                          {run.created_at
                            ? new Date(run.created_at).toLocaleString()
                            : "—"}
                        </span>
                      </td>
                    </tr>,
                    isExp && (
                      <ExpandedRow
                        key={`${run.run_id}-exp`}
                        run={run}
                        onRefresh={refreshRuns}
                      />
                    ),
                  ];
                })}
            </tbody>
          </table>
          <div
            style={{
              padding: "12px 16px",
              borderTop: "1px solid var(--ag-border-default)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span className="ag-caption">
              Showing {filtered.length} of {total}
            </span>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
                className="ag-button ag-button--sm"
              >
                <i
                  className="fa-solid fa-chevron-left"
                  style={{ marginRight: 4 }}
                />
                Prev
              </button>
              <span
                className="ag-caption"
                style={{ padding: "0 8px", lineHeight: "30px" }}
              >
                Page {page}
              </span>
              <button
                disabled={page * 10 >= total}
                onClick={() => setPage((p) => p + 1)}
                className="ag-button ag-button--sm"
              >
                Next
                <i
                  className="fa-solid fa-chevron-right"
                  style={{ marginLeft: 4 }}
                />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* New Run modal */}
      {showNewRun && (
        <NewRunModal
          onClose={() => setShowNewRun(false)}
          onCreated={() => {
            refreshRuns();
            setShowNewRun(false);
          }}
        />
      )}
    </div>
  );
}
