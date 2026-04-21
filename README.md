# Algenta Decision Engine

<p align="center">
  <strong>The open-core probabilistic decision engine.</strong><br>
  Run Monte Carlo simulations on any data. Get structured recommendations with SHA-256 auditability.<br>
  Use hosted at <a href="https://api.algenta.ai">api.algenta.ai</a> or self-host in minutes.
</p>

<p align="center">
  <a href="https://algenta.ai"><img src="https://img.shields.io/badge/website-algenta.ai-6B42FC" alt="Website"></a>
  <a href="https://docs.algenta.ai"><img src="https://img.shields.io/badge/docs-docs.algenta.ai-blue" alt="Docs"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-ACL_1.0-green" alt="License"></a>
  <a href="https://algenta.ai/discord"><img src="https://img.shields.io/badge/discord-join-7289DA" alt="Discord"></a>
</p>

---

## What is this?

Algenta is a **probabilistic simulation API** that quantifies uncertainty in any decision:

- Run **Monte Carlo / LHS / QMC / MCMC / Bootstrap / Sensitivity** simulations
- Define variables with any of **27 probability distributions**
- Get back: `recommended_action`, `confidence`, `expected_value`, `probability_of_loss`, VaR, CVaR, percentile distribution
- Every result is **SHA-256 hashed** for chain-of-custody auditability

**Works everywhere:** ChatGPT, Claude, Azure AI Studio, n8n, Zapier, Make, Python, TypeScript, Google Colab.

---

## One-line self-host

```bash
curl -fsSL https://algenta.ai/install | bash
```

Or with Docker Compose directly:

```bash
curl -fsSL https://raw.githubusercontent.com/algenta/decision-engine/main/infra/docker/docker-compose.selfhosted.yml -o docker-compose.yml
# Edit .env (auto-generated on first run)
docker compose up -d
```

**Portal:** http://localhost:3000 | **API:** http://localhost:8000 | **Docs:** http://localhost:8000/docs

---

## Quick API example

```bash
# Hosted (get your key at https://app.algenta.ai/dashboard/api-keys)
curl -X POST https://api.algenta.ai/v1/simulate \
  -H "Authorization: Bearer de_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "runs": 50000,
    "scenario": {
      "variables": {
        "revenue":     {"low": 80000,  "high": 250000},
        "cost":        {"low": 40000,  "high": 120000},
        "growth_rate": {"low": 0.05,   "high": 0.35}
      },
      "objective": "maximize_net_value"
    }
  }'
```

Response:
```json
{
  "recommended_action": "proceed",
  "confidence": 0.84,
  "rationale": "Expected value is positive in 84% of scenarios. Mean: $127,450.",
  "metrics": {
    "expected_value": 127450,
    "probability_of_loss": 0.16,
    "var_95": -42300
  },
  "result_hash": "sha256:786eef695be285f3..."
}
```

---

## SDK

### Python
```bash
pip install algenta-sdk
```

```python
from algenta import AlgentaClient

client = AlgentaClient(api_key="de_live_...")
result = client.simulate(
    mode="auto",
    runs=50000,
    scenario={
        "variables": {"revenue": {"low": 80000, "high": 250000}},
        "objective": "maximize_net_value",
    }
)
print(result.recommended_action, result.confidence)
```

### TypeScript / Node.js
```bash
npm install algenta-sdk
```

```typescript
import { AlgentaClient } from 'algenta-sdk';

const client = new AlgentaClient({ apiKey: 'de_live_...' });
const result = await client.simulate({
  mode: 'auto',
  runs: 50000,
  scenario: {
    variables: { revenue: { low: 80000, high: 250000 } },
    objective: 'maximize_net_value',
  },
});
console.log(result.recommended_action, result.confidence);
```

---

