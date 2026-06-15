# Phase 7 — Enterprise Portal Upgrade

> **Goal:** Transform the current basic developer portal into a professional enterprise AI engine dashboard that large organizations and developers will recognize as production-grade infrastructure.
>
> **Current gap:** The portal shows quota bars and quick links. A real enterprise client needs to see simulation run history, data pipelines, compute infrastructure, team management, and clear deployment options.

---

## Architecture Overview

```
apps/portal/src/app/
├── page.tsx                          ← Public marketing landing page (7-G)
├── dashboard/
│   ├── layout.tsx                    ← Restructured nav (7-H)
│   ├── page.tsx                      ← Dashboard + Plotly charts (7-A)
│   ├── simulations/
│   │   └── page.tsx                  ← Run browser + drill-down (7-B)
│   ├── jobs/
│   │   └── page.tsx                  ← Async job queue (7-E)
│   ├── data/
│   │   └── page.tsx                  ← Data connectors (7-C)
│   ├── infrastructure/
│   │   └── page.tsx                  ← Deployment + MPC nodes (7-D)
│   ├── team/
│   │   └── page.tsx                  ← Members + RBAC + audit log (7-F)
│   ├── playground/page.tsx           ← Existing (keep)
│   ├── api-keys/page.tsx             ← Existing (keep)
│   ├── usage/page.tsx                ← Existing (keep)
│   ├── billing/page.tsx              ← Existing (keep)
│   └── settings/page.tsx             ← Existing (keep)
```

---

## 7-H: Navigation Restructure (implement FIRST — everything depends on it)

Replace the flat 6-item nav with grouped sections:

```
ALGENTA
─────────────────────────────
Overview
  ◈  Dashboard

Simulations
  ▷  Playground
  ≡  Runs
  ⊡  Jobs

Data
  ⬡  Connectors

Infrastructure
  ⊕  Compute

Organization
  ⊞  Team
─────────────────────────────
Account
  ⬡  API Keys
  ◉  Usage
  ◇  Billing
  ⊕  Settings
─────────────────────────────
Dev Org  [developer badge]
dev@example.com
[Sign out]
```

Nav items use section headers (non-clickable labels in grey) + individual links.

---

## 7-A: Dashboard Upgrade — Plotly Charts

Install: `npm install react-plotly.js plotly.js-dist-min`
Use dynamic import with `ssr: false` (Plotly is browser-only).

### Charts to add:

| Chart | X-axis | Y-axis | Plotly type |
|---|---|---|---|
| Simulation Volume (30d) | Date | Runs count | `scatter` with area fill, color `#6B42FC` |
| Decision Outcome Distribution | — | proceed/caution/reject % | `pie` donut, colors `#00A854/#F59E0B/#E53535` |
| Expected Value Distribution | EV buckets | Frequency | `histogram`, color `#6B42FC` opacity 0.7 |
| Latency Trend (30d) | Date | p50/p95 ms | `scatter` dual trace |
| Confidence Score Trend | Date | Confidence 0–1 | `scatter` with gradient |

### Plotly layout config (shared):
```json
{
  "paper_bgcolor": "rgba(0,0,0,0)",
  "plot_bgcolor": "rgba(0,0,0,0)",
  "font": { "family": "Inter, system-ui", "color": "#555555" },
  "margin": { "t": 20, "r": 10, "b": 40, "l": 40 },
  "xaxis": { "gridcolor": "#F0F1F5", "linecolor": "#C7C7CC" },
  "yaxis": { "gridcolor": "#F0F1F5", "linecolor": "#C7C7CC" }
}
```

### Recent runs activity feed (replaces quick links):
```
Latest activity                           [View all →]
──────────────────────────────────────────────────────
✓ proceed   run_abc123   Product Launch   EV $142k   12ms   2m ago
⚠ caution   run_def456   Risk Scenario    EV $-8k    18ms   14m ago
✓ proceed   run_ghi789   Market Entry     EV $310k   9ms    1h ago
✕ reject    run_jkl012   Acquisition      EV $-220k  22ms   2h ago
```

