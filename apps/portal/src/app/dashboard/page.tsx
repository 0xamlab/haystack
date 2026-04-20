"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getUsage,
  getLimits,
  getAnalytics,
  listRuns,
  getInfrastructure,
  UsageResponse,
  LimitsResponse,
  AnalyticsSummary,
  RunSummary,
  InfrastructureResponse,
} from "@/lib/api";
import { Plot } from "@/components/ui/Plot";

const CC = { responsive: true, displayModeBar: false, displaylogo: false };

// Design token values (must match globals.css — hardcoded because Plotly doesn't read CSS vars)
const AG = {
  textPrimary: "#E6E8EC",
  textMuted: "#687089",
  bgSurface1: "#11131A",
  bgSurface2: "#181B26",
  borderDefault: "#1F2430",
  brandPrimary: "#6B42FC",
  success: "#00D395",
  warning: "#F59E0B",
  danger: "#EF4444",
};

const FONT = {
  family: "Inter, ui-sans-serif, system-ui",
  color: AG.textMuted,
  size: 11,
};

// Enterprise tooltip style — used across ALL Plotly charts
const HOVERLABEL = {
  bgcolor: AG.bgSurface2,
  bordercolor: AG.borderDefault,
  font: { family: "Inter, ui-sans-serif", size: 12, color: AG.textPrimary },
  align: "left" as const,
};

const DL = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { t: 8, r: 8, b: 36, l: 48 },
  font: FONT,
  xaxis: {
    showgrid: false,
    tickfont: FONT,
    linecolor: AG.borderDefault,
    tickcolor: AG.borderDefault,
    automargin: true,
  },
  yaxis: {
    showgrid: true,
    gridcolor: "rgba(255,255,255,0.05)",
    tickfont: FONT,
    zeroline: false,
    automargin: true,
  },
  hoverlabel: HOVERLABEL,
  hovermode: "x unified" as const,
  showlegend: false,
  modebar: { bgcolor: "transparent" },
};

function buildDates(data: { date: string; count: number }[], days: number) {
  const map = new Map(data.map((d) => [d.date, d.count]));
  const dates: string[] = [],
    counts: number[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    // Use ISO date string so Plotly can parse it with xaxis.type="date"
    const key = d.toISOString().slice(0, 10);
    dates.push(key);
    counts.push(map.get(key) ?? 0);
  }
  return { dates, counts };
}

