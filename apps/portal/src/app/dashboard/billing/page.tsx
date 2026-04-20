"use client";
import { useEffect, useState } from "react";
import {
  getUsage,
  getLimits,
  getBillingInfo,
  createCheckoutSession,
  createBillingPortalSession,
  exportToCSV,
  UsageResponse,
  LimitsResponse,
  PlanInfo,
} from "@/lib/api";

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

const PLANS = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    period: "forever",
    sims: "1,000",
    conc: "5",
    rate: "100/min",
    features: [
      "1,000 simulations/month",
      "5 concurrent runs",
      "100 req/min",
      "Community support",
      "REST API access",
    ],
  },
  {
    id: "developer",
    name: "Developer",
    price: "$299",
    period: "per month",
    sims: "50,000",
    conc: "100",
    rate: "5,000/min",
    features: [
      "50,000 simulations/month",
      "100 concurrent runs",
      "5,000 req/min",
      "Email support",
      "Webhooks & async jobs",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "Custom",
    period: "contact sales",
    sims: "Unlimited",
    conc: "Unlimited",
    rate: "Custom",
    features: [
      "Unlimited simulations",
      "Unlimited concurrent runs",
      "Custom rate limits",
      "Dedicated support",
      "SLA guarantee",
      "SSO & RBAC",
    ],
  },
];

