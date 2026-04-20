"use client";
import { useEffect, useState } from "react";
import {
  listSimulationTemplates,
  getSimulationTemplate,
  simulate,
  SimulationTemplatePreview,
} from "@/lib/api";

const T = {
  page: {
    minHeight: "100vh",
    background: "var(--ag-bg-canvas)",
  } as React.CSSProperties,
  topbar: {
    height: "var(--ag-topbar-height)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 24px",
    background:
      "linear-gradient(180deg,rgba(255,255,255,0.015),rgba(255,255,255,0)),var(--ag-bg-surface-1)",
    borderBottom: "1px solid var(--ag-border-default)",
    position: "sticky" as const,
    top: 0,
    zIndex: 40,
  } as React.CSSProperties,
};

const DOMAIN_ICONS: Record<string, string> = {
  finance: "fa-chart-line",
  medical: "fa-heart-pulse",
  pharma: "fa-pills",
  manufacturing: "fa-industry",
  aerospace: "fa-rocket",
  defense: "fa-shield-halved",
  energy: "fa-bolt",
  supply_chain: "fa-truck",
  hospitality: "fa-hotel",
  construction: "fa-hard-hat",
  cybersecurity: "fa-lock",
  environmental: "fa-leaf",
  agriculture: "fa-seedling",
  general: "fa-cube",
};

const DOMAIN_COLORS: Record<string, string> = {
  finance: "#6B42FC",
  medical: "#EF4444",
  pharma: "#F59E0B",
  manufacturing: "#3B82F6",
  aerospace: "#8B5CF6",
  defense: "#64748B",
  energy: "#F59E0B",
  supply_chain: "#06B6D4",
  hospitality: "#EC4899",
  construction: "#D97706",
  cybersecurity: "#EF4444",
  environmental: "#00D395",
  agriculture: "#22C55E",
  general: "#687089",
};

function TemplateCard({
  t,
  onSelect,
}: {
  t: SimulationTemplatePreview;
  onSelect: (t: SimulationTemplatePreview) => void;
}) {
  const icon = DOMAIN_ICONS[t.domain] ?? "fa-cube";
  const color = DOMAIN_COLORS[t.domain] ?? "#6B42FC";

  return (
    <div
      className="ag-card"
      style={{
        cursor: "pointer",
        transition: "border-color 0.15s",
        display: "flex",
        flexDirection: "column",
      }}
      onClick={() => onSelect(t)}
      onMouseEnter={(e) =>
        ((e.currentTarget as HTMLDivElement).style.borderColor = color + "66")
      }
      onMouseLeave={(e) =>
        ((e.currentTarget as HTMLDivElement).style.borderColor =
          "var(--ag-border-default)")
      }
    >
      <div
        style={{
          padding: "16px 18px",
          display: "flex",
          flexDirection: "column",
          flex: 1,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            marginBottom: 10,
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: "var(--ag-radius-sm)",
              background: color + "22",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <i className={`fa-solid ${icon}`} style={{ color, fontSize: 16 }} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: "var(--ag-text-primary)",
                margin: "0 0 2px",
              }}
            >
              {t.name}
            </p>
            <p
              className="ag-caption"
              style={{ margin: 0, fontSize: 11, color }}
            >
              {t.industry}
            </p>
          </div>
        </div>
        <p
          className="ag-caption"
          style={{ margin: "0 0 10px", fontSize: 12, lineHeight: "1.5" }}
        >
          {t.description.length > 100
            ? t.description.slice(0, 100) + "…"
            : t.description}
        </p>
        <div
          style={{
            background: "var(--ag-bg-surface-0)",
            borderRadius: "var(--ag-radius-xs)",
            padding: "6px 8px",
            marginBottom: 10,
            fontSize: 11,
            color: "var(--ag-text-muted)",
            fontStyle: "italic",
            lineHeight: "1.4",
          }}
        >
          <i
            className="fa-solid fa-lightbulb"
            style={{ marginRight: 5, color: "#F59E0B" }}
          />
          {t.use_case}
        </div>
        <div style={{ flex: 1 }} />
        <div
          style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}
        >
          <span className="ag-badge ag-badge--muted" style={{ fontSize: 10 }}>
            <i className="fa-solid fa-variable" style={{ marginRight: 3 }} />
            {t.n_variables} vars
          </span>
          <span className="ag-badge ag-badge--muted" style={{ fontSize: 10 }}>
            <i className="fa-solid fa-function" style={{ marginRight: 3 }} />
            {t.output_labels.join(" | ")}
          </span>
          {t.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="ag-badge"
              style={{
                fontSize: 10,
                background: color + "18",
                color,
                border: `1px solid ${color}33`,
              }}
            >
              {tag}
            </span>
          ))}
        </div>
        <button
          className="ag-button ag-button--sm ag-button--primary"
          style={{ width: "100%" }}
          onClick={(e) => {
            e.stopPropagation();
            onSelect(t);
          }}
        >
          <i className="fa-solid fa-play" style={{ marginRight: 5 }} />
          Use This Template
        </button>
      </div>
    </div>
  );
}

