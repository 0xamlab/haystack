"use client";
import { useState } from "react";
import { simulate, exportToJSON } from "@/lib/api";
import type { RunSummary } from "@/lib/api";

interface Props {
  run: RunSummary;
  onRefresh: () => void;
}

export function SimulationExpandedRow({ run, onRefresh }: Props) {
  const [rerunning, setRerunning] = useState(false);
  const [rerunStatus, setRerunStatus] = useState<"success" | "error" | null>(
    null,
  );
  const [rerunError, setRerunError] = useState("");
  const [copied, setCopied] = useState(false);

  const handleRerun = async () => {
    setRerunning(true);
    setRerunStatus(null);
    setRerunError("");
    try {
      const payload =
        run.mode === "expert"
          ? {
              mode: "expert",
              runs: run.scenarios_run ?? 10000,
              simulation: {
                variables: [
                  {
                    name: "variable_1",
                    distribution: "normal",
                    params: { mean: 0, std: 1 },
                  },
                ],
                objective_function: "variable_1",
                scoring: { expected_value: 0.6, downside_risk: 0.4 },
              },
            }
          : {
              mode: "auto",
              runs: run.scenarios_run ?? 10000,
              scenario: {
                name: `Re-run of ${run.run_id.slice(0, 8)}`,
                variables: { metric: { low: 0, high: 1000000 } },
                objective: "maximize_net_value",
              },
            };
      await simulate(payload);
      setRerunStatus("success");
      onRefresh();
      setTimeout(() => setRerunStatus(null), 3000);
    } catch (err: unknown) {
      setRerunStatus("error");
      setRerunError(
        err instanceof Error
          ? err.message
          : "Re-run failed. Use 'Build Simulation' for exact re-runs.",
      );
    } finally {
      setRerunning(false);
    }
  };

  const handleCopyId = () => {
    navigator.clipboard.writeText(run.run_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fmtValue = (v: number | null | undefined) => {
    if (v == null) return "—";
    return v >= 1e6
      ? `$${(v / 1e6).toFixed(2)}M`
      : v >= 1000
        ? `$${(v / 1000).toFixed(0)}k`
        : `$${v.toFixed(0)}`;
  };

  return (
    <tr style={{ background: "var(--ag-bg-surface-2)" }}>
      <td colSpan={8} style={{ padding: "16px 18px" }}>
        {/* Metrics */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 10,
            marginBottom: 12,
          }}
        >
          {[
            [
              "Expected Value",
              fmtValue(run.expected_value),
              run.recommended_action ?? "—",
              run.recommended_action === "proceed"
                ? "var(--ag-success)"
                : run.recommended_action === "reject"
                  ? "var(--ag-danger)"
                  : "var(--ag-warning)",
            ],
            [
              "Probability of Loss",
              run.probability_of_loss != null
                ? `${(run.probability_of_loss * 100).toFixed(1)}%`
                : "—",
              "Monte Carlo distribution",
              "var(--ag-text-muted)",
            ],
            [
              "Confidence",
              run.confidence != null
                ? `${Math.round(run.confidence * 100)}%`
                : "—",
              `${run.scenarios_run?.toLocaleString() ?? "?"} scenarios`,
              "var(--ag-text-muted)",
            ],
          ].map(([label, value, sub, subColor]) => (
            <div
              key={label as string}
              style={{
                background: "var(--ag-bg-surface-1)",
                border: "1px solid var(--ag-border-default)",
                borderRadius: "var(--ag-radius-md)",
                padding: 12,
              }}
            >
              <p className="ag-caption" style={{ margin: "0 0 4px" }}>
                {label}
              </p>
              <p
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  letterSpacing: "-0.03em",
                  color: "var(--ag-text-primary)",
                  margin: 0,
                }}
              >
                {value}
              </p>
              <p
                style={{
                  fontSize: 11,
                  color: subColor as string,
                  margin: "3px 0 0",
                }}
              >
                {sub}
              </p>
            </div>
          ))}
        </div>

        {/* Data integrity hashes */}
        {(run.result_hash || run.request_hash) && (
          <div
            style={{
              background: "rgba(0,211,149,0.04)",
              border: "1px solid rgba(0,211,149,0.2)",
              borderRadius: "var(--ag-radius-md)",
              padding: "12px 14px",
              marginBottom: 12,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 10,
              }}
            >
              <i
                className="fa-solid fa-shield-check"
                style={{ color: "var(--ag-success)", fontSize: 13 }}
              />
              <p
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "var(--ag-success)",
                  margin: 0,
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                }}
              >
                Data Integrity — Full Chain of Custody
              </p>
            </div>
            {[
              {
                hash: run.request_hash,
                label: "Input Hash — what data was used",
                color: "var(--ag-text-faint)",
              },
              {
                hash: run.result_hash,
                label: "Output Hash — what decision was made",
                color: "var(--ag-text-secondary)",
              },
            ]
              .filter((h) => h.hash)
              .map(({ hash, label, color }) => (
                <div key={label} style={{ marginBottom: 8 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: 2,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        color: "var(--ag-text-muted)",
                        letterSpacing: "0.04em",
                        textTransform: "uppercase",
                      }}
                    >
                      {label}
                    </span>
                    <button
                      className="ag-button ag-button--sm"
                      style={{ padding: "2px 6px", fontSize: 10 }}
                      onClick={() => navigator.clipboard.writeText(hash!)}
                    >
                      <i
                        className="fa-solid fa-copy"
                        style={{ fontSize: 9, marginRight: 3 }}
                      />
                      Copy
                    </button>
                  </div>
                  <code
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      color,
                      wordBreak: "break-all",
                      lineHeight: 1.6,
                      display: "block",
                    }}
                  >
                    sha256:{hash}
                  </code>
                </div>
              ))}
            <p
              className="ag-caption"
              style={{
                marginTop: 8,
                fontSize: 10,
                color: "var(--ag-text-faint)",
              }}
            >
              Any change to input data or decision output invalidates both
              hashes — cryptographic proof of what was decided and why.
            </p>
          </div>
        )}

        {!run.result_hash && run.status === "completed" && (
          <div
            style={{
              padding: "8px 12px",
              background: "var(--ag-bg-surface-1)",
              border: "1px solid var(--ag-border-default)",
              borderRadius: "var(--ag-radius-md)",
              marginBottom: 12,
            }}
          >
            <p className="ag-caption">
              <i
                className="fa-solid fa-circle-info"
                style={{ marginRight: 6, color: "var(--ag-text-faint)" }}
              />
              Hash not available for this run (pre-migration). New simulations
              include SHA-256 data integrity hash.
            </p>
          </div>
        )}

        {run.status === "failed" && (
          <div
            style={{
              background: "var(--ag-danger-soft)",
              border: "1px solid rgba(239,68,68,0.25)",
              borderRadius: "var(--ag-radius-md)",
              padding: 12,
              marginBottom: 12,
              display: "flex",
              gap: 10,
              alignItems: "flex-start",
            }}
          >
            <i
              className="fa-solid fa-circle-exclamation"
              style={{ color: "var(--ag-danger)", fontSize: 15, marginTop: 1 }}
            />
            <div>
              <p
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--ag-danger)",
                  margin: "0 0 3px",
                }}
              >
                Execution Failed
              </p>
              <p className="ag-caption">
                An error occurred during simulation execution.
              </p>
            </div>
          </div>
        )}

        {/* JSON payload */}
        <details
          style={{
            background: "var(--ag-bg-surface-1)",
            border: "1px solid var(--ag-border-default)",
            borderRadius: "var(--ag-radius-md)",
            padding: "10px 12px",
            marginBottom: 12,
          }}
        >
          <summary
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--ag-text-muted)",
              cursor: "pointer",
            }}
          >
            JSON Payload
          </summary>
          <pre
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--ag-text-secondary)",
              marginTop: 8,
              overflow: "auto",
            }}
          >
            {JSON.stringify(
              {
                run_id: run.run_id,
                mode: run.mode,
                status: run.status,
                confidence: run.confidence,
                created_at: run.created_at,
              },
              null,
              2,
            )}
          </pre>
        </details>

        {/* Re-run status banners */}
        {rerunStatus === "success" && (
          <div
            style={{
              background: "var(--ag-success-soft)",
              border: "1px solid rgba(0,211,149,0.25)",
              borderRadius: "var(--ag-radius-md)",
              padding: "8px 12px",
              marginBottom: 10,
              fontSize: 13,
              color: "var(--ag-success)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <i className="fa-solid fa-circle-check" />
            Re-run submitted successfully.
          </div>
        )}
        {rerunStatus === "error" && (
          <div
            style={{
              background: "var(--ag-danger-soft)",
              border: "1px solid rgba(239,68,68,0.25)",
              borderRadius: "var(--ag-radius-md)",
              padding: "8px 12px",
              marginBottom: 10,
              fontSize: 13,
              color: "var(--ag-danger)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <i className="fa-solid fa-circle-exclamation" />
            {rerunError}
          </div>
        )}

        <div style={{ display: "flex", gap: 7 }}>
          <button
            className="ag-button ag-button--sm ag-button--primary"
            onClick={handleRerun}
            disabled={rerunning}
          >
            <i
              className={`fa-solid ${rerunning ? "fa-spinner fa-spin" : "fa-rotate-right"}`}
              style={{ marginRight: 5 }}
            />
            {rerunning ? "Re-running…" : "Re-run"}
          </button>
          <button
            className="ag-button ag-button--sm"
            onClick={() => exportToJSON(run, `simulation-${run.run_id}.json`)}
          >
            <i className="fa-solid fa-download" style={{ marginRight: 5 }} />
            Export
          </button>
          <button className="ag-button ag-button--sm" onClick={handleCopyId}>
            <i
              className={`fa-solid ${copied ? "fa-check" : "fa-copy"}`}
              style={{ marginRight: 5 }}
            />
            {copied ? "Copied!" : "Copy ID"}
          </button>
        </div>
      </td>
    </tr>
  );
}
