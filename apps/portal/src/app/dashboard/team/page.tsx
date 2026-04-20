"use client";
import { useEffect, useState } from "react";
import {
  listTeam,
  inviteMember,
  updateMemberRole,
  removeMember,
  getAuditLogs,
  MemberInfo,
  AuditLogEntry,
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

const ROLES = ["viewer", "member", "admin", "owner"];

const PERMISSIONS = [
  {
    label: "Run simulations",
    owner: true,
    admin: true,
    member: true,
    viewer: false,
  },
  {
    label: "View results",
    owner: true,
    admin: true,
    member: true,
    viewer: true,
  },
  {
    label: "Manage connectors",
    owner: true,
    admin: true,
    member: true,
    viewer: false,
  },
  {
    label: "Invite team members",
    owner: true,
    admin: true,
    member: false,
    viewer: false,
  },
  {
    label: "Manage infrastructure",
    owner: true,
    admin: true,
    member: false,
    viewer: false,
  },
  {
    label: "View audit logs",
    owner: true,
    admin: true,
    member: false,
    viewer: false,
  },
  {
    label: "Manage billing",
    owner: true,
    admin: false,
    member: false,
    viewer: false,
  },
  {
    label: "Delete workspace",
    owner: true,
    admin: false,
    member: false,
    viewer: false,
  },
];

function RoleBadge({ role }: { role: string }) {
  const cls: Record<string, string> = {
    owner: "ag-badge--primary",
    admin: "ag-badge--info",
    member: "ag-badge--success",
    viewer: "ag-badge--muted",
  };
  return (
    <span
      className={`ag-badge ${cls[role.toLowerCase()] ?? "ag-badge--muted"}`}
      style={{ fontSize: 11, textTransform: "capitalize" }}
    >
      {role}
    </span>
  );
}

type Tab = "members" | "audit" | "permissions";

export default function TeamPage() {
  const [tab, setTab] = useState<Tab>("members");
  const [members, setMembers] = useState<MemberInfo[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviting, setInviting] = useState(false);
  const [inviteMsg, setInviteMsg] = useState<{
    ok: boolean;
    text: string;
  } | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [auditPage, setAuditPage] = useState(1);
  const [auditTotal, setAuditTotal] = useState(0);

  function loadMembers() {
    setLoading(true);
    listTeam()
      .then(setMembers)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  function loadAudit() {
    setLoading(true);
    getAuditLogs(auditPage, 20)
      .then((r) => {
        setAuditLogs(r.entries);
        setAuditTotal(r.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadMembers();
  }, []);
  useEffect(() => {
    if (tab === "audit") loadAudit();
  }, [tab, auditPage]);

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setInviteMsg(null);
    try {
      await inviteMember(inviteEmail.trim(), inviteRole);
      setInviteMsg({ ok: true, text: `Invite sent to ${inviteEmail.trim()}` });
      setInviteEmail("");
      loadMembers();
    } catch (err: unknown) {
      setInviteMsg({
        ok: false,
        text: err instanceof Error ? err.message : "Failed to send invite",
      });
    }
    setInviting(false);
  }

  async function handleRoleChange(userId: string, newRole: string) {
    setUpdatingId(userId);
    try {
      await updateMemberRole(userId, newRole);
      loadMembers();
    } catch {}
    setUpdatingId(null);
  }

  async function handleRemove(userId: string, email: string) {
    if (!confirm(`Remove ${email} from the team?`)) return;
    setRemovingId(userId);
    try {
      await removeMember(userId);
      setMembers((ms) => ms.filter((m) => m.user_id !== userId));
    } catch {}
    setRemovingId(null);
  }

  const TABS: { key: Tab; label: string }[] = [
    { key: "members", label: "Members" },
    { key: "audit", label: "Audit Log" },
    { key: "permissions", label: "Permissions" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: "var(--ag-bg-canvas)" }}>
      <header style={topbar}>
        <div>
          <h1 className="ag-page-title">Team Management</h1>
        </div>
      </header>

      <div className="ag-content" style={{ maxWidth: 1100 }}>
        {/* Invite form */}
        <div className="ag-card">
          <div className="ag-card-header">
            <p className="ag-section-title">Invite Team Member</p>
          </div>
          <form onSubmit={handleInvite} className="ag-card-body">
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto auto",
                gap: 10,
                alignItems: "flex-end",
              }}
            >
              <div>
                <label className="ag-label">
                  Email Address
                </label>
                <input
                  className="ag-input"
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="colleague@company.com"
                  style={{ height: 36 }}
                  required
                />
              </div>
              <div>
                <label className="ag-label">
                  Role
                </label>
                <select
                  className="ag-select"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  style={{ height: 36, width: 130 }}
                >
                  {ROLES.map((r) => (
                    <option
                      key={r}
                      value={r}
                      style={{ textTransform: "capitalize" }}
                    >
                      {r}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="submit"
                disabled={inviting || !inviteEmail.trim()}
                className="ag-button ag-button--primary"
                style={{ height: 36 }}
              >
                <i
                  className="fa-solid fa-paper-plane"
                  style={{ marginRight: 6 }}
                />
                {inviting ? "Sending…" : "Send Invite"}
              </button>
            </div>
            {inviteMsg && (
              <div
                style={{
                  marginTop: 10,
                  padding: "8px 12px",
                  background: inviteMsg.ok
                    ? "var(--ag-success-soft)"
                    : "var(--ag-danger-soft)",
                  border: `1px solid ${inviteMsg.ok ? "rgba(0,211,149,0.25)" : "rgba(239,68,68,0.25)"}`,
                  borderRadius: "var(--ag-radius-md)",
                }}
              >
                <p
                  className="ag-caption"
                  style={{
                    color: inviteMsg.ok
                      ? "var(--ag-success)"
                      : "var(--ag-danger)",
                  }}
                >
                  {inviteMsg.text}
                </p>
              </div>
            )}
          </form>
        </div>

        {/* Tabs */}
        <div className="ag-card">
          <div
            style={{
              display: "flex",
              borderBottom: "1px solid var(--ag-border-default)",
              padding: "0 2px",
              overflowX: "auto",
            }}
          >
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                style={{
                  padding: "12px 16px",
                  fontSize: 13,
                  fontWeight: 600,
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  transition: "all 150ms",
                  whiteSpace: "nowrap",
                  borderBottom: `2px solid ${tab === key ? "var(--ag-brand-primary)" : "transparent"}`,
                  marginBottom: -1,
                  color:
                    tab === key
                      ? "var(--ag-text-primary)"
                      : "var(--ag-text-muted)",
                }}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Members tab */}
          {tab === "members" && (
            <table className="ag-table">
              <thead>
                <tr>
                  {["Member", "Email", "Role", "Status", "Actions"].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td
                      colSpan={5}
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
                      Loading members…
                    </td>
                  </tr>
                )}
                {!loading && members.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      style={{
                        textAlign: "center",
                        padding: "32px 0",
                        color: "var(--ag-text-muted)",
                      }}
                    >
                      No team members found.
                    </td>
                  </tr>
                )}
                {!loading &&
                  members.map((m) => (
                    <tr key={m.user_id}>
                      <td>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                          }}
                        >
                          <div
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: "50%",
                              background: "var(--ag-brand-primary)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              color: "#fff",
                              fontWeight: 700,
                              fontSize: 13,
                              flexShrink: 0,
                            }}
                          >
                            {(m.email ?? "?").charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p
                              style={{
                                fontSize: 13,
                                fontWeight: 500,
                                color: "var(--ag-text-primary)",
                                margin: 0,
                              }}
                            >
                              {m.name ?? m.email}
                            </p>
                            {m.name && (
                              <p className="ag-caption" style={{ margin: 0 }}>
                                {m.email}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className="ag-mono" style={{ fontSize: 12 }}>
                          {m.email}
                        </span>
                      </td>
                      <td>
                        <select
                          className="ag-select"
                          value={m.role}
                          onChange={(e) =>
                            handleRoleChange(m.user_id, e.target.value)
                          }
                          disabled={
                            updatingId === m.user_id || m.role === "owner"
                          }
                          style={{
                            height: 30,
                            fontSize: 12,
                            width: 100,
                            background: "var(--ag-bg-surface-2)",
                            border: "1px solid var(--ag-border-default)",
                            borderRadius: "var(--ag-radius-sm)",
                          }}
                        >
                          {ROLES.map((r) => (
                            <option
                              key={r}
                              value={r}
                              style={{ textTransform: "capitalize" }}
                            >
                              {r}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <span
                          className={`ag-badge ${m.status === "active" ? "ag-badge--success" : "ag-badge--warning"}`}
                          style={{ fontSize: 11 }}
                        >
                          {m.status ?? "active"}
                        </span>
                      </td>
                      <td>
                        {m.role !== "owner" && (
                          <button
                            className="ag-button ag-button--sm ag-button--danger"
                            disabled={removingId === m.user_id}
                            onClick={() =>
                              handleRemove(m.user_id, m.email ?? "this member")
                            }
                          >
                            {removingId === m.user_id ? (
                              <i className="fa-solid fa-spinner fa-spin" />
                            ) : (
                              <i className="fa-solid fa-user-minus" />
                            )}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}

          {/* Audit log tab */}
          {tab === "audit" && (
            <>
              <table className="ag-table">
                <thead>
                  <tr>
                    {["Time", "Actor", "Action", "Resource", "Details"].map(
                      (h) => (
                        <th key={h}>{h}</th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {loading && (
                    <tr>
                      <td
                        colSpan={5}
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
                        Loading audit log…
                      </td>
                    </tr>
                  )}
                  {!loading && auditLogs.length === 0 && (
                    <tr>
                      <td
                        colSpan={5}
                        style={{
                          textAlign: "center",
                          padding: "32px 0",
                          color: "var(--ag-text-muted)",
                        }}
                      >
                        No audit events found.
                      </td>
                    </tr>
                  )}
                  {!loading &&
                    auditLogs.map((log, i) => (
                      <tr key={i}>
                        <td>
                          <span className="ag-mono" style={{ fontSize: 11 }}>
                            {new Date(log.timestamp).toLocaleString()}
                          </span>
                        </td>
                        <td>
                          <span className="ag-caption">
                            {log.actor_email ?? "system"}
                          </span>
                        </td>
                        <td>
                          <span
                            className="ag-badge ag-badge--muted"
                            style={{ fontSize: 11 }}
                          >
                            {log.action}
                          </span>
                        </td>
                        <td>
                          <span className="ag-caption">
                            {log.resource_type}
                            {log.resource_id
                              ? ` / ${log.resource_id.slice(0, 8)}`
                              : ""}
                          </span>
                        </td>
                        <td>
                          <span
                            className="ag-caption"
                            style={{
                              maxWidth: 200,
                              display: "block",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {log.result ?? "—"}
                          </span>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
              <div
                style={{
                  padding: "10px 16px",
                  borderTop: "1px solid var(--ag-border-default)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span className="ag-caption">
                  Showing {auditLogs.length} of {auditTotal} events
                </span>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    disabled={auditPage === 1}
                    onClick={() => setAuditPage((p) => p - 1)}
                    className="ag-button ag-button--sm"
                  >
                    <i
                      className="fa-solid fa-chevron-left"
                      style={{ marginRight: 4 }}
                    />
                    Prev
                  </button>
                  <span
                    className="ag-caption"
                    style={{ lineHeight: "30px", padding: "0 8px" }}
                  >
                    Page {auditPage}
                  </span>
                  <button
                    disabled={auditPage * 20 >= auditTotal}
                    onClick={() => setAuditPage((p) => p + 1)}
                    className="ag-button ag-button--sm"
                  >
                    Next
                    <i
                      className="fa-solid fa-chevron-right"
                      style={{ marginLeft: 4 }}
                    />
                  </button>
                </div>
              </div>
            </>
          )}

          {/* Permissions tab */}
          {tab === "permissions" && (
            <div className="ag-card-body">
              <p className="ag-section-subtitle" style={{ marginBottom: 16 }}>
                Role-based access control matrix for this organization
              </p>
              <div style={{ overflowX: "auto" }}>
                <table className="ag-table">
                  <thead>
                    <tr>
                      <th>Permission</th>
                      {["Owner", "Admin", "Member", "Viewer"].map((r) => (
                        <th key={r} style={{ textAlign: "center" }}>
                          <RoleBadge role={r.toLowerCase()} />
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {PERMISSIONS.map(
                      ({ label, owner, admin, member, viewer }) => (
                        <tr key={label}>
                          <td
                            style={{
                              fontWeight: 500,
                              color: "var(--ag-text-primary)",
                            }}
                          >
                            {label}
                          </td>
                          {[owner, admin, member, viewer].map((allowed, i) => (
                            <td key={i} style={{ textAlign: "center" }}>
                              {allowed ? (
                                <i
                                  className="fa-solid fa-check"
                                  style={{
                                    color: "var(--ag-success)",
                                    fontSize: 13,
                                  }}
                                />
                              ) : (
                                <i
                                  className="fa-solid fa-xmark"
                                  style={{
                                    color: "var(--ag-border-strong)",
                                    fontSize: 13,
                                  }}
                                />
                              )}
                            </td>
                          ))}
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