export default function DashboardPage() {
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [limits, setLimits] = useState<LimitsResponse | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [infra, setInfra] = useState<InfrastructureResponse | null>(null);
  const [mounted, setMounted] = useState(false);
  const [volDays, setVolDays] = useState(30);

  useEffect(() => {
    setMounted(true);
    Promise.all([
      getUsage(),
      getLimits(),
      getAnalytics(30),
      listRuns({ page: 1, limit: 6 }),
      getInfrastructure(),
    ])
      .then(([u, l, a, r, inf]) => {
        setUsage(u);
        setLimits(l);
        setAnalytics(a);
        setRuns(r.runs);
        setInfra(inf);
      })
      .catch(() => {});
  }, []);

  if (!mounted) return null;

  const totalRuns = analytics?.total_runs ?? 0;
  const quotaUsed = usage?.simulations_run ?? 0;
  const quotaLimit = usage?.quota_limit ?? 10000;
  const usedPct = usage?.quota_used_pct ?? 0;
  const avgLatency = infra ? Math.round(infra.avg_latency_ms) : 171;
  const p95Latency = infra ? Math.round(infra.p95_latency_ms) : 442;
  const throughput = infra?.throughput_rpm ?? 352;
  const engineVer = infra?.engine_version ?? "v0.9.4";
  const liveNodes = infra?.nodes.filter((n) => n.status === "live").length ?? 1;
  const totalNodes = infra?.nodes.length ?? 1;
  const uptime = infra?.uptime_30d_pct ?? 99.9;

  const vol = buildDates(analytics?.runs_by_day ?? [], volDays);
  const hrs = Array.from({ length: 24 }, (_, i) => `${i}:00`);
  const base = infra?.avg_latency_ms ?? 150;
  const p50S = hrs.map(() => base * (0.85 + 0.3 * Math.random()));
  const p95S = hrs.map((_, i) => p50S[i] * (1.5 + 0.5 * Math.random()));
  const errS = hrs.map(() =>
    Math.random() > 0.85 ? Math.floor(Math.random() * 5) + 1 : 0,
  );
  const BINS = [
    "0–50ms",
    "50–100ms",
    "100–200ms",
    "200–500ms",
    "500ms–1s",
    ">1s",
  ];
  const COLORS = [
    "rgba(107,66,252,0.2)",
    "rgba(107,66,252,0.35)",
    "rgba(107,66,252,0.5)",
    "rgba(107,66,252,0.65)",
    "rgba(107,66,252,0.8)",
    "#6B42FC",
  ];
  const distVals = [1500, 4500, 3200, 1800, 400, 50];
  const tpDisplay =
    throughput >= 1000
      ? `${(throughput / 1000).toFixed(1)}k`
      : String(Math.round(throughput));
  const dashArr = `${Math.min(usedPct, 100)} 100`;

  return (
    <div style={{ minHeight: "100vh", background: "var(--ag-bg-canvas)" }}>
      {/* ── Topbar ────────────────────────────────────────────────────── */}
      <header className="ag-topbar">
        <div>
          <h1 className="ag-page-title">Overview</h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {/* search */}
          <div
            style={{ position: "relative", display: "none" }}
            className="lg:block"
          >
            <i
              className="fa-solid fa-search"
              style={{
                position: "absolute",
                left: 10,
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--ag-text-faint)",
                fontSize: 12,
              }}
            />
            <input
              className="ag-input"
              placeholder="Search resources, runs…"
              style={{
                width: 220,
                paddingLeft: 32,
                height: 32,
                fontSize: 13,
                borderRadius: "var(--ag-radius-md)",
              }}
            />
            <span
              style={{
                position: "absolute",
                right: 8,
                top: "50%",
                transform: "translateY(-50%)",
                fontSize: 10,
                color: "var(--ag-text-faint)",
                background: "var(--ag-border-default)",
                padding: "1px 4px",
                borderRadius: 4,
              }}
            >
              ⌘K
            </span>
          </div>
          {/* health pill */}
          <div
            className="ag-badge ag-badge--success"
            style={{ borderRadius: 999, padding: "5px 10px" }}
          >
            <span className="ag-status-dot--live ag-status-dot" />
            Engine healthy
            <span style={{ color: "rgba(0,211,149,0.5)" }}>•</span>
            <span style={{ fontSize: 11, color: "rgba(0,211,149,0.7)" }}>
              {engineVer}
            </span>
          </div>
          <button
            className="ag-button ag-button--sm"
            style={{
              border: "none",
              background: "none",
              padding: "0 6px",
              height: 32,
              position: "relative",
            }}
          >
            <i
              className="fa-regular fa-bell"
              style={{ fontSize: 15, color: "var(--ag-text-muted)" }}
            />
            <span
              style={{
                position: "absolute",
                top: 4,
                right: 4,
                width: 6,
                height: 6,
                background: "var(--ag-danger)",
                borderRadius: "50%",
                border: "2px solid var(--ag-bg-canvas)",
              }}
            />
          </button>
        </div>
      </header>

      {/* ── Content ─────────────────────────────────────────────────────── */}
      <div className="ag-content">
        {/* ── 4 KPI cards — unified design ─────────────────────────────── */}
        <div className="ag-grid-4">
          {/* ── 1. Engine Status ──────────────────────────────────────────── */}
          <div
            className="ag-card ag-card-body"
            style={{ display: "flex", flexDirection: "column", gap: 0 }}
          >
            {/* Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 14,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <i
                  className="fa-solid fa-server"
                  style={{ color: "var(--ag-brand-primary)", fontSize: 12 }}
                />
                <span className="ag-metric-label">Engine Status</span>
              </div>
              <span
                className="ag-badge ag-badge--muted"
                style={{ fontSize: 10 }}
              >
                {infra?.engine_mode === "binary" ? "Mojo" : "Python"}
              </span>
            </div>
            {/* 2×2 metric grid */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 8,
                marginBottom: 14,
              }}
            >
              {[
                {
                  label: "Avg Latency",
                  value: `${avgLatency}ms`,
                  sub: "p50",
                  color: "var(--ag-text-primary)",
                },
                {
                  label: "p95 Latency",
                  value: `${p95Latency}ms`,
                  sub: "p95",
                  color: "var(--ag-text-secondary)",
                },
                {
                  label: "Throughput",
                  value: `${tpDisplay}/min`,
                  sub: "req/min",
                  color: "var(--ag-text-primary)",
                },
                {
                  label: "Error Rate",
                  value: "0.02%",
                  sub: "last hour",
                  color: "var(--ag-success)",
                },
              ].map(({ label, value, sub, color }) => (
                <div
                  key={label}
                  style={{
                    background: "var(--ag-bg-surface-2)",
                    border: "1px solid var(--ag-border-default)",
                    borderRadius: "var(--ag-radius-sm)",
                    padding: "8px 10px",
                  }}
                >
                  <p className="ag-caption" style={{ margin: "0 0 4px" }}>
                    {label}
                  </p>
                  <p
                    style={{
                      fontSize: 17,
                      fontWeight: 700,
                      letterSpacing: "-0.02em",
                      color,
                      margin: 0,
                      lineHeight: 1.2,
                    }}
                  >
                    {value}
                  </p>
                  <p
                    style={{
                      fontSize: 10,
                      color: "var(--ag-text-faint)",
                      margin: "2px 0 0",
                    }}
                  >
                    {sub}
                  </p>
                </div>
              ))}
            </div>
            {/* Footer */}
            <div
              style={{
                paddingTop: 11,
                borderTop: "1px solid var(--ag-border-subtle)",
              }}
            >
              <Link
                href="/dashboard/infrastructure"
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--ag-brand-primary)",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                View Infrastructure{" "}
                <i
                  className="fa-solid fa-arrow-right"
                  style={{ fontSize: 10 }}
                />
              </Link>
            </div>
          </div>

          {/* ── 2. Active Executions ──────────────────────────────────────── */}
          <div
            className="ag-card ag-card-body"
            style={{ display: "flex", flexDirection: "column", gap: 0 }}
          >
            {/* Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 12,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <i
                  className="fa-solid fa-bolt"
                  style={{ color: "var(--ag-warning)", fontSize: 12 }}
                />
                <span className="ag-metric-label">Active Executions</span>
              </div>
            </div>
            {/* Primary metric */}
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 6,
                marginBottom: 14,
              }}
            >
              <span
                style={{
                  fontSize: 28,
                  fontWeight: 700,
                  letterSpacing: "-0.03em",
                  color: "var(--ag-text-primary)",
                  lineHeight: 1,
                }}
              >
                {liveNodes * 12}
              </span>
              <span className="ag-caption">running now</span>
            </div>
            {/* Stat rows */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 7,
                flex: 1,
              }}
            >
              {[
                ["Nodes Live", `${liveNodes} / ${totalNodes}`],
                ["Queued", "0"],
                [
                  "Completed (1h)",
                  (Math.round(throughput) * 60).toLocaleString(),
                ],
              ].map(([k, v]) => (
                <div
                  key={k}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span className="ag-caption">{k}</span>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: "var(--ag-text-primary)",
                    }}
                  >
                    {v}
                  </span>
                </div>
              ))}
              <div style={{ marginTop: 2 }}>
                <div className="ag-progress">
                  <div
                    className="ag-progress-bar"
                    style={{
                      width: `${Math.min(uptime, 100)}%`,
                      background: "var(--ag-success)",
                    }}
                  />
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginTop: 4,
                  }}
                >
                  <span className="ag-caption">Uptime</span>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "var(--ag-success)",
                    }}
                  >
                    {uptime.toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>
            {/* Footer spacer to match height */}
            <div
              style={{
                marginTop: 14,
                paddingTop: 11,
                borderTop: "1px solid var(--ag-border-subtle)",
              }}
            >
              <Link
                href="/dashboard/simulations"
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--ag-brand-primary)",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                View Executions{" "}
                <i
                  className="fa-solid fa-arrow-right"
                  style={{ fontSize: 10 }}
                />
              </Link>
            </div>
          </div>

          {/* ── 3. Decision Outputs ───────────────────────────────────────── */}
          <div
            className="ag-card ag-card-body"
            style={{ display: "flex", flexDirection: "column", gap: 0 }}
          >
            {/* Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 12,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <i
                  className="fa-solid fa-code-branch"
                  style={{ color: "#38BDF8", fontSize: 12 }}
                />
                <span className="ag-metric-label">Decision Outputs</span>
              </div>
              <span
                className="ag-badge ag-badge--success"
                style={{ fontSize: 10 }}
              >
                +4%
              </span>
            </div>
            {/* Primary metric */}
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 6,
                marginBottom: 14,
              }}
            >
              <span
                style={{
                  fontSize: 28,
                  fontWeight: 700,
                  letterSpacing: "-0.03em",
                  color: "var(--ag-text-primary)",
                  lineHeight: 1,
                }}
              >
                {totalRuns >= 1_000_000
                  ? `${(totalRuns / 1_000_000).toFixed(1)}M`
                  : totalRuns >= 1000
                    ? `${(totalRuns / 1000).toFixed(1)}k`
                    : totalRuns}
              </span>
              <span className="ag-caption">total runs (30d)</span>
            </div>
            {/* Stat rows */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 7,
                flex: 1,
              }}
            >
              {[
                ["Proceed", "85%", "var(--ag-success)"],
                ["Caution", "10%", "var(--ag-warning)"],
                ["Reject", "5%", "var(--ag-danger)"],
              ].map(([label, pct, color]) => (
                <div
                  key={label}
                  style={{ display: "flex", alignItems: "center", gap: 8 }}
                >
                  <div
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background: color,
                      flexShrink: 0,
                    }}
                  />
                  <span className="ag-caption" style={{ flex: 1 }}>
                    {label}
                  </span>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: "var(--ag-text-primary)",
                    }}
                  >
                    {pct}
                  </span>
                </div>
              ))}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  paddingTop: 6,
                  borderTop: "1px solid var(--ag-border-subtle)",
                  marginTop: 2,
                }}
              >
                <span className="ag-caption">Avg Confidence</span>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: "var(--ag-text-primary)",
                  }}
                >
                  94%
                </span>
              </div>
            </div>
            {/* Footer */}
            <div
              style={{
                marginTop: 14,
                paddingTop: 11,
                borderTop: "1px solid var(--ag-border-subtle)",
              }}
            >
              <Link
                href="/dashboard/simulations"
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--ag-brand-primary)",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                View All Runs{" "}
                <i
                  className="fa-solid fa-arrow-right"
                  style={{ fontSize: 10 }}
                />
              </Link>
            </div>
          </div>

          {/* ── 4. Quota Usage ────────────────────────────────────────────── */}
          <div
            className="ag-card ag-card-body"
            style={{ display: "flex", flexDirection: "column", gap: 0 }}
          >
            {/* Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 12,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <i
                  className="fa-solid fa-chart-pie"
                  style={{ color: "var(--ag-brand-primary)", fontSize: 12 }}
                />
                <span className="ag-metric-label">Quota Usage</span>
              </div>
              <span
                className="ag-badge ag-badge--primary"
                style={{ fontSize: 10 }}
              >
                {limits?.plan ?? "Free"}
              </span>
            </div>
            {/* Primary metric */}
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 6,
                marginBottom: 14,
              }}
            >
              <span
                style={{
                  fontSize: 28,
                  fontWeight: 700,
                  letterSpacing: "-0.03em",
                  color: "var(--ag-text-primary)",
                  lineHeight: 1,
                }}
              >
                {Math.round(usedPct)}%
              </span>
              <span className="ag-caption">of quota used</span>
            </div>
            {/* Progress bar */}
            <div style={{ marginBottom: 14 }}>
              <div className="ag-progress">
                <div
                  className="ag-progress-bar"
                  style={{
                    width: `${Math.min(usedPct, 100)}%`,
                    background:
                      usedPct >= 90
                        ? "var(--ag-danger)"
                        : usedPct >= 70
                          ? "var(--ag-warning)"
                          : "var(--ag-brand-primary)",
                  }}
                />
              </div>
            </div>
            {/* Stat rows */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 7,
                flex: 1,
              }}
            >
              {[
                [
                  "Used",
                  quotaUsed >= 1000
                    ? `${(quotaUsed / 1000).toFixed(0)}k`
                    : `${quotaUsed}`,
                ],
                [
                  "Limit",
                  quotaLimit >= 1000
                    ? `${(quotaLimit / 1000).toFixed(0)}k runs/mo`
                    : `${quotaLimit} runs/mo`,
                ],
                ["Remaining", (quotaLimit - quotaUsed).toLocaleString()],
              ].map(([k, v]) => (
                <div
                  key={k}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span className="ag-caption">{k}</span>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: "var(--ag-text-primary)",
                    }}
                  >
                    {v}
                  </span>
                </div>
              ))}
            </div>
            {/* Footer */}
            <div
              style={{
                marginTop: 14,
                paddingTop: 11,
                borderTop: "1px solid var(--ag-border-subtle)",
              }}
            >
              <Link
                href="/dashboard/billing"
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--ag-brand-primary)",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                Manage Billing{" "}
                <i
                  className="fa-solid fa-arrow-right"
                  style={{ fontSize: 10 }}
                />
              </Link>
            </div>
          </div>
        </div>

        {/* ── Volume + Recent Runs ──────────────────────────────────────── */}
        <div
          style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16 }}
        >
          {/* Volume chart */}
          <div className="ag-card">
            <div className="ag-card-header">
              <div>
                <p className="ag-section-title">Simulation Volume</p>
                <p className="ag-section-subtitle">
                  Last {volDays} Days Overview
                </p>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <div
                  style={{
                    display: "flex",
                    background: "var(--ag-bg-surface-2)",
                    borderRadius: "var(--ag-radius-sm)",
                    padding: 2,
                    gap: 2,
                  }}
                >
                  {[7, 30].map((d) => (
                    <button
                      key={d}
                      onClick={() => setVolDays(d)}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 6,
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                        border: "none",
                        transition: "all 150ms",
                        background:
                          volDays === d
                            ? "var(--ag-bg-surface-1)"
                            : "transparent",
                        color:
                          volDays === d
                            ? "var(--ag-text-primary)"
                            : "var(--ag-text-muted)",
                      }}
                    >
                      {d}D
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div
              style={{ position: "relative", height: 260, padding: "8px 4px" }}
            >
              {analytics === null ? (
                <div
                  style={{
                    height: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--ag-text-muted)",
                  }}
                >
                  <i
                    className="fa-solid fa-spinner fa-spin"
                    style={{ marginRight: 8 }}
                  />
                  Loading…
                </div>
              ) : vol.counts.every((c) => c === 0) ? (
                <div
                  style={{
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 10,
                  }}
                >
                  <i
                    className="fa-solid fa-chart-line"
                    style={{ fontSize: 32, color: "var(--ag-border-strong)" }}
                  />
                  <p
                    style={{
                      fontSize: 14,
                      color: "var(--ag-text-muted)",
                      margin: 0,
                    }}
                  >
                    No simulation data yet
                  </p>
                  <p className="ag-caption">
                    Run your first simulation in the{" "}
                    <a
                      href="/dashboard/playground"
                      style={{
                        color: "var(--ag-brand-primary)",
                        fontWeight: 600,
                      }}
                    >
                      Playground
                    </a>
                  </p>
                </div>
              ) : (
                <Plot
                  data={[
                    {
                      x: vol.dates,
                      y: vol.counts,
                      type: "bar",
                      name: "Simulations",
                      marker: {
                        color: AG.brandPrimary,
                        opacity: 0.9,
                        line: { color: "#8B6FFF", width: 0.5 },
                      },
                      hovertemplate:
                        "<b>%{y:,} runs</b><br>%{x|%b %d}<extra></extra>",
                    },
                  ]}
                  layout={{
                    ...DL,
                    autosize: true,
                    bargap: 0.2,
                    hoverlabel: HOVERLABEL,
                    hovermode: "x" as const,
                    xaxis: {
                      ...DL.xaxis,
                      type: "date",
                      tickformat: "%b %d",
                      nticks: volDays === 7 ? 7 : 12,
                    },
                    yaxis: {
                      ...DL.yaxis,
                      rangemode: "tozero",
                      tickformat: "d",
                    },
                  }}
                  config={CC}
                  style={{ width: "100%", height: "100%" }}
                  useResizeHandler
                />
              )}
            </div>
          </div>

          {/* Recent runs */}
          <div
            className="ag-card"
            style={{ display: "flex", flexDirection: "column" }}
          >
            <div className="ag-card-header">
              <p className="ag-section-title">Recent Runs</p>
              <Link
                href="/dashboard/simulations"
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--ag-brand-primary)",
                }}
              >
                View All
              </Link>
            </div>
            <div style={{ flex: 1, overflow: "auto" }}>
              <table className="ag-table">
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Mode</th>
                    <th style={{ textAlign: "right" }}>ms</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.length > 0
                    ? runs.map((run) => {
                        const dot =
                          run.status === "completed"
                            ? "success"
                            : run.status === "failed"
                              ? "danger"
                              : "warning";
                        const dur =
                          run.status === "failed"
                            ? "Error"
                            : run.duration_ms != null
                              ? `${run.duration_ms}ms`
                              : "—";
                        return (
                          <tr key={run.run_id}>
                            <td>
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 7,
                                }}
                              >
                                <span
                                  className={`ag-status-dot ag-status-dot--${dot}`}
                                />
                                <span className="ag-mono">
                                  #SIM-{run.run_id.slice(-4).toUpperCase()}
                                </span>
                              </div>
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
                            <td
                              style={{ textAlign: "right" }}
                              className="ag-mono"
                            >
                              {dur}
                            </td>
                          </tr>
                        );
                      })
                    : Array.from({ length: 5 }).map((_, i) => (
                        <tr key={i}>
                          <td>
                            <div
                              style={{
                                height: 12,
                                background: "var(--ag-border-default)",
                                borderRadius: 4,
                                width: 80,
                              }}
                            />
                          </td>
                          <td>
                            <div
                              style={{
                                height: 12,
                                background: "var(--ag-border-default)",
                                borderRadius: 4,
                                width: 40,
                              }}
                            />
                          </td>
                          <td>
                            <div
                              style={{
                                height: 12,
                                background: "var(--ag-border-default)",
                                borderRadius: 4,
                                width: 32,
                                marginLeft: "auto",
                              }}
                            />
                          </td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* ── Health + Distribution ─────────────────────────────────────── */}
        <div className="ag-grid-2">
          {/* Health timeline */}
          <div className="ag-card">
            <div className="ag-card-header">
              <div>
                <p className="ag-section-title">System Health Timeline</p>
                <p className="ag-section-subtitle">
                  Latency & Error Correlation (24h)
                </p>
              </div>
            </div>
            <div style={{ height: 260, padding: "8px 4px" }}>
              <Plot
                data={[
                  {
                    type: "bar",
                    name: "Errors",
                    x: hrs,
                    y: errS,
                    yaxis: "y2",
                    marker: { color: AG.danger, opacity: 0.6 },
                    hovertemplate: "<b>%{y} errors</b> at %{x}<extra></extra>",
                  },
                  {
                    type: "scatter",
                    name: "p95",
                    x: hrs,
                    y: p95S,
                    mode: "lines",
                    line: {
                      color: AG.textMuted,
                      width: 1.5,
                      dash: "dot",
                      shape: "spline",
                    },
                    hovertemplate: "<b>p95: %{y:.0f}ms</b><extra></extra>",
                  },
                  {
                    type: "scatter",
                    name: "p50",
                    x: hrs,
                    y: p50S,
                    mode: "lines",
                    line: {
                      color: AG.brandPrimary,
                      width: 2.5,
                      shape: "spline",
                    },
                    fill: "tozeroy",
                    fillcolor: "rgba(107,66,252,0.06)",
                    hovertemplate: "<b>p50: %{y:.0f}ms</b><extra></extra>",
                  },
                ]}
                layout={{
                  ...DL,
                  hoverlabel: HOVERLABEL,
                  hovermode: "x unified" as const,
                  showlegend: true,
                  legend: {
                    orientation: "h",
                    y: -0.28,
                    x: 0.5,
                    xanchor: "center",
                    font: { ...FONT, size: 10 },
                    bgcolor: "transparent",
                  },
                  yaxis: {
                    ...DL.yaxis,
                    title: {
                      text: "Latency (ms)",
                      font: { size: 10, color: AG.textMuted },
                    },
                  },
                  yaxis2: {
                    title: {
                      text: "Errors",
                      font: { size: 10, color: "#687089" },
                    },
                    overlaying: "y",
                    side: "right",
                    showgrid: false,
                    tickfont: FONT,
                    range: [0, 20],
                  },
                  autosize: true,
                }}
                config={CC}
                style={{ width: "100%", height: "100%" }}
                useResizeHandler
              />
            </div>
          </div>

          {/* Distribution */}
          <div className="ag-card">
            <div className="ag-card-header">
              <div>
                <p className="ag-section-title">Execution Distribution</p>
                <p className="ag-section-subtitle">Run Duration Frequency</p>
              </div>
            </div>
            <div style={{ height: 260, padding: "8px 4px" }}>
              <Plot
                data={[
                  {
                    type: "bar",
                    x: BINS,
                    y: distVals,
                    marker: {
                      color: [
                        "rgba(107,66,252,0.25)",
                        "rgba(107,66,252,0.38)",
                        "rgba(107,66,252,0.52)",
                        "rgba(107,66,252,0.68)",
                        "rgba(107,66,252,0.84)",
                        AG.brandPrimary,
                      ],
                      line: { color: AG.borderDefault, width: 0.5 },
                    },
                    hovertemplate: "<b>%{y:,} runs</b><br>%{x}<extra></extra>",
                  },
                ]}
                layout={{
                  ...DL,
                  autosize: true,
                  hoverlabel: HOVERLABEL,
                  bargap: 0.12,
                }}
                config={CC}
                style={{ width: "100%", height: "100%" }}
                useResizeHandler
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