---

## 7-B: Simulations / Runs Page — `/dashboard/simulations`

### Run browser table
```
Filter bar:
  [Search run_id...] [Mode: All▼] [Action: All▼] [From: ___] [To: ___] [Export CSV]

Table (sortable columns):
  Run ID          | Mode    | Action    | EV          | Confidence | Latency | Created
  run_abc123...   | auto    | ● proceed | $142,000    | 89%        | 12ms    | 3/20 18:42
  run_def456...   | expert  | ⚠ caution | $-8,200     | 61%        | 18ms    | 3/20 18:28
  
Pagination: [← Prev] [1 2 3 ... 24] [Next →]
```

### Run drill-down side panel (opens on row click):
```
Run detail: run_abc123
─────────────────────────────────────────────────
Recommended action:   ● PROCEED
Confidence:           89%
Rationale:            "High probability of positive return..."

Metrics:
  Expected value      $142,000
  Probability loss    3.2%
  Scenarios run       10,000
  Execution           12ms

Percentile chart (Plotly horizontal bar P5→P95):
[════════════════════════════════]
 P5    P25    P50    P75    P95

Full JSON payload (collapsible)
Result hash (SHA-256): abc123...

Actions: [Re-run →] [Export JSON] [Copy run_id]
```

### Requires new API endpoint:
`GET /v1/runs?page=1&limit=20&action=proceed&mode=auto&from=2026-03-01&to=2026-03-20`

Response:
```json
{
  "runs": [
    {
      "run_id": "uuid",
      "mode": "auto",
      "recommended_action": "proceed",
      "confidence": 0.89,
      "metrics": { "expected_value": 142000, "probability_of_loss": 0.032 },
      "scenarios_run": 10000,
      "execution_ms": 12,
      "created_at": "2026-03-20T18:42:00Z"
    }
  ],
  "total": 487,
  "page": 1,
  "limit": 20
}
```

---

## 7-C: Data Connectors — `/dashboard/data`

### Connection type cards (grid layout):

```
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  AWS S3             │  │  Google BigQuery     │  │  PostgreSQL         │
│  Cloud Storage      │  │  Data Warehouse      │  │  Database           │
│  ● 2 connected      │  │  ○ Not configured    │  │  ● 1 connected      │
│  [Manage →]         │  │  [Connect →]         │  │  [Manage →]         │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘

┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  Snowflake          │  │  Azure Blob          │  │  REST API           │
│  Data Warehouse     │  │  Cloud Storage       │  │  Custom Endpoint    │
│  ○ Not configured   │  │  ○ Not configured    │  │  ● 3 connected      │
│  [Connect →]        │  │  [Connect →]         │  │  [Manage →]         │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘

┌─────────────────────┐
│  File Upload        │
│  CSV / Parquet      │
│  / Excel / JSON     │
│  [Upload file →]    │
└─────────────────────┘
```

### Active connections list (below the grid):
```
Name            Type        Status    Last tested    Tables/Columns    Actions
prod-s3-bucket  AWS S3      ● Live    2m ago         —                 [Test] [Edit] [Delete]
analytics-db    PostgreSQL  ● Live    1h ago         14 tables         [Browse] [Test] [Delete]
webhook-api     REST API    ✕ Error   3d ago         —                 [Fix config] [Delete]
```

### Add connector dialog (full form):
- Connection type selector
- Name field
- Config fields (dynamically rendered per type)
- Test connection button (calls `POST /v1/connectors/test`)
- Credentials encrypted in browser before sending

