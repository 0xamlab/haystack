/**
 * Shared Plotly wrapper — single dynamic import used by all dashboard pages.
 *
 * WHY: Each page previously had its own `dynamic(() => import('react-plotly.js'))`
 * which made Next.js create a separate JS chunk per page. The 3MB Plotly bundle
 * was re-downloaded on every navigation. By importing from this one file, Next.js
 * deduplicates the chunk and the browser only loads Plotly once (cached).
 *
 * Usage:
 *   import { Plot, CC, DL, HOVERLABEL } from "@/components/ui/Plot"
 *   <Plot data={[...]} layout={DL} config={CC} ... />
 */
"use client";

import dynamic from "next/dynamic";
import type { PlotParams } from "react-plotly.js";

// One dynamic import — shared across all pages
export const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        color: "var(--ag-text-muted)",
        fontSize: 13,
      }}
    >
      <i className="fa-solid fa-spinner fa-spin" style={{ marginRight: 8 }} />
      Loading chart…
    </div>
  ),
});

// ── Shared chart constants ────────────────────────────────────────────────────
// Import these instead of re-declaring in each page.

const FONT = { family: "Inter, ui-sans-serif", color: "#687089", size: 11 };

/** Shared Plotly config — no toolbar, no branding */
export const CC: Partial<PlotParams["config"]> = {
  responsive: true,
  displayModeBar: false,
  displaylogo: false,
};

/** Shared dark-theme layout defaults */
export const DL: Partial<PlotParams["layout"]> = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { t: 5, r: 5, b: 28, l: 40 },
  font: FONT,
  xaxis: {
    showgrid: false,
    tickfont: FONT,
    color: "#687089",
  },
  yaxis: {
    showgrid: true,
    gridcolor: "rgba(255,255,255,0.06)",
    tickfont: FONT,
    zeroline: false,
    color: "#687089",
  },
  showlegend: false,
};

/** Shared hover label style */
export const HOVERLABEL = {
  bgcolor: "var(--ag-bg-surface-1)",
  bordercolor: "var(--ag-border-default)",
  font: { family: "Inter, ui-sans-serif", size: 12, color: "#e2e8f0" },
};
