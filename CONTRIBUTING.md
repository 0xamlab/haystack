# Contributing to Algenta Decision Engine

Thank you for your interest in contributing! We follow the open-core model:
- **Framework, API, portal, SDKs, integrations** — open to contributions
- **Mojo simulation engine core** (`mojo/engine/`) — proprietary, not open for contribution

---

## What you can contribute

| Area | Status | Notes |
|------|--------|-------|
| API server (FastAPI) | ✅ Open | Bug fixes, new endpoints |
| Portal UI (Next.js) | ✅ Open | UI improvements, new pages |
| Python SDK | ✅ Open | New methods, type fixes |
| TypeScript SDK | ✅ Open | New methods, type fixes |
| MCP server | ✅ Open | New tools, transport improvements |
| Integration examples | ✅ Open | New platforms, fixes |
| Documentation | ✅ Open | Corrections, new guides |
| Tests | ✅ Open | More coverage is always welcome |
| Distribution schemas | ✅ Open | New distribution validators |
| Simulation engine core | 🔒 Closed | Proprietary Mojo code |

---

## Getting started

### 1. Fork and clone

```bash
git clone https://github.com/YOUR_USERNAME/decision-engine
cd decision-engine
```

### 2. Set up development environment

```bash
cp .env.example .env
pip install -r requirements-dev.txt

# Start infrastructure
docker compose -f infra/docker/docker-compose.yml up -d postgres redis

# Run migrations
PYTHONPATH=. python -m alembic -c apps/api_server/alembic.ini upgrade head

# Seed dev data
PYTHONPATH=. python scripts/seed_dev.py

# Start API (hot reload)
make dev-api

# Start portal (new terminal)
make dev-portal
```

### 3. Run tests

```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/unit/test_auth_service.py -v

# With coverage
pytest tests/ --cov=apps/api_server --cov-report=term-missing
```

---

## Development workflow

### Branch naming
- `feat/short-description` — New feature
- `fix/short-description` — Bug fix
- `docs/short-description` — Documentation only
- `refactor/short-description` — Code cleanup

### Commit messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
feat(api): add batch simulation endpoint
fix(portal): fix billing badge pill shape
docs(self-hosting): add Docker Compose guide
refactor(sdk): simplify retry logic
```

### Pull request checklist
- [ ] Tests pass locally (`pytest tests/ -v`)
- [ ] New features have tests
- [ ] Documentation updated if needed
- [ ] No hardcoded credentials or secrets
- [ ] `mojo/engine/` files NOT modified (proprietary)

---

## Contributor License Agreement

By submitting a PR, you agree that your contribution is licensed under the
[Algenta Community License](./LICENSE) and you grant Algenta, Inc. a perpetual,
worldwide, irrevocable license to use your contribution in both open-source
and commercial versions of this software.

If your organization requires a CLA on file, contact: cla@algenta.ai

---

## Code style

**Python:**
```bash
# Format
black apps/ tests/ scripts/
isort apps/ tests/ scripts/

# Lint
ruff check apps/ tests/
mypy apps/api_server/ --ignore-missing-imports
```

**TypeScript:**
```bash
cd apps/portal && npm run lint
```

All CI checks must pass. Pre-commit hooks are configured in `.pre-commit-config.yaml`.

---

## Reporting issues

- **Security vulnerabilities** → security@algenta.ai (do NOT open public issues)
- **Bugs** → [GitHub Issues](https://github.com/algenta/decision-engine/issues) with the `bug` label
- **Feature requests** → [GitHub Discussions](https://github.com/algenta/decision-engine/discussions)
- **Questions** → [Discord](https://algenta.ai/discord)

---

## Community

- Discord: https://algenta.ai/discord
- Twitter/X: @algenta_ai
- Docs: https://docs.algenta.ai
- Email: community@algenta.ai
