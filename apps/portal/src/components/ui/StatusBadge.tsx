"use client";

/** Shared status badge — used across simulations, jobs, connectors pages. */
export function StatusBadge({ status }: { status: string }) {
  const cls: Record<string, string> = {
    completed: "ag-badge--success",
    active: "ag-badge--success",
    live: "ag-badge--success",
    failed: "ag-badge--danger",
    error: "ag-badge--danger",
    running: "ag-badge--info",
    queued: "ag-badge--warning",
    warning: "ag-badge--warning",
    cancelled: "ag-badge--muted",
    expired: "ag-badge--muted",
    untested: "ag-badge--muted",
  };
  const lbl: Record<string, string> = {
    completed: "Completed",
    active: "Active",
    live: "Live",
    failed: "Failed",
    error: "Error",
    running: "Running",
    queued: "Queued",
    warning: "Warning",
    cancelled: "Cancelled",
    expired: "Expired",
    untested: "Untested",
  };
  return (
    <span
      className={`ag-badge ${cls[status] ?? "ag-badge--muted"}`}
      style={{ fontSize: 11, borderRadius: "var(--ag-radius-xs)" }}
    >
      {lbl[status] ?? status}
    </span>
  );
}
