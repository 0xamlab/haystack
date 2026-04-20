import Link from "next/link";
import { Logo } from "@/components/Logo";

const PLANS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    sims: "500 sims/month",
    highlight: false,
    features: [
      "500 simulations/month",
      "10K max runs",
      "Auto + Expert mode",
      "Python + TS SDKs",
    ],
  },
  {
    name: "Developer",
    price: "$29",
    period: "/month",
    sims: "10,000 sims/month",
    highlight: true,
    features: [
      "10,000 simulations/month",
      "100K max runs",
      "Async jobs",
      "Webhooks",
      "Priority support",
    ],
  },
  {
    name: "Pro",
    price: "$99",
    period: "/month",
    sims: "100,000 sims/month",
    highlight: false,
    features: [
      "100,000 simulations/month",
      "1M max runs",
      "Unlimited async jobs",
      "Dedicated support",
      "SLA 99.9%",
    ],
  },
];

const INTEGRATIONS = [
  "ChatGPT Actions",
  "LangChain",
  "n8n",
  "Power Automate",
  "Zapier",
  "Make",
];

export default function LandingPage() {
  return (
    <div
      style={{
        fontFamily: "var(--font-body)",
        color: "var(--color-text-dark)",
        background: "#FFFFFF",
        minHeight: "100vh",
      }}
    >
      {/* Nav */}
      <nav
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "18px 48px",
          borderBottom: "1px solid var(--color-border-light)",
          position: "sticky",
          top: 0,
          background: "rgba(255,255,255,0.95)",
          backdropFilter: "blur(12px)",
          zIndex: 100,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Logo width={28} height={19} />
          <span
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 600,
              fontSize: "15px",
              color: "var(--color-text-dark)",
              letterSpacing: "-0.01em",
            }}
          >
            Algenta
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
          <a
            href="http://localhost:3001"
            style={{
              fontFamily: "var(--font-body)",
              fontWeight: 300,
              fontSize: "14px",
              color: "var(--color-text-secondary)",
              textDecoration: "none",
            }}
          >
            Docs
          </a>
          <Link
            href="/login"
            style={{
              fontFamily: "var(--font-body)",
              fontWeight: 300,
              fontSize: "14px",
              color: "var(--color-text-secondary)",
              textDecoration: "none",
            }}
          >
            Log in
          </Link>
          <Link
            href="/login"
            style={{
              padding: "8px 18px",
              background: "#1E1B31",
              borderRadius: "var(--radius-btn)",
              fontFamily: "var(--font-body)",
              fontWeight: 500,
              fontSize: "14px",
              color: "#FFFFFF",
              textDecoration: "none",
            }}
          >
            Start free →
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section
        style={{
          padding: "96px 48px 72px",
          maxWidth: "1100px",
          margin: "0 auto",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "4px 12px",
            background: "rgba(107,66,252,0.06)",
            border: "1px solid rgba(107,66,252,0.2)",
            borderRadius: "160px",
            marginBottom: "28px",
          }}
        >
          <div
            style={{
              width: "5px",
              height: "5px",
              borderRadius: "50%",
              background: "#6B42FC",
            }}
          />
          <span
            style={{
              fontFamily: "var(--font-body)",
              fontWeight: 400,
              fontSize: "13px",
              color: "#6B42FC",
            }}
          >
            Monte Carlo Simulation as an API
          </span>
        </div>
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 300,
            fontSize: "68px",
            lineHeight: "108%",
            color: "var(--color-text-dark)",
            margin: "0 0 24px",
            letterSpacing: "-0.02em",
            maxWidth: "800px",
          }}
        >
          Run 1 million simulations.
          <br />
          Make decisions with confidence.
        </h1>
        <p
          style={{
            fontFamily: "var(--font-body)",
            fontWeight: 300,
            fontSize: "20px",
            lineHeight: "150%",
            color: "var(--color-text-secondary)",
            maxWidth: "600px",
            margin: "0 0 40px",
          }}
        >
          Algenta gives your AI agents and enterprise workflows a probabilistic
          decision engine. One API call returns a full decision envelope with
          expected value, risk metrics, and a clear recommendation.
        </p>
        <div style={{ display: "flex", gap: "14px", alignItems: "center" }}>
          <Link
            href="/login"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "14px 28px",
              background: "#1E1B31",
              borderRadius: "var(--radius-btn)",
              fontFamily: "var(--font-body)",
              fontWeight: 500,
              fontSize: "16px",
              color: "#FFFFFF",
              textDecoration: "none",
            }}
          >
            Get started free
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path
                d="M2 7H12M12 7L8 3M12 7L8 11"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </Link>
          <a
            href="http://localhost:3001/quickstart"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "13px 27px",
              border: "1px solid var(--color-border-light)",
              borderRadius: "var(--radius-btn)",
              fontFamily: "var(--font-body)",
              fontWeight: 400,
              fontSize: "16px",
              color: "var(--color-text-secondary)",
              textDecoration: "none",
            }}
          >
            Read the docs
          </a>
        </div>
      </section>

      {/* Code example */}
      <section
        style={{ padding: "0 48px 80px", maxWidth: "1100px", margin: "0 auto" }}
      >
        <div
          style={{
            background: "#1E1B31",
            borderRadius: "10px",
            padding: "28px 32px",
            overflow: "auto",
          }}
        >
          <pre
            style={{
              margin: 0,
              fontFamily: "monospace",
              fontSize: "13px",
              lineHeight: "170%",
              color: "#E8E4FF",
            }}
          >{`curl -X POST https://api.algenta.ai/v1/simulate \\
  -H "X-API-Key: de_live_your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "mode": "auto",
    "scenario": {
      "variables": { "revenue": { "low": 80000, "high": 300000 } },
      "objective": "maximize_net_value"
    },
    "runs": 10000
  }'

# → { "recommended_action": "proceed", "confidence": 0.89,
#     "metrics": { "expected_value": 142000, ... } }`}</pre>
        </div>
      </section>

      {/* How it works */}
      <section
        style={{
          padding: "72px 48px",
          background: "var(--color-bg-light-grey)",
        }}
      >
        <div style={{ maxWidth: "1100px", margin: "0 auto" }}>
          <p
            style={{
              fontFamily: "var(--font-body)",
              fontWeight: 500,
              fontSize: "12px",
              color: "#6B42FC",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              margin: "0 0 16px",
            }}
          >
            HOW IT WORKS
          </p>
          <h2
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 400,
              fontSize: "42px",
              color: "var(--color-text-dark)",
              margin: "0 0 48px",
              letterSpacing: "-0.01em",
            }}
          >
            From data to decision in one call
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "24px",
            }}
          >
            {[
              {
                step: "01",
                title: "Define your variables",
                desc: "Describe the uncertain inputs to your decision — revenue ranges, cost scenarios, market probabilities — using our simple JSON schema or Python/TypeScript SDK.",
              },
              {
                step: "02",
                title: "Run Monte Carlo simulation",
                desc: "Algenta runs 10,000–1,000,000 scenario iterations on our Mojo-powered compute engine, sampling distributions and computing statistics in milliseconds.",
              },
              {
                step: "03",
                title: "Get a decision envelope",
                desc: "Receive expected value, confidence score, probability of loss, percentile breakdown, and a clear recommended action — proceed, caution, or reject.",
              },
            ].map(({ step, title, desc }) => (
              <div
                key={step}
                style={{
                  background: "#FFFFFF",
                  borderRadius: "var(--radius-card)",
                  padding: "28px",
                }}
              >
                <p
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 400,
                    fontSize: "32px",
                    color: "rgba(107,66,252,0.2)",
                    margin: "0 0 16px",
                    lineHeight: 1,
                  }}
                >
                  {step}
                </p>
                <p
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 400,
                    fontSize: "18px",
                    color: "var(--color-text-dark)",
                    margin: "0 0 10px",
                  }}
                >
                  {title}
                </p>
                <p
                  style={{
                    fontFamily: "var(--font-body)",
                    fontWeight: 300,
                    fontSize: "14px",
                    color: "var(--color-text-secondary)",
                    margin: 0,
                    lineHeight: "150%",
                  }}
                >
                  {desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Integrations */}
      <section
        style={{ padding: "72px 48px", maxWidth: "1100px", margin: "0 auto" }}
      >
        <p
          style={{
            fontFamily: "var(--font-body)",
            fontWeight: 500,
            fontSize: "12px",
            color: "#6B42FC",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            margin: "0 0 16px",
          }}
        >
          INTEGRATIONS
        </p>
        <h2
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 400,
            fontSize: "36px",
            color: "var(--color-text-dark)",
            margin: "0 0 12px",
          }}
        >
          Works where you work
        </h2>
        <p
          style={{
            fontFamily: "var(--font-body)",
            fontWeight: 300,
            fontSize: "16px",
            color: "var(--color-text-secondary)",
            margin: "0 0 40px",
          }}
        >
          Native integrations for every AI and automation platform.
        </p>
        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
          {INTEGRATIONS.map((name) => (
            <div
              key={name}
              style={{
                padding: "10px 20px",
                background: "var(--color-bg-light-grey)",
                borderRadius: "160px",
                fontFamily: "var(--font-body)",
                fontWeight: 400,
                fontSize: "14px",
                color: "var(--color-text-secondary)",
              }}
            >
              {name}
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section
        style={{
          padding: "72px 48px",
          background: "var(--color-bg-light-grey)",
        }}
      >
        <div style={{ maxWidth: "1100px", margin: "0 auto" }}>
          <p
            style={{
              fontFamily: "var(--font-body)",
              fontWeight: 500,
              fontSize: "12px",
              color: "#6B42FC",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              margin: "0 0 16px",
            }}
          >
            PRICING
          </p>
          <h2
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 400,
              fontSize: "42px",
              color: "var(--color-text-dark)",
              margin: "0 0 8px",
            }}
          >
            Simple, transparent pricing
          </h2>
          <p
            style={{
              fontFamily: "var(--font-body)",
              fontWeight: 300,
              fontSize: "16px",
              color: "var(--color-text-secondary)",
              margin: "0 0 40px",
            }}
          >
            Start free, scale as you grow. No hidden fees.
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "16px",
              marginBottom: "20px",
            }}
          >
            {PLANS.map((plan) => (
              <div
                key={plan.name}
                style={{
                  background: "#FFFFFF",
                  border: `1px solid ${plan.highlight ? "#6B42FC" : "var(--color-border-light)"}`,
                  borderRadius: "var(--radius-card)",
                  padding: "28px",
                  position: "relative",
                  overflow: "hidden",
                }}
              >
                {plan.highlight && (
                  <div
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      right: 0,
                      height: "3px",
                      background: "#6B42FC",
                    }}
                  />
                )}
                {plan.highlight && (
                  <span
                    style={{
                      display: "inline-block",
                      marginBottom: "8px",
                      padding: "2px 10px",
                      background: "rgba(107,66,252,0.08)",
                      borderRadius: "3px",
                      fontFamily: "var(--font-body)",
                      fontSize: "11px",
                      fontWeight: 500,
                      color: "#6B42FC",
                    }}
                  >
                    Most popular
                  </span>
                )}
                <p
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 400,
                    fontSize: "20px",
                    color: "var(--color-text-dark)",
                    margin: "0 0 4px",
                  }}
                >
                  {plan.name}
                </p>
                <div style={{ marginBottom: "6px" }}>
                  <span
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 400,
                      fontSize: "38px",
                      color: "var(--color-text-dark)",
                      lineHeight: 1,
                    }}
                  >
                    {plan.price}
                  </span>
                  <span
                    style={{
                      fontFamily: "var(--font-body)",
                      fontWeight: 300,
                      fontSize: "14px",
                      color: "var(--color-text-grey)",
                      marginLeft: "4px",
                    }}
                  >
                    {plan.period}
                  </span>
                </div>
                <p
                  style={{
                    fontFamily: "var(--font-body)",
                    fontWeight: 300,
                    fontSize: "13px",
                    color: "var(--color-text-grey)",
                    margin: "0 0 20px",
                  }}
                >
                  {plan.sims}
                </p>
                <ul
                  style={{
                    listStyle: "none",
                    padding: 0,
                    margin: "0 0 24px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                  }}
                >
                  {plan.features.map((f) => (
                    <li
                      key={f}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "8px",
                        fontFamily: "var(--font-body)",
                        fontWeight: 300,
                        fontSize: "13px",
                        color: "var(--color-text-secondary)",
                      }}
                    >
                      <span
                        style={{
                          color: plan.highlight ? "#6B42FC" : "#00A854",
                          flexShrink: 0,
                          marginTop: "1px",
                        }}
                      >
                        ✓
                      </span>
                      {f}
                    </li>
                  ))}
                </ul>
                <Link
                  href="/login"
                  style={{
                    display: "block",
                    textAlign: "center",
                    padding: "10px",
                    background: plan.highlight
                      ? "#6B42FC"
                      : "var(--color-bg-light-grey)",
                    border: `1px solid ${plan.highlight ? "#6B42FC" : "var(--color-border-light)"}`,
                    borderRadius: "var(--radius-btn)",
                    fontFamily: "var(--font-body)",
                    fontWeight: 500,
                    fontSize: "14px",
                    color: plan.highlight
                      ? "#FFFFFF"
                      : "var(--color-text-dark)",
                    textDecoration: "none",
                  }}
                >
                  {plan.name === "Free" ? "Start free" : `Start ${plan.name}`}
                </Link>
              </div>
            ))}
          </div>

          {/* Enterprise row */}
          <div
            style={{
              background: "#1E1B31",
              borderRadius: "var(--radius-card)",
              padding: "24px 32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div>
              <p
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 400,
                  fontSize: "20px",
                  color: "#FFFFFF",
                  margin: "0 0 4px",
                }}
              >
                Enterprise
              </p>
              <p
                style={{
                  fontFamily: "var(--font-body)",
                  fontWeight: 300,
                  fontSize: "14px",
                  color: "rgba(255,255,255,0.6)",
                  margin: 0,
                }}
              >
                Custom SLAs · SSO / SAML · On-premises or hybrid deployment ·
                Dedicated compute · Volume pricing
              </p>
            </div>
            <a
              href="mailto:enterprise@algenta.ai"
              style={{
                flexShrink: 0,
                padding: "12px 24px",
                background: "rgba(255,255,255,0.1)",
                border: "1px solid rgba(255,255,255,0.2)",
                borderRadius: "var(--radius-btn)",
                fontFamily: "var(--font-body)",
                fontWeight: 500,
                fontSize: "14px",
                color: "#FFFFFF",
                textDecoration: "none",
              }}
            >
              Contact sales →
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer
        style={{
          padding: "40px 48px",
          borderTop: "1px solid var(--color-border-light)",
          background: "#FFFFFF",
        }}
      >
        <div
          style={{
            maxWidth: "1100px",
            margin: "0 auto",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Logo width={22} height={15} />
            <span
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 600,
                fontSize: "14px",
                color: "var(--color-text-dark)",
              }}
            >
              Algenta
            </span>
          </div>
          <div style={{ display: "flex", gap: "24px" }}>
            {[
              ["Docs", "http://localhost:3001"],
              ["API Reference", "http://localhost:3001/api-reference"],
              ["GitHub", "https://github.com"],
              ["Status", "#"],
              ["Privacy", "#"],
            ].map(([label, href]) => (
              <a
                key={label}
                href={href}
                style={{
                  fontFamily: "var(--font-body)",
                  fontWeight: 300,
                  fontSize: "13px",
                  color: "var(--color-text-grey)",
                  textDecoration: "none",
                }}
              >
                {label}
              </a>
            ))}
          </div>
          <p
            style={{
              fontFamily: "var(--font-body)",
              fontWeight: 300,
              fontSize: "13px",
              color: "var(--color-text-grey)",
              margin: 0,
            }}
          >
            © 2026 Algenta
          </p>
        </div>
      </footer>
    </div>
  );
}
