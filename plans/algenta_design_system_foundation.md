# Algenta Design System Foundation

## 1. `design-tokens.ts`

```ts
export const algentaColors = {
  bg: {
    canvas: "#0B0D12",
    surface0: "#0F1117",
    surface1: "#11131A",
    surface2: "#151823",
    surface3: "#1A1F2B",
    sidebar: "#0D1016",
    overlay: "rgba(7, 10, 18, 0.82)",
  },
  border: {
    subtle: "#1B2130",
    default: "#1F2430",
    strong: "#2A3142",
    focus: "#6B42FC",
  },
  text: {
    primary: "#E6E8EC",
    secondary: "#B0B7C6",
    muted: "#8A90A2",
    faint: "#687089",
    inverse: "#0B0D12",
  },
  brand: {
    primary: "#6B42FC",
    primaryHover: "#7C5CFF",
    primaryActive: "#5B34E8",
    primarySoft: "rgba(107, 66, 252, 0.16)",
    primaryBorder: "rgba(107, 66, 252, 0.34)",
  },
  status: {
    success: "#00D395",
    successSoft: "rgba(0, 211, 149, 0.14)",
    warning: "#F59E0B",
    warningSoft: "rgba(245, 158, 11, 0.14)",
    danger: "#EF4444",
    dangerSoft: "rgba(239, 68, 68, 0.14)",
    info: "#38BDF8",
    infoSoft: "rgba(56, 189, 248, 0.14)",
  },
  chart: {
    purple: "#6B42FC",
    purple2: "#8E6BFF",
    green: "#00D395",
    orange: "#F59E0B",
    red: "#EF4444",
    blue: "#38BDF8",
    grid: "rgba(255,255,255,0.06)",
  },
} as const;

export const algentaTypography = {
  fontFamily: {
    sans: [
      'Inter',
      'Geist',
      'ui-sans-serif',
      'system-ui',
      '-apple-system',
      'BlinkMacSystemFont',
      'Segoe UI',
      'sans-serif',
    ].join(', '),
    mono: [
      'JetBrains Mono',
      'SFMono-Regular',
      'Menlo',
      'Monaco',
      'Consolas',
      'monospace',
    ].join(', '),
  },
  fontSize: {
    xs: ['11px', { lineHeight: '16px', letterSpacing: '0.02em' }],
    sm: ['12px', { lineHeight: '18px', letterSpacing: '0.01em' }],
    base: ['14px', { lineHeight: '20px', letterSpacing: '0em' }],
    md: ['15px', { lineHeight: '22px', letterSpacing: '0em' }],
    lg: ['16px', { lineHeight: '24px', letterSpacing: '-0.01em' }],
    xl: ['18px', { lineHeight: '26px', letterSpacing: '-0.01em' }],
    '2xl': ['22px', { lineHeight: '30px', letterSpacing: '-0.02em' }],
    '3xl': ['28px', { lineHeight: '36px', letterSpacing: '-0.025em' }],
    '4xl': ['36px', { lineHeight: '42px', letterSpacing: '-0.03em' }],
  },
  fontWeight: {
    regular: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
} as const;

export const algentaRadius = {
  xs: '6px',
  sm: '8px',
  md: '10px',
  lg: '14px',
  xl: '18px',
} as const;

export const algentaSpacing = {
  0: '0px',
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  5: '20px',
  6: '24px',
  7: '28px',
  8: '32px',
  10: '40px',
  12: '48px',
  16: '64px',
} as const;

export const algentaShadows = {
  card: '0 0 0 1px rgba(255,255,255,0.03), 0 8px 24px rgba(0,0,0,0.24)',
  panel: '0 0 0 1px rgba(255,255,255,0.04), 0 12px 40px rgba(0,0,0,0.28)',
  focus: '0 0 0 1px rgba(107,66,252,0.55), 0 0 0 4px rgba(107,66,252,0.16)',
} as const;

export const algentaLayout = {
  sidebarWidth: '248px',
  topbarHeight: '60px',
  contentMaxWidth: '1600px',
  gridGap: '16px',
} as const;
```

---

## 2. `typography.ts`