export default function BillingPage() {
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [limits, setLimits] = useState<LimitsResponse | null>(null);
  const [billingInfo, setBillingInfo] = useState<PlanInfo | null>(null);
  const [upgrading, setUpgrading] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getUsage(), getLimits(), getBillingInfo().catch(() => null)])
      .then(([u, l, b]) => {
        setUsage(u);
        setLimits(l);
        if (b) setBillingInfo(b);
      })
      .catch(() => {});
  }, []);

  async function handleUpgrade(planId: string) {
    if (planId === "enterprise") {
      window.location.href =
        "mailto:sales@algenta.io?subject=Enterprise Inquiry";
      return;
    }
    setUpgrading(planId);
    try {
      const s = await createCheckoutSession(planId);
      window.location.href = s.url;
    } catch {}
    setUpgrading(null);
  }

  async function handleManage() {
    try {
      const p = await createBillingPortalSession();
      window.location.href = p.url;
    } catch {}
  }

  const INVOICES = [
    {
      date: "Mar 1, 2024",
      desc: "Developer Plan — Monthly",
      amount: "$299.00",
    },
    {
      date: "Feb 1, 2024",
      desc: "Developer Plan — Monthly",
      amount: "$299.00",
    },
    {
      date: "Jan 1, 2024",
      desc: "Developer Plan — Monthly",
      amount: "$299.00",
    },
  ];

  const currentPlan = limits?.plan ?? billingInfo?.plan ?? "free";
  const quotaUsed = usage?.simulations_run ?? 0;
  const quotaLimit = usage?.quota_limit ?? 1000;
  const usedPct = usage?.quota_used_pct ?? 0;
  const nextBillingDate = billingInfo?.current_period_end
    ? new Date(billingInfo.current_period_end).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;
  const planPrice =
    currentPlan === "developer"
      ? "$299"
      : currentPlan === "enterprise"
        ? "Custom"
        : "$0";
  const planPeriod =
    currentPlan === "enterprise"
      ? ""
      : currentPlan === "free"
        ? "forever"
        : "per month";

  return (
    <div style={{ minHeight: "100vh", background: "var(--ag-bg-canvas)" }}>
      <header style={topbar}>
        <div>
          <h1 className="ag-page-title">Billing & Subscription</h1>
        </div>
      </header>

      <div className="ag-content" style={{ maxWidth: 1100 }}>
        {/* Current plan */}
        <div className="ag-card">
          <div className="ag-card-header">
            <p className="ag-section-title">Current Plan</p>
          </div>
          <div className="ag-card-body">
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <div>
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ marginBottom: 10 }}>
                      <span className="ag-badge ag-badge--primary">
                        {currentPlan} Plan
                      </span>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "baseline",
                        gap: 6,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 32,
                          fontWeight: 700,
                          letterSpacing: "-0.04em",
                          color: "var(--ag-text-primary)",
                        }}
                      >
                        {planPrice}
                      </span>
                      {planPeriod && (
                        <span className="ag-caption">{planPeriod}</span>
                      )}
                    </div>
                    {nextBillingDate && (
                      <p className="ag-caption" style={{ marginTop: 3 }}>
                        Billed monthly · Next billing date: {nextBillingDate}
                      </p>
                    )}
                  </div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(3, 1fr)",
                      gap: 8,
                    }}
                  >
                    {[
                      ["Simulations/Month", quotaLimit.toLocaleString()],
                      [
                        "Concurrent Runs",
                        String(limits?.max_runs_per_simulation ?? 5),
                      ],
                      [
                        "Rate Limit",
                        `${limits?.rate_limit_per_minute ?? 100}/min`,
                      ],
                    ].map(([k, v]) => (
                      <div
                        key={k}
                        style={{
                          background: "var(--ag-bg-surface-2)",
                          border: "1px solid var(--ag-border-default)",
                          borderRadius: "var(--ag-radius-md)",
                          padding: 10,
                        }}
                      >
                        <p className="ag-caption" style={{ marginBottom: 3 }}>
                          {k}
                        </p>
                        <p
                          style={{
                            fontSize: 15,
                            fontWeight: 600,
                            color: "var(--ag-text-primary)",
                            margin: 0,
                          }}
                        >
                          {v}
                        </p>
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: 4,
                      }}
                    >
                      <span className="ag-caption">Usage this period</span>
                      <span className="ag-caption">
                        {quotaUsed.toLocaleString()} /{" "}
                        {quotaLimit.toLocaleString()}
                      </span>
                    </div>
                    <div className="ag-progress">
                      <div
                        className="ag-progress-bar"
                        style={{ width: `${Math.min(usedPct, 100)}%` }}
                      />
                    </div>
                    <p className="ag-caption" style={{ marginTop: 4 }}>
                      {usedPct.toFixed(1)}% used
                    </p>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      gap: 8,
                      marginTop: 16,
                      flexWrap: "wrap",
                    }}
                  >
                    <button
                      className="ag-button ag-button--primary"
                      onClick={handleManage}
                    >
                      <i
                        className="fa-solid fa-arrow-up"
                        style={{ marginRight: 6 }}
                      />
                      Upgrade Plan
                    </button>
                    <button className="ag-button" onClick={handleManage}>
                      <i
                        className="fa-solid fa-external-link"
                        style={{ marginRight: 6 }}
                      />
                      Manage Billing
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Available plans */}
        <div>
          <div className="ag-section-header">
            <p className="ag-section-title">Available Plans</p>
            <p className="ag-section-subtitle">
              Choose the plan that best fits your simulation needs
            </p>
          </div>
          <div className="ag-grid-3">
            {PLANS.map((plan) => {
              const isCurrent = currentPlan === plan.id;
              return (
                <div
                  key={plan.id}
                  className="ag-card"
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    ...(isCurrent
                      ? { border: "1px solid var(--ag-brand-border)" }
                      : {}),
                  }}
                >
                  <div
                    className="ag-card-header"
                    style={{
                      borderBottom: "1px solid var(--ag-border-default)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "flex-start",
                        width: "100%",
                        gap: 8,
                      }}
                    >
                      <div>
                        <p className="ag-section-title">{plan.name}</p>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "baseline",
                            gap: 4,
                            marginTop: 4,
                          }}
                        >
                          <span
                            style={{
                              fontSize: 22,
                              fontWeight: 700,
                              letterSpacing: "-0.03em",
                              color: "var(--ag-text-primary)",
                            }}
                          >
                            {plan.price}
                          </span>
                          <span className="ag-caption">{plan.period}</span>
                        </div>
                      </div>
                      {isCurrent && (
                        <span
                          className="ag-badge ag-badge--primary"
                          style={{ alignSelf: "flex-start", flexShrink: 0 }}
                        >
                          Current
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="ag-card-body" style={{ flex: 1 }}>
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(3, 1fr)",
                        gap: 6,
                        marginBottom: 12,
                      }}
                    >
                      {[
                        ["Sims/mo", plan.sims],
                        ["Concurrent", plan.conc],
                        ["Rate", plan.rate],
                      ].map(([k, v]) => (
                        <div
                          key={k}
                          style={{
                            background: "var(--ag-bg-surface-2)",
                            border: "1px solid var(--ag-border-default)",
                            borderRadius: "var(--ag-radius-sm)",
                            padding: "6px 8px",
                            textAlign: "center",
                          }}
                        >
                          <p
                            className="ag-caption"
                            style={{ marginBottom: 1, fontSize: 10 }}
                          >
                            {k}
                          </p>
                          <p
                            style={{
                              fontSize: 11,
                              fontWeight: 600,
                              color: "var(--ag-text-primary)",
                              margin: 0,
                            }}
                          >
                            {v}
                          </p>
                        </div>
                      ))}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                      }}
                    >
                      {plan.features.map((f) => (
                        <div
                          key={f}
                          style={{
                            display: "flex",
                            alignItems: "flex-start",
                            gap: 7,
                          }}
                        >
                          <i
                            className="fa-solid fa-check"
                            style={{
                              color: "var(--ag-success)",
                              fontSize: 11,
                              marginTop: 2,
                              flexShrink: 0,
                            }}
                          />
                          <span className="ag-caption">{f}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div
                    style={{
                      padding: "12px 16px",
                      borderTop: "1px solid var(--ag-border-default)",
                    }}
                  >
                    {isCurrent ? (
                      <button
                        disabled
                        className="ag-button"
                        style={{ width: "100%" }}
                      >
                        Current Plan
                      </button>
                    ) : (
                      <button
                        className="ag-button ag-button--primary"
                        style={{ width: "100%" }}
                        disabled={upgrading === plan.id}
                        onClick={() => handleUpgrade(plan.id)}
                      >
                        {upgrading === plan.id
                          ? "Redirecting…"
                          : plan.id === "enterprise"
                            ? "Contact Sales"
                            : "Upgrade"}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Invoice history */}
        <div className="ag-card">
          <div className="ag-card-header">
            <p className="ag-section-title">Billing History</p>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className="ag-button ag-button--sm"
                onClick={() =>
                  exportToCSV(
                    INVOICES.map((inv) => ({
                      date: inv.date,
                      description: inv.desc,
                      amount: inv.amount,
                      status: "Paid",
                    })),
                    "billing-history.csv",
                  )
                }
              >
                <i
                  className="fa-solid fa-download"
                  style={{ marginRight: 5 }}
                />
                Export CSV
              </button>
              <button
                className="ag-button ag-button--sm"
                onClick={handleManage}
              >
                View All Invoices
              </button>
            </div>
          </div>
          <table className="ag-table">
            <thead>
              <tr>
                {["Date", "Description", "Amount", "Status", ""].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {INVOICES.map((inv) => (
                <tr key={inv.date}>
                  <td className="ag-caption">{inv.date}</td>
                  <td style={{ color: "var(--ag-text-primary)" }}>
                    {inv.desc}
                  </td>
                  <td
                    style={{ color: "var(--ag-text-primary)", fontWeight: 500 }}
                  >
                    {inv.amount}
                  </td>
                  <td>
                    <span
                      className="ag-badge ag-badge--success"
                      style={{ fontSize: 11 }}
                    >
                      Paid
                    </span>
                  </td>
                  <td>
                    <button
                      className="ag-button ag-button--sm"
                      onClick={() =>
                        exportToCSV(
                          [
                            {
                              date: inv.date,
                              description: inv.desc,
                              amount: inv.amount,
                              status: "Paid",
                            },
                          ],
                          `invoice-${inv.date.replace(/[, ]/g, "-")}.csv`,
                        )
                      }
                    >
                      <i
                        className="fa-solid fa-download"
                        style={{ marginRight: 4 }}
                      />
                      CSV
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
