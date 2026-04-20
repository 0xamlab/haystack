"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { isAuthenticated, getSession, clearSession, Session } from "@/lib/auth";

const NAV_GROUPS = [
  {
    label: "Infrastructure",
    items: [
      {
        href: "/dashboard",
        label: "Overview",
        icon: "fa-chart-line",
        exact: true,
      },
      {
        href: "/dashboard/infrastructure",
        label: "Compute Nodes",
        icon: "fa-server",
        exact: false,
      },
    ],
  },
  {
    label: "Execution",
    items: [
      {
        href: "/dashboard/simulations",
        label: "Executions",
        icon: "fa-code-compare",
        exact: false,
      },
      {
        href: "/dashboard/templates",
        label: "Templates",
        icon: "fa-layer-group",
        exact: false,
      },
      {
        href: "/dashboard/playground",
        label: "Playground",
        icon: "fa-flask",
        exact: false,
      },
      {
        href: "/dashboard/jobs",
        label: "Job Queue",
        icon: "fa-list-check",
        exact: false,
      },
      {
        href: "/dashboard/data",
        label: "Connectors",
        icon: "fa-plug",
        exact: false,
      },
    ],
  },
  {
    label: "Account",
    items: [
      {
        href: "/dashboard/usage",
        label: "Usage",
        icon: "fa-chart-bar",
        exact: false,
      },
      {
        href: "/dashboard/api-keys",
        label: "API Keys",
        icon: "fa-key",
        exact: false,
      },
      {
        href: "/dashboard/billing",
        label: "Billing",
        icon: "fa-credit-card",
        exact: false,
      },
      {
        href: "/dashboard/settings",
        label: "Settings",
        icon: "fa-sliders",
        exact: false,
      },
    ],
  },
];

// ── Sidebar content (shared between desktop fixed sidebar and mobile drawer) ──

function SidebarContent({
  session,
  pathname,
  isActive,
  handleLogout,
  onNavClick,
}: {
  session: Session;
  pathname: string;
  isActive: (href: string, exact: boolean) => boolean;
  handleLogout: () => void;
  onNavClick?: () => void;
}) {
  const initials = (session.email ?? "A").charAt(0).toUpperCase();

  return (
    <>
      {/* Logo */}
      <div className="ag-logo-area">
        <div className="ag-logo-icon">
          <i className="fa-solid fa-cube" />
        </div>
        <span className="ag-logo-name">ALGENTA</span>
      </div>

      {/* Nav */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px 8px",
          display: "flex",
          flexDirection: "column",
          gap: 24,
        }}
      >
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <p className="ag-nav-group-label" style={{ marginBottom: 6 }}>
              {group.label}
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {group.items.map(({ href, label, icon, exact }) => {
                const active = isActive(href, exact);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`ag-nav-item${active ? " ag-nav-item--active" : ""}`}
                    onClick={onNavClick}
                  >
                    <i
                      className={`fa-solid ${icon}`}
                      style={{
                        width: 16,
                        textAlign: "center",
                        fontSize: 13,
                        flexShrink: 0,
                      }}
                    />
                    {label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* User */}
      <div
        style={{
          padding: "12px 8px",
          borderTop: "1px solid var(--ag-border-default)",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "8px",
            borderRadius: "var(--ag-radius-sm)",
            cursor: "pointer",
            transition: "background 120ms",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = "rgba(255,255,255,0.04)")
          }
          onMouseLeave={(e) => (e.currentTarget.style.background = "")}
        >
          <div
            style={{
              width: 30,
              height: 30,
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
            {initials}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p
              style={{
                fontSize: 13,
                fontWeight: 500,
                color: "var(--ag-text-primary)",
                margin: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {session.org_name ?? "Org"}
            </p>
            <p
              style={{
                fontSize: 11,
                color: "var(--ag-text-faint)",
                margin: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {session.email}
            </p>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--ag-text-faint)",
              padding: "2px 4px",
              borderRadius: 4,
              flexShrink: 0,
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.color = "var(--ag-danger)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.color = "var(--ag-text-faint)")
            }
          >
            <i
              className="fa-solid fa-arrow-right-from-bracket"
              style={{ fontSize: 12 }}
            />
          </button>
        </div>
      </div>
    </>
  );
}

// ── Layout ─────────────────────────────────────────────────────────────────────

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [session, setSession] = useState<Session | null>(null);
  const [mounted, setMounted] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    const s = getSession();
    if (!s || !isAuthenticated()) {
      router.replace("/login");
    } else {
      setSession(s);
    }
    setMounted(true);
  }, [router]);

  // Close drawer when route changes
  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  // Prevent body scroll when drawer is open
  useEffect(() => {
    if (drawerOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [drawerOpen]);

  if (!mounted || !session) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--ag-bg-canvas)",
        }}
      >
        <div
          style={{
            width: 24,
            height: 24,
            border: "2px solid var(--ag-brand-primary)",
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.7s linear infinite",
          }}
        />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  function isActive(href: string, exact: boolean) {
    return exact
      ? pathname === href
      : pathname === href || pathname.startsWith(href + "/");
  }

  function handleLogout() {
    clearSession();
    router.push("/login");
  }

  function openDrawer() {
    setDrawerOpen(true);
  }

  function closeDrawer() {
    // Close via state — does NOT trigger browser back navigation
    setDrawerOpen(false);
  }

  return (
    <div className="ag-shell">
      {/* ── Desktop fixed sidebar ──────────────────────────────────────────── */}
      <aside className="ag-sidebar">
        <SidebarContent
          session={session}
          pathname={pathname}
          isActive={isActive}
          handleLogout={handleLogout}
        />
      </aside>

      {/* ── Mobile topbar (hidden on desktop) ─────────────────────────────── */}
      <div className="ag-mobile-topbar">
        <button
          className="ag-hamburger"
          onClick={openDrawer}
          aria-label="Open navigation"
        >
          <i className="fa-solid fa-bars" style={{ fontSize: 14 }} />
        </button>

        {/* Centered brand */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            className="ag-logo-icon"
            style={{ width: 28, height: 28, borderRadius: 8 }}
          >
            <i className="fa-solid fa-cube" style={{ fontSize: 13 }} />
          </div>
          <span
            style={{
              fontWeight: 700,
              fontSize: 16,
              letterSpacing: "-0.02em",
              color: "var(--ag-text-primary)",
            }}
          >
            ALGENTA
          </span>
        </div>

        {/* Spacer to balance hamburger */}
        <div style={{ width: 36 }} />
      </div>

      {/* ── Mobile sidebar backdrop + drawer ──────────────────────────────── */}
      {/* Backdrop — clicking closes drawer without navigating back */}
      <div
        className={`ag-sidebar-backdrop${drawerOpen ? " is-open" : ""}`}
        onClick={closeDrawer}
        aria-hidden="true"
      />

      {/* Slide-in drawer */}
      <div className={`ag-sidebar-drawer${drawerOpen ? " is-open" : ""}`}>
        {/* Close button — state-based, not browser back */}
        <button
          className="ag-sidebar-drawer-close"
          onClick={closeDrawer}
          aria-label="Close navigation"
        >
          <i className="fa-solid fa-xmark" />
        </button>

        <SidebarContent
          session={session}
          pathname={pathname}
          isActive={isActive}
          handleLogout={handleLogout}
          onNavClick={closeDrawer}
        />
      </div>

      {/* ── Main content ───────────────────────────────────────────────────── */}
      <main className="ag-main">{children}</main>
    </div>
  );
}
