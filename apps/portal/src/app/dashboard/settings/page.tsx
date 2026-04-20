"use client";
import { useEffect, useState } from "react";
import { getSession } from "@/lib/auth";
import { updateMe } from "@/lib/api";

const topbar: React.CSSProperties = {
  height: "var(--ag-topbar-height)",
  display: "flex",
  alignItems: "center",
  padding: "0 24px",
  background:
    "linear-gradient(180deg, rgba(255,255,255,0.015), rgba(255,255,255,0)), var(--ag-bg-surface-1)",
  borderBottom: "1px solid var(--ag-border-default)",
  position: "sticky",
  top: 0,
  zIndex: 40,
};

const NOTIF_DEFAULTS = {
  job_completion: true,
  error_rate: true,
  quota_warnings: true,
  security_events: false,
  product_updates: false,
};

type Tab = "profile" | "api" | "notifications" | "account" | "security";

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "profile", label: "Profile", icon: "fa-user" },
  { key: "api", label: "API Access", icon: "fa-plug" },
  { key: "notifications", label: "Notifications", icon: "fa-bell" },
  { key: "account", label: "Account", icon: "fa-building" },
  { key: "security", label: "Security", icon: "fa-shield-halved" },
];

function Toggle({ on, onChange }: { on: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      style={{
        width: 44,
        height: 24,
        borderRadius: 12,
        border: "none",
        cursor: "pointer",
        background: on ? "var(--ag-brand-primary)" : "var(--ag-border-strong)",
        position: "relative",
        flexShrink: 0,
        transition: "background 150ms",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 3,
          left: on ? 23 : 3,
          width: 18,
          height: 18,
          borderRadius: "50%",
          background: "#fff",
          transition: "left 150ms",
          boxShadow: "0 1px 3px rgba(0,0,0,0.25)",
        }}
      />
    </button>
  );
}