```ts
export const typography = {
  pageEyebrow: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '11px',
    lineHeight: '16px',
    fontWeight: 600,
    letterSpacing: '0.12em',
    textTransform: 'uppercase' as const,
    color: '#8A90A2',
  },
  pageTitle: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '36px',
    lineHeight: '42px',
    fontWeight: 600,
    letterSpacing: '-0.03em',
    color: '#E6E8EC',
  },
  pageSubtitle: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '16px',
    lineHeight: '24px',
    fontWeight: 400,
    letterSpacing: '-0.01em',
    color: '#8A90A2',
  },
  sectionTitle: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '18px',
    lineHeight: '26px',
    fontWeight: 600,
    letterSpacing: '-0.01em',
    color: '#E6E8EC',
  },
  sectionKicker: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '12px',
    lineHeight: '18px',
    fontWeight: 600,
    letterSpacing: '0.1em',
    textTransform: 'uppercase' as const,
    color: '#8A90A2',
  },
  metricLabel: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '12px',
    lineHeight: '18px',
    fontWeight: 500,
    letterSpacing: '0.02em',
    color: '#8A90A2',
  },
  metricValueLg: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '42px',
    lineHeight: '46px',
    fontWeight: 600,
    letterSpacing: '-0.04em',
    color: '#E6E8EC',
  },
  metricValueMd: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '28px',
    lineHeight: '34px',
    fontWeight: 600,
    letterSpacing: '-0.03em',
    color: '#E6E8EC',
  },
  body: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '14px',
    lineHeight: '20px',
    fontWeight: 400,
    letterSpacing: '0em',
    color: '#B0B7C6',
  },
  bodyStrong: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '14px',
    lineHeight: '20px',
    fontWeight: 500,
    letterSpacing: '0em',
    color: '#E6E8EC',
  },
  caption: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '12px',
    lineHeight: '18px',
    fontWeight: 400,
    letterSpacing: '0.01em',
    color: '#8A90A2',
  },
  mono: {
    fontFamily: 'JetBrains Mono, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    fontSize: '12px',
    lineHeight: '18px',
    fontWeight: 500,
    letterSpacing: '0em',
    color: '#B0B7C6',
  },
  button: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '13px',
    lineHeight: '18px',
    fontWeight: 600,
    letterSpacing: '-0.01em',
    color: '#E6E8EC',
  },
  navSection: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '11px',
    lineHeight: '16px',
    fontWeight: 700,
    letterSpacing: '0.12em',
    textTransform: 'uppercase' as const,
    color: '#687089',
  },
  navItem: {
    fontFamily: 'Inter, Geist, ui-sans-serif, system-ui, sans-serif',
    fontSize: '15px',
    lineHeight: '22px',
    fontWeight: 500,
    letterSpacing: '-0.01em',
    color: '#B0B7C6',
  },
} as const;
```

---

## 3. `globals.css`