### Data model: `data_connectors` table
```sql
CREATE TABLE data_connectors (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL REFERENCES organizations(id),
  name TEXT NOT NULL,
  type TEXT NOT NULL,  -- 's3'|'gcs'|'bigquery'|'snowflake'|'postgres'|'rest'|'file'
  config JSONB,        -- AES-256 encrypted config blob
  status TEXT DEFAULT 'untested',
  last_tested_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 7-D: Infrastructure — `/dashboard/infrastructure`

### Deployment mode selector:
```
┌────────────────────────────────────────────────────────────────────────┐
│  ALGENTA CLOUD                                           ● Active       │
│  Fully managed infrastructure. No DevOps required.                     │
│  Region: us-east-1 | Engine: v0.3.1 | Uptime 30d: 99.97%              │
│  Compute: Codna shared cluster | Max runs/request: 1,000,000         │
│  [View status page ↗]                                                  │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  SELF-HOSTED                                             ○ Configure   │
│  Run the Codna engine in your own VPC, cluster, or bare metal.       │
│  Docker Compose | Kubernetes (Helm chart) | VM / bare metal            │
│  Your data never leaves your infrastructure.                           │
│  Requires Enterprise license.                                          │
│  [Read self-hosting guide →] [Get license key →]                       │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  HYBRID                                                  ○ Contact sales│
│  API gateway + auth on Codna Cloud.                                  │
│  Simulation workers run inside your VPC.                               │
│  Zero data egress. Full audit trail. Enterprise plan only.             │
│  [Contact enterprise →]                                                │
└────────────────────────────────────────────────────────────────────────┘
```

### MPC Compute Nodes panel (shown for self-hosted / hybrid):
```
Compute Nodes                                              [Add node +]
────────────────────────────────────────────────────────────────────────
Node              Status    Engine     CPU   Memory   Throughput   Region
algenta-node-1    ● Live    v0.3.1     12%   2.1 GB   142 jobs/s   us-east-1
algenta-node-2    ● Live    v0.3.1     34%   3.8 GB   398 jobs/s   eu-west-1
algenta-node-3    ○ Idle    v0.3.1     1%    0.9 GB   0 jobs/s     ap-south-1
algenta-node-4    ✕ Error   v0.2.9     —     —        —            us-west-2

[algenta-node-4]  Engine version mismatch. Expected v0.3.1, running v0.2.9.
                  [View logs] [Restart] [Update engine]
```

### Engine health panel:
```
Engine Status
  Current version:   v0.3.1
  Latest available:  v0.3.2 [Update available]
  Mode:              subprocess (Pattern A)
  Python adapter:    healthy
  Last health check: 12 seconds ago

Performance (last 1h):
  Median latency:    8ms
  P95 latency:       24ms
  Throughput:        1,240 runs/min
  Error rate:        0.02%
```

---

## 7-E: Jobs / Async Queue — `/dashboard/jobs`

### Status tabs + filter:
```
[All (124)] [Queued (3)] [Running (2)] [Completed (115)] [Failed (4)]

Table:
Job ID          | Submitted       | Status     | Runs    | Duration | Webhook  | Actions
job_abc123...   | 3/20 18:42:01   | ✓ done     | 50,000  | 4.2s     | ✓ 200   | [View] [Re-run]
job_def456...   | 3/20 18:38:14   | ▶ running  | 1M      | 12s...   | pending  | [Cancel]
job_ghi789...   | 3/20 18:30:00   | ⏳ queued  | 10,000  | —        | pending  | [Cancel]
job_jkl012...   | 3/20 16:12:44   | ✕ failed   | 100,000 | error    | —        | [Retry] [View error]
```

### Job detail panel:
```
Job: job_abc123
Status: ✓ Completed in 4.2s

Input: mode=expert, variables=3, runs=50,000, seed=42
Result: proceed (92% confidence) | EV $248,000

Webhook delivery log:
  Attempt 1 → POST https://hooks.example.com/algenta
  Status: 200 OK | Latency: 142ms | Delivered: 3/20 18:42:06

[View full result →] [Download JSON] [Re-run with same payload]
```

---

## 7-F: Team — `/dashboard/team`

### Members table:
```
[+ Invite member]                                              [2 of 5 seats used]

Avatar  Name           Email                  Role     Last active    Actions
  AB    Angel Burgess  angel@codna.ai        Owner    Just now       [—]
  JD    Jane Doe       jane@example.com        Admin    2h ago         [Change role ▼] [Remove]
  
