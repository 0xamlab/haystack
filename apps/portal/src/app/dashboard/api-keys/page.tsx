"use client";
import { useEffect, useState } from "react";
import {
  listApiKeys,
  createApiKey,
  revokeApiKey,
  exportToCSV,
  ApiKeyInfo,
  ApiKeyCreated,
} from "@/lib/api";

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

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [label, setLabel] = useState("");
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState<ApiKeyCreated | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  function load() {
    setLoading(true);
    listApiKeys()
      .then(setKeys)
      .catch(() => {})
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!label.trim()) return;
    setCreating(true);
    try {
      const k = await createApiKey(label.trim());
      setNewKey(k);
      setLabel("");
      load();
    } catch {}
    setCreating(false);
  }

  async function handleRevoke(id: string) {
    if (!confirm("Revoke this API key? This action cannot be undone.")) return;
    try {
      await revokeApiKey(id);
      load();
    } catch {}
  }

  function copy(text: string, id: string) {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--ag-bg-canvas)" }}>
      <header style={topbar}>
        <div>
          <h1 className="ag-page-title">API Keys</h1>
        </div>
        <button className="ag-button ag-button--sm">
          <i className="fa-solid fa-book" style={{ marginRight: 5 }} />
          Documentation
        </button>
      </header>

      <div className="ag-content" style={{ maxWidth: 960 }}>
        {/* New key revealed */}
        {newKey && (
          <div
            style={{
              background: "var(--ag-success-soft)",
              border: "1px solid rgba(0,211,149,0.25)",
              borderRadius: "var(--ag-radius-lg)",
              padding: 16,
              display: "flex",
              gap: 12,
            }}
          >
            <i
              className="fa-solid fa-check-circle"
              style={{
                color: "var(--ag-success)",
                fontSize: 16,
                flexShrink: 0,
                marginTop: 1,
              }}
            />
            <div style={{ flex: 1 }}>
              <p
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--ag-success)",
                  margin: "0 0 4px",
                }}
              >
                New API Key Created
              </p>
              <p className="ag-caption" style={{ marginBottom: 10 }}>
                Copy this key now — it will not be shown again.
              </p>
              <div style={{ display: "flex", gap: 8 }}>
                <code
                  style={{
                    flex: 1,
                    background: "var(--ag-bg-surface-0)",
                    border: "1px solid var(--ag-border-default)",
                    borderRadius: "var(--ag-radius-md)",
                    padding: "8px 12px",
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    color: "var(--ag-text-secondary)",
                    display: "block",
                    overflow: "auto",
                  }}
                >
                  {newKey.raw_key}
                </code>
                <button
                  className="ag-button ag-button--sm ag-button--primary"
                  onClick={() => copy(newKey.raw_key, "newKey")}
                >
                  <i
                    className={`fa-solid ${copiedId === "newKey" ? "fa-check" : "fa-copy"}`}
                    style={{ marginRight: 4 }}
                  />
                  {copiedId === "newKey" ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>
            <button
              onClick={() => setNewKey(null)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "var(--ag-text-muted)",
                padding: "2px 6px",
                borderRadius: 4,
                flexShrink: 0,
              }}
            >
              <i className="fa-solid fa-xmark" />
            </button>
          </div>
        )}

        {/* Create form */}
        <div className="ag-card">
          <div className="ag-card-header">
            <p className="ag-section-title">Create New API Key</p>
          </div>
          <form onSubmit={handleCreate} className="ag-card-body">
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: 10,
                alignItems: "flex-end",
              }}
            >
              <div>
                <label className="ag-label">Key Label</label>
                <input
                  className="ag-input"
                  type="text"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="e.g., Production Server, CI/CD Pipeline, Development Environment"
                  style={{ height: 36 }}
                />
                <p className="ag-caption" style={{ marginTop: 4 }}>
                  A descriptive name to identify this key's purpose
                </p>
              </div>
              <button
                type="submit"
                disabled={creating || !label.trim()}
                className="ag-button ag-button--primary"
                style={{ height: 36 }}
              >
                <i className="fa-solid fa-plus" style={{ marginRight: 5 }} />
                {creating ? "Creating…" : "Create API Key"}
              </button>
            </div>
          </form>
        </div>

        {/* Keys table */}
        <div className="ag-card">
          <div className="ag-card-header">
            <div>
              <p className="ag-section-title">Active API Keys</p>
              <p className="ag-section-subtitle">
                {keys.length} key{keys.length !== 1 ? "s" : ""} created
              </p>
            </div>
            <button
              className="ag-button ag-button--sm"
              onClick={() =>
                exportToCSV(
                  keys.map((k) => ({
                    id: k.id,
                    name: k.label,
                    prefix: k.key_prefix,
                    status: k.status,
                    created: k.created_at,
                    last_used: k.last_used_at ?? "",
                  })),
                  "api-keys.csv",
                )
              }
            >
              <i className="fa-solid fa-download" style={{ marginRight: 5 }} />
              Export
            </button>
          </div>
          <table className="ag-table">
            <thead>
              <tr>
                {[
                  "Name",
                  "Key",
                  "Created",
                  "Last Used",
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
                    colSpan={6}
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
              {!loading && keys.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    style={{
                      textAlign: "center",
                      padding: "32px 0",
                      color: "var(--ag-text-muted)",
                    }}
                  >
                    No API keys yet. Create one above.
                  </td>
                </tr>
              )}
              {!loading &&
                keys.map((k) => (
                  <tr key={k.id}>
                    <td>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 7,
                        }}
                      >
                        <i
                          className={`fa-solid fa-key`}
                          style={{
                            color:
                              k.status === "active"
                                ? "var(--ag-brand-primary)"
                                : "var(--ag-text-faint)",
                            fontSize: 11,
                          }}
                        />
                        <span
                          style={{
                            color: "var(--ag-text-primary)",
                            fontWeight: 500,
                          }}
                        >
                          {k.label}
                        </span>
                      </div>
                    </td>
                    <td>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 7,
                        }}
                      >
                        <span
                          className="ag-mono"
                          style={{ letterSpacing: "0.12em" }}
                        >
                          {k.key_prefix}••••••••••••
                        </span>
                        {k.status === "active" && (
                          <button
                            onClick={() => copy(k.key_prefix || k.id, k.id)}
                            title={
                              copiedId === k.id ? "Copied!" : "Copy prefix"
                            }
                            style={{
                              background: "none",
                              border: "none",
                              cursor: "pointer",
                              color:
                                copiedId === k.id
                                  ? "var(--ag-success)"
                                  : "var(--ag-text-faint)",
                              padding: "2px 4px",
                              borderRadius: 4,
                            }}
                          >
                            <i
                              className={`fa-solid ${copiedId === k.id ? "fa-check" : "fa-copy"}`}
                              style={{ fontSize: 11 }}
                            />
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="ag-mono">
                      {k.created_at
                        ? new Date(k.created_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="ag-caption">
                      {k.last_used_at
                        ? new Date(k.last_used_at).toLocaleString()
                        : "Never"}
                    </td>
                    <td>
                      <span
                        className={`ag-badge ${k.status === "active" ? "ag-badge--success" : "ag-badge--danger"}`}
                        style={{ fontSize: 11 }}
                      >
                        <span
                          className={`ag-status-dot ag-status-dot--${k.status === "active" ? "success" : "danger"}`}
                          style={{ width: 5, height: 5 }}
                        />
                        {k.status === "active" ? "Active" : "Revoked"}
                      </span>
                    </td>
                    <td>
                      <button
                        onClick={() => handleRevoke(k.id)}
                        disabled={k.status !== "active"}
                        className="ag-button ag-button--sm ag-button--danger"
                      >
                        <i className="fa-solid fa-ban" />
                      </button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
