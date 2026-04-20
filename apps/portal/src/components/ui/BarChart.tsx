"use client";

/**
 * Lightweight SVG bar chart — replaces react-plotly.js for simple volume charts.
 * Zero dependencies, instant render, no lazy-load delay.
 *
 * Props:
 *   dates    — x-axis labels (date strings or any string)
 *   counts   — y-axis values (integers)
 *   color    — bar fill colour (default: var(--ag-brand-primary))
 *   height   — container height in px (default: 220)
 */

interface BarChartProps {
  dates: string[];
  counts: number[];
  color?: string;
  height?: number;
}

export function BarChart({
  dates,
  counts,
  color = "var(--ag-brand-primary)",
  height = 220,
}: BarChartProps) {
  if (!dates.length || !counts.length) return null;

  const PADDING = { top: 16, right: 8, bottom: 36, left: 44 };
  const W = 600; // viewBox width (scales with container via preserveAspectRatio)
  const H = height;
  const chartW = W - PADDING.left - PADDING.right;
  const chartH = H - PADDING.top - PADDING.bottom;

  const maxVal = Math.max(...counts, 1);
  // Nice round ceiling: next multiple of 10 above max
  const yMax = Math.ceil(maxVal / 10) * 10 || 10;

  const n = dates.length;
  const barW = Math.max(4, (chartW / n) * 0.65);
  const barGap = chartW / n;

  // Y-axis ticks: 4 evenly spaced
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * yMax));

  const fmtDate = (d: string) => {
    // "2024-03-15" → "Mar 15", others pass through
    const match = d.match(/\d{4}-(\d{2})-(\d{2})/);
    if (!match) return d.slice(-5);
    const months = [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "May",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
      "Dec",
    ];
    return `${months[parseInt(match[1]) - 1]} ${parseInt(match[2])}`;
  };

  const fmtCount = (v: number) =>
    v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ width: "100%", height: "100%", overflow: "visible" }}
    >
      {/* Y-axis grid lines + labels */}
      {yTicks.map((tick) => {
        const y = PADDING.top + chartH - (tick / yMax) * chartH;
        return (
          <g key={tick}>
            <line
              x1={PADDING.left}
              y1={y}
              x2={PADDING.left + chartW}
              y2={y}
              stroke="rgba(255,255,255,0.07)"
              strokeWidth={1}
            />
            <text
              x={PADDING.left - 6}
              y={y + 4}
              textAnchor="end"
              fontSize={10}
              fill="rgba(255,255,255,0.35)"
              fontFamily="Inter, ui-sans-serif"
            >
              {fmtCount(tick)}
            </text>
          </g>
        );
      })}

      {/* Bars */}
      {counts.map((count, i) => {
        const barH = (count / yMax) * chartH;
        const x = PADDING.left + i * barGap + (barGap - barW) / 2;
        const y = PADDING.top + chartH - barH;
        const label = fmtDate(dates[i] ?? "");
        const showLabel = n <= 14 || i % Math.ceil(n / 10) === 0 || i === n - 1;

        return (
          <g key={i}>
            {/* Bar */}
            <rect
              x={x}
              y={y}
              width={barW}
              height={Math.max(barH, 1)}
              fill={color}
              opacity={0.85}
              rx={2}
              style={{ transition: "height 400ms ease, y 400ms ease" }}
            >
              <title>{`${label}: ${count.toLocaleString()}`}</title>
            </rect>

            {/* X-axis label */}
            {showLabel && (
              <text
                x={x + barW / 2}
                y={PADDING.top + chartH + 18}
                textAnchor="middle"
                fontSize={9.5}
                fill="rgba(255,255,255,0.35)"
                fontFamily="Inter, ui-sans-serif"
              >
                {label}
              </text>
            )}
          </g>
        );
      })}

      {/* Y-axis line */}
      <line
        x1={PADDING.left}
        y1={PADDING.top}
        x2={PADDING.left}
        y2={PADDING.top + chartH}
        stroke="rgba(255,255,255,0.1)"
        strokeWidth={1}
      />
    </svg>
  );
}
