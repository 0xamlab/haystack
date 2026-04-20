# Algenta Portal — Go-Live Gap Analysis & Implementation Plan

## Executive Summary

The current portal is **demo-level** — it renders UI but most interactions are non-functional. This document tracks every gap and the implementation path to production.

---

## Critical Infrastructure Issues (Must Fix First)

### 1. Layout Regression
**Problem:** Sidebar and main content share same visual container; content overflows sidebar boundary.
**Root cause:** `ag-shell` CSS grid + `position: sticky` on sidebar breaks column containment.
**Fix:** Use `position: fixed` for sidebar + `padding-left: 248px` on html body, OR use a proper flex layout without grid.

### 2. Overview/Dashboard — Fake Historical Data
**Problem:** Volume chart shows "last 30 days" but DB is empty (just started).
**Fix:** Only show data that exists. If 0 runs → show empty state, not fabricated spline.

---

## Data Connectors (`/dashboard/data`) — 100% Fake

### What's fake:
- "Connect" button creates a DB record with **empty config** — no credentials stored
- `test_connector` endpoint in backend **doesn't actually connect** to S3/GCS/PostgreSQL
- "Browse" button does nothing
- Status is always "untested" because nothing real was configured

### What needs to happen:
1. **Credential forms per connector type** (modal with proper fields):
   - AWS S3: `bucket`, `region`, `access_key_id`, `secret_access_key`
   - GCS: `bucket`, `project_id`, `service_account_json`
   - Azure Blob: `account_name`, `account_key`, `container`
   - BigQuery: `project_id`, `dataset`, `service_account_json`
   - Snowflake: `account`, `user`, `password`, `database`, `warehouse`
   - PostgreSQL: `host`, `port`, `database`, `user`, `password`, `ssl_mode`
   - REST API: `base_url`, `auth_type`, `api_key_header`, `api_key`
   - File Upload: direct file upload UI

2. **Backend actually validates connections:**
   - `POST /v1/connectors/{id}/test` must attempt a real connection
   - For S3: `boto3.client('s3').list_objects_v2(Bucket=bucket, MaxKeys=1)`
   - For PostgreSQL: `psycopg2.connect(dsn).cursor().execute('SELECT 1')`
   - For REST API: `requests.get(base_url, headers=auth_headers, timeout=5)`
   - Store config encrypted in DB (use Fernet symmetric key from `settings.SECRET_KEY`)

3. **Browse button:**
   - S3/GCS/Azure: list objects/files in the bucket
   - PostgreSQL/BigQuery/Snowflake: list tables
   - REST API: show last response from health endpoint

### Required packages:
```
boto3          # AWS S3
google-cloud-storage  # GCS
azure-storage-blob    # Azure
snowflake-connector-python  # Snowflake
psycopg2-binary  # PostgreSQL
requests       # REST API
cryptography   # For encrypting credentials at rest
```

---

## Playground (`/dashboard/playground`) — Partially Works

### What's real:
- `simulate()` API call works if API server is running
- Monaco editor renders JSON
- Results panel shows real API response

### What's broken:
- Variable sliders don't actually affect the JSON payload (they're separate state, but the `body` sent uses `vals` only when `mode === "auto"`)
- Expert mode sends raw JSON from editor — this DOES work if valid JSON
- No error recovery if API is down

### Fix:
- Sync variable sliders → JSON editor in real time (both directions)
- Show proper error if API unreachable
- Add "Save as template" functionality (saves to localStorage)

---

## Infrastructure (`/dashboard/infrastructure`) — Conceptually Wrong

