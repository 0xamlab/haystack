"use client";
import { useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api/client";
import { Plot } from "@/components/ui/Plot";

// ── Types (matching DecisionEnvelope from /v1/compare) ────────────────────────

interface VarRow {
  name: string;
  distribution: string;
  low: string;
  mode: string;
  high: string;
  mean: string;
  std: string;
  value: string;
}
interface ScenarioInput {
  name: string;
  objective: string;
  vars: VarRow[];
}

// /v1/compare → CompareResponse.scenarios[] → ScenarioComparison
interface Metrics {
  expected_value: number;
  median: number;
  std_deviation: number;
  variance: number;
  probability_of_loss: number;
  var_95?: number;
  cvar_95?: number;
}
interface Percentiles {
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}
interface DecisionEnvelope {
  metrics: Metrics;
  percentiles: Percentiles;
  score?: number;
  scenarios_run?: number;
  engine_version?: string;
  recommended_action?: string;
  confidence?: number;
}
interface ScenarioComparison {
  name: string;
  envelope: DecisionEnvelope;
  delta_vs_best?: {
    expected_value_delta?: number;
    probability_of_loss_delta?: number;
  };
}
interface CompareResponse {
  winner?: string;
  scenarios?: ScenarioComparison[];
  compare_results?: ScenarioComparison[]; // fallback for alternate shape
}

const DISTS = [
  { value: "triangular", label: "Triangular" },
  { value: "normal", label: "Normal" },
  { value: "lognormal", label: "Log-normal" },
  { value: "uniform", label: "Uniform" },
  { value: "pert", label: "PERT" },
  { value: "fixed", label: "Fixed" },
];
const COLORS = [
  "#6B42FC",
  "#22d3a0",
  "#f59e0b",
  "#ef4444",
  "#3b82f6",
  "#ec4899",
  "#8b5cf6",
  "#14b8a6",
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number | undefined | null, d = 2): string {
  if (n == null || isNaN(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(d) + "B";
  if (a >= 1e6) return (n / 1e6).toFixed(d) + "M";
  if (a >= 1e3) return (n / 1e3).toFixed(d) + "K";
  return n.toFixed(d);
}
function pct(n?: number | null) {
  return n == null ? "—" : (n * 100).toFixed(1) + "%";
}

function newVar(): VarRow {
  return {
    name: "",
    distribution: "triangular",
    low: "",
    mode: "",
    high: "",
    mean: "",
    std: "",
    value: "",
  };
}
function buildPayload(scenarios: ScenarioInput[], runs: number) {
  return {
    scenarios: scenarios.map((sc) => ({
      name: sc.name,
      request: {
        mode: "expert",
        // runs is a TOP-LEVEL field on SimulateRequestExpert, not inside simulation
        runs,
        simulation_model: "monte_carlo",
        simulation: {
          variables: sc.vars
            .filter((v) => v.name.trim())
            .map((v) => {
              const d = v.distribution;
              let params: Record<string, number> = {};
              if (d === "normal" || d === "lognormal")
                params = {
                  mean: parseFloat(v.mean) || 0,
                  std: parseFloat(v.std) || 1,
                };
              else if (d === "uniform")
                params = {
                  low: parseFloat(v.low) || 0,
                  high: parseFloat(v.high) || 1,
                };
              else if (d === "fixed")
                params = { value: parseFloat(v.value) || 0 };
              else
                params = {
                  low: parseFloat(v.low) || 0,
                  mode: parseFloat(v.mode) || 0.5,
                  high: parseFloat(v.high) || 1,
                };
              return { name: v.name.trim(), distribution: d, params };
            }),
          objective_function:
            sc.objective.trim() ||
            sc.vars.find((v) => v.name.trim())?.name ||
            "",
          // scoring is required by ExpertSimulation
          scoring: { expected_value: 0.6, downside_risk: 0.4 },
        },
      },
    })),
  };
}

// ── Param fields per distribution ─────────────────────────────────────────────

const IS: React.CSSProperties = {
  background: "var(--ag-bg-canvas)",
  border: "1px solid var(--ag-border-subtle)",
  borderRadius: 5,
  padding: "4px 8px",
  color: "var(--ag-text-primary)",
  fontSize: 12,
  outline: "none",
  width: 80,
};
const LB: React.CSSProperties = {
  fontSize: 10,
  color: "var(--ag-text-faint)",
  marginRight: 3,
};

function ParamFields({
  v,
  set,
}: {
  v: VarRow;
  set: (k: keyof VarRow, val: string) => void;
}) {
  const inp = (key: keyof VarRow, ph: string, lb?: string) => (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
      {lb && <span style={LB}>{lb}</span>}
      <input
        value={v[key]}
        onChange={(e) => set(key, e.target.value)}
        placeholder={ph}
        style={IS}
      />
    </span>
  );
  const d = v.distribution;
  if (d === "normal" || d === "lognormal")
    return (
      <>
        {inp("mean", "100000", "μ")}
        {inp("std", "15000", "σ")}
      </>
    );
  if (d === "uniform")
    return (
      <>
        {inp("low", "50000", "lo")}
        {inp("high", "150000", "hi")}
      </>
    );
  if (d === "fixed") return <>{inp("value", "100000")}</>;
  return (
    <>
      {inp("low", "70000", "lo")}
      {inp("mode", "100000", "m")}
      {inp("high", "140000", "hi")}
    </>
  );
}

// ── Scenario builder card ─────────────────────────────────────────────────────

function ScenarioCard({
  sc,
  idx,
  color,
  onChange,
  onRemove,
  canRemove,
}: {
  sc: ScenarioInput;
  idx: number;
  color: string;
  onChange: (s: ScenarioInput) => void;
  onRemove: () => void;
  canRemove: boolean;
}) {
  function setVar(vi: number, k: keyof VarRow, val: string) {
    onChange({
      ...sc,
      vars: sc.vars.map((v, i) => (i === vi ? { ...v, [k]: val } : v)),
    });
  }
  return (
    <div
      style={{
        background: "var(--ag-bg-surface-1)",
        borderRadius: 10,
        overflow: "hidden",
        border: `1px solid ${color}33`,
        marginBottom: 12,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 14px",
          background: `${color}0d`,
          borderBottom: `1px solid ${color}22`,
        }}
      >
        <div
          style={{
            width: 24,
            height: 24,
            borderRadius: "50%",
            background: color,
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            fontWeight: 700,
            fontSize: 11,
          }}
        >
          {idx + 1}
        </div>
        <input
          value={sc.name}
          onChange={(e) => onChange({ ...sc, name: e.target.value })}
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "var(--ag-text-primary)",
            fontSize: 14,
            fontWeight: 600,
          }}
        />
        {canRemove && (
          <button
            onClick={onRemove}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--ag-text-faint)",
              fontSize: 14,
              padding: "2px 4px",
            }}
          >
            ✕
          </button>
        )}
      </div>

      <div style={{ padding: "12px 14px" }}>
        <div style={{ marginBottom: 10 }}>
          <label
            style={{
              fontSize: 10,
              color: "var(--ag-text-faint)",
              display: "block",
              marginBottom: 4,
              letterSpacing: "0.04em",
            }}
          >
            OBJECTIVE FUNCTION
          </label>
          <input
            value={sc.objective}
            onChange={(e) => onChange({ ...sc, objective: e.target.value })}
            placeholder="revenue - cost"
            style={{
              width: "100%",
              boxSizing: "border-box",
              background: "var(--ag-bg-canvas)",
              border: "1px solid var(--ag-border-subtle)",
              borderRadius: 6,
              padding: "7px 10px",
              color: "var(--ag-text-primary)",
              fontSize: 12,
              fontFamily: "monospace",
              outline: "none",
            }}
          />
        </div>

        <label
          style={{
            fontSize: 10,
            color: "var(--ag-text-faint)",
            display: "block",
            marginBottom: 6,
            letterSpacing: "0.04em",
          }}
        >
          VARIABLES
        </label>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {sc.vars.map((v, vi) => (
            <div
              key={vi}
              style={{
                background: "var(--ag-bg-canvas)",
                border: "1px solid var(--ag-border-subtle)",
                borderRadius: 7,
                padding: "8px 10px",
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <input
                  value={v.name}
                  onChange={(e) => setVar(vi, "name", e.target.value)}
                  placeholder="variable_name"
                  style={{ ...IS, flex: 1, width: "auto" }}
                />
                <select
                  value={v.distribution}
                  onChange={(e) => setVar(vi, "distribution", e.target.value)}
                  style={{
                    background: "var(--ag-bg-surface-2)",
                    border: "1px solid var(--ag-border-subtle)",
                    borderRadius: 5,
                    padding: "4px 6px",
                    color: "var(--ag-text-primary)",
                    fontSize: 12,
                    flexShrink: 0,
                  }}
                >
                  {DISTS.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
                {sc.vars.length > 1 && (
                  <button
                    onClick={() =>
                      onChange({
                        ...sc,
                        vars: sc.vars.filter((_, i) => i !== vi),
                      })
                    }
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      color: "var(--ag-text-faint)",
                      fontSize: 13,
                      padding: "1px 2px",
                      flexShrink: 0,
                    }}
                  >
                    ✕
                  </button>
                )}
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <ParamFields v={v} set={(k, val) => setVar(vi, k, val)} />
              </div>
            </div>
          ))}
        </div>
        <button
          onClick={() => onChange({ ...sc, vars: [...sc.vars, newVar()] })}
          style={{
            marginTop: 8,
            background: "none",
            border: "none",
            cursor: "pointer",
            color: color,
            fontSize: 12,
            padding: "3px 0",
            display: "flex",
            alignItems: "center",
            gap: 5,
          }}
        >
          <span style={{ fontSize: 15 }}>+</span> Add variable
        </button>
      </div>
    </div>
  );
}

