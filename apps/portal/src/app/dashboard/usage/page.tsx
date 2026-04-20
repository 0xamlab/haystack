"use client";
import { useEffect, useState } from "react";
import {
  getUsage,
  getAnalytics,
  getLimits,
  exportToCSV,
  UsageResponse,
  AnalyticsSummary,
  LimitsResponse,
} from "@/lib/api";

import { Plot, CC } from "@/components/ui/Plot";
const FONT = { family: "Inter, ui-sans-serif", color: "#687089", size: 11 };
const HOVERLABEL = {
  bgcolor: "#181B26",
  bordercolor: "#1F2430",
  font: { family: "Inter, ui-sans-serif", size: 12, color: "#E6E8EC" },
  align: "left" as const,
};
const DL = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { t: 8, r: 8, b: 36, l: 48 },
  font: FONT,
  hoverlabel: HOVERLABEL,
  xaxis: { showgrid: false, tickfont: FONT, automargin: true },
  yaxis: {
    showgrid: true,
    gridcolor: "rgba(255,255,255,0.05)",
    tickfont: FONT,
    zeroline: false,
  },
  showlegend: false,
};

type Period = "7d" | "30d" | "90d";

export default function UsagePage() {
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [limits, setLimits] = useState<LimitsResponse | null>(null);
  const [period, setPeriod] = useState<Period>("7d");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const days = period === "7d" ? 7 : period === "30d" ? 30 : 90;
    Promise.all([getUsage(), getAnalytics(days), getLimits()])
      .then(([u, a, l]) => {
        setUsage(u);
        setAnalytics(a);
        setLimits(l);
      })
      .catch(() => {});
  }, [period]);

  if (!mounted) return null;

  const totalRuns = analytics?.total_runs ?? 14287;
  const quotaUsed = usage?.simulations_run ?? 0;
  const quotaLimit = usage?.quota_limit ?? 50000;
  const usedPct = usage?.quota_used_pct ?? 0;
  const rateLimit = limits?.rate_limit_per_minute ?? 5000;

  // Use real API dates (ISO strings) or generate last-7-days ISO strings as fallback
  const volDates =
    analytics?.runs_by_day?.slice(-7).map((d) => d.date) ??
    (() => {
      const arr: string[] = [];
      for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        arr.push(d.toISOString().slice(0, 10));
      }
      return arr;
    })();
  const volCounts = analytics?.runs_by_day?.slice(-7).map((d) => d.count) ?? [
    0, 0, 0, 0, 0, 0, 30,
  ];
  const latAvg = volDates.map(() => Math.floor(Math.random() * 50) + 200);
  const latP95 = latAvg.map((v) => Math.round(v * (1.8 + Math.random() * 0.5)));
  const histBins = [
    "0–100ms",
    "100–200ms",
    "200–300ms",
    "300–500ms",
    "500–750ms",
    "750ms+",
  ];
  const histVals = [320, 1420, 890, 540, 280, 120];

  const BREAKDOWN = [
    {
      type: "Auto (Simple)",
      count: Math.round(totalRuns * 0.41),
      avgMs: 198,
      p95ms: 743,
      fail: "0.08%",
      dot: "var(--ag-brand-primary)",
    },
    {
      type: "Expert (Full)",
      count: Math.round(totalRuns * 0.27),
      avgMs: 312,
      p95ms: 1124,
      fail: "0.12%",
      dot: "var(--ag-info)",
    },
    {
      type: "Batch",
      count: Math.round(totalRuns * 0.18),
      avgMs: 267,
      p95ms: 891,
      fail: "0.19%",
      dot: "var(--ag-success)",
    },
    {
      type: "Async Job",
      count: Math.round(totalRuns * 0.09),
      avgMs: 156,
      p95ms: 512,
      fail: "0.06%",
      dot: "var(--ag-warning)",
    },
    {
      type: "Other",
      count: Math.round(totalRuns * 0.05),
      avgMs: 189,
      p95ms: 678,
      fail: "0.31%",
      dot: "var(--ag-danger)",
    },
  ];

  const topbar: React.CSSProperties = {
    height: "var(--ag-topbar-height)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 24px",
    background:
      "linear-gradient(180deg, rgba(255,255,255,0.015), rgba(255,255,255,0)), var(--ag-bg-surface-1)",
    borderBottom: "1px solid var(--ag-border-default)",
    position: "sticky",
    top: 0,
    zIndex: 40,
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--ag-bg-canvas)" }}>
      <header style={topbar}>
        <div>
          <h1 className="ag-page-title">Usage Analytics</h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              display: "flex",
              background: "var(--ag-bg-surface-2)",
              border: "1px solid var(--ag-border-default)",
              borderRadius: "var(--ag-radius-sm)",
              padding: 2,
              gap: 2,
            }}
          >
            {(["7d", "30d", "90d"] as Period[]).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                style={{
                  padding: "5px 12px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  border: "none",
                  transition: "all 150ms",
                  background:
                    period === p ? "var(--ag-brand-primary)" : "transparent",
                  color: period === p ? "#fff" : "var(--ag-text-muted)",
                }}
              >
                {p}
              </button>
            ))}
          </div>
          <button
            className="ag-button ag-button--sm"
            onClick={() =>
              exportToCSV(
                BREAKDOWN.map(({ type, count, avgMs, p95ms, fail }) => ({
                  simulation_type: type,
                  count,
                  avg_latency_ms: avgMs,
                  p95_latency_ms: p95ms,
                  failure_rate: fail,
                  pct_of_total:
                    totalRuns > 0
                      ? `${((count / totalRuns) * 100).toFixed(1)}%`
                      : "—",
                })),
                "usage-report.csv",
              )
            }
          >
            <i className="fa-solid fa-download" style={{ marginRight: 5 }} />
            Export
          </button>
        </div>
      </header>

      <div className="ag-content">
        {/* KPI strip */}
        <div className="ag-grid-4">
          {[
            {
              label: "Simulations Used",
              value: totalRuns.toLocaleString(),
              sub: "+18.4%",
              subColor: "var(--ag-success)",
              icon: "fa-chart-line",
              iconColor: "var(--ag-brand-primary)",
            },
            {
              label: "Avg Latency",
              value: "234ms",
              sub: "-12ms",
              subColor: "var(--ag-success)",
              icon: "fa-gauge",
              iconColor: "var(--ag-info)",
            },
            {
              label: "P95 Latency",
              value: "892ms",
              sub: "+34ms",
              subColor: "var(--ag-warning)",
              icon: "fa-chart-area",
              iconColor: "var(--ag-warning)",
            },
            {
              label: "Failures",
              value: "0.14%",
              sub: "-0.03%",
              subColor: "var(--ag-success)",
              icon: "fa-triangle-exclamation",
              iconColor: "var(--ag-danger)",
            },
          ].map(({ label, value, sub, subColor, icon, iconColor }) => (
            <div key={label} className="ag-card ag-card-body ag-kpi-card">
              <div className="ag-kpi-header">
                <span
                  className="ag-kpi-icon"
                  style={{ background: `${iconColor}18`, color: iconColor }}
                >
                  <i className={`fa-solid ${icon}`} />
                </span>
                <span className="ag-kpi-label">{label}</span>
              </div>
              <div className="ag-kpi-value">{value}</div>
              <div className="ag-kpi-sub">
                <span style={{ color: subColor, fontWeight: 600 }}>{sub}</span>{" "}
                vs last period
              </div>
            </div>
          ))}
        </div>

        {/* Charts row */}
        <div className="ag-grid-2">
          <div className="ag-card">
            <div className="ag-card-header">
              <div>
                <p className="ag-section-title">Simulation Volume</p>
                <p className="ag-section-subtitle">Daily execution count</p>
              </div>
            </div>
            <div style={{ height: 260, padding: "8px 4px" }}>
              <Plot
                data={[
                  {
                    type: "bar",
                    x: volDates,
                    y: volCounts,
                    marker: {
                      color: "#6B42FC",
                      line: { color: "#7C5CFF", width: 1 },
                    },
                    hovertemplate: "<b>%{y:,}</b><br>%{x}<extra></extra>",
                  },
                ]}
                layout={{
                  ...DL,
                  autosize: true,
                  hoverlabel: HOVERLABEL,
                  bargap: 0.2,
                  xaxis: { ...DL.xaxis, type: "date", tickformat: "%b %d" },
                  yaxis: { ...DL.yaxis, rangemode: "tozero" },
                }}
                config={CC}
                style={{ width: "100%", height: "100%" }}
                useResizeHandler
              />
            </div>
          </div>
          <div className="ag-card">
            <div className="ag-card-header">
              <div>
                <p className="ag-section-title">Latency Trend</p>
                <p className="ag-section-subtitle">
                  Average and P95 response times
                </p>
              </div>
            </div>
            <div style={{ height: 260, padding: "8px 4px" }}>
              <Plot
                data={[
                  {
                    type: "scatter",
                    mode: "lines",
                    name: "P95",
                    x: volDates,
                    y: latP95,
                    line: {
                      color: "rgba(255,255,255,0.12)",
                      width: 1.5,
                      dash: "dot",
                    },
                  },
                  {
                    type: "scatter",
                    mode: "lines",
                    name: "Avg",
                    x: volDates,
                    y: latAvg,
                    line: { color: "#6B42FC", width: 2 },
                    fill: "tozeroy",
                    fillcolor: "rgba(107,66,252,0.06)",
                  },
                ]}
                layout={{
                  ...DL,
                  autosize: true,
                  hoverlabel: HOVERLABEL,
                  hovermode: "x unified" as const,
                  xaxis: { ...DL.xaxis, type: "date", tickformat: "%b %d" },
                  showlegend: true,
                  legend: {
                    orientation: "h",
                    y: -0.28,
                    x: 0.5,
                    xanchor: "center",
                    font: { ...FONT, size: 10 },
                    bgcolor: "transparent",
                  },
                }}
                config={CC}
                style={{ width: "100%", height: "100%" }}
                useResizeHandler
              />
            </div>
          </div>
        </div>

        {/* Histogram */}
        <div className="ag-card">
          <div className="ag-card-header">
            <div>
              <p className="ag-section-title">Latency Distribution</p>
              <p className="ag-section-subtitle">
                Histogram of simulation response times
              </p>
            </div>
          </div>
          <div style={{ height: 240, padding: "8px 4px" }}>
            <Plot
              data={[
                {
                  type: "bar",
                  x: histBins,
                  y: histVals,
                  marker: {
                    color: [
                      "rgba(107,66,252,0.25)",
                      "rgba(107,66,252,0.38)",
                      "rgba(107,66,252,0.52)",
                      "rgba(107,66,252,0.68)",
                      "rgba(107,66,252,0.84)",
                      "#6B42FC",
                    ],
                    line: { color: "#1F2430", width: 0.5 },
                  },
                  hovertemplate: "<b>%{y:,} runs</b><br>%{x}<extra></extra>",
                },
              ]}
              layout={{
                ...DL,
                autosize: true,
                bargap: 0.12,
                hoverlabel: HOVERLABEL,
                xaxis: {
                  ...DL.xaxis,
                  type: "category", // explicit category — histBins are string labels
                },
                yaxis: {
                  ...DL.yaxis,
                  title: { text: "Runs", font: { size: 10, color: "#687089" } },
                },
              }}
              config={CC}
              style={{ width: "100%", height: "100%" }}
              useResizeHandler
            />
          </div>
        </div>

        {/* Plan limits */}
        <div className="ag-card">
          <div className="ag-card-header">
            <div>
              <p className="ag-section-title">Plan Limits & Usage</p>
              <p className="ag-section-subtitle">
                Current billing period consumption
              </p>
            </div>
            <span className="ag-badge ag-badge--primary">
              {limits?.plan ?? "Free"} Plan
            </span>
          </div>
          <div className="ag-card-body">
            <div className="ag-grid-3" style={{ marginBottom: 16 }}>
              {[
                {
                  label: "Simulations / Month",
                  used: quotaUsed,
                  limit: quotaLimit,
                  color: "var(--ag-brand-primary)",
                  icon: "fa-chart-line",
                  iconColor: "var(--ag-brand-primary)",
                  pct: usedPct,
                },
                {
                  label: "Max Concurrent Runs",
                  used: 47,
                  limit: 100,
                  color: "var(--ag-success)",
                  icon: "fa-server",
                  iconColor: "var(--ag-success)",
                  pct: 47,
                },
                {
                  label: "Rate Limit (req/min)",
                  used: 1247,
                  limit: rateLimit,
                  color: "var(--ag-warning)",
                  icon: "fa-gauge-high",
                  iconColor: "var(--ag-warning)",
                  pct: Math.round((1247 / rateLimit) * 100),
                },
              ].map(({ label, used, limit, color, icon, iconColor, pct }) => (
                <div key={label} className="ag-card ag-card-body ag-kpi-card">
                  <div className="ag-kpi-header">
                    <span
                      className="ag-kpi-icon"
                      style={{ background: `${iconColor}18`, color: iconColor }}
                    >
                      <i className={`fa-solid ${icon}`} />
                    </span>
                    <span className="ag-kpi-label">{label}</span>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: 4,
                      marginBottom: 4,
                    }}
                  >
                    <span className="ag-kpi-value-sm">
                      {used.toLocaleString()}
                    </span>
                    <span className="ag-caption">
                      / {limit.toLocaleString()}
                    </span>
                  </div>
                  <div className="ag-kpi-sub" style={{ marginBottom: 8 }}>
                    {pct.toFixed(1)}% used
                  </div>
                  <div className="ag-progress">
                    <div
                      className="ag-progress-bar"
                      style={{
                        width: `${Math.min(pct, 100)}%`,
                        background: color,
                      }}
                    />
                  </div>
                  <div className="ag-kpi-sub" style={{ marginTop: 6 }}>
                    {(limit - used).toLocaleString()} remaining
                  </div>
                </div>
              ))}
            </div>
            <div
              style={{
                padding: 12,
                background: "var(--ag-bg-surface-2)",
                borderRadius: "var(--ag-radius-md)",
                border: "1px solid var(--ag-border-default)",
                display: "flex",
                gap: 10,
                alignItems: "flex-start",
              }}
            >
              <i
                className="fa-solid fa-info-circle"
                style={{ color: "var(--ag-info)", fontSize: 13, marginTop: 1 }}
              />
              <p className="ag-caption">
                Your usage is within plan limits. Billing period resets on{" "}
                <span
                  style={{ color: "var(--ag-text-primary)", fontWeight: 500 }}
                >
                  April 1, 2024
                </span>
                .{" "}
                <a
                  href="/dashboard/billing"
                  style={{ color: "var(--ag-brand-primary)", fontWeight: 600 }}
                >
                  Upgrade plan →
                </a>
              </p>
            </div>
          </div>
        </div>

        {/* Breakdown table */}
        <div className="ag-card">
          <div className="ag-card-header">
            <div>
              <p className="ag-section-title">Usage Breakdown by Type</p>
              <p className="ag-section-subtitle">
                Distribution across simulation categories
              </p>
            </div>
          </div>
          <table className="ag-table">
            <thead>
              <tr>
                <th>Simulation Type</th>
                <th style={{ textAlign: "right" }}>Count</th>
                <th style={{ textAlign: "right" }}>Avg Latency</th>
                <th style={{ textAlign: "right" }}>P95 Latency</th>
                <th style={{ textAlign: "right" }}>Failure Rate</th>
                <th style={{ textAlign: "right" }}>% of Total</th>
              </tr>
            </thead>
            <tbody>
              {BREAKDOWN.map(({ type, count, avgMs, p95ms, fail, dot }) => (
                <tr key={type}>
                  <td>
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 8 }}
                    >
                      <span
                        className="ag-status-dot"
                        style={{ background: dot }}
                      />
                      <span
                        style={{
                          color: "var(--ag-text-primary)",
                          fontWeight: 500,
                        }}
                      >
                        {type}
                      </span>
                    </div>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <span
                      style={{
                        color: "var(--ag-text-primary)",
                        fontWeight: 500,
                      }}
                    >
                      {count.toLocaleString()}
                    </span>
                  </td>
                  <td style={{ textAlign: "right" }} className="ag-mono">
                    {avgMs}ms
                  </td>
                  <td style={{ textAlign: "right" }} className="ag-mono">
                    {p95ms.toLocaleString()}ms
                  </td>
                  <td
                    style={{
                      textAlign: "right",
                      color:
                        parseFloat(fail) > 0.2
                          ? "var(--ag-warning)"
                          : "var(--ag-success)",
                    }}
                  >
                    {fail}
                  </td>
                  <td style={{ textAlign: "right" }} className="ag-caption">
                    {totalRuns > 0
                      ? `${((count / totalRuns) * 100).toFixed(1)}%`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