### Reality check:
- **Algenta Cloud** = our own managed API server (what's already running)
- **Self-hosted** = Docker/K8s deployment the customer runs themselves
- **Hybrid** = Customer's compute calling our API

### What's real:
- Engine health metrics (latency, throughput, uptime) come from real `/v1/infrastructure` API
- Node list shows actual compute nodes registered

### What's fake:
- "Add Node" → no real node registration system
- "Logs" → fake timestamped strings, not real logs
- "Restart" → no real restart mechanism
- Deployment mode cards → purely informational, can't actually switch

### Correct framing for production:
- **Compute Nodes section** = Show real nodes from infrastructure API
- **Deployment Mode** = Read-only info card showing current deployment type from env config
- **Add Node** → Only available in Self-hosted mode (links to docs for adding workers)
- **Logs** → Tail actual structured logs from the API (via `/v1/logs` SSE stream)
- Remove fake modal/restart for now, replace with links to infrastructure docs

---

## Simulation Volume — Shows Fake History

### Problem:
- Chart uses `buildDates()` which fills missing dates with 0
- Shows 30 days starting from today-30, but we may have 0 historical runs
- Looks like a chart going from 0 to a spike "today"

### Fix:
- Fetch actual `analytics` data
- If `analytics.total_runs === 0` → show empty state: "No simulations yet. Run your first simulation in the Playground."
- If data exists, show only days with actual data (don't pad 30 empty days)

---

## Settings (`/dashboard/settings`) — Profile Save Works But...

### Issues:
- `updateMe()` calls `PATCH /v1/me` — ✅ this works (just implemented)
- But the schema allows updating `name` and `org_name`, not `email` (email is auth identity)
- Notification preferences: localStorage only, never sent to backend
- Password change: no endpoint exists
- 2FA: no infrastructure exists
- "Delete Organization" → no endpoint exists

### Fix priority:
1. ✅ Name/org save works
2. Gray out email field (can't change via UI — requires auth flow)
3. Notification preferences: add user-level preferences table in DB
4. Remove 2FA, Password, Delete buttons → replace with "Coming soon" or links to support

---

## Full Go-Live Checklist

### Phase 1 — Fix What's Broken (Now)
- [ ] Fix sidebar layout (CSS)
- [ ] Overview: show empty state when no data
- [ ] Playground: sync sliders ↔ JSON editor
- [ ] Infrastructure: remove fake elements, show real data only
- [ ] Data connectors: add real credential forms per connector type
- [ ] Settings: gray out email, remove fake 2FA/delete buttons

### Phase 2 — Real Backend for Connectors (Week 1)
- [ ] Add credential encryption (`cryptography` package, Fernet)
- [ ] `connector.config` stored encrypted in DB
- [ ] `test_connector` actually connects for each type
- [ ] Install required packages: `boto3`, `psycopg2-binary`, `requests` (already installed)
- [ ] `browse_connector` endpoint: returns schema/file list

### Phase 3 — Real Infrastructure (Week 2)
- [ ] Real log streaming via SSE (`/v1/logs?node_id=xxx`)
- [ ] Node registration API (for self-hosted deployments)
- [ ] Health check aggregation across registered nodes

### Phase 4 — Production Hardening (Week 3-4)
- [ ] Email-based password reset
- [ ] Notification preferences stored in DB
- [ ] Audit log UI fully wired to real `/v1/audit-logs`
- [ ] Team management fully wired
- [ ] Usage export generates real CSV from DB
- [ ] Billing fully wired to Stripe (webhooks, subscription management)

---

## What "Go Live" Actually Means

**Minimal viable production portal:**
1. Users can log in, create API keys, and call the simulation API ✅
2. Dashboard shows real simulation history ✅ (when they have runs)
3. Playground works for testing ✅
4. Usage tracking works ✅
5. Billing via Stripe ✅ (Stripe integration exists)
6. Data connectors work for at least PostgreSQL + REST API (most common)
7. Clean, honest UI that doesn't show fake data

**What stays "coming soon" for V1:**
- AWS S3, GCS, Azure connectors (need cloud SDK packages)
- Snowflake, BigQuery (need enterprise licenses)
- Infrastructure scaling (Kubernetes-level work)
- 2FA, SSO