```css
:root {
  --ag-bg-canvas: #0b0d12;
  --ag-bg-surface-0: #0f1117;
  --ag-bg-surface-1: #11131a;
  --ag-bg-surface-2: #151823;
  --ag-bg-surface-3: #1a1f2b;
  --ag-bg-sidebar: #0d1016;

  --ag-border-subtle: #1b2130;
  --ag-border-default: #1f2430;
  --ag-border-strong: #2a3142;
  --ag-border-focus: #6b42fc;

  --ag-text-primary: #e6e8ec;
  --ag-text-secondary: #b0b7c6;
  --ag-text-muted: #8a90a2;
  --ag-text-faint: #687089;

  --ag-brand-primary: #6b42fc;
  --ag-brand-primary-hover: #7c5cff;
  --ag-brand-primary-active: #5b34e8;
  --ag-brand-soft: rgba(107, 66, 252, 0.16);
  --ag-brand-border: rgba(107, 66, 252, 0.34);

  --ag-success: #00d395;
  --ag-success-soft: rgba(0, 211, 149, 0.14);
  --ag-warning: #f59e0b;
  --ag-warning-soft: rgba(245, 158, 11, 0.14);
  --ag-danger: #ef4444;
  --ag-danger-soft: rgba(239, 68, 68, 0.14);
  --ag-info: #38bdf8;
  --ag-info-soft: rgba(56, 189, 248, 0.14);

  --ag-radius-xs: 6px;
  --ag-radius-sm: 8px;
  --ag-radius-md: 10px;
  --ag-radius-lg: 14px;
  --ag-radius-xl: 18px;

  --ag-shadow-card: 0 0 0 1px rgba(255, 255, 255, 0.03), 0 8px 24px rgba(0, 0, 0, 0.24);
  --ag-shadow-panel: 0 0 0 1px rgba(255, 255, 255, 0.04), 0 12px 40px rgba(0, 0, 0, 0.28);
  --ag-shadow-focus: 0 0 0 1px rgba(107, 66, 252, 0.55), 0 0 0 4px rgba(107, 66, 252, 0.16);

  --ag-sidebar-width: 248px;
  --ag-topbar-height: 60px;
  --ag-grid-gap: 16px;
  --ag-content-max: 1600px;

  --font-sans: Inter, Geist, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', 'SFMono-Regular', Menlo, Monaco, Consolas, monospace;
}

* {
  box-sizing: border-box;
}

html,
body {
  margin: 0;
  padding: 0;
  background: var(--ag-bg-canvas);
  color: var(--ag-text-primary);
  font-family: var(--font-sans);
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  min-height: 100vh;
  font-size: 14px;
  line-height: 20px;
}

a {
  color: inherit;
  text-decoration: none;
}

button,
input,
select,
textarea {
  font: inherit;
}

::selection {
  background: rgba(107, 66, 252, 0.34);
  color: var(--ag-text-primary);
}

.ag-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: var(--ag-sidebar-width) 1fr;
  background:
    radial-gradient(circle at top right, rgba(107, 66, 252, 0.08), transparent 24%),
    var(--ag-bg-canvas);
}

.ag-sidebar {
  background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0)), var(--ag-bg-sidebar);
  border-right: 1px solid var(--ag-border-default);
  padding: 20px 16px;
}

.ag-main {
  min-width: 0;
  padding: 24px;
}

.ag-content {
  max-width: var(--ag-content-max);
  margin: 0 auto;
  display: grid;
  gap: 24px;
}

.ag-page-eyebrow {
  font-size: 11px;
  line-height: 16px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ag-text-faint);
}

.ag-page-title {
  font-size: 36px;
  line-height: 42px;
  font-weight: 600;
  letter-spacing: -0.03em;
  color: var(--ag-text-primary);
}

.ag-page-subtitle {
  font-size: 16px;
  line-height: 24px;
  font-weight: 400;
  color: var(--ag-text-muted);
}

.ag-card {
  background: linear-gradient(180deg, rgba(255,255,255,0.015), rgba(255,255,255,0)), var(--ag-bg-surface-1);
  border: 1px solid var(--ag-border-default);
  border-radius: var(--ag-radius-lg);
  box-shadow: var(--ag-shadow-card);
}

.ag-panel {
  background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0)), var(--ag-bg-surface-2);
  border: 1px solid var(--ag-border-default);
  border-radius: var(--ag-radius-lg);
  box-shadow: var(--ag-shadow-panel);
}

.ag-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px 0;
}

.ag-card-body {
  padding: 16px 18px 18px;
}

.ag-section-kicker {
  font-size: 12px;
  line-height: 18px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ag-text-muted);
}

.ag-section-title {
  font-size: 18px;
  line-height: 26px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.ag-metric-label {
  font-size: 12px;
  line-height: 18px;
  font-weight: 500;
  color: var(--ag-text-muted);
}

.ag-metric-value-lg {
  font-size: 42px;
  line-height: 46px;
  font-weight: 600;
  letter-spacing: -0.04em;
}

.ag-metric-value-md {
  font-size: 28px;
  line-height: 34px;
  font-weight: 600;
  letter-spacing: -0.03em;
}

.ag-body {
  font-size: 14px;
  line-height: 20px;
  color: var(--ag-text-secondary);
}

.ag-body-strong {
  font-size: 14px;
  line-height: 20px;
  font-weight: 500;
  color: var(--ag-text-primary);
}

.ag-caption {
  font-size: 12px;
  line-height: 18px;
  color: var(--ag-text-muted);
}

.ag-mono {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 18px;
  color: var(--ag-text-secondary);
}

.ag-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid var(--ag-border-strong);
  background: rgba(255,255,255,0.03);
  font-size: 11px;
  line-height: 16px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.ag-badge--primary {
  color: #c9bcff;
  background: var(--ag-brand-soft);
  border-color: var(--ag-brand-border);
}

.ag-badge--success {
  color: var(--ag-success);
  background: var(--ag-success-soft);
  border-color: rgba(0, 211, 149, 0.22);
}

.ag-badge--warning {
  color: var(--ag-warning);
  background: var(--ag-warning-soft);
  border-color: rgba(245, 158, 11, 0.22);
}

.ag-badge--danger {
  color: var(--ag-danger);
  background: var(--ag-danger-soft);
  border-color: rgba(239, 68, 68, 0.22);
}

.ag-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 38px;
  padding: 0 14px;
  border-radius: var(--ag-radius-md);
  border: 1px solid var(--ag-border-strong);
  background: var(--ag-bg-surface-2);
  color: var(--ag-text-primary);
  font-size: 13px;
  line-height: 18px;
  font-weight: 600;
  letter-spacing: -0.01em;
  cursor: pointer;
  transition: 150ms ease;
}

.ag-button:hover {
  border-color: #384258;
  background: #181c28;
}

.ag-button:focus-visible {
  outline: none;
  box-shadow: var(--ag-shadow-focus);
}

.ag-button--primary {
  background: linear-gradient(180deg, var(--ag-brand-primary-hover), var(--ag-brand-primary));
  border-color: transparent;
  color: white;
}

.ag-button--primary:hover {
  background: linear-gradient(180deg, #8b70ff, var(--ag-brand-primary-hover));
}

.ag-input,
.ag-select,
.ag-textarea {
  width: 100%;
  border-radius: var(--ag-radius-md);
  border: 1px solid var(--ag-border-default);
  background: var(--ag-bg-surface-0);
  color: var(--ag-text-primary);
  padding: 10px 12px;
  transition: 150ms ease;
}

.ag-input::placeholder,
.ag-textarea::placeholder {
  color: var(--ag-text-faint);
}

.ag-input:focus,
.ag-select:focus,
.ag-textarea:focus {
  outline: none;
  border-color: var(--ag-brand-primary);
  box-shadow: var(--ag-shadow-focus);
}

.ag-table {
  width: 100%;
  border-collapse: collapse;
}

.ag-table th {
  text-align: left;
  font-size: 11px;
  line-height: 16px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ag-text-faint);
  padding: 12px 14px;
  border-bottom: 1px solid var(--ag-border-default);
}

.ag-table td {
  padding: 14px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  color: var(--ag-text-secondary);
}

.ag-table tbody tr:hover {
  background: rgba(255,255,255,0.02);
}

.ag-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  display: inline-block;
}

.ag-status-dot--success { background: var(--ag-success); }
.ag-status-dot--warning { background: var(--ag-warning); }
.ag-status-dot--danger { background: var(--ag-danger); }
.ag-status-dot--info { background: var(--ag-info); }
.ag-status-dot--primary { background: var(--ag-brand-primary); }

.ag-grid-2,
.ag-grid-3,
.ag-grid-4 {
  display: grid;
  gap: var(--ag-grid-gap);
}

.ag-grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.ag-grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.ag-grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }

@media (max-width: 1280px) {
  .ag-grid-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 980px) {
  .ag-shell {
    grid-template-columns: 1fr;
  }

  .ag-sidebar {
    display: none;
  }

  .ag-grid-2,
  .ag-grid-3,
  .ag-grid-4 {
    grid-template-columns: 1fr;
  }

  .ag-main {
    padding: 16px;
  }
}
```