## AI integration (MCP — Claude, Cursor, Zed)

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "algenta": {
      "command": "python",
      "args": ["-m", "apps.mcp_server.server"],
      "env": {
        "ALGENTA_API_KEY": "de_live_...",
        "ALGENTA_BASE_URL": "https://api.algenta.ai"
      }
    }
  }
}
```

Claude can then run simulations, analyze risks, and get recommendations directly in conversation.
Full guide: [examples/claude-desktop/README.md](examples/claude-desktop/README.md)

---

## Local API Key Self-Check

To verify that a real API key can power the local runtime on your machine, run:

```bash
DE_API_KEY=de_live_... python3 scripts/verify_local_api_key_runtime.py
```

To point at a specific API base URL:

```bash
DE_API_KEY=de_live_... DE_BASE_URL=https://api.algenta.ai python3 scripts/verify_local_api_key_runtime.py
```

This performs a real health check, device-license exchange, local credit seeding, daemon auto-start, and a real local runtime execution.

---

## Simulation models

| Model | Description |
|-------|-------------|
| `monte_carlo` | Standard random sampling (default) |
| `qmc_sobol` | Quasi-random Sobol sequences — better coverage |
| `lhs` | Latin Hypercube Sampling — stratified coverage |
| `bootstrap` | Non-parametric resampling from historical data |
| `scenario` | Discrete scenario comparison (base/optimistic/pessimistic) |
| `sensitivity` | Sobol sensitivity indices — identify key drivers |
| `mcmc` | Metropolis-Hastings Bayesian MCMC |

---

## Integrations

| Platform | Guide |
|----------|-------|
| ChatGPT Custom Actions | [examples/chatgpt-actions/](examples/chatgpt-actions/) |
| Claude and Codex (MCP) | [examples/claude-desktop/](examples/claude-desktop/) |
| Azure AI Foundry / Studio | [examples/azure-ai-studio/](examples/azure-ai-studio/) |
| n8n | [examples/n8n/](examples/n8n/) |
| Local Runtime | [examples/local-runtime/](examples/local-runtime/) |
| Zapier | [examples/zapier/](examples/zapier/) |
| Make (Integromat) | [examples/make/](examples/make/) |
| Power Automate | [examples/power-automate/](examples/power-automate/) |
| Google Colab | [examples/google-colab/](examples/google-colab/) |
| LangChain / LangGraph | [examples/langgraph/](examples/langgraph/) |

---

## Architecture

```
┌── Portal UI (Next.js)  ── http://localhost:3000
├── API Server (FastAPI)  ── http://localhost:8000
├── Worker (async jobs)
├── PostgreSQL 16
├── Redis 7
└── MinIO (S3-compatible object storage)
```

- Multi-tenant: every org is isolated by `org_id` on every row
- Per-org quota + rate limiting via Redis
- SHA-256 chain-of-custody: `request_hash` → `result_hash` on every simulation
- Mojo simulation engine: compiled binary (proprietary) + Python fallback

---

## Mojo Library Ecosystem

The compute path runs on **189 native Mojo libraries** — zero Python, zero external dependencies at runtime.

| Metric | Value |
|--------|-------|
| 🔥 **Mojo library modules** | **189** |
| 📦 **Python packages replaced** | **75+** |
| ✅ **Test assertions** | **1,100+** |
| 🧪 **Test files** | **64** |
| 📐 **Total LOC (Mojo)** | **~49,800** |
| 🌊 **Build waves** | **54** |
| 🎯 **External deps in compute path** | **0** |

### What's inside

| Domain | Count | Highlights |
|--------|-------|------------|
| **Simulation engines** | 7 | Monte Carlo, MCMC, LHS, QMC-Sobol, Bootstrap, Scenario, Sensitivity |
| **Probability distributions** | 22 | All PhD-grade accurate (10k-run statistical tests) |
| **Statistics & probability** | 12 | Hypothesis testing, Bayesian inference, copulas, bootstrap CI |
| **Mathematics & numerical** | 16 | Linear algebra, FFT, ODE/PDE, root finding, integration |
| **Machine learning** | 8 | Classifiers, clustering, regression, preprocessing, metrics |
| **Cryptography** | 9 | SHA-256, HMAC, Base64, UUID, ChaCha20, PBKDF2, AES S-box |
| **Data processing** | 3 | CSV parser, DataFrame, type conversion |
| **Compression** | 4 | RLE, LZ77, Huffman, delta encoding |
| **Text & NLP** | 7 | Regex, fuzzy match, tokenizer, sentiment, string distance |
| **Finance & risk** | 4 | Black-Scholes, VaR/CVaR, NPV/IRR, options pricing |
| **Domain-specific** | 13 | Supply chain, queueing theory, anomaly detection, epidemiology |
| **+ 80 more** | ... | Graph algorithms, physics, game theory, control systems, etc. |

Full inventory: [plans/MOJO_LIBRARY_EXPANSION.md](plans/MOJO_LIBRARY_EXPANSION.md)

---

## Open-core model

Like **Supabase**, **n8n**, and **Reown** — the framework is open, the engine core is proprietary:

| Component | Status |
|-----------|--------|
| API server, SDKs, MCP, integrations, docs content | Open source (ACL 1.0) |
| Simulation engine binary | Free to run, proprietary |
| Mojo engine source | Proprietary |

**Community use** (personal, research, <$5M revenue, <50 employees): free self-hosting under ACL 1.0.
**Commercial self-hosting**: [licensing@algenta.ai](mailto:licensing@algenta.ai)

---

## Development

```bash
git clone https://github.com/algenta/decision-engine
cd decision-engine
cp .env.example .env

pip install -r requirements-dev.txt
make dev-api      # API on :8000

pytest tests/ -v  # Run tests
```

The web interface is maintained outside this repository.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

---

## License

[Algenta Community License 1.0](./LICENSE) — source-available, free for community use.
Commercial self-hosting requires a license: [algenta.ai/pricing](https://algenta.ai/pricing)
