"use client";

/** Node health badge for the infrastructure Compute Nodes table. */
export function NodeStatusBadge({ status }: { status: string }) {
  if (status === "live")
    return (
      <>
        <span className="ag-status-dot ag-status-dot--success" />
        <span
          style={{ color: "var(--ag-success)", fontSize: 12, fontWeight: 500 }}
        >
          Healthy
        </span>
      </>
    );
  if (status === "warning")
    return (
      <>
        <span className="ag-status-dot ag-status-dot--warning" />
        <span
          style={{ color: "var(--ag-warning)", fontSize: 12, fontWeight: 500 }}
        >
          Warning
        </span>
      </>
    );
  if (status === "error")
    return (
      <>
        <span className="ag-status-dot ag-status-dot--danger" />
        <span
          style={{ color: "var(--ag-danger)", fontSize: 12, fontWeight: 500 }}
        >
          Error
        </span>
      </>
    );
  return (
    <>
      <span className="ag-status-dot ag-status-dot--muted" />
      <span
        style={{ color: "var(--ag-text-muted)", fontSize: 12, fontWeight: 500 }}
      >
        Offline
      </span>
    </>
  );
}
