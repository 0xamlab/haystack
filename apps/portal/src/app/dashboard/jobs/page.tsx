"use client";
import { useEffect, useState } from "react";
import { listJobs, cancelJob, exportToJSON, JobStatus } from "@/lib/api";

type Tab = "all" | "queued" | "running" | "completed" | "failed";
const TABS: { key: Tab; label: string }[] = [
  { key: "all", label: "All" },
  { key: "queued", label: "Queued" },
  { key: "running", label: "Running" },
  { key: "completed", label: "Completed" },
  { key: "failed", label: "Failed" },
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

function StatusBadge({ status }: { status: string }) {
  const m: Record<string, string> = {
    queued: "ag-badge--warning",
    running: "ag-badge--info",
    completed: "ag-badge--success",
    failed: "ag-badge--danger",
    cancelled: "ag-badge--muted",
  };
  const l: Record<string, string> = {
    queued: "Queued",
    running: "Running",
    completed: "Completed",
    failed: "Failed",
    cancelled: "Cancelled",
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

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("all");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);

  async function handleCancel(e: React.MouseEvent, jobId: string) {
    e.stopPropagation();
    setCancellingId(jobId);
    setCancelError(null);
    try {
      await cancelJob(jobId);
      setJobs((prev) =>
        prev.map((j) =>
          j.job_id === jobId ? { ...j, status: "cancelled" } : j,
        ),
      );
    } catch (err) {
      setCancelError(
        err instanceof Error ? err.message : "Failed to cancel job",
      );
    } finally {
      setCancellingId(null);
    }
  }

  useEffect(() => {
    setLoading(true);
    const params: Parameters<typeof listJobs>[0] = { page, limit: 10 };
    if (tab !== "all") params.status = tab;
    listJobs(params)
      .then((r) => {
        setJobs(r.jobs);
        setTotal(r.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, tab]);

  const queued = jobs.filter((j) => j.status === "queued").length;
  const running = jobs.filter((j) => j.status === "running").length;
  const completed = jobs.filter((j) => j.status === "completed").length;
  const totalShown = queued + running + completed || 1;

  return (
    <div style={{ minHeight: "100vh", background: "var(--ag-bg-canvas)" }}>
      <header style={topbar}>
        <div>
          <h1 className="ag-page-title">Async Job Queue</h1>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="ag-button ag-button--sm"
            onClick={() => setPage(1)}
          >
            <i className="fa-solid fa-rotate" style={{ marginRight: 5 }} />
            Refresh
          </button>
          <button className="ag-button ag-button--sm ag-button--primary">
            <i className="fa-solid fa-plus" style={{ marginRight: 5 }} />
            New Job
          </button>
        </div>
      </header>

      <div className="ag-content">
        {/* Queue pipeline */}
        <div className="ag-grid-3">
          {[
            {
              label: "Queued",
              count: queued,
              icon: "fa-clock",
              color: "var(--ag-brand-primary)",
              bar: "var(--ag-brand-primary)",
              pct: Math.round((queued / totalShown) * 100),
              sub: "Waiting for execution",
            },
            {
              label: "Running",
              count: running,
              icon: "fa-spinner",
              color: "var(--ag-info)",
              bar: "var(--ag-info)",
              pct: Math.round((running / totalShown) * 100),
              sub: "Currently processing",
            },
            {
              label: "Completed",
              count: completed,
              icon: "fa-check-circle",
              color: "var(--ag-success)",
              bar: "var(--ag-success)",
              pct: Math.round((completed / totalShown) * 100),
              sub: "This page",
            },
          ].map(({ label, count, icon, color, bar, pct, sub }) => (
            <div key={label} className="ag-card ag-card-body ag-kpi-card">
              {/* Header: icon + label */}
              <div className="ag-kpi-header">
                <span
                  className="ag-kpi-icon"
                  style={{ background: `${color}18`, color }}
                >
                  <i className={`fa-solid ${icon}`} />
                </span>
                <span className="ag-kpi-label">{label}</span>
              </div>
              {/* Hero number */}
              <div className="ag-kpi-value" style={{ color }}>
                {count}
              </div>
              {/* Sub caption */}
              <div className="ag-kpi-sub" style={{ marginBottom: 10 }}>
                {sub}
              </div>
              {/* Progress */}
              <div className="ag-progress">
                <div
                  className="ag-progress-bar"
                  style={{ width: `${pct}%`, background: bar }}
                />
              </div>
            </div>
          ))}
        </div>

        {/* Table */}
        <div className="ag-card">
          {/* Tabs */}
          <div
            style={{
              display: "flex",
              borderBottom: "1px solid var(--ag-border-default)",
              padding: "0 2px",
              overflowX: "auto",
            }}
          >
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => {
                  setTab(key);
                  setPage(1);
                }}
                style={{
                  padding: "12px 16px",
                  fontSize: 13,
                  fontWeight: 600,
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  transition: "all 150ms",
                  whiteSpace: "nowrap",
                  borderBottom: `2px solid ${tab === key ? "var(--ag-brand-primary)" : "transparent"}`,
                  marginBottom: -1,
                  color:
                    tab === key
                      ? "var(--ag-text-primary)"
                      : "var(--ag-text-muted)",
                }}
              >
                {label}
              </button>
            ))}
          </div>

          {cancelError && (
            <div
              style={{
                margin: "12px 16px 0",
                padding: "10px 14px",
                background: "var(--ag-danger-subtle, rgba(239,68,68,0.1))",
                border: "1px solid var(--ag-danger, #ef4444)",
                borderRadius: "var(--ag-radius-md)",
                color: "var(--ag-danger, #ef4444)",
                fontSize: 13,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <i className="fa-solid fa-circle-exclamation" />
              {cancelError}
              <button
                style={{
                  marginLeft: "auto",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "inherit",
                  fontSize: 14,
                }}
                onClick={() => setCancelError(null)}
              >
                <i className="fa-solid fa-xmark" />
              </button>
            </div>
          )}
          <table className="ag-table">
            <thead>
              <tr>
                {[
                  "Job ID",
                  "Callback URL",
                  "Webhook Status",
                  "Status",
                  "Actions",
                ].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td
                    colSpan={5}
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
              {!loading && jobs.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    style={{
                      textAlign: "center",
                      padding: "32px 0",
                      color: "var(--ag-text-muted)",
                    }}
                  >
                    No jobs found.
                  </td>
                </tr>
              )}
              {!loading &&
                jobs.map((job) => {
                  const isExp = expandedId === job.job_id;
                  return [
                    <tr
                      key={job.job_id}
                      style={{ cursor: "pointer" }}
                      onClick={() => setExpandedId(isExp ? null : job.job_id)}
                    >
                      <td>
                        <span className="ag-mono">
                          {job.job_id.slice(0, 14).toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <span
                          className="ag-caption"
                          style={{
                            maxWidth: 160,
                            display: "block",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {job.callback_url ?? "—"}
                        </span>
                      </td>
                      <td>
                        <span className="ag-caption">
                          {job.callback_status ?? "—"}
                        </span>
                      </td>
                      <td>
                        <StatusBadge status={job.status} />
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: 5 }}>
                          {job.status !== "completed" &&
                            job.status !== "failed" &&
                            job.status !== "cancelled" && (
                              <button
                                className="ag-button ag-button--sm ag-button--danger"
                                disabled={cancellingId === job.job_id}
                                onClick={(e) => handleCancel(e, job.job_id)}
                              >
                                {cancellingId === job.job_id ? (
                                  <>
                                    <i
                                      className="fa-solid fa-spinner fa-spin"
                                      style={{ marginRight: 4 }}
                                    />
                                    Cancelling…
                                  </>
                                ) : (
                                  <i className="fa-solid fa-stop" />
                                )}
                              </button>
                            )}
                          <button
                            className="ag-button ag-button--sm"
                            title="Export JSON"
                            onClick={(e) => {
                              e.stopPropagation();
                              exportToJSON(job, `job-${job.job_id}.json`);
                            }}
                          >
                            <i className="fa-solid fa-download" />
                          </button>
                          <button
                            className="ag-button ag-button--sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigator.clipboard.writeText(job.job_id);
                            }}
                          >
                            <i className="fa-solid fa-copy" />
                          </button>
                        </div>
                      </td>
                    </tr>,
                    isExp && (
                      <tr
                        key={`${job.job_id}-exp`}
                        style={{ background: "var(--ag-bg-surface-2)" }}
                      >
                        <td colSpan={5} style={{ padding: "14px 18px" }}>
                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "repeat(4, 1fr)",
                              gap: 10,
                            }}
                          >
                            {[
                              ["Job ID", job.job_id],
                              ["Status", job.status],
                              ["Callback", job.callback_url ?? "—"],
                              ["Webhook", job.callback_status ?? "—"],
                            ].map(([k, v]) => (
                              <div
                                key={k}
                                style={{
                                  background: "var(--ag-bg-surface-1)",
                                  border: "1px solid var(--ag-border-default)",
                                  borderRadius: "var(--ag-radius-md)",
                                  padding: 10,
                                }}
                              >
                                <p
                                  className="ag-caption"
                                  style={{ margin: "0 0 3px" }}
                                >
                                  {k}
                                </p>
                                <p
                                  className="ag-mono"
                                  style={{
                                    margin: 0,
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {v}
                                </p>
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ),
                  ];
                })}
            </tbody>
          </table>

          <div
            style={{
              padding: "10px 16px",
              borderTop: "1px solid var(--ag-border-default)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span className="ag-caption">
              Showing {jobs.length} of {total}
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
    </div>
  );
}