Invite dialog: [Email] [Role: Member ▼] [Send invite]
```

### Roles:
```
Owner   → full access, billing, delete org, manage SSO
Admin   → all except billing and org deletion
Member  → simulate, view runs, use playground, manage own API keys
Viewer  → read-only access to runs and usage
```

### SSO Section (Enterprise badge):
```
Single Sign-On                                    [Enterprise feature]
  Provider: [None ▼]  or  [SAML 2.0] or [OIDC]

  When SAML 2.0 selected:
    IdP Entity ID:  [_________________________]
    SSO URL:        [_________________________]
    Certificate:    [Upload PEM file...]
    
  [Test SSO connection]  [Save]
```

### Audit Log:
```
Export: [CSV] [JSON]    Filter: [Actor ▼] [Action ▼] [From—To]

Timestamp            Actor              Action              Resource    Result
2026-03-20 18:42:01  angel@codna.ai   simulate            run_abc     success
2026-03-20 18:40:14  angel@codna.ai   api_key.create      key_xyz     success
2026-03-20 17:15:33  jane@example.com   login               —           success
2026-03-20 16:44:01  angel@codna.ai   plan.upgrade        developer   success
```

---

## 7-G: Public Landing Page — `apps/portal/src/app/page.tsx`

Replace the current minimal page with a full marketing site:

### Sections:
1. **Hero** — Headline + subhead + two CTAs + rotating code block (curl / Python / TS)
2. **How it works** — 3 steps (Define variables → Run Monte Carlo → Get Decision)
3. **Integration logos** — ChatGPT, LangChain, n8n, Power Automate, Zapier, Make
4. **Live simulation demo** — Plotly chart showing a simulation result animating
5. **Pricing table** — Free / Developer $29 / Pro $99 / Enterprise (columns)
6. **Enterprise section** — Compliance, SSO, dedicated compute, SLA
7. **Footer** — Links, docs, GitHub, status, email

### Key headline options:
- *"Monte Carlo Simulation as an API"*
- *"AI-Powered Decision Intelligence for Enterprise Teams"*
- *"Run 1 million simulations in milliseconds. Make decisions with confidence."*

---

## 7-I: New API Endpoints

### Portal API (`apps/api_server/routers/`)

| File | Endpoints | Notes |
|---|---|---|
| `runs.py` | `GET /v1/runs`, `GET /v1/runs/{id}` | Paginated simulation history |
| `connectors.py` | `GET/POST /v1/connectors`, `POST /v1/connectors/{id}/test`, `DELETE /v1/connectors/{id}` | Data source management |
| `nodes.py` | `GET /v1/nodes` | Compute node health (stub for hosted) |
| `team.py` | `GET /v1/team`, `POST /v1/team/invite`, `PATCH /v1/team/{id}/role`, `DELETE /v1/team/{id}` | Member management |
| `audit.py` | `GET /v1/audit-logs` | Paginated audit trail |

---

## Implementation Order

Priority based on visual impact and enterprise demo value:

1. **7-H** — Nav restructure (layout.tsx) — enables everything else
2. **7-A** — Dashboard Plotly charts — first impression
3. **7-B** — Simulations runs page — "real data" feel
4. **7-D** — Infrastructure page — answers deployment question
5. **7-E** — Jobs page — reuses existing `/v1/jobs` API
6. **7-C** — Data connectors page — static UI first
7. **7-F** — Team page — static UI first
8. **7-G** — Landing page — standalone marketing page
9. **7-I** — New API endpoints — backend for new pages

---

## Dependencies to install

```bash
cd apps/portal
npm install react-plotly.js plotly.js-dist-min
npm install @types/react-plotly.js
```

`plotly.js-dist-min` is used instead of full `plotly.js` to keep bundle size reasonable (~1.2MB vs 3.5MB).

---

## Definition of Done

A senior developer at an enterprise company viewing this portal should be able to:
- See their simulation run history with charts showing trends
- Understand exactly where compute runs (hosted vs self-hosted vs hybrid)
- Connect their data sources (S3, databases, APIs)
- Track async jobs with webhook delivery status
- Manage team access and audit who did what
- Understand the pricing and upgrade path
