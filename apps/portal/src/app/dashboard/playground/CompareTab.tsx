"use client";
import { useState } from "react";
import { simulate, DecisionEnvelope } from "@/lib/api";
import { Plot } from "@/components/ui/Plot";
import css from "./playground.module.css";

// ── Types ─────────────────────────────────────────────────────────────────────

interface CVarRow {
  name: string;
  dist: string;
  low: string;
  mode: string;
  high: string;
  mean: string;
  std: string;
}
interface CScenario {
  name: string;
  objective: string;
  vars: CVarRow[];
}
interface CResult {
  name: string;
  ev: number;
  std: number;
  pol: number;
  p5: number;
  p50: number;
  p95: number;
  score: number;
  runs: number;
}

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
const DISTS = ["triangular", "normal", "lognormal", "uniform", "fixed"];

function cFmt(n?: number | null, d = 2): string {
  if (n == null || isNaN(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e6) return (n / 1e6).toFixed(d) + "M";
  if (a >= 1e3) return (n / 1e3).toFixed(d) + "K";
  return n.toFixed(d);
}
function cPct(n?: number | null) {
  return n == null ? "—" : (n * 100).toFixed(1) + "%";
}

function newVar(): CVarRow {
  return {
    name: "",
    dist: "triangular",
    low: "",
    mode: "",
    high: "",
    mean: "",
    std: "",
  };
}

function buildSim(sc: CScenario, runs: number) {
  return {
    mode: "expert" as const,
    runs,
    simulation: {
      variables: sc.vars
        .filter((v) => v.name.trim())
        .map((v) => {
          const d = v.dist;
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
          else if (d === "fixed") params = { value: parseFloat(v.mean) || 0 };
          else
            params = {
              low: parseFloat(v.low) || 0,
              mode: parseFloat(v.mode) || 0.5,
              high: parseFloat(v.high) || 1,
            };
          return { name: v.name.trim(), distribution: d, params };
        }),
      objective_function:
        sc.objective.trim() || sc.vars.find((v) => v.name.trim())?.name || "",
      scoring: { expected_value: 0.6, downside_risk: 0.4 },
    },
  };
}

const FONT = { family: "Inter, ui-sans-serif", color: "#687089", size: 11 };

// ── ParamFields ───────────────────────────────────────────────────────────────

function ParamFields({
  v,
  set,
}: {
  v: CVarRow;
  set: (k: keyof CVarRow, val: string) => void;
}) {
  const i = (k: keyof CVarRow, ph: string, lb?: string) => (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
      {lb && <span className={css.paramLabel}>{lb}</span>}
      <input
        value={v[k]}
        onChange={(e) => set(k, e.target.value)}
        placeholder={ph}
        className={css.paramInput}
      />
    </span>
  );
  const d = v.dist;
  if (d === "normal" || d === "lognormal")
    return (
      <>
        {i("mean", "100000", "μ")}
        {i("std", "15000", "σ")}
      </>
    );
  if (d === "uniform")
    return (
      <>
        {i("low", "50000", "lo")}
        {i("high", "150000", "hi")}
      </>
    );
  if (d === "fixed") return <>{i("mean", "100000")}</>;
  return (
    <>
      {i("low", "70000", "lo")}
      {i("mode", "100000", "m")}
      {i("high", "140000", "hi")}
    </>
  );
}

// ── ScenarioBuilder ───────────────────────────────────────────────────────────

function ScenarioBuilder({
  sc,
  idx,
  color,
  onChange,
  onRemove,
  canRemove,
}: {
  sc: CScenario;
  idx: number;
  color: string;
  onChange: (s: CScenario) => void;
  onRemove: () => void;
  canRemove: boolean;
}) {
  function setVar(vi: number, k: keyof CVarRow, val: string) {
    onChange({
      ...sc,
      vars: sc.vars.map((v, i) => (i === vi ? { ...v, [k]: val } : v)),
    });
  }
  return (
    <div
      className={css.scenarioCard}
      style={{ border: `1px solid ${color}33` }}
    >
      <div
        className={css.scenarioCardHeader}
        style={{
          background: `${color}0d`,
          borderBottom: `1px solid ${color}22`,
        }}
      >
        <div className={css.scenarioNum} style={{ background: color }}>
          {idx + 1}
        </div>
        <input
          value={sc.name}
          onChange={(e) => onChange({ ...sc, name: e.target.value })}
          className={css.scenarioNameInput}
        />
        {canRemove && (
          <button onClick={onRemove} className={css.iconBtn}>
            ✕
          </button>
        )}
      </div>
      <div className={css.scenarioBody}>
        <label className={css.scenarioObjLabel}>Objective function</label>
        <input
          value={sc.objective}
          onChange={(e) => onChange({ ...sc, objective: e.target.value })}
          placeholder="revenue - cost"
          className={css.scenarioObjInput}
        />
        <label className={css.scenarioObjLabel}>Variables</label>
        {sc.vars.map((v, vi) => (
          <div key={vi} className={css.varBuilderRow}>
            <div className={css.varBuilderTop}>
              <input
                value={v.name}
                onChange={(e) => setVar(vi, "name", e.target.value)}
                placeholder="variable_name"
                className={css.nameInput}
              />
              <select
                value={v.dist}
                onChange={(e) => setVar(vi, "dist", e.target.value)}
                className={css.distSelect}
              >
                {DISTS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
              {sc.vars.length > 1 && (
                <button
                  onClick={() =>
                    onChange({
                      ...sc,
                      vars: sc.vars.filter((_, j) => j !== vi),
                    })
                  }
                  className={css.iconBtn}
                >
                  ✕
                </button>
              )}
            </div>
            <div className={css.varBuilderParams}>
              <ParamFields v={v} set={(k, val) => setVar(vi, k, val)} />
            </div>
          </div>
        ))}
        <button
          onClick={() => onChange({ ...sc, vars: [...sc.vars, newVar()] })}
          className={css.addVarBtn}
          style={{ color }}
        >
          <span style={{ fontSize: 14 }}>+</span> Add variable
        </button>
      </div>
    </div>
  );
}

// ── ResultCard ────────────────────────────────────────────────────────────────

function ResultCard({
  r,
  isWinner,
  color,
}: {
  r: CResult;
  isWinner: boolean;
  color: string;
}) {
  const ac = r.pol < 0.15 ? "#22d3a0" : r.pol < 0.35 ? "#f59e0b" : "#ef4444";
  const action = r.pol < 0.15 ? "Proceed" : r.pol < 0.35 ? "Caution" : "Reject";
  return (
    <div
      className={css.resultCard}
      style={{
        border: isWinner
          ? `1px solid ${color}55`
          : "1px solid var(--ag-border-default)",
      }}
    >
      <div className={css.resultCardAccent} style={{ background: color }} />
      <div className={css.resultCardBody}>
        <div className={css.resultCardTopRow}>
          <div className={css.resultCardName}>
            <div
              className={css.rankBadge}
              style={{
                background: isWinner
                  ? "linear-gradient(135deg,#FFD700,#FF8C00)"
                  : color + "22",
                color: isWinner ? "#1a1a0e" : color,
              }}
            >
              {isWinner ? "🏆" : "#"}
            </div>
            <div>
              <p className={css.resultName}>{r.name}</p>
              <p className={css.resultRuns}>
                {r.runs?.toLocaleString()} runs · {r.score?.toFixed(4)}
              </p>
            </div>
          </div>
          <span
            className={css.actionPill}
            style={{ color: ac, background: ac + "18" }}
          >
            <span style={{ fontSize: 8 }}>●</span>
            {action}
          </span>
        </div>
        <div className={css.resultMetricGrid}>
          {(
            [
              ["EV", cFmt(r.ev)],
              ["Std", cFmt(r.std)],
              ["P5", cFmt(r.p5)],
              ["P95", cFmt(r.p95)],
              [
                "PoL",
                cPct(r.pol),
                r.pol > 0.3 ? "#ef4444" : r.pol > 0.15 ? "#f59e0b" : "#22d3a0",
              ],
              ["P50", cFmt(r.p50)],
            ] as [string, string, string?][]
          ).map(([l, v, vc]) => (
            <div key={l} className={css.resultMetricTile}>
              <p className={css.resultMetricLabel}>{l}</p>
              <p
                className={css.resultMetricValue}
                style={vc ? { color: vc } : {}}
              >
                {v}
              </p>
            </div>
          ))}
        </div>
        <div className={css.pctBar}>
          <div
            className={css.pctBarBg}
            style={{ background: color + "33", left: "5%", width: "90%" }}
          />
          <div
            className={css.pctBarMid}
            style={{ background: color + "77", left: "25%", width: "50%" }}
          />
          <div
            className={css.pctBarMedium}
            style={{ background: color, left: "50%" }}
          />
        </div>
        <div className={css.pctBarLabels}>
          <span>P5: {cFmt(r.p5)}</span>
          <span style={{ color, fontWeight: 600 }}>P50: {cFmt(r.p50)}</span>
          <span>P95: {cFmt(r.p95)}</span>
        </div>
      </div>
    </div>
  );
}

// ── Parse a simulate JSON payload into a CScenario ────────────────────────────

function payloadToScenario(jsonStr: string, name: string): CScenario | null {
  try {
    const p = JSON.parse(jsonStr) as Record<string, unknown>;
    const sim = p.simulation as Record<string, unknown> | undefined;
    if (!sim) return null;
    const vars = (sim.variables as Array<Record<string, unknown>>) ?? [];
    const objective = (sim.objective_function as string) ?? "";
    const cvars: CVarRow[] = vars.map((v) => {
      const params = (v.params as Record<string, number>) ?? {};
      const dist = (v.distribution as string) ?? "triangular";
      return {
        name: (v.name as string) ?? "",
        dist,
        low: String(params.low ?? ""),
        mode: String(params.mode ?? ""),
        high: String(params.high ?? ""),
        mean: String(params.mean ?? params.mu ?? ""),
        std: String(params.std ?? ""),
      };
    });
    return { name, objective, vars: cvars.length > 0 ? cvars : [newVar()] };
  } catch {
    return null;
  }
}

// ── CompareTab (main export) ──────────────────────────────────────────────────

export default function CompareTab({
  initialPayload,
}: {
  initialPayload?: string;
}) {
  const DEFAULT: CScenario[] = [
    {
      name: "Conservative",
      objective: "revenue - cost",
      vars: [
        {
          name: "revenue",
          dist: "triangular",
          low: "80000",
          mode: "100000",
          high: "130000",
          mean: "",
          std: "",
        },
        {
          name: "cost",
          dist: "normal",
          low: "",
          mode: "",
          high: "",
          mean: "60000",
          std: "8000",
        },
      ],
    },
    {
      name: "Aggressive",
      objective: "revenue - cost",
      vars: [
        {
          name: "revenue",
          dist: "triangular",
          low: "70000",
          mode: "120000",
          high: "180000",
          mean: "",
          std: "",
        },
        {
          name: "cost",
          dist: "normal",
          low: "",
          mode: "",
          high: "",
          mean: "75000",
          std: "15000",
        },
      ],
    },
  ];

  function initScenarios(): CScenario[] {
    if (initialPayload) {
      const s1 = payloadToScenario(initialPayload, "Scenario 1");
      if (s1) {
        const s2: CScenario = {
          name: "Scenario 2",
          objective: s1.objective,
          vars: s1.vars.map((v) => ({ ...v })),
        };
        return [s1, s2];
      }
    }
    return DEFAULT;
  }

  const [scenarios, setScenarios] = useState<CScenario[]>(initScenarios);
  const [runs, setRuns] = useState(20000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<CResult[] | null>(null);

  function setScenario(idx: number, sc: CScenario) {
    setScenarios((p) => p.map((s, i) => (i === idx ? sc : s)));
  }

  async function runCompare() {
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const envs: DecisionEnvelope[] = await Promise.all(
        scenarios.map((sc) => simulate(buildSim(sc, runs))),
      );
      setResults(
        envs
          .map((r, i) => ({
            name: scenarios[i].name,
            ev: r.metrics.expected_value,
            std: r.metrics.std_deviation,
            pol: r.metrics.probability_of_loss,
            p5: r.percentiles.p5,
            p50: r.percentiles.p50,
            p95: r.percentiles.p95,
            score: r.confidence ?? 0,
            runs: r.scenarios_run,
          }))
          .sort((a, b) => b.score - a.score),
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const colors = scenarios.map((_, i) => COLORS[i % COLORS.length]);
  const winner = results?.[0];

  return (
    <div className={css.compareGrid}>
      {/* Left: builder */}
      <div className={css.compareLeft}>
        <div className={css.compareLeftHeader}>
          <span className="ag-section-kicker">
            SCENARIOS ({scenarios.length}/8)
          </span>
          <button
            onClick={() => {
              if (scenarios.length < 8)
                setScenarios((p) => [
                  ...p,
                  {
                    name: `Option ${String.fromCharCode(65 + p.length)}`,
                    objective: "revenue - cost",
                    vars: [newVar()],
                  },
                ]);
            }}
            disabled={scenarios.length >= 8}
            className="ag-button ag-button--sm ag-button--ghost"
            style={{ fontSize: 11 }}
          >
            + Add
          </button>
        </div>

        {scenarios.map((sc, idx) => (
          <ScenarioBuilder
            key={idx}
            sc={sc}
            idx={idx}
            color={colors[idx]}
            onChange={(s) => setScenario(idx, s)}
            onRemove={() => setScenarios((p) => p.filter((_, i) => i !== idx))}
            canRemove={scenarios.length > 2}
          />
        ))}

        <div className={css.runsCard}>
          <label className="ag-section-kicker">RUNS PER SCENARIO</label>
          <div className={css.runsBtns}>
            {[5000, 20000, 50000].map((n) => (
              <button
                key={n}
                onClick={() => setRuns(n)}
                className={`${css.runsBtn}${runs === n ? " " + css.runsBtnActive : ""}`}
              >
                {n.toLocaleString()}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={runCompare}
          disabled={loading}
          className="ag-button ag-button--primary"
          style={{
            width: "100%",
            justifyContent: "center",
            gap: 7,
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? (
            <>
              <i className="fa-solid fa-circle-notch fa-spin" />
              Running…
            </>
          ) : (
            <>
              <i className="fa-solid fa-bolt" />
              Compare {scenarios.length} Scenarios (
              {(runs * scenarios.length).toLocaleString()} runs)
            </>
          )}
        </button>

        {error && (
          <p
            className="ag-caption"
            style={{ color: "var(--ag-danger)", marginTop: 4 }}
          >
            {error}
          </p>
        )}
      </div>

      {/* Right: results */}
      <div className={css.compareRight}>
        {!results && !loading && (
          <div className={css.emptyState}>
            <i className={`fa-solid fa-scale-balanced ${css.emptyIcon}`} />
            <p className={css.emptyTitle}>
              Pre-filled Conservative vs Aggressive — click Compare
            </p>
            <p className={css.emptySubtitle}>
              All scenarios run in parallel via native Mojo engine
            </p>
          </div>
        )}

        {loading && (
          <div className={css.emptyState}>
            <div className={css.spinner} />
            <p className={css.emptyTitle}>
              Running {scenarios.length} parallel simulations…
            </p>
          </div>
        )}

        {results && (
          <>
            <div className={css.winnerBanner}>
              <span className={css.winnerEmoji}>🏆</span>
              <div>
                <p className={css.winnerTitle}>
                  {winner?.name} is the best option
                </p>
                <p className={css.winnerMeta}>
                  EV: <b>{cFmt(winner?.ev)}</b> · Confidence:{" "}
                  <b>{winner?.score?.toFixed(4)}</b> · PoL:{" "}
                  <b>{cPct(winner?.pol)}</b>
                </p>
              </div>
            </div>

            <div
              className={css.resultCardsGrid}
              style={{
                gridTemplateColumns: `repeat(${Math.min(results.length, 3)},1fr)`,
              }}
            >
              {results.map((r, i) => (
                <ResultCard
                  key={r.name}
                  r={r}
                  isWinner={i === 0}
                  color={
                    colors[
                      scenarios.findIndex((s) => s.name === r.name) %
                        colors.length
                    ] || colors[i]
                  }
                />
              ))}
            </div>

            <div className={`${css.rankingTableWrap} ag-card`}>
              <div className={css.rankingTableHeader}>
                <span className="ag-section-kicker">FULL RANKING</span>
              </div>
              <table className="ag-table" style={{ fontSize: 11 }}>
                <thead>
                  <tr>
                    {"# Scenario Conf EV Std P5 P50 P95 PoL"
                      .split(" ")
                      .map((h) => (
                        <th key={h} style={{ padding: "8px 10px" }}>
                          {h}
                        </th>
                      ))}
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, i) => {
                    const c =
                      colors[
                        scenarios.findIndex((s) => s.name === r.name) %
                          colors.length
                      ] || colors[i];
                    return (
                      <tr
                        key={r.name}
                        style={{
                          background:
                            i === 0 ? "rgba(255,215,0,0.03)" : undefined,
                        }}
                      >
                        <td
                          style={{ padding: "8px 10px", textAlign: "center" }}
                        >
                          {i === 0 ? (
                            <span>🏆</span>
                          ) : (
                            <span className="ag-caption">#{i + 1}</span>
                          )}
                        </td>
                        <td style={{ padding: "8px 10px" }}>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 6,
                            }}
                          >
                            <div
                              style={{
                                width: 7,
                                height: 7,
                                borderRadius: "50%",
                                background: c,
                              }}
                            />
                            {r.name}
                          </div>
                        </td>
                        <td
                          style={{
                            padding: "8px 10px",
                            fontWeight: 700,
                            color: c,
                          }}
                        >
                          {r.score?.toFixed(4)}
                        </td>
                        <td style={{ padding: "8px 10px" }}>{cFmt(r.ev)}</td>
                        <td
                          style={{
                            padding: "8px 10px",
                            color: "var(--ag-text-secondary)",
                          }}
                        >
                          {cFmt(r.std)}
                        </td>
                        <td
                          style={{
                            padding: "8px 10px",
                            color: "var(--ag-text-faint)",
                          }}
                        >
                          {cFmt(r.p5)}
                        </td>
                        <td style={{ padding: "8px 10px" }}>{cFmt(r.p50)}</td>
                        <td style={{ padding: "8px 10px" }}>{cFmt(r.p95)}</td>
                        <td
                          style={{
                            padding: "8px 10px",
                            fontWeight: 600,
                            color:
                              r.pol > 0.3
                                ? "#ef4444"
                                : r.pol > 0.15
                                  ? "#f59e0b"
                                  : "#22d3a0",
                          }}
                        >
                          {cPct(r.pol)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* EV comparison chart */}
            <div
              className="ag-card"
              style={{ marginTop: 12, padding: "12px 14px" }}
            >
              <p className="ag-section-kicker" style={{ marginBottom: 8 }}>
                Expected Value Comparison
              </p>
              <Plot
                data={[
                  {
                    type: "bar" as const,
                    x: results.map((r) =>
                      r.name.length > 12 ? r.name.slice(0, 12) + "…" : r.name,
                    ),
                    y: results.map((r) => r.ev),
                    marker: {
                      color: results.map(
                        (_, i) =>
                          colors[
                            scenarios.findIndex(
                              (s) => s.name === results[i].name,
                            ) % colors.length
                          ] || colors[i],
                      ),
                    },
                    text: results.map((r) => cFmt(r.ev)),
                    textposition: "outside" as const,
                    textfont: { size: 10, color: "var(--ag-text-secondary)" },
                  },
                ]}
                layout={{
                  paper_bgcolor: "transparent",
                  plot_bgcolor: "transparent",
                  height: 160,
                  margin: { t: 8, r: 8, b: 36, l: 55 },
                  xaxis: { showgrid: false, tickfont: FONT },
                  yaxis: {
                    showgrid: true,
                    gridcolor: "rgba(255,255,255,0.06)",
                    tickfont: FONT,
                    zeroline: false,
                  },
                  showlegend: false,
                }}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
