---
sidebar_position: 10
---

# Self-Hosting

Run the full Algenta Decision Engine on your own infrastructure — same engine, same API, your own data.

## Two deployment modes

| Mode | Description | When to use |
|------|-------------|-------------|
| **Hosted** | Use `https://api.algenta.ai` with your API key | Default — no setup required |
| **Self-hosted** | Run the engine on your own servers | Data sovereignty, air-gap, enterprise compliance |

When self-hosted, **all client code still works unchanged** — just set `ALGENTA_BASE_URL` to your own server.

---

## Requirements

- **Python 3.12+**
- **PostgreSQL 14+**
- **Redis 7+**
- **Node.js 20+** (optional, only if you need Node-based tooling alongside this repo)
- **Docker + Docker Compose** (optional — or run natively)

---

## Quick Start (without Docker)

### 1. Clone and configure

```bash
git clone https://github.com/algenta/decision-engine
cd decision-engine
cp .env.example .env
```

Edit `.env` — at minimum set your PostgreSQL URL:

```bash
DATABASE_URL=postgresql+asyncpg://YOUR_USER:@localhost:5432/algenta
DATABASE_URL_SYNC=postgresql://YOUR_USER:@localhost:5432/algenta
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=change-me-use-256-bit-random-value
```

### 2. Install Python dependencies

```bash
pip install -r requirements-dev.txt
```

### 3. Create database and run migrations

```bash
createdb algenta 2>/dev/null || true
PYTHONPATH=. python -m alembic -c apps/api_server/alembic.ini upgrade head
```

### 4. Seed an admin org + API key

```bash
PYTHONPATH=. python scripts/seed_dev.py
```

This creates:
- An organization: `Dev Org`
- A user: `dev@example.com`
- An API key printed to stdout: `de_test_...`

**Save the printed API key** — it is shown only once.

### 5. Start the API server

```bash
make dev-api
# or:
PYTHONPATH=. uvicorn apps.api_server.main:app --port 8000 --reload
```

### 6. Test your key

```bash
curl -X POST http://localhost:8000/v1/simulate \
  -H "Authorization: Bearer de_test_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "runs": 10000,
    "scenario": {
      "variables": {"revenue": {"low": 80000, "high": 200000}},
      "objective": "maximize_net_value"
    }
  }'
```

Expected: `{"recommended_action": "proceed", "confidence": 0.84, ...}`

### 7. Connect an external web interface (optional)

This repository does not include a bundled web interface. Point your external UI at `http://localhost:8000` after the API is running.

---

## Quick Start (Docker Compose)

```bash
cp .env.example .env
# Edit .env with your settings

docker compose -f infra/docker/docker-compose.yml up --build -d

# Run migrations inside the container
docker compose -f infra/docker/docker-compose.yml exec api \
  python -m alembic -c apps/api_server/alembic.ini upgrade head

# Seed dev data
docker compose -f infra/docker/docker-compose.yml exec api \
  python scripts/seed_dev.py
```

---

## Connecting SDKs to your self-hosted instance

All SDKs and integrations accept a `base_url` override:

### Python SDK
```python
from decision_engine import DecisionEngineClient

client = DecisionEngineClient(
    api_key="de_test_YOUR_KEY",
    base_url="http://localhost:8000",  # your server
)
result = client.simulate(mode="auto", runs=10000, scenario={...})
```

### TypeScript SDK
```typescript
import { DecisionEngineClient } from 'algenta-sdk';

const client = new DecisionEngineClient({
  apiKey: 'de_test_YOUR_KEY',
  baseUrl: 'http://localhost:8000',
});
```

### MCP Server (Claude Desktop)
```json
{
  "mcpServers": {
    "algenta-local": {
      "command": "/path/to/mcp_venv/bin/python",
      "args": ["-m", "apps.mcp_server.server"],
      "env": {
        "ALGENTA_API_KEY": "de_test_YOUR_KEY",
        "ALGENTA_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

### External web interface
Set your UI's API base URL to `http://localhost:8000`.

---

## API Key management

After seeding, you can create additional keys via the API:

```bash
# Create a new key
curl -X POST http://localhost:8000/v1/api-keys \
  -H "Authorization: Bearer de_test_SEED_KEY" \
  -H "Content-Type: application/json" \
  -d '{"label": "my-integration"}'

# List keys
curl http://localhost:8000/v1/api-keys \
  -H "Authorization: Bearer de_test_SEED_KEY"

# Revoke a key
curl -X DELETE http://localhost:8000/v1/api-keys/KEY_ID \
  -H "Authorization: Bearer de_test_SEED_KEY"
```

Or use your external account interface against the same local API server.

---

## Environment variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://...`) | ✅ |
| `DATABASE_URL_SYNC` | PostgreSQL sync URL for migrations | ✅ |
| `REDIS_URL` | Redis URL | ✅ |
| `JWT_SECRET` | 256-bit random secret for JWT signing | ✅ |
| `API_ENV` | `development` or `production` | |
| `MOJO_BINARY_PATH` | Path to compiled Mojo binary | `./mojo_build/simulate` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000` |
| `STRIPE_SECRET_KEY` | Stripe key (skip for self-hosted, billing disabled) | |
| `S3_BUCKET_NAME` | MinIO/S3 bucket for large result storage | |
| `S3_ENDPOINT_URL` | MinIO endpoint (self-hosted object store) | |

---

## Production checklist

- [ ] Set a strong `JWT_SECRET` (256-bit random)
- [ ] Set `API_ENV=production`
- [ ] Configure TLS (nginx/Caddy in front of port 8000)
- [ ] Set `CORS_ORIGINS=https://your-domain.com`
- [ ] Configure PostgreSQL backups
- [ ] Set up Redis persistence (`appendonly yes`)
- [ ] Enable `/metrics` endpoint monitoring (Prometheus-compatible)
- [ ] Rotate the seed API key and create org-specific keys
- [ ] Review `QUOTA_*` env vars for your usage limits

---

## Architecture overview

```
┌── Portal UI (Next.js :3000) ──────────────────────────────┐
│   └── Calls API with Bearer token                         │
└────────────────────────────────────────────────────────────┘
                           │
┌── API Server (FastAPI :8000) ─────────────────────────────┐
│   ├── Auth: Bearer token → org_id lookup (Redis → Postgres)│
│   ├── Quota check (per org, per billing period)            │
│   ├── Rate limit (Redis, per org)                          │
│   ├── Simulation engine (Mojo binary or Python fallback)  │
│   └── SHA-256 chain-of-custody on every result             │
└────────────────────────────────────────────────────────────┘
        │               │
┌─ Postgres ─┐  ┌─ Redis ─┐  ┌─ MinIO/S3 ─┐
│ All orgs   │  │ Cache   │  │ Results    │
│ row-level  │  │ Rate    │  │ /org_id/   │
│ isolation  │  │ limits  │  │ run_id     │
└────────────┘  └─────────┘  └────────────┘
```
