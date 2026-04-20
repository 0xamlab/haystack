"use client";
import { useEffect, useState } from "react";
import {
  listConnectors,
  createConnector,
  testConnector,
  deleteConnector,
  browseConnector,
  BrowseResult,
  ConnectorInfo,
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

/* ── Connector type definitions with required fields ── */
type FieldDef = {
  key: string;
  label: string;
  type?: "text" | "password" | "number" | "select" | "textarea";
  options?: string[];
  placeholder?: string;
  required?: boolean;
  hint?: string;
};

const CONNECTOR_FIELDS: Record<
  string,
  { label: string; icon: string; desc: string; fields: FieldDef[] }
> = {
  postgresql: {
    label: "PostgreSQL",
    icon: "fa-solid fa-database",
    desc: "Relational database connector",
    fields: [
      {
        key: "host",
        label: "Host",
        placeholder: "localhost or IP",
        required: true,
      },
      {
        key: "port",
        label: "Port",
        type: "number",
        placeholder: "5432",
        required: true,
      },
      {
        key: "database",
        label: "Database",
        placeholder: "my_database",
        required: true,
      },
      {
        key: "user",
        label: "Username",
        placeholder: "postgres",
        required: true,
      },
      {
        key: "password",
        label: "Password",
        type: "password",
        placeholder: "••••••••",
        required: true,
      },
      {
        key: "ssl_mode",
        label: "SSL Mode",
        type: "select",
        options: ["disable", "prefer", "require", "verify-full"],
      },
    ],
  },
  s3: {
    label: "AWS S3",
    icon: "fa-brands fa-aws",
    desc: "Amazon S3 object storage",
    fields: [
      {
        key: "bucket",
        label: "Bucket Name",
        placeholder: "my-bucket",
        required: true,
      },
      {
        key: "region",
        label: "AWS Region",
        placeholder: "us-east-1",
        required: true,
      },
      {
        key: "access_key_id",
        label: "Access Key ID",
        placeholder: "AKIAIOSFODNN7EXAMPLE",
        required: true,
      },
      {
        key: "secret_access_key",
        label: "Secret Access Key",
        type: "password",
        placeholder: "wJalrXUtnFEMI...",
        required: true,
      },
      {
        key: "endpoint_url",
        label: "Custom Endpoint",
        placeholder: "https://s3.example.com (optional for MinIO etc.)",
      },
    ],
  },
  gcs: {
    label: "Google Cloud Storage",
    icon: "fa-brands fa-google",
    desc: "GCS object storage",
    fields: [
      {
        key: "bucket",
        label: "Bucket",
        placeholder: "my-gcs-bucket",
        required: true,
      },
      {
        key: "project_id",
        label: "GCP Project ID",
        placeholder: "my-gcp-project",
        required: true,
      },
      {
        key: "service_account_json",
        label: "Service Account JSON",
        type: "textarea",
        placeholder: '{"type": "service_account", ...}',
        required: true,
        hint: "Paste your service account JSON key file contents",
      },
    ],
  },
  azure: {
    label: "Azure Blob Storage",
    icon: "fa-brands fa-microsoft",
    desc: "Microsoft Azure Blob Storage",
    fields: [
      {
        key: "account_name",
        label: "Account Name",
        placeholder: "mystorageaccount",
        required: true,
      },
      {
        key: "account_key",
        label: "Account Key",
        type: "password",
        placeholder: "base64key==",
        required: true,
      },
      {
        key: "container",
        label: "Container",
        placeholder: "my-container",
        required: true,
      },
    ],
  },
  bigquery: {
    label: "BigQuery",
    icon: "fa-solid fa-chart-simple",
    desc: "Google BigQuery data warehouse",
    fields: [
      {
        key: "project_id",
        label: "GCP Project ID",
        placeholder: "my-project",
        required: true,
      },
      {
        key: "dataset",
        label: "Dataset (optional)",
        placeholder: "my_dataset",
      },
      {
        key: "service_account_json",
        label: "Service Account JSON",
        type: "textarea",
        placeholder: '{"type": "service_account", ...}',
        required: true,
      },
    ],
  },
  snowflake: {
    label: "Snowflake",
    icon: "fa-solid fa-snowflake",
    desc: "Snowflake cloud data platform",
    fields: [
      {
        key: "account",
        label: "Account Identifier",
        placeholder: "xy12345.us-east-1",
        required: true,
        hint: "Format: <account>.<region>",
      },
      {
        key: "user",
        label: "Username",
        placeholder: "my_user",
        required: true,
      },
      {
        key: "password",
        label: "Password",
        type: "password",
        placeholder: "••••••••",
        required: true,
      },
      { key: "database", label: "Database", placeholder: "MY_DATABASE" },
      { key: "warehouse", label: "Warehouse", placeholder: "COMPUTE_WH" },
      { key: "schema", label: "Schema", placeholder: "PUBLIC" },
    ],
  },
  rest_api: {
    label: "REST API",
    icon: "fa-solid fa-code",
    desc: "Custom HTTP API endpoint",
    fields: [
      {
        key: "base_url",
        label: "Base URL",
        placeholder: "https://api.example.com",
        required: true,
      },
      {
        key: "auth_type",
        label: "Auth Type",
        type: "select",
        options: ["none", "bearer", "api_key", "basic"],
      },
      {
        key: "api_key",
        label: "API Key / Token",
        type: "password",
        placeholder: "sk-...",
      },
      {
        key: "api_key_header",
        label: "API Key Header",
        placeholder: "X-API-Key (if auth_type=api_key)",
      },
      { key: "username", label: "Username", placeholder: "For basic auth" },
      {
        key: "password",
        label: "Password",
        type: "password",
        placeholder: "For basic auth",
      },
      {
        key: "health_path",
        label: "Health Check Path",
        placeholder: "/health or /ping",
      },
    ],
  },
  file_upload: {
    label: "File Upload",
    icon: "fa-solid fa-file-arrow-up",
    desc: "Direct CSV/JSON file upload (no credentials required)",
    fields: [],
  },
};

/* Map display name → connector_type sent to API */
const TYPE_MAP: Record<string, string> = {
  postgresql: "postgresql",
  s3: "s3",
  gcs: "gcs",
  azure: "azure",
  bigquery: "bigquery",
  snowflake: "snowflake",
  rest_api: "rest_api",
  file_upload: "file_upload",
};

function StatusDot({ status }: { status: string }) {
  if (status === "live")
    return (
      <>
        <span className="ag-status-dot ag-status-dot--success" />
        <span
          style={{ color: "var(--ag-success)", fontSize: 12, fontWeight: 500 }}
        >
          Live
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
        Untested
      </span>
    </>
  );
}

interface ConnectModalProps {
  typeKey: string;
  onClose: () => void;
  onCreated: () => void;
}

function ConnectModal({ typeKey, onClose, onCreated }: ConnectModalProps) {
  const def = CONNECTOR_FIELDS[typeKey];
  const [name, setName] = useState(
    `${def.label.toLowerCase().replace(/\s+/g, "-")}-${Date.now()}`,
  );
  const [fieldVals, setFieldVals] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // File upload state
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadPreview, setUploadPreview] = useState<string | null>(null);
  const [uploadRows, setUploadRows] = useState<number>(0);
  const [fileInputEl, setFileInputEl] = useState<HTMLInputElement | null>(null);

  const isFileUpload = typeKey === "file_upload";

  function handleFileSelect(file: File) {
    setUploadedFile(file);
    setError(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      if (file.name.endsWith(".csv")) {
        const lines = text.trim().split("\n");
        setUploadRows(Math.max(0, lines.length - 1));
        setUploadPreview(lines.slice(0, 3).join("\n"));
      } else if (file.name.endsWith(".json") || file.name.endsWith(".jsonl")) {
        try {
          const parsed = JSON.parse(text);
          const rows = Array.isArray(parsed) ? parsed.length : 1;
          setUploadRows(rows);
          setUploadPreview(
            JSON.stringify(parsed, null, 2).slice(0, 200) +
              (text.length > 200 ? "…" : ""),
          );
        } catch {
          setUploadPreview(text.slice(0, 200));
          setUploadRows(0);
        }
      } else {
        const lines = text.trim().split("\n");
        setUploadRows(lines.length);
        setUploadPreview(lines.slice(0, 3).join("\n"));
      }
    };
    reader.readAsText(file);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const config: Record<string, string | number> = {};

      if (isFileUpload) {
        if (!uploadedFile) {
          setError("Please select a file to upload");
          setSaving(false);
          return;
        }
        // Store file metadata as connector config
        config["filename"] = uploadedFile.name;
        config["file_size"] = uploadedFile.size;
        config["file_type"] = uploadedFile.type || "text/plain";
        config["row_count"] = uploadRows;

        // Read file content and store as base64 in config (for small files)
        // Large files would go to MinIO via the API
        if (uploadedFile.size < 5 * 1024 * 1024) {
          // < 5MB inline
          const content = await uploadedFile.text();
          config["content"] = content.slice(0, 100000); // cap at 100KB
        }
      } else {
        for (const f of def.fields) {
          const v = fieldVals[f.key] ?? "";
          if (f.required && !v.trim()) {
            setError(`${f.label} is required`);
            setSaving(false);
            return;
          }
          if (v.trim()) config[f.key] = f.type === "number" ? parseInt(v) : v;
        }
      }

      await createConnector(
        name.trim() || def.label,
        TYPE_MAP[typeKey],
        config,
      );
      onCreated();
      onClose();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to create connector",
      );
    }
    setSaving(false);
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(7,10,18,0.82)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
      }}
    >
      <div
        style={{
          background: "var(--ag-bg-surface-1)",
          border: "1px solid var(--ag-border-default)",
          borderRadius: "var(--ag-radius-lg)",
          width: "min(520px, 92vw)",
          maxHeight: "85vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "18px 22px",
            borderBottom: "1px solid var(--ag-border-default)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <i
              className={def.icon}
              style={{ color: "var(--ag-brand-primary)", fontSize: 16 }}
            />
            <p className="ag-section-title">Connect {def.label}</p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--ag-text-muted)",
              fontSize: 16,
            }}
          >
            ✕
          </button>
        </div>
        <form
          onSubmit={handleSubmit}
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "18px 22px",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          <div>
            <label className="ag-label">
              Connection Name
            </label>
            <input
              className="ag-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ height: 36, fontSize: 13 }}
              required
            />
            <p className="ag-caption" style={{ marginTop: 3 }}>
              A unique name to identify this connection
            </p>
          </div>
          {isFileUpload ? (
            <div>
              {/* Drag-and-drop zone */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputEl?.click()}
                style={{
                  border: `2px dashed ${dragOver ? "var(--ag-brand-primary)" : uploadedFile ? "var(--ag-success)" : "var(--ag-border-default)"}`,
                  borderRadius: "var(--ag-radius-md)",
                  padding: "28px 20px",
                  textAlign: "center",
                  cursor: "pointer",
                  background: dragOver
                    ? "rgba(107,66,252,0.06)"
                    : uploadedFile
                      ? "rgba(0,211,149,0.04)"
                      : "var(--ag-bg-surface-2)",
                  transition: "all 0.15s",
                }}
              >
                <input
                  ref={(el) => setFileInputEl(el)}
                  type="file"
                  accept=".csv,.json,.jsonl,.tsv,.txt,.parquet,.xlsx"
                  style={{ display: "none" }}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleFileSelect(f);
                  }}
                />
                {uploadedFile ? (
                  <>
                    <i
                      className="fa-solid fa-circle-check"
                      style={{
                        fontSize: 28,
                        color: "var(--ag-success)",
                        display: "block",
                        marginBottom: 8,
                      }}
                    />
                    <p
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--ag-text-primary)",
                        margin: "0 0 4px",
                      }}
                    >
                      {uploadedFile.name}
                    </p>
                    <p className="ag-caption">
                      {(uploadedFile.size / 1024).toFixed(1)} KB
                      {uploadRows > 0
                        ? ` · ${uploadRows.toLocaleString()} rows`
                        : ""}
                    </p>
                    <button
                      type="button"
                      className="ag-button ag-button--sm"
                      style={{ marginTop: 8, fontSize: 11 }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setUploadedFile(null);
                        setUploadPreview(null);
                        setUploadRows(0);
                      }}
                    >
                      <i
                        className="fa-solid fa-xmark"
                        style={{ marginRight: 4 }}
                      />
                      Remove
                    </button>
                  </>
                ) : (
                  <>
                    <i
                      className="fa-solid fa-cloud-arrow-up"
                      style={{
                        fontSize: 28,
                        color: dragOver
                          ? "var(--ag-brand-primary)"
                          : "var(--ag-text-faint)",
                        display: "block",
                        marginBottom: 8,
                      }}
                    />
                    <p
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--ag-text-primary)",
                        margin: "0 0 4px",
                      }}
                    >
                      {dragOver
                        ? "Drop file here"
                        : "Drop file or click to browse"}
                    </p>
                    <p className="ag-caption">
                      CSV, JSON, JSONL, TSV, TXT, XLSX · Max 50MB
                    </p>
                  </>
                )}
              </div>

              {/* Preview */}
              {uploadPreview && (
                <div style={{ marginTop: 10 }}>
                  <p
                    className="ag-caption"
                    style={{ marginBottom: 4, fontWeight: 600 }}
                  >
                    Preview
                  </p>
                  <pre
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      color: "var(--ag-text-muted)",
                      background: "var(--ag-bg-surface-2)",
                      border: "1px solid var(--ag-border-default)",
                      borderRadius: "var(--ag-radius-sm)",
                      padding: "8px 10px",
                      overflow: "auto",
                      maxHeight: 100,
                      margin: 0,
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-all",
                    }}
                  >
                    {uploadPreview}
                  </pre>
                </div>
              )}

              {/* Supported formats */}
              <div
                style={{
                  marginTop: 10,
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 5,
                }}
              >
                {["CSV", "JSON", "JSONL", "TSV", "XLSX", "TXT"].map((fmt) => (
                  <span
                    key={fmt}
                    className="ag-badge ag-badge--muted"
                    style={{ fontSize: 10 }}
                  >
                    {fmt}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <>
              {/* no-fields placeholder for other types (should not reach here) */}
            </>
          )}
          {def.fields.map((f) => (
            <div key={f.key}>
              <label className="ag-label">
                {f.label}
                {f.required && (
                  <span style={{ color: "var(--ag-danger)", marginLeft: 3 }}>
                    *
                  </span>
                )}
              </label>
              {f.type === "textarea" ? (
                <textarea
                  className="ag-textarea"
                  rows={5}
                  placeholder={f.placeholder}
                  value={fieldVals[f.key] ?? ""}
                  onChange={(e) =>
                    setFieldVals((v) => ({ ...v, [f.key]: e.target.value }))
                  }
                  style={{
                    fontSize: 12,
                    fontFamily: "var(--font-mono)",
                    resize: "vertical",
                  }}
                />
              ) : f.type === "select" ? (
                <select
                  className="ag-select"
                  style={{ height: 36, fontSize: 13 }}
                  value={fieldVals[f.key] ?? f.options?.[0] ?? ""}
                  onChange={(e) =>
                    setFieldVals((v) => ({ ...v, [f.key]: e.target.value }))
                  }
                >
                  {f.options?.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="ag-input"
                  type={f.type ?? "text"}
                  placeholder={f.placeholder}
                  value={fieldVals[f.key] ?? ""}
                  onChange={(e) =>
                    setFieldVals((v) => ({ ...v, [f.key]: e.target.value }))
                  }
                  style={{ height: 36, fontSize: 13 }}
                  autoComplete={
                    f.type === "password" ? "new-password" : undefined
                  }
                />
              )}
              {f.hint && (
                <p className="ag-caption" style={{ marginTop: 3 }}>
                  {f.hint}
                </p>
              )}
            </div>
          ))}
          {error && (
            <div
              style={{
                padding: 10,
                background: "var(--ag-danger-soft)",
                border: "1px solid rgba(239,68,68,0.25)",
                borderRadius: "var(--ag-radius-sm)",
              }}
            >
              <p className="ag-caption" style={{ color: "var(--ag-danger)" }}>
                {error}
              </p>
            </div>
          )}
        </form>
        <div
          style={{
            padding: "14px 22px",
            borderTop: "1px solid var(--ag-border-default)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
          }}
        >
          <button className="ag-button ag-button--sm" onClick={onClose}>
            Cancel
          </button>
          <button
            className="ag-button ag-button--sm ag-button--primary"
            onClick={handleSubmit}
            disabled={saving}
          >
            {saving ? (
              <>
                <i
                  className="fa-solid fa-spinner fa-spin"
                  style={{ marginRight: 5 }}
                />
                Connecting…
              </>
            ) : (
              "Save & Connect"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

const CONNECTOR_CARDS = Object.entries(CONNECTOR_FIELDS).map(([key, def]) => ({
  key,
  ...def,
}));

export default function DataConnectorsPage() {
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [connectModal, setConnectModal] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<
    Record<string, { success: boolean; msg: string }>
  >({});
  const [browsingId, setBrowsingId] = useState<string | null>(null);
  const [browseModal, setBrowseModal] = useState<{
    connName: string;
    result: BrowseResult;
  } | null>(null);

  function load() {
    setLoading(true);
    listConnectors()
      .then(setConnectors)
      .catch(() => {})
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function handleTest(id: string) {
    setTesting(id);
    try {
      const result = await testConnector(id);
      setTestResults((r) => ({
        ...r,
        [id]: { success: result.success, msg: result.message },
      }));
      load(); // refresh status
    } catch (err: unknown) {
      setTestResults((r) => ({
        ...r,
        [id]: {
          success: false,
          msg: err instanceof Error ? err.message : "Test failed",
        },
      }));
    }
    setTesting(null);
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete connector "${name}"? This cannot be undone.`)) return;
    setDeleting(id);
    try {
      await deleteConnector(id);
      setConnectors((cs) => cs.filter((c) => c.id !== id));
    } catch {}
    setDeleting(null);
  }

  async function handleBrowse(id: string) {
    const conn = connectors.find((c) => c.id === id);
    if (!conn) return;
    setBrowsingId(id);
    try {
      const result = await browseConnector(id);
      setBrowseModal({ connName: conn.name, result });
    } catch (err: unknown) {
      alert(
        err instanceof Error
          ? err.message
          : "Browse failed — connector may not be live.",
      );
    }
    setBrowsingId(null);
  }

  const liveCount = connectors.filter((c) => c.status === "live").length;
  const connectedTypes = new Set(connectors.map((c) => c.connector_type));

  return (
    <div style={{ minHeight: "100vh", background: "var(--ag-bg-canvas)" }}>
      {connectModal && (
        <ConnectModal
          typeKey={connectModal}
          onClose={() => setConnectModal(null)}
          onCreated={load}
        />
      )}
      {browseModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(7,10,18,0.82)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
          }}
        >
          <div
            style={{
              background: "var(--ag-bg-surface-1)",
              border: "1px solid var(--ag-border-default)",
              borderRadius: "var(--ag-radius-lg)",
              width: "min(700px, 92vw)",
              maxHeight: "80vh",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              style={{
                padding: "16px 20px",
                borderBottom: "1px solid var(--ag-border-default)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <p className="ag-section-title">
                  Browse: {browseModal.connName}
                </p>
                <p className="ag-section-subtitle">
                  {browseModal.result.message}
                </p>
              </div>
              <button
                onClick={() => setBrowseModal(null)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--ag-text-muted)",
                  fontSize: 16,
                }}
              >
                ✕
              </button>
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
              {browseModal.result.items.length === 0 ? (
                <p className="ag-caption">No items found.</p>
              ) : (
                <table className="ag-table">
                  <thead>
                    <tr>
                      {Object.keys(browseModal.result.items[0]).map((k) => (
                        <th key={k}>{k}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {browseModal.result.items.map((item, i) => (
                      <tr key={i}>
                        {Object.values(item).map((v, j) => (
                          <td key={j}>
                            <span className="ag-mono" style={{ fontSize: 11 }}>
                              {String(v)}
                            </span>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div
              style={{
                padding: "12px 20px",
                borderTop: "1px solid var(--ag-border-default)",
                display: "flex",
                justifyContent: "flex-end",
                gap: 8,
              }}
            >
              <span
                className="ag-caption"
                style={{ flex: 1, alignSelf: "center" }}
              >
                {browseModal.result.total} items •{" "}
                {browseModal.result.connector_type}
              </span>
              <button
                className="ag-button ag-button--sm"
                onClick={() => setBrowseModal(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      <header style={topbar}>
        <div>
          <h1 className="ag-page-title">Data Connectors</h1>
        </div>
      </header>

      <div className="ag-content">
        {/* Metrics */}
        <div className="ag-grid-4">
          {[
            [
              "Total Connectors",
              String(connectors.length),
              "fa-plug",
              "var(--ag-brand-primary)",
            ],
            [
              "Connected",
              String(liveCount),
              "fa-circle-check",
              "var(--ag-success)",
            ],
            [
              "Connector Types",
              String(connectedTypes.size),
              "fa-layer-group",
              "#38BDF8",
            ],
            [
              "Available Types",
              String(CONNECTOR_CARDS.length),
              "fa-grid-2",
              "var(--ag-warning)",
            ],
          ].map(([label, value, icon, color]) => (
            <div key={label} className="ag-card ag-card-body ag-kpi-card">
              <div className="ag-kpi-header">
                <span
                  className="ag-kpi-icon"
                  style={{ background: `${color}18`, color }}
                >
                  <i className={`fa-solid ${icon}`} />
                </span>
                <span className="ag-kpi-label">{label}</span>
              </div>
              <div className="ag-kpi-value">{value}</div>
            </div>
          ))}
        </div>

        {/* Available connector types */}
        <div>
          <div className="ag-section-header">
            <p className="ag-section-title">Available Connectors</p>
            <p className="ag-section-subtitle">
              Click Connect to add credentials and create a real connection
            </p>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, minmax(0,1fr))",
              gap: 12,
              alignItems: "stretch",
            }}
          >
            {CONNECTOR_CARDS.map((c) => {
              const existing = connectors.filter(
                (conn) => conn.connector_type === c.key,
              );
              const hasLive = existing.some((e) => e.status === "live");
              return (
                <div
                  key={c.key}
                  className="ag-card"
                  style={{
                    cursor: "pointer",
                    transition: "border-color 150ms",
                    border: `1px solid ${hasLive ? "rgba(0,211,149,0.35)" : "var(--ag-border-default)"}`,
                    display: "flex",
                    flexDirection: "column",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.borderColor =
                      "var(--ag-brand-primary)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.borderColor = hasLive
                      ? "rgba(0,211,149,0.35)"
                      : "var(--ag-border-default)")
                  }
                >
                  <div
                    style={{
                      padding: "14px 14px 12px",
                      display: "flex",
                      flexDirection: "column",
                      flex: 1,
                    }}
                  >
                    {/* Header: icon + badge */}
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "flex-start",
                        marginBottom: 10,
                      }}
                    >
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          background: "var(--ag-bg-surface-2)",
                          border: "1px solid var(--ag-border-default)",
                          borderRadius: "var(--ag-radius-sm)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        <i
                          className={c.icon}
                          style={{
                            color: hasLive
                              ? "var(--ag-success)"
                              : "var(--ag-text-muted)",
                            fontSize: 13,
                          }}
                        />
                      </div>
                      <span
                        className={`ag-badge ${hasLive ? "ag-badge--success" : "ag-badge--muted"}`}
                        style={{ fontSize: 10 }}
                      >
                        {existing.length > 0
                          ? `${existing.length} connected`
                          : "Not Connected"}
                      </span>
                    </div>
                    {/* Name */}
                    <p
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--ag-text-primary)",
                        marginBottom: 4,
                      }}
                    >
                      {c.label}
                    </p>
                    {/* Description */}
                    <p className="ag-caption" style={{ marginBottom: 0 }}>
                      {c.desc}
                    </p>
                    {/* Spacer — pushes button to bottom */}
                    <div style={{ flex: 1 }} />
                    {/* Connect button — always at bottom */}
                    <button
                      className="ag-button ag-button--sm"
                      style={{ width: "100%", marginTop: 12 }}
                      onClick={() => setConnectModal(c.key)}
                    >
                      <i
                        className="fa-solid fa-plus"
                        style={{ marginRight: 5 }}
                      />
                      Connect
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Active connections */}
        <div className="ag-card">
          <div className="ag-card-header">
            <div>
              <p className="ag-section-title">Active Connections</p>
              <p className="ag-section-subtitle">
                {connectors.length} connector
                {connectors.length !== 1 ? "s" : ""} configured
              </p>
            </div>
            <button className="ag-button ag-button--sm" onClick={load}>
              <i className="fa-solid fa-rotate" style={{ marginRight: 5 }} />
              Refresh
            </button>
          </div>
          <table className="ag-table">
            <thead>
              <tr>
                {[
                  "Name",
                  "Type",
                  "Status",
                  "Last Tested",
                  "Test Result",
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
              {!loading && connectors.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    style={{ textAlign: "center", padding: "48px 0" }}
                  >
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <i
                        className="fa-solid fa-plug"
                        style={{
                          fontSize: 32,
                          color: "var(--ag-border-strong)",
                        }}
                      />
                      <p
                        style={{
                          fontSize: 14,
                          color: "var(--ag-text-muted)",
                          margin: 0,
                        }}
                      >
                        No connectors yet.
                      </p>
                      <p className="ag-caption">
                        Click "Connect" on any connector above to add real
                        credentials.
                      </p>
                    </div>
                  </td>
                </tr>
              )}
              {!loading &&
                connectors.map((conn) => {
                  const tr = testResults[conn.id];
                  return (
                    <tr key={conn.id}>
                      <td>
                        <span className="ag-mono">{conn.name}</span>
                      </td>
                      <td>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                          }}
                        >
                          {CONNECTOR_FIELDS[conn.connector_type]?.icon && (
                            <i
                              className={
                                CONNECTOR_FIELDS[conn.connector_type].icon
                              }
                              style={{
                                color: "var(--ag-text-muted)",
                                fontSize: 11,
                              }}
                            />
                          )}
                          <span
                            className="ag-caption"
                            style={{ textTransform: "capitalize" }}
                          >
                            {CONNECTOR_FIELDS[conn.connector_type]?.label ??
                              conn.connector_type}
                          </span>
                        </div>
                      </td>
                      <td>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                          }}
                        >
                          <StatusDot status={conn.status} />
                        </div>
                      </td>
                      <td>
                        <span className="ag-caption">
                          {conn.last_tested_at
                            ? new Date(conn.last_tested_at).toLocaleString()
                            : "Never"}
                        </span>
                      </td>
                      <td>
                        {tr ? (
                          <span
                            style={{
                              fontSize: 11,
                              color: tr.success
                                ? "var(--ag-success)"
                                : "var(--ag-danger)",
                              maxWidth: 200,
                              display: "block",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                            title={tr.msg}
                          >
                            {tr.success ? "✓ " : "✗ "}
                            {tr.msg}
                          </span>
                        ) : conn.error_message ? (
                          <span
                            style={{
                              fontSize: 11,
                              color: "var(--ag-danger)",
                              maxWidth: 200,
                              display: "block",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                            title={conn.error_message}
                          >
                            ✗ {conn.error_message}
                          </span>
                        ) : (
                          <span className="ag-caption">—</span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: 5 }}>
                          <button
                            className="ag-button ag-button--sm"
                            disabled={
                              conn.status !== "live" || browsingId === conn.id
                            }
                            onClick={() => handleBrowse(conn.id)}
                            title={
                              conn.status !== "live"
                                ? "Test connection first"
                                : "Browse schema"
                            }
                          >
                            {browsingId === conn.id ? (
                              <i className="fa-solid fa-spinner fa-spin" />
                            ) : (
                              "Browse"
                            )}
                          </button>
                          <button
                            className="ag-button ag-button--sm"
                            onClick={() => handleTest(conn.id)}
                            disabled={testing === conn.id}
                          >
                            {testing === conn.id ? (
                              <i className="fa-solid fa-spinner fa-spin" />
                            ) : (
                              "Test"
                            )}
                          </button>
                          <button
                            className="ag-button ag-button--sm ag-button--danger"
                            onClick={() => handleDelete(conn.id, conn.name)}
                            disabled={deleting === conn.id}
                          >
                            {deleting === conn.id ? (
                              <i className="fa-solid fa-spinner fa-spin" />
                            ) : (
                              <i className="fa-solid fa-trash" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