// ── Result card ───────────────────────────────────────────────────────────────

function ResultCard({
  result,
  rank,
  isWinner,
  color,
}: {
  result: ScenarioComparison;
  rank: number;
  isWinner: boolean;
  color: string;
}) {
  const m = result.envelope.metrics;
  const p = result.envelope.percentiles;
  const pol = m?.probability_of_loss ?? 0;
  const action = pol < 0.15 ? "proceed" : pol < 0.35 ? "caution" : "reject";
  const ac =
    action === "proceed"
      ? "#22d3a0"
      : action === "caution"
        ? "#f59e0b"
        : "#ef4444";
  const score = result.envelope.score;

  return (
    <div
      style={{
        background: "var(--ag-bg-surface-1)",
        borderRadius: 10,
        overflow: "hidden",
        border: isWinner
          ? `1px solid ${color}55`
          : "1px solid var(--ag-border-default)",
      }}
    >
      <div style={{ height: 3, background: color }} />
      <div style={{ padding: "14px 16px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            marginBottom: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                flexShrink: 0,
                background: isWinner
                  ? "linear-gradient(135deg,#FFD700,#FF8C00)"
                  : color + "22",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: isWinner ? "#1a1a0e" : color,
                fontWeight: 800,
                fontSize: 13,
              }}
            >
              {isWinner ? "🏆" : rank}
            </div>
            <div>
              <p
                style={{
                  margin: 0,
                  fontSize: 14,
                  fontWeight: 700,
                  color: "var(--ag-text-primary)",
                }}
              >
                {result.name}
              </p>
              <p
                style={{
                  margin: 0,
                  fontSize: 10,
                  color: "var(--ag-text-faint)",
                  marginTop: 1,
                }}
              >
                {result.envelope.scenarios_run?.toLocaleString() ?? "—"} runs ·
                score {score?.toFixed(4) ?? "—"}
              </p>
            </div>
          </div>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: ac,
              background: ac + "18",
              padding: "3px 9px",
              borderRadius: 999,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span style={{ fontSize: 8 }}>●</span>
            {action.charAt(0).toUpperCase() + action.slice(1)}
          </span>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 6,
            marginBottom: 10,
          }}
        >
          {(
            [
              ["Expected Value", fmt(m?.expected_value)],
              ["Std Deviation", fmt(m?.std_deviation)],
              ["P5", fmt(p?.p5)],
              ["P95", fmt(p?.p95)],
              [
                "Prob of Loss",
                pct(pol),
                pol > 0.3 ? "#ef4444" : pol > 0.15 ? "#f59e0b" : "#22d3a0",
              ],
              ["VaR 95%", fmt(m?.var_95)],
            ] as [string, string, string?][]
          ).map(([label, value, vc]) => (
            <div
              key={label}
              style={{
                background: "var(--ag-bg-surface-2)",
                borderRadius: 7,
                padding: "7px 10px",
              }}
            >
              <p
                style={{
                  margin: 0,
                  fontSize: 10,
                  color: "var(--ag-text-faint)",
                  marginBottom: 2,
                }}
              >
                {label}
              </p>
              <p
                style={{
                  margin: 0,
                  fontSize: 13,
                  fontWeight: 600,
                  color: vc || "var(--ag-text-primary)",
                }}
              >
                {value}
              </p>
            </div>
          ))}
        </div>

        <div>
          <p
            style={{
              margin: "0 0 4px",
              fontSize: 10,
              color: "var(--ag-text-faint)",
            }}
          >
            Percentile range
          </p>
          <div
            style={{
              height: 6,
              background: "var(--ag-bg-surface-2)",
              borderRadius: 3,
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                position: "absolute",
                top: 0,
                height: "100%",
                background: color + "33",
                left: "5%",
                width: "90%",
                borderRadius: 3,
              }}
            />
            <div
              style={{
                position: "absolute",
                top: 0,
                height: "100%",
                background: color + "77",
                left: "25%",
                width: "50%",
              }}
            />
            <div
              style={{
                position: "absolute",
                top: 0,
                height: "100%",
                width: 2,
                background: color,
                left: "50%",
                transform: "translateX(-50%)",
              }}
            />
          </div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: 3,
            }}
          >
            <span style={{ fontSize: 9, color: "var(--ag-text-faint)" }}>
              P5: {fmt(p?.p5)}
            </span>
            <span style={{ fontSize: 9, color: color, fontWeight: 600 }}>
              P50: {fmt(p?.p50)}
            </span>
            <span style={{ fontSize: 9, color: "var(--ag-text-faint)" }}>
              P95: {fmt(p?.p95)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Chart ─────────────────────────────────────────────────────────────────────

const FONT = { family: "Inter, ui-sans-serif", color: "#687089", size: 11 };
const DL = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { t: 28, r: 8, b: 40, l: 55 },
  xaxis: { showgrid: false, tickfont: FONT, tickangle: -20 },
  yaxis: {
    showgrid: true,
    gridcolor: "rgba(255,255,255,0.06)",
    tickfont: FONT,
    zeroline: false,
  },
  showlegend: false,
};