export default function SettingsPage() {
  const session = getSession();
  const [tab, setTab] = useState<Tab>("profile");
  const [name, setName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [saveStatus, setSaveStatus] = useState<
    "idle" | "saving" | "saved" | "error"
  >("idle");
  const [saveMsg, setSaveMsg] = useState("");
  const [notifs, setNotifs] = useState(NOTIF_DEFAULTS);
  const [copied, setCopied] = useState("");

  useEffect(() => {
    if (session) {
      setName(session.org_name ?? "");
      setOrgName(session.org_name ?? "");
    }
    try {
      const saved = localStorage.getItem("algenta_notifications");
      if (saved) setNotifs({ ...NOTIF_DEFAULTS, ...JSON.parse(saved) });
    } catch {}
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaveStatus("saving");
    try {
      await updateMe({
        name: name.trim() || undefined,
        org_name: orgName.trim() || undefined,
      });
      setSaveStatus("saved");
      setSaveMsg("Profile updated successfully.");
      setTimeout(() => setSaveStatus("idle"), 3000);
    } catch (err: unknown) {
      setSaveStatus("error");
      setSaveMsg(err instanceof Error ? err.message : "Failed to save.");
    }
  }

  function handleNotifToggle(key: keyof typeof NOTIF_DEFAULTS) {
    setNotifs((n) => {
      const updated = { ...n, [key]: !n[key] };
      try {
        localStorage.setItem("algenta_notifications", JSON.stringify(updated));
      } catch {}
      return updated;
    });
  }

  function copy(text: string, key: string) {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(""), 2000);
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  return (
    <div style={{ minHeight: "100vh", background: "var(--ag-bg-canvas)" }}>
      <header style={topbar}>
        <div>
          <h1 className="ag-page-title">Settings</h1>
        </div>
      </header>

      {/* Horizontal tab strip — same pattern as Team/Jobs pages */}
      <div
        style={{
          background: "var(--ag-bg-surface-1)",
          borderBottom: "1px solid var(--ag-border-default)",
          padding: "0 24px",
          display: "flex",
          gap: 2,
        }}
      >
        {TABS.map(({ key, label, icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
              padding: "12px 16px",
              background: "none",
              border: "none",
              borderBottom:
                tab === key
                  ? "2px solid var(--ag-brand-primary)"
                  : "2px solid transparent",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: tab === key ? 600 : 400,
              color:
                tab === key ? "var(--ag-text-primary)" : "var(--ag-text-muted)",
              transition: "color 120ms",
              marginBottom: -1,
              whiteSpace: "nowrap",
            }}
          >
            <i className={`fa-solid ${icon}`} style={{ fontSize: 11 }} />
            {label}
          </button>
        ))}
      </div>

      <div className="ag-content">
        {/* ── PROFILE ── */}
        {tab === "profile" && (
          <>
            <div className="ag-card">
              <div className="ag-card-header">
                <div>
                  <p className="ag-section-title">Identity</p>
                  <p className="ag-section-subtitle">
                    Update your display name and organization
                  </p>
                </div>
              </div>
              <form onSubmit={handleSave} className="ag-card-body">
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr 1fr",
                    gap: 16,
                    marginBottom: 16,
                  }}
                >
                  <div>
                    <label className="ag-label">Display Name</label>
                    <input
                      className="ag-input"
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Your name"
                      style={{ height: 36 }}
                    />
                  </div>
                  <div>
                    <label className="ag-label">Email Address</label>
                    <input
                      className="ag-input"
                      type="email"
                      value={session?.email ?? ""}
                      disabled
                      style={{
                        height: 36,
                        opacity: 0.5,
                        cursor: "not-allowed",
                      }}
                    />
                    <p className="ag-caption" style={{ marginTop: 3 }}>
                      Cannot be changed — contact support
                    </p>
                  </div>
                  <div>
                    <label className="ag-label">Organization Name</label>
                    <input
                      className="ag-input"
                      type="text"
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      placeholder="Your org"
                      style={{ height: 36 }}
                    />
                  </div>
                </div>
                {saveStatus !== "idle" && (
                  <div
                    style={{
                      padding: "8px 12px",
                      background:
                        saveStatus === "error"
                          ? "var(--ag-danger-soft)"
                          : saveStatus === "saved"
                            ? "var(--ag-success-soft)"
                            : "var(--ag-brand-soft)",
                      border: `1px solid ${saveStatus === "error" ? "rgba(239,68,68,0.22)" : saveStatus === "saved" ? "rgba(0,211,149,0.22)" : "rgba(107,66,252,0.22)"}`,
                      borderRadius: "var(--ag-radius-md)",
                      marginBottom: 14,
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    {saveStatus === "saving" && (
                      <i
                        className="fa-solid fa-spinner fa-spin"
                        style={{
                          color: "var(--ag-brand-primary)",
                          fontSize: 12,
                        }}
                      />
                    )}
                    {saveStatus === "saved" && (
                      <i
                        className="fa-solid fa-circle-check"
                        style={{ color: "var(--ag-success)", fontSize: 12 }}
                      />
                    )}
                    {saveStatus === "error" && (
                      <i
                        className="fa-solid fa-circle-exclamation"
                        style={{ color: "var(--ag-danger)", fontSize: 12 }}
                      />
                    )}
                    <p
                      className="ag-caption"
                      style={{
                        color:
                          saveStatus === "error"
                            ? "var(--ag-danger)"
                            : saveStatus === "saved"
                              ? "var(--ag-success)"
                              : "var(--ag-brand-primary)",
                        margin: 0,
                      }}
                    >
                      {saveStatus === "saving" ? "Saving…" : saveMsg}
                    </p>
                  </div>
                )}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "flex-end",
                    gap: 8,
                    paddingTop: 12,
                    borderTop: "1px solid var(--ag-border-subtle)",
                  }}
                >
                  <button
                    type="button"
                    className="ag-button ag-button--sm"
                    onClick={() => {
                      setName(session?.org_name ?? "");
                      setOrgName(session?.org_name ?? "");
                      setSaveStatus("idle");
                    }}
                  >
                    Reset
                  </button>
                  <button
                    type="submit"
                    className="ag-button ag-button--sm ag-button--primary"
                    disabled={saveStatus === "saving"}
                  >
                    {saveStatus === "saving" ? "Saving…" : "Save Changes"}
                  </button>
                </div>
              </form>
            </div>

            <div className="ag-card">
              <div className="ag-card-header">
                <p className="ag-section-title">Session Info</p>
              </div>
              <div className="ag-card-body">
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(4, 1fr)",
                    gap: 12,
                  }}
                >
                  {[
                    { label: "Email", value: session?.email ?? "—" },
                    { label: "Organization", value: session?.org_name ?? "—" },
                    { label: "Plan", value: "Developer" },
                    { label: "API URL", value: apiBase },
                  ].map(({ label, value }) => (
                    <div key={label} className="ag-kpi-card">
                      <p className="ag-kpi-label">{label}</p>
                      <p
                        style={{
                          fontSize: 12,
                          fontWeight: 600,
                          color: "var(--ag-text-primary)",
                          margin: 0,
                          fontFamily:
                            label === "API URL" || label === "Email"
                              ? "var(--font-mono)"
                              : "inherit",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {value}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}

        {/* ── API ACCESS ── */}
        {tab === "api" && (
          <>
            <div className="ag-card">
              <div className="ag-card-header">
                <div>
                  <p className="ag-section-title">Endpoint Configuration</p>
                  <p className="ag-section-subtitle">
                    Base URLs and endpoint reference for all API calls
                  </p>
                </div>
              </div>
              <div
                className="ag-card-body"
                style={{ display: "flex", flexDirection: "column", gap: 16 }}
              >
                <div>
                  <label className="ag-label">API Base URL</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <code
                      style={{
                        flex: 1,
                        background: "var(--ag-bg-surface-0)",
                        border: "1px solid var(--ag-border-default)",
                        borderRadius: "var(--ag-radius-md)",
                        padding: "10px 14px",
                        fontFamily: "var(--font-mono)",
                        fontSize: 13,
                        color: "var(--ag-text-secondary)",
                        display: "block",
                      }}
                    >
                      {apiBase}
                    </code>
                    <button
                      className="ag-button ag-button--sm"
                      onClick={() => copy(apiBase, "base")}
                      style={{ minWidth: 80 }}
                    >
                      <i
                        className={`fa-solid ${copied === "base" ? "fa-check" : "fa-copy"}`}
                        style={{ marginRight: 5 }}
                      />
                      {copied === "base" ? "Copied" : "Copy"}
                    </button>
                  </div>
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(2, 1fr)",
                    gap: 10,
                  }}
                >
                  {[
                    { label: "Simulate", path: "/v1/simulate" },
                    { label: "Runs History", path: "/v1/runs" },
                    { label: "Templates", path: "/v1/simulate/templates" },
                    { label: "Health", path: "/health" },
                  ].map(({ label, path }) => (
                    <div
                      key={label}
                      style={{
                        background: "var(--ag-bg-surface-2)",
                        border: "1px solid var(--ag-border-default)",
                        borderRadius: "var(--ag-radius-md)",
                        padding: "10px 12px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <div>
                        <p className="ag-caption" style={{ margin: "0 0 2px" }}>
                          {label}
                        </p>
                        <code
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: 11,
                            color: "var(--ag-text-secondary)",
                          }}
                        >
                          {apiBase}
                          {path}
                        </code>
                      </div>
                      <button
                        className="ag-button ag-button--sm"
                        style={{ padding: "4px 8px" }}
                        onClick={() => copy(apiBase + path, label)}
                      >
                        <i
                          className={`fa-solid ${copied === label ? "fa-check" : "fa-copy"}`}
                          style={{ fontSize: 10 }}
                        />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="ag-card">
              <div className="ag-card-header">
                <div>
                  <p className="ag-section-title">Authentication</p>
                  <p className="ag-section-subtitle">
                    How to authenticate API requests
                  </p>
                </div>
                <a
                  href="/dashboard/api-keys"
                  className="ag-button ag-button--sm ag-button--primary"
                  style={{ textDecoration: "none" }}
                >
                  <i className="fa-solid fa-key" style={{ marginRight: 5 }} />
                  Manage Keys
                </a>
              </div>
              <div
                className="ag-card-body"
                style={{ display: "flex", flexDirection: "column", gap: 14 }}
              >
                <div
                  style={{
                    background: "var(--ag-bg-surface-0)",
                    border: "1px solid var(--ag-border-default)",
                    borderRadius: "var(--ag-radius-md)",
                    padding: "12px 16px",
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    lineHeight: 1.8,
                  }}
                >
                  <span style={{ color: "var(--ag-text-faint)" }}>POST </span>
                  <span style={{ color: "var(--ag-brand-primary)" }}>
                    /v1/simulate
                  </span>
                  <br />
                  <span style={{ color: "var(--ag-text-faint)" }}>
                    Authorization: Bearer{" "}
                  </span>
                  <span style={{ color: "var(--ag-success)" }}>
                    {"<your-api-key>"}
                  </span>
                  <br />
                  <span style={{ color: "var(--ag-text-faint)" }}>
                    Content-Type:{" "}
                  </span>
                  <span style={{ color: "var(--ag-text-secondary)" }}>
                    application/json
                  </span>
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: 10,
                  }}
                >
                  {[
                    {
                      label: "Live Key Prefix",
                      value: "de_live_...",
                      color: "var(--ag-success)",
                      bg: "var(--ag-success-soft)",
                    },
                    {
                      label: "Test Key Prefix",
                      value: "de_test_...",
                      color: "var(--ag-warning)",
                      bg: "var(--ag-warning-soft)",
                    },
                    {
                      label: "Rate Limit",
                      value: "5,000 req/min",
                      color: "var(--ag-info)",
                      bg: "var(--ag-info-soft)",
                    },
                  ].map(({ label, value, color, bg }) => (
                    <div
                      key={label}
                      style={{
                        background: bg,
                        border: `1px solid ${color}33`,
                        borderRadius: "var(--ag-radius-md)",
                        padding: "10px 14px",
                      }}
                    >
                      <p
                        className="ag-section-kicker"
                        style={{ color, marginBottom: 4 }}
                      >
                        {label}
                      </p>
                      <code
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 12,
                          color: "var(--ag-text-secondary)",
                        }}
                      >
                        {value}
                      </code>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}

        {/* ── NOTIFICATIONS ── */}
        {tab === "notifications" && (
          <div className="ag-card">
            <div className="ag-card-header">
              <div>
                <p className="ag-section-title">Alert Preferences</p>
                <p className="ag-section-subtitle">
                  Stored locally in this browser — email delivery coming soon
                </p>
              </div>
            </div>
            <div
              className="ag-card-body"
              style={{ display: "flex", flexDirection: "column", gap: 0 }}
            >
              {(
                [
                  {
                    key: "job_completion" as const,
                    label: "Job Completion Alerts",
                    desc: "Notify when async simulation jobs finish or fail",
                    color: "var(--ag-success)",
                  },
                  {
                    key: "error_rate" as const,
                    label: "Error Rate Alerts",
                    desc: "Alert when API error rate exceeds threshold",
                    color: "var(--ag-warning)",
                  },
                  {
                    key: "quota_warnings" as const,
                    label: "Quota Warnings",
                    desc: "Warn when monthly quota reaches 80% and 100%",
                    color: "var(--ag-info)",
                  },
                  {
                    key: "security_events" as const,
                    label: "Security Events",
                    desc: "Notify on API key creation, revocation, or failed auth",
                    color: "var(--ag-danger)",
                  },
                  {
                    key: "product_updates" as const,
                    label: "Product Updates",
                    desc: "Announcements about new features and engine versions",
                    color: "var(--ag-brand-primary)",
                  },
                ] as {
                  key: keyof typeof NOTIF_DEFAULTS;
                  label: string;
                  desc: string;
                  color: string;
                }[]
              ).map(({ key, label, desc, color }, i, arr) => (
                <div
                  key={key}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 16,
                    padding: "14px 0",
                    borderBottom:
                      i < arr.length - 1
                        ? "1px solid var(--ag-border-subtle)"
                        : "none",
                  }}
                >
                  <div>
                    <p
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--ag-text-primary)",
                        margin: 0,
                      }}
                    >
                      {label}
                    </p>
                    <p className="ag-caption" style={{ margin: "2px 0 0" }}>
                      {desc}
                    </p>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      flexShrink: 0,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: notifs[key] ? color : "var(--ag-text-faint)",
                      }}
                    >
                      {notifs[key] ? "ON" : "OFF"}
                    </span>
                    <Toggle
                      on={notifs[key]}
                      onChange={() => handleNotifToggle(key)}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── ACCOUNT ── */}
        {tab === "account" && (
          <>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 14,
              }}
            >
              {[
                {
                  label: "Current Plan",
                  value: "Developer",
                  sub: "$299 / month",
                  icon: "fa-star",
                  color: "var(--ag-brand-primary)",
                },
                {
                  label: "Monthly Quota",
                  value: "50,000",
                  sub: "simulations / month",
                  icon: "fa-chart-bar",
                  color: "var(--ag-info)",
                },
                {
                  label: "Rate Limit",
                  value: "5,000 / min",
                  sub: "API requests per minute",
                  icon: "fa-bolt",
                  color: "var(--ag-success)",
                },
              ].map(({ label, value, sub, icon, color }) => (
                <div
                  key={label}
                  className="ag-card ag-card-body"
                  style={{ display: "flex", flexDirection: "column", gap: 0 }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 12,
                    }}
                  >
                    <div
                      style={{
                        width: 30,
                        height: 30,
                        borderRadius: "var(--ag-radius-sm)",
                        background: color + "18",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <i
                        className={`fa-solid ${icon}`}
                        style={{ color, fontSize: 13 }}
                      />
                    </div>
                    <p className="ag-caption" style={{ margin: 0 }}>
                      {label}
                    </p>
                  </div>
                  <p
                    style={{
                      fontSize: 26,
                      fontWeight: 700,
                      color: "var(--ag-text-primary)",
                      margin: "0 0 2px",
                      letterSpacing: "-0.03em",
                    }}
                  >
                    {value}
                  </p>
                  <p className="ag-caption">{sub}</p>
                </div>
              ))}
            </div>

            <div className="ag-card">
              <div className="ag-card-header">
                <p className="ag-section-title">Organization Details</p>
              </div>
              <div
                className="ag-card-body"
                style={{ display: "flex", flexDirection: "column", gap: 0 }}
              >
                {[
                  { key: "Email", value: session?.email ?? "—" },
                  { key: "Organization", value: session?.org_name ?? "—" },
                  { key: "Plan Tier", value: "Developer" },
                  { key: "API Base URL", value: apiBase },
                ].map(({ key, value }, i, arr) => (
                  <div
                    key={key}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "12px 0",
                      borderBottom:
                        i < arr.length - 1
                          ? "1px solid var(--ag-border-subtle)"
                          : "none",
                    }}
                  >
                    <span className="ag-caption">{key}</span>
                    {key === "Plan Tier" ? (
                      <span className="ag-badge ag-badge--primary">
                        Developer
                      </span>
                    ) : (
                      <span
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 12,
                          color: "var(--ag-text-secondary)",
                        }}
                      >
                        {value}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* ── SECURITY ── */}
        {tab === "security" && (
          <>
            <div className="ag-card">
              <div className="ag-card-header">
                <div>
                  <p className="ag-section-title">Access Controls</p>
                  <p className="ag-section-subtitle">
                    Manage API keys, authentication, and access policies
                  </p>
                </div>
                <a
                  href="/dashboard/api-keys"
                  className="ag-button ag-button--sm ag-button--primary"
                  style={{ textDecoration: "none" }}
                >
                  <i className="fa-solid fa-key" style={{ marginRight: 5 }} />
                  Manage API Keys
                </a>
              </div>
              <div
                className="ag-card-body"
                style={{ display: "flex", flexDirection: "column", gap: 0 }}
              >
                {[
                  {
                    label: "API Key Management",
                    desc: "Create, rotate, and revoke programmatic access keys",
                    action: (
                      <a
                        href="/dashboard/api-keys"
                        className="ag-button ag-button--sm"
                        style={{ textDecoration: "none" }}
                      >
                        View Keys
                      </a>
                    ),
                  },
                  {
                    label: "Two-Factor Authentication",
                    desc: "Add an extra verification step to your login",
                    action: (
                      <span className="ag-badge ag-badge--muted">
                        Coming soon
                      </span>
                    ),
                  },
                  {
                    label: "Password Change",
                    desc: "Update your account password",
                    action: (
                      <span className="ag-badge ag-badge--muted">
                        Coming soon
                      </span>
                    ),
                  },
                  {
                    label: "SAML / SSO",
                    desc: "Single sign-on integration for enterprise organizations",
                    action: (
                      <span className="ag-badge ag-badge--primary">
                        Enterprise
                      </span>
                    ),
                  },
                  {
                    label: "IP Allowlisting",
                    desc: "Restrict API access to specific IP ranges",
                    action: (
                      <span className="ag-badge ag-badge--muted">
                        Coming soon
                      </span>
                    ),
                  },
                ].map(({ label, desc, action }, i, arr) => (
                  <div
                    key={label}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 16,
                      padding: "14px 0",
                      borderBottom:
                        i < arr.length - 1
                          ? "1px solid var(--ag-border-subtle)"
                          : "none",
                    }}
                  >
                    <div>
                      <p
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: "var(--ag-text-primary)",
                          margin: 0,
                        }}
                      >
                        {label}
                      </p>
                      <p className="ag-caption" style={{ margin: "2px 0 0" }}>
                        {desc}
                      </p>
                    </div>
                    <div style={{ flexShrink: 0 }}>{action}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="ag-card">
              <div className="ag-card-header">
                <p className="ag-section-title">Security Contact</p>
              </div>
              <div className="ag-card-body">
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 12,
                    background: "var(--ag-success-soft)",
                    border: "1px solid rgba(0,211,149,0.22)",
                    borderRadius: "var(--ag-radius-md)",
                    padding: "14px 16px",
                  }}
                >
                  <i
                    className="fa-solid fa-shield-check"
                    style={{
                      color: "var(--ag-success)",
                      fontSize: 16,
                      marginTop: 2,
                      flexShrink: 0,
                    }}
                  />
                  <div>
                    <p
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--ag-text-primary)",
                        margin: "0 0 4px",
                      }}
                    >
                      Responsible Disclosure
                    </p>
                    <p className="ag-caption" style={{ lineHeight: 1.6 }}>
                      For security vulnerabilities or unauthorized access,
                      contact{" "}
                      <a
                        href="mailto:security@algenta.io"
                        style={{
                          color: "var(--ag-brand-primary)",
                          fontWeight: 600,
                        }}
                      >
                        security@algenta.io
                      </a>
                      . We respond to all security reports within 24 hours.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
