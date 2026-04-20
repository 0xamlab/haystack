"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { login, signup } from "@/lib/api";
import { saveSession, isAuthenticated } from "@/lib/auth";
import { Logo } from "@/components/Logo";
import { C } from "@/lib/console";

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isAuthenticated()) router.replace("/dashboard");
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (tab === "signup") {
        const res = await signup(email, password, name);
        saveSession({
          email: res.user.email,
          name: res.user.name,
          org_name: res.org.name,
          plan: res.org.plan as "free" | "developer" | "pro" | "enterprise",
          api_key: res.api_key?.raw_key ?? "",
          access_token: res.access_token,
        });
      } else {
        const res = await login(email, password);
        saveSession({
          email: res.user.email,
          name: res.user.name,
          org_name: res.org.name,
          plan: res.org.plan as "free" | "developer" | "pro" | "enterprise",
          api_key: "",
          access_token: res.access_token,
        });
      }
      router.replace("/dashboard");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: C.bg,
        fontFamily: C.fontBody,
      }}
    >
      {/* Subtle grid background */}
      <div
        style={{
          position: "fixed",
          inset: 0,
          backgroundImage: `radial-gradient(${C.border} 1px, transparent 1px)`,
          backgroundSize: "28px 28px",
          pointerEvents: "none",
        }}
      />

      <div style={{ width: "340px", position: "relative", zIndex: 1 }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "10px",
              marginBottom: "10px",
            }}
          >
            <Logo width={28} height={19} />
            <span
              style={{
                fontFamily: C.fontDisplay,
                fontWeight: 600,
                fontSize: "16px",
                color: C.text,
                letterSpacing: "0.01em",
              }}
            >
              Algenta
            </span>
          </div>
          <p
            style={{
              fontFamily: C.fontBody,
              fontWeight: 300,
              fontSize: "12px",
              color: C.muted,
              margin: 0,
            }}
          >
            Simulation Infrastructure Console
          </p>
        </div>

        {/* Card */}
        <div
          style={{
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: "8px",
            padding: "24px",
          }}
        >
          {/* Tabs */}
          <div
            style={{
              display: "flex",
              gap: "1px",
              marginBottom: "20px",
              background: C.s2,
              padding: "2px",
              borderRadius: "4px",
            }}
          >
            {(["login", "signup"] as const).map((t) => (
              <button
                key={t}
                onClick={() => {
                  setTab(t);
                  setError("");
                }}
                style={{
                  flex: 1,
                  padding: "6px",
                  borderRadius: "3px",
                  border: "none",
                  fontFamily: C.fontBody,
                  fontSize: "12px",
                  fontWeight: tab === t ? 500 : 300,
                  color: tab === t ? C.text : C.muted,
                  background: tab === t ? C.s3 : "transparent",
                  cursor: "pointer",
                  textTransform: "capitalize",
                }}
              >
                {t === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit}>
            {tab === "signup" && (
              <div style={{ marginBottom: "10px" }}>
                <label
                  style={{
                    fontFamily: C.fontBody,
                    fontWeight: 600,
                    fontSize: "9px",
                    letterSpacing: "0.09em",
                    textTransform: "uppercase",
                    color: C.muted,
                    display: "block",
                    marginBottom: "4px",
                  }}
                >
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  required
                  style={{
                    width: "100%",
                    padding: "8px 10px",
                    background: C.s2,
                    border: `1px solid ${C.border}`,
                    borderRadius: "4px",
                    fontFamily: C.fontBody,
                    fontWeight: 300,
                    fontSize: "12px",
                    color: C.text,
                    outline: "none",
                    boxSizing: "border-box",
                  }}
                  onFocus={(e) =>
                    (e.currentTarget.style.borderColor = C.purple)
                  }
                  onBlur={(e) => (e.currentTarget.style.borderColor = C.border)}
                />
              </div>
            )}

            <div style={{ marginBottom: "10px" }}>
              <label
                style={{
                  fontFamily: C.fontBody,
                  fontWeight: 600,
                  fontSize: "9px",
                  letterSpacing: "0.09em",
                  textTransform: "uppercase",
                  color: C.muted,
                  display: "block",
                  marginBottom: "4px",
                }}
              >
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  background: C.s2,
                  border: `1px solid ${C.border}`,
                  borderRadius: "4px",
                  fontFamily: C.fontBody,
                  fontWeight: 300,
                  fontSize: "12px",
                  color: C.text,
                  outline: "none",
                  boxSizing: "border-box",
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = C.purple)}
                onBlur={(e) => (e.currentTarget.style.borderColor = C.border)}
              />
            </div>

            <div style={{ marginBottom: "16px" }}>
              <label
                style={{
                  fontFamily: C.fontBody,
                  fontWeight: 600,
                  fontSize: "9px",
                  letterSpacing: "0.09em",
                  textTransform: "uppercase",
                  color: C.muted,
                  display: "block",
                  marginBottom: "4px",
                }}
              >
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  background: C.s2,
                  border: `1px solid ${C.border}`,
                  borderRadius: "4px",
                  fontFamily: C.fontBody,
                  fontWeight: 300,
                  fontSize: "12px",
                  color: C.text,
                  outline: "none",
                  boxSizing: "border-box",
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = C.purple)}
                onBlur={(e) => (e.currentTarget.style.borderColor = C.border)}
              />
            </div>

            {error && (
              <div
                style={{
                  marginBottom: "12px",
                  background: C.redD,
                  border: `1px solid rgba(229,53,53,0.25)`,
                  borderRadius: "4px",
                  padding: "8px 10px",
                }}
              >
                <p
                  style={{
                    fontFamily: C.fontBody,
                    fontSize: "11px",
                    color: C.red,
                    margin: 0,
                  }}
                >
                  {error}
                </p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%",
                padding: "9px",
                background: loading ? C.purpleD : C.purple,
                border: "none",
                borderRadius: "4px",
                fontFamily: C.fontBody,
                fontWeight: 500,
                fontSize: "13px",
                color: "#FFFFFF",
                cursor: loading ? "not-allowed" : "pointer",
                transition: "opacity 0.15s",
              }}
            >
              {loading ? "…" : tab === "login" ? "Sign in" : "Create account"}
            </button>
          </form>
        </div>

        <p
          style={{
            textAlign: "center",
            fontFamily: C.fontBody,
            fontWeight: 300,
            fontSize: "11px",
            color: C.muted,
            marginTop: "16px",
          }}
        >
          Algenta Simulation Infrastructure Console · v1.0
        </p>
      </div>
    </div>
  );
}
