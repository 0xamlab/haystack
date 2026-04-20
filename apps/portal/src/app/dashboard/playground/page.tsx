"use client";
import { useState, useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import {
  simulate,
  DecisionEnvelope,
  listSimulationTemplates,
  getSimulationTemplate,
  SimulationTemplatePreview,
  exportToJSON,
} from "@/lib/api";
import { Plot } from "@/components/ui/Plot";
import CompareTab from "./CompareTab";
import css from "./playground.module.css";
import {
  Mode,
  TemplatePayload,
  SIM_MODELS,
  BUILTIN_TEMPLATES,
  paramVal,
  applySliderVals,
} from "./constants";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
});

// ── Plot config ───────────────────────────────────────────────────────────────

const FONT = { family: "Inter, ui-sans-serif", color: "#687089", size: 10 };
const HOVERLABEL = {
  bgcolor: "#181B26",
  bordercolor: "#1F2430",
  font: { family: "Inter, ui-sans-serif", size: 12, color: "#E6E8EC" },
  align: "left" as const,
};
const DL = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { t: 4, r: 4, b: 28, l: 40 },
  font: FONT,
  hoverlabel: HOVERLABEL,
  xaxis: { showgrid: false, tickfont: FONT, automargin: true },
  yaxis: {
    showgrid: true,
    gridcolor: "rgba(255,255,255,0.05)",
    tickfont: FONT,
    zeroline: false,
    automargin: true,
  },
  showlegend: false,
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtNum(n: number | null | undefined, d = 2): string {
  if (n == null || isNaN(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(d) + "B";
  if (a >= 1e6) return (n / 1e6).toFixed(d) + "M";
  if (a >= 1e3) return (n / 1e3).toFixed(d) + "K";
  return n.toFixed(d);
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PlaygroundPage() {
  const [playgroundTab, setPlaygroundTab] = useState<"simulate" | "compare">(
    "simulate",
  );
  const [mode, setMode] = useState<Mode>("expert");
  const [simModel, setSimModel] = useState("monte_carlo");
  const [template, setTpl] = useState("");
  const [apiTemplates, setApiTemplates] = useState<SimulationTemplatePreview[]>(
    [],
  );
  const [templatePayload, setTemplatePayload] =
    useState<TemplatePayload | null>(null);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [vals, setVals] = useState<Record<string, number>>({});
  const [runs, setRuns] = useState(50000);
  const [seed, setSeed] = useState(42);
  const [payload, setPayload] = useState("{}");
  const [result, setResult] = useState<DecisionEnvelope | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [editorTab, setEditorTab] = useState<"visual" | "json">("visual");

  // ── Template loading ────────────────────────────────────────────────────────

  const loadBuiltin = useCallback(
    (name: string) => {
      setTpl(name);
      const t = BUILTIN_TEMPLATES[name];
      if (!t) return;
      setTemplatePayload(t);
      const sim = (t as Record<string, unknown>).simulation as
        | Record<string, unknown>
        | undefined;
      const vars = (sim?.variables as Array<Record<string, unknown>>) ?? [];
      const initialVals: Record<string, number> = {};
      vars.forEach((v) => {
        const n = v.name as string;
        initialVals[n] = paramVal(v.params as Record<string, number>);
      });
      setVals(initialVals);
      const p = applySliderVals(t, initialVals, runs, seed);
      setPayload(JSON.stringify(p, null, 2));
      setResult(null);
      setError(null);
    },
    [runs, seed],
  );

  const loadTemplate = useCallback(
    async (id: string, name: string) => {
      setTemplateLoading(true);
      try {
        const { payload: p } = await getSimulationTemplate(id, runs);
        setTpl(name);
        setTemplatePayload(p);
        const sim = (p as Record<string, unknown>).simulation as
          | Record<string, unknown>
          | undefined;
        const vars = (sim?.variables as Array<Record<string, unknown>>) ?? [];
        const initialVals: Record<string, number> = {};
        vars.forEach((v) => {
          const n = v.name as string;
          initialVals[n] = paramVal(v.params as Record<string, number>);
        });
        setVals(initialVals);
        setPayload(
          JSON.stringify(applySliderVals(p, initialVals, runs, seed), null, 2),
        );
        setResult(null);
        setError(null);
      } catch {
        loadBuiltin(Object.keys(BUILTIN_TEMPLATES)[0]);
      } finally {
        setTemplateLoading(false);
      }
    },
    [runs, seed, loadBuiltin],
  );

  useEffect(() => {
    listSimulationTemplates()
      .then((r) => {
        setApiTemplates(r.templates);
        if (r.templates.length > 0)
          loadTemplate(r.templates[0].id, r.templates[0].name);
      })
      .catch(() => {
        const names = Object.keys(BUILTIN_TEMPLATES);
        if (names.length > 0) loadBuiltin(names[0]);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleTemplateChange(name: string) {
    const found = apiTemplates.find((t) => t.name === name);
    if (found) loadTemplate(found.id, found.name);
    else loadBuiltin(name);
  }

  function handleModeChange(m: Mode) {
    setMode(m);
    if (!templatePayload) return;
    if (m === "auto") {
      const ap = { ...templatePayload, mode: "auto", runs, seed };
      setPayload(JSON.stringify(ap, null, 2));
    } else {
      setPayload(
        JSON.stringify(
          applySliderVals(templatePayload, vals, runs, seed),
          null,
          2,
        ),
      );
    }
    setResult(null);
    setError(null);
  }

  function handleSlider(name: string, val: number) {
    const nv = { ...vals, [name]: val };
    setVals(nv);
    if (templatePayload)
      setPayload(
        JSON.stringify(
          applySliderVals(templatePayload, nv, runs, seed),
          null,
          2,
        ),
      );
  }

  function handleJsonChange(v: string | undefined) {
    const s = v ?? "";
    setPayload(s);
    try {
      JSON.parse(s);
      setJsonError(null);
    } catch {
      setJsonError("Invalid JSON");
    }
  }

  async function runSim() {
    let parsed: unknown;
    try {
      parsed = JSON.parse(payload);
    } catch {
      setJsonError("Fix JSON before running");
      return;
    }
    setRunning(true);
    setError(null);
    const t0 = performance.now();
    try {
      const r = await simulate(parsed as Parameters<typeof simulate>[0]);
      setResult(r);
      setElapsed(Math.round(performance.now() - t0));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setRunning(false);
    }
  }

  function handleExport() {
    if (result) exportToJSON(result, `playground-${Date.now()}.json`);
  }

  // ── Left panel variables ────────────────────────────────────────────────────

  const simVars = (() => {
    try {
      const p = JSON.parse(payload) as Record<string, unknown>;
      const sim = p.simulation as Record<string, unknown> | undefined;
      return (sim?.variables as Array<Record<string, unknown>>) ?? [];
    } catch {
      return [];
    }
  })();

  // ── Result display helpers ──────────────────────────────────────────────────

  const ev = result?.metrics.expected_value ?? 0;
  const pol = result?.metrics.probability_of_loss ?? 0;
  const actionClass = result
    ? pol < 0.2
      ? css["decisionBadge--proceed"]
      : pol < 0.5
        ? css["decisionBadge--caution"]
        : css["decisionBadge--reject"]
    : "";
  const actionIcon =
    pol < 0.2
      ? "fa-circle-check"
      : pol < 0.5
        ? "fa-triangle-exclamation"
        : "fa-circle-xmark";

  const seed_ = ev > 0 ? ev : 70000;
  const distX = Array.from({ length: 40 }, (_, i) => seed_ * (0.4 + i * 0.025));
  const distY = distX.map((x) => {
    const s = seed_ * 0.18;
    return (
      (Math.exp(-0.5 * Math.pow((x - seed_) / s, 2)) /
        (s * Math.sqrt(2 * Math.PI))) *
      200000
    );
  });

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className={css.page}>
      {/* Topbar */}
      <header className={css.topbar}>
        <div className={css.topbarLeft}>
          <div>
            <h1 className="ag-page-title">Simulation Playground</h1>
          </div>
          <div className={css.tabBar}>
            {(["simulate", "compare"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setPlaygroundTab(t)}
                className={`${css.tabBtn}${playgroundTab === t ? " " + css.tabBtnActive : ""}`}
              >
                {t === "simulate" ? "Simulate" : "Compare"}
              </button>
            ))}
          </div>
        </div>

        {playgroundTab === "simulate" && (
          <div className={css.topbarRight}>
            <select
              value={template}
              onChange={(e) => handleTemplateChange(e.target.value)}
              className="ag-select"
              style={{ width: "auto", height: 36, fontSize: 13, minWidth: 220 }}
              disabled={templateLoading}
            >
              {apiTemplates.length > 0
                ? apiTemplates.map((t) => (
                    <option key={t.id} value={t.name}>
                      {t.name}
                    </option>
                  ))
                : Object.keys(BUILTIN_TEMPLATES).map((t) => (
                    <option key={t}>{t}</option>
                  ))}
            </select>
            <button
              className="ag-button ag-button--sm"
              onClick={() => handleTemplateChange(template)}
            >
              <i
                className="fa-solid fa-rotate-left"
                style={{ marginRight: 5 }}
              />
              Reset
            </button>
            {result && (
              <button
                className="ag-button ag-button--sm"
                onClick={handleExport}
              >
                <i
                  className="fa-solid fa-download"
                  style={{ marginRight: 5 }}
                />
                Export
              </button>
            )}
            <button
              className="ag-button ag-button--sm ag-button--primary"
              onClick={runSim}
              disabled={running}
            >
              {running ? (
                <>
                  <i
                    className="fa-solid fa-spinner fa-spin"
                    style={{ marginRight: 5 }}
                  />
                  Running…
                </>
              ) : (
                <>
                  <i className="fa-solid fa-play" style={{ marginRight: 5 }} />
                  Run Simulation
                </>
              )}
            </button>
          </div>
        )}
      </header>

      {/* Compare tab — receives current JSON payload so it can pre-populate */}
      {playgroundTab === "compare" && (
        <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
          <CompareTab initialPayload={payload} />
        </div>
      )}

      {/* Simulate tab — 3-panel grid */}
      {playgroundTab === "simulate" && (
        <div className={css.grid3}>
          {/* LEFT: Variables */}
          <div className={css.leftPanel}>
            <div className={css.leftPanelSection}>
              <div>
                <p className="ag-section-kicker" style={{ marginBottom: 8 }}>
                  Execution Mode
                </p>
                <div className={css.modeRow}>
                  {(["auto", "expert"] as Mode[]).map((m) => (
                    <button
                      key={m}
                      onClick={() => handleModeChange(m)}
                      className={`ag-button ag-button--sm ${css.modeBtn}`}
                      style={
                        mode === m
                          ? {
                              background: "var(--ag-brand-primary)",
                              borderColor: "transparent",
                              color: "#fff",
                              textTransform: "capitalize",
                            }
                          : { textTransform: "capitalize" }
                      }
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="ag-section-kicker" style={{ marginBottom: 8 }}>
                  Simulation Model
                </p>
                <select
                  value={simModel}
                  onChange={(e) => setSimModel(e.target.value)}
                  className="ag-select"
                  style={{ width: "100%" }}
                >
                  {SIM_MODELS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <p className="ag-section-kicker" style={{ marginBottom: 4 }}>
                    Runs
                  </p>
                  <input
                    type="number"
                    value={runs}
                    min={100}
                    max={1000000}
                    onChange={(e) => setRuns(parseInt(e.target.value) || 50000)}
                    className="ag-input"
                    style={{ width: "100%" }}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <p className="ag-section-kicker" style={{ marginBottom: 4 }}>
                    Seed
                  </p>
                  <input
                    type="number"
                    value={seed}
                    min={0}
                    onChange={(e) => setSeed(parseInt(e.target.value) || 42)}
                    className="ag-input"
                    style={{ width: "100%" }}
                  />
                </div>
              </div>
            </div>

            <div className={css.varList}>
              {simVars.length === 0 && (
                <p
                  className="ag-caption"
                  style={{ textAlign: "center", padding: "16px 0" }}
                >
                  Select a template to see variables
                </p>
              )}
              {simVars.map((v, i) => {
                const name = v.name as string;
                const dist = v.distribution as string;
                const params = v.params as Record<string, number>;
                const unit = v.unit as string | undefined;
                const desc = v.description as string | undefined;
                const cur = vals[name] ?? paramVal(params);
                const lo = params.low ?? params.min ?? cur * 0.3;
                const hi = params.high ?? params.max ?? cur * 2;
                return (
                  <div key={i} className={css.varCard}>
                    <div className={css.varCardHeader}>
                      <span className={css.varCardName}>{name}</span>
                      <span className={css.varCardMeta}>
                        {dist}
                        {unit ? ` · ${unit}` : ""}
                      </span>
                    </div>
                    {desc && (
                      <p className="ag-caption" style={{ marginBottom: 4 }}>
                        {desc}
                      </p>
                    )}
                    <input
                      type="range"
                      min={lo}
                      max={hi}
                      step={(hi - lo) / 100}
                      value={cur}
                      onChange={(e) =>
                        handleSlider(name, parseFloat(e.target.value))
                      }
                      className={css.varSlider}
                    />
                    <div className={css.varSliderValues}>
                      <span>{fmtNum(lo)}</span>
                      <span
                        style={{
                          color: "var(--ag-brand-primary)",
                          fontWeight: 600,
                        }}
                      >
                        {fmtNum(cur)}
                      </span>
                      <span>{fmtNum(hi)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* MIDDLE: Editor */}
          <div className={css.middlePanel}>
            <div className={css.editorTabs}>
              {(["visual", "json"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setEditorTab(t)}
                  className={`${css.editorTab}${editorTab === t ? " " + css.editorTabActive : ""}`}
                >
                  {t === "visual" ? "Visual Editor" : "Raw JSON"}
                </button>
              ))}
            </div>
            {jsonError && <p className={css.jsonError}>{jsonError}</p>}
            <div className={css.editorArea}>
              <MonacoEditor
                height="100%"
                defaultLanguage="json"
                value={payload}
                onChange={handleJsonChange}
                theme="vs-dark"
                options={{
                  fontSize: 12,
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                  wordWrap: "on",
                  tabSize: 2,
                }}
              />
            </div>
          </div>

          {/* RIGHT: Results */}
          <div className={css.rightPanel}>
            <div className={css.rightPanelHeader}>
              <span className="ag-section-kicker">Results</span>
              {elapsed != null && result && (
                <span className="ag-caption">
                  {elapsed}ms · {result.scenarios_run?.toLocaleString()} runs
                </span>
              )}
            </div>
            <div className={css.rightPanelBody}>
              {running && (
                <div className={css.emptyState}>
                  <div className={css.spinner} />
                  <p className={css.emptyTitle}>Running simulation…</p>
                </div>
              )}
              {!running && !result && !error && (
                <div className={css.emptyState}>
                  <i className={`fa-solid fa-play ${css.emptyIcon}`} />
                  <p className={css.emptyTitle}>Click Run Simulation</p>
                  <p className={css.emptySubtitle}>
                    Adjust sliders and run to see full distribution, VaR, and
                    recommendation.
                  </p>
                </div>
              )}
              {error && (
                <div className={css.emptyState}>
                  <i
                    className="fa-solid fa-triangle-exclamation"
                    style={{ fontSize: 24, color: "var(--ag-danger)" }}
                  />
                  <p
                    className={css.emptyTitle}
                    style={{ color: "var(--ag-danger)" }}
                  >
                    Simulation Error
                  </p>
                  <p className={css.emptySubtitle}>{error}</p>
                </div>
              )}

              {result && !running && (
                <>
                  {/* Decision badge */}
                  <div className={`${css.decisionBadge} ${actionClass}`}>
                    <i
                      className={`fa-solid ${actionIcon} ${css.decisionIcon}`}
                    />
                    <div className={css.decisionText}>
                      <span className={css.decisionTitle}>
                        {result.recommended_action.charAt(0).toUpperCase() +
                          result.recommended_action.slice(1)}
                        {" · "}
                        {(result.confidence * 100).toFixed(1)}% confidence
                      </span>
                      <span className={css.decisionRationale}>
                        {result.rationale}
                      </span>
                    </div>
                  </div>

                  {/* Metrics grid */}
                  <div className={css.resultSection}>
                    <p className="ag-section-kicker">Key Metrics</p>
                    <div className={css.metricGrid}>
                      {[
                        ["Expected Value", fmtNum(ev)],
                        ["Std Deviation", fmtNum(result.metrics.std_deviation)],
                        ["Median (P50)", fmtNum(result.metrics.median)],
                        ["VaR 95%", fmtNum(result.metrics.var_95)],
                        ["VaR 95%", fmtNum(result.metrics.var_95)],
                        ["Prob of Loss", (pol * 100).toFixed(1) + "%"],
                      ].map(([l, v]) => (
                        <div key={l} className={css.metricTile}>
                          <p className={css.metricTileLabel}>{l}</p>
                          <p
                            className={`${css.metricTileValue}${l === "Prob of Loss" ? (pol > 0.35 ? " " + css["metricTileValue--danger"] : pol > 0.2 ? " " + css["metricTileValue--warning"] : "") : ""}`}
                          >
                            {v}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Percentiles */}
                  <div className={css.resultSection}>
                    <p className="ag-section-kicker">Percentiles</p>
                    <div className={css.metricGrid}>
                      {(
                        [
                          "p5",
                          "p10",
                          "p25",
                          "p50",
                          "p75",
                          "p90",
                          "p95",
                          "p99",
                        ] as const
                      ).map((k) => (
                        <div key={k} className={css.metricTile}>
                          <p className={css.metricTileLabel}>
                            {k.toUpperCase()}
                          </p>
                          <p className={css.metricTileValue}>
                            {fmtNum(
                              (result.percentiles as Record<string, number>)[k],
                            )}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Distribution chart */}
                  <div className={css.resultSection}>
                    <p className="ag-section-kicker">Distribution (approx.)</p>
                    <Plot
                      data={[
                        {
                          type: "scatter" as const,
                          mode: "lines" as const,
                          x: distX,
                          y: distY,
                          fill: "tozeroy",
                          line: { color: "#6b42fc", width: 1.5 },
                          fillcolor: "rgba(107,66,252,0.12)",
                        },
                      ]}
                      layout={{ ...DL, height: 100 }}
                    />
                  </div>

                  {/* Integrity */}
                  <div className={css.resultSection}>
                    <p className="ag-section-kicker">Integrity</p>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 4,
                      }}
                    >
                      {[
                        [
                          "Run ID",
                          result.run_id?.toString().slice(0, 16) + "…",
                        ],
                        ["Result Hash", result.result_hash?.slice(0, 16) + "…"],
                        ["Engine", result.engine_version],
                        ["Mode", mode],
                      ].map(([k, v]) => (
                        <div
                          key={k}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: 11,
                          }}
                        >
                          <span className="ag-caption">{k}</span>
                          <span className="ag-mono" style={{ fontSize: 10 }}>
                            {v || "—"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Raw JSON */}
                  <details className="ag-card" style={{ overflow: "hidden" }}>
                    <summary
                      style={{
                        padding: "8px 12px",
                        fontSize: 11,
                        fontWeight: 700,
                        letterSpacing: "0.08em",
                        textTransform: "uppercase" as const,
                        color: "var(--ag-text-muted)",
                        cursor: "pointer",
                      }}
                    >
                      Raw API Response
                    </summary>
                    <pre
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        color: "var(--ag-text-secondary)",
                        padding: "0 12px 12px",
                        overflow: "auto",
                        maxHeight: 400,
                        margin: 0,
                        wordBreak: "break-all" as const,
                        whiteSpace: "pre-wrap" as const,
                      }}
                    >
                      {JSON.stringify(
                        result,
                        (_, v) => (v === null ? undefined : v),
                        2,
                      )}
                    </pre>
                  </details>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
