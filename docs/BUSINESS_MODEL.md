---
icon: chart-line
description: Internal Codna product strategy, packaging, and go-to-market reference.
---

# Codna — Business Model

## What We Are

Codna is a **modular AI + decision compute runtime** built on a Mojo-powered engine that runs 95–112× faster than Python.

We replace a stack that most companies stitch together manually:

| What companies buy today | What Codna replaces it with |
|---|---|
| PyTorch + Triton | ML Training Engine + fused kernels |
| vLLM + TGI | Inference Engine + continuous batching |
| LangChain + LangGraph | Agent Engine + workflow engine |
| FAISS + Weaviate | Retrieval Engine + vector search |
| Airflow + Celery | Serving Engine + scheduler |
| Ray Distributed | Distributed collectives + model parallel |

One runtime. One API. One bill.

---

## Product Architecture

### The Runtime (what we sell)

444 Mojo libraries organized into 12 product engines:

**Core Engines** — available on all paid plans

| Engine | What it does |
|---|---|
| Decision Engine | Monte Carlo, distributions, optimization, risk scoring |
| Inference Engine | LLM inference, KV cache, flash attention, speculative decoding |
| Agent Engine | Tool calling, workflow DAGs, structured output, session memory |
| Retrieval Engine | Vector search, BM25, reranking, RAG pipelines |
| Optimization Engine | Convex, constrained, multi-objective, gradient-based solvers |
| Serving Engine | Continuous batching, scheduling, latency optimization, fault tolerance |

**Advanced Engines** — Pro and above

| Engine | What it does |
|---|---|
| Training Engine | Autograd, optimizers, LoRA, RLHF/DPO, distributed training |
| Data Engine | ETL, feature engineering, streaming pipelines, deduplication |
| Model Engine | Load, shard, adapt models — safetensors, GGUF, ONNX, HF |
| Cost Engine | Cost-aware routing, GPU/CPU placement, SLA-budget tradeoffs |

**Platform Engines** — Enterprise only

| Engine | What it does |
|---|---|
| Security & Governance Engine | Prompt injection, PII filtering, RBAC, audit logging, DP noise |
| Hybrid Intelligence Engine | ML + simulation + optimization + rules unified into one system |

---

## Pricing Tiers

### Free
- 500 simulations / month
- 60 requests / minute
- Core Decision Engine only
- No async jobs
- No webhooks
- Community support

### Developer — paid
- 10,000 simulations / month
- 300 requests / minute
- All 6 Core Engines
- Async jobs + webhook callbacks
- Up to 100,000 Monte Carlo runs per request
- Email support

### Pro — paid
- 100,000 simulations / month
- 1,000 requests / minute
- All 10 Core + Advanced Engines
- Data connectors (PostgreSQL, S3, REST APIs)
- Up to 1,000,000 Monte Carlo runs per request
- Priority support + SLA

### Enterprise — custom contract
- Unlimited simulations
- 10,000 requests / minute
- All 12 engines including Security & Governance + Hybrid Intelligence
- Dedicated deployment (cloud or on-prem)
- SSO / SAML
- Audit logs + compliance exports
- Custom data retention
- Dedicated SRE + integration support
- Custom SLA

---

## Revenue Streams

### 1. API subscriptions (primary)
Recurring monthly/annual subscription per organization. Checkout and billing via Stripe. Plan upgrades self-serve through the hosted account interface.

### 2. Compute overages
Usage above monthly simulation quota billed per additional billing unit. Metered via `usage_records` table, invoiced monthly.

### 3. Enterprise contracts
Annual contracts for unlimited usage, dedicated infrastructure, compliance add-ons, and professional services. Sales-assisted.

### 4. Managed deployments (future)
Single-tenant cloud deployments on AWS, GCP, or Azure provisioned and managed by Codna. Monthly infrastructure fee + platform fee.