function CompareChart({
  results,
  metric,
  label,
  colors,
}: {
  results: ScenarioComparison[];
  metric: (r: ScenarioComparison) => number;
  label: string;
  colors: string[];
}) {
  const values = results.map(metric);
  const max = Math.max(...values.map(Math.abs), 1);
  return (
    <Plot
      data={[
        {
          type: "bar" as const,
          x: results.map((r) =>
            r.name.length > 12 ? r.name.slice(0, 12) + "…" : r.name,
          ),
          y: values,
          marker: { color: colors },
          text: values.map((v) => fmt(v)),
          textposition: "outside" as const,
          textfont: { size: 10, color: "var(--ag-text-secondary)" },
        },
      ]}
      layout={{
        ...DL,
        height: 190,
        title: {
          text: label,
          font: { ...FONT, size: 11, color: "var(--ag-text-faint)" },
          x: 0.04,
        },
        yaxis: {
          ...DL.yaxis,
          range: [values.some((v) => v < 0) ? -max * 1.3 : 0, max * 1.3],
        },
      }}
    />
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function ComparePage() {
  const [scenarios, setScenarios] = useState<ScenarioInput[]>([
    {
      name: "Conservative",
      objective: "revenue - cost",
      vars: [
        {
          name: "revenue",
          distribution: "triangular",
          low: "80000",
          mode: "100000",
          high: "130000",
          mean: "",
          std: "",
          value: "",
        },
        {
          name: "cost",
          distribution: "normal",
          low: "",
          mode: "",
          high: "",
          mean: "60000",
          std: "8000",
          value: "",
        },
      ],
    },
    {
      name: "Aggressive",
      objective: "revenue - cost",
      vars: [
        {
          name: "revenue",
          distribution: "triangular",
          low: "70000",
          mode: "120000",
          high: "180000",
          mean: "",
          std: "",
          value: "",
        },
        {
          name: "cost",
          distribution: "normal",
          low: "",
          mode: "",
          high: "",
          mean: "75000",
          std: "15000",
          value: "",
        },
      ],
    },
  ]);
  const [runs, setRuns] = useState(20000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<ScenarioComparison[] | null>(null);
  const [winner, setWinner] = useState<string | null>(null);

  function setScenario(idx: number, sc: ScenarioInput) {
    setScenarios((prev) => prev.map((s, i) => (i === idx ? sc : s)));
  }

  async function handleRun() {
    setLoading(true);
    setError(null);
    setResults(null);
    setWinner(null);
    try {
      const payload = buildPayload(scenarios, runs);
      console.log(
        "[compare] sending payload:",
        JSON.stringify(payload, null, 2),
      );
      const resp = await apiFetch<CompareResponse>("/v1/compare", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      console.log("[compare] raw response:", JSON.stringify(resp, null, 2));
      // /v1/compare returns { winner, scenarios: ScenarioComparison[] }
      const list = resp.scenarios ?? resp.compare_results ?? [];
      const sorted = [...list].sort(
        (a, b) => (b.envelope.score ?? 0) - (a.envelope.score ?? 0),
      );
      setResults(sorted);
      setWinner(resp.winner ?? sorted[0]?.name ?? null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function scenarioColor(name: string): string {
    const idx = scenarios.findIndex((s) => s.name === name);
    return COLORS[(idx >= 0 ? idx : 0) % COLORS.length];
  }
  const cardColors = scenarios.map((_, i) => COLORS[i % COLORS.length]);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--ag-bg-canvas)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <header
        style={{
          height: "var(--ag-topbar-height)",
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
          position: "sticky" as const,
          top: 0,
          zIndex: 40,
          background:
            "linear-gradient(180deg, rgba(255,255,255,0.015), rgba(255,255,255,0)), var(--ag-bg-surface-1)",
          borderBottom: "1px solid var(--ag-border-default)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <i
            className="fa-solid fa-scale-balanced"
            style={{ color: "var(--ag-brand-primary)", fontSize: 16 }}
          />
          <span
            style={{
              fontWeight: 700,
              fontSize: 16,
              color: "var(--ag-text-primary)",
            }}
          >
            Scenario Comparison
          </span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.05em",
              background: "rgba(107,66,252,0.12)",
              color: "var(--ag-brand-primary)",
              padding: "3px 10px",
              borderRadius: 999,
            }}
          >
            Mojo Parallel
          </span>
        </div>
        <Link
          href="/dashboard/simulations"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            textDecoration: "none",
            fontSize: 12,
            color: "var(--ag-text-secondary)",
            padding: "5px 10px",
            border: "1px solid var(--ag-border-default)",
            borderRadius: 6,
          }}
        >
          <i className="fa-solid fa-arrow-left" style={{ fontSize: 11 }} /> Back
          to Runs
        </Link>
      </header>

      {/* Split layout */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "380px 1fr",
          flex: 1,
          minHeight: 0,
        }}
      >
        {/* Left: Builder */}
        <div
          style={{
            borderRight: "1px solid var(--ag-border-default)",
            overflowY: "auto",
            padding: "18px 16px",
            background: "var(--ag-bg-canvas)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 14,
            }}
          >
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "var(--ag-text-faint)",
                letterSpacing: "0.06em",
              }}
            >
              SCENARIOS ({scenarios.length}/8)
            </span>
            <button
              onClick={() => {
                if (scenarios.length < 8)
                  setScenarios((prev) => [
                    ...prev,
                    {
                      name: `Option ${String.fromCharCode(65 + prev.length)}`,
                      objective: "revenue - cost",
                      vars: [newVar()],
                    },
                  ]);
              }}
              disabled={scenarios.length >= 8}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 5,
                background: "none",
                border: "1px solid var(--ag-border-default)",
                borderRadius: 6,
                padding: "4px 10px",
                color:
                  scenarios.length >= 8
                    ? "var(--ag-text-faint)"
                    : "var(--ag-text-secondary)",
                fontSize: 12,
                cursor: scenarios.length >= 8 ? "not-allowed" : "pointer",
              }}
            >
              <span style={{ fontSize: 14 }}>+</span> Add Scenario
            </button>
          </div>

          {scenarios.map((sc, idx) => (
            <ScenarioCard
              key={idx}
              sc={sc}
              idx={idx}
              color={cardColors[idx]}
              onChange={(s) => setScenario(idx, s)}
              onRemove={() =>
                setScenarios((prev) => prev.filter((_, i) => i !== idx))
              }
              canRemove={scenarios.length > 2}
            />
          ))}

          <div
            style={{
              marginTop: 4,
              marginBottom: 12,
              background: "var(--ag-bg-surface-1)",
              border: "1px solid var(--ag-border-default)",
              borderRadius: 10,
              padding: "12px 14px",
            }}
          >
            <label
              style={{
                fontSize: 10,
                color: "var(--ag-text-faint)",
                display: "block",
                marginBottom: 8,
                letterSpacing: "0.04em",
              }}
            >
              SIMULATION RUNS PER SCENARIO
            </label>
            <div style={{ display: "flex", gap: 6 }}>
              {[5000, 20000, 50000, 100000].map((n) => (
                <button
                  key={n}
                  onClick={() => setRuns(n)}
                  style={{
                    padding: "5px 10px",
                    borderRadius: 6,
                    fontSize: 11,
                    cursor: "pointer",
                    background:
                      runs === n
                        ? "var(--ag-brand-primary)"
                        : "var(--ag-bg-surface-2)",
                    color: runs === n ? "#fff" : "var(--ag-text-secondary)",
                    border:
                      runs === n
                        ? "1px solid transparent"
                        : "1px solid var(--ag-border-default)",
                    fontWeight: runs === n ? 700 : 400,
                  }}
                >
                  {n.toLocaleString()}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleRun}
            disabled={loading}
            style={{
              width: "100%",
              padding: "12px 16px",
              borderRadius: 8,
              background: loading
                ? "rgba(107,66,252,0.4)"
                : "var(--ag-brand-primary)",
              color: "#fff",
              border: "none",
              cursor: loading ? "not-allowed" : "pointer",
              fontWeight: 700,
              fontSize: 14,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
            }}
          >
            {loading ? (
              <>
                <i className="fa-solid fa-circle-notch fa-spin" />
                Running {scenarios.length} scenarios…
              </>
            ) : (
              <>
                <i className="fa-solid fa-bolt" />
                Compare {scenarios.length} Scenarios
              </>
            )}
          </button>
          <p
            style={{
              textAlign: "center",
              margin: "7px 0 0",
              fontSize: 11,
              color: "var(--ag-text-faint)",
            }}
          >
            {(runs * scenarios.length).toLocaleString()} total simulation runs
          </p>
          {error && (
            <div
              style={{
                marginTop: 12,
                padding: "10px 13px",
                background: "rgba(239,68,68,0.08)",
                border: "1px solid rgba(239,68,68,0.25)",
                borderRadius: 8,
                fontSize: 12,
                color: "#ef4444",
                display: "flex",
                gap: 8,
              }}
            >
              <i
                className="fa-solid fa-triangle-exclamation"
                style={{ marginTop: 1 }}
              />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Right: Results */}
        <div style={{ overflowY: "auto", padding: "24px" }}>
          {!results && !loading && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 500,
                gap: 14,
                color: "var(--ag-text-faint)",
              }}
            >
              <div
                style={{
                  width: 80,
                  height: 80,
                  borderRadius: "50%",
                  background: "rgba(107,66,252,0.06)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <i
                  className="fa-solid fa-scale-balanced"
                  style={{ fontSize: 32, opacity: 0.25 }}
                />
              </div>
              <p
                style={{
                  margin: 0,
                  fontSize: 15,
                  fontWeight: 600,
                  color: "var(--ag-text-secondary)",
                }}
              >
                The example is pre-filled — click Compare
              </p>
              <p
                style={{
                  margin: 0,
                  fontSize: 13,
                  maxWidth: 340,
                  textAlign: "center",
                  lineHeight: 1.6,
                }}
              >
                Conservative vs Aggressive compares two revenue/cost scenarios.
                Run as-is or customize the parameters.
              </p>
              <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                {["Monte Carlo", "Parallel cores", "Real-time scoring"].map(
                  (t) => (
                    <span
                      key={t}
                      style={{
                        fontSize: 11,
                        fontWeight: 500,
                        background: "rgba(107,66,252,0.08)",
                        color: "var(--ag-brand-primary)",
                        padding: "4px 10px",
                        borderRadius: 999,
                      }}
                    >
                      {t}
                    </span>
                  ),
                )}
              </div>
            </div>
          )}

          {loading && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 500,
                gap: 20,
              }}
            >
              <div style={{ position: "relative", width: 56, height: 56 }}>
                <div
                  style={{
                    width: 56,
                    height: 56,
                    border: "3px solid rgba(107,66,252,0.12)",
                    borderRadius: "50%",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: 56,
                    height: 56,
                    border: "3px solid transparent",
                    borderTopColor: "var(--ag-brand-primary)",
                    borderRadius: "50%",
                    animation: "spin 0.7s linear infinite",
                  }}
                />
              </div>
              <div style={{ textAlign: "center" }}>
                <p
                  style={{
                    margin: "0 0 4px",
                    fontWeight: 600,
                    color: "var(--ag-text-primary)",
                  }}
                >
                  Running {scenarios.length} scenarios in parallel
                </p>
                <p
                  style={{
                    margin: 0,
                    fontSize: 12,
                    color: "var(--ag-text-faint)",
                  }}
                >
                  {(runs * scenarios.length).toLocaleString()} total Mojo runs
                </p>
              </div>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          )}

          {results && (
            <>
              {/* Winner banner */}
              <div
                style={{
                  padding: "14px 18px",
                  marginBottom: 20,
                  background:
                    "linear-gradient(135deg, rgba(255,215,0,0.07), rgba(255,140,0,0.03))",
                  border: "1px solid rgba(255,215,0,0.2)",
                  borderRadius: 12,
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                }}
              >
                <span style={{ fontSize: 28 }}>🏆</span>
                <div>
                  <p
                    style={{
                      margin: 0,
                      fontWeight: 800,
                      fontSize: 15,
                      color: "var(--ag-text-primary)",
                    }}
                  >
                    {winner} is the best option
                  </p>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 12,
                      color: "var(--ag-text-secondary)",
                      marginTop: 2,
                    }}
                  >
                    Score: <b>{results[0]?.envelope.score?.toFixed(4)}</b>{" "}
                    &nbsp;·&nbsp; EV:{" "}
                    <b>{fmt(results[0]?.envelope.metrics?.expected_value)}</b>{" "}
                    &nbsp;·&nbsp; PoL:{" "}
                    <b>
                      {pct(results[0]?.envelope.metrics?.probability_of_loss)}
                    </b>
                  </p>
                </div>
              </div>

              {/* Result cards */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: `repeat(${Math.min(results.length, 3)}, 1fr)`,
                  gap: 14,
                  marginBottom: 22,
                }}
              >
                {results.map((r, i) => (
                  <ResultCard
                    key={r.name}
                    result={r}
                    rank={i + 1}
                    isWinner={r.name === winner}
                    color={scenarioColor(r.name)}
                  />
                ))}
              </div>

              {/* 2×2 charts */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 14,
                  marginBottom: 22,
                }}
              >
                {[
                  {
                    label: "Expected Value",
                    fn: (r: ScenarioComparison) =>
                      r.envelope.metrics?.expected_value ?? 0,
                  },
                  {
                    label: "Composite Score",
                    fn: (r: ScenarioComparison) => r.envelope.score ?? 0,
                  },
                  {
                    label: "Probability of Loss",
                    fn: (r: ScenarioComparison) =>
                      r.envelope.metrics?.probability_of_loss ?? 0,
                  },
                  {
                    label: "Value at Risk (P5)",
                    fn: (r: ScenarioComparison) =>
                      r.envelope.metrics?.var_95 ?? 0,
                  },
                ].map(({ label, fn }) => (
                  <div
                    key={label}
                    className="ag-card"
                    style={{ padding: "12px 14px" }}
                  >
                    <CompareChart
                      results={results}
                      metric={fn}
                      label={label}
                      colors={results.map((r) => scenarioColor(r.name))}
                    />
                  </div>
                ))}
              </div>

              {/* Ranking table */}
              <div className="ag-card">
                <div
                  style={{
                    padding: "12px 16px 10px",
                    borderBottom: "1px solid var(--ag-border-subtle)",
                  }}
                >
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: "var(--ag-text-secondary)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    FULL RANKING
                  </span>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="ag-table" style={{ fontSize: 12 }}>
                    <thead>
                      <tr>
                        {[
                          "#",
                          "Scenario",
                          "Score",
                          "EV",
                          "Std Dev",
                          "P5",
                          "P50",
                          "P95",
                          "PoL",
                          "VaR 95",
                        ].map((h) => (
                          <th
                            key={h}
                            style={{
                              padding: "10px 12px",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {results.map((r, i) => {
                        const m = r.envelope.metrics;
                        const p = r.envelope.percentiles;
                        const c = scenarioColor(r.name);
                        return (
                          <tr
                            key={r.name}
                            style={{
                              background:
                                r.name === winner
                                  ? "rgba(255,215,0,0.03)"
                                  : undefined,
                            }}
                          >
                            <td
                              style={{
                                padding: "10px 12px",
                                textAlign: "center",
                              }}
                            >
                              {r.name === winner ? (
                                <span>🏆</span>
                              ) : (
                                <span
                                  style={{
                                    color: "var(--ag-text-faint)",
                                    fontWeight: 600,
                                  }}
                                >
                                  #{i + 1}
                                </span>
                              )}
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 8,
                                }}
                              >
                                <div
                                  style={{
                                    width: 8,
                                    height: 8,
                                    borderRadius: "50%",
                                    background: c,
                                    flexShrink: 0,
                                  }}
                                />
                                <span
                                  style={{
                                    fontWeight: r.name === winner ? 700 : 400,
                                    color: "var(--ag-text-primary)",
                                  }}
                                >
                                  {r.name}
                                </span>
                              </div>
                            </td>
                            <td
                              style={{
                                padding: "10px 12px",
                                fontWeight: 700,
                                color: c,
                              }}
                            >
                              {r.envelope.score?.toFixed(4)}
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              {fmt(m?.expected_value)}
                            </td>
                            <td
                              style={{
                                padding: "10px 12px",
                                color: "var(--ag-text-secondary)",
                              }}
                            >
                              {fmt(m?.std_deviation)}
                            </td>
                            <td
                              style={{
                                padding: "10px 12px",
                                color: "var(--ag-text-faint)",
                              }}
                            >
                              {fmt(p?.p5)}
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              {fmt(p?.p50)}
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              {fmt(p?.p95)}
                            </td>
                            <td
                              style={{
                                padding: "10px 12px",
                                fontWeight: 600,
                                color:
                                  (m?.probability_of_loss ?? 0) > 0.3
                                    ? "#ef4444"
                                    : (m?.probability_of_loss ?? 0) > 0.15
                                      ? "#f59e0b"
                                      : "#22d3a0",
                              }}
                            >
                              {pct(m?.probability_of_loss)}
                            </td>
                            <td
                              style={{
                                padding: "10px 12px",
                                color: "var(--ag-text-faint)",
                              }}
                            >
                              {fmt(m?.var_95)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