function TemplateModal({
  template,
  onClose,
  onRun,
}: {
  template: SimulationTemplatePreview;
  onClose: () => void;
  onRun: (
    id: string,
    runs: number,
    varOverrides: Record<string, number>,
  ) => void;
}) {
  const icon = DOMAIN_ICONS[template.domain] ?? "fa-cube";
  const color = DOMAIN_COLORS[template.domain] ?? "#6B42FC";
  const [runs, setRuns] = useState("50000");
  // Editable variable overrides — key = variable name, val = numeric override
  const [varOverrides, setVarOverrides] = useState<Record<string, string>>(
    () => {
      const init: Record<string, string> = {};
      for (const v of template.variables_preview) {
        init[v.name] = "";
      }
      return init;
    },
  );

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.65)",
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        style={{
          background: "var(--ag-bg-surface-1)",
          border: "1px solid var(--ag-border-default)",
          borderRadius: "var(--ag-radius-lg)",
          width: 600,
          maxHeight: "88vh",
          overflowY: "auto",
          padding: 24,
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: 18,
          }}
        >
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <div
              style={{
                width: 42,
                height: 42,
                borderRadius: "var(--ag-radius-md)",
                background: color + "22",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <i
                className={`fa-solid ${icon}`}
                style={{ color, fontSize: 20 }}
              />
            </div>
            <div>
              <h2
                style={{
                  fontSize: 16,
                  fontWeight: 700,
                  margin: 0,
                  color: "var(--ag-text-primary)",
                }}
              >
                {template.name}
              </h2>
              <p className="ag-caption" style={{ margin: "2px 0 0", color }}>
                {template.industry}
              </p>
            </div>
          </div>
          <button className="ag-button ag-button--sm" onClick={onClose}>
            <i className="fa-solid fa-xmark" />
          </button>
        </div>

        <p
          style={{
            fontSize: 13,
            color: "var(--ag-text-secondary)",
            marginBottom: 14,
            lineHeight: "1.6",
          }}
        >
          {template.description}
        </p>

        <div
          style={{
            background: "var(--ag-bg-surface-0)",
            border: "1px solid var(--ag-border-default)",
            borderRadius: "var(--ag-radius-sm)",
            padding: "10px 12px",
            marginBottom: 16,
          }}
        >
          <p
            className="ag-caption"
            style={{
              margin: "0 0 4px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            Use Case
          </p>
          <p
            style={{
              fontSize: 13,
              color: "var(--ag-text-secondary)",
              margin: 0,
            }}
          >
            <i
              className="fa-solid fa-lightbulb"
              style={{ marginRight: 6, color: "#F59E0B" }}
            />
            {template.use_case}
          </p>
        </div>

        <div style={{ marginBottom: 16 }}>
          <p
            className="ag-caption"
            style={{
              margin: "0 0 8px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            Variables ({template.n_variables})
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {template.variables_preview.map((v) => (
              <div
                key={v.name}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto auto",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 10px",
                  background: "var(--ag-bg-surface-0)",
                  borderRadius: "var(--ag-radius-xs)",
                  fontSize: 12,
                }}
              >
                <div>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      color: "var(--ag-text-primary)",
                      fontWeight: 600,
                      display: "block",
                    }}
                  >
                    {v.name}
                  </span>
                  <span
                    className="ag-badge ag-badge--muted"
                    style={{ fontSize: 10, marginTop: 2 }}
                  >
                    {v.distribution}
                    {v.unit ? ` · ${v.unit}` : ""}
                  </span>
                </div>
                <input
                  type="number"
                  className="ag-input"
                  placeholder="default"
                  value={varOverrides[v.name] ?? ""}
                  onChange={(e) =>
                    setVarOverrides((prev) => ({
                      ...prev,
                      [v.name]: e.target.value,
                    }))
                  }
                  style={{
                    width: 100,
                    height: 28,
                    fontSize: 11,
                    textAlign: "right",
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <p
            className="ag-caption"
            style={{
              margin: "0 0 6px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            Objective Function
          </p>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--ag-success)",
              background: "rgba(0,211,149,0.06)",
              border: "1px solid rgba(0,211,149,0.2)",
              borderRadius: "var(--ag-radius-sm)",
              padding: "8px 10px",
              wordBreak: "break-all",
              lineHeight: "1.6",
            }}
          >
            {template.objective_function}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            gap: 10,
            alignItems: "center",
            marginBottom: 16,
          }}
        >
          <div style={{ flex: 1 }}>
            <label className="ag-label">Scenarios</label>
            <select
              className="ag-input"
              value={runs}
              onChange={(e) => setRuns(e.target.value)}
              style={{ width: "100%", height: 34 }}
            >
              {["10000", "50000", "100000", "500000", "1000000"].map((r) => (
                <option key={r} value={r}>
                  {parseInt(r).toLocaleString()} scenarios
                </option>
              ))}
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <p className="ag-caption" style={{ margin: "0 0 4px" }}>
              Outputs
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {template.output_labels.map((l, i) => (
                <span
                  key={i}
                  className="ag-badge ag-badge--primary"
                  style={{ fontSize: 11 }}
                >
                  {l} ({template.output_units[i] ?? ""})
                </span>
              ))}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="ag-button ag-button--sm" onClick={onClose}>
            Cancel
          </button>
          <button
            className="ag-button ag-button--sm ag-button--primary"
            onClick={() => {
              const overrides: Record<string, number> = {};
              for (const [k, v] of Object.entries(varOverrides)) {
                if (v !== "") overrides[k] = parseFloat(v);
              }
              onRun(template.id, parseInt(runs), overrides);
            }}
          >
            <i className="fa-solid fa-rocket" style={{ marginRight: 5 }} />
            Run Template ({parseInt(runs).toLocaleString()} scenarios)
          </button>
        </div>
      </div>
    </div>
  );
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<SimulationTemplatePreview[]>([]);
  const [domains, setDomains] = useState<string[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [domainFilter, setDomainFilter] = useState("all");
  const [tagFilter, setTagFilter] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<SimulationTemplatePreview | null>(
    null,
  );
  const [running, setRunning] = useState(false);
  const [runStatus, setRunStatus] = useState<"success" | "error" | null>(null);
  const [runError, setRunError] = useState("");

  useEffect(() => {
    setLoading(true);
    listSimulationTemplates()
      .then((r) => {
        setTemplates(r.templates);
        setDomains(r.domains);
        setTags(r.tags);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = templates.filter((t) => {
    const matchDomain = domainFilter === "all" || t.domain === domainFilter;
    const matchTag = !tagFilter || t.tags.includes(tagFilter);
    const matchSearch =
      !search ||
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase()) ||
      t.industry.toLowerCase().includes(search.toLowerCase());
    return matchDomain && matchTag && matchSearch;
  });

  async function handleRun(
    templateId: string,
    runs: number,
    varOverrides: Record<string, number>,
  ) {
    setRunning(true);
    setRunStatus(null);
    setRunError("");
    try {
      const detail = await getSimulationTemplate(templateId, runs);
      // Apply variable overrides to the payload
      const payload = detail.payload as Record<string, unknown>;
      const sim = payload.simulation as Record<string, unknown> | undefined;
      if (sim && varOverrides && Object.keys(varOverrides).length > 0) {
        const vars = (sim.variables as Array<Record<string, unknown>>) ?? [];
        sim.variables = vars.map((v) => {
          const name = v.name as string;
          if (varOverrides[name] !== undefined) {
            const params = v.params as Record<string, number>;
            // Find the primary param key and override it
            const key = Object.keys(params).find((k) =>
              ["mean", "mode", "value", "mu", "lambda", "low"].includes(k),
            );
            if (key) {
              return { ...v, params: { ...params, [key]: varOverrides[name] } };
            }
          }
          return v;
        });
      }
      await simulate(payload as Parameters<typeof simulate>[0]);
      setRunStatus("success");
      setSelected(null);
      setTimeout(() => setRunStatus(null), 4000);
    } catch (err: unknown) {
      setRunStatus("error");
      setRunError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div style={T.page}>
      <header style={T.topbar}>
        <div>
          <h1 className="ag-page-title">Domain Templates</h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}></div>
      </header>

      <div className="ag-content">
        {runStatus === "success" && (
          <div
            style={{
              background: "var(--ag-success-soft)",
              border: "1px solid rgba(0,211,149,0.25)",
              borderRadius: "var(--ag-radius-md)",
              padding: "10px 14px",
              marginBottom: 16,
              fontSize: 13,
              color: "var(--ag-success)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <i className="fa-solid fa-circle-check" />
            Simulation submitted! View results in{" "}
            <a
              href="/dashboard/simulations"
              style={{
                color: "var(--ag-success)",
                textDecoration: "underline",
              }}
            >
              Simulation Runs
            </a>
            .
          </div>
        )}
        {runStatus === "error" && (
          <div
            style={{
              background: "var(--ag-danger-soft)",
              border: "1px solid rgba(239,68,68,0.2)",
              borderRadius: "var(--ag-radius-md)",
              padding: "10px 14px",
              marginBottom: 16,
              fontSize: 13,
              color: "var(--ag-danger)",
            }}
          >
            <i
              className="fa-solid fa-circle-exclamation"
              style={{ marginRight: 6 }}
            />
            {runError}
          </div>
        )}

        {/* Filters */}
        <div className="ag-card ag-card-body" style={{ marginBottom: 12 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 200px 200px",
              gap: 12,
            }}
          >
            <div>
              <label className="ag-label">Search</label>
              <div style={{ position: "relative" }}>
                <i
                  className="fa-solid fa-search"
                  style={{
                    position: "absolute",
                    left: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    color: "var(--ag-text-faint)",
                    fontSize: 11,
                  }}
                />
                <input
                  className="ag-input"
                  style={{ paddingLeft: 30, height: 34 }}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search templates, industries…"
                />
              </div>
            </div>
            <div>
              <label className="ag-label">Domain</label>
              <select
                className="ag-input"
                value={domainFilter}
                onChange={(e) => setDomainFilter(e.target.value)}
                style={{ width: "100%", height: 34 }}
              >
                <option value="all">All Domains</option>
                {domains.map((d) => (
                  <option key={d} value={d}>
                    {d.charAt(0).toUpperCase() + d.slice(1).replace("_", " ")}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="ag-label">Tag</label>
              <select
                className="ag-input"
                value={tagFilter}
                onChange={(e) => setTagFilter(e.target.value)}
                style={{ width: "100%", height: 34 }}
              >
                <option value="">All Tags</option>
                {tags.map((tag) => (
                  <option key={tag} value={tag}>
                    {tag}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {loading ? (
            <div
              style={{
                textAlign: "center",
                padding: "48px 0",
                color: "var(--ag-text-muted)",
              }}
            >
              <i
                className="fa-solid fa-spinner fa-spin"
                style={{ fontSize: 24, display: "block", marginBottom: 12 }}
              />
              Loading templates…
            </div>
          ) : filtered.length === 0 ? (
            <div
              style={{
                textAlign: "center",
                padding: "48px 0",
                color: "var(--ag-text-muted)",
              }}
            >
              <i
                className="fa-solid fa-magnifying-glass"
                style={{ fontSize: 24, display: "block", marginBottom: 12 }}
              />
              No templates found for this filter.
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                gap: 14,
              }}
            >
              {filtered.map((t) => (
                <TemplateCard key={t.id} t={t} onSelect={setSelected} />
              ))}
            </div>
          )}
        </div>

        {/* Universal capabilities callout */}
        <div
          className="ag-card"
          style={{
            marginTop: 24,
            background:
              "linear-gradient(135deg, rgba(107,66,252,0.08), rgba(0,211,149,0.06))",
            border: "1px solid rgba(107,66,252,0.2)",
          }}
        >
          <div style={{ padding: "20px 24px" }}>
            <h3
              style={{
                fontSize: 14,
                fontWeight: 700,
                margin: "0 0 8px",
                color: "var(--ag-text-primary)",
              }}
            >
              <i
                className="fa-solid fa-infinity"
                style={{ marginRight: 8, color: "var(--ag-brand-primary)" }}
              />
              No Domain Restrictions — Simulate Anything
            </h3>
            <p
              style={{
                fontSize: 13,
                color: "var(--ag-text-secondary)",
                margin: "0 0 12px",
                lineHeight: "1.6",
              }}
            >
              The Algenta simulation engine supports any data type, any
              variable, any industry. Don't see your domain? Use the Expert mode
              with custom variables and objective functions. All 27
              distributions and every math function are available.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {[
                [
                  "fa-circle-nodes",
                  "27 Distributions",
                  "Normal, Weibull, PERT, Student-t, Cauchy, Gumbel + more",
                ],
                [
                  "fa-function",
                  "Full Math Library",
                  "ln, exp, sqrt, if/else, clip, min, max, pow, floor, ceil",
                ],
                [
                  "fa-arrows-cross",
                  "Cholesky Correlation",
                  "Correlated Normal variables via Cholesky decomposition",
                ],
                [
                  "fa-list-ol",
                  "Multi-Output",
                  "Simulate multiple objectives with | separator",
                ],
                [
                  "fa-bolt",
                  "High Performance Engine",
                  "Optimized simulation engine with sub-second execution",
                ],
              ].map(([icon, title, desc]) => (
                <div
                  key={title}
                  style={{
                    flex: "1 1 200px",
                    background: "var(--ag-bg-surface-1)",
                    border: "1px solid var(--ag-border-default)",
                    borderRadius: "var(--ag-radius-md)",
                    padding: "10px 12px",
                  }}
                >
                  <p
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      margin: "0 0 3px",
                      color: "var(--ag-brand-primary)",
                    }}
                  >
                    <i
                      className={`fa-solid ${icon}`}
                      style={{ marginRight: 5 }}
                    />
                    {title}
                  </p>
                  <p className="ag-caption" style={{ margin: 0, fontSize: 11 }}>
                    {desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {selected && (
        <TemplateModal
          template={selected}
          onClose={() => setSelected(null)}
          onRun={handleRun}
        />
      )}

      {running && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            zIndex: 200,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              background: "var(--ag-bg-surface-1)",
              border: "1px solid var(--ag-border-default)",
              borderRadius: "var(--ag-radius-lg)",
              padding: "32px 48px",
              textAlign: "center",
            }}
          >
            <i
              className="fa-solid fa-rocket fa-spin"
              style={{
                fontSize: 32,
                color: "var(--ag-brand-primary)",
                display: "block",
                marginBottom: 12,
              }}
            />
            <p
              style={{
                fontSize: 14,
                fontWeight: 600,
                margin: 0,
                color: "var(--ag-text-primary)",
              }}
            >
              Running simulation in Mojo…
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