### 5. Marketplace (future)
Third-party engine plugins, simulation templates, and industry-specific models. Revenue share with contributors.

---

## Distribution Channels

### Developer-led growth
- Open-core repo (ACL 1.0 license) — free self-hosting drives awareness
- Python SDK (`pip install algenta-sdk`)
- TypeScript / Node.js SDK (`npm install algenta-sdk`)
- CLI (`de simulate`, `de recommend`, `de job`)
- One-line self-host (`curl -fsSL https://codna.ai/install | bash`)

### AI-native distribution
- MCP server — Claude Desktop, Cursor, VS Code, Zed
- ChatGPT Custom Actions
- Azure AI Studio integration
- Google Colab examples
- LangChain / LangGraph tool wrappers

### No-code / low-code distribution
- n8n HTTP nodes
- Zapier actions
- Make (Integromat) webhooks
- Power Automate / Logic Apps OpenAPI connector

### Enterprise sales
- Direct outbound to AI/ML teams at mid-market and enterprise companies
- Partner channel via cloud marketplaces (AWS, GCP, Azure)

---

## Open-Core Strategy

Like Supabase, n8n, and Grafana — the framework is open, the engine is proprietary.

| Layer | License | Who gets it |
|---|---|---|
| API server, SDKs, CLI, integrations, docs content | ACL 1.0 (source-available) | Everyone |
| 444 Mojo math libraries (compiled binary) | Proprietary — free to run | All paying plans |
| Mojo engine source code | Proprietary | Enterprise contract only |
| Security & Governance Engine | Proprietary | Enterprise only |
| Hybrid Intelligence Engine | Proprietary | Enterprise only |

**ACL 1.0 terms:** Free for personal use, research, and organizations with < $5M annual revenue and < 50 employees. Commercial use requires a license from [licensing@codna.ai](mailto:licensing@codna.ai).

---

## Competitive Moat

### Speed
95–112× median speedup over Python. Max observed: 1,734×. This is the benchmark, not a claim — it comes from running 3,707 functions across 444 libraries head-to-head.

### Unification
Everything from tokenization to RL training to structured output to cost routing runs in the same runtime. No glue code. No inter-framework latency.

### The Hybrid Intelligence Engine
No competing product unifies ML prediction + physics simulation + optimization + symbolic rules into a single callable. This is the long-term defensible moat.

### Depth of coverage
444 domain libraries across ML/AI primitives, GenAI serving, distributed training, and decision science. Most ML platforms specialize in one layer. We cover all of them.

---

## Key Metrics to Track

| Metric | Why it matters |
|---|---|
| Monthly Active Organizations | Top-of-funnel health |
| Simulation volume (billing units/month) | Revenue proxy |
| Free → Developer conversion rate | PLG efficiency |
| Developer → Pro conversion rate | Revenue expansion |
| Net Revenue Retention | Enterprise health |
| Mojo speedup (median) | Product moat signal |
| API p50 / p99 latency | Serving quality |
| Webhook delivery success rate | Reliability signal |

---

## Go-To-Market Sequence

**Now — Land developers**
Ship the open-core repo. Make self-hosting trivially easy. Win the Python ML community with the benchmark.

**Next — Convert to hosted**
Hosted API removes ops burden. Free tier creates habit. Developer plan ($x/mo) is the conversion target.

**Then — Move upmarket**
Pro plan for ML teams running production workloads. Enterprise contracts for companies that need compliance, SSO, and SLAs.

**Later — Expand the platform**
Marketplace, managed deployments, cloud-native integrations, vertical templates.

---

## What We Are Not

- Not a model provider (we run your models, we don't train or host foundation models)
- Not a no-code tool (developers first, low-code is a channel not the product)
- Not a data warehouse (we process, not store)
- Not a monitoring platform (observability is a feature, not the product)

## Next step

Validate any packaging or go-to-market change against the current product registry and entitlement contracts before changing public copy.