---

## 4. Optional `tailwind.theme.ts` mapping

```ts
import type { Config } from 'tailwindcss';

export default {
  theme: {
    extend: {
      colors: {
        ag: {
          bg: {
            canvas: '#0B0D12',
            0: '#0F1117',
            1: '#11131A',
            2: '#151823',
            3: '#1A1F2B',
            sidebar: '#0D1016',
          },
          border: {
            subtle: '#1B2130',
            DEFAULT: '#1F2430',
            strong: '#2A3142',
            focus: '#6B42FC',
          },
          text: {
            primary: '#E6E8EC',
            secondary: '#B0B7C6',
            muted: '#8A90A2',
            faint: '#687089',
          },
          brand: {
            DEFAULT: '#6B42FC',
            hover: '#7C5CFF',
            active: '#5B34E8',
          },
          success: '#00D395',
          warning: '#F59E0B',
          danger: '#EF4444',
          info: '#38BDF8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Geist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      borderRadius: {
        ag: '14px',
      },
      boxShadow: {
        'ag-card': '0 0 0 1px rgba(255,255,255,0.03), 0 8px 24px rgba(0,0,0,0.24)',
        'ag-focus': '0 0 0 1px rgba(107,66,252,0.55), 0 0 0 4px rgba(107,66,252,0.16)',
      },
    },
  },
} satisfies Config;
```

---

## 5. Usage Notes

- Use **dark mode only** for the entire Algenta enterprise console.
- Keep all KPI cards compact and dense; avoid oversized empty panels.
- Prefer **Inter** for UI text and **JetBrains Mono** for IDs, hashes, JSON, logs, and code.
- Use purple only as the primary action and system accent, not everywhere.
- Use success/warning/danger strictly for status semantics.

