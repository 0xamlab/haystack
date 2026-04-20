"use client";

/** Horizontal progress bar with percentage label. */
export function ProgressBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div>
      <p
        style={{
          fontSize: 11,
          fontWeight: 500,
          color: "var(--ag-text-primary)",
          marginBottom: 4,
        }}
      >
        {pct}%
      </p>
      <div
        style={{
          width: 72,
          height: 4,
          background: "var(--ag-border-strong)",
          borderRadius: 2,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(pct, 100)}%`,
            height: "100%",
            background: color,
            borderRadius: 2,
            transition: "width 300ms",
          }}
        />
      </div>
    </div>
  );
}

/** CPU/memory colour helper */
export function cpuColor(pct: number): string {
  return pct >= 85
    ? "var(--ag-danger)"
    : pct >= 65
      ? "var(--ag-warning)"
      : "var(--ag-brand-primary)";
}
